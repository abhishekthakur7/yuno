from __future__ import annotations

from sqlalchemy import Engine, inspect, text


def test_notebook_and_review_composite_ownership_and_queue_index(
    engine: Engine,
) -> None:
    inspector = inspect(engine)

    entry_fks = inspector.get_foreign_keys("notebook_entries")
    assert any(
        fk["constrained_columns"] == ["goal_id", "owner_id"]
        and fk["referred_table"] == "goal_workspaces"
        and fk["referred_columns"] == ["id", "owner_id"]
        for fk in entry_fks
    )
    assert any(
        fk["constrained_columns"] == ["evidence_id", "owner_id", "goal_id"]
        and fk["referred_table"] == "evidence"
        and fk["referred_columns"] == ["id", "owner_id", "goal_id"]
        for fk in entry_fks
    )
    assert any(
        fk["constrained_columns"] == ["source_id", "owner_id"]
        and fk["referred_table"] == "sources"
        and fk["referred_columns"] == ["id", "owner_id"]
        for fk in entry_fks
    )

    attempt_fks = inspector.get_foreign_keys("review_attempts")
    assert any(
        fk["constrained_columns"] == ["review_item_id", "owner_id", "goal_id"]
        and fk["referred_table"] == "review_items"
        and fk["referred_columns"] == ["id", "owner_id", "goal_id"]
        for fk in attempt_fks
    )

    indexes = inspector.get_indexes("review_items")
    assert any(
        index["name"] == "ix_review_items_owner_goal_status_due"
        and index["column_names"] == ["owner_id", "goal_id", "status", "due_at"]
        for index in indexes
    )


def test_database_installs_append_only_review_attempt_guards(engine: Engine) -> None:
    with engine.connect() as connection:
        trigger_names = set(
            connection.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'trigger' AND tbl_name = 'review_attempts'"
                )
            ).scalars()
        )

    assert {
        "trg_review_attempts_no_update",
        "trg_review_attempts_no_delete",
        "trg_review_attempts_no_insert_replace",
    } <= trigger_names


def test_review_writes_have_no_progress_memo_invalidation_trigger(
    engine: Engine,
) -> None:
    with engine.connect() as connection:
        trigger_sql = "\n".join(
            connection.execute(
                text(
                    "SELECT coalesce(sql, '') FROM sqlite_master "
                    "WHERE type = 'trigger' AND tbl_name IN "
                    "('review_items','review_attempts','goal_review_preferences')"
                )
            ).scalars()
        ).lower()

    assert "goal_progress_memos" not in trigger_sql
