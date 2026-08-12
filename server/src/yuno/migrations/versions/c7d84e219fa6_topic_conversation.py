"""Persist topic-attached tutor conversation turns.

Revision ID: c7d84e219fa6
Revises: 9b31c2d7e4f8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7d84e219fa6"
down_revision: str | Sequence[str] | None = "9b31c2d7e4f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "topic_conversation_turns",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), sa.ForeignKey("owners.id"), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("graph_version_id", sa.Text(), nullable=False),
        sa.Column("topic_stable_id", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("response_to_id", sa.Text()),
        sa.Column("job_id", sa.Text()),
        sa.Column("idempotency_key", sa.Text()),
        sa.Column("request_hash", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint("role IN ('learner','tutor')", name="role_valid"),
        sa.CheckConstraint("length(trim(body)) > 0", name="body_non_blank"),
        sa.CheckConstraint(
            "(role = 'learner' AND response_to_id IS NULL AND job_id IS NOT NULL AND idempotency_key IS NOT NULL AND request_hash IS NOT NULL) OR "
            "(role = 'tutor' AND response_to_id IS NOT NULL AND job_id IS NULL AND idempotency_key IS NULL AND request_hash IS NULL)",
            name="role_fields_valid",
        ),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_topic_conversation_turns_goal_owner",
        ),
        sa.ForeignKeyConstraint(
            ["graph_version_id", "topic_stable_id"],
            ["topics.graph_version_id", "topics.stable_id"],
            name="fk_topic_conversation_turns_topic",
        ),
        sa.ForeignKeyConstraint(
            ["response_to_id", "owner_id", "goal_id"],
            [
                "topic_conversation_turns.id",
                "topic_conversation_turns.owner_id",
                "topic_conversation_turns.goal_id",
            ],
            name="fk_topic_conversation_turns_response_owner_goal",
        ),
        sa.UniqueConstraint(
            "id",
            "owner_id",
            "goal_id",
            name="uq_topic_conversation_turns_id_owner_goal",
        ),
        sa.UniqueConstraint(
            "owner_id",
            "idempotency_key",
            name="uq_topic_conversation_turns_idempotency",
        ),
        sa.UniqueConstraint(
            "response_to_id", name="uq_topic_conversation_turns_response"
        ),
        sa.UniqueConstraint("job_id", name="uq_topic_conversation_turns_job"),
    )
    op.create_index(
        "ix_topic_conversation_turns_scope",
        "topic_conversation_turns",
        ["owner_id", "goal_id", "topic_stable_id", "created_at"],
    )
    op.create_table(
        "source_retrieval_commands",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), sa.ForeignKey("owners.id"), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id", "owner_id"],
            ["sources.id", "sources.owner_id"],
            name="fk_source_retrieval_commands_source_owner",
        ),
        sa.UniqueConstraint(
            "id", "owner_id", name="uq_source_retrieval_commands_id_owner"
        ),
        sa.UniqueConstraint(
            "owner_id",
            "idempotency_key",
            name="uq_source_retrieval_commands_idempotency",
        ),
        sa.UniqueConstraint("job_id", name="uq_source_retrieval_commands_job"),
    )


def downgrade() -> None:
    op.drop_table("source_retrieval_commands")
    op.drop_table("topic_conversation_turns")
