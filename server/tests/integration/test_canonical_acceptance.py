"""Cross-cutting acceptance tests: every read path, every table's
database-layer immutability guard, the two-version fixture, and per-rule
publish-transaction rollback.

Uses the real `uow_factory`/`engine`/`client` fixtures (`tests/conftest.py`)
against a genuinely migrated SQLite database, and `tests.fixtures.canonical`'s
already-validated MVP fixtures -- never a hand-built dict, never a mocked
repository or session.
"""

from __future__ import annotations

import inspect

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import IntegrityError

from tests.fixtures.canonical import EXPECTED_VIOLATIONS, load_fixture
from yuno.api.routes import canonical as canonical_routes
from yuno.modules.canonical.domain import (
    CanonicalGraphVersion,
    CanonicalVersionStatus,
    Topic,
    TopicIdentity,
    TopicRelation,
)
from yuno.modules.canonical.models import (
    CanonicalGraphVersionRow,
    ContentRevisionRow,
    EditorialApprovalRow,
    TopicIdentityRow,
    TopicRelationRow,
    TopicRow,
)
from yuno.modules.canonical.ports import CanonicalGraphRepository
from yuno.modules.canonical.publisher import publish_canonical_graph
from yuno.modules.identity.domain import Role
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.errors import DomainValidationError
from yuno.shared.domain.ids import new_id

_CANONICAL_TABLES = (
    CanonicalGraphVersionRow,
    TopicIdentityRow,
    TopicRow,
    TopicRelationRow,
    ContentRevisionRow,
    EditorialApprovalRow,
)


def _row_counts(engine: Engine) -> dict[str, int]:
    with engine.connect() as connection:
        return {
            model.__tablename__: connection.execute(
                select(func.count()).select_from(model)
            ).scalar_one()
            for model in _CANONICAL_TABLES
        }


def _assert_canonical_tables_empty(engine: Engine) -> None:
    counts = _row_counts(engine)
    assert all(count == 0 for count in counts.values()), counts


@pytest.fixture
def approver_owner_id(uow_factory: UnitOfWorkFactory) -> str:
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Acceptance Approver")
        uow.owners.grant_role(
            owner.id, Role.DESIGNATED_EDITORIAL_APPROVER, assigned_by_owner_id=owner.id
        )
        uow.commit()
    return owner.id


# ---------------------------------------------------------------------------
# 1. A half-seeded version (no approval row) is unreadable through EVERY
#    read path the codebase now has -- enumerated, not spot-checked.
# ---------------------------------------------------------------------------


def test_every_read_path_in_the_codebase_is_enumerated_here() -> None:
    """Guards the enumeration itself: if a future ticket adds a read
    method to `CanonicalGraphRepository` or a route to
    `yuno.api.routes.canonical`, this test fails until the new path is
    added to `test_half_seeded_version_unreadable_through_every_read_path`
    below, instead of that test silently covering fewer paths than exist.

    No `roadmap`/`topic-studio`/`search`/`generation`/`diff` module exists
    yet (spec §6.1 step 6 names these as future read surfaces); `canonical`'s
    own repository and the two API routes are the entire set today.
    """
    read_methods = {
        name
        for name, _ in inspect.getmembers(CanonicalGraphRepository, predicate=inspect.isfunction)
        if name.startswith(("get_", "list_"))
    }
    assert read_methods == {
        "get_published_version",
        "list_published_versions",
        "get_published_topics",
        "get_published_relations",
    }

    route_paths = {route.path for route in canonical_routes.router.routes}
    assert route_paths == {"/canonical/versions", "/canonical/versions/{version_id}"}


