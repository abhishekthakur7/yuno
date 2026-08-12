"""immutable evidence, transfer ownership, and governed tombstones

Revision ID: a61e3f9c2b47
Revises: 6834679f0af4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a61e3f9c2b47"
down_revision: str | Sequence[str] | None = "6834679f0af4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _immutable_triggers(table: str, identity_predicate: str) -> None:
    op.execute(
        f"CREATE TRIGGER trg_{table}_no_update BEFORE UPDATE ON {table} "
        f"BEGIN SELECT RAISE(ABORT, '{table} is immutable: UPDATE is not permitted'); END"
    )
    op.execute(
        f"CREATE TRIGGER trg_{table}_no_delete BEFORE DELETE ON {table} "
        f"BEGIN SELECT RAISE(ABORT, '{table} is immutable: DELETE is not permitted'); END"
    )
    op.execute(
        f"CREATE TRIGGER trg_{table}_no_insert_replace BEFORE INSERT ON {table} "
        f"WHEN EXISTS (SELECT 1 FROM {table} WHERE {identity_predicate}) "
        f"BEGIN SELECT RAISE(ABORT, '{table} is immutable: replacement is not permitted'); END"
    )


def _drop_immutable_triggers(table: str) -> None:
    op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_insert_replace")
    op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete")
    op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_update")


def upgrade() -> None:
    op.create_table(
        "evidence",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("topic_stable_id", sa.Text(), nullable=False),
        sa.Column("evidence_type", sa.Text(), nullable=False),
        sa.Column("capability", sa.Text(), nullable=False),
        sa.Column("payload_hash", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "length(trim(evidence_type)) > 0",
            name=op.f("ck_evidence_evidence_type_non_blank"),
        ),
        sa.CheckConstraint(
            "capability IN ('know','understand','choose','implement','diagnose','defend')",
            name=op.f("ck_evidence_capability_valid"),
        ),
        sa.CheckConstraint(
            "length(trim(payload_hash)) > 0",
            name=op.f("ck_evidence_payload_hash_non_blank"),
        ),
        sa.CheckConstraint(
            "length(trim(origin)) > 0",
            name=op.f("ck_evidence_origin_non_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["owners.id"], name=op.f("fk_evidence_owner_id_owners")
        ),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_evidence_goal_owner",
        ),
        sa.ForeignKeyConstraint(
            ["topic_stable_id"],
            ["topic_identities.stable_id"],
            name=op.f("fk_evidence_topic_stable_id_topic_identities"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence")),
        sa.UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_evidence_id_owner_goal"
        ),
    )
    op.create_index(
        "ix_evidence_owner_goal_topic_created",
        "evidence",
        ["owner_id", "goal_id", "topic_stable_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "evidence_payloads",
        sa.Column("evidence_id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_version", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "length(trim(content_version)) > 0",
            name=op.f("ck_evidence_payloads_content_version_non_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_evidence_payloads_owner_id_owners"),
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id", "owner_id", "goal_id"],
            ["evidence.id", "evidence.owner_id", "evidence.goal_id"],
            name="fk_evidence_payloads_evidence_owner_goal",
        ),
        sa.PrimaryKeyConstraint("evidence_id", name=op.f("pk_evidence_payloads")),
        sa.UniqueConstraint(
            "evidence_id",
            "owner_id",
            "goal_id",
            name="uq_evidence_payloads_evidence_owner_goal",
        ),
    )

    op.create_table(
        "evidence_tombstones",
        sa.Column("evidence_id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("delete_operation_id", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("tombstoned_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "length(trim(delete_operation_id)) > 0",
            name=op.f("ck_evidence_tombstones_delete_operation_id_non_blank"),
        ),
        sa.CheckConstraint(
            "length(trim(reason)) > 0",
            name=op.f("ck_evidence_tombstones_reason_non_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_evidence_tombstones_owner_id_owners"),
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id", "owner_id", "goal_id"],
            ["evidence.id", "evidence.owner_id", "evidence.goal_id"],
            name="fk_evidence_tombstones_evidence_owner_goal",
        ),
        sa.PrimaryKeyConstraint("evidence_id", name=op.f("pk_evidence_tombstones")),
        sa.UniqueConstraint(
            "evidence_id",
            "owner_id",
            "goal_id",
            name="uq_evidence_tombstones_evidence_owner_goal",
        ),
    )

    op.create_table(
        "evidence_delete_snapshots",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("impact_json", sa.Text(), nullable=False),
        sa.Column("impact_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "json_valid(impact_json)",
            name=op.f("ck_evidence_delete_snapshots_impact_json_valid"),
        ),
        sa.CheckConstraint(
            "json_type(impact_json) = 'object'",
            name=op.f("ck_evidence_delete_snapshots_impact_json_object"),
        ),
        sa.CheckConstraint(
            "length(trim(impact_hash)) > 0",
            name=op.f("ck_evidence_delete_snapshots_impact_hash_non_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_evidence_delete_snapshots_owner_id_owners"),
        ),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_evidence_delete_snapshots_goal_owner",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence_delete_snapshots")),
        sa.UniqueConstraint(
            "id",
            "owner_id",
            "goal_id",
            name="uq_evidence_delete_snapshots_id_owner_goal",
        ),
    )

    with op.batch_alter_table("transferred_evidence_refs", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_transferred_evidence_refs_source_evidence_owner_goal",
            "evidence",
            ["source_evidence_id", "owner_id", "source_goal_id"],
            ["id", "owner_id", "goal_id"],
        )
        batch_op.create_unique_constraint(
            "uq_transferred_evidence_refs_state_evidence",
            ["learning_state_id", "source_evidence_id"],
        )

    with op.batch_alter_table("goal_workspaces", schema=None) as batch_op:
        batch_op.drop_constraint("status_valid", type_="check")
        batch_op.create_check_constraint(
            "status_valid", "status IN ('active','archived','tombstoned')"
        )

    _immutable_triggers("evidence", "id = NEW.id")
    _immutable_triggers("evidence_tombstones", "evidence_id = NEW.evidence_id")
    _immutable_triggers("evidence_delete_snapshots", "id = NEW.id")
    _immutable_triggers("transferred_evidence_refs", "id = NEW.id")

    op.execute(
        "CREATE TRIGGER trg_evidence_payloads_no_update BEFORE UPDATE ON evidence_payloads "
        "BEGIN SELECT RAISE(ABORT, 'evidence_payloads is immutable: UPDATE is not permitted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_evidence_payloads_governed_delete BEFORE DELETE ON evidence_payloads "
        "WHEN NOT EXISTS (SELECT 1 FROM evidence_tombstones t "
        "WHERE t.evidence_id = OLD.evidence_id AND t.owner_id = OLD.owner_id "
        "AND t.goal_id = OLD.goal_id) "
        "BEGIN SELECT RAISE(ABORT, 'evidence payload deletion requires a tombstone'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_evidence_payloads_no_insert_replace BEFORE INSERT ON evidence_payloads "
        "WHEN EXISTS (SELECT 1 FROM evidence_payloads p WHERE p.evidence_id = NEW.evidence_id) "
        "OR EXISTS (SELECT 1 FROM evidence_tombstones t WHERE t.evidence_id = NEW.evidence_id) "
        "BEGIN SELECT RAISE(ABORT, 'evidence payload replacement or restoration is not permitted'); END"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_evidence_payloads_no_insert_replace")
    op.execute("DROP TRIGGER IF EXISTS trg_evidence_payloads_governed_delete")
    op.execute("DROP TRIGGER IF EXISTS trg_evidence_payloads_no_update")
    _drop_immutable_triggers("transferred_evidence_refs")
    _drop_immutable_triggers("evidence_delete_snapshots")
    _drop_immutable_triggers("evidence_tombstones")
    _drop_immutable_triggers("evidence")

    with op.batch_alter_table("goal_workspaces", schema=None) as batch_op:
        batch_op.drop_constraint("status_valid", type_="check")
        batch_op.create_check_constraint(
            "status_valid", "status IN ('active','archived')"
        )

    with op.batch_alter_table("transferred_evidence_refs", schema=None) as batch_op:
        batch_op.drop_constraint(
            "uq_transferred_evidence_refs_state_evidence", type_="unique"
        )
        batch_op.drop_constraint(
            "fk_transferred_evidence_refs_source_evidence_owner_goal",
            type_="foreignkey",
        )

    op.drop_table("evidence_delete_snapshots")
    op.drop_table("evidence_tombstones")
    op.drop_table("evidence_payloads")
    op.drop_index("ix_evidence_owner_goal_topic_created", table_name="evidence")
    op.drop_table("evidence")
