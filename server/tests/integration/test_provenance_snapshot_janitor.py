"""Integration coverage for `prune_excess_snapshot_bodies`
(IDK-003 §12 item 9's janitor half / IDK-503 gate 3 finding "20-per-source
retained-snapshot janitor ... Not implemented"): the §6 "Retained snapshots
per source" row required beside `purge_license_revoked_snapshot_bodies`
(`provenance/adapters.py`), which this file's helpers are deliberately
modelled on (`test_provenance_license_purge.py` is the template for the
citation-scaffolding helpers below).

Every assertion here runs against a real, migrated SQLite database so the
`source_snapshots` immutability triggers (`trg_source_snapshots_no_update`/
`_no_delete`/`_no_insert_replace`, created by
`6ee79a009c2a_generated_content_cache_and_provenance.py` and redefined by
`e10d1a0c0100_policy_1_0_body_separation_and_retention.py`) are exercised
for real: this file proves the janitor prunes only `source_snapshot_bodies`
pointer rows and `file_cleanup_intents` records, never `source_snapshots`
metadata.

`prune_excess_snapshot_bodies` orders a source's *body-bearing* snapshots
newest-first by `retrieved_at`; the newest 20 are always retained; among
the rest, every snapshot with no `citations.source_snapshot_id` reference
is pruned, oldest-first, and a cited snapshot is never pruned even when it
falls outside the newest 20.
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

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
from yuno.modules.provenance.adapters import prune_excess_snapshot_bodies
from yuno.modules.provenance.domain import (
    ArtifactProvenanceSnapshot,
    Citation,
    Claim,
    ClaimStatus,
    ClaimType,
    Source,
    SourceAvailability,
    SourceSnapshot,
)
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.ids import new_id

_RETAINED_SNAPSHOTS_PER_SOURCE = 20  # IDK-003 §6, approved and non-configurable
_BASE_TS = datetime(2026, 8, 14, tzinfo=UTC)
_SECOND_OWNER_KIND = "test_secondary_owner"


def _ts(offset_seconds: int) -> str:
    moment = _BASE_TS + timedelta(seconds=offset_seconds)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.000000Z")


def _content_hash(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _owner(uow_factory: UnitOfWorkFactory) -> str:
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Owner")
        uow.commit()
    return owner.id


def _insert_second_owner(
    database_url: str, *, owner_id: str, display_name: str
) -> None:
    """Insert a second `owners` row directly via raw SQL, exactly mirroring
    `test_owner_isolation.py::_insert_second_owner`. `owners.kind` carries
    both `CheckConstraint("kind IN ('local_builtin')")` and `unique=True`,
    so the normal `create_local_owner` path can only ever produce one
    owner; `PRAGMA ignore_check_constraints=ON` on a dedicated, immediately
    closed raw connection is the narrow, precedented escape hatch that lets
    this owner-scoping test prove the janitor's `owner_id` filter actually
    matters, without touching UNIQUE/FK/NOT NULL/PK enforcement or leaking
    the pragma onto the pooled engine other assertions use.
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
            (owner_id, _SECOND_OWNER_KIND, display_name, now_text(SystemClock())),
        )
        connection.commit()
    finally:
        connection.close()


def _source(uow_factory: UnitOfWorkFactory, owner_id: str, *, suffix: str) -> str:
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
    uow_factory: UnitOfWorkFactory,
    owner_id: str,
    source_id: str,
    *,
    suffix: str,
    snapshot_root: Path,
    retrieved_at: str,
) -> SourceSnapshot:
    content_hash = _content_hash(suffix)
    snapshot_root.mkdir(parents=True, exist_ok=True)
    (snapshot_root / content_hash).write_bytes(f"body-{suffix}".encode())
    snapshot = SourceSnapshot(
        new_id(),
        owner_id,
        source_id,
        retrieved_at,
        f"source-snapshot:{content_hash}",
        content_hash,
        "available",
        "v1",
    )
    with uow_factory() as uow:
        uow.provenance.add_source_snapshot(snapshot)
        uow.commit()
    return snapshot


def _snapshots(
    uow_factory: UnitOfWorkFactory,
    owner_id: str,
    source_id: str,
    *,
    count: int,
    snapshot_root: Path,
    suffix: str,
) -> list[SourceSnapshot]:
    """Returns `count` snapshots ordered oldest-first (index 0 is oldest,
    index `count - 1` is newest) via strictly increasing `retrieved_at`.
    """
    return [
        _snapshot(
            uow_factory,
            owner_id,
            source_id,
            suffix=f"{suffix}-{i:02d}",
            snapshot_root=snapshot_root,
            retrieved_at=_ts(i),
        )
        for i in range(count)
    ]


