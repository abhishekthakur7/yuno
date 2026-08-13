"""Immutable evidence and evaluation domain contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from yuno.shared.domain.hashing import hash_payload


class TransferClassification(StrEnum):
    LIKELY_KNOWN = "likely-known"
    PARTIAL = "partial"
    UNVERIFIED = "unverified"
    NEW = "new"


class RubricStatus(StrEnum):
    FIXTURE = "fixture"
    APPROVED = "approved"
    RETIRED = "retired"


class AssessmentState(StrEnum):
    FEEDBACK_READY = "feedback-ready"
    AMBIGUITY_UNRESOLVED = "ambiguity-unresolved"


class DimensionOutcome(StrEnum):
    PASS = "pass"
    TRADE_OFF = "trade-off"
    FACTUAL_CORRECTION = "factual-correction"
    AMBIGUITY_UNRESOLVED = "ambiguity-unresolved"


class DisputeStatus(StrEnum):
    REQUESTED = "requested"


class ReevaluationStatus(StrEnum):
    REQUESTED = "requested"
    COMPLETED = "completed"
    FAILED = "failed"


class ProgressClassification(StrEnum):
    LIKELY_KNOWN = "likely-known"
    PARTIAL = "partial"
    UNVERIFIED = "unverified"
    NEW = "new"


FIXTURE_DERIVATION_VERSION = "fixture-v0"


@dataclass(frozen=True)
class ProgressEvidence:
    evidence: Evidence
    assessment: Assessment | None
    dimensions: tuple[AssessmentDimensionResult, ...]


@dataclass(frozen=True)
class ProgressCorrection:
    id: str
    owner_id: str
    goal_id: str
    topic_stable_id: str
    correction_type: str
    value: str
    reason: str | None
    created_at: str
    supersedes_correction_id: str | None


@dataclass(frozen=True)
class ProgressTransfer:
    id: str
    owner_id: str
    goal_id: str
    topic_stable_id: str
    source_evidence_id: str
    classification: ProgressClassification
    rationale: str
    created_at: str


@dataclass(frozen=True)
class LearningStateExplanation:
    topic_stable_id: str
    classification: ProgressClassification
    definition: str
    supporting_evidence_refs: tuple[str, ...]
    uncertainty: str
    correction_ref: str | None


@dataclass(frozen=True)
class ProgressDimension:
    classification: ProgressClassification
    definition: str
    supporting_evidence_refs: tuple[str, ...]
    uncertainty: str


@dataclass(frozen=True)
class DerivedProgress:
    coverage: ProgressDimension
    proficiency: ProgressDimension
    retention: ProgressDimension
    readiness: ProgressDimension
    learning_states: tuple[LearningStateExplanation, ...]
    input_hash: str
    rule_version: str
    effective_now: str


@dataclass(frozen=True)
class GoalProgressMemo:
    goal_id: str
    owner_id: str
    coverage: ProgressClassification
    proficiency: ProgressClassification
    retention: ProgressClassification
    readiness: ProgressClassification
    explanation_json: str
    input_hash: str
    derivation_version: str
    computed_at: str


_DEFINITIONS = {
    "coverage": "Whether fixture inputs exist across the topics represented by evidence or learner corrections.",
    "proficiency": "What active, non-ambiguous fixture assessment outcomes support; this is not an interview or job prediction.",
    "retention": "How recently the supporting fixture evidence was recorded, using fixture-only date bands.",
    "readiness": "The most uncertain supported fixture dimension after standing learner corrections are applied.",
}
_UNCERTAINTY = (
    "Fixture-only derivation pending approval of production rules under IDK-009."
)
_ORDER = {
    ProgressClassification.NEW: 0,
    ProgressClassification.UNVERIFIED: 1,
    ProgressClassification.PARTIAL: 2,
    ProgressClassification.LIKELY_KNOWN: 3,
}


def progress_input_hash(
    goal_id: str,
    topic_ids: tuple[str, ...],
    evidence: tuple[ProgressEvidence, ...],
    corrections: tuple[ProgressCorrection, ...],
    transfers: tuple[ProgressTransfer, ...],
    now: str,
    rule_version: str,
) -> str:
    """Canonical cache key covering every pure-function input."""

    return hash_payload(
        {
            "goal_id": goal_id,
            "topic_ids": sorted(topic_ids),
            "evidence": [
                {
                    "evidence": item.evidence,
                    "assessment": item.assessment,
                    "dimensions": sorted(item.dimensions, key=lambda value: value.id),
                }
                for item in sorted(evidence, key=lambda item: item.evidence.id)
            ],
            "corrections": sorted(corrections, key=lambda item: item.id),
            "transfers": sorted(transfers, key=lambda item: item.id),
            # fixture-v0 retention changes only at UTC date boundaries.
            "time_bucket": now[:10],
            "rule_version": rule_version,
        }
    )


def derive_progress(
    goal_id: str,
    topic_ids: tuple[str, ...],
    evidence: tuple[ProgressEvidence, ...],
    corrections: tuple[ProgressCorrection, ...],
    transfers: tuple[ProgressTransfer, ...],
    now: str,
    rule_version: str,
) -> DerivedProgress:
    """Pure fixture-v0 D6 derivation; no database, clock, or mutable state."""

    if rule_version != FIXTURE_DERIVATION_VERSION:
        raise ValueError("Only the fixture-v0 derivation is available pending IDK-009.")
    from datetime import date, datetime

    try:
        effective_now = datetime.fromisoformat(now)
    except ValueError as exc:
        raise ValueError("now must be a canonical UTC timestamp.") from exc
    if effective_now.tzinfo is None or not now.endswith("Z"):
        raise ValueError("now must be a canonical UTC timestamp.")
    if (
        len(topic_ids) != len(set(topic_ids))
        or not goal_id
        or any(not item for item in topic_ids)
    ):
        raise ValueError("The goal and canonical topic spine must be valid and unique.")
    topic_set = set(topic_ids)
    for item in evidence:
        if (
            item.evidence.goal_id != goal_id
            or item.evidence.topic_stable_id not in topic_set
        ):
            raise ValueError(
                "Evidence must belong to the requested goal and topic spine."
            )
        created = datetime.fromisoformat(item.evidence.created_at)
        if (
            created.tzinfo is None
            or not item.evidence.created_at.endswith("Z")
            or created > effective_now
        ):
            raise ValueError(
                "Evidence timestamps must be canonical UTC and no later than now."
            )
        if item.assessment is not None and (
            item.assessment.owner_id != item.evidence.owner_id
            or item.assessment.goal_id != goal_id
            or item.assessment.evidence_id != item.evidence.id
        ):
            raise ValueError("Assessments must match their evidence scope.")
        if any(
            dimension.owner_id != item.evidence.owner_id
            or dimension.goal_id != goal_id
            or (
                item.assessment is not None
                and dimension.assessment_id != item.assessment.id
            )
            for dimension in item.dimensions
        ):
            raise ValueError("Assessment dimensions must match their assessment scope.")
    owners = (
        {item.evidence.owner_id for item in evidence}
        | {item.owner_id for item in corrections}
        | {item.owner_id for item in transfers}
    )
    if len(owners) > 1:
        raise ValueError("Progress inputs must belong to one owner.")
    correction_by_id = {item.id: item for item in corrections}
    if len(correction_by_id) != len(corrections):
        raise ValueError("Correction ids must be unique.")
    children: dict[str, list[str]] = {}
    for item in corrections:
        if item.goal_id != goal_id or item.topic_stable_id not in topic_set:
            raise ValueError(
                "Corrections must belong to the requested goal and topic spine."
            )
        if item.supersedes_correction_id:
            predecessor = correction_by_id.get(item.supersedes_correction_id)
            if predecessor is None or (
                predecessor.owner_id,
                predecessor.goal_id,
                predecessor.topic_stable_id,
            ) != (item.owner_id, item.goal_id, item.topic_stable_id):
                raise ValueError(
                    "A correction may only supersede its same-scope predecessor."
                )
            children.setdefault(predecessor.id, []).append(item.id)
        if item.value not in ProgressClassification or item.correction_type not in {
            "correction",
            "confirmation",
            "gap",
            "transfer-confirmation",
        }:
            raise ValueError(
                "Correction type and value must use the closed vocabularies."
            )
        corrected = datetime.fromisoformat(item.created_at)
        if (
            corrected.tzinfo is None
            or not item.created_at.endswith("Z")
            or corrected > effective_now
        ):
            raise ValueError(
                "Correction timestamps must be canonical UTC and no later than now."
            )
    for item in transfers:
        if item.goal_id != goal_id or item.topic_stable_id not in topic_set:
            raise ValueError(
                "Transfers must belong to the requested goal and topic spine."
            )
        transferred = datetime.fromisoformat(item.created_at)
        if (
            transferred.tzinfo is None
            or not item.created_at.endswith("Z")
            or transferred > effective_now
        ):
            raise ValueError(
                "Transfer timestamps must be canonical UTC and no later than now."
            )
    if any(len(value) != 1 for value in children.values()):
        raise ValueError("Correction histories cannot branch.")
    for topic in topic_ids:
        topic_rows = [item for item in corrections if item.topic_stable_id == topic]
        leaves = [item for item in topic_rows if item.id not in children]
        roots = [item for item in topic_rows if item.supersedes_correction_id is None]
        if topic_rows and (len(leaves) != 1 or len(roots) != 1):
            raise ValueError("Correction histories must be one connected linear chain.")
        visited: set[str] = set()
        cursor = roots[0].id if roots else None
        while cursor is not None:
            visited.add(cursor)
            cursor = children.get(cursor, [None])[0]
        if len(visited) != len(topic_rows):
            raise ValueError("Correction histories must be one connected linear chain.")
    input_hash = progress_input_hash(
        goal_id, topic_ids, evidence, corrections, transfers, now, rule_version
    )
    by_topic: dict[str, list[ProgressEvidence]] = {}
    for item in sorted(evidence, key=lambda item: item.evidence.id):
        by_topic.setdefault(item.evidence.topic_stable_id, []).append(item)

    superseded = set(children)
    active_corrections = {
        item.topic_stable_id: item
        for item in sorted(corrections, key=lambda item: (item.created_at, item.id))
        if item.id not in superseded
    }
    transfers_by_topic: dict[str, list[ProgressTransfer]] = {}
    for item in transfers:
        transfers_by_topic.setdefault(item.topic_stable_id, []).append(item)
    topics = sorted(topic_ids)
    states: list[LearningStateExplanation] = []
    metric_states: list[ProgressClassification] = []
    metric_evidence_refs: list[str] = []
    for topic in topics:
        correction = active_corrections.get(topic)
        refs = tuple(sorted(item.evidence.id for item in by_topic.get(topic, ())))
        if correction is not None:
            classification = ProgressClassification(correction.value)
            states.append(
                LearningStateExplanation(
                    topic,
                    classification,
                    "Standing learner correction; inference cannot replace it until explicitly superseded.",
                    refs,
                    correction.reason or _UNCERTAINTY,
                    correction.id,
                )
            )
            metric_states.append(classification)
            metric_evidence_refs.extend(refs)
            continue
        topic_transfers = transfers_by_topic.get(topic, [])
        topic_evidence = by_topic.get(topic, [])
        outcomes = [
            dimension.outcome
            for item in topic_evidence
            if item.assessment is not None
            and item.assessment.state is not AssessmentState.AMBIGUITY_UNRESOLVED
            for dimension in item.dimensions
            if dimension.outcome is not DimensionOutcome.AMBIGUITY_UNRESOLVED
        ]
        ambiguity_only = bool(topic_evidence) and not outcomes
        transfer_classification = (
            min(
                (item.classification for item in topic_transfers),
                key=_ORDER.__getitem__,
            )
            if topic_transfers
            else None
        )
        if not topic_evidence and transfer_classification is not None:
            classification = transfer_classification
        elif not topic_evidence:
            classification = ProgressClassification.NEW
        elif not outcomes and transfer_classification is not None:
            classification = transfer_classification
        elif not outcomes:
            classification = ProgressClassification.UNVERIFIED
        elif DimensionOutcome.FACTUAL_CORRECTION in outcomes:
            classification = (
                ProgressClassification.PARTIAL
                if any(
                    value in (DimensionOutcome.PASS, DimensionOutcome.TRADE_OFF)
                    for value in outcomes
                )
                else ProgressClassification.UNVERIFIED
            )
        else:
            classification = ProgressClassification.LIKELY_KNOWN
        if outcomes and transfer_classification is not None:
            classification = min(
                (classification, transfer_classification), key=_ORDER.__getitem__
            )
        transfer_refs = tuple(
            sorted(item.source_evidence_id for item in topic_transfers)
        )
        refs = tuple(sorted(set(refs) | set(transfer_refs)))
        states.append(
            LearningStateExplanation(
                topic,
                classification,
                "Derived from active eligible fixture assessment outcomes and conservative transfer inputs.",
                refs,
                _UNCERTAINTY,
                None,
            )
        )
        metric_states.append(
            classification
            if ambiguity_only and transfer_classification is not None
            else ProgressClassification.NEW
            if ambiguity_only
            else classification
        )
        if not ambiguity_only:
            metric_evidence_refs.extend(refs)
        elif transfer_classification is not None:
            metric_evidence_refs.extend(transfer_refs)

    evidence_refs = tuple(sorted(set(metric_evidence_refs)))
    if not topics:
        coverage_value = proficiency_value = retention_value = readiness_value = (
            ProgressClassification.NEW
        )
    else:
        covered_topics = len(
            {
                item.evidence.topic_stable_id
                for item in evidence
                if item.evidence.id in evidence_refs
            }
            | set(active_corrections)
            | set(transfers_by_topic)
        )
        coverage_value = (
            ProgressClassification.NEW
            if covered_topics == 0
            else ProgressClassification.LIKELY_KNOWN
            if covered_topics == len(topics)
            else ProgressClassification.PARTIAL
        )
        proficiency_value = (
            min(metric_states, key=_ORDER.__getitem__)
            if metric_states
            else ProgressClassification.NEW
        )
        # Deliberately simple, explicitly non-production fixture bands. Corrections
        # remain authoritative and therefore are not decayed by evidence age.
        dated = [
            item.evidence.created_at[:10]
            for item in evidence
            if item.evidence.id in evidence_refs
        ] + [item.created_at[:10] for item in transfers]
        if not dated:
            retention_value = proficiency_value
        else:
            age = (
                date.fromisoformat(now[:10])
                - max(date.fromisoformat(value) for value in dated)
            ).days
            retention_value = (
                ProgressClassification.LIKELY_KNOWN
                if age <= 30
                else ProgressClassification.PARTIAL
                if age <= 90
                else ProgressClassification.UNVERIFIED
            )
        if active_corrections and not evidence_refs:
            retention_value = proficiency_value
        readiness_value = min(
            (coverage_value, proficiency_value, retention_value), key=_ORDER.__getitem__
        )

    def metric(name: str, value: ProgressClassification) -> ProgressDimension:
        return ProgressDimension(value, _DEFINITIONS[name], evidence_refs, _UNCERTAINTY)

    return DerivedProgress(
        metric("coverage", coverage_value),
        metric("proficiency", proficiency_value),
        metric("retention", retention_value),
        metric("readiness", readiness_value),
        tuple(states),
        input_hash,
        rule_version,
        now,
    )


@dataclass(frozen=True)
class Evidence:
    id: str
    owner_id: str
    goal_id: str
    topic_stable_id: str
    evidence_type: str
    capability: str
    payload_hash: str
    summary: str
    origin: str
    created_at: str


@dataclass(frozen=True)
class EvidencePayload:
    evidence_id: str
    owner_id: str
    goal_id: str
    content: str
    content_version: str


@dataclass(frozen=True)
class TransferredEvidenceRef:
    id: str
    owner_id: str
    goal_id: str
    learning_state_id: str
    source_goal_id: str
    source_evidence_id: str
    classification: TransferClassification
    rationale: str
    created_at: str


@dataclass(frozen=True)
class EvidenceTombstone:
    evidence_id: str
    owner_id: str
    goal_id: str
    delete_operation_id: str
    reason: str
    tombstoned_at: str


@dataclass(frozen=True)
class TransferredLearningState:
    id: str
    owner_id: str
    goal_id: str
    topic_stable_id: str
    graph_version_id: str
    classification: TransferClassification
    origin: str
    recommended_depth: str
    explanation: str
    derivation_version: str
    input_hash: str
    derived_at: str


@dataclass(frozen=True)
class DeleteImpact:
    snapshot_id: str
    goal_id: str
    evidence_ids: tuple[str, ...]
    learning_state_ids: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceDeleteSnapshot:
    id: str
    owner_id: str
    goal_id: str
    impact_json: str
    impact_hash: str
    created_at: str


@dataclass(frozen=True)
class Rubric:
    id: str
    owner_id: str
    task_context: str
    capability: str
    role: str | None
    level: str | None
    version: str
    status: RubricStatus
    provenance: str
    created_at: str


@dataclass(frozen=True)
class RubricDimension:
    id: str
    rubric_id: str
    stable_dimension_id: str
    name: str
    description: str
    ordinal: int
    evaluation_guidance: str


@dataclass(frozen=True)
class EvaluationRequest:
    evidence_id: str
    task_ref: str
    rubric_id: str
    rubric_version: str
    assumptions: tuple[str, ...]
    requested_capability: str
    source_refs: tuple[str, ...]
    provenance_refs: tuple[str, ...]
    role: str | None
    level: str | None
    evaluation_method: str


@dataclass(frozen=True)
class EvaluationDimensionResult:
    dimension_id: str
    outcome: DimensionOutcome
    rationale: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class EvaluationResult:
    state: AssessmentState
    dimensions: tuple[EvaluationDimensionResult, ...]
    facts: tuple[str, ...]
    trade_offs: tuple[str, ...]
    citations: tuple[str, ...]
    ambiguities: tuple[str, ...]
    feedback: str
    cross_question_candidate: str | None
    revision_invitation: str | None
    warnings: tuple[str, ...]
    limitation_labels: tuple[str, ...]


@dataclass(frozen=True)
class Assessment:
    id: str
    owner_id: str
    goal_id: str
    evidence_id: str
    run_id: str | None
    rubric_id: str
    rubric_version: str
    state: AssessmentState
    task_ref: str
    requested_capability: str
    role: str | None
    level: str | None
    evaluation_method: str
    assumptions: tuple[str, ...]
    source_refs: tuple[str, ...]
    provenance_refs: tuple[str, ...]
    facts: tuple[str, ...]
    trade_offs: tuple[str, ...]
    citations: tuple[str, ...]
    ambiguities: tuple[str, ...]
    feedback: str
    cross_question_candidate: str | None
    revision_invitation: str | None
    warnings: tuple[str, ...]
    limitation_labels: tuple[str, ...]
    predecessor_assessment_id: str | None
    derivation_excluded: bool
    created_at: str


@dataclass(frozen=True)
class AssessmentDimensionResult:
    id: str
    owner_id: str
    goal_id: str
    assessment_id: str
    rubric_dimension_id: str
    outcome: DimensionOutcome
    rationale: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class AssessmentDispute:
    id: str
    owner_id: str
    goal_id: str
    assessment_id: str
    reason: str
    status: DisputeStatus
    requested_at: str
    resolved_at: str | None
    resolution_note: str | None


@dataclass(frozen=True)
class ReevaluationRequest:
    id: str
    owner_id: str
    goal_id: str
    dispute_id: str
    prior_assessment_id: str
    job_id: str
    status: ReevaluationStatus
    resulting_assessment_id: str | None
    requested_at: str
    completed_at: str | None
    failure_reference: str | None


@dataclass(frozen=True)
class EvidenceEvaluationIdempotencyRecord:
    id: str
    owner_id: str
    operation: str
    idempotency_key: str
    request_hash: str
    response_json: str
    created_at: str
    request_ref: str | None = None
    completed: bool = True
