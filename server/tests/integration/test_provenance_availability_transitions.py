"""Integration coverage for IDK-003 §8/§12 item 6 (IDK-503 finding B7): the
automatic 3-attempt/72-hour `unavailable` transition, and its reset-on-
success, in `run_source_retrieval_job`
(`server/src/yuno/modules/provenance/service.py`).

§8 (`IDK-003:109`) fixes the rule: `unavailable` is entered automatically
only after 3 consecutive independent retrieval attempts fail, spanning at
least 72 hours; a subsequent successful retrieval returns the source to
`available` automatically. §10 (`IDK-003:138`) forbids any automatic
`unavailable` transition from fewer than 3 consecutive failures, or from a
span under 72 hours, and forbids any automatic `withdrawn` transition ever.

No failure-counter column exists (§12.1's schema list has none); the
service instead persists each failed retrieval as a `source_snapshots` row
with `status = 'failed'` (that CHECK already admits `'failed'`,
`provenance/models.py:87-89`) and derives the streak from
`list_source_snapshots`, which is naturally reset by any intervening
success.

**Implementation choice this decision does not settle (recorded per the
task brief):** the 72-hour window is measured from the earliest to the
latest retrieval in the *entire* current run of consecutive failures (not
just the most recent 3) -- the most literal reading of "3 consecutive
independent retrieval attempts fail, spanning at least 72 hours". A second
implementation choice: what counts as a "failed attempt" is any `Exception`
raised by `adapter.retrieve(...)` *or* by the service's own
`_validate_retrieval_result` post-check on a returned result -- i.e. a
successful call that returns a malformed result also counts as a failed
attempt, not just a raised/transport-level failure.

**Why these tests call `run_source_retrieval_job` directly** rather than
driving it through the HTTP API + durable job dispatcher (the way
`test_topic_conversation_source_retrieval.py` does): the dispatcher's
probe/apply/replay machinery (`api/app.py`'s `external_job_handler`) exists
to run the real external call exactly once outside a DB transaction: it
wraps whatever the adapter raises into `JobPreparedFailure` before it ever
reaches the service function. That wrapping is dispatcher plumbing already
exercised by the existing HTTP-level test; it is orthogonal to the
streak/window state-machine logic under test here, and a direct call
exercises the identical service + repository + real-migrated-SQLite path
with far less incidental complexity. A plain fake adapter (with a `fail`
toggle) that raises `RuntimeError` proves the service's `except Exception`
handling doesn't care about the *type* of failure, matching production
where the type varies (`DomainValidationError`, `RuntimeError`,
`JobPreparedFailure`, ...).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from yuno.modules.provenance.domain import (
    Source,
    SourceAvailability,
    SourceRetrievalRequest,
    SourceRetrievalResult,
    SourceWithdrawalReason,
)
from yuno.modules.provenance.service import run_source_retrieval_job
from yuno.shared.application.jobs import JobRequest
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.errors import ConflictError
from yuno.shared.domain.ids import new_id

_BASE = datetime(2026, 8, 1, 0, 0, 0, tzinfo=UTC)


@dataclass
class _StepClock:
    """A controllable `Clock` (duck-typed, per the project's existing
    `_FixedClock`/`_FixedProgressClock` test idiom) whose `instant` the test
    advances explicitly between job runs -- never by sleeping.
    """

    instant: datetime

    def now(self) -> datetime:
        return self.instant


@dataclass
class _FakeRetriever:
    """A `SourceRetrievalAdapter` with a failure toggle, mirroring
    `FakeRetriever` in `test_topic_conversation_source_retrieval.py:54-74`.
    """

    calls: int = 0
    fail: bool = False

    def retrieve(
        self,
        request: SourceRetrievalRequest,
        *,
        cancelled=lambda: False,
    ) -> SourceRetrievalResult:
        self.calls += 1
        assert not cancelled()
        if self.fail:
            raise RuntimeError("synthetic retrieval failure")
        return SourceRetrievalResult(
            content_ref=f"secure:source:{request.source_id}:v{self.calls}",
            content_hash=f"hash-{request.source_id}-{self.calls}",
            retrieved_at="2026-08-13T10:00:00.000000Z",
            version_label="fixture-v1",
        )


def _source(
    owner_id: str,
    *,
    suffix: str,
    availability: SourceAvailability = SourceAvailability.AVAILABLE,
) -> Source:
    timestamp = "2026-08-01T00:00:00.000000Z"
    return Source(
        id=new_id(),
        owner_id=owner_id,
        origin="fixture",
        source_type="documentation",
        title=f"Source {suffix}",
        publisher="Fixture publisher",
        canonical_url=f"https://example.invalid/{suffix}",
        license_status="approved-open-license",
        availability_status=availability,
        withdrawal_reason=SourceWithdrawalReason.PUBLISHER_RETRACTED
        if availability is SourceAvailability.WITHDRAWN
        else None,
        superseded_by_source_id=None,
        created_at=timestamp,
        updated_at=timestamp,
    )


def _seed_source(
    uow_factory: UnitOfWorkFactory,
    *,
    suffix: str,
    availability: SourceAvailability = SourceAvailability.AVAILABLE,
) -> tuple[str, str]:
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Owner")
        source = _source(owner.id, suffix=suffix, availability=availability)
        uow.provenance.add_source(source)
        uow.commit()
    return owner.id, source.id


def _attempt(
    uow_factory: UnitOfWorkFactory,
    owner_id: str,
    source_id: str,
    adapter: _FakeRetriever,
    clock: _StepClock,
) -> None:
    request = JobRequest("retrieve_source_snapshot", owner_id, {"source_id": source_id})
    if adapter.fail:
        with pytest.raises(RuntimeError, match="synthetic retrieval failure"):
            run_source_retrieval_job(request, uow_factory, adapter, clock=clock)
    else:
        run_source_retrieval_job(request, uow_factory, adapter, clock=clock)


def _status(uow_factory: UnitOfWorkFactory, owner_id: str, source_id: str) -> Source:
    with uow_factory() as uow:
        source = uow.provenance.get_source(owner_id, source_id)
    assert source is not None
    return source


def test_one_failure_still_available(uow_factory: UnitOfWorkFactory) -> None:
    owner_id, source_id = _seed_source(uow_factory, suffix="one-failure")
    adapter = _FakeRetriever(fail=True)
    clock = _StepClock(_BASE)

    _attempt(uow_factory, owner_id, source_id, adapter, clock)

    source = _status(uow_factory, owner_id, source_id)
    assert source.availability_status is SourceAvailability.AVAILABLE
    assert source.withdrawal_reason is None


def test_two_failures_still_available(uow_factory: UnitOfWorkFactory) -> None:
    owner_id, source_id = _seed_source(uow_factory, suffix="two-failures")
    adapter = _FakeRetriever(fail=True)
    clock = _StepClock(_BASE)

    _attempt(uow_factory, owner_id, source_id, adapter, clock)
    clock.instant = _BASE + timedelta(hours=40)
    _attempt(uow_factory, owner_id, source_id, adapter, clock)

    source = _status(uow_factory, owner_id, source_id)
    assert source.availability_status is SourceAvailability.AVAILABLE


def test_three_failures_spanning_at_least_72h_transitions_to_unavailable(
    uow_factory: UnitOfWorkFactory,
) -> None:
    """The named IDK-503 gate-3 clearance test: 3 consecutive failures
    spanning >= 72h (here exactly 72h, the boundary) trip the transition,
    and `withdrawal_reason` stays NULL -- `unavailable` is never
    `withdrawn` (§12.1's CHECK requires the reason non-null exactly when
    `withdrawn`).
    """
    owner_id, source_id = _seed_source(uow_factory, suffix="three-failures-72h")
    adapter = _FakeRetriever(fail=True)
    clock = _StepClock(_BASE)

    _attempt(uow_factory, owner_id, source_id, adapter, clock)
    clock.instant = _BASE + timedelta(hours=40)
    _attempt(uow_factory, owner_id, source_id, adapter, clock)
    clock.instant = _BASE + timedelta(hours=72)
    _attempt(uow_factory, owner_id, source_id, adapter, clock)

    source = _status(uow_factory, owner_id, source_id)
    assert source.availability_status is SourceAvailability.UNAVAILABLE
    assert source.withdrawal_reason is None


def test_three_failures_spanning_under_72h_stays_available(
    uow_factory: UnitOfWorkFactory,
) -> None:
    """Proves the time condition is load-bearing, not decorative: 3
    consecutive failures with a span just under 72h must not transition.
    """
    owner_id, source_id = _seed_source(uow_factory, suffix="three-failures-under-72h")
    adapter = _FakeRetriever(fail=True)
    clock = _StepClock(_BASE)

    _attempt(uow_factory, owner_id, source_id, adapter, clock)
    clock.instant = _BASE + timedelta(hours=1)
    _attempt(uow_factory, owner_id, source_id, adapter, clock)
    clock.instant = _BASE + timedelta(hours=71, minutes=59)
    _attempt(uow_factory, owner_id, source_id, adapter, clock)

    source = _status(uow_factory, owner_id, source_id)
    assert source.availability_status is SourceAvailability.AVAILABLE


def test_success_between_failures_resets_the_streak(
    uow_factory: UnitOfWorkFactory,
) -> None:
    """failure, failure, success, failure, failure -- still available: the
    success resets the streak, so the two later failures cannot combine
    with the two stale ones (which alone would span >= 72h) to reach 3.
    """
    owner_id, source_id = _seed_source(uow_factory, suffix="reset-on-success")
    adapter = _FakeRetriever()
    clock = _StepClock(_BASE)

    adapter.fail = True
    _attempt(uow_factory, owner_id, source_id, adapter, clock)
    clock.instant = _BASE + timedelta(hours=40)
    _attempt(uow_factory, owner_id, source_id, adapter, clock)

    clock.instant = _BASE + timedelta(hours=50)
    adapter.fail = False
    _attempt(uow_factory, owner_id, source_id, adapter, clock)

    clock.instant = _BASE + timedelta(hours=60)
    adapter.fail = True
    _attempt(uow_factory, owner_id, source_id, adapter, clock)
    clock.instant = _BASE + timedelta(hours=140)
    _attempt(uow_factory, owner_id, source_id, adapter, clock)

    source = _status(uow_factory, owner_id, source_id)
    assert source.availability_status is SourceAvailability.AVAILABLE


def test_unavailable_then_success_returns_to_available(
    uow_factory: UnitOfWorkFactory,
) -> None:
    owner_id, source_id = _seed_source(uow_factory, suffix="reset-after-unavailable")
    adapter = _FakeRetriever(fail=True)
    clock = _StepClock(_BASE)

    _attempt(uow_factory, owner_id, source_id, adapter, clock)
    clock.instant = _BASE + timedelta(hours=40)
    _attempt(uow_factory, owner_id, source_id, adapter, clock)
    clock.instant = _BASE + timedelta(hours=72)
    _attempt(uow_factory, owner_id, source_id, adapter, clock)

    unavailable = _status(uow_factory, owner_id, source_id)
    assert unavailable.availability_status is SourceAvailability.UNAVAILABLE
    assert unavailable.withdrawal_reason is None

    clock.instant = _BASE + timedelta(hours=80)
    adapter.fail = False
    _attempt(uow_factory, owner_id, source_id, adapter, clock)

    available_again = _status(uow_factory, owner_id, source_id)
    assert available_again.availability_status is SourceAvailability.AVAILABLE
    assert available_again.withdrawal_reason is None


def test_withdrawn_source_is_never_transitioned_by_this_job(
    uow_factory: UnitOfWorkFactory,
) -> None:
    owner_id, source_id = _seed_source(
        uow_factory,
        suffix="withdrawn-untouched",
        availability=SourceAvailability.WITHDRAWN,
    )
    adapter = _FakeRetriever(fail=True)
    clock = _StepClock(_BASE)
    request = JobRequest("retrieve_source_snapshot", owner_id, {"source_id": source_id})

    with pytest.raises(ConflictError):
        run_source_retrieval_job(request, uow_factory, adapter, clock=clock)

    source = _status(uow_factory, owner_id, source_id)
    assert source.availability_status is SourceAvailability.WITHDRAWN
    assert adapter.calls == 0
    with uow_factory() as uow:
        assert uow.provenance.list_source_snapshots(owner_id, source_id) == ()

    adapter.fail = False
    with pytest.raises(ConflictError):
        run_source_retrieval_job(request, uow_factory, adapter, clock=clock)

    source = _status(uow_factory, owner_id, source_id)
    assert source.availability_status is SourceAvailability.WITHDRAWN
    assert adapter.calls == 0
