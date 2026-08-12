"""durable owner progress-display setting

Revision ID: d208f9a4c6e1
Revises: 6ee79a009c2a
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d208f9a4c6e1"
down_revision: str | Sequence[str] | None = "6ee79a009c2a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "owner_settings",
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column(
            "progress_display",
            sa.Text(),
            server_default="detailed",
            nullable=False,
        ),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "progress_display IN ('detailed','simple')",
            name=op.f("ck_owner_settings_progress_display_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_owner_settings_owner_id_owners"),
        ),
        sa.PrimaryKeyConstraint("owner_id", name=op.f("pk_owner_settings")),
    )


def downgrade() -> None:
    op.drop_table("owner_settings")
