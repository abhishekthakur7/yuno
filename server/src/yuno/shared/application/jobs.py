"""The async-operation port shared by application modules."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from yuno.shared.domain.ids import new_id


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel-requested"
    CANCELLED = "cancelled"


class JobLane(StrEnum):
    INTERACTIVE = "interactive"
    BACKGROUND = "background"


@dataclass(frozen=True)
class JobRequest:
    kind: str
    owner_id: str
    payload: Mapping[str, Any]
    dedupe_key: str | None = None
    idempotency_key: str | None = None
    requested_job_id: str | None = None
    goal_id: str | None = None
    lane: JobLane | None = None
    schema_version: str = "1"
    request_ref: str | None = None
    disclosure_ref: str | None = None
    confirmation_ref: str | None = None
    correlation_id: str = field(default_factory=new_id)
    request_id: str = field(default_factory=new_id)
    run_id: str | None = None


@dataclass(frozen=True)
class JobRef:
    """The `202` enqueue response; callers must branch on `status`."""

    job_id: str
    kind: str
    status: JobStatus
    enqueued_at: str
    deduplicated: bool = False
    lane: JobLane | None = None
    retryable: bool = False
    goal_id: str | None = None
    schema_version: str = "1"
    attempt: int = 0
    diagnostic: str | None = None
    started_at: str | None = None
    terminal_at: str | None = None
    substitution_ref: str | None = None
    result_ref: str | None = None
    result_hash: str | None = None


@dataclass(frozen=True)
class JobAttempt:
    attempt_number: int
    process_identity: str | None
    pid: int | None
    pgid: int | None
    temp_path: str | None
    started_at: str
    ended_at: str | None
    outcome: str | None
    diagnostic: str | None
    substitution_ref: str | None
    confirmation_ref: str | None


@dataclass(frozen=True)
class JobResult:
    """Validated authoritative output returned by every job handler."""

    kind: str
    schema_version: str
    result_ref: str
    result_hash: str
    warnings: tuple[str, ...] = ()
    diagnostic_ref: str | None = None


@dataclass(frozen=True)
class JobCompletion:
    """Prepared output whose domain publication is part of terminal commit."""

    result: JobResult
    apply: Callable[[Any], JobResult | None]


class JobCancelled(Exception):
    """Raised cooperatively before a handler publishes its result."""


class JobPreparedFailure(Exception):
    """External failure replayed so domain and job failure commit together."""


@dataclass(frozen=True)
class JobExecution:
    request: JobRequest
    cancel_requested: Callable[[], bool]
    record_runtime: Callable[..., None]

    def checkpoint(self) -> None:
        if self.cancel_requested():
            raise JobCancelled("Cancellation committed before job completion.")


JobHandler = Callable[[JobExecution], JobCompletion]


class JobDispatcher(Protocol):
    """Single-flight non-terminal jobs and reject conflicting idempotency keys."""

    def enqueue(self, request: JobRequest) -> JobRef: ...

    def get(self, owner_id: str, job_id: str) -> JobRef | None: ...

    def list(self, owner_id: str) -> tuple[JobRef, ...]: ...

    def retry(
        self,
        owner_id: str,
        job_id: str,
        *,
        substitution_ref: str | None = None,
        confirmation_ref: str | None = None,
    ) -> JobRef: ...

    def cancel(self, owner_id: str, job_id: str) -> JobRef: ...

    def reconcile(self, owner_id: str, job_id: str) -> JobRef: ...

    def attempts(self, owner_id: str, job_id: str) -> tuple[JobAttempt, ...]: ...
