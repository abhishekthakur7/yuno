"""SQLAlchemy generated-content cache repository."""

from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from yuno.modules.learning_content.domain import (
    ArtifactState,
    ConversationRole,
    GeneratedArtifact,
    GenerationAttempt,
    GenerationAttemptStatus,
    GenerationIdempotencyRecord,
    TopicConversationTurn,
    TopicLayer,
)
from yuno.modules.learning_content.models import (
    GeneratedArtifactRow,
    GenerationAttemptRow,
    LearningContentIdempotencyRow,
    TopicConversationTurnRow,
)
from yuno.shared.infrastructure.repository import (
    SqlAlchemyRepository,
    owner_scoped_select,
)


class SqlAlchemyLearningContentRepository(SqlAlchemyRepository):
    def get_artifact_by_key(
        self,
        owner_id,
        graph_version_id,
        topic_id,
        goal_id,
        layer,
        imports_hash,
        template_version,
    ):
        row = self._session.scalars(
            owner_scoped_select(GeneratedArtifactRow, owner_id).where(
                GeneratedArtifactRow.graph_version_id == graph_version_id,
                GeneratedArtifactRow.topic_stable_id == topic_id,
                GeneratedArtifactRow.goal_id == goal_id,
                GeneratedArtifactRow.layer == layer,
                GeneratedArtifactRow.imports_hash == imports_hash,
                GeneratedArtifactRow.prompt_template_version == template_version,
            )
        ).one_or_none()
        return _artifact(row) if row else None

    def get_artifact(self, owner_id, artifact_id):
        row = self._session.scalars(
            owner_scoped_select(GeneratedArtifactRow, owner_id).where(
                GeneratedArtifactRow.id == artifact_id
            )
        ).one_or_none()
        return _artifact(row) if row else None

    def get_latest_artifact(self, owner_id, goal_id, topic_id, layer):
        row = self._session.scalars(
            owner_scoped_select(GeneratedArtifactRow, owner_id)
            .where(
                GeneratedArtifactRow.goal_id == goal_id,
                GeneratedArtifactRow.topic_stable_id == topic_id,
                GeneratedArtifactRow.layer == layer,
                GeneratedArtifactRow.body_ref.is_not(None),
            )
            .order_by(GeneratedArtifactRow.generated_at.desc())
            .limit(1)
        ).first()
        return _artifact(row) if row else None

    def list_artifacts(self, owner_id, goal_id, layer):
        rows = self._session.scalars(
            owner_scoped_select(GeneratedArtifactRow, owner_id)
            .where(
                GeneratedArtifactRow.goal_id == goal_id,
                GeneratedArtifactRow.layer == layer,
                GeneratedArtifactRow.body_ref.is_not(None),
            )
            .order_by(
                GeneratedArtifactRow.topic_stable_id,
                GeneratedArtifactRow.generated_at.desc(),
                GeneratedArtifactRow.id.desc(),
            )
        ).all()
        return tuple(_artifact(row) for row in rows)

    def add_artifact(self, artifact):
        values = artifact.__dict__.copy()
        body = values.pop("body")
        values["body_ref"] = "inline:" + body if body is not None else None
        values.update(
            layer=artifact.layer.value,
            state=artifact.state.value,
            last_attempt_status=artifact.last_attempt_status.value
            if artifact.last_attempt_status
            else None,
            retryable=int(artifact.retryable),
        )
        self._session.execute(
            sqlite_insert(GeneratedArtifactRow)
            .values(**values)
            .on_conflict_do_nothing()
        )
        self._session.flush()
        return self.get_artifact_by_key(
            artifact.owner_id,
            artifact.graph_version_id,
            artifact.topic_stable_id,
            artifact.goal_id,
            artifact.layer.value,
            artifact.imports_hash,
            artifact.prompt_template_version,
        )

    def update_artifact(self, owner_id, artifact_id, changes):
        changes = dict(changes)
        if "body" in changes:
            body = changes.pop("body")
            changes["body_ref"] = "inline:" + body if body is not None else None
        values = {
            k: (
                v.value if hasattr(v, "value") else int(v) if isinstance(v, bool) else v
            )
            for k, v in changes.items()
        }
        values["row_version"] = GeneratedArtifactRow.row_version + 1
        self._session.execute(
            update(GeneratedArtifactRow)
            .where(
                GeneratedArtifactRow.owner_id == owner_id,
                GeneratedArtifactRow.id == artifact_id,
            )
            .values(**values)
        )
        self._session.flush()
        return self.get_artifact(owner_id, artifact_id)

    def add_attempt(self, attempt):
        values = attempt.__dict__.copy()
        values.update(status=attempt.status.value, retryable=int(attempt.retryable))
        self._session.execute(
            sqlite_insert(GenerationAttemptRow)
            .values(**values)
            .on_conflict_do_nothing()
        )
        self._session.flush()
        return self.get_active_attempt(attempt.owner_id, attempt.artifact_id)

    def get_attempt(self, owner_id, attempt_id):
        row = self._session.scalars(
            owner_scoped_select(GenerationAttemptRow, owner_id).where(
                GenerationAttemptRow.id == attempt_id
            )
        ).one_or_none()
        return _attempt(row) if row else None

    def get_active_attempt(self, owner_id, artifact_id):
        row = self._session.scalars(
            owner_scoped_select(GenerationAttemptRow, owner_id).where(
                GenerationAttemptRow.artifact_id == artifact_id,
                GenerationAttemptRow.status.in_(("queued", "running")),
            )
        ).one_or_none()
        return _attempt(row) if row else None

    def update_attempt(self, owner_id, attempt_id, expected_status, changes):
        values = {
            k: (
                v.value if hasattr(v, "value") else int(v) if isinstance(v, bool) else v
            )
            for k, v in changes.items()
        }
        result = self._session.execute(
            update(GenerationAttemptRow)
            .where(
                GenerationAttemptRow.owner_id == owner_id,
                GenerationAttemptRow.id == attempt_id,
                GenerationAttemptRow.status == expected_status,
            )
            .values(**values)
        )
        if result.rowcount != 1:
            raise RuntimeError("Generation attempt changed concurrently.")
        self._session.flush()
        return self.get_attempt(owner_id, attempt_id)

    def get_idempotency(self, owner_id, operation, key):
        r = self._session.scalars(
            owner_scoped_select(LearningContentIdempotencyRow, owner_id).where(
                LearningContentIdempotencyRow.operation == operation,
                LearningContentIdempotencyRow.idempotency_key == key,
            )
        ).one_or_none()
        return _idempotency(r) if r else None

    def add_idempotency(self, record):
        self._session.execute(
            sqlite_insert(LearningContentIdempotencyRow)
            .values(**record.__dict__)
            .on_conflict_do_nothing()
        )
        self._session.flush()
        return self.get_idempotency_by_key(record.owner_id, record.idempotency_key)

    def get_idempotency_by_key(self, owner_id, key):
        r = self._session.scalars(
            owner_scoped_select(LearningContentIdempotencyRow, owner_id)
            .where(LearningContentIdempotencyRow.idempotency_key == key)
            .limit(1)
        ).first()
        return _idempotency(r) if r else None

    def add_conversation_turn(self, turn):
        values = turn.__dict__.copy()
        values["role"] = turn.role.value
        self._session.add(TopicConversationTurnRow(**values))
        self._session.flush()
        return turn

    def get_conversation_turn(self, owner_id, turn_id):
        row = self._session.scalars(
            owner_scoped_select(TopicConversationTurnRow, owner_id).where(
                TopicConversationTurnRow.id == turn_id
            )
        ).one_or_none()
        return _conversation_turn(row) if row else None

    def get_conversation_turn_by_idempotency(self, owner_id, key):
        row = self._session.scalars(
            owner_scoped_select(TopicConversationTurnRow, owner_id).where(
                TopicConversationTurnRow.idempotency_key == key
            )
        ).one_or_none()
        return _conversation_turn(row) if row else None

    def list_conversation_turns(self, owner_id, goal_id, topic_id):
        rows = self._session.scalars(
            owner_scoped_select(TopicConversationTurnRow, owner_id)
            .where(
                TopicConversationTurnRow.goal_id == goal_id,
                TopicConversationTurnRow.topic_stable_id == topic_id,
            )
            .order_by(
                TopicConversationTurnRow.created_at,
                TopicConversationTurnRow.id,
            )
        ).all()
        return tuple(_conversation_turn(row) for row in rows)


