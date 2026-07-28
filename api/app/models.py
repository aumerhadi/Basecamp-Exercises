"""Pydantic models describing the e-mail data contract."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# `28-Jul-2026` / `13:53` — the literal formats named in the data contract.
DATE_FORMAT = "%d-%b-%Y"
TIME_FORMAT = "%H:%M"
DATE_PATTERN = r"^\d{2}-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{4}$"
TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    CRITICAL = "critical"


class Email(BaseModel):
    """A single e-mail.

    Field names are snake_case in Python and serialised under the contract's
    aliases (`from`, `to`, `highPriority`) — `from` is a reserved word, so it
    cannot be a plain attribute name.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: int = Field(examples=[1])
    sender: str = Field(alias="from", examples=["test@gmail.com"])
    recipient: str = Field(alias="to", examples=["test@gmail.com"])
    subject: str = Field(examples=["Critical Bug"])
    body: str = Field(examples=["Email text"])
    priority: Priority = Field(examples=[Priority.CRITICAL])
    date: str = Field(pattern=DATE_PATTERN, examples=["28-Jul-2026"])
    time: str = Field(pattern=TIME_PATTERN, examples=["13:53"])
    high_priority: bool = Field(alias="highPriority", examples=[True])

    @model_validator(mode="before")
    @classmethod
    def _derive_high_priority(cls, data: Any) -> Any:
        """Default `highPriority` from `priority` when the source omits it."""
        if not isinstance(data, dict):
            return data
        if data.get("highPriority") is None and data.get("high_priority") is None:
            return {**data, "highPriority": data.get("priority") == Priority.CRITICAL.value}
        return data

    @property
    def sent_at(self) -> datetime:
        """`date` + `time` as a single value, for sorting."""
        return datetime.strptime(f"{self.date} {self.time}", f"{DATE_FORMAT} {TIME_FORMAT}")

    def matches(self, query: str) -> bool:
        """Case-insensitive substring search over subject and body."""
        needle = query.casefold()
        return needle in self.subject.casefold() or needle in self.body.casefold()


class ImportResult(BaseModel):
    """Result of `POST /emails/import`."""

    model_config = ConfigDict(populate_by_name=True)

    received: int = Field(description="E-mails found in the uploaded file.")
    inserted: int = Field(description="Ids that did not exist before.")
    updated: int = Field(description="Ids that already existed and were overwritten.")
    email_ids: list[int] = Field(alias="emailIds")


class EmailSummary(BaseModel):
    """Result of `GET /emails/summarize`."""

    model_config = ConfigDict(populate_by_name=True)

    email_ids: list[int] = Field(alias="emailIds")
    count: int
    summary: str | None = Field(
        default=None,
        description="Generated summary; null while the summariser is a stub.",
    )
    status: Literal["ok", "not_implemented"] = "not_implemented"


class SummarizeJob(BaseModel):
    """A row of the `summarize_queue` table."""

    model_config = ConfigDict(populate_by_name=True)

    id: int = Field(examples=[1], description="Summarization id.")
    email_ids: list[int] = Field(alias="emailIds", examples=[[1, 2, 3]])
    summary: str | None = Field(
        default=None,
        description="Generated summary; null or empty while the job is pending.",
    )
    created_at: datetime = Field(alias="createdAt")


class SummarizeJobCreated(BaseModel):
    """Result of `POST /summarize` — the id to poll for the summary."""

    id: int = Field(examples=[1], description="Summarization id.")


class SummarizeJobSummary(BaseModel):
    """Result of `GET /summarize/{id}` — the queued job's `summary` field."""

    id: int = Field(examples=[1], description="Summarization id.")
    summary: str | None = Field(
        default=None,
        description="Generated summary; null or empty while the job is pending.",
    )
