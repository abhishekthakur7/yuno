"""Integration coverage for `sources_due_for_recheck`
(IDK-003 §12 item 9's cadence half / IDK-503 gate 3: "Add the 180-day (or
failure-triggered) staleness re-check job (§9) ... neither exists today")
and its production wiring in `app.py`'s `apply_staleness_recheck` closure.

§9 (`IDK-003:129`) fixes the rule: "Detection runs on a 180-day re-check
cadence for every `available` source, or immediately on crossing the §8
`unavailable` threshold, or on any explicit content-owner-initiated
re-retrieval." This file covers only the cadence leg -- the other two
triggers are already satisfied by existing code with no new code needed
(see `sources_due_for_recheck`'s docstring, `provenance/service.py`, and
`apply_staleness_recheck`'s docstring, `api/app.py`, for the reasoning);
`test_repeated_failures_are_retryable_until_unavailable_then_excluded`
below is what proves the crossing-into-`unavailable` reading holds without
new code.

Every assertion here runs against a real, migrated SQLite database
(`uow_factory`, `engine`, `session_factory` from `conftest.py`), matching
the project's existing provenance-suite convention
(`test_provenance_availability_transitions.py`,
`test_provenance_snapshot_janitor.py`). Dueness is computed with a fixed
`_NOW`/`_StepClock`, never wall-clock arithmetic.

**Why the "wiring, end to end" tests below call `_sweep_once` (a small
helper that mirrors `apply_staleness_recheck`'s body) instead of booting
the real app through `create_app()`/`TestClient`:** `apply_staleness_recheck`
is a closure inside `create_app`'s lifespan, like `apply_retention`/
`apply_snapshot_janitor` beside it -- none of the three are exported or
reachable from `app.state` (confirmed: no test in this repo drives
`apply_retention`/`apply_snapshot_janitor` through a live app either;
`test_provenance_snapshot_janitor.py` tests `prune_excess_snapshot_bodies`
directly for the same reason). Worse, `apply_staleness_recheck` runs
*during startup*, before a test can get control back, and a real
`create_app()` boot starts live background worker threads that poll for
queued jobs every 0.1s (`jobs_events/service.py:434-438`) -- so a live
two-boot test cannot deterministically prove "two sweeps with no
intervening snapshot enqueue one job" without either a real network
dependency or a race against those workers. `_sweep_once` instead calls
the exact same real functions (`sources_due_for_recheck`,
`reserve_source_retrieval`, `dispatcher.reserve`) with the exact same
call shape `apply_staleness_recheck` uses (`server/src/yuno/api/app.py`,
see the cross-reference in `_sweep_once`'s own docstring below), against
a `DurableJobDispatcher` that is registered but never `.start()`-ed, so
nothing it reserves ever actually executes -- fully deterministic, no
network, no threads.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from yuno.modules.jobs_events.service import DurableJobDispatcher
from yuno.modules.provenance.domain import (
    Source,
    SourceAvailability,
    SourceRetrievalRequest,
    SourceSnapshot,
    SourceWithdrawalReason,
)
from yuno.modules.provenance.service import (
    reserve_source_retrieval,
    run_source_retrieval_job,
    sources_due_for_recheck,
)
from yuno.modules.provider.service import accept_disclosure
from yuno.shared.application.jobs import JobLane, JobRequest
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import utc_text
from yuno.shared.domain.ids import new_id

_NOW = datetime(2026, 8, 15, tzinfo=UTC)
_STALENESS_RECHECK_CADENCE_DAYS = 180  # IDK-003 §9, approved and non-configurable
_FAILURE_BASE = datetime(2026, 1, 1, tzinfo=UTC)
_DISCLOSURE_KWARGS = {
    "category": "source-retrieval",
    "operation": "Explicit authoritative source retrieval",
    "destination": "The selected source's approved canonical URL",
    "data_categories": ("source URL", "operation metadata"),
    "disclosure_version": "source-network-v1",
}
_SECOND_OWNER_KIND = "test_secondary_owner"


def _owner(uow_factory: UnitOfWorkFactory) -> str:
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Owner")
        uow.commit()
    return owner.id


def _insert_second_owner(
    database_url: str, *, owner_id: str, display_name: str
) -> None:
    """Insert a second `owners` row directly via raw SQL, mirroring
    `test_provenance_snapshot_janitor.py::_insert_second_owner`:
    `owners.kind` carries both a CHECK restricting it to `'local_builtin'`
    and a UNIQUE constraint, so `create_local_owner` can only ever succeed
    once per database, and this is the established escape hatch for an
    owner-scoping test that needs a second owner to prove against.
    """
    prefix = "sqlite+pysqlite:///"
    assert database_url.startswith(prefix), (
        f"unexpected database URL scheme: {database_url!r}"
    )
    path = database_url.removeprefix(prefix)

    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute(
            "INSERT INTO owners (id, kind, display_name, status, created_at) "
            "VALUES (?, ?, ?, 'active', ?)",
            (owner_id, _SECOND_OWNER_KIND, display_name, utc_text(_NOW)),
        )
        connection.commit()
    finally:
        connection.close()


def _source(
    owner_id: str,
    *,
    suffix: str,
    availability: SourceAvailability = SourceAvailability.AVAILABLE,
    withdrawal_reason: SourceWithdrawalReason | None = None,
) -> Source:
    timestamp = utc_text(_NOW - timedelta(days=400))
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
        withdrawal_reason=withdrawal_reason,
        superseded_by_source_id=None,
        created_at=timestamp,
        updated_at=timestamp,
    )


def _seed_source(
    uow_factory: UnitOfWorkFactory,
    owner_id: str,
    *,
    suffix: str,
    availability: SourceAvailability = SourceAvailability.AVAILABLE,
    withdrawal_reason: SourceWithdrawalReason | None = None,
) -> str:
    source = _source(
        owner_id,
        suffix=suffix,
        availability=availability,
        withdrawal_reason=withdrawal_reason,
    )
    with uow_factory() as uow:
        uow.provenance.add_source(source)
        uow.commit()
    return source.id


def _snapshot(
    uow_factory: UnitOfWorkFactory,
    owner_id: str,
    source_id: str,
    *,
    suffix: str,
    retrieved_at: str,
    status: str = SourceAvailability.AVAILABLE.value,
) -> SourceSnapshot:
    snapshot = SourceSnapshot(
        id=new_id(),
        owner_id=owner_id,
        source_id=source_id,
        retrieved_at=retrieved_at,
        content_ref=f"source-snapshot:{suffix}",
        content_hash=f"hash-{suffix}",
        status=status,
        version_label=None,
    )
    with uow_factory() as uow:
        uow.provenance.add_source_snapshot(snapshot)
        uow.commit()
    return snapshot


def _due_ids(
    uow_factory: UnitOfWorkFactory, owner_id: str, *, now: datetime
) -> set[str]:
    with uow_factory() as uow:
        return {s.id for s in sources_due_for_recheck(uow, owner_id, now=now)}


# ---------------------------------------------------------------------------
# `sources_due_for_recheck` selection
# ---------------------------------------------------------------------------


def test_181_days_since_last_success_is_due(uow_factory: UnitOfWorkFactory) -> None:
    owner_id = _owner(uow_factory)
    source_id = _seed_source(uow_factory, owner_id, suffix="181-days")
    _snapshot(
        uow_factory,
        owner_id,
        source_id,
        suffix="181-days",
        retrieved_at=utc_text(_NOW - timedelta(days=181)),
    )

    assert _due_ids(uow_factory, owner_id, now=_NOW) == {source_id}


def test_179_days_since_last_success_is_not_due(uow_factory: UnitOfWorkFactory) -> None:
    owner_id = _owner(uow_factory)
    source_id = _seed_source(uow_factory, owner_id, suffix="179-days")
    _snapshot(
        uow_factory,
        owner_id,
        source_id,
        suffix="179-days",
        retrieved_at=utc_text(_NOW - timedelta(days=179)),
    )

    assert _due_ids(uow_factory, owner_id, now=_NOW) == set()


def test_exactly_180_days_is_due_the_boundary_is_inclusive(
    uow_factory: UnitOfWorkFactory,
) -> None:
    """Proves the `>=` in "now - retrieved_at >= 180 days" is load-bearing,
    mirroring `test_provenance_availability_transitions.py`'s identical
    boundary-inclusive proof for §8's 72-hour window.
    """
    owner_id = _owner(uow_factory)
    source_id = _seed_source(uow_factory, owner_id, suffix="180-days")
    _snapshot(
        uow_factory,
        owner_id,
        source_id,
        suffix="180-days",
        retrieved_at=utc_text(_NOW - timedelta(days=_STALENESS_RECHECK_CADENCE_DAYS)),
    )

    assert _due_ids(uow_factory, owner_id, now=_NOW) == {source_id}


def test_only_failed_snapshots_is_due(uow_factory: UnitOfWorkFactory) -> None:
    """A source with attempts on record, none of them successful, has no
    baseline to measure staleness from and is therefore always due --
    regardless of how recent the failed attempt was.
    """
    owner_id = _owner(uow_factory)
    source_id = _seed_source(uow_factory, owner_id, suffix="only-failed")
    _snapshot(
        uow_factory,
        owner_id,
        source_id,
        suffix="only-failed",
        retrieved_at=utc_text(_NOW - timedelta(days=1)),
        status="failed",
    )

    assert _due_ids(uow_factory, owner_id, now=_NOW) == {source_id}


def test_no_snapshots_at_all_is_due(uow_factory: UnitOfWorkFactory) -> None:
    owner_id = _owner(uow_factory)
    source_id = _seed_source(uow_factory, owner_id, suffix="never-retrieved")

    assert _due_ids(uow_factory, owner_id, now=_NOW) == {source_id}


def test_withdrawn_source_is_never_selected(uow_factory: UnitOfWorkFactory) -> None:
    owner_id = _owner(uow_factory)
    _seed_source(
        uow_factory,
        owner_id,
        suffix="withdrawn",
        availability=SourceAvailability.WITHDRAWN,
        withdrawal_reason=SourceWithdrawalReason.PUBLISHER_RETRACTED,
    )
    # No snapshot at all -- would be due if it were `available`.

    assert _due_ids(uow_factory, owner_id, now=_NOW) == set()


def test_unavailable_source_is_never_selected(uow_factory: UnitOfWorkFactory) -> None:
    owner_id = _owner(uow_factory)
    _seed_source(
        uow_factory,
        owner_id,
        suffix="unavailable",
        availability=SourceAvailability.UNAVAILABLE,
    )
    # No snapshot at all -- would be due if it were `available`.

    assert _due_ids(uow_factory, owner_id, now=_NOW) == set()


def test_owner_scoping_excludes_another_owners_due_source(
    uow_factory: UnitOfWorkFactory, database_url: str
) -> None:
    owner_a = _owner(uow_factory)
    owner_b = new_id()
    _insert_second_owner(database_url, owner_id=owner_b, display_name="Owner B")
    _seed_source(uow_factory, owner_b, suffix="owner-b-due")  # never retrieved -> due

    assert _due_ids(uow_factory, owner_a, now=_NOW) == set()
    assert _due_ids(uow_factory, owner_b, now=_NOW) != set()


# ---------------------------------------------------------------------------
# The idempotency-key/retry composition (task-brief requirement: prove it
# holds, or say what was done instead -- it holds; this is the proof).
# ---------------------------------------------------------------------------


@dataclass
class _StepClock:
    """A controllable `Clock`, per the project's existing test idiom
    (`test_provenance_availability_transitions.py::_StepClock`).
    """

    instant: datetime

    def now(self) -> datetime:
        return self.instant


@dataclass
class _FailingRetriever:
    """A `SourceRetrievalAdapter` that always fails -- no network call is
    ever made; this is a pure-Python fake, mirroring `_FakeRetriever` in
    `test_provenance_availability_transitions.py`.
    """

    calls: int = 0

    def retrieve(self, request: SourceRetrievalRequest, *, cancelled=lambda: False):
        self.calls += 1
        raise RuntimeError("synthetic retrieval failure")


def _newest_snapshot_id_of_any_status(
    uow_factory: UnitOfWorkFactory, owner_id: str, source_id: str
) -> str:
    """The sweep's idempotency-key cursor
    (`api/app.py`'s `apply_staleness_recheck`: `snapshots[0].id if
    snapshots else "never-retrieved"`), read directly for assertions.
    """
    with uow_factory() as uow:
        snapshots = uow.provenance.list_source_snapshots(owner_id, source_id)
    return snapshots[0].id if snapshots else "never-retrieved"


def test_repeated_failures_are_retryable_until_unavailable_then_excluded(
    uow_factory: UnitOfWorkFactory,
) -> None:
    """The composition the task brief asks to be proven: dueness (from the
    newest *successful* snapshot) stays true across repeated failures, so
    the source keeps being selected -- while the idempotency-key cursor
    (newest snapshot of *any* status) advances on every failed attempt, so
    a repeat sweep is a fresh reservation rather than a silently
    deduplicated no-op -- until the source crosses into `unavailable`
    (IDK-003 §8's 3-attempt/72-hour rule, exercised here exactly as
    `test_three_failures_spanning_at_least_72h_transitions_to_unavailable`
    does), at which point `sources_due_for_recheck` excludes it: the retry
    storm is self-limiting, not unbounded.
    """
    owner_id = _owner(uow_factory)
    source_id = _seed_source(uow_factory, owner_id, suffix="retry-storm")
    adapter = _FailingRetriever()
    clock = _StepClock(_FAILURE_BASE)

    def attempt() -> None:
        request = JobRequest(
            "retrieve_source_snapshot", owner_id, {"source_id": source_id}
        )
        with pytest.raises(RuntimeError, match="synthetic retrieval failure"):
            run_source_retrieval_job(request, uow_factory, adapter, clock=clock)

    cursor_0 = _newest_snapshot_id_of_any_status(uow_factory, owner_id, source_id)
    assert cursor_0 == "never-retrieved"
    assert source_id in _due_ids(uow_factory, owner_id, now=_NOW)

    attempt()
    cursor_1 = _newest_snapshot_id_of_any_status(uow_factory, owner_id, source_id)
    assert cursor_1 != cursor_0
    assert source_id in _due_ids(uow_factory, owner_id, now=_NOW)
    with uow_factory() as uow:
        source = uow.provenance.get_source(owner_id, source_id)
    assert source is not None
    assert source.availability_status is SourceAvailability.AVAILABLE

    clock.instant = _FAILURE_BASE + timedelta(hours=40)
    attempt()
    cursor_2 = _newest_snapshot_id_of_any_status(uow_factory, owner_id, source_id)
    assert cursor_2 != cursor_1
    assert source_id in _due_ids(uow_factory, owner_id, now=_NOW)
    with uow_factory() as uow:
        source = uow.provenance.get_source(owner_id, source_id)
    assert source is not None
    assert source.availability_status is SourceAvailability.AVAILABLE

    clock.instant = _FAILURE_BASE + timedelta(hours=72)
    attempt()
    with uow_factory() as uow:
        source = uow.provenance.get_source(owner_id, source_id)
    assert source is not None
    assert source.availability_status is SourceAvailability.UNAVAILABLE
    assert source_id not in _due_ids(uow_factory, owner_id, now=_NOW)


# ---------------------------------------------------------------------------
# Wiring, end to end: the disclosure gate and the enqueue composition,
# proven via `_sweep_once` (see module docstring for why not a live
# `create_app()` boot).
# ---------------------------------------------------------------------------


def _dispatcher(session_factory: sessionmaker[Session]) -> DurableJobDispatcher:
    """A `DurableJobDispatcher` bound to the same database as
    `uow_factory`, registered for `retrieve_source_snapshot` but never
    `.start()`-ed -- jobs stay `queued` forever, so a test can assert on
    reservation semantics (dedupe/idempotency) deterministically, without
    a live background worker thread able to claim and execute one (real
    lane workers poll every 0.1s -- `jobs_events/service.py:434-438`).
    """
    dispatcher = DurableJobDispatcher(
        session_factory,
        pending_cap=100,
        background_age_promotion_seconds=300,
        janitor_retention_seconds=3600,
    )

    def _must_not_execute(execution):
        raise AssertionError(
            "this dispatcher is never started; a reserved job must stay queued"
        )

    dispatcher.register("retrieve_source_snapshot", _must_not_execute)
    return dispatcher


def _sweep_once(
    uow_factory: UnitOfWorkFactory,
    dispatcher: DurableJobDispatcher,
    owner_id: str,
    *,
    now: datetime,
) -> None:
    """Mirrors `apply_staleness_recheck`'s body in `server/src/yuno/api/
    app.py` exactly: the disclosure gate (`uow.provider.get_active_
    disclosure`, skip silently when `None`), the `sources_due_for_recheck`
    selection, and the "mirror the HTTP route" reservation, including its
    idempotency-key cursor. Kept here rather than imported because
    `apply_staleness_recheck` is a closure inside `create_app`'s lifespan
    with no export point (see module docstring).
    """
    with uow_factory() as uow:
        disclosure = uow.provider.get_active_disclosure(
            owner_id, "source-retrieval", "source-network-v1"
        )
        if disclosure is None:
            return
        for source in sources_due_for_recheck(uow, owner_id, now=now):
            snapshots = uow.provenance.list_source_snapshots(owner_id, source.id)
            cursor = snapshots[0].id if snapshots else "never-retrieved"
            key = f"staleness-recheck:{source.id}:{cursor}"
            command, _ = reserve_source_retrieval(
                uow, owner_id, source.id, key, new_id()
            )
            dispatcher.reserve(
                uow.session,
                JobRequest(
                    "retrieve_source_snapshot",
                    owner_id,
                    {"source_id": source.id},
                    dedupe_key=source.id,
                    idempotency_key=key,
                    requested_job_id=command.job_id,
                    lane=JobLane.BACKGROUND,
                    schema_version="source-snapshot-v1",
                    request_ref=f"Source:{source.id}",
                    disclosure_ref=disclosure.id,
                ),
            )
        uow.commit()


def _accept_source_retrieval_disclosure(
    uow_factory: UnitOfWorkFactory, owner_id: str
) -> None:
    with uow_factory() as uow:
        accept_disclosure(uow, owner_id, **_DISCLOSURE_KWARGS)
        uow.commit()


def _job_count(engine: Engine, owner_id: str, kind: str) -> int:
    with engine.connect() as connection:
        return connection.scalar(
            text("SELECT count(*) FROM jobs WHERE owner_id=:owner_id AND kind=:kind"),
            {"owner_id": owner_id, "kind": kind},
        )


def test_wiring_with_disclosure_one_sweep_enqueues_one_job(
    uow_factory: UnitOfWorkFactory,
    session_factory: sessionmaker[Session],
    engine: Engine,
) -> None:
    owner_id = _owner(uow_factory)
    _seed_source(uow_factory, owner_id, suffix="wired-due")
    _accept_source_retrieval_disclosure(uow_factory, owner_id)
    dispatcher = _dispatcher(session_factory)

    _sweep_once(uow_factory, dispatcher, owner_id, now=_NOW)

    assert _job_count(engine, owner_id, "retrieve_source_snapshot") == 1


def test_wiring_without_disclosure_enqueues_nothing(
    uow_factory: UnitOfWorkFactory,
    session_factory: sessionmaker[Session],
    engine: Engine,
) -> None:
    """Proves the no-implicit-network rule instead of asserting it: no
    disclosure on record means nothing is enqueued, and nothing at all is
    written -- not even a `source_retrieval_commands` idempotency record.
    """
    owner_id = _owner(uow_factory)
    _seed_source(uow_factory, owner_id, suffix="undisclosed-due")
    dispatcher = _dispatcher(session_factory)

    _sweep_once(uow_factory, dispatcher, owner_id, now=_NOW)

    assert _job_count(engine, owner_id, "retrieve_source_snapshot") == 0
    with engine.connect() as connection:
        commands = connection.scalar(
            text(
                "SELECT count(*) FROM source_retrieval_commands "
                "WHERE owner_id=:owner_id"
            ),
            {"owner_id": owner_id},
        )
    assert commands == 0


def test_wiring_two_consecutive_sweeps_enqueue_one_job_total(
    uow_factory: UnitOfWorkFactory,
    session_factory: sessionmaker[Session],
    engine: Engine,
) -> None:
    """Two sweeps with no intervening snapshot (the dispatcher here is
    never started, so the first sweep's reservation never executes and
    never appends a new snapshot) must collapse into one job, proving the
    dedupe_key/idempotency_key composition holds and does not pile up
    duplicates on every hourly tick.
    """
    owner_id = _owner(uow_factory)
    _seed_source(uow_factory, owner_id, suffix="repeat-sweep")
    _accept_source_retrieval_disclosure(uow_factory, owner_id)
    dispatcher = _dispatcher(session_factory)

    _sweep_once(uow_factory, dispatcher, owner_id, now=_NOW)
    _sweep_once(uow_factory, dispatcher, owner_id, now=_NOW)

    assert _job_count(engine, owner_id, "retrieve_source_snapshot") == 1
