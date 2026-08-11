"""profiles and isolated goal workspaces

Revision ID: b5d8d9a6104a
Revises: 87af9746aec1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b5d8d9a6104a"
down_revision: str | Sequence[str] | None = "87af9746aec1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "goal_workspaces",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), nullable=True),
        sa.Column("target_level", sa.Text(), nullable=False),
        sa.Column("target_capability", sa.Text(), nullable=False),
        sa.Column("graph_version_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("resume_position", sa.Text(), nullable=True),
        sa.Column("last_accessed_at", sa.Text(), nullable=True),
        sa.Column(
            "row_version", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "path IN ('learn','interview_prep')",
            name=op.f("ck_goal_workspaces_path_valid"),
        ),
        sa.CheckConstraint(
            "target_level IN ('Mid-level','Senior','Staff')",
            name=op.f("ck_goal_workspaces_target_level_valid"),
        ),
        sa.CheckConstraint(
            "target_capability IN ('know','understand','choose','implement','diagnose','defend')",
            name=op.f("ck_goal_workspaces_target_capability_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('active','archived')",
            name=op.f("ck_goal_workspaces_status_valid"),
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0", name=op.f("ck_goal_workspaces_name_non_blank")
        ),
        sa.CheckConstraint(
            "path != 'learn' OR length(trim(subject)) > 0",
            name=op.f("ck_goal_workspaces_learn_subject_required"),
        ),
        sa.CheckConstraint(
            "path != 'interview_prep' OR length(trim(role)) > 0",
            name=op.f("ck_goal_workspaces_interview_role_required"),
        ),
        sa.CheckConstraint(
            "path != 'learn' OR role IS NULL",
            name=op.f("ck_goal_workspaces_learn_role_absent"),
        ),
        sa.CheckConstraint(
            "path != 'interview_prep' OR subject IS NULL",
            name=op.f("ck_goal_workspaces_interview_subject_absent"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["owners.id"], name=op.f("fk_goal_workspaces_owner_id_owners")
        ),
        sa.ForeignKeyConstraint(
            ["graph_version_id"],
            ["canonical_graph_versions.id"],
            name=op.f("fk_goal_workspaces_graph_version_id_canonical_graph_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_goal_workspaces")),
        sa.UniqueConstraint("id", "owner_id", name="uq_goal_workspaces_id_owner"),
    )
    op.create_index(
        "ix_goal_workspaces_owner_status_recent",
        "goal_workspaces",
        ["owner_id", "status", "last_accessed_at"],
    )
    op.create_table(
        "learner_profiles",
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("experience", sa.Text(), nullable=True),
        sa.Column("strengths", sa.Text(), nullable=True),
        sa.Column("weaknesses", sa.Text(), nullable=True),
        sa.Column("current_goal_id", sa.Text(), nullable=True),
        sa.Column(
            "profile_revision",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_learner_profiles_owner_id_owners"),
        ),
        sa.ForeignKeyConstraint(
            ["current_goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_learner_profiles_current_goal_owner",
        ),
        sa.PrimaryKeyConstraint("owner_id", name=op.f("pk_learner_profiles")),
    )
    for table, timestamp in (
        ("goal_navigation_events", "occurred_at"),
        ("recommendation_dismissals", "dismissed_at"),
    ):
        key_column = (
            sa.Column("position", sa.Text(), nullable=True)
            if table == "goal_navigation_events"
            else sa.Column("recommendation_key", sa.Text(), nullable=False)
        )
        extra = (
            [sa.Column("destination", sa.Text(), nullable=False)]
            if table == "goal_navigation_events"
            else []
        )
        constraints: list[sa.SchemaItem] = [
            sa.ForeignKeyConstraint(
                ["owner_id"], ["owners.id"], name=op.f(f"fk_{table}_owner_id_owners")
            ),
            sa.ForeignKeyConstraint(
                ["goal_id", "owner_id"],
                ["goal_workspaces.id", "goal_workspaces.owner_id"],
                name=f"fk_{table}_goal_owner",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table}")),
            sa.UniqueConstraint(
                "id", "owner_id", "goal_id", name=f"uq_{table}_id_owner_goal"
            ),
        ]
        if table == "goal_navigation_events":
            constraints.append(
                sa.CheckConstraint(
                    "destination IN ('/app/learn-roadmap','/app/topic-studio','/app/interview-hub','/app/practice','/app/mock')",
                    name=op.f("ck_goal_navigation_events_destination_valid"),
                )
            )
        else:
            constraints.extend(
                [
                    sa.UniqueConstraint(
                        "owner_id",
                        "goal_id",
                        "recommendation_key",
                        name="uq_recommendation_dismissal_key",
                    ),
                    sa.CheckConstraint(
                        "length(trim(recommendation_key)) > 0",
                        name=op.f(
                            "ck_recommendation_dismissals_recommendation_key_non_blank"
                        ),
                    ),
                ]
            )
        op.create_table(
            table,
            sa.Column("id", sa.Text(), nullable=False),
            sa.Column("owner_id", sa.Text(), nullable=False),
            sa.Column("goal_id", sa.Text(), nullable=False),
            key_column,
            *extra,
            sa.Column(timestamp, sa.Text(), nullable=False),
            *constraints,
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_update BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_insert_replace BEFORE INSERT ON {table} "
            f"WHEN EXISTS (SELECT 1 FROM {table} WHERE id = NEW.id) "
            f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END"
        )
    op.create_table(
        "profiles_goals_idempotency",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "length(trim(operation)) > 0",
            name=op.f("ck_profiles_goals_idempotency_operation_non_blank"),
        ),
        sa.CheckConstraint(
            "length(trim(idempotency_key)) > 0",
            name=op.f("ck_profiles_goals_idempotency_idempotency_key_non_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_profiles_goals_idempotency_owner_id_owners"),
        ),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_profiles_goals_idempotency_goal_owner",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_profiles_goals_idempotency")),
        sa.UniqueConstraint(
            "id",
            "owner_id",
            "goal_id",
            name="uq_profiles_goals_idempotency_id_owner_goal",
        ),
        sa.UniqueConstraint(
            "owner_id",
            "operation",
            "idempotency_key",
            name="uq_profiles_goals_idempotency_command",
        ),
    )


def downgrade() -> None:
    op.drop_table("profiles_goals_idempotency")
    op.drop_table("recommendation_dismissals")
    op.drop_table("goal_navigation_events")
    op.drop_table("learner_profiles")
    op.drop_index(
        "ix_goal_workspaces_owner_status_recent", table_name="goal_workspaces"
    )
    op.drop_table("goal_workspaces")
