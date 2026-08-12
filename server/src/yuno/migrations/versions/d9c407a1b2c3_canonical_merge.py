"""atomic canonical merge proposals and follow-up intents

Revision ID: d9c407a1b2c3
Revises: f406a1b2c3d4
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d9c407a1b2c3"
down_revision: str | Sequence[str] | None = "f406a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_overlay_entries_no_delete")
    op.execute("DROP TRIGGER IF EXISTS trg_overlay_entries_no_update")
    with op.batch_alter_table("overlay_entries") as batch:
        batch.drop_constraint("entry_type_valid", type_="check")
        batch.drop_constraint("source_valid", type_="check")
        batch.create_check_constraint(
            "entry_type_valid",
            "entry_type IN ('order_constraint','skip','depth','bridge','recommendation','merge_resolution','archived_local_topic')",
        )
        batch.create_check_constraint(
            "source_valid",
            "source IN ('learner','diagnostic_confirmation','overlay_proposal','canonical_merge')",
        )
    _create_overlay_triggers()

    op.create_table(
        "canonical_merge_proposals",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), sa.ForeignKey("owners.id"), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column(
            "base_version_id",
            sa.Text(),
            sa.ForeignKey("editorial_approvals.graph_version_id"),
            nullable=False,
        ),
        sa.Column(
            "target_version_id",
            sa.Text(),
            sa.ForeignKey("editorial_approvals.graph_version_id"),
            nullable=False,
        ),
        sa.Column("goal_row_version", sa.Integer(), nullable=False),
        sa.Column("diff_hash", sa.Text(), nullable=False),
        sa.Column("local_state_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("decided_at", sa.Text()),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"], ["goal_workspaces.id", "goal_workspaces.owner_id"]
        ),
        sa.CheckConstraint(
            "status IN ('awaiting','postponed','dismissed','accepted')",
            name="status_valid",
        ),
        sa.CheckConstraint(
            "base_version_id != target_version_id", name="versions_distinct"
        ),
        sa.UniqueConstraint(
            "id",
            "owner_id",
            "goal_id",
            name="uq_canonical_merge_proposals_id_owner_goal",
        ),
    )
    op.create_index(
        "uq_canonical_merge_proposals_active_target",
        "canonical_merge_proposals",
        ["goal_id", "target_version_id"],
        unique=True,
        sqlite_where=sa.text("status = 'awaiting'"),
    )
    op.create_table(
        "merge_items",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), sa.ForeignKey("owners.id"), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column(
            "proposal_id",
            sa.Text(),
            sa.ForeignKey("canonical_merge_proposals.id"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("change_type", sa.Text(), nullable=False),
        sa.Column("topic_id", sa.Text()),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("impact", sa.Text(), nullable=False),
        sa.Column("conflict_type", sa.Text()),
        sa.Column("selected", sa.Integer(), nullable=False),
        sa.Column("recommended_resolution", sa.Text(), nullable=False),
        sa.Column("chosen_resolution", sa.Text()),
        sa.Column("resolution_explanation", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "entity_type IN ('topic','relation','content')", name="entity_type_valid"
        ),
        sa.CheckConstraint(
            "change_type IN ('added','modified','deleted')", name="change_type_valid"
        ),
        sa.CheckConstraint("selected IN (0,1)", name="selected_valid"),
        sa.CheckConstraint(
            "recommended_resolution IN ('accept-canonical','overlay-wins','retain-local')",
            name="recommended_resolution_valid",
        ),
        sa.CheckConstraint(
            "chosen_resolution IS NULL OR chosen_resolution IN ('accept-canonical','overlay-wins','retain-local')",
            name="chosen_resolution_valid",
        ),
        sa.CheckConstraint("json_valid(payload_json)", name="payload_json_valid"),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"], ["goal_workspaces.id", "goal_workspaces.owner_id"]
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id", "owner_id", "goal_id"],
            [
                "canonical_merge_proposals.id",
                "canonical_merge_proposals.owner_id",
                "canonical_merge_proposals.goal_id",
            ],
        ),
        sa.UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_merge_items_id_owner_goal"
        ),
    )
    op.create_index("ix_merge_items_proposal", "merge_items", ["proposal_id", "id"])
    op.create_table(
        "canonical_merge_followups",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), sa.ForeignKey("owners.id"), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("proposal_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("job_id", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"], ["goal_workspaces.id", "goal_workspaces.owner_id"]
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id", "owner_id", "goal_id"],
            [
                "canonical_merge_proposals.id",
                "canonical_merge_proposals.owner_id",
                "canonical_merge_proposals.goal_id",
            ],
        ),
        sa.CheckConstraint(
            "kind IN ('reprocess_import','roadmap','generated_content','search')",
            name="kind_valid",
        ),
        sa.CheckConstraint(
            "status IN ('pending-dispatch','dispatched','completed-derived')",
            name="status_valid",
        ),
        sa.CheckConstraint("json_valid(payload_json)", name="payload_json_valid"),
        sa.UniqueConstraint(
            "proposal_id",
            "kind",
            "payload_hash",
            name="uq_canonical_merge_followups_intent",
        ),
        sa.UniqueConstraint(
            "id",
            "owner_id",
            "goal_id",
            name="uq_canonical_merge_followups_id_owner_goal",
        ),
    )


def downgrade() -> None:
    op.drop_table("canonical_merge_followups")
    op.drop_index("ix_merge_items_proposal", table_name="merge_items")
    op.drop_table("merge_items")
    op.drop_index(
        "uq_canonical_merge_proposals_active_target",
        table_name="canonical_merge_proposals",
    )
    op.drop_table("canonical_merge_proposals")
    op.execute("DROP TRIGGER IF EXISTS trg_overlay_entries_no_delete")
    op.execute("DROP TRIGGER IF EXISTS trg_overlay_entries_no_update")
    with op.batch_alter_table("overlay_entries") as batch:
        batch.drop_constraint("entry_type_valid", type_="check")
        batch.drop_constraint("source_valid", type_="check")
        batch.create_check_constraint(
            "entry_type_valid",
            "entry_type IN ('order_constraint','skip','depth','bridge','recommendation')",
        )
        batch.create_check_constraint(
            "source_valid",
            "source IN ('learner','diagnostic_confirmation','overlay_proposal')",
        )
    _create_overlay_triggers()


def _create_overlay_triggers() -> None:
    op.execute(
        "CREATE TRIGGER trg_overlay_entries_no_update BEFORE UPDATE ON overlay_entries BEGIN SELECT RAISE(ABORT, 'overlay_entries is append-only: UPDATE is not permitted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_overlay_entries_no_delete BEFORE DELETE ON overlay_entries BEGIN SELECT RAISE(ABORT, 'overlay_entries is append-only: DELETE is not permitted'); END"
    )
