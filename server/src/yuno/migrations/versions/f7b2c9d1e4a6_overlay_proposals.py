"""explicit overlay and bridge proposals

Revision ID: f7b2c9d1e4a6
Revises: a61e3f9c2b47
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7b2c9d1e4a6"
down_revision: str | Sequence[str] | None = "a61e3f9c2b47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_overlay_entries_no_delete")
    op.execute("DROP TRIGGER IF EXISTS trg_overlay_entries_no_update")
    with op.batch_alter_table("overlay_entries") as batch_op:
        batch_op.drop_constraint("entry_type_valid", type_="check")
        batch_op.drop_constraint("source_valid", type_="check")
        batch_op.create_check_constraint(
            "entry_type_valid",
            "entry_type IN ('order_constraint','skip','depth','bridge','recommendation')",
        )
        batch_op.create_check_constraint(
            "source_valid",
            "source IN ('learner','diagnostic_confirmation','overlay_proposal')",
        )
    op.execute(
        "CREATE TRIGGER trg_overlay_entries_no_update BEFORE UPDATE ON overlay_entries "
        "BEGIN SELECT RAISE(ABORT, 'overlay_entries is append-only: UPDATE is not permitted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_overlay_entries_no_delete BEFORE DELETE ON overlay_entries "
        "BEGIN SELECT RAISE(ABORT, 'overlay_entries is append-only: DELETE is not permitted'); END"
    )

    op.create_table(
        "overlay_proposals",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("generated_against_graph_version_id", sa.Text(), nullable=False),
        sa.Column("topic_stable_id", sa.Text(), nullable=True),
        sa.Column("proposal_type", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("state_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("decided_at", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "proposal_type IN ('recommendation','emphasis','example','exercise','ordering','bridge')",
            name=op.f("ck_overlay_proposals_proposal_type_valid"),
        ),
        sa.CheckConstraint(
            "state IN ('awaiting-learner-decision','accepted','postponed','dismissed','rejected-stale')",
            name=op.f("ck_overlay_proposals_state_valid"),
        ),
        sa.CheckConstraint(
            "json_valid(payload_json)",
            name=op.f("ck_overlay_proposals_payload_json_valid"),
        ),
        sa.CheckConstraint(
            "json_type(payload_json) = 'object'",
            name=op.f("ck_overlay_proposals_payload_json_object"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_overlay_proposals_owner_id_owners"),
        ),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_overlay_proposals_goal_owner",
        ),
        sa.ForeignKeyConstraint(
            ["generated_against_graph_version_id"],
            ["editorial_approvals.graph_version_id"],
            name=op.f(
                "fk_overlay_proposals_generated_against_graph_version_id_editorial_approvals"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_overlay_proposals")),
        sa.UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_overlay_proposals_id_owner_goal"
        ),
    )
    op.create_index(
        "ix_overlay_proposals_owner_goal_state_created",
        "overlay_proposals",
        ["owner_id", "goal_id", "state", "created_at"],
        unique=False,
    )
    op.create_index(
        "uq_overlay_proposals_pending_goal_hash",
        "overlay_proposals",
        ["goal_id", "content_hash"],
        unique=True,
        sqlite_where=sa.text("state = 'awaiting-learner-decision'"),
    )

    op.create_table(
        "overlay_proposal_decisions",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("proposal_id", sa.Text(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "decision IN ('accept','add','postpone','dismiss')",
            name=op.f("ck_overlay_proposal_decisions_decision_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_overlay_proposal_decisions_owner_id_owners"),
        ),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_overlay_proposal_decisions_goal_owner",
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id", "owner_id", "goal_id"],
            [
                "overlay_proposals.id",
                "overlay_proposals.owner_id",
                "overlay_proposals.goal_id",
            ],
            name="fk_overlay_proposal_decisions_proposal_owner_goal",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_overlay_proposal_decisions")),
        sa.UniqueConstraint(
            "id",
            "owner_id",
            "goal_id",
            name="uq_overlay_proposal_decisions_id_owner_goal",
        ),
    )
    op.create_index(
        "ix_overlay_proposal_decisions_owner_proposal_decided",
        "overlay_proposal_decisions",
        ["owner_id", "proposal_id", "decided_at"],
        unique=False,
    )
    op.execute(
        "CREATE TRIGGER trg_overlay_proposal_decisions_no_update BEFORE UPDATE ON "
        "overlay_proposal_decisions BEGIN SELECT RAISE(ABORT, "
        "'overlay_proposal_decisions is append-only: UPDATE is not permitted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_overlay_proposal_decisions_no_delete BEFORE DELETE ON "
        "overlay_proposal_decisions BEGIN SELECT RAISE(ABORT, "
        "'overlay_proposal_decisions is append-only: DELETE is not permitted'); END"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_overlay_proposal_decisions_no_delete")
    op.execute("DROP TRIGGER IF EXISTS trg_overlay_proposal_decisions_no_update")
    op.drop_index(
        "ix_overlay_proposal_decisions_owner_proposal_decided",
        table_name="overlay_proposal_decisions",
    )
    op.drop_table("overlay_proposal_decisions")
    op.drop_index(
        "uq_overlay_proposals_pending_goal_hash", table_name="overlay_proposals"
    )
    op.drop_index(
        "ix_overlay_proposals_owner_goal_state_created", table_name="overlay_proposals"
    )
    op.drop_table("overlay_proposals")

    op.execute("DROP TRIGGER IF EXISTS trg_overlay_entries_no_delete")
    op.execute("DROP TRIGGER IF EXISTS trg_overlay_entries_no_update")
    with op.batch_alter_table("overlay_entries") as batch_op:
        batch_op.drop_constraint("entry_type_valid", type_="check")
        batch_op.drop_constraint("source_valid", type_="check")
        batch_op.create_check_constraint(
            "entry_type_valid", "entry_type IN ('order_constraint','skip','depth')"
        )
        batch_op.create_check_constraint(
            "source_valid", "source IN ('learner','diagnostic_confirmation')"
        )
    op.execute(
        "CREATE TRIGGER trg_overlay_entries_no_update BEFORE UPDATE ON overlay_entries "
        "BEGIN SELECT RAISE(ABORT, 'overlay_entries is append-only: UPDATE is not permitted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_overlay_entries_no_delete BEFORE DELETE ON overlay_entries "
        "BEGIN SELECT RAISE(ABORT, 'overlay_entries is append-only: DELETE is not permitted'); END"
    )
