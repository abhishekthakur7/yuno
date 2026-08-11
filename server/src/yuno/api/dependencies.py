"""Reusable FastAPI dependencies: the owner seam, one-UoW-per-request, the
job dispatcher, and the `Idempotency-Key`/`If-Match` header guards (spec
§5.1).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, Request

from yuno.modules.identity.ports import IdentityUnitOfWork
from yuno.shared.application.jobs import JobDispatcher
from yuno.shared.domain.errors import (
    MalformedRequestError,
    PreconditionFailedError,
    UnavailableError,
)


def get_unit_of_work(request: Request) -> Iterator[IdentityUnitOfWork]:
    """Yield exactly one `UnitOfWork` for this request (spec §3.4: one
    application UoW per HTTP command). Route/service code decides whether
    to call `uow.commit()`; an uncommitted UoW rolls back when the request
    finishes.

    Typed as `IdentityUnitOfWork` (rather than the minimal
    `shared.application.unit_of_work.UnitOfWork`) since `get_owner_id`
    below needs `uow.owners`; the object yielded at runtime is always the
    composition root's `yuno.unit_of_work.SqlAlchemyUnitOfWork`, which
    satisfies every module's UnitOfWork protocol at once.
    """
    with request.app.state.uow_factory() as uow:
        yield uow


def get_owner_id(uow: Annotated[IdentityUnitOfWork, Depends(get_unit_of_work)]) -> str:
    """Resolve the built-in local owner id, server-side, for this request.

    This is the owner seam (DAT-01, spec §5.1): the acting owner id always
    comes from the `owners` table via this function, never from client
    input (an `X-Owner-Id` header, an `owner_id` query param or body
    field). Routes needing the acting owner id must take it from this
    dependency, not parse one from the request themselves.
    """
    owner = uow.owners.get_local_owner()
    if owner is None:
        raise UnavailableError("The local owner has not been provisioned yet.")
    return owner.id


def get_job_dispatcher(request: Request) -> JobDispatcher:
    """Return the process-wide `JobDispatcher` built at startup."""
    return request.app.state.dispatcher


def idempotency_key(
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str:
    """Required on every mutating create/action (spec §5.1). A route that
    declares this dependency rejects a request with a missing header as
    `400` before any handler code runs.
    """
    if not idempotency_key or not idempotency_key.strip():
        raise MalformedRequestError(
            "The 'Idempotency-Key' header is required for this operation."
        )
    return idempotency_key.strip()


def if_match(
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> str:
    """Required on every PATCH (spec §5.1); raises `412` when missing. A
    *stale* value — one that doesn't match the loaded resource's current
    `row_version` — can only be detected once that resource is loaded, so
    each PATCH route compares this returned value itself and raises the
    same `PreconditionFailedError` on a mismatch.
    """
    if not if_match:
        raise PreconditionFailedError(
            "The 'If-Match' header is required for this operation."
        )
    return if_match


def parse_if_match(raw: str) -> int:
    """Parse a validated If-Match header as the resource row version."""
    try:
        value = int(raw.strip().strip('"'))
    except ValueError as exc:
        raise MalformedRequestError(
            "If-Match must contain an integer row version."
        ) from exc
    if value < 1:
        raise MalformedRequestError("If-Match must contain a positive row version.")
    return value
