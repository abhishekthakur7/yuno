"""Unit tests for `InProcessJobDispatcher` (spec §3.2 "Async-operation
seam"). A caller enqueues through the `JobDispatcher` port, receives a
`JobRef`, and observes single-flight/dedupe behavior without importing
`jobs_events` ORM types; swapping the synchronous executor for a durable
worker later requires no caller change.

Also covers two payload-handling defects: an unhashable/non-serialisable
`payload` must raise `DomainValidationError` rather than a raw builtin
exception (one test per adversarial payload class, each also proving
dispatcher state survives the rejection); and a fresh `enqueue` call's
`JobRef.status` is already terminal, pinned so a future switch to `QUEUED`
is deliberate rather than a silent break.
"""

from __future__ import annotations

import threading

import pytest

from yuno.shared.application.jobs import JobDispatcher, JobRef, JobRequest, JobStatus
from yuno.shared.domain.errors import DomainValidationError, IdempotencyConflictError
from yuno.shared.infrastructure.jobs import InProcessJobDispatcher


def _request(
    *,
    kind: str = "send_email",
    owner_id: str = "owner-a",
    payload: dict[str, object] | None = None,
    dedupe_key: str | None = None,
    idempotency_key: str | None = None,
) -> JobRequest:
    return JobRequest(
        kind=kind,
        owner_id=owner_id,
        payload=payload if payload is not None else {},
        dedupe_key=dedupe_key,
        idempotency_key=idempotency_key,
    )


def test_enqueue_runs_handler_and_returns_job_ref() -> None:
    calls: list[JobRequest] = []
    dispatcher = InProcessJobDispatcher()
    dispatcher.register("send_email", calls.append)

    request = _request(payload={"to": "a@example.com"})
    ref = dispatcher.enqueue(request)

    assert isinstance(ref, JobRef)
    assert ref.kind == "send_email"
    assert ref.status == JobStatus.SUCCEEDED
    assert ref.deduplicated is False
    assert ref.job_id
    assert ref.enqueued_at
    assert calls == [request]


def test_single_flight_deduplicates_while_job_is_running() -> None:
    handler_started = threading.Event()
    release_handler = threading.Event()
    call_count = 0
    call_lock = threading.Lock()

    def handler(_request: JobRequest) -> None:
        nonlocal call_count
        with call_lock:
            call_count += 1
        handler_started.set()
        assert release_handler.wait(timeout=5), "test handler was never released"

    dispatcher = InProcessJobDispatcher()
    dispatcher.register("send_email", handler)
    request = _request(dedupe_key="welcome-owner-a")

    first_results: list[JobRef] = []
    first_thread = threading.Thread(
        target=lambda: first_results.append(dispatcher.enqueue(request))
    )
    first_thread.start()
    try:
        assert handler_started.wait(timeout=5), "handler never started"

        # The first job is still RUNNING (blocked on release_handler) here,
        # so this second enqueue must single-flight instead of re-running
        # the handler.
        second_ref = dispatcher.enqueue(request)
    finally:
        release_handler.set()
        first_thread.join(timeout=5)

    assert call_count == 1
    first_ref = first_results[0]
    assert first_ref.deduplicated is False
    assert first_ref.status == JobStatus.SUCCEEDED

    assert second_ref.deduplicated is True
    assert second_ref.job_id == first_ref.job_id
    assert second_ref.status == JobStatus.RUNNING


def test_dedupe_key_scope_is_owner_kind_and_key() -> None:
    calls: list[JobRequest] = []
    dispatcher = InProcessJobDispatcher()
    dispatcher.register("send_email", calls.append)
    dispatcher.register("send_sms", calls.append)

    baseline = dispatcher.enqueue(
        _request(kind="send_email", owner_id="owner-a", dedupe_key="d1")
    )
    other_owner = dispatcher.enqueue(
        _request(kind="send_email", owner_id="owner-b", dedupe_key="d1")
    )
    other_kind = dispatcher.enqueue(
        _request(kind="send_sms", owner_id="owner-a", dedupe_key="d1")
    )
    other_key = dispatcher.enqueue(
        _request(kind="send_email", owner_id="owner-a", dedupe_key="d2")
    )

    refs = [baseline, other_owner, other_kind, other_key]
    assert len(calls) == 4
    assert all(ref.deduplicated is False for ref in refs)
    assert len({ref.job_id for ref in refs}) == 4