def _seed_half_seeded_material(uow_factory: UnitOfWorkFactory, *, owner_id: str) -> str:
    """Writes the `half_seeded` fixture's topics/relations directly through
    the repository, deliberately never calling `record_approval`. The real
    offline publisher is all-or-nothing (approval always last) and never
    leaves a version in this state; this reproduces the failure mode spec
    §6.1 step 6 guards against: dependent material exists but the
    `EditorialApproval` row does not (e.g. a process killed between the two).
    """
    fixture = load_fixture("half_seeded")
    assert fixture.approval is None

    version_id = new_id()
    created_at = now_text(SystemClock())
    with uow_factory() as uow:
        uow.canonical.create_version(
            CanonicalGraphVersion(
                id=version_id,
                version_label=fixture.manifest.version_label,
                manifest_version=fixture.manifest.manifest_version,
                manifest_hash=fixture.manifest.manifest_hash,
                status=CanonicalVersionStatus.PENDING_APPROVAL,
                creator_owner_id=owner_id,
                created_at=created_at,
                published_at=None,
                supersedes_version_id=None,
            )
        )
        for topic in fixture.manifest.topics:
            uow.canonical.create_topic_identity(
                TopicIdentity(
                    stable_id=topic.stable_id,
                    stable_slug=fixture.topic_identity_slugs[topic.stable_id],
                    created_at=created_at,
                    retired_at=None,
                )
            )
            uow.canonical.add_topic(
                Topic(
                    graph_version_id=version_id,
                    stable_id=topic.stable_id,
                    title=topic.title,
                    subject=topic.subject,
                    scope_tags=topic.scope_tags,
                    level_tag=topic.level_tag,
                    target_capability=topic.target_capability,
                    recommended_layer=topic.recommended_layer,
                    checkpoint_start=topic.checkpoint_start,
                    checkpoint_end=topic.checkpoint_end,
                )
            )
        for relation in fixture.manifest.relations:
            uow.canonical.add_relation(
                TopicRelation(
                    id=relation.id,
                    graph_version_id=version_id,
                    from_stable_id=relation.from_stable_id,
                    to_stable_id=relation.to_stable_id,
                    relation_type=relation.relation_type,
                    rationale=relation.rationale,
                )
            )
        # Deliberately no `uow.canonical.record_approval(...)` call.
        uow.commit()
    return version_id


def test_half_seeded_version_unreadable_through_every_read_path(
    client: TestClient, uow_factory: UnitOfWorkFactory
) -> None:
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
    assert owner is not None
    version_id = _seed_half_seeded_material(uow_factory, owner_id=owner.id)
    fixture_version_label = load_fixture("half_seeded").manifest.version_label

    # -- Repository reads (all four) --
    with uow_factory() as uow:
        assert uow.canonical.get_published_version(version_id) is None
        assert version_id not in {v.id for v in uow.canonical.list_published_versions()}
        assert uow.canonical.get_published_topics(version_id) == []
        assert uow.canonical.get_published_relations(version_id) == []

    # -- API: GET /api/v1/canonical/versions --
    list_response = client.get("/api/v1/canonical/versions")
    assert list_response.status_code == 200
    assert version_id not in {entry["id"] for entry in list_response.json()}

    # -- API: GET /api/v1/canonical/versions/{id} --
    detail_response = client.get(f"/api/v1/canonical/versions/{version_id}")
    assert detail_response.status_code == 404

    # Contrast case: the publish-time lookups (`version_label_exists` and
    # friends) are deliberately NOT approval-gated -- they exist so the
    # publisher can detect a label/hash/stable-id conflict against a
    # not-yet-approved row (repository.py's docstring). Not a "read path".
    with uow_factory() as uow:
        assert uow.canonical.version_label_exists(fixture_version_label) is True


# ---------------------------------------------------------------------------
# 2. Database-layer rejection of UPDATE/DELETE against an approved
#    version's rows via raw SQL, bypassing the repository entirely.
# ---------------------------------------------------------------------------


