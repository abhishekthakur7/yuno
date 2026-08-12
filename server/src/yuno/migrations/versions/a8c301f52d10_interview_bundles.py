"""interview preparation bundles

Revision ID: a8c301f52d10
Revises: d208f9a4c6e1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8c301f52d10"
down_revision: str | Sequence[str] | None = "d208f9a4c6e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_bundles",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text()),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("generic_role", sa.Text(), nullable=False),
        sa.Column("target_level", sa.Text(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("copy_source_id", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "status IN ('active','archived')",
            name=op.f("ck_interview_bundles_status_valid"),
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0", name=op.f("ck_interview_bundles_name_non_blank")
        ),
        sa.CheckConstraint(
            "length(trim(generic_role)) > 0",
            name=op.f("ck_interview_bundles_generic_role_non_blank"),
        ),
        sa.CheckConstraint(
            "target_level IN ('Mid-level','Senior','Staff')",
            name=op.f("ck_interview_bundles_target_level_valid"),
        ),
        sa.CheckConstraint(
            "length(trim(origin)) > 0",
            name=op.f("ck_interview_bundles_origin_non_blank"),
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_interview_bundles_goal_owner",
        ),
        sa.ForeignKeyConstraint(
            ["copy_source_id", "owner_id"],
            ["interview_bundles.id", "interview_bundles.owner_id"],
            name="fk_interview_bundles_copy_source_owner",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "owner_id", name="uq_interview_bundles_id_owner"),
    )
    op.create_index(
        op.f("ix_interview_bundles_owner_id"), "interview_bundles", ["owner_id"]
    )
    op.create_table(
        "interview_bundle_items",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("bundle_id", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("topic_stable_id", sa.Text()),
        sa.Column("question", sa.Text()),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_optional", sa.Integer(), server_default="0", nullable=False),
        sa.Column("included", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint(
            "subject IN ('technical','behavioral','leadership')",
            name=op.f("ck_interview_bundle_items_subject_valid"),
        ),
        sa.CheckConstraint(
            "question IS NULL OR length(trim(question)) > 0",
            name=op.f("ck_interview_bundle_items_question_non_blank"),
        ),
        sa.CheckConstraint(
            "position >= 0", name=op.f("ck_interview_bundle_items_position_nonnegative")
        ),
        sa.CheckConstraint(
            "subject = 'technical' OR is_optional = 1",
            name=op.f("ck_interview_bundle_items_nontechnical_optional"),
        ),
        sa.CheckConstraint(
            "is_optional IN (0,1)",
            name=op.f("ck_interview_bundle_items_is_optional_valid"),
        ),
        sa.CheckConstraint(
            "is_optional IN (0,1)",
            name=op.f("ck_interview_bundle_items_is_optional_in_0_1"),
        ),
        sa.CheckConstraint(
            "included IN (0,1)", name=op.f("ck_interview_bundle_items_included_valid")
        ),
        sa.CheckConstraint(
            "included IN (0,1)", name=op.f("ck_interview_bundle_items_included_in_0_1")
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.ForeignKeyConstraint(
            ["bundle_id", "owner_id"],
            ["interview_bundles.id", "interview_bundles.owner_id"],
            ondelete="CASCADE",
            name="fk_interview_bundle_items_bundle_owner",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "owner_id", name="uq_interview_bundle_items_id_owner"
        ),
        sa.UniqueConstraint(
            "bundle_id",
            "owner_id",
            "position",
            name="uq_interview_bundle_items_bundle_owner_position",
        ),
    )
    op.create_index(
        op.f("ix_interview_bundle_items_owner_id"),
        "interview_bundle_items",
        ["owner_id"],
    )
    op.create_index(
        op.f("ix_interview_bundle_items_bundle_id"),
        "interview_bundle_items",
        ["bundle_id"],
    )
    op.create_table(
        "interview_idempotency",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "length(trim(operation)) > 0",
            name=op.f("ck_interview_idempotency_operation_non_blank"),
        ),
        sa.CheckConstraint(
            "length(trim(idempotency_key)) > 0",
            name=op.f("ck_interview_idempotency_key_non_blank"),
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "owner_id", name="uq_interview_idempotency_id_owner"),
        sa.UniqueConstraint(
            "owner_id",
            "operation",
            "idempotency_key",
            name="uq_interview_idempotency_owner_operation_key",
        ),
    )
    op.create_index(
        op.f("ix_interview_idempotency_owner_id"), "interview_idempotency", ["owner_id"]
    )


def downgrade() -> None:
    op.drop_table("interview_idempotency")
    op.drop_table("interview_bundle_items")
    op.drop_table("interview_bundles")