def _artifact(r):
    return GeneratedArtifact(
        r.id,
        r.owner_id,
        r.goal_id,
        r.graph_version_id,
        r.topic_stable_id,
        TopicLayer(r.layer),
        r.artifact_type,
        r.imports_hash,
        r.prompt_template_version,
        r.cache_key_hash,
        ArtifactState(r.state),
        r.body_ref.removeprefix("inline:")
        if r.body_ref and r.body_ref.startswith("inline:")
        else None,
        r.body_hash,
        r.current_snapshot_id,
        r.producing_job_id,
        r.last_attempt_id,
        r.last_job_id,
        GenerationAttemptStatus(r.last_attempt_status)
        if r.last_attempt_status
        else None,
        r.failure_reference,
        bool(r.retryable),
        r.row_version,
        r.created_at,
        r.updated_at,
        r.generated_at,
    )


def _attempt(r):
    return GenerationAttempt(
        r.id,
        r.owner_id,
        r.goal_id,
        r.artifact_id,
        r.cache_key_hash,
        r.job_id,
        r.kind,
        GenerationAttemptStatus(r.status),
        r.request_hash,
        r.result_hash,
        r.failure_classification,
        r.failure_reference,
        bool(r.retryable),
        r.created_at,
        r.started_at,
        r.completed_at,
    )


def _idempotency(r):
    return GenerationIdempotencyRecord(
        r.id,
        r.owner_id,
        r.operation,
        r.idempotency_key,
        r.request_hash,
        r.attempt_id,
        r.job_id,
        r.response_json,
        r.created_at,
    )


def _conversation_turn(r):
    return TopicConversationTurn(
        r.id,
        r.owner_id,
        r.goal_id,
        r.graph_version_id,
        r.topic_stable_id,
        ConversationRole(r.role),
        r.body,
        r.response_to_id,
        r.job_id,
        r.idempotency_key,
        r.request_hash,
        r.created_at,
    )