def _publish_v1(engine: Engine, uow_factory: UnitOfWorkFactory, *, approver_owner_id: str) -> str:
    fixture = load_fixture("v1_approved")
    assert fixture.approval is not None
    version = publish_canonical_graph(
        engine=engine,
        uow_factory=uow_factory,
        manifest=fixture.manifest,
        actor_owner_id=approver_owner_id,
        basis_ref=fixture.approval.basis_ref,
        topic_identity_slugs=fixture.topic_identity_slugs,
    )
    return version.id


@pytest.mark.parametrize(
    "table",
    [
        "canonical_graph_versions",
        "topics",
        "topic_relations",
        "content_revisions",
        "editorial_approvals",
    ],
)
def test_raw_sql_update_against_approved_version_rows_is_rejected_for_every_table(
    engine: Engine, uow_factory: UnitOfWorkFactory, approver_owner_id: str, table: str
) -> None:
    """Raw SQL, bypassing `SqlAlchemyCanonicalRepository` entirely, against
    a version published through the real end-to-end publisher path (rather
    than the raw-seeded rows `test_canonical_immutability.py` uses).
    """
    version_id = _publish_v1(engine, uow_factory, approver_owner_id=approver_owner_id)

    with engine.connect() as connection:
        pk_column, pk_value = _one_row_pk(connection, table, version_id)

    update_sql = {
        "canonical_graph_versions": "UPDATE canonical_graph_versions SET version_label = 'tampered' WHERE id = :pk",
        "topics": "UPDATE topics SET title = 'tampered' WHERE graph_version_id = :pk",
        "topic_relations": "UPDATE topic_relations SET rationale = 'tampered' WHERE id = :pk",
        "content_revisions": "UPDATE content_revisions SET markdown_ref = 'tampered' WHERE id = :pk",
        "editorial_approvals": "UPDATE editorial_approvals SET basis_ref = 'tampered' WHERE id = :pk",
    }[table]

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text(update_sql), {"pk": pk_value})

    delete_sql = f"DELETE FROM {table} WHERE {pk_column} = :pk"
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text(delete_sql), {"pk": pk_value})


def _one_row_pk(connection, table: str, version_id: str) -> tuple[str, str]:
    """(pk_column_name, pk_value) for one row of `table` belonging to
    `version_id`."""
    if table == "canonical_graph_versions":
        return "id", version_id
    if table == "topics":
        return (
            "graph_version_id",
            connection.execute(
                text("SELECT graph_version_id FROM topics WHERE graph_version_id = :v LIMIT 1"),
                {"v": version_id},
            ).scalar_one(),
        )
    if table == "topic_relations":
        return (
            "id",
            connection.execute(
                text("SELECT id FROM topic_relations WHERE graph_version_id = :v LIMIT 1"),
                {"v": version_id},
            ).scalar_one(),
        )
    if table == "content_revisions":
        return (
            "id",
            connection.execute(
                text("SELECT id FROM content_revisions WHERE graph_version_id = :v LIMIT 1"),
                {"v": version_id},
            ).scalar_one(),
        )
    if table == "editorial_approvals":
        return (
            "id",
            connection.execute(
                text("SELECT id FROM editorial_approvals WHERE graph_version_id = :v LIMIT 1"),
                {"v": version_id},
            ).scalar_one(),
        )
    raise AssertionError(f"unhandled table {table!r}")


def test_upsert_on_conflict_do_update_against_an_approved_version_is_rejected(
    engine: Engine, uow_factory: UnitOfWorkFactory, approver_owner_id: str
) -> None:
    """`INSERT ... ON CONFLICT(id) DO UPDATE` fires SQLite's UPDATE
    trigger for the DO UPDATE action, so it's already covered by the
    plain `no_update` trigger -- locked in here against regression.
    """
    version_id = _publish_v1(engine, uow_factory, approver_owner_id=approver_owner_id)

    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT id, version_label, manifest_version, manifest_hash, status, "
                "creator_owner_id, created_at, published_at, supersedes_version_id "
                "FROM canonical_graph_versions WHERE id = :id"
            ),
            {"id": version_id},
        ).mappings().one()

    upsert_sql = text(
        """
        INSERT INTO canonical_graph_versions
            (id, version_label, manifest_version, manifest_hash, status,
             creator_owner_id, created_at, published_at, supersedes_version_id)
        VALUES
            (:id, 'upserted-tampered', :manifest_version, :manifest_hash, :status,
             :creator_owner_id, :created_at, :published_at, :supersedes_version_id)
        ON CONFLICT(id) DO UPDATE SET version_label = excluded.version_label
        """
    )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(upsert_sql, dict(row))

    with engine.connect() as connection:
        label = connection.execute(
            text("SELECT version_label FROM canonical_graph_versions WHERE id = :id"), {"id": version_id}
        ).scalar_one()
    assert label == row["version_label"]


