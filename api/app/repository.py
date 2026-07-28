"""SQLite-backed stores: the e-mail table and the summarization queue."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone

from .models import Email, Priority, SummarizeJob

COLUMNS = (
    "id, sender, recipient, subject, body, priority, date, time, high_priority, sent_at"
)

UPSERT = f"""
INSERT INTO emails ({COLUMNS})
VALUES (:id, :sender, :recipient, :subject, :body, :priority, :date, :time,
        :high_priority, :sent_at)
ON CONFLICT(id) DO UPDATE SET
    sender        = excluded.sender,
    recipient     = excluded.recipient,
    subject       = excluded.subject,
    body          = excluded.body,
    priority      = excluded.priority,
    date          = excluded.date,
    time          = excluded.time,
    high_priority = excluded.high_priority,
    sent_at       = excluded.sent_at
"""


def escape_like(value: str) -> str:
    """Escape LIKE wildcards so a query is matched literally, as `in` would."""
    for char in ("\\", "%", "_"):
        value = value.replace(char, f"\\{char}")
    return value


class EmailRepository:
    """Queries over the `emails` table. One instance per request/connection."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def list(
        self,
        q: str | None = None,
        priority: Priority | None = None,
        ids: Iterable[int] | None = None,
    ) -> list[Email]:
        clauses: list[str] = []
        params: dict[str, object] = {}

        if q is not None:
            # casefold() is registered in db.connect(); ESCAPE keeps % and _ literal.
            clauses.append(
                "(casefold(subject) LIKE casefold(:q) ESCAPE '\\'"
                " OR casefold(body) LIKE casefold(:q) ESCAPE '\\')"
            )
            params["q"] = f"%{escape_like(q)}%"

        if priority is not None:
            clauses.append("priority = :priority")
            params["priority"] = priority.value

        if ids is not None:
            wanted = list(ids)
            if not wanted:
                return []
            placeholders = ", ".join(f":id{index}" for index in range(len(wanted)))
            clauses.append(f"id IN ({placeholders})")
            params.update({f"id{index}": value for index, value in enumerate(wanted)})

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._connection.execute(
            f"SELECT {COLUMNS} FROM emails{where} ORDER BY sent_at DESC, id DESC", params
        ).fetchall()
        return [_row_to_email(row) for row in rows]

    def max_id(self) -> int:
        """Highest id in the table, or 0 when it is empty."""
        return self._connection.execute(
            "SELECT COALESCE(MAX(id), 0) AS value FROM emails"
        ).fetchone()["value"]

    def get(self, email_id: int) -> Email | None:
        row = self._connection.execute(
            f"SELECT {COLUMNS} FROM emails WHERE id = ?", (email_id,)
        ).fetchone()
        return _row_to_email(row) if row is not None else None

    def upsert_many(self, emails: Sequence[Email]) -> tuple[int, int]:
        """Insert or replace `emails` by id. Returns `(inserted, updated)`."""
        if not emails:
            return (0, 0)

        incoming = {email.id for email in emails}
        placeholders = ", ".join("?" * len(incoming))
        existing = {
            row["id"]
            for row in self._connection.execute(
                f"SELECT id FROM emails WHERE id IN ({placeholders})", tuple(incoming)
            )
        }

        with self._connection:  # one transaction — a failure writes nothing
            self._connection.executemany(UPSERT, [_email_to_params(e) for e in emails])

        updated = len(existing)
        return (len(incoming) - updated, updated)


QUEUE_COLUMNS = "id, email_ids, summary, created_at"

# NULL and '' both count as "not summarised yet": nothing forbids a worker from
# writing an empty string, and a pending job must not disappear from the queue.
PENDING = "(summary IS NULL OR summary = '')"


class SummarizeQueueRepository:
    """Queries over the `summarize_queue` table. One instance per connection."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def enqueue(self, email_ids: Sequence[int]) -> int:
        """Queue a summarization job. Returns its id."""
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connection:
            cursor = self._connection.execute(
                "INSERT INTO summarize_queue (email_ids, summary, created_at)"
                " VALUES (?, NULL, ?)",
                (json.dumps(list(email_ids)), created_at),
            )
        return int(cursor.lastrowid)

    def list_pending(self) -> list[SummarizeJob]:
        """Jobs whose `summary` is still empty, oldest first."""
        rows = self._connection.execute(
            f"SELECT {QUEUE_COLUMNS} FROM summarize_queue WHERE {PENDING} ORDER BY id"
        ).fetchall()
        return [_row_to_job(row) for row in rows]

    def get(self, job_id: int) -> SummarizeJob | None:
        row = self._connection.execute(
            f"SELECT {QUEUE_COLUMNS} FROM summarize_queue WHERE id = ?", (job_id,)
        ).fetchone()
        return _row_to_job(row) if row is not None else None


def _row_to_job(row: sqlite3.Row) -> SummarizeJob:
    return SummarizeJob(
        id=row["id"],
        email_ids=json.loads(row["email_ids"]),
        summary=row["summary"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _row_to_email(row: sqlite3.Row) -> Email:
    return Email(
        id=row["id"],
        sender=row["sender"],
        recipient=row["recipient"],
        subject=row["subject"],
        body=row["body"],
        priority=Priority(row["priority"]),
        date=row["date"],
        time=row["time"],
        high_priority=bool(row["high_priority"]),
    )


def _email_to_params(email: Email) -> dict[str, object]:
    return {
        "id": email.id,
        "sender": email.sender,
        "recipient": email.recipient,
        "subject": email.subject,
        "body": email.body,
        "priority": email.priority.value,
        "date": email.date,
        "time": email.time,
        "high_priority": int(email.high_priority),
        # Derived: the contract's DD-Mon-YYYY does not sort, ISO does.
        "sent_at": email.sent_at.isoformat(),
    }
