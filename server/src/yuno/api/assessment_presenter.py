"""Shared API presentation for immutable assessment records."""

from yuno.api.contracts import (
    AssessmentDimensionResponse,
    AssessmentDisputeDetailResponse,
    AssessmentResponse,
    ReevaluationRequestResponse,
)
from yuno.modules.evidence_evaluation.ports import EvidenceUnitOfWork


def assessment_response(
    uow: EvidenceUnitOfWork, owner_id: str, assessment
) -> AssessmentResponse:
    rubric_dimensions = {
        item.id: item.stable_dimension_id
        for item in uow.evidence.list_rubric_dimensions(
            owner_id, assessment.rubric_id
        )
    }
    dimensions = [
        AssessmentDimensionResponse(
            dimension_id=rubric_dimensions[item.rubric_dimension_id],
            outcome=item.outcome,
            rationale=item.rationale,
            evidence_refs=list(item.evidence_refs),
        )
        for item in uow.evidence.list_assessment_dimensions(
            owner_id, assessment.id
        )
    ]
    values = {
        key: value
        for key, value in assessment.__dict__.items()
        if key != "owner_id"
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
        values[field] = list(values[field])
    disputes = []
    for dispute in uow.evidence.list_disputes(owner_id, assessment.id):
        reevaluation = uow.evidence.get_reevaluation_for_dispute(
            owner_id, dispute.id
        )
        disputes.append(
            AssessmentDisputeDetailResponse(
                id=dispute.id,
                reason=dispute.reason,
                status=dispute.status,
                requested_at=dispute.requested_at,
                resolved_at=dispute.resolved_at,
                resolution_note=dispute.resolution_note,
                reevaluation=(
                    ReevaluationRequestResponse(
                        **{
                            key: value
                            for key, value in reevaluation.__dict__.items()
                            if key
                            not in {
                                "owner_id",
                                "goal_id",
                                "prior_assessment_id",
                            }
                        }
                    )
                    if reevaluation
                    else None
                ),
            )
        )
    return AssessmentResponse(
        **values, dimensions=dimensions, disputes=disputes
    )