def test_insert_or_replace_against_an_approved_version_is_rejected(
    engine: Engine, uow_factory: UnitOfWorkFactory, approver_owner_id: str
) -> None:
    version_id = _publish_v1(engine, uow_factory, approver_owner_id=approver_owner_id)

    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT id, version_label, manifest_version, manifest_hash, status, "
                "creator_owner_id, created_at, published_at, supersedes_version_id "
                "FROM canonical_graph_versions WHERE id = :id"
            ),
            {"id": version_id},
        ).mappings().one()

    replace_sql = text(
        """
        INSERT OR REPLACE INTO canonical_graph_versions
            (id, version_label, manifest_version, manifest_hash, status,
             creator_owner_id, created_at, published_at, supersedes_version_id)
        VALUES
            (:id, 'replaced-tampered', :manifest_version, :manifest_hash, :status,
             :creator_owner_id, :created_at, :published_at, :supersedes_version_id)
        """
    )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(replace_sql, dict(row))

    with engine.connect() as connection:
        label = connection.execute(
            text("SELECT version_label FROM canonical_graph_versions WHERE id = :id"), {"id": version_id}
        ).scalar_one()
    assert label == row["version_label"]


# ---------------------------------------------------------------------------
# 3. The two-version fixture (v1 -> v2) is independently publishable and
#    each remains immutable afterwards.
# ---------------------------------------------------------------------------


def test_v1_then_v2_each_independently_publishable_and_each_remains_immutable(
    engine: Engine, uow_factory: UnitOfWorkFactory, approver_owner_id: str
) -> None:
    v1 = load_fixture("v1_approved")
    v2 = load_fixture("v2_approved")
    assert v1.approval is not None
    assert v2.approval is not None

    v1_version = publish_canonical_graph(
        engine=engine,
        uow_factory=uow_factory,
        manifest=v1.manifest,
        actor_owner_id=approver_owner_id,
        basis_ref=v1.approval.basis_ref,
        topic_identity_slugs=v1.topic_identity_slugs,
    )

    # v1 immutable immediately after its own publish, before v2 exists.
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text("UPDATE canonical_graph_versions SET version_label = 'tampered-v1-early' WHERE id = :id"),
            {"id": v1_version.id},
        )

    v2_version = publish_canonical_graph(
        engine=engine,
        uow_factory=uow_factory,
        manifest=v2.manifest,
        actor_owner_id=approver_owner_id,
        basis_ref=v2.approval.basis_ref,
        topic_identity_slugs=v2.topic_identity_slugs,
    )

    # Both independently readable through the approval-gated repository.
    with uow_factory() as uow:
        assert uow.canonical.get_published_version(v1_version.id) is not None
        assert uow.canonical.get_published_version(v2_version.id) is not None
        v1_topics = {t.stable_id for t in uow.canonical.get_published_topics(v1_version.id)}
        v2_topics = {t.stable_id for t in uow.canonical.get_published_topics(v2_version.id)}
    assert v1_topics == {t.stable_id for t in v1.manifest.topics}
    assert v2_topics == {t.stable_id for t in v2.manifest.topics}

    # v1 still immutable after v2 has landed -- publishing v2 never
    # mutates v1's rows, even the stable ids it carries forward
    # (spec §4.3: identities persist unchanged across versions).
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text("UPDATE canonical_graph_versions SET version_label = 'tampered-v1-late' WHERE id = :id"),
            {"id": v1_version.id},
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text("DELETE FROM canonical_graph_versions WHERE id = :id"), {"id": v1_version.id}
        )

    # v2 immutable too.
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text("UPDATE canonical_graph_versions SET version_label = 'tampered-v2' WHERE id = :id"),
            {"id": v2_version.id},
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text("DELETE FROM canonical_graph_versions WHERE id = :id"), {"id": v2_version.id}
        )

    with engine.connect() as connection:
        labels = dict(
            connection.execute(
                text("SELECT id, version_label FROM canonical_graph_versions")
            ).all()
        )
    assert labels[v1_version.id] == v1.manifest.version_label
    assert labels[v2_version.id] == v2.manifest.version_label

    # Both remain listed side by side -- supersession is a derived read,
    # not a mutation of v1; these are two independent published versions.
    with uow_factory() as uow:
        listed_ids = {v.id for v in uow.canonical.list_published_versions()}
    assert {v1_version.id, v2_version.id} <= listed_ids


