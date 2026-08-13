"""SQLAlchemy generated-content cache repository."""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from yuno.modules.data_lifecycle.models import (
    GeneratedArtifactBodyRow,
    LearningContentIdempotencyBodyRow,
    TopicConversationTurnBodyRow,
)
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
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.infrastructure.repository import (
    SqlAlchemyRepository,
    owner_scoped_select,
)


class SqlAlchemyLearningContentRepository(SqlAlchemyRepository):
    def count_live_artifacts(self, owner_id: str) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(GeneratedArtifactBodyRow)
                .where(GeneratedArtifactBodyRow.owner_id == owner_id)
            )
            or 0
        )

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
        return self._artifact(row) if row else None

    def get_artifact(self, owner_id, artifact_id):
        row = self._session.scalars(
            owner_scoped_select(GeneratedArtifactRow, owner_id).where(
                GeneratedArtifactRow.id == artifact_id
            )
        ).one_or_none()
        return self._artifact(row) if row else None

    def get_latest_artifact(self, owner_id, goal_id, topic_id, layer):
        row = self._session.scalars(
            owner_scoped_select(GeneratedArtifactRow, owner_id)
            .where(
                GeneratedArtifactRow.goal_id == goal_id,
                GeneratedArtifactRow.topic_stable_id == topic_id,
                GeneratedArtifactRow.layer == layer,
                GeneratedArtifactRow.id.in_(
                    select(GeneratedArtifactBodyRow.artifact_id)
                ),
            )
            .order_by(GeneratedArtifactRow.generated_at.desc())
            .limit(1)
        ).first()
        return self._artifact(row) if row else None

    def list_artifacts(self, owner_id, goal_id, layer):
        rows = self._session.scalars(
            owner_scoped_select(GeneratedArtifactRow, owner_id)
            .where(
                GeneratedArtifactRow.goal_id == goal_id,
                GeneratedArtifactRow.layer == layer,
                GeneratedArtifactRow.id.in_(
                    select(GeneratedArtifactBodyRow.artifact_id)
                ),
            )
            .order_by(
                GeneratedArtifactRow.topic_stable_id,
                GeneratedArtifactRow.generated_at.desc(),
                GeneratedArtifactRow.id.desc(),
            )
        ).all()
        return tuple(self._artifact(row) for row in rows)

    def add_artifact(self, artifact):
        values = artifact.__dict__.copy()
        body = values.pop("body")
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
        if body is not None:
            self._session.execute(
                sqlite_insert(GeneratedArtifactBodyRow)
                .values(
                    artifact_id=artifact.id,
                    owner_id=artifact.owner_id,
                    goal_id=artifact.goal_id,
                    body_ref="inline:" + body,
                )
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
            if body is None:
                self._session.execute(
                    GeneratedArtifactBodyRow.__table__.delete().where(
                        GeneratedArtifactBodyRow.owner_id == owner_id,
                        GeneratedArtifactBodyRow.artifact_id == artifact_id,
                    )
                )
            else:
                self._session.execute(
                    sqlite_insert(GeneratedArtifactBodyRow)
                    .values(
                        artifact_id=artifact_id,
                        owner_id=owner_id,
                        goal_id=self._session.scalar(
                            select(GeneratedArtifactRow.goal_id).where(
                                GeneratedArtifactRow.id == artifact_id
                            )
                        ),
                        body_ref="inline:" + body,
                    )
                    .on_conflict_do_update(
                        index_elements=["artifact_id"],
                        set_={"body_ref": "inline:" + body},
                    )
                )
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
        body = self._session.get(LearningContentIdempotencyBodyRow, r.id) if r else None
        return _idempotency(r, body) if r and body else None

    def add_idempotency(self, record):
        result = self._session.execute(
            sqlite_insert(LearningContentIdempotencyRow)
            .values(
                **{
                    **{
                        k: v for k, v in record.__dict__.items() if k != "response_json"
                    },
                    "response_hash": hash_payload(record.response_json),
                }
            )
            .on_conflict_do_nothing()
        )
        if result.rowcount:
            self._session.add(
                LearningContentIdempotencyBodyRow(
                    idempotency_id=record.id,
                    owner_id=record.owner_id,
                    response_json=record.response_json,
                )
            )
        self._session.flush()
        return self.get_idempotency_by_key(record.owner_id, record.idempotency_key)

    def get_idempotency_by_key(self, owner_id, key):
        r = self._session.scalars(
            owner_scoped_select(LearningContentIdempotencyRow, owner_id)
            .where(LearningContentIdempotencyRow.idempotency_key == key)
            .limit(1)
        ).first()
        body = self._session.get(LearningContentIdempotencyBodyRow, r.id) if r else None
        return _idempotency(r, body) if r and body else None

    def add_conversation_turn(self, turn):
        values = turn.__dict__.copy()
        body = values.pop("body")
        values["role"] = turn.role.value
        values["body_hash"] = hash_payload(body)
        self._session.add(TopicConversationTurnRow(**values))
        self._session.flush()
        self._session.add(
            TopicConversationTurnBodyRow(
                turn_id=turn.id,
                owner_id=turn.owner_id,
                goal_id=turn.goal_id,
                body=body,
            )
        )
        self._session.flush()
        return turn

    def get_conversation_turn(self, owner_id, turn_id):
        row = self._session.scalars(
            owner_scoped_select(TopicConversationTurnRow, owner_id).where(
                TopicConversationTurnRow.id == turn_id
            )
        ).one_or_none()
        return self._conversation_turn(row) if row else None

    def get_conversation_turn_by_idempotency(self, owner_id, key):
        row = self._session.scalars(
            owner_scoped_select(TopicConversationTurnRow, owner_id).where(
                TopicConversationTurnRow.idempotency_key == key
            )
        ).one_or_none()
        return self._conversation_turn(row) if row else None

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
        return tuple(
            value for row in rows if (value := self._conversation_turn(row)) is not None
        )

    def _artifact(self, row):
        body = self._session.get(GeneratedArtifactBodyRow, row.id)
        return _artifact(row, body)

    def _conversation_turn(self, row):
        body = self._session.get(TopicConversationTurnBodyRow, row.id)
        return _conversation_turn(row, body.body) if body is not None else None


def _artifact(r, stored_body):
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
        stored_body.body_ref.removeprefix("inline:")
        if stored_body and stored_body.body_ref.startswith("inline:")
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


def _idempotency(r, body):
    return GenerationIdempotencyRecord(
        r.id,
        r.owner_id,
        r.operation,
        r.idempotency_key,
        r.request_hash,
        r.attempt_id,
        r.job_id,
        body.response_json,
        r.created_at,
    )


def _conversation_turn(r, body):
    return TopicConversationTurn(
        r.id,
        r.owner_id,
        r.goal_id,
        r.graph_version_id,
        r.topic_stable_id,
        ConversationRole(r.role),
        body,
        r.response_to_id,
        r.job_id,
        r.idempotency_key,
        r.request_hash,
        r.created_at,
    )
