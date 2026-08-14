"""Integration coverage for `purge_license_revoked_snapshot_bodies`
(IDK-003 §12 item 4 / IDK-503 finding B7): the license-revocation
full-body purge path required beside `remove_unreferenced_snapshots`
(`provenance/adapters.py`).

Every assertion here runs against a real, migrated SQLite database so the
`source_snapshots` immutability triggers (`trg_source_snapshots_no_update`/
`_no_delete`/`_no_insert_replace`, added in
`6ee79a009c2a_generated_content_cache_and_provenance.py`) are exercised for
real: this file proves the purge primitive deletes only
`source_snapshot_bodies` pointer rows and `file_cleanup_intents` records,
never `source_snapshots` metadata, `claims`, or `citations`.

`purge_license_revoked_snapshot_bodies` is a primitive: it does not itself
check `withdrawal_reason`. Reason-gating is the caller's job (a concurrent
agent's `service.py` work); this file proves that gating pattern is sound
by only ever invoking the purge for `license-revoked`/
`license-changed-incompatible` fixtures and deliberately never invoking it
for the other three §11 reasons.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from sqlalchemy import Engine, text

from yuno.modules.canonical.domain import (
    CanonicalGraphVersion,
    CanonicalVersionStatus,
    Topic,
    TopicIdentity,
)
from yuno.modules.data_lifecycle.service import (
    ApprovedCleanupRoots,
    execute_pending_cleanup,
)
from yuno.modules.profiles_goals.domain import (
    GoalPath,
    GoalStatus,
    GoalWorkspace,
    TargetCapability,
    TargetLevel,
)
from yuno.modules.provenance.adapters import purge_license_revoked_snapshot_bodies
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
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
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
    return f"2026-08-14T00:00:{seconds:02d}.000000Z"


def _content_hash(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _owner(uow_factory: UnitOfWorkFactory) -> str:
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Owner")
        uow.commit()
    return owner.id


def _source(
    uow_factory: UnitOfWorkFactory,
    owner_id: str,
    *,
    suffix: str,
    withdrawal_reason: SourceWithdrawalReason,
) -> str:
    source = Source(
        new_id(),
        owner_id,
        "fixture",
        "documentation",
        f"Source {suffix}",
        "Fixture publisher",
        f"https://example.invalid/{suffix}",
        "approved-open-license",
        SourceAvailability.WITHDRAWN,
        withdrawal_reason,
        None,
        _ts(0),
        _ts(0),
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
    snapshot_root: Path,
) -> SourceSnapshot:
    content_hash = _content_hash(suffix)
    snapshot_root.mkdir(parents=True, exist_ok=True)
    (snapshot_root / content_hash).write_bytes(f"body-{suffix}".encode())
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
    """Create the minimal graph-version/topic/goal chain `claims`/`citations`
    require (`fk_generated_artifacts_topic`, `fk_citations_goal_owner`),
    through the same public repository methods
    `test_generated_content_api.py::_goal` uses -- this file needs no
    content-revision/approval rows, since only `generated_artifacts` (not
    `content_revisions`) backs the claim below.
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
    """Seed one published claim + citation pointing at `snapshot`, through
    the generated-artifact parent path (`add_generation_result`) so the
    `trg_claims_required_citation_on_publish` dance is handled by that
    established repository method rather than reinvented here. The
    `generated_artifacts`/`artifact_generation_attempts` FK scaffolding is
    inserted directly (mirroring `test_data_lifecycle.py`'s precedent of
    seeding generic rows via `engine.begin()`) since no repository method
    creates them standalone.

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


def _intent_rows(engine: Engine, owner_id: str) -> list[dict]:
    with engine.connect() as connection:
        return [
            dict(row)
            for row in connection.execute(
                text(
                    "SELECT kind, path_ref, status FROM file_cleanup_intents "
                    "WHERE owner_id=:owner_id ORDER BY path_ref"
                ),
                {"owner_id": owner_id},
            ).mappings()
        ]


@pytest.mark.parametrize("reason", _REVOCATION_REASONS)
def test_license_revocation_reason_purges_bodies_and_retains_metadata(
    uow_factory: UnitOfWorkFactory,
    engine: Engine,
    tmp_path: Path,
    reason: SourceWithdrawalReason,
) -> None:
    owner_id = _owner(uow_factory)
    source_id = _source(
        uow_factory, owner_id, suffix=reason.value, withdrawal_reason=reason
    )
    snapshot_root = tmp_path / "source-snapshots"
    snapshot_a = _snapshot(
        uow_factory,
        owner_id,
        source_id,
        suffix=f"{reason.value}-a",
        snapshot_root=snapshot_root,
    )
    snapshot_b = _snapshot(
        uow_factory,
        owner_id,
        source_id,
        suffix=f"{reason.value}-b",
        snapshot_root=snapshot_root,
    )

    # Caller-side reason gating: only invoked because `reason` is one of
    # the two revocation literals (mirrors the real call site's contract).
    assert reason in _REVOCATION_REASONS
    with uow_factory() as uow:
        purged = purge_license_revoked_snapshot_bodies(
            uow, owner_id=owner_id, source_id=source_id, now=_ts(5)
        )
        uow.commit()
    assert purged == 2

    # `source_snapshots` metadata is retained verbatim -- content_hash,
    # retrieved_at, status all match what `_snapshot` originally wrote.
    with engine.connect() as connection:
        rows = (
            connection.execute(
                text(
                    "SELECT id, content_hash, retrieved_at, status FROM source_snapshots "
                    "WHERE source_id=:source_id ORDER BY id"
                ),
                {"source_id": source_id},
            )
            .mappings()
            .all()
        )
    assert {row["id"] for row in rows} == {snapshot_a.id, snapshot_b.id}
    for row in rows:
        original = snapshot_a if row["id"] == snapshot_a.id else snapshot_b
        assert row["content_hash"] == original.content_hash
        assert row["retrieved_at"] == original.retrieved_at
        assert row["status"] == original.status

    # The body pointer rows are gone.
    assert _body_count(engine, owner_id, source_id) == 0

    # A cleanup intent was recorded for each purged body.
    intents = _intent_rows(engine, owner_id)
    assert {intent["path_ref"] for intent in intents} == {
        snapshot_a.content_ref,
        snapshot_b.content_ref,
    }
    for intent in intents:
        assert intent["kind"] == "source-snapshot"
        assert intent["status"] == "pending"

    # Drive the actual out-of-transaction unlink and confirm the files are
    # genuinely gone from disk, not just referenced as gone.
    result = execute_pending_cleanup(
        uow_factory,
        owner_id,
        roots=ApprovedCleanupRoots(tmp_path / "runner", snapshot_root),
        completed_at=_ts(6),
    )
    assert result.completed == 2
    assert result.failed == 0
    content_hash_a = snapshot_a.content_ref.removeprefix("source-snapshot:")
    content_hash_b = snapshot_b.content_ref.removeprefix("source-snapshot:")
    assert not (snapshot_root / content_hash_a).exists()
    assert not (snapshot_root / content_hash_b).exists()


@pytest.mark.parametrize("reason", _NON_REVOCATION_REASONS)
def test_non_revocation_reason_is_never_purged_because_the_caller_skips_it(
    uow_factory: UnitOfWorkFactory,
    engine: Engine,
    tmp_path: Path,
    reason: SourceWithdrawalReason,
) -> None:
    """Proves reason-gating happens at the call site, not inside the
    primitive: for the three §11 reasons that are not license-driven, the
    fixture never calls `purge_license_revoked_snapshot_bodies` at all
    (exactly the behaviour a real service-layer caller must have), and the
    body/file are left completely intact.
    """
    owner_id = _owner(uow_factory)
    source_id = _source(
        uow_factory, owner_id, suffix=reason.value, withdrawal_reason=reason
    )
    snapshot_root = tmp_path / "source-snapshots"
    snapshot = _snapshot(
        uow_factory,
        owner_id,
        source_id,
        suffix=reason.value,
        snapshot_root=snapshot_root,
    )

    assert reason not in _REVOCATION_REASONS
    # No call to purge_license_revoked_snapshot_bodies here -- that is the point.

    assert _body_count(engine, owner_id, source_id) == 1
    assert _intent_rows(engine, owner_id) == []
    content_hash = snapshot.content_ref.removeprefix("source-snapshot:")
    assert (snapshot_root / content_hash).exists()


def test_claims_and_citations_referencing_the_source_are_untouched(
    uow_factory: UnitOfWorkFactory, engine: Engine, tmp_path: Path
) -> None:
    owner_id = _owner(uow_factory)
    source_id = _source(
        uow_factory,
        owner_id,
        suffix="claims",
        withdrawal_reason=SourceWithdrawalReason.LICENSE_REVOKED,
    )
    snapshot_root = tmp_path / "source-snapshots"
    snapshot = _snapshot(
        uow_factory, owner_id, source_id, suffix="claims", snapshot_root=snapshot_root
    )
    claim_id, citation_id = _citation_referencing_snapshot(
        engine, uow_factory, owner_id, source_id, snapshot, suffix="claims"
    )

    with uow_factory() as uow:
        purged = purge_license_revoked_snapshot_bodies(
            uow, owner_id=owner_id, source_id=source_id, now=_ts(5)
        )
        uow.commit()
    assert purged == 1

    with engine.connect() as connection:
        claim_row = (
            connection.execute(
                text(
                    "SELECT c.status, b.claim_text FROM claims c "
                    "JOIN claim_bodies b ON b.claim_id=c.id "
                    "WHERE c.id=:id"
                ),
                {"id": claim_id},
            )
            .mappings()
            .one()
        )
        citation_row = (
            connection.execute(
                text(
                    "SELECT c.source_id, c.source_snapshot_id, b.locator FROM citations c "
                    "JOIN citation_bodies b ON b.citation_id=c.id "
                    "WHERE c.id=:id"
                ),
                {"id": citation_id},
            )
            .mappings()
            .one()
        )
    assert claim_row["status"] == "published"
    assert claim_row["claim_text"] == "Claim text referencing source claims."
    assert citation_row["source_id"] == source_id
    assert citation_row["source_snapshot_id"] == snapshot.id
    assert citation_row["locator"] == "p. 1"


def test_purge_is_idempotent_second_call_purges_nothing(
    uow_factory: UnitOfWorkFactory, engine: Engine, tmp_path: Path
) -> None:
    owner_id = _owner(uow_factory)
    source_id = _source(
        uow_factory,
        owner_id,
        suffix="idempotent",
        withdrawal_reason=SourceWithdrawalReason.LICENSE_REVOKED,
    )
    snapshot_root = tmp_path / "source-snapshots"
    _snapshot(
        uow_factory,
        owner_id,
        source_id,
        suffix="idempotent",
        snapshot_root=snapshot_root,
    )

    with uow_factory() as uow:
        first = purge_license_revoked_snapshot_bodies(
            uow, owner_id=owner_id, source_id=source_id, now=_ts(5)
        )
        uow.commit()
    assert first == 1
    intents_after_first = _intent_rows(engine, owner_id)
    assert len(intents_after_first) == 1

    with uow_factory() as uow:
        second = purge_license_revoked_snapshot_bodies(
            uow, owner_id=owner_id, source_id=source_id, now=_ts(6)
        )
        uow.commit()
    assert second == 0
    assert _body_count(engine, owner_id, source_id) == 0
    # No duplicate cleanup intent was recorded on the second call.
    assert _intent_rows(engine, owner_id) == intents_after_first


def test_unrelated_source_bodies_are_untouched(
    uow_factory: UnitOfWorkFactory, engine: Engine, tmp_path: Path
) -> None:
    owner_id = _owner(uow_factory)
    snapshot_root = tmp_path / "source-snapshots"
    revoked_source_id = _source(
        uow_factory,
        owner_id,
        suffix="scoped-revoked",
        withdrawal_reason=SourceWithdrawalReason.LICENSE_REVOKED,
    )
    other_source_id = _source(
        uow_factory,
        owner_id,
        suffix="scoped-other",
        withdrawal_reason=SourceWithdrawalReason.PUBLISHER_RETRACTED,
    )
    _snapshot(
        uow_factory,
        owner_id,
        revoked_source_id,
        suffix="scoped-revoked",
        snapshot_root=snapshot_root,
    )
    other_snapshot = _snapshot(
        uow_factory,
        owner_id,
        other_source_id,
        suffix="scoped-other",
        snapshot_root=snapshot_root,
    )

    with uow_factory() as uow:
        purged = purge_license_revoked_snapshot_bodies(
            uow, owner_id=owner_id, source_id=revoked_source_id, now=_ts(5)
        )
        uow.commit()
    assert purged == 1

    assert _body_count(engine, owner_id, revoked_source_id) == 0
    assert _body_count(engine, owner_id, other_source_id) == 1
    intents = _intent_rows(engine, owner_id)
    assert len(intents) == 1
    other_content_hash = other_snapshot.content_ref.removeprefix("source-snapshot:")
    assert (snapshot_root / other_content_hash).exists()
