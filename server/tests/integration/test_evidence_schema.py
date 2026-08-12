"""Database-level guards for IDK-108 evidence ownership and immutability."""

from __future__ import annotations

from sqlalchemy import Engine, inspect, text


def test_transfer_source_uses_owner_and_source_goal_composite_fk(
    engine: Engine,
) -> None:
    foreign_keys = inspect(engine).get_foreign_keys("transferred_evidence_refs")
    assert any(
        fk["referred_table"] == "evidence"
        and fk["constrained_columns"]
        == ["source_evidence_id", "owner_id", "source_goal_id"]
        and fk["referred_columns"] == ["id", "owner_id", "goal_id"]
        for fk in foreign_keys
    )


def test_evidence_guards_exist_at_alembic_head(engine: Engine) -> None:
    expected = {
        "evidence": {
            "trg_evidence_no_update",
            "trg_evidence_no_delete",
            "trg_evidence_no_insert_replace",
        },
        "evidence_tombstones": {
            "trg_evidence_tombstones_no_update",
            "trg_evidence_tombstones_no_delete",
            "trg_evidence_tombstones_no_insert_replace",
        },
        "evidence_delete_snapshots": {
            "trg_evidence_delete_snapshots_no_update",
            "trg_evidence_delete_snapshots_no_delete",
            "trg_evidence_delete_snapshots_no_insert_replace",
        },
        "transferred_evidence_refs": {
            "trg_transferred_evidence_refs_no_update",
            "trg_transferred_evidence_refs_no_delete",
            "trg_transferred_evidence_refs_no_insert_replace",
        },
        "evidence_payloads": {
            "trg_evidence_payloads_no_update",
            "trg_evidence_payloads_governed_delete",
            "trg_evidence_payloads_no_insert_replace",
        },
    }

    with engine.connect() as connection:
        for table, required in expected.items():
            actual = set(
                connection.execute(
                    text(
                        "SELECT name FROM sqlite_master "
                        "WHERE type = 'trigger' AND tbl_name = :table"
                    ),
                    {"table": table},
                ).scalars()
            )
            assert required <= actual

        governed_delete_sql = connection.execute(
            text(
                "SELECT sql FROM sqlite_master "
                "WHERE type = 'trigger' "
                "AND name = 'trg_evidence_payloads_governed_delete'"
            )
        ).scalar_one()

    assert "NOT EXISTS" in governed_delete_sql
    assert "evidence_tombstones" in governed_delete_sql
