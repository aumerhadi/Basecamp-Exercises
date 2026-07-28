"""`/summarize` routes — the summarization queue."""

from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, status

from ..db import get_connection
from ..models import SummarizeJob, SummarizeJobCreated, SummarizeJobSummary
from ..repository import SummarizeQueueRepository

router = APIRouter(prefix="/summarize", tags=["summarize"])


def get_queue(
    connection: Annotated[sqlite3.Connection, Depends(get_connection)],
) -> SummarizeQueueRepository:
    return SummarizeQueueRepository(connection)


Queue = Annotated[SummarizeQueueRepository, Depends(get_queue)]
JobId = Annotated[int, Path(description="Summarization id.", examples=[1])]


@router.post(
    "",
    response_model=SummarizeJobCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Queue a summarization job",
    description=(
        "Takes a JSON array of e-mail ids, stores it in the `summarize_queue` table and"
        " returns the summarization id. The job starts with an empty `summary`; poll"
        " `GET /summarize/{id}` for the result."
    ),
)
@router.post("/", response_model=SummarizeJobCreated, include_in_schema=False,
             status_code=status.HTTP_201_CREATED)
def enqueue_summarization(
    queue: Queue,
    email_ids: Annotated[
        list[int],
        Body(description="E-mail ids to summarize.", examples=[[1, 2, 3]]),
    ],
) -> SummarizeJobCreated:
    if not email_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Expected a non-empty JSON array of e-mail ids",
        )
    return SummarizeJobCreated(id=queue.enqueue(email_ids))


@router.get(
    "",
    response_model=list[SummarizeJob],
    summary="List pending summarization jobs",
    description="Queue records whose `summary` is still empty, oldest first.",
)
@router.get("/", response_model=list[SummarizeJob], include_in_schema=False)
def list_pending(queue: Queue) -> list[SummarizeJob]:
    return queue.list_pending()


@router.get(
    "/{job_id}",
    response_model=SummarizeJobSummary,
    summary="Get a job's summary",
    description="The `summary` field of the queued job; null while it is still pending.",
    responses={status.HTTP_404_NOT_FOUND: {"description": "No job with that id"}},
)
def get_summary(queue: Queue, job_id: JobId) -> SummarizeJobSummary:
    job = queue.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Summarization {job_id} not found",
        )
    return SummarizeJobSummary(id=job.id, summary=job.summary)
