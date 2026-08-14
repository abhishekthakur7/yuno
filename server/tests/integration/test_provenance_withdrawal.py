"""Integration coverage for `withdraw_source` (IDK-003 §12 item 4 gap):
withdrawal is one service-level operation that transitions
`sources.availability_status`/`withdrawal_reason` (and, optionally,
`superseded_by_source_id`) and, in the same transaction, invokes
`purge_license_revoked_snapshot_bodies` (`provenance/adapters.py`) exactly
when the reason is `license-revoked`/`license-changed-incompatible`
(IDK-003:119-120) -- never for the other three §11 reasons, since "the
original storage grant was never revoked" for those.

Every assertion here runs against a real, migrated SQLite database, so the
`sources`/`source_snapshots` triggers and CHECK constraints
(`4cb74877e4ba_source_license_withdrawal_supersession.py`,
`6ee79a009c2a_generated_content_cache_and_provenance.py`) are exercised for
real -- in particular `withdrawal_reason_required_iff_withdrawn`
(`provenance/models.py`), which only a single-statement update (status +
reason together) can satisfy.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

import pytest
from sqlalchemy import Engine, text

from yuno.modules.canonical.domain import (
    CanonicalGraphVersion,
    CanonicalVersionStatus,
    Topic,
    TopicIdentity,
)
from yuno.modules.profiles_goals.domain import (
    GoalPath,
    GoalStatus,
    GoalWorkspace,
    TargetCapability,
    TargetLevel,
)
from yuno.modules.provenance.domain import (
    ArtifactProvenanceSnapshot,
    Citation,
    Claim,
    ClaimStatus,
    ClaimType,
    Source,
    SourceAvailability,
    SourceSnapshot,
    SourceWithdrawalReason,
)
from yuno.modules.provenance.service import withdraw_source
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.errors import ConflictError
from yuno.shared.domain.ids import new_id

_REVOCATION_REASONS = (
    SourceWithdrawalReason.LICENSE_REVOKED,
    SourceWithdrawalReason.LICENSE_CHANGED_INCOMPATIBLE,
)
_NON_REVOCATION_REASONS = (
    SourceWithdrawalReason.PUBLISHER_RETRACTED,
    SourceWithdrawalReason.FACTUALLY_SUPERSEDED,
    SourceWithdrawalReason.REGISTRY_DECLINED,
)


def _ts(seconds: int) -> str:
    return f"2026-08-15T00:00:{seconds:02d}.000000Z"


class _FixedClock:
    """A controllable `Clock` (duck-typed, per the project's existing
    `_FixedClock`/`_StepClock` test idiom, e.g.
    `test_provenance_availability_transitions.py`), returning a fixed
    `datetime` so `updated_at` is deterministic across assertions.
    """

    def __init__(self, text_instant: str) -> None:
        self._instant = datetime.fromisoformat(text_instant)

    def now(self) -> datetime:
        return self._instant


def _content_hash(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _owner(uow_factory: UnitOfWorkFactory) -> str:
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Owner")
        uow.commit()
    return owner.id


def _source(uow_factory: UnitOfWorkFactory, owner_id: str, *, suffix: str) -> str:
    """An `available` source with no withdrawal reason yet -- the state
    every real source is in before `withdraw_source` is ever called.
    """
    source = Source(
        new_id(),
        owner_id,
        "fixture",
        "documentation",
        f"Source {suffix}",
        "Fixture publisher",
        f"https://example.invalid/{suffix}",
        "approved-open-license",
        SourceAvailability.AVAILABLE,
        None,
        None,
        _ts(0),
        _ts(0),
    )
    with uow_factory() as uow:
        uow.provenance.add_source(source)
        uow.commit()
    return source.id


def _snapshot(
    uow_factory: UnitOfWorkFactory, owner_id: str, source_id: str, *, suffix: str
) -> SourceSnapshot:
    content_hash = _content_hash(suffix)
    snapshot = SourceSnapshot(
        new_id(),
        owner_id,
        source_id,
        _ts(1),
        f"source-snapshot:{content_hash}",
        content_hash,
        "available",
        "v1",
    )
    with uow_factory() as uow:
        uow.provenance.add_source_snapshot(snapshot)
        uow.commit()
    return snapshot


def _goal_chain(
    uow_factory: UnitOfWorkFactory, owner_id: str, *, suffix: str
) -> tuple[str, str, str]:
    """Minimal graph-version/topic/goal chain `claims`/`citations` require
    (`fk_generated_artifacts_topic`, `fk_citations_goal_owner`), matching
    `test_provenance_license_purge.py::_goal_chain`'s established pattern.
    """
    graph_id = new_id()
    topic_id = f"topic-{suffix}"
    goal = GoalWorkspace(
        new_id(),
        owner_id,
        f"Goal {suffix}",
        GoalPath.LEARN,
        "backend",
        None,
        TargetLevel.SENIOR,
        TargetCapability.IMPLEMENT,
        graph_id,
        GoalStatus.ACTIVE,
        None,
        None,
        1,
        _ts(0),
        _ts(0),
    )
    with uow_factory() as uow:
        uow.canonical.create_topic_identity(
            TopicIdentity(topic_id, topic_id, _ts(0), None)
        )
        uow.canonical.create_version(
            CanonicalGraphVersion(
                graph_id,
                f"graph-{suffix}",
                "v1",
                new_id(),
                CanonicalVersionStatus.PUBLISHED,
                owner_id,
                _ts(0),
                _ts(0),
                None,
            )
        )
        uow.canonical.add_topic(
            Topic(
                graph_id,
                topic_id,
                f"Topic {suffix}",
                "backend",
                ("fixture",),
                "senior",
                "implement",
                "essential",
                0,
                1,
            )
        )
        uow.profiles_goals.create_goal(goal)
        uow.commit()
    return graph_id, topic_id, goal.id


def _citation_referencing_snapshot(
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
    owner_id: str,
    source_id: str,
    snapshot: SourceSnapshot,
    *,
    suffix: str,
) -> tuple[str, str]:
    """Seed one claim + citation pointing at `snapshot`, through the
    generated-artifact parent path (`add_generation_result`), mirroring
    `test_provenance_license_purge.py::_citation_referencing_snapshot`.
    Returns `(claim_id, citation_id)`.
    """
    graph_id, topic_id, goal_id = _goal_chain(uow_factory, owner_id, suffix=suffix)
    artifact_id = new_id()
    attempt_id = new_id()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO generated_artifacts "
                "(id, owner_id, goal_id, graph_version_id, topic_stable_id, layer, "
                "artifact_type, imports_hash, prompt_template_version, "
                "cache_key_hash, state, retryable, row_version, created_at, "
                "updated_at) "
                "VALUES (:id, :owner_id, :goal_id, :graph_version_id, "
                ":topic_stable_id, 'Essential', 'lesson-layer', :imports_hash, "
                "'prompt-v1', :cache_key_hash, 'generating', 0, 1, :now, :now)"
            ),
            {
                "id": artifact_id,
                "owner_id": owner_id,
                "goal_id": goal_id,
                "graph_version_id": graph_id,
                "topic_stable_id": topic_id,
                "imports_hash": _content_hash(f"imports-{suffix}"),
                "cache_key_hash": _content_hash(f"cache-{suffix}"),
                "now": _ts(2),
            },
        )
        connection.execute(
            text(
                "INSERT INTO artifact_generation_attempts "
                "(id, owner_id, goal_id, artifact_id, cache_key_hash, job_id, "
                "kind, status, request_hash, retryable, created_at) "
                "VALUES (:id, :owner_id, :goal_id, :artifact_id, :cache_key_hash, "
                ":job_id, 'generate', 'succeeded', :request_hash, 0, :now)"
            ),
            {
                "id": attempt_id,
                "owner_id": owner_id,
                "goal_id": goal_id,
                "artifact_id": artifact_id,
                "cache_key_hash": _content_hash(f"cache-{suffix}"),
                "job_id": new_id(),
                "request_hash": _content_hash(f"request-{suffix}"),
                "now": _ts(2),
            },
        )

    snapshot_id = new_id()
    claim_id = new_id()
    citation_id = new_id()
    with uow_factory() as uow:
        uow.provenance.add_generation_result(
            ArtifactProvenanceSnapshot(
                snapshot_id,
                owner_id,
                goal_id,
                artifact_id,
                attempt_id,
                _content_hash(f"evidence-{suffix}"),
                _content_hash(f"profile-{suffix}"),
                "fixture-provider",
                "fixture-model",
                _ts(3),
                "1.0",
                "1.0",
                "prompt-v1",
                _content_hash(f"snapshot-{suffix}"),
            ),
            (),
            (
                (
                    Claim(
                        claim_id,
                        owner_id,
                        goal_id,
                        None,
                        artifact_id,
                        snapshot_id,
                        f"Claim text referencing source {suffix}.",
                        ClaimType.FACT,
                        False,
                        ClaimStatus.PENDING,
                    ),
                    (
                        Citation(
                            citation_id,
                            owner_id,
                            goal_id,
                            claim_id,
                            source_id,
                            snapshot.id,
                            "p. 1",
                            "quote",
                            None,
                        ),
                    ),
                ),
            ),
        )
        uow.commit()
    return claim_id, citation_id


def _body_count(engine: Engine, owner_id: str, source_id: str) -> int:
    with engine.connect() as connection:
        return connection.scalar(
            text(
                "SELECT count(*) FROM source_snapshot_bodies "
                "WHERE owner_id=:owner_id AND source_id=:source_id"
            ),
            {"owner_id": owner_id, "source_id": source_id},
        )


def _claim_and_citation_row(
    engine: Engine, claim_id: str, citation_id: str
) -> tuple[dict, dict]:
    """`claim_text`/`locator` live on the `*_bodies` split tables
    (`ClaimBodyRow`/`CitationBodyRow`, `provenance/models.py`), not on
    `claims`/`citations` themselves.
    """
    with engine.connect() as connection:
        claim_row = dict(
            connection.execute(
                text(
                    "SELECT c.status, b.claim_text FROM claims c "
                    "JOIN claim_bodies b ON b.claim_id = c.id WHERE c.id=:id"
                ),
                {"id": claim_id},
            )
            .mappings()
            .one()
        )
        citation_row = dict(
            connection.execute(
                text(
                    "SELECT c.source_id, c.source_snapshot_id, b.locator "
                    "FROM citations c "
                    "JOIN citation_bodies b ON b.citation_id = c.id WHERE c.id=:id"
                ),
                {"id": citation_id},
            )
            .mappings()
            .one()
        )
    return claim_row, citation_row


@pytest.mark.parametrize("reason", _REVOCATION_REASONS)
def test_withdraw_with_license_reason_purges_bodies_and_retains_metadata(
    uow_factory: UnitOfWorkFactory,
    engine: Engine,
    reason: SourceWithdrawalReason,
) -> None:
    owner_id = _owner(uow_factory)
    source_id = _source(uow_factory, owner_id, suffix=reason.value)
    snapshot = _snapshot(uow_factory, owner_id, source_id, suffix=reason.value)
    claim_id, citation_id = _citation_referencing_snapshot(
        engine, uow_factory, owner_id, source_id, snapshot, suffix=reason.value
    )
    assert _body_count(engine, owner_id, source_id) == 1

    updated = withdraw_source(
        uow_factory, owner_id, source_id, reason, clock=_FixedClock(_ts(9))
    )

    assert updated.availability_status is SourceAvailability.WITHDRAWN
    assert updated.withdrawal_reason is reason

    with uow_factory() as uow:
        current = uow.provenance.get_source(owner_id, source_id)
    assert current is not None
    assert current.availability_status is SourceAvailability.WITHDRAWN
    assert current.withdrawal_reason is reason

    # Snapshot bodies are purged...
    assert _body_count(engine, owner_id, source_id) == 0
    # ...but the snapshot metadata row is retained untouched.
    with engine.connect() as connection:
        row = dict(
            connection.execute(
                text(
                    "SELECT content_hash, retrieved_at, status FROM source_snapshots "
                    "WHERE id=:id"
                ),
                {"id": snapshot.id},
            )
            .mappings()
            .one()
        )
    assert row["content_hash"] == snapshot.content_hash
    assert row["retrieved_at"] == snapshot.retrieved_at
    assert row["status"] == snapshot.status

    # claims/citations referencing the source are untouched.
    claim_row, citation_row = _claim_and_citation_row(engine, claim_id, citation_id)
    assert claim_row == {
        "claim_text": f"Claim text referencing source {reason.value}.",
        "status": "published",
    }
    assert citation_row == {
        "source_id": source_id,
        "source_snapshot_id": snapshot.id,
        "locator": "p. 1",
    }


@pytest.mark.parametrize("reason", _NON_REVOCATION_REASONS)
def test_withdraw_with_non_license_reason_sets_status_without_purging_bodies(
    uow_factory: UnitOfWorkFactory,
    engine: Engine,
    reason: SourceWithdrawalReason,
) -> None:
    owner_id = _owner(uow_factory)
    source_id = _source(uow_factory, owner_id, suffix=reason.value)
    snapshot = _snapshot(uow_factory, owner_id, source_id, suffix=reason.value)
    claim_id, citation_id = _citation_referencing_snapshot(
        engine, uow_factory, owner_id, source_id, snapshot, suffix=reason.value
    )
    assert _body_count(engine, owner_id, source_id) == 1

    updated = withdraw_source(
        uow_factory, owner_id, source_id, reason, clock=_FixedClock(_ts(9))
    )

    assert updated.availability_status is SourceAvailability.WITHDRAWN
    assert updated.withdrawal_reason is reason

    with uow_factory() as uow:
        current = uow.provenance.get_source(owner_id, source_id)
    assert current is not None
    assert current.availability_status is SourceAvailability.WITHDRAWN
    assert current.withdrawal_reason is reason

    # The body pointer row is left completely intact -- the original
    # storage grant was never revoked for these three reasons.
    assert _body_count(engine, owner_id, source_id) == 1
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM file_cleanup_intents WHERE owner_id=:owner_id"
                ),
                {"owner_id": owner_id},
            )
            == 0
        )

    claim_row, citation_row = _claim_and_citation_row(engine, claim_id, citation_id)
    assert claim_row == {
        "claim_text": f"Claim text referencing source {reason.value}.",
        "status": "published",
    }
    assert citation_row == {
        "source_id": source_id,
        "source_snapshot_id": snapshot.id,
        "locator": "p. 1",
    }


def test_withdrawing_an_already_withdrawn_source_is_refused(
    uow_factory: UnitOfWorkFactory, engine: Engine
) -> None:
    owner_id = _owner(uow_factory)
    source_id = _source(uow_factory, owner_id, suffix="already-withdrawn")
    snapshot = _snapshot(uow_factory, owner_id, source_id, suffix="already-withdrawn")
    claim_id, citation_id = _citation_referencing_snapshot(
        engine, uow_factory, owner_id, source_id, snapshot, suffix="already-withdrawn"
    )

    withdraw_source(
        uow_factory,
        owner_id,
        source_id,
        SourceWithdrawalReason.PUBLISHER_RETRACTED,
        clock=_FixedClock(_ts(9)),
    )

    with pytest.raises(ConflictError):
        withdraw_source(
            uow_factory,
            owner_id,
            source_id,
            SourceWithdrawalReason.REGISTRY_DECLINED,
            clock=_FixedClock(_ts(10)),
        )

    # Nothing from the refused second call was written: reason/status are
    # still exactly what the first (accepted) withdrawal left behind.
    with uow_factory() as uow:
        current = uow.provenance.get_source(owner_id, source_id)
    assert current is not None
    assert current.availability_status is SourceAvailability.WITHDRAWN
    assert current.withdrawal_reason is SourceWithdrawalReason.PUBLISHER_RETRACTED

    # Body was never purged (publisher-retracted is not a revocation
    # reason) and remains intact after the refused re-withdrawal too.
    assert _body_count(engine, owner_id, source_id) == 1
    claim_row, citation_row = _claim_and_citation_row(engine, claim_id, citation_id)
    assert claim_row == {
        "claim_text": "Claim text referencing source already-withdrawn.",
        "status": "published",
    }
    assert citation_row == {
        "source_id": source_id,
        "source_snapshot_id": snapshot.id,
        "locator": "p. 1",
    }


def test_withdrawal_with_replacement_points_old_source_at_new_source(
    uow_factory: UnitOfWorkFactory,
) -> None:
    owner_id = _owner(uow_factory)
    old_source_id = _source(uow_factory, owner_id, suffix="old")
    new_source_id = _source(uow_factory, owner_id, suffix="new")

    updated = withdraw_source(
        uow_factory,
        owner_id,
        old_source_id,
        SourceWithdrawalReason.FACTUALLY_SUPERSEDED,
        superseded_by_source_id=new_source_id,
        clock=_FixedClock(_ts(9)),
    )

    assert updated.superseded_by_source_id == new_source_id

    with uow_factory() as uow:
        old_source = uow.provenance.get_source(owner_id, old_source_id)
        new_source = uow.provenance.get_source(owner_id, new_source_id)
    assert old_source is not None
    assert old_source.availability_status is SourceAvailability.WITHDRAWN
    assert old_source.withdrawal_reason is SourceWithdrawalReason.FACTUALLY_SUPERSEDED
    assert old_source.superseded_by_source_id == new_source_id
    # Lineage is old -> new only: the replacement row is untouched.
    assert new_source is not None
    assert new_source.availability_status is SourceAvailability.AVAILABLE
    assert new_source.superseded_by_source_id is None
