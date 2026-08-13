"""owner-scoped FTS5 search projection

Revision ID: c8a4d0e9f217
Revises: d9c407a1b2c3
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8a4d0e9f217"
down_revision: str | Sequence[str] | None = "d9c407a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_documents",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("generation", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("topic_stable_id", sa.Text()),
        sa.Column("version", sa.Text()),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("tags", sa.Text(), nullable=False),
        sa.Column("projection_version", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"], ["goal_workspaces.id", "goal_workspaces.owner_id"]
        ),
        sa.UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_search_documents_id_owner_goal"
        ),
        sa.UniqueConstraint(
            "owner_id",
            "goal_id",
            "generation",
            "entity_type",
            "entity_id",
            name="uq_search_documents_projection_entity",
        ),
        sa.CheckConstraint(
            "entity_type IN ('canonical-topic','canonical-content','generated-artifact','notebook-entry','evidence')",
            name="entity_type_valid",
        ),
    )
    op.create_index(
        "ix_search_documents_acl_generation",
        "search_documents",
        ["owner_id", "goal_id", "generation", "entity_type"],
    )
    op.create_table(
        "search_index_state",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("projection_name", sa.Text(), nullable=False),
        sa.Column("active_generation", sa.Text()),
        sa.Column("projection_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("source_watermark", sa.Text(), nullable=False),
        sa.Column("rebuild_job_id", sa.Text()),
        sa.Column("failure_reference", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.UniqueConstraint("id", "owner_id", name="uq_search_index_state_id_owner"),
        sa.UniqueConstraint(
            "owner_id", "projection_name", name="uq_search_index_state_owner_projection"
        ),
        sa.CheckConstraint(
            "status IN ('ready','stale','rebuilding','failed','unavailable')",
            name="status_valid",
        ),
    )
    op.execute(
        "CREATE VIRTUAL TABLE search_fts USING fts5(title, body, tags, content='search_documents', content_rowid='rowid')"
    )


def downgrade() -> None:
    op.execute("DROP TABLE search_fts")
    op.drop_table("search_index_state")
    op.drop_index("ix_search_documents_acl_generation", table_name="search_documents")
    op.drop_table("search_documents")
