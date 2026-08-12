"""hands-on lifecycle

Revision ID: e7a405b1c2d3
Revises: c7d84e219fa6
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7a405b1c2d3"
down_revision: str | Sequence[str] | None = "c7d84e219fa6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hands_on_work",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("topic_stable_id", sa.Text(), nullable=False),
        sa.Column("scenario_title", sa.Text(), nullable=False),
        sa.Column("scenario_prompt", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("level", sa.Text(), nullable=False),
        sa.Column("constraints_json", sa.Text(), nullable=False),
        sa.Column("scenario_status", sa.Text(), nullable=False),
        sa.Column("scenario_source", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.Text(),
            nullable=False,
            server_default=sa.text("(strftime('%Y-%m-%dT%H:%M:%fZ','now'))"),
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_hands_on_work_goal_owner",
        ),
        sa.UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_hands_on_work_id_owner_goal"
        ),
        sa.UniqueConstraint(
            "owner_id", "goal_id", "topic_stable_id", name="uq_hands_on_work_topic"
        ),
        sa.CheckConstraint(
            "length(trim(scenario_title)) > 0", name="hands_on_scenario_title_non_blank"
        ),
        sa.CheckConstraint(
            "length(trim(scenario_prompt)) > 0",
            name="hands_on_scenario_prompt_non_blank",
        ),
        sa.CheckConstraint("length(trim(role)) > 0", name="hands_on_role_non_blank"),
        sa.CheckConstraint("length(trim(level)) > 0", name="hands_on_level_non_blank"),
        sa.CheckConstraint(
            "json_valid(constraints_json) AND json_type(constraints_json) = 'array'",
            name="hands_on_constraints_array",
        ),
        sa.CheckConstraint(
            "scenario_status IN ('fixture')", name="hands_on_scenario_status_valid"
        ),
        sa.CheckConstraint(
            "length(trim(scenario_source)) > 0",
            name="hands_on_scenario_source_non_blank",
        ),
    )
    op.create_table(
        "hands_on_artifacts",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("work_id", sa.Text(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("response_to_question_id", sa.Text()),
        sa.Column("cross_question_response", sa.Text()),
        sa.Column("evidence_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.Text(),
            nullable=False,
            server_default=sa.text("(strftime('%Y-%m-%dT%H:%M:%fZ','now'))"),
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.ForeignKeyConstraint(
            ["work_id", "owner_id", "goal_id"],
            ["hands_on_work.id", "hands_on_work.owner_id", "hands_on_work.goal_id"],
            name="fk_hands_on_artifacts_work",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id", "owner_id", "goal_id"],
            ["evidence.id", "evidence.owner_id", "evidence.goal_id"],
            name="fk_hands_on_artifacts_evidence",
        ),
        sa.UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_hands_on_artifacts_id_owner_goal"
        ),
        sa.UniqueConstraint(
            "work_id", "revision_number", name="uq_hands_on_artifacts_revision"
        ),
        sa.CheckConstraint("revision_number > 0", name="hands_on_revision_positive"),
        sa.CheckConstraint(
            "length(trim(content)) > 0", name="hands_on_artifact_content_non_blank"
        ),
        sa.CheckConstraint(
            "length(trim(content_hash)) > 0", name="hands_on_artifact_hash_non_blank"
        ),
        sa.CheckConstraint(
            "(response_to_question_id IS NULL) = (cross_question_response IS NULL)",
            name="hands_on_question_response_pair",
        ),
    )
    op.create_table(
        "hands_on_reviews",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("work_id", sa.Text(), nullable=False),
        sa.Column("artifact_id", sa.Text(), nullable=False),
        sa.Column("assessment_id", sa.Text(), nullable=False),
        sa.Column("review_mode", sa.Text(), nullable=False),
        sa.Column("required_limitation_label", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.Text(),
            nullable=False,
            server_default=sa.text("(strftime('%Y-%m-%dT%H:%M:%fZ','now'))"),
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.ForeignKeyConstraint(
            ["artifact_id", "owner_id", "goal_id"],
            [
                "hands_on_artifacts.id",
                "hands_on_artifacts.owner_id",
                "hands_on_artifacts.goal_id",
            ],
            name="fk_hands_on_reviews_artifact",
        ),
        sa.UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_hands_on_reviews_id_owner_goal"
        ),
        sa.UniqueConstraint("artifact_id", name="uq_hands_on_reviews_artifact"),
        sa.CheckConstraint(
            "review_mode IN ('static')", name="hands_on_review_mode_valid"
        ),
        sa.CheckConstraint(
            "review_mode != 'static' OR length(trim(required_limitation_label)) > 0",
            name="hands_on_static_limitation_non_blank",
        ),
    )
    op.create_table(
        "hands_on_cross_questions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("work_id", sa.Text(), nullable=False),
        sa.Column("review_id", sa.Text(), nullable=False),
        sa.Column("artifact_id", sa.Text(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("target_gap", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.Text(),
            nullable=False,
            server_default=sa.text("(strftime('%Y-%m-%dT%H:%M:%fZ','now'))"),
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.ForeignKeyConstraint(
            ["artifact_id", "owner_id", "goal_id"],
            [
                "hands_on_artifacts.id",
                "hands_on_artifacts.owner_id",
                "hands_on_artifacts.goal_id",
            ],
            name="fk_hands_on_questions_artifact",
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "owner_id", "goal_id"],
            [
                "hands_on_reviews.id",
                "hands_on_reviews.owner_id",
                "hands_on_reviews.goal_id",
            ],
            name="fk_hands_on_questions_review",
        ),
        sa.UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_hands_on_questions_id_owner_goal"
        ),
        sa.UniqueConstraint("review_id", name="uq_hands_on_questions_review"),
        sa.CheckConstraint(
            "length(trim(question)) > 0", name="hands_on_question_non_blank"
        ),
        sa.CheckConstraint(
            "length(trim(target_gap)) > 0", name="hands_on_target_gap_non_blank"
        ),
    )
    for table in ("hands_on_artifacts", "hands_on_reviews", "hands_on_cross_questions"):
        op.execute(
            f"CREATE TRIGGER {table}_immutable_update BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, '{table} rows are immutable'); END"
        )
        op.execute(
            f"CREATE TRIGGER {table}_immutable_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, '{table} rows are immutable'); END"
        )


def downgrade() -> None:
    for table in ("hands_on_cross_questions", "hands_on_reviews", "hands_on_artifacts"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_immutable_delete")
        op.execute(f"DROP TRIGGER IF EXISTS {table}_immutable_update")
        op.drop_table(table)
    op.drop_table("hands_on_work")
