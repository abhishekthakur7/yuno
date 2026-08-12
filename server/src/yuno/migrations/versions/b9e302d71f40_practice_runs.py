"""Practice runs, immutable turns, and terminal results.

Revision ID: b9e302d71f40
Revises: a8c301f52d10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b9e302d71f40"
down_revision: str | Sequence[str] | None = "a8c301f52d10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_runs",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("bundle_id", sa.Text(), nullable=False),
        sa.Column("bundle_item_id", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("hint_text", sa.Text()),
        sa.Column("rubric_id", sa.Text(), nullable=False),
        sa.Column("rubric_version", sa.Text(), nullable=False),
        sa.Column("requested_capability", sa.Text(), nullable=False),
        sa.Column("active_job_id", sa.Text()),
        sa.Column("active_answer_turn_id", sa.Text()),
        sa.Column("failure_reference", sa.Text()),
        sa.Column("retryable", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "mode = 'Practice'", name=op.f("ck_interview_runs_mode_valid")
        ),
        sa.CheckConstraint(
            "state IN ('ready','answering','follow-up','submitted','evaluating','feedback-ready','failed-recoverable')",
            name=op.f("ck_interview_runs_state_valid"),
        ),
        sa.CheckConstraint(
            "length(trim(question)) > 0",
            name=op.f("ck_interview_runs_question_non_blank"),
        ),
        sa.CheckConstraint(
            "hint_text IS NULL OR length(trim(hint_text)) > 0",
            name=op.f("ck_interview_runs_hint_non_blank"),
        ),
        sa.CheckConstraint(
            "retryable IN (0,1)", name=op.f("ck_interview_runs_retryable_valid")
        ),
        sa.CheckConstraint(
            "retryable IN (0,1)", name=op.f("ck_interview_runs_retryable_in_0_1")
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_interview_runs_goal_owner",
        ),
        sa.ForeignKeyConstraint(
            ["bundle_id", "owner_id"],
            ["interview_bundles.id", "interview_bundles.owner_id"],
            name="fk_interview_runs_bundle_owner",
        ),
        sa.ForeignKeyConstraint(
            ["bundle_item_id", "owner_id"],
            ["interview_bundle_items.id", "interview_bundle_items.owner_id"],
            name="fk_interview_runs_item_owner",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "owner_id", name="uq_interview_runs_id_owner"),
        sa.UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_interview_runs_id_owner_goal"
        ),
    )
    op.create_index(op.f("ix_interview_runs_owner_id"), "interview_runs", ["owner_id"])
    op.create_index(op.f("ix_interview_runs_goal_id"), "interview_runs", ["goal_id"])

    op.create_table(
        "interview_turns",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("turn_number", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("answer_turn_id", sa.Text()),
        sa.Column("evidence_id", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "turn_number >= 1", name=op.f("ck_interview_turns_turn_number_positive")
        ),
        sa.CheckConstraint(
            "kind IN ('question','answer','hint','follow-up')",
            name=op.f("ck_interview_turns_kind_valid"),
        ),
        sa.CheckConstraint(
            "length(trim(body)) > 0", name=op.f("ck_interview_turns_body_non_blank")
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.ForeignKeyConstraint(
            ["run_id", "owner_id"],
            ["interview_runs.id", "interview_runs.owner_id"],
            ondelete="CASCADE",
            name="fk_interview_turns_run_owner",
        ),
        sa.ForeignKeyConstraint(
            ["answer_turn_id", "owner_id"],
            ["interview_turns.id", "interview_turns.owner_id"],
            name="fk_interview_turns_answer_owner",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "owner_id", name="uq_interview_turns_id_owner"),
        sa.UniqueConstraint(
            "run_id", "turn_number", name="uq_interview_turns_run_number"
        ),
    )
    op.create_index(
        op.f("ix_interview_turns_owner_id"), "interview_turns", ["owner_id"]
    )
    op.create_index(op.f("ix_interview_turns_run_id"), "interview_turns", ["run_id"])

    op.create_table(
        "interview_turn_results",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("answer_turn_id", sa.Text(), nullable=False),
        sa.Column("assessment_id", sa.Text(), nullable=False),
        sa.Column("visible_at", sa.Text(), nullable=False),
        sa.Column("facts", sa.JSON(), nullable=False),
        sa.Column("trade_offs", sa.JSON(), nullable=False),
        sa.Column("dimensions", sa.JSON(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("cross_question_candidate", sa.Text()),
        sa.CheckConstraint(
            "json_valid(facts)", name=op.f("ck_interview_turn_results_facts_json_valid")
        ),
        sa.CheckConstraint(
            "json_valid(trade_offs)",
            name=op.f("ck_interview_turn_results_trade_offs_json_valid"),
        ),
        sa.CheckConstraint(
            "json_valid(dimensions)",
            name=op.f("ck_interview_turn_results_dimensions_json_valid"),
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.ForeignKeyConstraint(
            ["run_id", "owner_id"],
            ["interview_runs.id", "interview_runs.owner_id"],
            ondelete="CASCADE",
            name="fk_interview_turn_results_run_owner",
        ),
        sa.ForeignKeyConstraint(
            ["answer_turn_id", "owner_id"],
            ["interview_turns.id", "interview_turns.owner_id"],
            name="fk_interview_turn_results_answer_owner",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "owner_id", name="uq_interview_turn_results_id_owner"
        ),
        sa.UniqueConstraint("answer_turn_id", name="uq_interview_turn_results_answer"),
    )
    op.create_index(
        op.f("ix_interview_turn_results_owner_id"),
        "interview_turn_results",
        ["owner_id"],
    )
    op.create_index(
        op.f("ix_interview_turn_results_run_id"), "interview_turn_results", ["run_id"]
    )

    for table in ("interview_turns", "interview_turn_results"):
        op.execute(f"""
        CREATE TRIGGER trg_{table}_immutable_update
        BEFORE UPDATE ON {table}
        BEGIN SELECT RAISE(ABORT, '{table} are append-only'); END
        """)
        op.execute(f"""
        CREATE TRIGGER trg_{table}_immutable_delete
        BEFORE DELETE ON {table}
        BEGIN SELECT RAISE(ABORT, '{table} are append-only'); END
        """)
    op.execute("""
    CREATE TRIGGER trg_interview_turn_results_terminal_visibility
    BEFORE INSERT ON interview_turn_results
    BEGIN
      SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM interview_runs r JOIN interview_turns t
          ON t.id = NEW.answer_turn_id AND t.run_id = r.id AND t.owner_id = r.owner_id
        WHERE r.id = NEW.run_id AND r.owner_id = NEW.owner_id
          AND r.state = 'evaluating' AND t.kind = 'answer'
      ) THEN RAISE(ABORT, 'Practice result requires its submitted answer evaluation') END;
    END
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_interview_turn_results_terminal_visibility")
    for table in ("interview_turn_results", "interview_turns"):
        op.execute(f"DROP TRIGGER trg_{table}_immutable_delete")
        op.execute(f"DROP TRIGGER trg_{table}_immutable_update")
    op.drop_table("interview_turn_results")
    op.drop_table("interview_turns")
    op.drop_table("interview_runs")
