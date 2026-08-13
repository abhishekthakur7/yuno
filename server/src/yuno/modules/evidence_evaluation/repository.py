"""SQLAlchemy evidence repository."""

from __future__ import annotations

import json
from collections.abc import Sequence

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from yuno.modules.data_lifecycle.models import EvidenceEvaluationIdempotencyBodyRow
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
    AssessmentBodyRow,
    AssessmentDimensionResultBodyRow,
    AssessmentDimensionResultRow,
    AssessmentDisputeBodyRow,
    AssessmentDisputeRow,
    AssessmentRow,
    EvidenceDeleteSnapshotRow,
    EvidenceEvaluationIdempotencyRow,
    EvidencePayloadRow,
    EvidenceRow,
    EvidenceSummaryBodyRow,
    EvidenceTombstoneRow,
    GoalProgressMemoBodyRow,
    GoalProgressMemoRow,
    ReevaluationRequestRow,
    RubricBodyRow,
    RubricDimensionBodyRow,
    RubricDimensionRow,
    RubricRow,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.infrastructure.repository import (
    SqlAlchemyRepository,
    owner_scoped_select,
)


class SqlAlchemyEvidenceRepository(SqlAlchemyRepository):
    def count_live_evidence(self, owner_id: str) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(EvidencePayloadRow)
                .where(EvidencePayloadRow.owner_id == owner_id)
            )
            or 0
        )

    def add_evidence(self, evidence: Evidence, payload: EvidencePayload) -> Evidence:
        values = evidence.__dict__.copy()
        summary = values.pop("summary")
        values["summary_hash"] = hash_payload(summary)
        self._session.add(EvidenceRow(**values))
        self._session.add(
            EvidenceSummaryBodyRow(
                evidence_id=evidence.id,
                owner_id=evidence.owner_id,
                goal_id=evidence.goal_id,
                summary=summary,
            )
        )
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
        return self._evidence(row) if row else None

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
            owner_scoped_select(EvidenceRow, owner_id).where(
                EvidenceRow.id == evidence_id
            )
        ).one_or_none()
        return self._evidence(row) if row else None

    def list_evidence(self, owner_id: str, goal_id: str) -> Sequence[Evidence]:
        rows = self._session.scalars(
            owner_scoped_select(EvidenceRow, owner_id)
            .where(EvidenceRow.goal_id == goal_id)
            .order_by(EvidenceRow.created_at, EvidenceRow.id)
        ).all()
        return tuple(self._evidence(row) for row in rows)

    def add_tombstone(self, tombstone: EvidenceTombstone) -> None:
        self._session.add(EvidenceTombstoneRow(**tombstone.__dict__))
        self._session.flush()

    def _evidence(self, row: EvidenceRow) -> Evidence:
        body = self._session.get(EvidenceSummaryBodyRow, row.id)
        return Evidence(
            row.id,
            row.owner_id,
            row.goal_id,
            row.topic_stable_id,
            row.evidence_type,
            row.capability,
            row.payload_hash,
            body.summary if body else "",
            row.origin,
            row.created_at,
        )

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
        body = {
            "task_context": values.pop("task_context"),
            "role_context": values.pop("role"),
            "level_context": values.pop("level"),
            "provenance": values.pop("provenance"),
        }
        values.update(
            status=rubric.status.value,
            body_hash=hash_payload(body),
        )
        self._session.add(RubricRow(**values))
        self._session.flush()
        self._session.add(
            RubricBodyRow(rubric_id=rubric.id, owner_id=rubric.owner_id, **body)
        )
        self._session.flush()
        for dimension in dimensions:
            dimension_values = dimension.__dict__.copy()
            dimension_body = {
                key: dimension_values.pop(key)
                for key in ("name", "description", "evaluation_guidance")
            }
            self._session.add(
                RubricDimensionRow(
                    owner_id=rubric.owner_id,
                    body_hash=hash_payload(dimension_body),
                    **dimension_values,
                )
            )
            self._session.flush()
            self._session.add(
                RubricDimensionBodyRow(
                    dimension_id=dimension.id,
                    owner_id=rubric.owner_id,
                    **dimension_body,
                )
            )
        self._session.flush()
        return rubric

    def get_rubric(self, owner_id: str, rubric_id: str) -> Rubric | None:
        row = self._session.scalars(
            owner_scoped_select(RubricRow, owner_id).where(RubricRow.id == rubric_id)
        ).one_or_none()
        return _rubric(row, self._session.get(RubricBodyRow, row.id)) if row else None

    def list_rubrics(self, owner_id: str):
        rows = self._session.scalars(
            owner_scoped_select(RubricRow, owner_id).order_by(RubricRow.created_at)
        ).all()
        return tuple(
            rubric
            for row in rows
            if (rubric := _rubric(row, self._session.get(RubricBodyRow, row.id)))
            is not None
        )

    def list_rubric_dimensions(
        self, owner_id: str, rubric_id: str
    ) -> Sequence[RubricDimension]:
        rows = self._session.scalars(
            owner_scoped_select(RubricDimensionRow, owner_id)
            .where(RubricDimensionRow.rubric_id == rubric_id)
            .order_by(RubricDimensionRow.ordinal)
        ).all()
        return tuple(
            dimension
            for row in rows
            if (
                dimension := _rubric_dimension(
                    row, self._session.get(RubricDimensionBodyRow, row.id)
                )
            )
            is not None
        )

    def add_assessment(
        self,
        assessment: Assessment,
        dimensions: Sequence[AssessmentDimensionResult],
    ) -> Assessment:
        values = assessment.__dict__.copy()
        values.update(
            state=assessment.state.value,
            derivation_excluded=int(assessment.derivation_excluded),
        )
        body = {
            "task_ref": values.pop("task_ref"),
            "role_context": values.pop("role"),
            "level_context": values.pop("level"),
        }
        for field in (
            "assumptions",
            "source_refs",
            "provenance_refs",
            "facts",
            "trade_offs",
            "citations",
            "ambiguities",
            "warnings",
            "limitation_labels",
        ):
            body[f"{field}_json"] = _json(values.pop(field))
        for field in (
            "feedback",
            "cross_question_candidate",
            "revision_invitation",
        ):
            body[field] = values.pop(field)
        values["body_hash"] = hash_payload(body)
        self._session.add(AssessmentRow(**values))
        self._session.flush()
        self._session.add(
            AssessmentBodyRow(
                assessment_id=assessment.id,
                owner_id=assessment.owner_id,
                goal_id=assessment.goal_id,
                **body,
            )
        )
        self._session.flush()
        for dimension in dimensions:
            values = dimension.__dict__.copy()
            values["outcome"] = dimension.outcome.value
            body = {
                "rationale": values.pop("rationale"),
                "evidence_refs_json": _json(values.pop("evidence_refs")),
            }
            values["body_hash"] = hash_payload(body)
            self._session.add(AssessmentDimensionResultRow(**values))
            self._session.flush()
            self._session.add(
                AssessmentDimensionResultBodyRow(
                    result_id=dimension.id,
                    owner_id=dimension.owner_id,
                    goal_id=dimension.goal_id,
                    **body,
                )
            )
        self._session.flush()
        return assessment

    def get_assessment(self, owner_id: str, assessment_id: str) -> Assessment | None:
        row = self._session.scalars(
            owner_scoped_select(AssessmentRow, owner_id).where(
                AssessmentRow.id == assessment_id
            )
        ).one_or_none()
        return (
            _assessment(row, self._session.get(AssessmentBodyRow, row.id))
            if row
            else None
        )

    def get_active_assessment_for_evidence(
        self, owner_id: str, evidence_id: str
    ) -> Assessment | None:
        row = self._session.scalars(
            owner_scoped_select(AssessmentRow, owner_id).where(
                AssessmentRow.evidence_id == evidence_id,
                AssessmentRow.derivation_excluded == 0,
            )
        ).one_or_none()
        return (
            _assessment(row, self._session.get(AssessmentBodyRow, row.id))
            if row
            else None
        )

    def list_assessment_dimensions(
        self, owner_id: str, assessment_id: str
    ) -> Sequence[AssessmentDimensionResult]:
        rows = self._session.scalars(
            owner_scoped_select(AssessmentDimensionResultRow, owner_id)
            .where(AssessmentDimensionResultRow.assessment_id == assessment_id)
            .order_by(AssessmentDimensionResultRow.rubric_dimension_id)
        ).all()
        return tuple(
            dimension
            for row in rows
            if (
                dimension := _assessment_dimension(
                    row,
                    self._session.get(AssessmentDimensionResultBodyRow, row.id),
                )
            )
            is not None
        )

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
        body = {
            "reason": values.pop("reason"),
            "resolution_note": values.pop("resolution_note"),
        }
        values["body_hash"] = hash_payload(body)
        self._session.add(AssessmentDisputeRow(**values))
        self._session.flush()
        self._session.add(
            AssessmentDisputeBodyRow(
                dispute_id=dispute.id,
                owner_id=dispute.owner_id,
                goal_id=dispute.goal_id,
                **body,
            )
        )
        self._session.flush()
        return dispute

    def get_dispute(self, owner_id: str, dispute_id: str) -> AssessmentDispute | None:
        row = self._session.scalars(
            owner_scoped_select(AssessmentDisputeRow, owner_id).where(
                AssessmentDisputeRow.id == dispute_id
            )
        ).one_or_none()
        return (
            _dispute(row, self._session.get(AssessmentDisputeBodyRow, row.id))
            if row
            else None
        )

    def list_disputes(
        self, owner_id: str, assessment_id: str
    ) -> Sequence[AssessmentDispute]:
        rows = self._session.scalars(
            owner_scoped_select(AssessmentDisputeRow, owner_id)
            .where(AssessmentDisputeRow.assessment_id == assessment_id)
            .order_by(AssessmentDisputeRow.requested_at, AssessmentDisputeRow.id)
        ).all()
        return tuple(
            dispute
            for row in rows
            if (
                dispute := _dispute(
                    row, self._session.get(AssessmentDisputeBodyRow, row.id)
                )
            )
            is not None
        )

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
        values = record.__dict__.copy()
        response_json = values.pop("response_json")
        values["response_hash"] = hash_payload(response_json)
        self._session.add(EvidenceEvaluationIdempotencyRow(**values))
        self._session.flush()
        self._session.add(
            EvidenceEvaluationIdempotencyBodyRow(
                idempotency_id=record.id,
                owner_id=record.owner_id,
                response_json=response_json,
            )
        )
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
        body = self._session.get(EvidenceEvaluationIdempotencyBodyRow, row.id)
        if body is None:
            return None
        return EvidenceEvaluationIdempotencyRecord(
            row.id,
            row.owner_id,
            row.operation,
            row.idempotency_key,
            row.request_hash,
            body.response_json,
            row.created_at,
            row.request_ref,
            bool(row.completed),
        )

    def complete_idempotency(
        self, owner_id: str, operation: str, key: str, response_json: str
    ) -> None:
        row = self._session.scalars(
            owner_scoped_select(EvidenceEvaluationIdempotencyRow, owner_id).where(
                EvidenceEvaluationIdempotencyRow.operation == operation,
                EvidenceEvaluationIdempotencyRow.idempotency_key == key,
                EvidenceEvaluationIdempotencyRow.completed == 0,
            )
        ).one_or_none()
        if row is None:
            raise RuntimeError("The idempotency reservation was not found.")
        result = self._session.execute(
            update(EvidenceEvaluationIdempotencyRow)
            .where(
                EvidenceEvaluationIdempotencyRow.owner_id == owner_id,
                EvidenceEvaluationIdempotencyRow.operation == operation,
                EvidenceEvaluationIdempotencyRow.idempotency_key == key,
                EvidenceEvaluationIdempotencyRow.completed == 0,
            )
            .values(response_hash=hash_payload(response_json), completed=1)
        )
        if result.rowcount != 1:
            raise RuntimeError("The idempotency reservation was not found.")
        self._session.execute(
            update(EvidenceEvaluationIdempotencyBodyRow)
            .where(EvidenceEvaluationIdempotencyBodyRow.idempotency_id == row.id)
            .values(response_json=response_json)
        )
        self._session.flush()

    def list_pending_idempotency(
        self, operation_prefix: str
    ) -> Sequence[EvidenceEvaluationIdempotencyRecord]:
        rows = self._session.scalars(
            select(EvidenceEvaluationIdempotencyRow)
            .where(
                EvidenceEvaluationIdempotencyRow.operation.startswith(operation_prefix),
                EvidenceEvaluationIdempotencyRow.completed == 0,
            )
            .order_by(EvidenceEvaluationIdempotencyRow.created_at)
        ).all()
        records: list[EvidenceEvaluationIdempotencyRecord] = []
        for row in rows:
            body = self._session.get(EvidenceEvaluationIdempotencyBodyRow, row.id)
            if body is None:
                continue
            records.append(
                EvidenceEvaluationIdempotencyRecord(
                    row.id,
                    row.owner_id,
                    row.operation,
                    row.idempotency_key,
                    row.request_hash,
                    body.response_json,
                    row.created_at,
                    row.request_ref,
                    bool(row.completed),
                )
            )
        return tuple(records)

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

    def get_progress_memo(self, owner_id: str, goal_id: str) -> GoalProgressMemo | None:
        row = self._session.scalars(
            owner_scoped_select(GoalProgressMemoRow, owner_id).where(
                GoalProgressMemoRow.goal_id == goal_id
            )
        ).one_or_none()
        return (
            _progress_memo(row, self._session.get(GoalProgressMemoBodyRow, row.goal_id))
            if row
            else None
        )

    def put_progress_memo(self, memo: GoalProgressMemo) -> None:
        values = memo.__dict__.copy()
        body = {
            key: values.pop(key)
            for key in (
                "coverage",
                "proficiency",
                "retention",
                "readiness",
                "explanation_json",
            )
        }
        for field in ("coverage", "proficiency", "retention", "readiness"):
            body[field] = body[field].value
        values["body_hash"] = hash_payload(body)
        statement = sqlite_insert(GoalProgressMemoRow).values(**values)
        self._session.execute(
            statement.on_conflict_do_update(
                index_elements=[GoalProgressMemoRow.goal_id],
                set_={key: value for key, value in values.items() if key != "goal_id"},
            )
        )
        self._session.flush()
        body_statement = sqlite_insert(GoalProgressMemoBodyRow).values(
            goal_id=memo.goal_id, owner_id=memo.owner_id, **body
        )
        self._session.execute(
            body_statement.on_conflict_do_update(
                index_elements=[GoalProgressMemoBodyRow.goal_id], set_=body
            )
        )
        self._session.flush()


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


