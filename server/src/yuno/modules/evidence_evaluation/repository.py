"""SQLAlchemy evidence repository."""

from __future__ import annotations

import json
from collections.abc import Sequence

from sqlalchemy import delete, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from yuno.modules.evidence_evaluation.domain import (
    Assessment,
    AssessmentDimensionResult,
    AssessmentDispute,
    AssessmentState,
    DimensionOutcome,
    DisputeStatus,
    Evidence,
    EvidenceDeleteSnapshot,
    EvidenceEvaluationIdempotencyRecord,
    EvidencePayload,
    EvidenceTombstone,
    GoalProgressMemo,
    ProgressClassification,
    ProgressEvidence,
    ReevaluationRequest,
    ReevaluationStatus,
    Rubric,
    RubricDimension,
    RubricStatus,
)
from yuno.modules.evidence_evaluation.models import (
    AssessmentDimensionResultRow,
    AssessmentDisputeRow,
    AssessmentRow,
    EvidenceDeleteSnapshotRow,
    EvidenceEvaluationIdempotencyRow,
    EvidencePayloadRow,
    EvidenceRow,
    EvidenceTombstoneRow,
    GoalProgressMemoRow,
    ReevaluationRequestRow,
    RubricDimensionRow,
    RubricRow,
)
from yuno.shared.infrastructure.repository import (
    SqlAlchemyRepository,
    owner_scoped_select,
)


