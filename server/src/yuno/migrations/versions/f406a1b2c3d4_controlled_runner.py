"""controlled runner

Revision ID: f406a1b2c3d4
Revises: e7a405b1c2d3
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f406a1b2c3d4"
down_revision: str | Sequence[str] | None = "e7a405b1c2d3"
branch_labels = None
depends_on = None


def owned_id(name: str):
    return [
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.UniqueConstraint("id", "owner_id", name=f"uq_{name}_id_owner"),
    ]


def upgrade() -> None:
    op.create_table(
        "runner_confirmations",
        *owned_id("runner_confirmations"),
        sa.Column("goal_id", sa.Text()),
        sa.Column("artifact_id", sa.Text()),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("capability", sa.Text(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("inputs_hash", sa.Text(), nullable=False),
        sa.Column("acknowledgement_version", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text()),
        sa.Column("request_hash", sa.Text()),
        sa.Column("reserved_run_id", sa.Text()),
        sa.Column("environment_policy_version", sa.Text(), nullable=False),
        sa.Column("limits_config_version", sa.Text(), nullable=False),
        sa.Column("confirmed_at", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.Text(), nullable=False),
        sa.Column("consumed_at", sa.Text()),
        sa.CheckConstraint(
            "language IN ('java','python','relational')", name="language_valid"
        ),
        sa.CheckConstraint("operation IN ('compile','test')", name="operation_valid"),
        sa.UniqueConstraint(
            "owner_id",
            "idempotency_key",
            name="uq_runner_confirmations_owner_idempotency",
        ),
    )
    op.create_table(
        "runner_confirmation_inputs",
        *owned_id("runner_confirmation_inputs"),
        sa.Column("confirmation_id", sa.Text(), nullable=False),
        sa.Column("logical_path", sa.Text(), nullable=False),
        sa.Column("declared_type", sa.Text(), nullable=False),
        sa.Column("content_ref", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("resolved_content", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["confirmation_id", "owner_id"],
            ["runner_confirmations.id", "runner_confirmations.owner_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "confirmation_id",
            "logical_path",
            name="uq_runner_confirmation_inputs_confirmation_path",
        ),
    )
    op.create_table(
        "runner_records",
        *owned_id("runner_records"),
        sa.Column("goal_id", sa.Text()),
        sa.Column("artifact_id", sa.Text()),
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("confirmation_id", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("capability", sa.Text(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("toolchain", sa.Text(), nullable=False),
        sa.Column("argv_json", sa.Text(), nullable=False),
        sa.Column("working_directory_policy", sa.Text(), nullable=False),
        sa.Column("environment_policy_version", sa.Text(), nullable=False),
        sa.Column("limits_config_version", sa.Text(), nullable=False),
        sa.Column("pid", sa.Integer()),
        sa.Column("pgid", sa.Integer()),
        sa.Column("temp_path", sa.Text()),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("outcome_json", sa.Text()),
        sa.Column("cleanup_state", sa.Text(), nullable=False),
        sa.Column("cleanup_diagnostic", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.UniqueConstraint("job_id", name="uq_runner_records_job"),
        sa.CheckConstraint(
            "language IN ('java','python','relational')", name="language_valid"
        ),
        sa.CheckConstraint("operation IN ('compile','test')", name="operation_valid"),
        sa.CheckConstraint(
            "state IN ('queued','preparing','running','completed','failed','timed-out-or-limited','cancel-requested','cancelled')",
            name="state_valid",
        ),
        sa.CheckConstraint(
            "cleanup_state IN ('cleanup-pending','cleanup-complete','cleanup-failed')",
            name="cleanup_state_valid",
        ),
    )
    op.create_table(
        "runner_inputs",
        *owned_id("runner_inputs"),
        sa.Column("runner_id", sa.Text(), nullable=False),
        sa.Column("logical_path", sa.Text(), nullable=False),
        sa.Column("declared_type", sa.Text(), nullable=False),
        sa.Column("content_ref", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["runner_id", "owner_id"],
            ["runner_records.id", "runner_records.owner_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "runner_id", "logical_path", name="uq_runner_inputs_runner_path"
        ),
    )
    op.create_table(
        "runner_output_chunks",
        *owned_id("runner_output_chunks"),
        sa.Column("runner_id", sa.Text(), nullable=False),
        sa.Column("phase", sa.Text(), nullable=False),
        sa.Column("stream", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("content_ref", sa.Text(), nullable=False),
        sa.Column("truncated", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["runner_id", "owner_id"],
            ["runner_records.id", "runner_records.owner_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "runner_id",
            "stream",
            "sequence",
            name="uq_runner_output_chunks_runner_stream_sequence",
        ),
        sa.UniqueConstraint(
            "runner_id", "ordinal", name="uq_runner_output_chunks_runner_ordinal"
        ),
        sa.CheckConstraint("phase IN ('compile','test','static')", name="phase_valid"),
        sa.CheckConstraint("stream IN ('stdout','stderr')", name="stream_valid"),
        sa.CheckConstraint("truncated IN (0,1)", name="truncated_valid"),
    )


def downgrade() -> None:
    for table in (
        "runner_output_chunks",
        "runner_inputs",
        "runner_records",
        "runner_confirmation_inputs",
        "runner_confirmations",
    ):
        op.drop_table(table)