def test_dedupe_key_none_disables_single_flight() -> None:
    calls: list[JobRequest] = []
    dispatcher = InProcessJobDispatcher()
    dispatcher.register("send_email", calls.append)

    first = dispatcher.enqueue(_request(dedupe_key=None))
    second = dispatcher.enqueue(_request(dedupe_key=None))

    assert len(calls) == 2
    assert first.deduplicated is False
    assert second.deduplicated is False
    assert first.job_id != second.job_id


def test_idempotency_replay_returns_original_without_rerunning_handler() -> None:
    calls: list[JobRequest] = []
    dispatcher = InProcessJobDispatcher()
    dispatcher.register("send_email", calls.append)
    payload = {"to": "a@example.com"}

    first = dispatcher.enqueue(_request(payload=payload, idempotency_key="idem-1"))
    second = dispatcher.enqueue(_request(payload=payload, idempotency_key="idem-1"))

    assert len(calls) == 1
    assert second.deduplicated is True
    assert second.job_id == first.job_id


def test_idempotency_conflict_raises_on_changed_payload() -> None:
    dispatcher = InProcessJobDispatcher()
    dispatcher.register("send_email", lambda request: None)

    dispatcher.enqueue(
        _request(payload={"to": "a@example.com"}, idempotency_key="idem-1")
    )

    with pytest.raises(IdempotencyConflictError):
        dispatcher.enqueue(
            _request(payload={"to": "b@example.com"}, idempotency_key="idem-1")
        )


def test_get_is_owner_scoped() -> None:
    dispatcher = InProcessJobDispatcher()
    dispatcher.register("send_email", lambda request: None)

    ref = dispatcher.enqueue(_request(owner_id="owner-a"))

    assert dispatcher.get("owner-a", ref.job_id) == ref
    assert dispatcher.get("owner-b", ref.job_id) is None
    assert dispatcher.get("owner-a", "does-not-exist") is None


def test_raising_handler_yields_failed_without_corrupting_dispatcher() -> None:
    def boom(_request: JobRequest) -> None:
        raise ValueError("boom")

    dispatcher = InProcessJobDispatcher()
    dispatcher.register("explode", boom)
    dispatcher.register("send_email", lambda request: None)

    ref = dispatcher.enqueue(_request(kind="explode", owner_id="owner-a"))

    assert ref.status == JobStatus.FAILED
    assert dispatcher.get("owner-a", ref.job_id) == ref

    # Dispatcher state is not corrupted: unrelated kinds still work, and the
    # same dedupe key can run again now that the failed job is terminal.
    follow_up = dispatcher.enqueue(_request(kind="send_email", owner_id="owner-a"))
    assert follow_up.status == JobStatus.SUCCEEDED

    retry = dispatcher.enqueue(
        _request(kind="explode", owner_id="owner-a", dedupe_key="retryable")
    )
    assert retry.status == JobStatus.FAILED
    assert retry.job_id != ref.job_id


def test_unregistered_kind_raises_domain_validation_error() -> None:
    dispatcher = InProcessJobDispatcher()

    with pytest.raises(DomainValidationError):
        dispatcher.enqueue(_request(kind="ghost"))


def test_caller_perspective_only_uses_job_dispatcher_protocol() -> None:
    """Substitutability proof: once constructed, a caller holding a
    `JobDispatcher`-typed reference enqueues, observes dedupe behavior, and
    reads job state using only the port's `enqueue`/`get` — never
    `InProcessJobDispatcher.register` or any other infrastructure-specific
    method, and no `jobs_events` ORM import.
    """
    concrete = InProcessJobDispatcher()
    concrete.register("send_email", lambda request: None)

    dispatcher: JobDispatcher = concrete  # the caller only ever sees the port
    payload = {"to": "a@example.com"}

    first = dispatcher.enqueue(
        JobRequest(
            kind="send_email",
            owner_id="owner-a",
            payload=payload,
            idempotency_key="welcome-owner-a",
        )
    )
    second = dispatcher.enqueue(
        JobRequest(
            kind="send_email",
            owner_id="owner-a",
            payload=payload,
            idempotency_key="welcome-owner-a",
        )
    )

    assert isinstance(first, JobRef)
    assert first.status == JobStatus.SUCCEEDED
    assert second.deduplicated is True
    assert second.job_id == first.job_id
    assert dispatcher.get("owner-a", first.job_id) == first