class SqlAlchemyEvidenceRepository(SqlAlchemyRepository):
    def add_evidence(self, evidence: Evidence, payload: EvidencePayload) -> Evidence:
        self._session.add(EvidenceRow(**evidence.__dict__))
        self._session.flush()
        self._session.add(EvidencePayloadRow(**payload.__dict__))
        self._session.flush()
        return evidence

    def get_evidence(
        self, owner_id: str, goal_id: str, evidence_id: str
    ) -> Evidence | None:
        row = self._session.scalars(
            owner_scoped_select(EvidenceRow, owner_id).where(
                EvidenceRow.goal_id == goal_id, EvidenceRow.id == evidence_id
            )
        ).one_or_none()
        return _evidence(row) if row else None

    def get_payload(
        self, owner_id: str, goal_id: str, evidence_id: str
    ) -> EvidencePayload | None:
        row = self._session.scalars(
            owner_scoped_select(EvidencePayloadRow, owner_id).where(
                EvidencePayloadRow.goal_id == goal_id,
                EvidencePayloadRow.evidence_id == evidence_id,
            )
        ).one_or_none()
        return _payload(row) if row else None

    def get_evidence_by_id(self, owner_id: str, evidence_id: str) -> Evidence | None:
        row = self._session.scalars(
            owner_scoped_select(EvidenceRow, owner_id).where(EvidenceRow.id == evidence_id)
        ).one_or_none()
        return _evidence(row) if row else None

    def list_evidence(self, owner_id: str, goal_id: str) -> Sequence[Evidence]:
        rows = self._session.scalars(
            owner_scoped_select(EvidenceRow, owner_id)
            .where(EvidenceRow.goal_id == goal_id)
            .order_by(EvidenceRow.id)
        ).all()
        return tuple(_evidence(row) for row in rows)

    def add_tombstone(self, tombstone: EvidenceTombstone) -> None:
        self._session.add(EvidenceTombstoneRow(**tombstone.__dict__))
        self._session.flush()

    def remove_payload(self, owner_id: str, goal_id: str, evidence_id: str) -> None:
        self._session.execute(
            delete(EvidencePayloadRow).where(
                EvidencePayloadRow.owner_id == owner_id,
                EvidencePayloadRow.goal_id == goal_id,
                EvidencePayloadRow.evidence_id == evidence_id,
            )
        )
        self._session.flush()

    def list_tombstones(
        self, owner_id: str, goal_id: str
    ) -> Sequence[EvidenceTombstone]:
        rows = self._session.scalars(
            owner_scoped_select(EvidenceTombstoneRow, owner_id)
            .where(EvidenceTombstoneRow.goal_id == goal_id)
            .order_by(EvidenceTombstoneRow.evidence_id)
        ).all()
        return tuple(_tombstone(row) for row in rows)

    def add_delete_snapshot(self, snapshot: EvidenceDeleteSnapshot) -> None:
        self._session.add(EvidenceDeleteSnapshotRow(**snapshot.__dict__))
        self._session.flush()

    def get_delete_snapshot(
        self, owner_id: str, goal_id: str, snapshot_id: str
    ) -> EvidenceDeleteSnapshot | None:
        row = self._session.scalars(
            owner_scoped_select(EvidenceDeleteSnapshotRow, owner_id).where(
                EvidenceDeleteSnapshotRow.goal_id == goal_id,
                EvidenceDeleteSnapshotRow.id == snapshot_id,
            )
        ).one_or_none()
        if row is None:
            return None
        return EvidenceDeleteSnapshot(
            row.id,
            row.owner_id,
            row.goal_id,
            row.impact_json,
            row.impact_hash,
            row.created_at,
        )

    def add_rubric(
        self, rubric: Rubric, dimensions: Sequence[RubricDimension]
    ) -> Rubric:
        values = rubric.__dict__.copy()
        values.update(status=rubric.status.value, role_context=values.pop("role"), level_context=values.pop("level"))
        self._session.add(RubricRow(**values))
        self._session.flush()
        for dimension in dimensions:
            self._session.add(
                RubricDimensionRow(owner_id=rubric.owner_id, **dimension.__dict__)
            )
        self._session.flush()
        return rubric

    def get_rubric(self, owner_id: str, rubric_id: str) -> Rubric | None:
        row = self._session.scalars(
            owner_scoped_select(RubricRow, owner_id).where(RubricRow.id == rubric_id)
        ).one_or_none()
        return _rubric(row) if row else None

    def list_rubric_dimensions(
        self, owner_id: str, rubric_id: str
    ) -> Sequence[RubricDimension]:
        rows = self._session.scalars(
            owner_scoped_select(RubricDimensionRow, owner_id)
            .where(RubricDimensionRow.rubric_id == rubric_id)
            .order_by(RubricDimensionRow.ordinal)
        ).all()
        return tuple(_rubric_dimension(row) for row in rows)

    def add_assessment(
        self,
        assessment: Assessment,
        dimensions: Sequence[AssessmentDimensionResult],
    ) -> Assessment:
        values = assessment.__dict__.copy()
        values.update(
            state=assessment.state.value,
            derivation_excluded=int(assessment.derivation_excluded),
            role_context=values.pop("role"),
            level_context=values.pop("level"),
        )
        for field in (
            "assumptions", "source_refs", "provenance_refs", "facts", "trade_offs",
            "citations", "ambiguities", "warnings", "limitation_labels",
        ):
            values[f"{field}_json"] = _json(values.pop(field))
        self._session.add(AssessmentRow(**values))
        self._session.flush()
        for dimension in dimensions:
            values = dimension.__dict__.copy()
            values["outcome"] = dimension.outcome.value
            values["evidence_refs_json"] = _json(values.pop("evidence_refs"))
            self._session.add(AssessmentDimensionResultRow(**values))
        self._session.flush()
        return assessment

    def get_assessment(self, owner_id: str, assessment_id: str) -> Assessment | None:
        row = self._session.scalars(
            owner_scoped_select(AssessmentRow, owner_id).where(AssessmentRow.id == assessment_id)
        ).one_or_none()
        return _assessment(row) if row else None

    def get_active_assessment_for_evidence(
        self, owner_id: str, evidence_id: str
    ) -> Assessment | None:
        row = self._session.scalars(
            owner_scoped_select(AssessmentRow, owner_id).where(
                AssessmentRow.evidence_id == evidence_id,
                AssessmentRow.derivation_excluded == 0,
            )
        ).one_or_none()
        return _assessment(row) if row else None

    def list_assessment_dimensions(
        self, owner_id: str, assessment_id: str
    ) -> Sequence[AssessmentDimensionResult]:
        rows = self._session.scalars(
            owner_scoped_select(AssessmentDimensionResultRow, owner_id)
            .where(AssessmentDimensionResultRow.assessment_id == assessment_id)
            .order_by(AssessmentDimensionResultRow.rubric_dimension_id)
        ).all()
        return tuple(_assessment_dimension(row) for row in rows)

    def exclude_assessment(
        self, owner_id: str, goal_id: str, assessment_id: str
    ) -> None:
        result = self._session.execute(
            update(AssessmentRow)
            .where(
                AssessmentRow.owner_id == owner_id,
                AssessmentRow.goal_id == goal_id,
                AssessmentRow.id == assessment_id,
                AssessmentRow.derivation_excluded == 0,
            )
            .values(derivation_excluded=1)
        )
        if result.rowcount != 1:
            raise RuntimeError("The predecessor assessment was not active.")
        self._session.flush()

    def add_dispute(self, dispute: AssessmentDispute) -> AssessmentDispute:
        values = dispute.__dict__.copy()
        values["status"] = dispute.status.value
        self._session.add(AssessmentDisputeRow(**values))
        self._session.flush()
        return dispute

    def get_dispute(self, owner_id: str, dispute_id: str) -> AssessmentDispute | None:
        row = self._session.scalars(
            owner_scoped_select(AssessmentDisputeRow, owner_id).where(
                AssessmentDisputeRow.id == dispute_id
            )
        ).one_or_none()
        return _dispute(row) if row else None

    def add_reevaluation_request(
        self, request: ReevaluationRequest
    ) -> ReevaluationRequest:
        values = request.__dict__.copy()
        values["status"] = request.status.value
        self._session.add(ReevaluationRequestRow(**values))
        self._session.flush()
        return request

    def get_reevaluation_for_dispute(
        self, owner_id: str, dispute_id: str
    ) -> ReevaluationRequest | None:
        row = self._session.scalars(
            owner_scoped_select(ReevaluationRequestRow, owner_id).where(
                ReevaluationRequestRow.dispute_id == dispute_id
            )
        ).one_or_none()
        return _reevaluation(row) if row else None

    def get_reevaluation_request(
        self, owner_id: str, request_id: str
    ) -> ReevaluationRequest | None:
        row = self._session.scalars(
            owner_scoped_select(ReevaluationRequestRow, owner_id).where(
                ReevaluationRequestRow.id == request_id
            )
        ).one_or_none()
        return _reevaluation(row) if row else None

    def update_reevaluation_request(
        self, owner_id: str, request_id: str, changes: dict[str, object]
    ) -> None:
        values = {
            key: value.value if isinstance(value, ReevaluationStatus) else value
            for key, value in changes.items()
        }
        result = self._session.execute(
            update(ReevaluationRequestRow)
            .where(
                ReevaluationRequestRow.owner_id == owner_id,
                ReevaluationRequestRow.id == request_id,
            )
            .values(**values)
        )
        if result.rowcount != 1:
            raise RuntimeError("The re-evaluation request was not found.")
        self._session.flush()

    def add_idempotency(self, record: EvidenceEvaluationIdempotencyRecord) -> None:
        self._session.add(EvidenceEvaluationIdempotencyRow(**record.__dict__))
        self._session.flush()

    def get_idempotency(
        self, owner_id: str, operation: str, key: str
    ) -> EvidenceEvaluationIdempotencyRecord | None:
        row = self._session.scalars(
            owner_scoped_select(EvidenceEvaluationIdempotencyRow, owner_id).where(
                EvidenceEvaluationIdempotencyRow.operation == operation,
                EvidenceEvaluationIdempotencyRow.idempotency_key == key,
            )
        ).one_or_none()
        if row is None:
            return None
        return EvidenceEvaluationIdempotencyRecord(
            row.id, row.owner_id, row.operation, row.idempotency_key,
            row.request_hash, row.response_json, row.created_at,
            row.request_ref, bool(row.completed),
        )

    def complete_idempotency(
        self, owner_id: str, operation: str, key: str, response_json: str
    ) -> None:
        result = self._session.execute(
            update(EvidenceEvaluationIdempotencyRow)
            .where(
                EvidenceEvaluationIdempotencyRow.owner_id == owner_id,
                EvidenceEvaluationIdempotencyRow.operation == operation,
                EvidenceEvaluationIdempotencyRow.idempotency_key == key,
                EvidenceEvaluationIdempotencyRow.completed == 0,
            )
            .values(response_json=response_json, completed=1)
        )
        if result.rowcount != 1:
            raise RuntimeError("The idempotency reservation was not found.")
        self._session.flush()

    def list_progress_evidence(
        self, owner_id: str, goal_id: str
    ) -> Sequence[ProgressEvidence]:
        result = []
        for evidence in self.list_evidence(owner_id, goal_id):
            if self.get_payload(owner_id, goal_id, evidence.id) is None:
                continue
            assessment = self.get_active_assessment_for_evidence(owner_id, evidence.id)
            dimensions = (
                tuple(self.list_assessment_dimensions(owner_id, assessment.id))
                if assessment is not None
                else ()
            )
            result.append(ProgressEvidence(evidence, assessment, dimensions))
        return tuple(result)

    def get_progress_memo(
        self, owner_id: str, goal_id: str
    ) -> GoalProgressMemo | None:
        row = self._session.scalars(
            owner_scoped_select(GoalProgressMemoRow, owner_id).where(
                GoalProgressMemoRow.goal_id == goal_id
            )
        ).one_or_none()
        return _progress_memo(row) if row else None

    def put_progress_memo(self, memo: GoalProgressMemo) -> None:
        values = memo.__dict__.copy()
        for field in ("coverage", "proficiency", "retention", "readiness"):
            values[field] = values[field].value
        statement = sqlite_insert(GoalProgressMemoRow).values(**values)
        self._session.execute(
            statement.on_conflict_do_update(
                index_elements=[GoalProgressMemoRow.goal_id],
                set_={key: value for key, value in values.items() if key != "goal_id"},
            )
        )
        self._session.flush()


