"""In-process synchronous `JobDispatcher` adapter (spec §3.2 "Async-operation
seam"; ticket IDK-101).

`InProcessJobDispatcher` is the Phase 1-3 implementation of the
`JobDispatcher` port defined in `yuno.shared.application.jobs`: `enqueue` runs the
registered handler synchronously and records the terminal state. All state
(handler registry, jobs, single-flight and idempotency indexes) lives in
process memory and is guarded by a single `threading.Lock` around registry
mutations.

IDK-401 later replaces this executor — and adds the durable `jobs_events`
tables and two-lane worker — without changing the `JobDispatcher` contract
or any caller. This module therefore owns no table, defines no
`jobs_events` module, and imports nothing from `yuno.api` or SQLAlchemy: it
is only the port's in-process adapter.
"""

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
    """Internal mutable job state. Never exposed directly — `to_ref`
    produces the immutable `JobRef` snapshot callers receive.
    """

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
    """Synchronous, in-memory `JobDispatcher`.

    - `register` binds a `JobHandler` to a job `kind`; re-registering a
      `kind` replaces its handler.
    - `enqueue` single-flights on `(owner_id, kind, dedupe_key)` while a
      prior job for that key is non-terminal (`dedupe_key=None` disables
      single-flight for that request), and separately dedupes on
      `(owner_id, idempotency_key)` for the life of the dispatcher; a
      reused idempotency key with a different request payload hash raises
      `IdempotencyConflictError` (spec §5.1: 409 on a reused key with a
      different request hash).
    - `get` is owner-scoped: a job is only ever visible under the
      `owner_id` it was enqueued with.
    - `enqueue` runs the registered handler inline and blocks until it
      finishes: a freshly created (non-deduplicated) `JobRef.status` is
      therefore already terminal (`SUCCEEDED` or `FAILED`) by the time
      `enqueue` returns -- it is never `QUEUED`, and only ever `RUNNING` on
      the deduplicated branch, where it reflects another thread's
      still-executing job. A route following the documented `202
      accepted_job(dispatcher.enqueue(...))` pattern therefore returns
      `202` with an already-terminal body. Callers MUST NOT infer from a
      fresh `JobRef` that the job is still pending or needs polling --
      that is honest behavior for a synchronous executor, not a bug.
      IDK-401's durable worker returns `JobStatus.QUEUED` from this same
      `enqueue` call instead, with no change to the `JobDispatcher`/
      `JobRef` contract itself.
      `test_enqueue_returns_a_terminal_status_not_queued`
      (test_job_dispatcher.py) pins today's synchronous behaviour so that
      IDK-401's change is a deliberate, visible one rather than a silent
      regression.

    Not durable, no retry/cancellation/lanes/SSE — that is IDK-401's
    durable two-lane worker, behind this same `JobDispatcher` port.
    """

    def __init__(self, *, clock: Clock | None = None) -> None:
        self._clock: Clock = clock or SystemClock()
        self._lock = threading.Lock()
        self._handlers: dict[str, JobHandler] = {}
        self._jobs: dict[tuple[str, str], _JobRecord] = {}
        self._inflight: dict[tuple[str, str, str], str] = {}
        self._idempotency: dict[tuple[str, str], str] = {}

    def register(self, kind: str, handler: JobHandler) -> None:
        """Bind `handler` to `kind` for subsequent `enqueue` calls."""
        with self._lock:
            self._handlers[kind] = handler

    def enqueue(self, request: JobRequest) -> JobRef:
        # `request.payload` is arbitrary caller input (spec §5.1): a payload
        # `hash_payload` cannot canonicalise -- circular references,
        # non-string-coercible dict keys, mixed key types (which crash
        # `sort_keys=True`'s internal sort before `default=str` ever runs),
        # or a value whose `str()` fallback itself raises -- is bad caller
        # input, not a dispatcher bug. This runs before any record is
        # created or the lock is acquired, so a rejected payload never
        # touches dispatcher state. The message identifies the failure
        # without echoing the payload body itself (spec §8.5).
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

            record = _JobRecord(
                job_id=new_id(),
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

        # Run outside the lock: other threads may observe the RUNNING
        # record above (via `_inflight`) and single-flight against it
        # instead of blocking on dispatcher-wide state.
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
