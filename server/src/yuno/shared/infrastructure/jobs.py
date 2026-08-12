"""Synchronous in-memory `JobDispatcher` adapter."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from yuno.shared.application.jobs import JobHandler, JobRef, JobRequest, JobStatus
from yuno.shared.domain.clock import Clock, SystemClock, now_text
from yuno.shared.domain.errors import DomainValidationError, IdempotencyConflictError
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id


@dataclass
class _JobRecord:
    job_id: str
    owner_id: str
    kind: str
    status: JobStatus
    enqueued_at: str
    payload_hash: str

    def to_ref(self, *, deduplicated: bool) -> JobRef:
        return JobRef(
            job_id=self.job_id,
            kind=self.kind,
            status=self.status,
            enqueued_at=self.enqueued_at,
            deduplicated=deduplicated,
        )


class InProcessJobDispatcher:
    """Run handlers inline while preserving the `JobDispatcher` contract.

    New jobs return terminal status; concurrent duplicate requests may see
    `RUNNING`. Single-flight is scoped to `(owner_id, kind, dedupe_key)` and
    idempotency keys are owner-scoped for this dispatcher's lifetime.
    """

    def __init__(self, *, clock: Clock | None = None) -> None:
        self._clock: Clock = clock or SystemClock()
        self._lock = threading.Lock()
        self._handlers: dict[str, JobHandler] = {}
        self._jobs: dict[tuple[str, str], _JobRecord] = {}
        self._inflight: dict[tuple[str, str, str], str] = {}
        self._idempotency: dict[tuple[str, str], str] = {}

    def register(self, kind: str, handler: JobHandler) -> None:
        with self._lock:
            self._handlers[kind] = handler

    def enqueue(self, request: JobRequest) -> JobRef:
        # Validate before changing dispatcher state; error messages omit payloads.
        try:
            payload_hash = hash_payload(request.payload)
        except Exception as exc:
            raise DomainValidationError(
                f"Job payload for kind {request.kind!r} could not be "
                f"canonicalised for hashing ({type(exc).__name__}); it must "
                "be JSON-serialisable with string-coercible keys and no "
                "circular references."
            ) from exc

        idempotency_map_key = (
            (request.owner_id, request.idempotency_key)
            if request.idempotency_key is not None
            else None
        )
        inflight_map_key = (
            (request.owner_id, request.kind, request.dedupe_key)
            if request.dedupe_key is not None
            else None
        )

        with self._lock:
            handler = self._handlers.get(request.kind)
            if handler is None:
                raise DomainValidationError(
                    f"No handler is registered for job kind {request.kind!r}."
                )

            if idempotency_map_key is not None:
                existing_id = self._idempotency.get(idempotency_map_key)
                if existing_id is not None:
                    existing = self._jobs[(request.owner_id, existing_id)]
                    if existing.payload_hash != payload_hash:
                        raise IdempotencyConflictError(
                            f"Idempotency key {request.idempotency_key!r} was reused "
                            "with a different request payload."
                        )
                    return existing.to_ref(deduplicated=True)

            if inflight_map_key is not None:
                existing_id = self._inflight.get(inflight_map_key)
                if existing_id is not None:
                    existing = self._jobs[(request.owner_id, existing_id)]
                    return existing.to_ref(deduplicated=True)

            requested_job_id = request.requested_job_id
            if requested_job_id is not None:
                if not requested_job_id.strip():
                    raise DomainValidationError("A requested job id must not be blank.")
                if any(job_id == requested_job_id for _, job_id in self._jobs):
                    raise DomainValidationError(
                        f"Job id {requested_job_id!r} has already been used."
                    )

            record = _JobRecord(
                job_id=requested_job_id or new_id(),
                owner_id=request.owner_id,
                kind=request.kind,
                status=JobStatus.RUNNING,
                enqueued_at=now_text(self._clock),
                payload_hash=payload_hash,
            )
            self._jobs[(request.owner_id, record.job_id)] = record
            if inflight_map_key is not None:
                self._inflight[inflight_map_key] = record.job_id
            if idempotency_map_key is not None:
                self._idempotency[idempotency_map_key] = record.job_id

        # Run outside the lock so concurrent requests can single-flight on it.
        try:
            handler(request)
        except Exception:  # noqa: BLE001  (handler errors must not crash the caller)
            terminal_status = JobStatus.FAILED
        else:
            terminal_status = JobStatus.SUCCEEDED

        with self._lock:
            record.status = terminal_status
            if inflight_map_key is not None:
                self._inflight.pop(inflight_map_key, None)
            return record.to_ref(deduplicated=False)

    def get(self, owner_id: str, job_id: str) -> JobRef | None:
        with self._lock:
            record = self._jobs.get((owner_id, job_id))
            return None if record is None else record.to_ref(deduplicated=False)
