"""Source registry, goal notebooks, and optional review queue.

Revision ID: b206a7d4e9f1
Revises: e205f6a2c4d1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b206a7d4e9f1"
down_revision: str | Sequence[str] | None = "e205f6a2c4d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("publisher", sa.Text()),
        sa.Column("canonical_url", sa.Text()),
        sa.Column("license_status", sa.Text(), nullable=False),
        sa.Column("availability_status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["owners.id"], name="fk_sources_owner_id_owners"
        ),
        sa.UniqueConstraint("id", "owner_id", name="uq_sources_id_owner"),
        sa.CheckConstraint("length(trim(origin)) > 0", name="origin_non_blank"),
        sa.CheckConstraint(
            "length(trim(source_type)) > 0", name="source_type_non_blank"
        ),
        sa.CheckConstraint("length(trim(title)) > 0", name="title_non_blank"),
        sa.CheckConstraint(
            "length(trim(license_status)) > 0", name="license_status_non_blank"
        ),
        sa.CheckConstraint(
            "availability_status IN ('available','unavailable','withdrawn')",
            name="availability_status_valid",
        ),
    )
    op.create_index(
        "ix_sources_owner_availability_title",
        "sources",
        ["owner_id", "availability_status", "title"],
    )
    op.create_table(
        "notebook_entries",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("topic_stable_id", sa.Text()),
        sa.Column("evidence_id", sa.Text()),
        sa.Column("source_id", sa.Text()),
        sa.Column("entry_kind", sa.Text(), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("tombstoned_at", sa.Text()),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["owners.id"], name="fk_notebook_entries_owner_id_owners"
        ),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_notebook_entries_goal_owner",
        ),
        sa.ForeignKeyConstraint(
            ["topic_stable_id"],
            ["topic_identities.stable_id"],
            name="fk_notebook_entries_topic_stable_id_topic_identities",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id", "owner_id", "goal_id"],
            ["evidence.id", "evidence.owner_id", "evidence.goal_id"],
            name="fk_notebook_entries_evidence_owner_goal",
        ),
        sa.ForeignKeyConstraint(
            ["source_id", "owner_id"],
            ["sources.id", "sources.owner_id"],
            name="fk_notebook_entries_source_owner",
        ),
        sa.UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_notebook_entries_id_owner_goal"
        ),
        sa.CheckConstraint("entry_kind IN ('auto','user')", name="entry_kind_valid"),
        sa.CheckConstraint("length(trim(markdown)) > 0", name="markdown_non_blank"),
    )
    op.create_index(
        "ix_notebook_entries_owner_goal_tombstone_updated",
        "notebook_entries",
        ["owner_id", "goal_id", "tombstoned_at", "updated_at"],
    )
    op.create_table(
        "goal_review_preferences",
        sa.Column("goal_id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Integer(), server_default="1", nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("cadence", sa.Text(), nullable=False),
        sa.Column(
            "retrieval_enabled", sa.Integer(), server_default="1", nullable=False
        ),
        sa.Column(
            "varied_context_enabled", sa.Integer(), server_default="1", nullable=False
        ),
        sa.Column("scheduling_version", sa.Text(), nullable=False),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name="fk_goal_review_preferences_owner_id_owners",
        ),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_goal_review_preferences_goal_owner",
        ),
        sa.UniqueConstraint(
            "goal_id", "owner_id", name="uq_goal_review_preferences_goal_owner"
        ),
        sa.CheckConstraint("enabled IN (0,1)", name="enabled_in_0_1"),
        sa.CheckConstraint(
            "retrieval_enabled IN (0,1)", name="retrieval_enabled_in_0_1"
        ),
        sa.CheckConstraint(
            "varied_context_enabled IN (0,1)", name="varied_context_enabled_in_0_1"
        ),
        sa.CheckConstraint(
            "duration_minutes IN (10,15,25)", name="duration_minutes_valid"
        ),
        sa.CheckConstraint(
            "cadence IN ('once-weekly','twice-weekly','three-times-weekly')",
            name="cadence_valid",
        ),
        sa.CheckConstraint(
            "length(trim(scheduling_version)) > 0", name="scheduling_version_non_blank"
        ),
    )
    op.create_table(
        "review_items",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("topic_stable_id", sa.Text(), nullable=False),
        sa.Column("prompt_ref", sa.Text(), nullable=False),
        sa.Column("prompt_type", sa.Text(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("due_at", sa.Text()),
        sa.Column("interval_label", sa.Text()),
        sa.Column("context", sa.Text()),
        sa.Column("scheduling_version", sa.Text(), nullable=False),
        sa.Column("failure_reference", sa.Text()),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["owners.id"], name="fk_review_items_owner_id_owners"
        ),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_review_items_goal_owner",
        ),
        sa.ForeignKeyConstraint(
            ["topic_stable_id"],
            ["topic_identities.stable_id"],
            name="fk_review_items_topic_stable_id_topic_identities",
        ),
        sa.UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_review_items_id_owner_goal"
        ),
        sa.CheckConstraint(
            "prompt_type IN ('recall','explanation','application')",
            name="prompt_type_valid",
        ),
        sa.CheckConstraint(
            "status IN ('ready','due','dismissed','disabled','generation-failed','completed')",
            name="status_valid",
        ),
        sa.CheckConstraint("length(trim(prompt_ref)) > 0", name="prompt_ref_non_blank"),
        sa.CheckConstraint("length(trim(prompt)) > 0", name="prompt_non_blank"),
        sa.CheckConstraint(
            "answer IS NULL OR length(trim(answer)) > 0", name="answer_non_blank"
        ),
        sa.CheckConstraint(
            "status = 'generation-failed' OR answer IS NOT NULL",
            name="usable_has_answer",
        ),
        sa.CheckConstraint(
            "length(trim(scheduling_version)) > 0", name="scheduling_version_non_blank"
        ),
        sa.CheckConstraint(
            "status != 'due' OR due_at IS NOT NULL", name="due_has_timestamp"
        ),
        sa.CheckConstraint(
            "status != 'generation-failed' OR failure_reference IS NOT NULL",
            name="failure_has_reference",
        ),
    )
    op.create_index(
        "ix_review_items_owner_goal_status_due",
        "review_items",
        ["owner_id", "goal_id", "status", "due_at"],
    )
    op.create_table(
        "review_attempts",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("review_item_id", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Text()),
        sa.Column("feedback", sa.Text()),
        sa.Column("correction", sa.Text()),
        sa.Column("next_interval_label", sa.Text()),
        sa.Column("context_variation", sa.Text()),
        sa.Column("context_result", sa.Text()),
        sa.Column("scheduling_version", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["owners.id"], name="fk_review_attempts_owner_id_owners"
        ),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_review_attempts_goal_owner",
        ),
        sa.ForeignKeyConstraint(
            ["review_item_id", "owner_id", "goal_id"],
            ["review_items.id", "review_items.owner_id", "review_items.goal_id"],
            name="fk_review_attempts_item_owner_goal",
        ),
        sa.UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_review_attempts_id_owner_goal"
        ),
        sa.CheckConstraint("length(trim(response)) > 0", name="response_non_blank"),
        sa.CheckConstraint(
            "confidence IS NULL OR confidence IN ('low','medium','high')",
            name="confidence_valid",
        ),
        sa.CheckConstraint(
            "length(trim(scheduling_version)) > 0", name="scheduling_version_non_blank"
        ),
    )
    op.create_index(
        "ix_review_attempts_owner_goal_item_created",
        "review_attempts",
        ["owner_id", "goal_id", "review_item_id", "created_at"],
    )
    op.create_table(
        "notebook_review_idempotency",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name="fk_notebook_review_idempotency_owner_id_owners",
        ),
        sa.UniqueConstraint(
            "id", "owner_id", name="uq_notebook_review_idempotency_id_owner"
        ),
        sa.UniqueConstraint(
            "owner_id",
            "operation",
            "idempotency_key",
            name="uq_notebook_review_idempotency_command",
        ),
        sa.CheckConstraint("length(trim(operation)) > 0", name="operation_non_blank"),
        sa.CheckConstraint("json_valid(response_json)", name="response_json_valid"),
    )
    for table in ("review_attempts", "notebook_review_idempotency"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_update BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, '{table} is immutable'); END"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, '{table} is immutable'); END"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_insert_replace BEFORE INSERT ON {table} WHEN EXISTS (SELECT 1 FROM {table} WHERE id=NEW.id) BEGIN SELECT RAISE(ABORT, '{table} replacement is not permitted'); END"
        )


def downgrade() -> None:
    for table in ("notebook_review_idempotency", "review_attempts"):
        for suffix in ("no_insert_replace", "no_delete", "no_update"):
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_{suffix}")
    op.drop_table("notebook_review_idempotency")
    op.drop_index(
        "ix_review_attempts_owner_goal_item_created", table_name="review_attempts"
    )
    op.drop_table("review_attempts")
    op.drop_index("ix_review_items_owner_goal_status_due", table_name="review_items")
    op.drop_table("review_items")
    op.drop_table("goal_review_preferences")
    op.drop_index(
        "ix_notebook_entries_owner_goal_tombstone_updated",
        table_name="notebook_entries",
    )
    op.drop_table("notebook_entries")
    op.drop_index("ix_sources_owner_availability_title", table_name="sources")
    op.drop_table("sources")
