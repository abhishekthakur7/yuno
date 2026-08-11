"""The async-operation seam (spec §3.2 scope: "Async-operation seam").

This defines `JobRef` (the `202` enqueue response contract) and the
`JobDispatcher` port. IDK-401 later replaces the executor and the backing
`jobs`/`job_events` tables with a durable two-lane worker WITHOUT changing
this contract. Phase 2-3 modules depend only on this port and never import
`jobs_events` ORM types or write job rows directly (spec §3.2 cross-module
ORM rule).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class JobRequest:
    kind: str
    owner_id: str
    payload: Mapping[str, Any]
    dedupe_key: str | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True)
class JobRef:
    """The `202` enqueue response contract.

    `status` reflects whatever execution model the concrete adapter uses,
    so a freshly returned `JobRef` is NOT guaranteed to be non-terminal.
    IDK-101's synchronous `InProcessJobDispatcher` runs the handler inline
    and returns an already-terminal `SUCCEEDED`/`FAILED`; IDK-401's durable
    worker will return `QUEUED` for the same call. Callers must therefore
    branch on `status` rather than assume a `202` implies work is pending.
    """

    job_id: str
    kind: str
    status: JobStatus
    enqueued_at: str
    deduplicated: bool = False


JobHandler = Callable[[JobRequest], None]


class JobDispatcher(Protocol):
    """Enqueue is single-flight per `(owner_id, kind, dedupe_key)` while a
    job is non-terminal: a duplicate enqueue while one is queued/running
    returns the existing `JobRef` with `deduplicated=True` instead of
    creating a second job. A reused `idempotency_key` with a different
    request payload hash raises `IdempotencyConflictError`. Callers never
    import jobs ORM types — they depend only on this port.
    """

    def enqueue(self, request: JobRequest) -> JobRef: ...

    def get(self, owner_id: str, job_id: str) -> JobRef | None: ...