def _progress_memo(
    row: GoalProgressMemoRow, body: GoalProgressMemoBodyRow | None
) -> GoalProgressMemo | None:
    if body is None:
        return None
    return GoalProgressMemo(
        row.goal_id,
        row.owner_id,
        ProgressClassification(body.coverage),
        ProgressClassification(body.proficiency),
        ProgressClassification(body.retention),
        ProgressClassification(body.readiness),
        body.explanation_json,
        row.input_hash,
        row.derivation_version,
        row.computed_at,
    )


def _tuple(value: str) -> tuple[str, ...]:
    return tuple(json.loads(value))


def _rubric(row: RubricRow, body: RubricBodyRow | None) -> Rubric | None:
    if body is None:
        return None
    return Rubric(
        row.id,
        row.owner_id,
        body.task_context,
        row.capability,
        body.role_context,
        body.level_context,
        row.version,
        RubricStatus(row.status),
        body.provenance,
        row.created_at,
    )


def _rubric_dimension(
    row: RubricDimensionRow, body: RubricDimensionBodyRow | None
) -> RubricDimension | None:
    if body is None:
        return None
    return RubricDimension(
        row.id,
        row.rubric_id,
        row.stable_dimension_id,
        body.name,
        body.description,
        row.ordinal,
        body.evaluation_guidance,
    )


