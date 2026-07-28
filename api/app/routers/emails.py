"""`/emails` routes."""

from __future__ import annotations

import json
import sqlite3
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, UploadFile, status
from pydantic import ValidationError

from ..db import get_connection
from ..models import Email, EmailSummary, ImportResult, Priority
from ..repository import EmailRepository
from ..summarizer import summarize

router = APIRouter(prefix="/emails", tags=["emails"])

MAX_IMPORT_BYTES = 5 * 1024 * 1024


def get_repository(
    connection: Annotated[sqlite3.Connection, Depends(get_connection)],
) -> EmailRepository:
    return EmailRepository(connection)


Repo = Annotated[EmailRepository, Depends(get_repository)]
SearchQuery = Annotated[
    str | None,
    Query(description="Case-insensitive search over subject and body.", examples=["bug"]),
]
PriorityFilter = Annotated[Priority | None, Query(description="Keep only this priority.")]


@router.post(
    "/import",
    response_model=ImportResult,
    summary="Import e-mails from a JSON file",
    description=(
        "Upload a JSON file holding an array of e-mails (or a single e-mail object) in the"
        " standard data contract. Existing ids are overwritten, so re-importing the same"
        " file is idempotent. The whole file is validated before anything is written."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "The upload is not valid JSON"},
        status.HTTP_413_CONTENT_TOO_LARGE: {"description": "File over 5 MB"},
    },
)
async def import_emails(
    repo: Repo,
    file: Annotated[UploadFile, File(description="JSON file of e-mails.")],
) -> ImportResult:
    payload = await file.read(MAX_IMPORT_BYTES + 1)
    if len(payload) > MAX_IMPORT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File exceeds the {MAX_IMPORT_BYTES // (1024 * 1024)} MB import limit",
        )

    try:
        parsed: Any = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Uploaded file is not valid JSON: {error}",
        ) from error

    items = [parsed] if isinstance(parsed, dict) else parsed
    if not isinstance(items, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expected a JSON array of e-mails, or a single e-mail object",
        )

    # Validate everything up front so a bad item late in the file writes nothing.
    emails: list[Email] = []
    errors: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        try:
            emails.append(Email.model_validate(item))
        except ValidationError as error:
            errors.extend(
                {"loc": ["body", index, *problem["loc"]], "msg": problem["msg"]}
                for problem in error.errors()
            )
    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=errors)

    inserted, updated = repo.upsert_many(emails)
    return ImportResult(
        received=len(emails),
        inserted=inserted,
        updated=updated,
        email_ids=[email.id for email in emails],
    )


# Registered before `/{email_id}` — otherwise the path parameter swallows
# `/emails/summarize` and the request fails validation instead of routing here.
@router.get(
    "/summarize",
    response_model=EmailSummary,
    summary="Summarize e-mails",
    description="Summarizes the matching e-mails. The summariser itself is not implemented yet.",
)
def summarize_emails(
    repo: Repo,
    q: SearchQuery = None,
    priority: PriorityFilter = None,
    ids: Annotated[
        list[int] | None,
        Query(description="Restrict to these e-mail ids; omit for all matches."),
    ] = None,
) -> EmailSummary:
    emails = repo.list(q=q, priority=priority, ids=ids)
    summary = summarize(emails)
    return EmailSummary(
        email_ids=[email.id for email in emails],
        count=len(emails),
        summary=summary,
        status="ok" if summary is not None else "not_implemented",
    )


@router.get(
    "",
    response_model=list[Email],
    summary="List or search e-mails",
    description="Returns all e-mails, newest first. Pass `q` to search subject and body.",
)
@router.get("/", response_model=list[Email], include_in_schema=False)
def list_emails(
    repo: Repo,
    q: SearchQuery = None,
    priority: PriorityFilter = None,
) -> list[Email]:
    return repo.list(q=q, priority=priority)


@router.get(
    "/{email_id}",
    response_model=Email,
    summary="Get an e-mail by id",
    responses={status.HTTP_404_NOT_FOUND: {"description": "No e-mail with that id"}},
)
def get_email(
    repo: Repo,
    email_id: Annotated[int, Path(description="E-mail id.", examples=[1])],
) -> Email:
    email = repo.get(email_id)
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"E-mail {email_id} not found",
        )
    return email