def _evidence(row: EvidenceRow) -> Evidence:
    return Evidence(
        row.id,
        row.owner_id,
        row.goal_id,
        row.topic_stable_id,
        row.evidence_type,
        row.capability,
        row.payload_hash,
        row.summary,
        row.origin,
        row.created_at,
    )


def _payload(row: EvidencePayloadRow) -> EvidencePayload:
    return EvidencePayload(
        row.evidence_id, row.owner_id, row.goal_id, row.content, row.content_version
    )


def _tombstone(row: EvidenceTombstoneRow) -> EvidenceTombstone:
    return EvidenceTombstone(
        row.evidence_id,
        row.owner_id,
        row.goal_id,
        row.delete_operation_id,
        row.reason,
        row.tombstoned_at,
    )


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _progress_memo(row: GoalProgressMemoRow) -> GoalProgressMemo:
    return GoalProgressMemo(
        row.goal_id,
        row.owner_id,
        ProgressClassification(row.coverage),
        ProgressClassification(row.proficiency),
        ProgressClassification(row.retention),
        ProgressClassification(row.readiness),
        row.explanation_json,
        row.input_hash,
        row.derivation_version,
        row.computed_at,
    )


def _tuple(value: str) -> tuple[str, ...]:
    return tuple(json.loads(value))