# ---------------------------------------------------------------------------
# 4. A validation failure rolls back the ENTIRE publish transaction --
#    verified per rule.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_name",
    [
        "invalid_prerequisite_cycle",  # bad DAG
        "invalid_missing_stable_id",  # missing stable ID
        "invalid_out_of_boundary_subject",  # out-of-boundary curriculum tag
        "invalid_dsa_missing_scenario",  # DSA node without scenario relation
        "invalid_go_node",  # Go node
    ],
)
def test_each_named_validation_rule_rejects_before_any_write_and_leaves_tables_empty(
    engine: Engine, uow_factory: UnitOfWorkFactory, approver_owner_id: str, fixture_name: str
) -> None:
    fixture = load_fixture(fixture_name)

    with pytest.raises(DomainValidationError) as exc_info:
        publish_canonical_graph(
            engine=engine,
            uow_factory=uow_factory,
            manifest=fixture.manifest,
            actor_owner_id=approver_owner_id,
            basis_ref="fixture-basis-should-never-be-used",
            topic_identity_slugs=fixture.topic_identity_slugs,
        )

    actual_codes = {field_error["code"] for field_error in exc_info.value.field_errors}
    expected_codes = {code.value for code in EXPECTED_VIOLATIONS[fixture_name]}
    assert expected_codes <= actual_codes, (fixture_name, actual_codes, expected_codes)

    # The entire transaction rolled back: not one row of any of the six
    # tables this manifest would otherwise have populated exists.
    _assert_canonical_tables_empty(engine)

    # And every other read path agrees nothing is visible either.
    with uow_factory() as uow:
        assert uow.canonical.list_published_versions() == []


def test_validation_runs_before_any_uow_is_even_opened(
    engine: Engine, uow_factory: UnitOfWorkFactory, approver_owner_id: str
) -> None:
    """Stronger than "rolled back": for a validation failure specifically,
    `publish_canonical_graph` raises before `uow_factory()` is ever
    called at all (spec §3.4 -- validation is pure, framework-free work
    that must not run inside, or even open, a SQLite transaction). Proven
    by wrapping `uow_factory` and asserting it is never invoked.
    """
    fixture = load_fixture("invalid_prerequisite_cycle")
    calls: list[int] = []

    def _counting_uow_factory():
        calls.append(1)
        return uow_factory()

    with pytest.raises(DomainValidationError):
        publish_canonical_graph(
            engine=engine,
            uow_factory=_counting_uow_factory,
            manifest=fixture.manifest,
            actor_owner_id=approver_owner_id,
            basis_ref="fixture-basis-should-never-be-used",
            topic_identity_slugs=fixture.topic_identity_slugs,
        )

    assert calls == []
