"""The async-operation port shared by application modules."""

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
    """A dispatch command with an optional pre-persisted job identity."""

    kind: str
    owner_id: str
    payload: Mapping[str, Any]
    dedupe_key: str | None = None
    idempotency_key: str | None = None
    requested_job_id: str | None = None


@dataclass(frozen=True)
class JobRef:
    """The `202` enqueue response; callers must branch on `status`."""

    job_id: str
    kind: str
    status: JobStatus
    enqueued_at: str
    deduplicated: bool = False


JobHandler = Callable[[JobRequest], None]


class JobDispatcher(Protocol):
    """Single-flight non-terminal jobs and reject conflicting idempotency keys."""

    def enqueue(self, request: JobRequest) -> JobRef: ...

    def get(self, owner_id: str, job_id: str) -> JobRef | None: ...
