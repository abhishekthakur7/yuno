"""Mock interview lifecycle and exact persisted drafts.

Revision ID: 5d71a0c934be
Revises: b9e302d71f40
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5d71a0c934be"
down_revision: str | Sequence[str] | None = "b9e302d71f40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite requires a table rebuild to replace CHECK constraints. Alembic's
    # batch operation copies every existing Practice row before swapping tables.
    for trigger in (
        "trg_interview_turn_results_terminal_visibility",
        "trg_interview_turn_results_immutable_delete",
        "trg_interview_turn_results_immutable_update",
        "trg_interview_turns_immutable_delete",
        "trg_interview_turns_immutable_update",
    ):
        op.execute(f"DROP TRIGGER {trigger}")
    with op.batch_alter_table("interview_runs", recreate="always") as batch:
        batch.drop_constraint("mode_valid", type_="check")
        batch.drop_constraint("state_valid", type_="check")
        batch.alter_column("rubric_id", existing_type=sa.Text(), nullable=True)
        batch.alter_column("rubric_version", existing_type=sa.Text(), nullable=True)
        batch.add_column(sa.Column("draft", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("final_assessment_id", sa.Text()))
        batch.create_check_constraint(
            "mode_valid", "mode IN ('Practice','Mock')"
        )
        batch.create_check_constraint(
            "state_valid",
            "(mode = 'Practice' AND state IN ('ready','answering','follow-up',"
            "'submitted','evaluating','feedback-ready','failed-recoverable')) OR "
            "(mode = 'Mock' AND state IN ('ready','answering','follow-up','paused',"
            "'completing','completed','failed-recoverable'))",
        )
        batch.create_check_constraint(
            "mode_references_valid",
            "(mode = 'Practice' AND rubric_id IS NOT NULL AND rubric_version IS NOT NULL) OR "
            "(mode = 'Mock' AND ((rubric_id IS NULL AND rubric_version IS NULL) OR "
            "(rubric_id IS NOT NULL AND rubric_version IS NOT NULL)) AND hint_text IS NULL)",
        )
        batch.create_check_constraint(
            "mock_completed_assessment",
            "mode != 'Mock' OR state != 'completed' OR final_assessment_id IS NOT NULL",
        )
        batch.create_foreign_key(
            "final_assessment_owner_goal",
            "assessments",
            ["final_assessment_id", "owner_id", "goal_id"],
            ["id", "owner_id", "goal_id"],
        )

    _create_triggers()


def downgrade() -> None:
    for trigger in (
        "trg_interview_turn_results_terminal_visibility",
        "trg_interview_turn_results_mock_terminal_visibility",
        "trg_interview_turn_results_immutable_delete",
        "trg_interview_turn_results_immutable_update",
        "trg_interview_turns_mock_feedback_withheld",
        "trg_interview_turns_immutable_delete",
        "trg_interview_turns_immutable_update",
    ):
        op.execute(f"DROP TRIGGER {trigger}")
    with op.batch_alter_table("interview_runs", recreate="always") as batch:
        batch.drop_constraint(
            "final_assessment_owner_goal", type_="foreignkey"
        )
        batch.drop_constraint("mode_valid", type_="check")
        batch.drop_constraint("state_valid", type_="check")
        batch.drop_constraint("mode_references_valid", type_="check")
        batch.drop_constraint("mock_completed_assessment", type_="check")
        batch.drop_column("final_assessment_id")
        batch.drop_column("draft")
        batch.alter_column("rubric_version", existing_type=sa.Text(), nullable=False)
        batch.alter_column("rubric_id", existing_type=sa.Text(), nullable=False)
        batch.create_check_constraint("mode_valid", "mode = 'Practice'")
        batch.create_check_constraint(
            "state_valid",
            "state IN ('ready','answering','follow-up','submitted','evaluating',"
            "'feedback-ready','failed-recoverable')",
        )
    _create_practice_triggers()


def _create_triggers() -> None:
    _create_immutable_triggers()
    op.execute("""
    CREATE TRIGGER trg_interview_turns_mock_feedback_withheld
    BEFORE INSERT ON interview_turns
    WHEN NEW.kind = 'hint'
    BEGIN
      SELECT CASE WHEN EXISTS (
        SELECT 1 FROM interview_runs r WHERE r.id = NEW.run_id
          AND r.owner_id = NEW.owner_id AND r.mode = 'Mock'
          AND r.state != 'completed'
      ) THEN RAISE(ABORT, 'mock_feedback_withheld') END;
    END
    """)
    op.execute("""
    CREATE TRIGGER trg_interview_turn_results_mock_terminal_visibility
    BEFORE INSERT ON interview_turn_results
    BEGIN
      SELECT CASE WHEN EXISTS (
        SELECT 1 FROM interview_runs r WHERE r.id = NEW.run_id
          AND r.owner_id = NEW.owner_id AND r.mode = 'Mock'
          AND r.state != 'completed'
      ) THEN RAISE(ABORT, 'mock_feedback_withheld') END;
    END
    """)
    _create_practice_result_trigger()


def _create_practice_triggers() -> None:
    _create_immutable_triggers()
    _create_practice_result_trigger()


def _create_immutable_triggers() -> None:
    for table in ("interview_turns", "interview_turn_results"):
        op.execute(f"""
        CREATE TRIGGER trg_{table}_immutable_update BEFORE UPDATE ON {table}
        BEGIN SELECT RAISE(ABORT, '{table} are append-only'); END
        """)
        op.execute(f"""
        CREATE TRIGGER trg_{table}_immutable_delete BEFORE DELETE ON {table}
        BEGIN SELECT RAISE(ABORT, '{table} are append-only'); END
        """)


def _create_practice_result_trigger() -> None:
    op.execute("""
    CREATE TRIGGER trg_interview_turn_results_terminal_visibility
    BEFORE INSERT ON interview_turn_results
    BEGIN
      SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM interview_runs r JOIN interview_turns t
          ON t.id = NEW.answer_turn_id AND t.run_id = r.id AND t.owner_id = r.owner_id
        WHERE r.id = NEW.run_id AND r.owner_id = NEW.owner_id
          AND r.mode = 'Practice' AND r.state = 'evaluating' AND t.kind = 'answer'
      ) THEN RAISE(ABORT, 'Practice result requires its submitted answer evaluation') END;
    END
    """)