def _assessment(
    row: AssessmentRow, body: AssessmentBodyRow | None
) -> Assessment | None:
    if body is None:
        return None
    return Assessment(
        row.id,
        row.owner_id,
        row.goal_id,
        row.evidence_id,
        row.run_id,
        row.rubric_id,
        row.rubric_version,
        AssessmentState(row.state),
        body.task_ref,
        row.requested_capability,
        body.role_context,
        body.level_context,
        row.evaluation_method,
        _tuple(body.assumptions_json),
        _tuple(body.source_refs_json),
        _tuple(body.provenance_refs_json),
        _tuple(body.facts_json),
        _tuple(body.trade_offs_json),
        _tuple(body.citations_json),
        _tuple(body.ambiguities_json),
        body.feedback,
        body.cross_question_candidate,
        body.revision_invitation,
        _tuple(body.warnings_json),
        _tuple(body.limitation_labels_json),
        row.predecessor_assessment_id,
        bool(row.derivation_excluded),
        row.created_at,
    )


def _assessment_dimension(
    row: AssessmentDimensionResultRow,
    body: AssessmentDimensionResultBodyRow | None,
) -> AssessmentDimensionResult | None:
    if body is None:
        return None
    return AssessmentDimensionResult(
        row.id,
        row.owner_id,
        row.goal_id,
        row.assessment_id,
        row.rubric_dimension_id,
        DimensionOutcome(row.outcome),
        body.rationale,
        _tuple(body.evidence_refs_json),
    )


def _dispute(
    row: AssessmentDisputeRow, body: AssessmentDisputeBodyRow | None
) -> AssessmentDispute | None:
    if body is None:
        return None
    return AssessmentDispute(
        row.id,
        row.owner_id,
        row.goal_id,
        row.assessment_id,
        body.reason,
        DisputeStatus(row.status),
        row.requested_at,
        row.resolved_at,
        body.resolution_note,
    )


def _reevaluation(row: ReevaluationRequestRow) -> ReevaluationRequest:
    return ReevaluationRequest(
        row.id,
        row.owner_id,
        row.goal_id,
        row.dispute_id,
        row.prior_assessment_id,
        row.job_id,
        ReevaluationStatus(row.status),
        row.resulting_assessment_id,
        row.requested_at,
        row.completed_at,
        row.failure_reference,
    )
