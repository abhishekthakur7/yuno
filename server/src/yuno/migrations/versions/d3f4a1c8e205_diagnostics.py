"""persisted diagnostic sessions and append-only answers

Revision ID: d3f4a1c8e205
Revises: b5d8d9a6104a
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d3f4a1c8e205"
down_revision: str | Sequence[str] | None = "b5d8d9a6104a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ANSWER_NO_UPDATE = "trg_diagnostic_answers_no_update"
_ANSWER_NO_DELETE = "trg_diagnostic_answers_no_delete"
_ANSWER_NO_INSERT_REPLACE = "trg_diagnostic_answers_no_insert_replace"


def upgrade() -> None:
    op.create_table(
        "diagnostic_sessions",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("captured_graph_version_id", sa.Text(), nullable=False),
        sa.Column("question_set_version", sa.Text(), nullable=False),
        sa.Column("setup_inputs_json", sa.Text(), nullable=False),
        sa.Column("untrusted_seed_kind", sa.Text(), nullable=True),
        sa.Column("untrusted_seed_text", sa.Text(), nullable=True),
        sa.Column(
            "seed_skipped", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "diagnostic_skipped",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("started_at", sa.Text(), nullable=True),
        sa.Column("paused_at", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.Text(), nullable=True),
        sa.Column("failure_code", sa.Text(), nullable=True),
        sa.Column("failure_reference", sa.Text(), nullable=True),
        sa.Column("confirmed_goal_id", sa.Text(), nullable=True),
        sa.Column(
            "row_version", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "state IN ('not-started','in-progress','paused','resumed','skipped','roadmap-preview','failed','confirmed')",
            name=op.f("ck_diagnostic_sessions_state_valid"),
        ),
        sa.CheckConstraint(
            "untrusted_seed_kind IS NULL OR untrusted_seed_kind IN ('notes','questions')",
            name=op.f("ck_diagnostic_sessions_untrusted_seed_kind_valid"),
        ),
        sa.CheckConstraint(
            "(untrusted_seed_kind IS NULL) = (untrusted_seed_text IS NULL)",
            name=op.f(
                "ck_diagnostic_sessions_untrusted_seed_kind_and_text_together"
            ),
        ),
        sa.CheckConstraint(
            "json_valid(setup_inputs_json)",
            name=op.f("ck_diagnostic_sessions_setup_inputs_json_valid"),
        ),
        sa.CheckConstraint(
            "json_type(setup_inputs_json) = 'object'",
            name=op.f("ck_diagnostic_sessions_setup_inputs_json_object"),
        ),
        sa.CheckConstraint(
            "length(trim(question_set_version)) > 0",
            name=op.f("ck_diagnostic_sessions_question_set_version_non_blank"),
        ),
        sa.CheckConstraint(
            "seed_skipped IN (0,1)",
            name=op.f("ck_diagnostic_sessions_seed_skipped_in_0_1"),
        ),
        sa.CheckConstraint(
            "diagnostic_skipped IN (0,1)",
            name=op.f("ck_diagnostic_sessions_diagnostic_skipped_in_0_1"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["owners.id"], name=op.f("fk_diagnostic_sessions_owner_id_owners")
        ),
        sa.ForeignKeyConstraint(
            ["captured_graph_version_id"],
            ["editorial_approvals.graph_version_id"],
            name=op.f(
                "fk_diagnostic_sessions_captured_graph_version_id_editorial_approvals"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_diagnostic_sessions_confirmed_goal_owner",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_diagnostic_sessions")),
        sa.UniqueConstraint(
            "id", "owner_id", name="uq_diagnostic_sessions_id_owner"
        ),
    )
    op.create_index(
        "ix_diagnostic_sessions_owner_state_recent",
        "diagnostic_sessions",
        ["owner_id", "state", "updated_at"],
        unique=False,
    )

    op.create_table(
        "diagnostic_answers",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("question_ref", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Text(), nullable=False),
        sa.Column("adaptive_context_version", sa.Text(), nullable=False),
        sa.Column("answered_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "sequence >= 1", name=op.f("ck_diagnostic_answers_sequence_positive")
        ),
        sa.CheckConstraint(
            "confidence IN ('low','medium','high')",
            name=op.f("ck_diagnostic_answers_confidence_valid"),
        ),
        sa.CheckConstraint(
            "length(trim(question_ref)) > 0",
            name=op.f("ck_diagnostic_answers_question_ref_non_blank"),
        ),
        sa.CheckConstraint(
            "length(trim(adaptive_context_version)) > 0",
            name=op.f("ck_diagnostic_answers_adaptive_context_version_non_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["owners.id"], name=op.f("fk_diagnostic_answers_owner_id_owners")
        ),
        sa.ForeignKeyConstraint(
            ["session_id", "owner_id"],
            ["diagnostic_sessions.id", "diagnostic_sessions.owner_id"],
            name="fk_diagnostic_answers_session_owner",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_diagnostic_answers")),
        sa.UniqueConstraint("id", "owner_id", name="uq_diagnostic_answers_id_owner"),
        sa.UniqueConstraint(
            "session_id", "sequence", name="uq_diagnostic_answers_session_sequence"
        ),
    )
    op.create_index(
        "ix_diagnostic_answers_owner_session_sequence",
        "diagnostic_answers",
        ["owner_id", "session_id", "sequence"],
        unique=False,
    )
    op.execute(
        f"CREATE TRIGGER {_ANSWER_NO_UPDATE} BEFORE UPDATE ON diagnostic_answers "
        "BEGIN SELECT RAISE(ABORT, 'diagnostic_answers is append-only: UPDATE is not permitted'); END"
    )
    op.execute(
        f"CREATE TRIGGER {_ANSWER_NO_DELETE} BEFORE DELETE ON diagnostic_answers "
        "BEGIN SELECT RAISE(ABORT, 'diagnostic_answers is append-only: DELETE is not permitted'); END"
    )
    op.execute(
        f"CREATE TRIGGER {_ANSWER_NO_INSERT_REPLACE} BEFORE INSERT ON diagnostic_answers "
        "WHEN EXISTS (SELECT 1 FROM diagnostic_answers WHERE id = NEW.id) "
        "BEGIN SELECT RAISE(ABORT, 'diagnostic_answers is append-only: INSERT that overwrites an existing id is not permitted'); END"
    )

    op.create_table(
        "diagnostics_command_locks",
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_diagnostics_command_locks_owner_id_owners"),
        ),
        sa.PrimaryKeyConstraint(
            "owner_id", name=op.f("pk_diagnostics_command_locks")
        ),
    )

    op.create_table(
        "diagnostics_idempotency",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "length(trim(operation)) > 0",
            name=op.f("ck_diagnostics_idempotency_operation_non_blank"),
        ),
        sa.CheckConstraint(
            "length(trim(idempotency_key)) > 0",
            name=op.f("ck_diagnostics_idempotency_idempotency_key_non_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["owners.id"], name=op.f("fk_diagnostics_idempotency_owner_id_owners")
        ),
        sa.ForeignKeyConstraint(
            ["session_id", "owner_id"],
            ["diagnostic_sessions.id", "diagnostic_sessions.owner_id"],
            name="fk_diagnostics_idempotency_session_owner",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_diagnostics_idempotency")),
        sa.UniqueConstraint(
            "id", "owner_id", name="uq_diagnostics_idempotency_id_owner"
        ),
        sa.UniqueConstraint(
            "owner_id",
            "operation",
            "idempotency_key",
            name="uq_diagnostics_idempotency_command",
        ),
    )


def downgrade() -> None:
    op.drop_table("diagnostics_idempotency")
    op.drop_table("diagnostics_command_locks")
    op.execute(f"DROP TRIGGER IF EXISTS {_ANSWER_NO_INSERT_REPLACE}")
    op.execute(f"DROP TRIGGER IF EXISTS {_ANSWER_NO_DELETE}")
    op.execute(f"DROP TRIGGER IF EXISTS {_ANSWER_NO_UPDATE}")
    op.drop_index(
        "ix_diagnostic_answers_owner_session_sequence",
        table_name="diagnostic_answers",
    )
    op.drop_table("diagnostic_answers")
    op.drop_index(
        "ix_diagnostic_sessions_owner_state_recent",
        table_name="diagnostic_sessions",
    )
    op.drop_table("diagnostic_sessions")