def _rubric(row: RubricRow) -> Rubric:
    return Rubric(row.id, row.owner_id, row.task_context, row.capability, row.role_context, row.level_context, row.version, RubricStatus(row.status), row.provenance, row.created_at)


def _rubric_dimension(row: RubricDimensionRow) -> RubricDimension:
    return RubricDimension(row.id, row.rubric_id, row.stable_dimension_id, row.name, row.description, row.ordinal, row.evaluation_guidance)


def _assessment(row: AssessmentRow) -> Assessment:
    return Assessment(
        row.id, row.owner_id, row.goal_id, row.evidence_id, row.run_id, row.rubric_id,
        row.rubric_version, AssessmentState(row.state), row.task_ref,
        row.requested_capability, row.role_context, row.level_context, row.evaluation_method,
        _tuple(row.assumptions_json), _tuple(row.source_refs_json),
        _tuple(row.provenance_refs_json), _tuple(row.facts_json),
        _tuple(row.trade_offs_json), _tuple(row.citations_json),
        _tuple(row.ambiguities_json), row.feedback, row.cross_question_candidate,
        row.revision_invitation, _tuple(row.warnings_json),
        _tuple(row.limitation_labels_json), row.predecessor_assessment_id,
        bool(row.derivation_excluded), row.created_at,
    )


def _assessment_dimension(row: AssessmentDimensionResultRow) -> AssessmentDimensionResult:
    return AssessmentDimensionResult(row.id, row.owner_id, row.goal_id, row.assessment_id, row.rubric_dimension_id, DimensionOutcome(row.outcome), row.rationale, _tuple(row.evidence_refs_json))


def _dispute(row: AssessmentDisputeRow) -> AssessmentDispute:
    return AssessmentDispute(row.id, row.owner_id, row.goal_id, row.assessment_id, row.reason, DisputeStatus(row.status), row.requested_at, row.resolved_at, row.resolution_note)


def _reevaluation(row: ReevaluationRequestRow) -> ReevaluationRequest:
    return ReevaluationRequest(row.id, row.owner_id, row.goal_id, row.dispute_id, row.prior_assessment_id, row.job_id, ReevaluationStatus(row.status), row.resulting_assessment_id, row.requested_at, row.completed_at, row.failure_reference)
