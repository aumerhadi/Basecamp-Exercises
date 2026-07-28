"""SQLite storage: connection handling and schema bootstrap."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

# ../../data/emails.db — the repo-root data folder, shared with the rest of the project.
DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "emails.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS emails (
    id            INTEGER PRIMARY KEY,
    sender        TEXT    NOT NULL,
    recipient     TEXT    NOT NULL,
    subject       TEXT    NOT NULL,
    body          TEXT    NOT NULL,
    priority      TEXT    NOT NULL CHECK (priority IN ('low', 'medium', 'critical')),
    date          TEXT    NOT NULL,
    time          TEXT    NOT NULL,
    high_priority INTEGER NOT NULL,
    sent_at       TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_emails_sent_at ON emails (sent_at DESC);

CREATE TABLE IF NOT EXISTS summarize_queue (
    id         INTEGER PRIMARY KEY,
    -- JSON array of e-mail ids: SQLite has no list type, and the queue only
    -- ever reads the set back as a whole.
    email_ids  TEXT    NOT NULL,
    summary    TEXT,
    created_at TEXT    NOT NULL
);
-- Partial index: the pending listing is the only hot query over this table.
CREATE INDEX IF NOT EXISTS idx_summarize_queue_pending
    ON summarize_queue (id) WHERE summary IS NULL OR summary = '';

CREATE TABLE IF NOT EXISTS agenda_queue (
    id         INTEGER PRIMARY KEY,
    -- One plan per calendar day. `day` is YYYY-MM-DD derived from `date`: it is
    -- what lookups match on and what makes the day unique, while `date` keeps
    -- the full timestamp the contract asks for. UNIQUE indexes it for free.
    day        TEXT    NOT NULL UNIQUE,
    date       TEXT    NOT NULL,
    -- JSON array of e-mail ids, as in summarize_queue; the e-mails themselves
    -- are resolved from the emails table on read.
    email_ids  TEXT    NOT NULL,
    meeting    TEXT    NOT NULL,
    support    TEXT    NOT NULL,
    created_at TEXT    NOT NULL
);
"""


def db_path() -> Path:
    override = os.getenv("EMAILS_DB_PATH")
    return Path(override) if override else DEFAULT_DB_PATH


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Open a connection with the conventions the repository relies on."""
    path = path or db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: FastAPI resolves the sync dependency in a
    # threadpool worker and may run the handler on another thread. The
    # connection still belongs to a single request and is never used
    # concurrently, and the driver is built in serialized mode
    # (sqlite3.threadsafety == 3), so sequential thread hops are safe.
    connection = sqlite3.connect(path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    # SQLite's own LIKE/lower() fold ASCII only; `casefold` keeps search
    # Unicode-aware and identical to Email.matches().
    connection.create_function("casefold", 1, str.casefold, deterministic=True)
    # WAL lets reads continue while an import writes.
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def init_db(path: Path | None = None) -> None:
    """Create the database file and schema if they do not exist yet."""
    connection = connect(path)
    try:
        with connection:
            connection.executescript(SCHEMA)
    finally:
        connection.close()


def get_connection() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency — one connection per request.

    Sync endpoints run in a threadpool, so a shared connection would be used
    across threads; a short-lived per-request one sidesteps that entirely.
    """
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()