def _goal_chain(
    uow_factory: UnitOfWorkFactory, owner_id: str, *, suffix: str
) -> tuple[str, str, str]:
    """Minimal graph-version/topic/goal chain `claims`/`citations` require,
    identical in shape to `test_provenance_license_purge.py::_goal_chain`.
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
        _ts(9000),
        _ts(9000),
    )
    with uow_factory() as uow:
        uow.canonical.create_topic_identity(
            TopicIdentity(topic_id, topic_id, _ts(9000), None)
        )
        uow.canonical.create_version(
            CanonicalGraphVersion(
                graph_id,
                f"graph-{suffix}",
                "v1",
                new_id(),
                CanonicalVersionStatus.PUBLISHED,
                owner_id,
                _ts(9000),
                _ts(9000),
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
    the generated-artifact parent path (`add_generation_result`), identical
    in shape to `test_provenance_license_purge.py::_citation_referencing_snapshot`.
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
                "now": _ts(9001),
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
                "now": _ts(9001),
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
                _ts(9002),
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


def _body_exists(engine: Engine, snapshot_id: str) -> bool:
    with engine.connect() as connection:
        return (
            connection.scalar(
                text(
                    "SELECT count(*) FROM source_snapshot_bodies "
                    "WHERE snapshot_id=:snapshot_id"
                ),
                {"snapshot_id": snapshot_id},
            )
            == 1
        )


def _snapshot_row_count(engine: Engine, source_id: str) -> int:
    with engine.connect() as connection:
        return connection.scalar(
            text("SELECT count(*) FROM source_snapshots WHERE source_id=:source_id"),
            {"source_id": source_id},
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


def test_at_or_under_the_retained_count_prunes_nothing(
    uow_factory: UnitOfWorkFactory, engine: Engine, tmp_path: Path
) -> None:
    owner_id = _owner(uow_factory)
    source_id = _source(uow_factory, owner_id, suffix="under")
    snapshot_root = tmp_path / "source-snapshots"
    _snapshots(
        uow_factory,
        owner_id,
        source_id,
        count=_RETAINED_SNAPSHOTS_PER_SOURCE,
        snapshot_root=snapshot_root,
        suffix="under",
    )

    with uow_factory() as uow:
        pruned = prune_excess_snapshot_bodies(
            uow, owner_id=owner_id, source_id=source_id, now=_ts(9000)
        )
        uow.commit()

    assert pruned == 0
    assert _body_count(engine, owner_id, source_id) == _RETAINED_SNAPSHOTS_PER_SOURCE
    assert _intent_rows(engine, owner_id) == []


def test_excess_uncited_snapshots_are_pruned_oldest_first(
    uow_factory: UnitOfWorkFactory, engine: Engine, tmp_path: Path
) -> None:
    owner_id = _owner(uow_factory)
    source_id = _source(uow_factory, owner_id, suffix="excess")
    snapshot_root = tmp_path / "source-snapshots"
    snapshots = _snapshots(
        uow_factory,
        owner_id,
        source_id,
        count=25,
        snapshot_root=snapshot_root,
        suffix="excess",
    )  # snapshots[0] is oldest, snapshots[24] is newest

    with uow_factory() as uow:
        pruned = prune_excess_snapshot_bodies(
            uow, owner_id=owner_id, source_id=source_id, now=_ts(9000)
        )
        uow.commit()

    assert pruned == 5
    assert _body_count(engine, owner_id, source_id) == _RETAINED_SNAPSHOTS_PER_SOURCE
    for snapshot in snapshots[:5]:
        assert not _body_exists(engine, snapshot.id)
    for snapshot in snapshots[5:]:
        assert _body_exists(engine, snapshot.id)


def test_a_cited_snapshot_outside_the_newest_20_survives(
    uow_factory: UnitOfWorkFactory, engine: Engine, tmp_path: Path
) -> None:
    owner_id = _owner(uow_factory)
    source_id = _source(uow_factory, owner_id, suffix="cited")
    snapshot_root = tmp_path / "source-snapshots"
    snapshots = _snapshots(
        uow_factory,
        owner_id,
        source_id,
        count=25,
        snapshot_root=snapshot_root,
        suffix="cited",
    )
    cited_snapshot = snapshots[2]  # inside the oldest-5 excess band
    _citation_referencing_snapshot(
        engine, uow_factory, owner_id, source_id, cited_snapshot, suffix="cited"
    )

    with uow_factory() as uow:
        pruned = prune_excess_snapshot_bodies(
            uow, owner_id=owner_id, source_id=source_id, now=_ts(9500)
        )
        uow.commit()

    # 5 excess snapshots, minus the 1 cited one that must survive.
    assert pruned == 4
    assert _body_exists(engine, cited_snapshot.id)
    for snapshot in (snapshots[0], snapshots[1], snapshots[3], snapshots[4]):
        assert not _body_exists(engine, snapshot.id)
    for snapshot in snapshots[5:]:
        assert _body_exists(engine, snapshot.id)
    # The floor is 20 kept, not a hard cap: the surviving cited snapshot
    # pushes the real count to 21.
    assert _body_count(engine, owner_id, source_id) == 21


def test_source_snapshots_metadata_row_count_is_unchanged_by_pruning(
    uow_factory: UnitOfWorkFactory, engine: Engine, tmp_path: Path
) -> None:
    owner_id = _owner(uow_factory)
    source_id = _source(uow_factory, owner_id, suffix="metadata")
    snapshot_root = tmp_path / "source-snapshots"
    _snapshots(
        uow_factory,
        owner_id,
        source_id,
        count=25,
        snapshot_root=snapshot_root,
        suffix="metadata",
    )

    with uow_factory() as uow:
        pruned = prune_excess_snapshot_bodies(
            uow, owner_id=owner_id, source_id=source_id, now=_ts(9000)
        )
        uow.commit()

    assert pruned == 5
    assert _snapshot_row_count(engine, source_id) == 25


def test_a_cleanup_intent_is_recorded_per_pruned_body(
    uow_factory: UnitOfWorkFactory, engine: Engine, tmp_path: Path
) -> None:
    owner_id = _owner(uow_factory)
    source_id = _source(uow_factory, owner_id, suffix="intents")
    snapshot_root = tmp_path / "source-snapshots"
    snapshots = _snapshots(
        uow_factory,
        owner_id,
        source_id,
        count=25,
        snapshot_root=snapshot_root,
        suffix="intents",
    )

    with uow_factory() as uow:
        pruned = prune_excess_snapshot_bodies(
            uow, owner_id=owner_id, source_id=source_id, now=_ts(9000)
        )
        uow.commit()

    assert pruned == 5
    intents = _intent_rows(engine, owner_id)
    assert len(intents) == 5
    expected_refs = {snapshot.content_ref for snapshot in snapshots[:5]}
    assert {intent["path_ref"] for intent in intents} == expected_refs
    for intent in intents:
        assert intent["kind"] == "source-snapshot"
        assert intent["status"] == "pending"


def test_a_second_call_is_idempotent(
    uow_factory: UnitOfWorkFactory, engine: Engine, tmp_path: Path
) -> None:
    owner_id = _owner(uow_factory)
    source_id = _source(uow_factory, owner_id, suffix="idempotent")
    snapshot_root = tmp_path / "source-snapshots"
    _snapshots(
        uow_factory,
        owner_id,
        source_id,
        count=25,
        snapshot_root=snapshot_root,
        suffix="idempotent",
    )

    with uow_factory() as uow:
        first = prune_excess_snapshot_bodies(
            uow, owner_id=owner_id, source_id=source_id, now=_ts(9000)
        )
        uow.commit()
    assert first == 5
    intents_after_first = _intent_rows(engine, owner_id)
    assert len(intents_after_first) == 5

    with uow_factory() as uow:
        second = prune_excess_snapshot_bodies(
            uow, owner_id=owner_id, source_id=source_id, now=_ts(9500)
        )
        uow.commit()

    assert second == 0
    assert _body_count(engine, owner_id, source_id) == _RETAINED_SNAPSHOTS_PER_SOURCE
    # No duplicate cleanup intents were recorded on the second call.
    assert _intent_rows(engine, owner_id) == intents_after_first


def test_owner_scoping_leaves_another_owners_snapshots_untouched(
    uow_factory: UnitOfWorkFactory, engine: Engine, database_url: str, tmp_path: Path
) -> None:
    owner_a = _owner(uow_factory)
    owner_b = new_id()
    _insert_second_owner(database_url, owner_id=owner_b, display_name="Owner B")

    source_a = _source(uow_factory, owner_a, suffix="scope-a")
    source_b = _source(uow_factory, owner_b, suffix="scope-b")
    snapshot_root = tmp_path / "source-snapshots"
    _snapshots(
        uow_factory,
        owner_a,
        source_a,
        count=25,
        snapshot_root=snapshot_root,
        suffix="scope-a",
    )
    _snapshots(
        uow_factory,
        owner_b,
        source_b,
        count=25,
        snapshot_root=snapshot_root,
        suffix="scope-b",
    )

    with uow_factory() as uow:
        pruned = prune_excess_snapshot_bodies(
            uow, owner_id=owner_a, source_id=source_a, now=_ts(9000)
        )
        uow.commit()

    assert pruned == 5
    assert _body_count(engine, owner_a, source_a) == _RETAINED_SNAPSHOTS_PER_SOURCE
    assert _body_count(engine, owner_b, source_b) == 25
    assert _intent_rows(engine, owner_b) == []
