"""settings accessibility and durable data lifecycle

Revision ID: a9d4e6f1b208
Revises: c8a4d0e9f217
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a9d4e6f1b208"
down_revision: str | Sequence[str] | None = "c8a4d0e9f217"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("owner_settings") as batch:
        batch.add_column(
            sa.Column(
                "accessibility_json",
                sa.Text(),
                server_default='{"reduced_motion":false}',
                nullable=False,
            )
        )
        batch.add_column(sa.Column("provider_selection", sa.Text()))
        batch.create_check_constraint(
            "accessibility_json_valid",
            "json_valid(accessibility_json) AND json_type(accessibility_json)='object'",
        )
        batch.create_check_constraint(
            "provider_selection_valid",
            "provider_selection IS NULL OR provider_selection IN ('codex','claude')",
        )
    op.create_table(
        "export_operations",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("format_version", sa.Text(), nullable=False),
        sa.Column("package_json", sa.Text()),
        sa.Column("job_id", sa.Text()),
        sa.Column("result_ref", sa.Text()),
        sa.Column("failure_reference", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"], ["goal_workspaces.id", "goal_workspaces.owner_id"]
        ),
        sa.UniqueConstraint("id", "owner_id", name="uq_export_operations_id_owner"),
        sa.CheckConstraint(
            "status IN ('queued','running','complete','failed')", name="status_valid"
        ),
        sa.CheckConstraint(
            "length(trim(format_version)) > 0", name="format_version_non_blank"
        ),
        sa.CheckConstraint(
            "package_json IS NULL OR json_valid(package_json)",
            name="package_json_valid",
        ),
    )
    op.create_table(
        "delete_operations",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("snapshot_id", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("impact_json", sa.Text(), nullable=False),
        sa.Column("impact_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("job_id", sa.Text()),
        sa.Column("result_ref", sa.Text()),
        sa.Column("confirmed_at", sa.Text()),
        sa.Column("failure_reference", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"], ["goal_workspaces.id", "goal_workspaces.owner_id"]
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "owner_id", "goal_id"],
            [
                "evidence_delete_snapshots.id",
                "evidence_delete_snapshots.owner_id",
                "evidence_delete_snapshots.goal_id",
            ],
            name="fk_delete_operations_snapshot_owner_goal",
        ),
        sa.UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_delete_operations_id_owner_goal"
        ),
        sa.CheckConstraint(
            "status IN ('preflight','queued','running','complete','failed')",
            name="status_valid",
        ),
        sa.CheckConstraint(
            "json_valid(impact_json) AND json_type(impact_json)='object'",
            name="impact_json_valid",
        ),
        sa.CheckConstraint("scope IN ('goal')", name="scope_valid"),
    )
    op.execute(
        "CREATE TRIGGER trg_delete_operations_impact_no_update BEFORE UPDATE OF owner_id, goal_id, snapshot_id, scope, impact_json, impact_hash ON delete_operations BEGIN SELECT RAISE(ABORT, 'delete impact snapshot is immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_delete_operations_impact_no_delete BEFORE DELETE ON delete_operations BEGIN SELECT RAISE(ABORT, 'delete impact snapshot is immutable'); END"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_delete_operations_impact_no_update")
    op.execute("DROP TRIGGER trg_delete_operations_impact_no_delete")
    op.drop_table("delete_operations")
    op.drop_table("export_operations")
    with op.batch_alter_table("owner_settings") as batch:
        batch.drop_constraint("provider_selection_valid", type_="check")
        batch.drop_constraint("accessibility_json_valid", type_="check")
        batch.drop_column("provider_selection")
        batch.drop_column("accessibility_json")
