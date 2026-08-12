"""generated content cache and provenance

Revision ID: 6ee79a009c2a
Revises: b206a7d4e9f1
Create Date: 2026-08-12 17:47:18.234959

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6ee79a009c2a"
down_revision: str | Sequence[str] | None = "b206a7d4e9f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "source_snapshots",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("retrieved_at", sa.Text(), nullable=False),
        sa.Column("content_ref", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("version_label", sa.Text(), nullable=True),
        sa.Column("redacted_failure", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('available','unavailable','withdrawn','failed')",
            name=op.f("ck_source_snapshots_status_valid"),
        ),
        sa.CheckConstraint(
            "length(trim(content_hash)) > 0",
            name=op.f("ck_source_snapshots_content_hash_non_blank"),
        ),
        sa.CheckConstraint(
            "length(trim(content_ref)) > 0",
            name=op.f("ck_source_snapshots_content_ref_non_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_source_snapshots_owner_id_owners"),
        ),
        sa.ForeignKeyConstraint(
            ["source_id", "owner_id"],
            ["sources.id", "sources.owner_id"],
            name="fk_source_snapshots_source_owner",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_snapshots")),
        sa.UniqueConstraint(
            "id", "owner_id", "source_id", name="uq_source_snapshots_id_owner_source"
        ),
        sa.UniqueConstraint("id", "owner_id", name="uq_source_snapshots_id_owner"),
    )
    op.create_table(
        "generated_artifacts",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("graph_version_id", sa.Text(), nullable=False),
        sa.Column("topic_stable_id", sa.Text(), nullable=False),
        sa.Column("layer", sa.Text(), nullable=False),
        sa.Column("artifact_type", sa.Text(), nullable=False),
        sa.Column("imports_hash", sa.Text(), nullable=False),
        sa.Column("prompt_template_version", sa.Text(), nullable=False),
        sa.Column("cache_key_hash", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("body_ref", sa.Text(), nullable=True),
        sa.Column("body_hash", sa.Text(), nullable=True),
        sa.Column("current_snapshot_id", sa.Text(), nullable=True),
        sa.Column("producing_job_id", sa.Text(), nullable=True),
        sa.Column("last_attempt_id", sa.Text(), nullable=True),
        sa.Column("last_job_id", sa.Text(), nullable=True),
        sa.Column("last_attempt_status", sa.Text(), nullable=True),
        sa.Column("failure_reference", sa.Text(), nullable=True),
        sa.Column("retryable", sa.Integer(), server_default="0", nullable=False),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "artifact_type IN ('lesson-layer')",
            name=op.f("ck_generated_artifacts_artifact_type_valid"),
        ),
        sa.CheckConstraint(
            "last_attempt_status IS NULL OR last_attempt_status IN ('queued','running','succeeded','failed','quarantined')",
            name=op.f("ck_generated_artifacts_last_attempt_status_valid"),
        ),
        sa.CheckConstraint(
            "layer IN ('Essential','Implementation','Internals','Production','Alternatives','Failures','Interview','Sources')",
            name=op.f("ck_generated_artifacts_layer_valid"),
        ),
        sa.CheckConstraint(
            "state != 'ready' OR (body_ref IS NOT NULL AND body_hash IS NOT NULL AND current_snapshot_id IS NOT NULL AND producing_job_id IS NOT NULL)",
            name=op.f("ck_generated_artifacts_ready_complete"),
        ),
        sa.CheckConstraint(
            "state IN ('generating','ready','failed')",
            name=op.f("ck_generated_artifacts_state_valid"),
        ),
        sa.CheckConstraint(
            "retryable IN (0,1)", name=op.f("ck_generated_artifacts_retryable_in_0_1")
        ),
        sa.ForeignKeyConstraint(
            ["current_snapshot_id", "owner_id", "goal_id", "id"],
            [
                "artifact_provenance_snapshots.id",
                "artifact_provenance_snapshots.owner_id",
                "artifact_provenance_snapshots.goal_id",
                "artifact_provenance_snapshots.artifact_id",
            ],
            name="fk_generated_artifacts_current_snapshot_owner_goal_artifact",
            use_alter=True,
        ),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_generated_artifacts_goal_owner",
        ),
        sa.ForeignKeyConstraint(
            ["graph_version_id", "topic_stable_id"],
            ["topics.graph_version_id", "topics.stable_id"],
            name="fk_generated_artifacts_topic",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_generated_artifacts_owner_id_owners"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_generated_artifacts")),
        sa.UniqueConstraint(
            "graph_version_id",
            "topic_stable_id",
            "goal_id",
            "layer",
            "imports_hash",
            "prompt_template_version",
            name="uq_generated_artifacts_d3_exact_key",
        ),
        sa.UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_generated_artifacts_id_owner_goal"
        ),
    )
    with op.batch_alter_table("generated_artifacts", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_generated_artifacts_cache_key_hash"),
            ["cache_key_hash"],
            unique=False,
        )
        batch_op.create_index(
            "ix_generated_artifacts_owner_goal_topic_layer",
            ["owner_id", "goal_id", "topic_stable_id", "layer"],
            unique=False,
        )

    op.create_table(
        "artifact_generation_attempts",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("artifact_id", sa.Text(), nullable=False),
        sa.Column("cache_key_hash", sa.Text(), nullable=False),
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("result_hash", sa.Text(), nullable=True),
        sa.Column("failure_classification", sa.Text(), nullable=True),
        sa.Column("failure_reference", sa.Text(), nullable=True),
        sa.Column("retryable", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("started_at", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "kind IN ('generate','regenerate')",
            name=op.f("ck_artifact_generation_attempts_kind_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','failed','quarantined')",
            name=op.f("ck_artifact_generation_attempts_status_valid"),
        ),
        sa.CheckConstraint(
            "retryable IN (0,1)",
            name=op.f("ck_artifact_generation_attempts_retryable_in_0_1"),
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id", "owner_id", "goal_id"],
            [
                "generated_artifacts.id",
                "generated_artifacts.owner_id",
                "generated_artifacts.goal_id",
            ],
            name="fk_artifact_generation_attempts_artifact_owner_goal",
        ),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_artifact_generation_attempts_goal_owner",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_artifact_generation_attempts_owner_id_owners"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifact_generation_attempts")),
        sa.UniqueConstraint(
            "id",
            "owner_id",
            "goal_id",
            "artifact_id",
            name="uq_artifact_generation_attempts_id_owner_goal_artifact",
        ),
        sa.UniqueConstraint(
            "id",
            "owner_id",
            "goal_id",
            name="uq_artifact_generation_attempts_id_owner_goal",
        ),
        sa.UniqueConstraint("job_id", name="uq_artifact_generation_attempts_job"),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_artifact_generation_attempts_active_artifact ON artifact_generation_attempts(artifact_id) WHERE status IN ('queued','running')"
    )

    op.create_table(
        "artifact_provenance_snapshots",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("artifact_id", sa.Text(), nullable=False),
        sa.Column("attempt_id", sa.Text(), nullable=False),
        sa.Column("evidence_state_hash", sa.Text(), nullable=False),
        sa.Column("profile_hash", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("contract_version", sa.Text(), nullable=False),
        sa.Column("prompt_template_version", sa.Text(), nullable=False),
        sa.Column("snapshot_hash", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["artifact_id", "owner_id", "goal_id"],
            [
                "generated_artifacts.id",
                "generated_artifacts.owner_id",
                "generated_artifacts.goal_id",
            ],
            name="fk_artifact_provenance_snapshots_artifact_owner_goal",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id", "owner_id", "goal_id", "artifact_id"],
            [
                "artifact_generation_attempts.id",
                "artifact_generation_attempts.owner_id",
                "artifact_generation_attempts.goal_id",
                "artifact_generation_attempts.artifact_id",
            ],
            name="fk_artifact_provenance_snapshots_attempt_owner_goal_artifact",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["artifact_generation_attempts.id"],
            name=op.f(
                "fk_artifact_provenance_snapshots_attempt_id_artifact_generation_attempts"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_artifact_provenance_snapshots_owner_id_owners"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifact_provenance_snapshots")),
        sa.UniqueConstraint(
            "attempt_id", name="uq_artifact_provenance_snapshots_attempt"
        ),
        sa.UniqueConstraint(
            "id",
            "owner_id",
            "goal_id",
            "artifact_id",
            name="uq_artifact_provenance_snapshots_id_owner_goal_artifact",
        ),
        sa.UniqueConstraint(
            "id",
            "owner_id",
            "goal_id",
            name="uq_artifact_provenance_snapshots_id_owner_goal",
        ),
    )
    op.create_table(
        "learning_content_idempotency",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("attempt_id", sa.Text(), nullable=False),
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "json_valid(response_json)",
            name=op.f("ck_learning_content_idempotency_response_json_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["artifact_generation_attempts.id"],
            name="fk_learning_content_idempotency_attempt",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_learning_content_idempotency_owner_id_owners"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learning_content_idempotency")),
        sa.UniqueConstraint(
            "id", "owner_id", name="uq_learning_content_idempotency_id_owner"
        ),
        sa.UniqueConstraint(
            "owner_id",
            "operation",
            "idempotency_key",
            name="uq_learning_content_idempotency_command",
        ),
        sa.UniqueConstraint(
            "owner_id",
            "idempotency_key",
            name="uq_learning_content_idempotency_owner_key",
        ),
    )
    op.create_table(
        "schema_quarantines",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("attempt_id", sa.Text(), nullable=False),
        sa.Column("raw_output_hash", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("validation_errors_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["owners.id"], name="fk_schema_quarantines_owner_id_owners"
        ),
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
    op.create_table(
        "artifact_provenance_refs",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("artifact_id", sa.Text(), nullable=False),
        sa.Column("snapshot_id", sa.Text(), nullable=False),
        sa.Column("ref_kind", sa.Text(), nullable=False),
        sa.Column("reference_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_artifact_provenance_refs_owner_id_owners"),
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "owner_id", "goal_id", "artifact_id"],
            [
                "artifact_provenance_snapshots.id",
                "artifact_provenance_snapshots.owner_id",
                "artifact_provenance_snapshots.goal_id",
                "artifact_provenance_snapshots.artifact_id",
            ],
            name="fk_artifact_provenance_refs_snapshot_owner_goal_artifact",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifact_provenance_refs")),
        sa.UniqueConstraint(
            "id",
            "owner_id",
            "goal_id",
            name="uq_artifact_provenance_refs_id_owner_goal",
        ),
        sa.UniqueConstraint(
            "snapshot_id",
            "ref_kind",
            "reference_id",
            name="uq_artifact_provenance_refs_ref",
        ),
    )
    op.create_table(
        "claims",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=True),
        sa.Column("content_revision_id", sa.Text(), nullable=True),
        sa.Column("generated_artifact_id", sa.Text(), nullable=True),
        sa.Column("snapshot_id", sa.Text(), nullable=True),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("claim_type", sa.Text(), nullable=False),
        sa.Column("sensitive", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "claim_type IN ('fact','trade-off','routine','disputed','comparative','time-or-version-dependent')",
            name=op.f("ck_claims_claim_type_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','published')", name=op.f("ck_claims_status_valid")
        ),
        sa.CheckConstraint(
            "(content_revision_id IS NOT NULL) != (generated_artifact_id IS NOT NULL)",
            name=op.f("ck_claims_exactly_one_parent"),
        ),
        sa.CheckConstraint(
            "generated_artifact_id IS NOT NULL OR snapshot_id IS NULL",
            name=op.f("ck_claims_snapshot_generated_only"),
        ),
        sa.CheckConstraint(
            "length(trim(claim_text)) > 0", name=op.f("ck_claims_claim_text_non_blank")
        ),
        sa.CheckConstraint(
            "sensitive IN (0,1)", name=op.f("ck_claims_sensitive_in_0_1")
        ),
        sa.ForeignKeyConstraint(
            ["content_revision_id"],
            ["content_revisions.id"],
            name="fk_claims_content_revision",
        ),
        sa.ForeignKeyConstraint(
            ["generated_artifact_id", "owner_id", "goal_id"],
            [
                "generated_artifacts.id",
                "generated_artifacts.owner_id",
                "generated_artifacts.goal_id",
            ],
            name="fk_claims_artifact_owner_goal",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["owners.id"], name=op.f("fk_claims_owner_id_owners")
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "owner_id", "goal_id", "generated_artifact_id"],
            [
                "artifact_provenance_snapshots.id",
                "artifact_provenance_snapshots.owner_id",
                "artifact_provenance_snapshots.goal_id",
                "artifact_provenance_snapshots.artifact_id",
            ],
            name="fk_claims_snapshot_owner_goal_artifact",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_claims")),
        sa.UniqueConstraint("id", "owner_id", name="uq_claims_id_owner"),
    )
    op.create_table(
        "citations",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("claim_id", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("source_snapshot_id", sa.Text(), nullable=True),
        sa.Column("locator", sa.Text(), nullable=False),
        sa.Column("support_kind", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "length(trim(locator)) > 0", name=op.f("ck_citations_locator_non_blank")
        ),
        sa.CheckConstraint(
            "length(trim(support_kind)) > 0",
            name=op.f("ck_citations_support_kind_non_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["claim_id", "owner_id"],
            ["claims.id", "claims.owner_id"],
            name="fk_citations_claim_owner",
        ),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_citations_goal_owner",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["owners.id"], name=op.f("fk_citations_owner_id_owners")
        ),
        sa.ForeignKeyConstraint(
            ["source_id", "owner_id"],
            ["sources.id", "sources.owner_id"],
            name="fk_citations_source_owner",
        ),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id", "owner_id", "source_id"],
            [
                "source_snapshots.id",
                "source_snapshots.owner_id",
                "source_snapshots.source_id",
            ],
            name="fk_citations_source_snapshot_owner_source",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_citations")),
        sa.UniqueConstraint(
            "claim_id",
            "source_id",
            "source_snapshot_id",
            "locator",
            name="uq_citations_support",
        ),
        sa.UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_citations_id_owner_goal"
        ),
    )
    for table in (
        "source_snapshots",
        "artifact_provenance_snapshots",
        "artifact_provenance_refs",
        "citations",
    ):
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_update BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, '{table} is immutable'); END"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_insert_replace BEFORE INSERT ON {table} WHEN EXISTS (SELECT 1 FROM {table} WHERE id=NEW.id) BEGIN SELECT RAISE(ABORT, '{table} replacement is not permitted'); END"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, '{table} is immutable'); END"
        )
    op.execute(
        """CREATE TRIGGER trg_claims_required_citation_on_published_insert BEFORE INSERT ON claims WHEN NEW.status='published' AND (NEW.sensitive=1 OR NEW.claim_type IN ('disputed','comparative','time-or-version-dependent')) BEGIN SELECT RAISE(ABORT, 'required claim must publish through pending state'); END"""
    )
    op.execute(
        """CREATE TRIGGER trg_claims_required_citation_on_publish BEFORE UPDATE OF status ON claims WHEN NEW.status='published' AND (NEW.sensitive=1 OR NEW.claim_type IN ('disputed','comparative','time-or-version-dependent')) AND NOT EXISTS (SELECT 1 FROM citations WHERE claim_id=NEW.id AND owner_id=NEW.owner_id) BEGIN SELECT RAISE(ABORT, 'required claim citation missing'); END"""
    )
    op.execute(
        "CREATE TRIGGER trg_claims_published_no_delete BEFORE DELETE ON claims WHEN OLD.status='published' BEGIN SELECT RAISE(ABORT, 'published claims are immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_claims_no_insert_replace BEFORE INSERT ON claims WHEN EXISTS (SELECT 1 FROM claims WHERE id=NEW.id) BEGIN SELECT RAISE(ABORT, 'claim replacement is not permitted'); END"
    )
    op.execute(
        """CREATE TRIGGER trg_claims_published_no_update BEFORE UPDATE ON claims WHEN OLD.status='published' BEGIN SELECT RAISE(ABORT, 'published claims are immutable'); END"""
    )
    op.execute(
        "CREATE TRIGGER trg_sources_no_delete BEFORE DELETE ON sources BEGIN SELECT RAISE(ABORT, 'sources are retained'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_sources_no_insert_replace BEFORE INSERT ON sources WHEN EXISTS (SELECT 1 FROM sources WHERE id=NEW.id) BEGIN SELECT RAISE(ABORT, 'source replacement is not permitted'); END"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS trg_sources_no_delete")
    op.execute("DROP TRIGGER IF EXISTS trg_claims_published_no_delete")
    op.execute("DROP TRIGGER IF EXISTS trg_claims_no_insert_replace")
    op.execute("DROP TRIGGER IF EXISTS trg_claims_published_no_update")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_claims_required_citation_on_published_insert"
    )
    op.execute("DROP TRIGGER IF EXISTS trg_claims_required_citation_on_publish")
    op.execute("DROP TRIGGER IF EXISTS trg_sources_no_insert_replace")
    for table in (
        "citations",
        "artifact_provenance_refs",
        "artifact_provenance_snapshots",
        "source_snapshots",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_update")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_insert_replace")
    op.drop_table("citations")
    op.drop_table("claims")
    op.drop_table("artifact_provenance_refs")
    op.drop_table("learning_content_idempotency")
    op.drop_table("schema_quarantines")
    op.drop_table("artifact_provenance_snapshots")
    with op.batch_alter_table("artifact_generation_attempts", schema=None) as batch_op:
        batch_op.drop_index(
            "uq_artifact_generation_attempts_active_artifact",
            sqlite_where=sa.text("status IN ('queued','running')"),
        )

    op.drop_table("artifact_generation_attempts")
    with op.batch_alter_table("generated_artifacts", schema=None) as batch_op:
        batch_op.drop_index("ix_generated_artifacts_owner_goal_topic_layer")
        batch_op.drop_index(batch_op.f("ix_generated_artifacts_cache_key_hash"))

    op.drop_table("generated_artifacts")
    op.drop_table("source_snapshots")
