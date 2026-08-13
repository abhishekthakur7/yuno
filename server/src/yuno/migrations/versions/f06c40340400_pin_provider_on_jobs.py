"""Pin the selected provider on every provider-backed durable job."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "f06c40340400"
down_revision: str | None = "e10d1a0c0100"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("merge_items") as batch:
        batch.drop_constraint(
            "fk_merge_items_proposal_id_canonical_merge_proposals",
            type_="foreignkey",
        )
        batch.create_foreign_key(
            "fk_merge_items_proposal_owner_goal",
            "canonical_merge_proposals",
            ["proposal_id", "owner_id", "goal_id"],
            ["id", "owner_id", "goal_id"],
        )
    with op.batch_alter_table("jobs") as batch:
        batch.add_column(sa.Column("provider_name", sa.Text(), nullable=True))
        batch.create_check_constraint(
            "provider_name_valid",
            "provider_name IS NULL OR provider_name IN ('codex','claude')",
        )


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.drop_constraint("provider_name_valid", type_="check")
        batch.drop_column("provider_name")
    with op.batch_alter_table("merge_items") as batch:
        batch.drop_constraint(
            "fk_merge_items_proposal_owner_goal",
            type_="foreignkey",
        )
        batch.create_foreign_key(
            "fk_merge_items_proposal_id_canonical_merge_proposals",
            "canonical_merge_proposals",
            ["proposal_id"],
            ["id"],
        )
