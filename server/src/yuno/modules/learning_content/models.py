"""Generated-content cache persistence."""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from yuno.shared.infrastructure.base import (
    Base,
    boolean_column,
    id_column,
    row_version_column,
    utc_timestamp_column,
)

_LAYERS = "'Essential','Implementation','Internals','Production','Alternatives','Failures','Interview','Sources'"


class GeneratedArtifactRow(Base):
    __tablename__ = "generated_artifacts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_generated_artifacts_goal_owner",
        ),
        ForeignKeyConstraint(
            ["graph_version_id", "topic_stable_id"],
            ["topics.graph_version_id", "topics.stable_id"],
            name="fk_generated_artifacts_topic",
        ),
        UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_generated_artifacts_id_owner_goal"
        ),
        UniqueConstraint(
            "graph_version_id",
            "topic_stable_id",
            "goal_id",
            "layer",
            "imports_hash",
            "prompt_template_version",
            name="uq_generated_artifacts_d3_exact_key",
        ),
        CheckConstraint(f"layer IN ({_LAYERS})", name="layer_valid"),
        CheckConstraint(
            "artifact_type IN ('lesson-layer')", name="artifact_type_valid"
        ),
        CheckConstraint("state IN ('generating','ready','failed')", name="state_valid"),
        CheckConstraint(
            "last_attempt_status IS NULL OR last_attempt_status IN ('queued','running','succeeded','failed','quarantined')",
            name="last_attempt_status_valid",
        ),
        CheckConstraint(
            "state != 'ready' OR (body_ref IS NOT NULL AND body_hash IS NOT NULL AND current_snapshot_id IS NOT NULL AND producing_job_id IS NOT NULL)",
            name="ready_complete",
        ),
        Index(
            "ix_generated_artifacts_owner_goal_topic_layer",
            "owner_id",
            "goal_id",
            "topic_stable_id",
            "layer",
        ),
        ForeignKeyConstraint(
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
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    graph_version_id: Mapped[str] = mapped_column(Text, nullable=False)
    topic_stable_id: Mapped[str] = mapped_column(Text, nullable=False)
    layer: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_type: Mapped[str] = mapped_column(Text, nullable=False)
    imports_hash: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_template_version: Mapped[str] = mapped_column(Text, nullable=False)
    cache_key_hash: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    body_ref: Mapped[str | None] = mapped_column(Text)
    body_hash: Mapped[str | None] = mapped_column(Text)
    current_snapshot_id: Mapped[str | None] = mapped_column(Text)
    producing_job_id: Mapped[str | None] = mapped_column(Text)
    last_attempt_id: Mapped[str | None] = mapped_column(Text)
    last_job_id: Mapped[str | None] = mapped_column(Text)
    last_attempt_status: Mapped[str | None] = mapped_column(Text)
    failure_reference: Mapped[str | None] = mapped_column(Text)
    retryable: Mapped[int] = boolean_column("retryable", default=False)
    row_version: Mapped[int] = row_version_column()
    created_at: Mapped[str] = utc_timestamp_column()
    updated_at: Mapped[str] = utc_timestamp_column()
    generated_at: Mapped[str | None] = utc_timestamp_column(nullable=True)


class GenerationAttemptRow(Base):
    __tablename__ = "artifact_generation_attempts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_artifact_generation_attempts_goal_owner",
        ),
        ForeignKeyConstraint(
            ["artifact_id", "owner_id", "goal_id"],
            [
                "generated_artifacts.id",
                "generated_artifacts.owner_id",
                "generated_artifacts.goal_id",
            ],
            name="fk_artifact_generation_attempts_artifact_owner_goal",
        ),
        UniqueConstraint(
            "id",
            "owner_id",
            "goal_id",
            name="uq_artifact_generation_attempts_id_owner_goal",
        ),
        UniqueConstraint(
            "id",
            "owner_id",
            "goal_id",
            "artifact_id",
            name="uq_artifact_generation_attempts_id_owner_goal_artifact",
        ),
        UniqueConstraint("job_id", name="uq_artifact_generation_attempts_job"),
        CheckConstraint("kind IN ('generate','regenerate')", name="kind_valid"),
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed','quarantined')",
            name="status_valid",
        ),
        Index(
            "uq_artifact_generation_attempts_active_artifact",
            "artifact_id",
            unique=True,
            sqlite_where=text("status IN ('queued','running')"),
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_id: Mapped[str] = mapped_column(Text, nullable=False)
    cache_key_hash: Mapped[str] = mapped_column(Text, nullable=False)
    job_id: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    result_hash: Mapped[str | None] = mapped_column(Text)
    failure_classification: Mapped[str | None] = mapped_column(Text)
    failure_reference: Mapped[str | None] = mapped_column(Text)
    retryable: Mapped[int] = boolean_column("retryable", default=False)
    created_at: Mapped[str] = utc_timestamp_column()
    started_at: Mapped[str | None] = utc_timestamp_column(nullable=True)
    completed_at: Mapped[str | None] = utc_timestamp_column(nullable=True)


class LearningContentIdempotencyRow(Base):
    __tablename__ = "learning_content_idempotency"
    __table_args__ = (
        UniqueConstraint(
            "id", "owner_id", name="uq_learning_content_idempotency_id_owner"
        ),
        UniqueConstraint(
            "owner_id",
            "operation",
            "idempotency_key",
            name="uq_learning_content_idempotency_command",
        ),
        UniqueConstraint(
            "owner_id",
            "idempotency_key",
            name="uq_learning_content_idempotency_owner_key",
        ),
        CheckConstraint("json_valid(response_json)", name="response_json_valid"),
        ForeignKeyConstraint(
            ["attempt_id"],
            ["artifact_generation_attempts.id"],
            name="fk_learning_content_idempotency_attempt",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_id: Mapped[str] = mapped_column(Text, nullable=False)
    job_id: Mapped[str] = mapped_column(Text, nullable=False)
    response_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()


class TopicConversationTurnRow(Base):
    __tablename__ = "topic_conversation_turns"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_topic_conversation_turns_goal_owner",
        ),
        ForeignKeyConstraint(
            ["graph_version_id", "topic_stable_id"],
            ["topics.graph_version_id", "topics.stable_id"],
            name="fk_topic_conversation_turns_topic",
        ),
        ForeignKeyConstraint(
            ["response_to_id", "owner_id", "goal_id"],
            [
                "topic_conversation_turns.id",
                "topic_conversation_turns.owner_id",
                "topic_conversation_turns.goal_id",
            ],
            name="fk_topic_conversation_turns_response_owner_goal",
        ),
        UniqueConstraint(
            "id",
            "owner_id",
            "goal_id",
            name="uq_topic_conversation_turns_id_owner_goal",
        ),
        UniqueConstraint(
            "owner_id",
            "idempotency_key",
            name="uq_topic_conversation_turns_idempotency",
        ),
        UniqueConstraint("response_to_id", name="uq_topic_conversation_turns_response"),
        UniqueConstraint("job_id", name="uq_topic_conversation_turns_job"),
        CheckConstraint("role IN ('learner','tutor')", name="role_valid"),
        CheckConstraint("length(trim(body)) > 0", name="body_non_blank"),
        CheckConstraint(
            "(role = 'learner' AND response_to_id IS NULL AND job_id IS NOT NULL AND idempotency_key IS NOT NULL AND request_hash IS NOT NULL) OR "
            "(role = 'tutor' AND response_to_id IS NOT NULL AND job_id IS NULL AND idempotency_key IS NULL AND request_hash IS NULL)",
            name="role_fields_valid",
        ),
        Index(
            "ix_topic_conversation_turns_scope",
            "owner_id",
            "goal_id",
            "topic_stable_id",
            "created_at",
        ),
    )

    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    graph_version_id: Mapped[str] = mapped_column(Text, nullable=False)
    topic_stable_id: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    response_to_id: Mapped[str | None] = mapped_column(Text)
    job_id: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    request_hash: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = utc_timestamp_column()
