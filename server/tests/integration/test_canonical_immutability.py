"""SQLite triggers reject UPDATE/DELETE on any `canonical_graph_versions`/
`topics`/`topic_relations`/`content_revisions`/`editorial_approvals` row
belonging to a `published` canonical graph version (spec §4.3, §9.1).

No `canonical` repository exists yet, so these tests write raw SQL
directly against the migrated schema, as `test_audit_append_only.py` does
for `audit_events`'s triggers. Database layer only.

Two things proven per table: the guard fires for a row belonging to a
`published` version, and does *not* fire for a non-published version --
the guard is conditional, not blanket; only a published version's
material is immutable.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import SystemClock, now_text

_IMMUTABILITY_TRIGGERS = {
    "canonical_graph_versions": {
        "trg_canonical_graph_versions_no_update",
        "trg_canonical_graph_versions_no_delete",
        "trg_canonical_graph_versions_no_insert_replace",
    },
    "topics": {"trg_topics_no_update", "trg_topics_no_delete", "trg_topics_no_insert_replace"},
    "topic_relations": {
        "trg_topic_relations_no_update",
        "trg_topic_relations_no_delete",
        "trg_topic_relations_no_insert_replace",
    },
    "content_revisions": {
        "trg_content_revisions_no_update",
        "trg_content_revisions_no_delete",
        "trg_content_revisions_no_insert_replace",
    },
    "editorial_approvals": {
        "trg_editorial_approvals_no_update",
        "trg_editorial_approvals_no_delete",
        "trg_editorial_approvals_no_insert_replace",
    },
}


def _new_id() -> str:
    return uuid.uuid4().hex


def _insert_version(connection, *, owner_id: str, status: str) -> str:
    version_id = _new_id()
    connection.execute(
        text(
            """
            INSERT INTO canonical_graph_versions
                (id, version_label, manifest_version, manifest_hash, status,
                 creator_owner_id, created_at, published_at, supersedes_version_id)
            VALUES
                (:id, :version_label, 'v1', :manifest_hash, :status,
                 :creator_owner_id, :created_at, NULL, NULL)
            """
        ),
        {
            "id": version_id,
            "version_label": f"fixture-{version_id}",
            "manifest_hash": f"hash-{version_id}",
            "status": status,
            "creator_owner_id": owner_id,
            "created_at": now_text(SystemClock()),
        },
    )
    return version_id


def _insert_topic_identity(connection) -> str:
    stable_id = f"fixture-topic-{_new_id()}"
    connection.execute(
        text(
            "INSERT INTO topic_identities (stable_id, stable_slug, created_at, retired_at) "
            "VALUES (:stable_id, :slug, :created_at, NULL)"
        ),
        {"stable_id": stable_id, "slug": f"slug-{stable_id}", "created_at": now_text(SystemClock())},
    )
    return stable_id


def _insert_topic(connection, *, graph_version_id: str, stable_id: str, title: str) -> None:
    connection.execute(
        text(
            """
            INSERT INTO topics
                (graph_version_id, stable_id, title, subject, scope_tags, level_tag,
                 target_capability, recommended_layer, checkpoint_start, checkpoint_end)
            VALUES
                (:graph_version_id, :stable_id, :title, 'dsa', '[]', 'intro',
                 'fixture-capability', 'fixture-layer', 0, 1)
            """
        ),
        {"graph_version_id": graph_version_id, "stable_id": stable_id, "title": title},
    )


@pytest.fixture
def owner_id(uow_factory: UnitOfWorkFactory) -> str:
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Owner")
        uow.commit()
    return owner.id


def test_immutability_triggers_exist_at_alembic_head(engine: Engine) -> None:
    """Every table's trigger set survives to Alembic head. `batch_alter_table`
    silently drops raw-SQL triggers, so a future migration touching any of
    these tables would otherwise regress this without a test catching it.
    """
    with engine.connect() as connection:
        for table, expected in _IMMUTABILITY_TRIGGERS.items():
            names = set(
                connection.execute(
                    text(
                        "SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = :table"
                    ),
                    {"table": table},
                ).scalars()
            )
            missing = expected - names
            assert not missing, f"{table} is missing trigger(s) {sorted(missing)} at Alembic head"


def test_published_canonical_graph_version_rejects_update(engine: Engine, owner_id: str) -> None:
    with engine.begin() as connection:
        version_id = _insert_version(connection, owner_id=owner_id, status="published")

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text("UPDATE canonical_graph_versions SET version_label = 'tampered' WHERE id = :id"),
            {"id": version_id},
        )

    with engine.connect() as connection:
        label = connection.execute(
            text("SELECT version_label FROM canonical_graph_versions WHERE id = :id"), {"id": version_id}
        ).scalar_one()
    assert label == f"fixture-{version_id}"


def test_published_canonical_graph_version_rejects_delete(engine: Engine, owner_id: str) -> None:
    with engine.begin() as connection:
        version_id = _insert_version(connection, owner_id=owner_id, status="published")

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("DELETE FROM canonical_graph_versions WHERE id = :id"), {"id": version_id})

    with engine.connect() as connection:
        count = connection.execute(
            text("SELECT COUNT(*) FROM canonical_graph_versions WHERE id = :id"), {"id": version_id}
        ).scalar()
    assert count == 1


def test_non_published_canonical_graph_version_allows_update(engine: Engine, owner_id: str) -> None:
    """A version that has not been published may still be corrected."""
    with engine.begin() as connection:
        version_id = _insert_version(connection, owner_id=owner_id, status="pending_approval")

    with engine.begin() as connection:
        connection.execute(
            text("UPDATE canonical_graph_versions SET version_label = 'corrected' WHERE id = :id"),
            {"id": version_id},
        )

    with engine.connect() as connection:
        label = connection.execute(
            text("SELECT version_label FROM canonical_graph_versions WHERE id = :id"), {"id": version_id}
        ).scalar_one()
    assert label == "corrected"


def test_topic_belonging_to_published_version_rejects_update_and_delete(engine: Engine, owner_id: str) -> None:
    with engine.begin() as connection:
        version_id = _insert_version(connection, owner_id=owner_id, status="published")
        stable_id = _insert_topic_identity(connection)
        _insert_topic(connection, graph_version_id=version_id, stable_id=stable_id, title="Fixture Topic")

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE topics SET title = 'tampered' WHERE graph_version_id = :gv AND stable_id = :sid"
            ),
            {"gv": version_id, "sid": stable_id},
        )

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text("DELETE FROM topics WHERE graph_version_id = :gv AND stable_id = :sid"),
            {"gv": version_id, "sid": stable_id},
        )

    with engine.connect() as connection:
        title = connection.execute(
            text("SELECT title FROM topics WHERE graph_version_id = :gv AND stable_id = :sid"),
            {"gv": version_id, "sid": stable_id},
        ).scalar_one()
    assert title == "Fixture Topic"


def test_topic_belonging_to_non_published_version_allows_update(engine: Engine, owner_id: str) -> None:
    with engine.begin() as connection:
        version_id = _insert_version(connection, owner_id=owner_id, status="authored")
        stable_id = _insert_topic_identity(connection)
        _insert_topic(connection, graph_version_id=version_id, stable_id=stable_id, title="Draft Topic")

    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE topics SET title = 'corrected' WHERE graph_version_id = :gv AND stable_id = :sid"
            ),
            {"gv": version_id, "sid": stable_id},
        )

    with engine.connect() as connection:
        title = connection.execute(
            text("SELECT title FROM topics WHERE graph_version_id = :gv AND stable_id = :sid"),
            {"gv": version_id, "sid": stable_id},
        ).scalar_one()
    assert title == "corrected"


def test_editorial_approval_for_published_version_rejects_update_and_delete(
    engine: Engine, owner_id: str
) -> None:
    with engine.begin() as connection:
        version_id = _insert_version(connection, owner_id=owner_id, status="published")
        approval_id = _new_id()
        connection.execute(
            text(
                """
                INSERT INTO editorial_approvals
                    (id, graph_version_id, approver_owner_id, approver_role, basis_ref, approved_at)
                VALUES
                    (:id, :graph_version_id, :approver_owner_id, 'designated_editorial_approver',
                     '"fixture-basis"', :approved_at)
                """
            ),
            {
                "id": approval_id,
                "graph_version_id": version_id,
                "approver_owner_id": owner_id,
                "approved_at": now_text(SystemClock()),
            },
        )

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text("UPDATE editorial_approvals SET basis_ref = 'tampered' WHERE id = :id"),
            {"id": approval_id},
        )

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("DELETE FROM editorial_approvals WHERE id = :id"), {"id": approval_id})

    with engine.connect() as connection:
        basis_ref = connection.execute(
            text("SELECT basis_ref FROM editorial_approvals WHERE id = :id"), {"id": approval_id}
        ).scalar_one()
    assert basis_ref == '"fixture-basis"'
