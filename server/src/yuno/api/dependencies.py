"""Reusable FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Header, Request

from yuno.config import Settings
from yuno.modules.identity.ports import IdentityUnitOfWork
from yuno.shared.application.jobs import JobDispatcher
from yuno.shared.domain.clock import Clock, SystemClock
from yuno.shared.domain.errors import (
    MalformedRequestError,
    PreconditionFailedError,
)


def get_unit_of_work(request: Request) -> Iterator[IdentityUnitOfWork]:
    """Yield one UoW; routes explicitly commit commands."""
    with request.app.state.uow_factory() as uow:
        yield uow


def get_owner_id(request: Request) -> str:
    """Return the acting local owner's id, never from client input.

    The local owner is a singleton provisioned once during lifespan
    startup (`app.py`'s `ensure_local_owner` call, before traffic is
    accepted) and cached on `app.state.owner_id`. Reading it here is a
    plain attribute read -- no `UnitOfWork`, no SQL -- so it runs before
    body validation without opening a database connection, the same as
    `get_settings_dependency`/`get_clock` below.
    """
    return request.app.state.owner_id


def get_job_dispatcher(request: Request) -> JobDispatcher:
    return request.app.state.dispatcher


def get_settings_dependency(request: Request) -> Settings:
    return request.app.state.settings


def get_clock(request: Request) -> Clock:
    return getattr(request.app.state, "clock", SystemClock())


def idempotency_key(
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str:
    """Require `Idempotency-Key` before a mutating command runs."""
    if not idempotency_key or not idempotency_key.strip():
        raise MalformedRequestError(
            "The 'Idempotency-Key' header is required for this operation."
        )
    return idempotency_key.strip()


def if_match(
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> str:
    """Require `If-Match`; each PATCH checks staleness after loading."""
    if not if_match:
        raise PreconditionFailedError(
            "The 'If-Match' header is required for this operation."
        )
    return if_match


def parse_if_match(raw: str) -> int:
    try:
        value = int(raw.strip().strip('"'))
    except ValueError as exc:
        raise MalformedRequestError(
            "If-Match must contain an integer row version."
        ) from exc
    if value < 1:
        raise MalformedRequestError("If-Match must contain a positive row version.")
    return value
