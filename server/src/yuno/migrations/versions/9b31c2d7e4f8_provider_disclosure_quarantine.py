"""Provider disclosure and canonical schema quarantine.

Revision ID: 9b31c2d7e4f8
Revises: a401d8e2f701
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9b31c2d7e4f8"
down_revision: str | Sequence[str] | None = "a401d8e2f701"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "network_disclosures",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), sa.ForeignKey("owners.id"), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("destination", sa.Text(), nullable=False),
        sa.Column("data_categories_json", sa.Text(), nullable=False),
        sa.Column("disclosure_version", sa.Text(), nullable=False),
        sa.Column("accepted_at", sa.Text(), nullable=False),
        sa.Column("revoked_at", sa.Text()),
        sa.CheckConstraint("length(trim(category)) > 0", name="category_valid"),
        sa.CheckConstraint(
            "json_valid(data_categories_json)", name="data_categories_json_valid"
        ),
        sa.UniqueConstraint(
            "owner_id",
            "category",
            "disclosure_version",
            name="uq_network_disclosure_version",
        ),
        sa.UniqueConstraint("id", "owner_id", name="uq_network_disclosures_id_owner"),
    )
    op.create_index(
        "ix_network_disclosures_owner_id", "network_disclosures", ["owner_id"]
    )
    op.create_table(
        "provider_requests",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), sa.ForeignKey("owners.id"), nullable=False),
        sa.Column("goal_id", sa.Text()),
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("adapter_version", sa.Text(), nullable=False),
        sa.Column("contract_version", sa.Text(), nullable=False),
        sa.Column("context_ref_hash", sa.Text(), nullable=False),
        sa.Column("disclosure_id", sa.Text(), nullable=False),
        sa.Column("pid", sa.Integer()),
        sa.Column("pgid", sa.Integer()),
        sa.Column("process_identity", sa.Text()),
        sa.Column("temp_path", sa.Text()),
        sa.Column("lifecycle", sa.Text(), nullable=False),
        sa.Column("diagnostic_classification", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("started_at", sa.Text()),
        sa.Column("completed_at", sa.Text()),
        sa.CheckConstraint("provider IN ('codex','claude')", name="provider_valid"),
        sa.CheckConstraint(
            "lifecycle IN ('preparing','running','succeeded','failed','quarantined','cancelled')",
            name="lifecycle_valid",
        ),
        sa.UniqueConstraint("id", "owner_id", name="uq_provider_requests_id_owner"),
        sa.ForeignKeyConstraint(
            ["job_id", "owner_id"],
            ["jobs.id", "jobs.owner_id"],
            name="fk_provider_requests_job_owner",
        ),
        sa.ForeignKeyConstraint(
            ["disclosure_id", "owner_id"],
            ["network_disclosures.id", "network_disclosures.owner_id"],
            name="fk_provider_requests_disclosure_owner",
        ),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_provider_requests_goal_owner",
        ),
    )
    op.create_index("ix_provider_requests_owner_id", "provider_requests", ["owner_id"])
    op.create_index("ix_provider_requests_job_id", "provider_requests", ["job_id"])
    op.drop_table("schema_quarantines")
    op.create_table(
        "schema_quarantines",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), sa.ForeignKey("owners.id"), nullable=False),
        sa.Column("provider_request_id", sa.Text(), nullable=False),
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("raw_output_ref", sa.Text(), nullable=False),
        sa.Column("raw_output_hash", sa.Text(), nullable=False),
        sa.Column("expected_schema_version", sa.Text(), nullable=False),
        sa.Column("validation_errors_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "json_valid(validation_errors_json)", name="validation_errors_json_valid"
        ),
        sa.UniqueConstraint("id", "owner_id", name="uq_schema_quarantines_id_owner"),
        sa.ForeignKeyConstraint(
            ["provider_request_id", "owner_id"],
            ["provider_requests.id", "provider_requests.owner_id"],
            name="fk_schema_quarantine_request_owner",
        ),
        sa.ForeignKeyConstraint(
            ["job_id", "owner_id"],
            ["jobs.id", "jobs.owner_id"],
            name="fk_schema_quarantine_job_owner",
        ),
    )
    op.create_index(
        "ix_schema_quarantines_owner_id", "schema_quarantines", ["owner_id"]
    )
    op.create_index(
        "ix_schema_quarantines_provider_request_id",
        "schema_quarantines",
        ["provider_request_id"],
    )
    for table in ("provider_requests", "schema_quarantines"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_immutable_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, '{table} are append-only'); END"
        )
    op.execute(
        "CREATE TRIGGER trg_schema_quarantines_immutable_update BEFORE UPDATE ON schema_quarantines BEGIN SELECT RAISE(ABORT, 'schema_quarantines are append-only'); END"
    )


def downgrade() -> None:
    for trigger in (
        "trg_schema_quarantines_immutable_update",
        "trg_schema_quarantines_immutable_delete",
        "trg_provider_requests_immutable_delete",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    op.drop_table("schema_quarantines")
    op.drop_table("provider_requests")
    op.drop_table("network_disclosures")
    op.create_table(
        "schema_quarantines",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), sa.ForeignKey("owners.id"), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("attempt_id", sa.Text(), nullable=False),
        sa.Column("raw_output_hash", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("validation_errors_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id", "owner_id", "goal_id"],
            [
                "artifact_generation_attempts.id",
                "artifact_generation_attempts.owner_id",
                "artifact_generation_attempts.goal_id",
            ],
            name="fk_schema_quarantines_attempt_owner_goal",
        ),
        sa.UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_schema_quarantines_id_owner_goal"
        ),
        sa.UniqueConstraint("attempt_id", name="uq_schema_quarantines_attempt"),
        sa.CheckConstraint(
            "json_valid(validation_errors_json)", name="validation_errors_json_valid"
        ),
    )
