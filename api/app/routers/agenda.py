"""`/agenda` routes — the plan of the day."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from ..db import get_connection
from ..models import DATE_FORMAT, Agenda, AgendaCreate
from ..repository import AgendaRepository

router = APIRouter(prefix="/agenda", tags=["agenda"])

# `28-Jul-2026` is the project's contract format; ISO is accepted too because it
# is what a date picker or `date -I` hands you. The two cannot be confused.
DAY_FORMATS = (DATE_FORMAT, "%Y-%m-%d")


def get_agendas(
    connection: Annotated[sqlite3.Connection, Depends(get_connection)],
) -> AgendaRepository:
    return AgendaRepository(connection)


Agendas = Annotated[AgendaRepository, Depends(get_agendas)]


def parse_day(value: str) -> date:
    for day_format in DAY_FORMATS:
        try:
            return datetime.strptime(value, day_format).date()
        except ValueError:
            continue
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"Expected a day as DD-Mon-YYYY or YYYY-MM-DD, got {value!r}",
    )


def require_agenda(agendas: AgendaRepository, day: date) -> Agenda:
    agenda = agendas.get(day)
    if agenda is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No agenda stored for {day.strftime(DATE_FORMAT)}",
        )
    return agenda


@router.post(
    "",
    response_model=Agenda,
    status_code=status.HTTP_201_CREATED,
    summary="Store the plan of the day",
    description=(
        "Stores the plan for the day named by `date`, defaulting to today. One plan per"
        " day: storing again for the same day replaces it. `top` takes e-mail ids or"
        " whole e-mail objects, and every id must already be in the inbox."
    ),
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Unknown e-mail id in `top`"}
    },
)
@router.post(
    "/",
    response_model=Agenda,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def store_agenda(agendas: Agendas, plan: AgendaCreate) -> Agenda:
    email_ids = plan.email_ids
    missing = agendas.missing_email_ids(email_ids)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"No e-mail with id {missing}",
        )
    return agendas.save(
        when=plan.date or datetime.now(),
        email_ids=email_ids,
        meeting=plan.meeting,
        support=plan.support,
    )


@router.get(
    "",
    response_model=Agenda,
    summary="Get today's plan",
    description="The plan of the current day, by the server's local clock.",
    responses={status.HTTP_404_NOT_FOUND: {"description": "No plan stored for today"}},
)
@router.get("/", response_model=Agenda, include_in_schema=False)
def get_today(agendas: Agendas) -> Agenda:
    return require_agenda(agendas, datetime.now().date())


@router.get(
    "/{day}",
    response_model=Agenda,
    summary="Get the plan for a day",
    description="The plan of one day, as `DD-Mon-YYYY` or `YYYY-MM-DD`.",
    responses={status.HTTP_404_NOT_FOUND: {"description": "No plan stored for that day"}},
)
def get_agenda(
    agendas: Agendas,
    day: Annotated[str, Path(description="Day to fetch.", examples=["28-Jul-2026"])],
) -> Agenda:
    return require_agenda(agendas, parse_day(day))
