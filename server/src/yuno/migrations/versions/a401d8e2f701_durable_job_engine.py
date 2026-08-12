"""Durable two-lane job engine.

Revision ID: a401d8e2f701
Revises: 5d71a0c934be
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a401d8e2f701"
down_revision: str | Sequence[str] | None = "5d71a0c934be"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), sa.ForeignKey("owners.id"), nullable=False),
        sa.Column("goal_id", sa.Text()),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("lane", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("retryable", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dedupe_key", sa.Text()),
        sa.Column("idempotency_key", sa.Text()),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_hash", sa.Text(), nullable=False),
        sa.Column("request_ref", sa.Text()),
        sa.Column("disclosure_ref", sa.Text()),
        sa.Column("confirmation_ref", sa.Text()),
        sa.Column("correlation_id", sa.Text(), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text()),
        sa.Column("substitution_ref", sa.Text()),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("diagnostic", sa.Text()),
        sa.Column("result_ref", sa.Text()),
        sa.Column("result_hash", sa.Text()),
        sa.Column("worker_id", sa.Text()),
        sa.Column("queued_at", sa.Text(), nullable=False),
        sa.Column("started_at", sa.Text()),
        sa.Column("terminal_at", sa.Text()),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.CheckConstraint("length(trim(kind)) > 0", name="kind_valid"),
        sa.CheckConstraint("lane IN ('interactive','background')", name="lane_valid"),
        sa.CheckConstraint(
            "state IN ('queued','running','succeeded','failed','cancel-requested','cancelled')",
            name="state_valid",
        ),
        sa.CheckConstraint("retryable IN (0,1)", name="retryable_valid"),
        sa.CheckConstraint("retryable IN (0,1)", name="retryable_in_0_1"),
        sa.CheckConstraint("attempt >= 0", name="attempt_nonnegative"),
        sa.CheckConstraint("priority >= 0", name="priority_nonnegative"),
        sa.CheckConstraint("json_valid(payload_json)", name="payload_json_valid"),
        sa.UniqueConstraint("id", "owner_id", name="uq_jobs_id_owner"),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_jobs_goal_owner",
        ),
    )
    op.create_index("ix_jobs_owner_id", "jobs", ["owner_id"])
    op.create_index(
        "ix_jobs_lane_state_queue", "jobs", ["lane", "state", "priority", "queued_at"]
    )
    op.create_index(
        "uq_jobs_active_dedupe",
        "jobs",
        ["owner_id", "kind", "dedupe_key"],
        unique=True,
        sqlite_where=sa.text(
            "dedupe_key IS NOT NULL AND state IN ('queued','running','cancel-requested')"
        ),
    )
    op.create_table(
        "job_attempts",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), sa.ForeignKey("owners.id"), nullable=False),
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("process_identity", sa.Text()),
        sa.Column("pid", sa.Integer()),
        sa.Column("pgid", sa.Integer()),
        sa.Column("temp_path", sa.Text()),
        sa.Column("substitution_ref", sa.Text()),
        sa.Column("confirmation_ref", sa.Text()),
        sa.Column("started_at", sa.Text(), nullable=False),
        sa.Column("ended_at", sa.Text()),
        sa.Column("outcome", sa.Text()),
        sa.Column("diagnostic", sa.Text()),
        sa.CheckConstraint("attempt_number >= 1", name="attempt_number_positive"),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('succeeded','failed','cancelled')",
            name="outcome_valid",
        ),
        sa.UniqueConstraint("id", "owner_id", name="uq_job_attempts_id_owner"),
        sa.UniqueConstraint(
            "job_id", "attempt_number", name="uq_job_attempts_job_attempt"
        ),
        sa.ForeignKeyConstraint(
            ["job_id", "owner_id"],
            ["jobs.id", "jobs.owner_id"],
            ondelete="CASCADE",
            name="fk_job_attempts_job_owner",
        ),
    )
    op.create_index("ix_job_attempts_owner_id", "job_attempts", ["owner_id"])
    op.create_index("ix_job_attempts_job_id", "job_attempts", ["job_id"])
    op.create_table(
        "job_events",
        sa.Column("sequence", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "event_id",
            sa.Text(),
            sa.Computed("printf('%020d', sequence)", persisted=True),
            nullable=False,
        ),
        sa.Column("owner_id", sa.Text(), sa.ForeignKey("owners.id"), nullable=False),
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text()),
        sa.Column("run_id", sa.Text()),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("progress", sa.Text()),
        sa.Column("result_ref", sa.Text()),
        sa.Column("retryable", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("correlation_id", sa.Text(), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint("length(trim(type)) > 0", name="type_valid"),
        sa.CheckConstraint(
            "state IN ('queued','running','succeeded','failed','cancel-requested','cancelled')",
            name="state_valid",
        ),
        sa.CheckConstraint("retryable IN (0,1)", name="retryable_valid"),
        sa.CheckConstraint("retryable IN (0,1)", name="retryable_in_0_1"),
        sa.ForeignKeyConstraint(
            ["job_id", "owner_id"],
            ["jobs.id", "jobs.owner_id"],
            ondelete="CASCADE",
            name="fk_job_events_job_owner",
        ),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_job_events_goal_owner",
        ),
    )
    op.create_index("ix_job_events_owner_id", "job_events", ["owner_id"])
    op.create_index("ix_job_events_job_id", "job_events", ["job_id"])
    op.create_index("ix_job_events_owner_event", "job_events", ["owner_id", "event_id"])
    op.create_index("ix_job_events_job_event", "job_events", ["job_id", "event_id"])
    op.create_table(
        "job_results",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), sa.ForeignKey("owners.id"), nullable=False),
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("result_ref", sa.Text(), nullable=False),
        sa.Column("result_hash", sa.Text(), nullable=False),
        sa.Column("warnings_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("diagnostic_ref", sa.Text()),
        sa.Column("committed_at", sa.Text(), nullable=False),
        sa.CheckConstraint("length(trim(kind)) > 0", name="kind_valid"),
        sa.CheckConstraint("json_valid(warnings_json)", name="warnings_json_valid"),
        sa.UniqueConstraint("id", "owner_id", name="uq_job_results_id_owner"),
        sa.UniqueConstraint("job_id", name="uq_job_results_job"),
        sa.ForeignKeyConstraint(
            ["job_id", "owner_id"],
            ["jobs.id", "jobs.owner_id"],
            ondelete="CASCADE",
            name="fk_job_results_job_owner",
        ),
    )
    op.create_index("ix_job_results_owner_id", "job_results", ["owner_id"])
    op.create_index("ix_job_results_job_id", "job_results", ["job_id"])
    op.execute(
        """CREATE TRIGGER trg_job_attempts_immutable_delete BEFORE DELETE ON job_attempts BEGIN SELECT RAISE(ABORT, 'job_attempts are immutable'); END"""
    )
    op.execute(
        """CREATE TRIGGER trg_job_attempts_final_immutable BEFORE UPDATE ON job_attempts WHEN OLD.ended_at IS NOT NULL OR NEW.id != OLD.id OR NEW.owner_id != OLD.owner_id OR NEW.started_at != OLD.started_at OR NEW.job_id != OLD.job_id OR NEW.attempt_number != OLD.attempt_number BEGIN SELECT RAISE(ABORT, 'completed job_attempts are immutable'); END"""
    )
    for table in ("job_events", "job_results"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_immutable_update BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, '{table} are append-only'); END"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_immutable_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, '{table} are append-only'); END"
        )


def downgrade() -> None:
    for trigger in (
        "trg_job_attempts_immutable_delete",
        "trg_job_attempts_final_immutable",
        "trg_job_events_immutable_update",
        "trg_job_events_immutable_delete",
        "trg_job_results_immutable_update",
        "trg_job_results_immutable_delete",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    op.drop_table("job_results")
    op.drop_table("job_events")
    op.drop_table("job_attempts")
    op.drop_table("jobs")
