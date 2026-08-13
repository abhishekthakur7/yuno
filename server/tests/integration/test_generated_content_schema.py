"""Database-enforced IDK-207 cache, provenance, and citation invariants."""

from __future__ import annotations

from sqlalchemy import Engine, inspect, text


def test_exact_d3_tuple_and_active_attempt_are_database_authoritative(
    engine: Engine,
) -> None:
    inspector = inspect(engine)
    artifact_columns = {
        column["name"] for column in inspector.get_columns("generated_artifacts")
    }
    assert "body_ref" not in artifact_columns
    body_columns = {
        column["name"] for column in inspector.get_columns("generated_artifact_bodies")
    }
    assert "body_ref" in body_columns
    artifact_uniques = inspector.get_unique_constraints("generated_artifacts")
    assert any(
        unique["name"] == "uq_generated_artifacts_d3_exact_key"
        and unique["column_names"]
        == [
            "graph_version_id",
            "topic_stable_id",
            "goal_id",
            "layer",
            "imports_hash",
            "prompt_template_version",
        ]
        for unique in artifact_uniques
    )
    assert not any(
        unique["column_names"] == ["cache_key_hash"] for unique in artifact_uniques
    ), "the hash is an index aid, never a substitute for the exact six-column key"

    attempt_indexes = inspector.get_indexes("artifact_generation_attempts")
    assert any(
        index["name"] == "uq_artifact_generation_attempts_active_artifact"
        and index["unique"]
        and index["column_names"] == ["artifact_id"]
        for index in attempt_indexes
    )
    with engine.connect() as connection:
        active_sql = connection.execute(
            text(
                "SELECT sql FROM sqlite_master WHERE type='index' "
                "AND name='uq_artifact_generation_attempts_active_artifact'"
            )
        ).scalar_one()
    assert "queued" in active_sql and "running" in active_sql


def test_provenance_ownership_is_composite_end_to_end(engine: Engine) -> None:
    inspector = inspect(engine)

    snapshot_fks = inspector.get_foreign_keys("artifact_provenance_snapshots")
    assert any(
        fk["constrained_columns"] == ["artifact_id", "owner_id", "goal_id"]
        and fk["referred_table"] == "generated_artifacts"
        and fk["referred_columns"] == ["id", "owner_id", "goal_id"]
        for fk in snapshot_fks
    )
    assert any(
        fk["constrained_columns"]
        == ["attempt_id", "owner_id", "goal_id", "artifact_id"]
        and fk["referred_table"] == "artifact_generation_attempts"
        and fk["referred_columns"] == ["id", "owner_id", "goal_id", "artifact_id"]
        for fk in snapshot_fks
    )

    artifact_fks = inspector.get_foreign_keys("generated_artifacts")
    assert any(
        fk["constrained_columns"]
        == ["current_snapshot_id", "owner_id", "goal_id", "id"]
        and fk["referred_table"] == "artifact_provenance_snapshots"
        and fk["referred_columns"] == ["id", "owner_id", "goal_id", "artifact_id"]
        for fk in artifact_fks
    )

    claim_fks = inspector.get_foreign_keys("claims")
    assert any(
        fk["constrained_columns"]
        == ["snapshot_id", "owner_id", "goal_id", "generated_artifact_id"]
        and fk["referred_table"] == "artifact_provenance_snapshots"
        and fk["referred_columns"] == ["id", "owner_id", "goal_id", "artifact_id"]
        for fk in claim_fks
    )

    citation_fks = inspector.get_foreign_keys("citations")
    assert any(
        fk["constrained_columns"] == ["source_snapshot_id", "owner_id", "source_id"]
        and fk["referred_table"] == "source_snapshots"
        and fk["referred_columns"] == ["id", "owner_id", "source_id"]
        for fk in citation_fks
    )


def test_provenance_tables_install_required_immutable_and_citation_guards(
    engine: Engine,
) -> None:
    with engine.connect() as connection:
        triggers = {
            row.tbl_name: set()
            for row in connection.execute(
                text("SELECT DISTINCT tbl_name FROM sqlite_master WHERE type='trigger'")
            )
        }
        for row in connection.execute(
            text("SELECT tbl_name, name FROM sqlite_master WHERE type='trigger'")
        ):
            triggers.setdefault(row.tbl_name, set()).add(row.name)

    for table in ("source_snapshots", "artifact_provenance_snapshots", "citations"):
        assert {
            f"trg_{table}_no_update",
            f"trg_{table}_no_delete",
            f"trg_{table}_no_insert_replace",
        } <= triggers.get(table, set())
    assert {
        "trg_claims_required_citation_on_publish",
        "trg_claims_required_citation_on_published_insert",
        "trg_claims_published_no_update",
        "trg_claims_published_no_delete",
        "trg_claims_no_insert_replace",
    } <= triggers.get("claims", set())
    assert {
        "trg_sources_no_delete",
        "trg_sources_no_insert_replace",
    } <= triggers.get("sources", set())