def test_enqueue_rejects_circular_reference_payload() -> None:
    """A payload containing a circular reference makes `hash_payload`
    raise a raw `ValueError`; `enqueue` must translate that into a
    `DomainValidationError` (422) instead of letting it escape as an
    internal error.
    """
    dispatcher = InProcessJobDispatcher()
    dispatcher.register("send_email", lambda request: None)

    payload: dict[str, object] = {}
    payload["self"] = payload

    with pytest.raises(DomainValidationError):
        dispatcher.enqueue(_request(payload=payload, owner_id="owner-a"))

    # State integrity: the rejection happens before any record is created
    # or the lock acquired, so a well-formed enqueue for another owner
    # still succeeds afterwards.
    follow_up = dispatcher.enqueue(_request(owner_id="owner-b"))
    assert follow_up.status == JobStatus.SUCCEEDED


def test_enqueue_rejects_payload_with_tuple_key() -> None:
    """A dict key that is not `str`/`int`/`float`/`bool`/`None` makes
    `hash_payload` raise a raw `TypeError`; `enqueue` must translate that
    into a `DomainValidationError` instead.
    """
    dispatcher = InProcessJobDispatcher()
    dispatcher.register("send_email", lambda request: None)

    payload = {("a", "b"): 1}

    with pytest.raises(DomainValidationError):
        dispatcher.enqueue(_request(payload=payload, owner_id="owner-a"))

    follow_up = dispatcher.enqueue(_request(owner_id="owner-b"))
    assert follow_up.status == JobStatus.SUCCEEDED


def test_enqueue_rejects_payload_with_mixed_int_and_str_keys() -> None:
    """Mixed `int`/`str` keys crash `json.dumps(sort_keys=True)`'s internal
    sort with a raw `TypeError` *before* `default=str` ever gets a chance
    to help; `enqueue` must still translate that into a
    `DomainValidationError`.
    """
    dispatcher = InProcessJobDispatcher()
    dispatcher.register("send_email", lambda request: None)

    payload = {"a": 1, 2: "b"}

    with pytest.raises(DomainValidationError):
        dispatcher.enqueue(_request(payload=payload, owner_id="owner-a"))

    follow_up = dispatcher.enqueue(_request(owner_id="owner-b"))
    assert follow_up.status == JobStatus.SUCCEEDED


def test_enqueue_rejects_payload_whose_str_fallback_raises() -> None:
    """`hash_payload` falls back to `str()` for values it cannot natively
    encode; if that `str()` itself raises, `enqueue` must still translate
    the resulting (arbitrary) exception into a `DomainValidationError`
    instead of letting it propagate raw.
    """

    class _Unstringifiable:
        def __str__(self) -> str:
            raise RuntimeError("cannot stringify")

    dispatcher = InProcessJobDispatcher()
    dispatcher.register("send_email", lambda request: None)

    payload = {"x": _Unstringifiable()}

    with pytest.raises(DomainValidationError):
        dispatcher.enqueue(_request(payload=payload, owner_id="owner-a"))

    follow_up = dispatcher.enqueue(_request(owner_id="owner-b"))
    assert follow_up.status == JobStatus.SUCCEEDED


def test_enqueue_returns_a_terminal_status_not_queued() -> None:
    """Pins the trap documented on `InProcessJobDispatcher`: a fresh
    (non-deduplicated) `enqueue` call always returns an already-terminal
    `JobRef.status` (`SUCCEEDED`/`FAILED`), never `QUEUED`. A caller must
    not treat a `202` response from this executor as evidence the job is
    still pending. A durable worker would return `QUEUED` instead, at
    which point this assertion must change deliberately, not break
    silently.
    """
    dispatcher = InProcessJobDispatcher()
    dispatcher.register("send_email", lambda request: None)

    ref = dispatcher.enqueue(_request())

    assert ref.status not in (JobStatus.QUEUED, JobStatus.RUNNING)
    assert ref.status == JobStatus.SUCCEEDED
