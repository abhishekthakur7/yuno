"""Evidence transfer and goal deletion."""

from __future__ import annotations

import json
from dataclasses import asdict

from yuno.modules.audit.domain import AuditEvent
from yuno.modules.evidence_evaluation.domain import (
    FIXTURE_DERIVATION_VERSION,
    Assessment,
    AssessmentDimensionResult,
    AssessmentDispute,
    AssessmentState,
    DeleteImpact,
    DerivedProgress,
    DisputeStatus,
    EvaluationRequest,
    EvaluationResult,
    Evidence,
    EvidenceDeleteSnapshot,
    EvidencePayload,
    EvidenceTombstone,
    GoalProgressMemo,
    LearningStateExplanation,
    ProgressClassification,
    ProgressCorrection,
    ProgressDimension,
    ProgressTransfer,
    ReevaluationRequest,
    ReevaluationStatus,
    RubricStatus,
    TransferClassification,
    TransferredEvidenceRef,
    TransferredLearningState,
    derive_progress,
    progress_input_hash,
)
from yuno.modules.evidence_evaluation.ports import EvaluationAdapter, EvidenceUnitOfWork
from yuno.shared.domain.clock import Clock, SystemClock, now_text
from yuno.shared.domain.errors import (
    ConflictError,
    DomainValidationError,
    NotFoundError,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id


def get_derived_progress(
    uow: EvidenceUnitOfWork,
    owner_id: str,
    goal_id: str,
    *,
    clock: Clock,
):
    goal = uow.profiles_goals.get_goal(owner_id, goal_id)
    if goal is None:
        raise NotFoundError(f"Goal '{goal_id}' was not found.")
    now = now_text(clock)
    topic_ids = tuple(
        sorted(item.stable_id for item in uow.canonical.get_published_topics(goal.graph_version_id))
    )
    evidence = tuple(uow.evidence.list_progress_evidence(owner_id, goal_id))
    corrections = tuple(
        ProgressCorrection(
            f"correction:{item.id}", item.owner_id, item.goal_id, item.topic_stable_id,
            item.correction_type.value, item.value, item.reason, item.created_at,
            f"correction:{item.supersedes_correction_id}"
            if item.supersedes_correction_id else None,
        )
        for item in uow.roadmap.list_corrections(owner_id, goal_id)
    )
    transfers = tuple(
        ProgressTransfer(
            item.id, item.owner_id, item.goal_id, item.topic_stable_id,
            item.source_evidence_id, ProgressClassification(item.classification),
            item.rationale, item.created_at,
        )
        for item in uow.roadmap.list_progress_transfers(owner_id, goal_id)
    )
    expected_hash = progress_input_hash(
        goal_id, topic_ids, evidence, corrections, transfers, now, FIXTURE_DERIVATION_VERSION
    )
    memo = uow.evidence.get_progress_memo(owner_id, goal_id)
    if memo is not None and memo.input_hash == expected_hash:
        try:
            data = json.loads(memo.explanation_json)
            integrity_digest = data.pop("integrity_digest")
            if integrity_digest != hash_payload(data):
                raise ValueError("Progress memo integrity digest mismatch.")

            def dimension(name: str) -> ProgressDimension:
                value = data[name]
                return ProgressDimension(
                    ProgressClassification(value["classification"]), value["definition"],
                    tuple(value["supporting_evidence_refs"]), value["uncertainty"],
                )

            states = tuple(
                LearningStateExplanation(
                    item["topic_stable_id"], ProgressClassification(item["classification"]),
                    item["definition"], tuple(item["supporting_evidence_refs"]),
                    item["uncertainty"], item["correction_ref"],
                )
                for item in data["learning_states"]
            )
            if tuple(item.topic_stable_id for item in states) != topic_ids:
                raise ValueError("Progress memo topic spine mismatch.")
            cached = DerivedProgress(
                dimension("coverage"), dimension("proficiency"), dimension("retention"),
                dimension("readiness"), states, memo.input_hash, memo.derivation_version,
                memo.computed_at,
            )
            if (
                cached.rule_version == FIXTURE_DERIVATION_VERSION
                and (cached.coverage.classification, cached.proficiency.classification,
                     cached.retention.classification, cached.readiness.classification)
                == (memo.coverage, memo.proficiency, memo.retention, memo.readiness)
            ):
                return DerivedProgress(
                    cached.coverage, cached.proficiency, cached.retention, cached.readiness,
                    cached.learning_states, cached.input_hash, cached.rule_version, now,
                )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass
        memo = None
    result = derive_progress(
        goal_id, topic_ids, evidence, corrections, transfers, now, FIXTURE_DERIVATION_VERSION
    )
    if memo is None or memo.input_hash != result.input_hash:
        explanation = {
            "coverage": asdict(result.coverage),
            "proficiency": asdict(result.proficiency),
            "retention": asdict(result.retention),
            "readiness": asdict(result.readiness),
            "learning_states": [asdict(item) for item in result.learning_states],
        }
        explanation_json = json.dumps(
            {**explanation, "integrity_digest": hash_payload(explanation)},
            sort_keys=True,
            separators=(",", ":"),
        )
        uow.evidence.put_progress_memo(
            GoalProgressMemo(
                goal_id, owner_id, result.coverage.classification,
                result.proficiency.classification, result.retention.classification,
                result.readiness.classification, explanation_json, result.input_hash,
                result.rule_version, result.effective_now,
            )
        )
    return result


def create_evidence(
    uow: EvidenceUnitOfWork,
    owner_id: str,
    goal_id: str,
    *,
    topic_stable_id: str,
    evidence_type: str,
    capability: str,
    summary: str,
    origin: str,
    content: str,
    content_version: str,
    clock: Clock | None = None,
) -> Evidence:
    goal = uow.profiles_goals.get_goal(owner_id, goal_id)
    if goal is None:
        raise NotFoundError(f"Goal '{goal_id}' was not found.")
    if getattr(goal.status, "value", goal.status) != "active":
        raise ConflictError("Evidence can only be added to an active goal.")
    topics = {topic.stable_id for topic in uow.canonical.get_published_topics(goal.graph_version_id)}
    if topic_stable_id not in topics:
        raise DomainValidationError("Evidence must reference a topic in the goal's approved graph.")
    required = {
        "evidence_type": evidence_type,
        "capability": capability,
        "origin": origin,
        "content": content,
        "content_version": content_version,
    }
    for field, value in required.items():
        if not value.strip():
            raise DomainValidationError(f"{field} must not be blank.")
    timestamp = now_text(clock or SystemClock())
    evidence = Evidence(
        new_id(), owner_id, goal_id, topic_stable_id, evidence_type.strip(),
        capability, hash_payload({"content": content, "content_version": content_version}),
        summary.strip(), origin.strip(), timestamp,
    )
    uow.evidence.add_evidence(
        evidence,
        EvidencePayload(evidence.id, owner_id, goal_id, content, content_version.strip()),
    )
    uow.audit.append(_audit(owner_id, goal_id, "evidence", evidence.id, "created", None, hash_payload(evidence), timestamp))
    return evidence


def list_goal_evidence(uow: EvidenceUnitOfWork, owner_id: str, goal_id: str):
    if uow.profiles_goals.get_goal(owner_id, goal_id) is None:
        raise NotFoundError(f"Goal '{goal_id}' was not found.")
    return uow.evidence.list_evidence(owner_id, goal_id)


def get_evidence_record(uow: EvidenceUnitOfWork, owner_id: str, evidence_id: str):
    record = uow.evidence.get_evidence_by_id(owner_id, evidence_id)
    if record is None:
        raise NotFoundError(f"Evidence '{evidence_id}' was not found.")
    return record, uow.evidence.get_payload(owner_id, record.goal_id, evidence_id)


def perform_assessment(
    uow: EvidenceUnitOfWork,
    adapter: EvaluationAdapter,
    owner_id: str,
    request: EvaluationRequest,
    *,
    run_id: str | None = None,
    predecessor: Assessment | None = None,
    clock: Clock | None = None,
) -> Assessment:
    evidence = uow.evidence.get_evidence_by_id(owner_id, request.evidence_id)
    if evidence is None:
        raise NotFoundError("The evidence was not found.")
    if uow.evidence.get_payload(owner_id, evidence.goal_id, evidence.id) is None:
        raise ConflictError("Tombstoned evidence cannot be assessed.")
    rubric = uow.evidence.get_rubric(owner_id, request.rubric_id)
    if rubric is None or rubric.status is RubricStatus.RETIRED:
        raise NotFoundError("The rubric was not found or is retired.")
    if request.rubric_version != rubric.version:
        raise ConflictError("The requested rubric version is stale.")
    if request.requested_capability != evidence.capability:
        raise DomainValidationError("The requested capability must match the evidence capability.")
    active = uow.evidence.get_active_assessment_for_evidence(owner_id, evidence.id)
    if predecessor is None and active is not None:
        raise ConflictError("Evidence already has an active assessment; dispute and re-evaluate it.")
    if predecessor is not None and (active is None or active.id != predecessor.id or predecessor.derivation_excluded):
        raise ConflictError("Only the active assessment tip can be re-evaluated.")

    result = adapter.evaluate(request)
    rubric_dimensions = tuple(uow.evidence.list_rubric_dimensions(owner_id, rubric.id))
    _validate_evaluation_result(result, rubric_dimensions)
    timestamp = now_text(clock or SystemClock())
    assessment_id = new_id()
    assessment = Assessment(
        assessment_id, owner_id, evidence.goal_id, evidence.id, run_id, rubric.id,
        rubric.version, result.state, request.task_ref, request.requested_capability,
        request.role, request.level, request.evaluation_method, request.assumptions,
        request.source_refs, request.provenance_refs, result.facts, result.trade_offs,
        result.citations, result.ambiguities, result.feedback,
        result.cross_question_candidate, result.revision_invitation, result.warnings,
        result.limitation_labels, predecessor.id if predecessor else None, False,
        timestamp,
    )
    dimensions_by_stable_id = {dimension.stable_dimension_id: dimension for dimension in rubric_dimensions}
    dimension_rows = tuple(
        AssessmentDimensionResult(
            new_id(), owner_id, evidence.goal_id, assessment_id,
            dimensions_by_stable_id[item.dimension_id].id, item.outcome,
            item.rationale, item.evidence_refs,
        )
        for item in result.dimensions
    )
    # Successor and all of its dimensions exist before the sole permitted
    # predecessor update; the surrounding UoW makes the chain atomic.
    uow.evidence.add_assessment(assessment, dimension_rows)
    if predecessor is not None:
        uow.evidence.exclude_assessment(owner_id, evidence.goal_id, predecessor.id)
    uow.audit.append(_audit(owner_id, evidence.goal_id, "assessment", assessment.id, "created", None, hash_payload(assessment), timestamp))
    return assessment


def create_dispute(
    uow: EvidenceUnitOfWork,
    owner_id: str,
    assessment_id: str,
    reason: str,
    *,
    clock: Clock | None = None,
) -> AssessmentDispute:
    assessment = get_assessment(uow, owner_id, assessment_id)
    if not reason.strip():
        raise DomainValidationError("A dispute reason must not be blank.")
    timestamp = now_text(clock or SystemClock())
    dispute = AssessmentDispute(new_id(), owner_id, assessment.goal_id, assessment.id, reason.strip(), DisputeStatus.REQUESTED, timestamp, None, None)
    uow.evidence.add_dispute(dispute)
    uow.audit.append(_audit(owner_id, assessment.goal_id, "assessment_dispute", dispute.id, "created", None, hash_payload(dispute), timestamp))
    return dispute


def request_reevaluation(
    uow: EvidenceUnitOfWork,
    owner_id: str,
    assessment_id: str,
    dispute_id: str,
    *,
    job_id: str | None = None,
    clock: Clock | None = None,
) -> ReevaluationRequest:
    assessment = get_assessment(uow, owner_id, assessment_id)
    active = uow.evidence.get_active_assessment_for_evidence(owner_id, assessment.evidence_id)
    if assessment.derivation_excluded or active is None or active.id != assessment.id:
        raise ConflictError("Only the active assessment tip can be re-evaluated.")
    dispute = uow.evidence.get_dispute(owner_id, dispute_id)
    if dispute is None or dispute.assessment_id != assessment_id:
        raise NotFoundError("The dispute does not belong to this assessment.")
    if uow.evidence.get_reevaluation_for_dispute(owner_id, dispute_id) is not None:
        raise ConflictError("This dispute already has a re-evaluation request.")
    timestamp = now_text(clock or SystemClock())
    request = ReevaluationRequest(new_id(), owner_id, assessment.goal_id, dispute.id, assessment.id, job_id or new_id(), ReevaluationStatus.REQUESTED, None, timestamp, None, None)
    uow.evidence.add_reevaluation_request(request)
    uow.audit.append(_audit(owner_id, assessment.goal_id, "reevaluation_request", request.id, "requested", None, hash_payload(request), timestamp))
    return request


def complete_reevaluation(
    uow: EvidenceUnitOfWork,
    adapter: EvaluationAdapter,
    owner_id: str,
    request_id: str,
    *,
    clock: Clock | None = None,
) -> Assessment:
    request_record = uow.evidence.get_reevaluation_request(owner_id, request_id)
    if request_record is None:
        raise NotFoundError("The re-evaluation request was not found.")
    if request_record.status is not ReevaluationStatus.REQUESTED:
        if request_record.resulting_assessment_id:
            return get_assessment(uow, owner_id, request_record.resulting_assessment_id)
        raise ConflictError("The re-evaluation request is no longer runnable.")
    predecessor = get_assessment(uow, owner_id, request_record.prior_assessment_id)
    evaluation_request = EvaluationRequest(
        predecessor.evidence_id, predecessor.task_ref, predecessor.rubric_id,
        predecessor.rubric_version, predecessor.assumptions,
        predecessor.requested_capability, predecessor.source_refs,
        predecessor.provenance_refs, predecessor.role, predecessor.level,
        predecessor.evaluation_method,
    )
    successor = perform_assessment(uow, adapter, owner_id, evaluation_request, run_id=predecessor.run_id, predecessor=predecessor, clock=clock)
    timestamp = now_text(clock or SystemClock())
    uow.evidence.update_reevaluation_request(owner_id, request_id, {
        "status": ReevaluationStatus.COMPLETED,
        "resulting_assessment_id": successor.id,
        "completed_at": timestamp,
    })
    uow.audit.append(_audit(owner_id, predecessor.goal_id, "reevaluation_request", request_id, "completed", hash_payload(request_record), hash_payload({"resulting_assessment_id": successor.id}), timestamp))
    return successor


def fail_reevaluation(uow: EvidenceUnitOfWork, owner_id: str, request_id: str, failure_reference: str) -> None:
    request = uow.evidence.get_reevaluation_request(owner_id, request_id)
    if request is not None and request.status is ReevaluationStatus.REQUESTED:
        uow.evidence.update_reevaluation_request(owner_id, request_id, {"status": ReevaluationStatus.FAILED, "failure_reference": failure_reference})
        timestamp = now_text(SystemClock())
        uow.audit.append(_audit(owner_id, request.goal_id, "reevaluation_request", request_id, "failed", hash_payload(request), hash_payload({"failure_reference": failure_reference}), timestamp))


def get_assessment(uow: EvidenceUnitOfWork, owner_id: str, assessment_id: str) -> Assessment:
    assessment = uow.evidence.get_assessment(owner_id, assessment_id)
    if assessment is None:
        raise NotFoundError(f"Assessment '{assessment_id}' was not found.")
    return assessment


def _validate_evaluation_result(result: EvaluationResult, rubric_dimensions) -> None:
    expected = {dimension.stable_dimension_id for dimension in rubric_dimensions}
    actual = [dimension.dimension_id for dimension in result.dimensions]
    if not expected or len(actual) != len(set(actual)) or set(actual) != expected:
        raise DomainValidationError("Evaluation result must contain exactly one result for every rubric dimension.")
    if not result.feedback.strip() or any(not item.rationale.strip() for item in result.dimensions):
        raise DomainValidationError("Evaluation feedback and every dimension rationale must be non-blank.")
    all_text_groups = (
        result.facts, result.trade_offs, result.citations, result.ambiguities,
        result.warnings, result.limitation_labels,
    )
    if any(not value.strip() for group in all_text_groups for value in group):
        raise DomainValidationError("Evaluation result list values must not be blank.")
    has_unresolved = bool(result.ambiguities) or any(
        item.outcome.value == "ambiguity-unresolved" for item in result.dimensions
    )
    if (result.state is AssessmentState.AMBIGUITY_UNRESOLVED) != has_unresolved:
        raise DomainValidationError("ambiguity-unresolved state must exactly match unresolved ambiguity content.")


def transfer_evidence(
    uow: EvidenceUnitOfWork,
    owner_id: str,
    *,
    source_goal_id: str,
    source_evidence_id: str,
    target_goal_id: str,
    classification: TransferClassification,
    rationale: str,
    recommended_depth: str,
    clock: Clock | None = None,
) -> TransferredEvidenceRef:
    source_goal = uow.profiles_goals.get_goal(owner_id, source_goal_id)
    target_goal = uow.profiles_goals.get_goal(owner_id, target_goal_id)
    if source_goal is None or target_goal is None:
        raise NotFoundError("The source or target goal was not found.")
    if source_goal_id == target_goal_id:
        raise ConflictError("Evidence transfer requires two different goals.")
    if not rationale.strip():
        raise DomainValidationError("Evidence transfer rationale must not be blank.")
    if not recommended_depth.strip():
        raise DomainValidationError("Recommended depth must not be blank.")
    evidence = uow.evidence.get_evidence(owner_id, source_goal_id, source_evidence_id)
    if evidence is None:
        raise NotFoundError("The source evidence was not found.")
    target_topic_ids = {
        topic.stable_id
        for topic in uow.canonical.get_published_topics(target_goal.graph_version_id)
    }
    if evidence.topic_stable_id not in target_topic_ids:
        raise ConflictError(
            "The source evidence topic is not part of the target goal's graph."
        )
    if (
        uow.roadmap.get_learning_state_for_topic(
            owner_id, target_goal_id, evidence.topic_stable_id
        )
        is not None
    ):
        raise ConflictError(
            "The target goal already has a learning state for this topic."
        )
    timestamp = now_text(clock or SystemClock())
    state = TransferredLearningState(
        id=new_id(),
        owner_id=owner_id,
        goal_id=target_goal_id,
        topic_stable_id=evidence.topic_stable_id,
        graph_version_id=target_goal.graph_version_id,
        classification=classification,
        origin="transferred-evidence",
        recommended_depth=recommended_depth,
        explanation=rationale.strip(),
        derivation_version="evidence-transfer-v1",
        input_hash=hash_payload(
            {
                "source_evidence_id": source_evidence_id,
                "classification": classification.value,
                "rationale": rationale,
            }
        ),
        derived_at=timestamp,
    )
    ref = TransferredEvidenceRef(
        id=new_id(),
        owner_id=owner_id,
        goal_id=target_goal_id,
        learning_state_id=state.id,
        source_goal_id=source_goal_id,
        source_evidence_id=source_evidence_id,
        classification=classification,
        rationale=rationale.strip(),
        created_at=timestamp,
    )
    uow.roadmap.add_transferred_evidence(state, ref)
    uow.audit.append(
        _audit(
            owner_id,
            target_goal_id,
            "evidence_transfer",
            ref.id,
            "created",
            None,
            hash_payload(ref),
            timestamp,
        )
    )
    return ref


def create_delete_preflight(
    uow: EvidenceUnitOfWork, owner_id: str, goal_id: str, *, clock: Clock | None = None
) -> DeleteImpact:
    goal = uow.profiles_goals.get_goal(owner_id, goal_id)
    if goal is None:
        raise NotFoundError(f"Goal '{goal_id}' was not found.")
    impact_data = _current_impact(uow, owner_id, goal_id)
    timestamp = now_text(clock or SystemClock())
    snapshot = EvidenceDeleteSnapshot(
        id=new_id(),
        owner_id=owner_id,
        goal_id=goal_id,
        impact_json=json.dumps(impact_data, sort_keys=True, separators=(",", ":")),
        impact_hash=hash_payload(impact_data),
        created_at=timestamp,
    )
    uow.evidence.add_delete_snapshot(snapshot)
    return DeleteImpact(
        snapshot.id,
        goal_id,
        tuple(impact_data["evidence_ids"]),
        tuple(impact_data["learning_state_ids"]),
    )


def delete_goal(
    uow: EvidenceUnitOfWork,
    owner_id: str,
    goal_id: str,
    snapshot_id: str,
    *,
    clock: Clock | None = None,
) -> DeleteImpact:
    goal = uow.profiles_goals.get_goal_for_lifecycle(owner_id, goal_id)
    if goal is None:
        raise NotFoundError(f"Goal '{goal_id}' was not found.")
    snapshot = uow.evidence.get_delete_snapshot(owner_id, goal_id, snapshot_id)
    if snapshot is None:
        raise NotFoundError("The delete impact snapshot was not found.")
    data = json.loads(snapshot.impact_json)
    impact = DeleteImpact(
        snapshot.id,
        goal_id,
        tuple(data["evidence_ids"]),
        tuple(data["learning_state_ids"]),
    )
    if goal.status.value == "tombstoned":
        return impact
    current_impact = _current_impact(uow, owner_id, goal_id)
    if hash_payload(current_impact) != snapshot.impact_hash:
        raise ConflictError(
            "The delete impact changed after preflight; request a new preflight."
        )
    timestamp = now_text(clock or SystemClock())
    for evidence_id in impact.evidence_ids:
        uow.evidence.add_tombstone(
            EvidenceTombstone(
                evidence_id,
                owner_id,
                goal_id,
                snapshot.id,
                "source goal deleted",
                timestamp,
            )
        )
        uow.evidence.remove_payload(owner_id, goal_id, evidence_id)
    uow.roadmap.downgrade_transfer_dependents(owner_id, goal_id, derived_at=timestamp)
    updated = uow.profiles_goals.tombstone_goal(owner_id, goal_id, goal.row_version)
    if updated is None:
        raise ConflictError("The goal changed during deletion.")
    profile = uow.profiles_goals.get_profile(owner_id)
    if (
        profile is not None
        and profile.current_goal_id == goal_id
        and uow.profiles_goals.update_profile(
            owner_id, profile.profile_revision, {"current_goal_id": None}
        )
        is None
    ):
        raise ConflictError("The profile changed during deletion.")
    uow.audit.append(
        _audit(
            owner_id,
            goal_id,
            "goal_workspace",
            goal_id,
            "deleted",
            hash_payload(goal),
            hash_payload(impact),
            timestamp,
        )
    )
    return impact


def _current_impact(
    uow: EvidenceUnitOfWork, owner_id: str, goal_id: str
) -> dict[str, object]:
    dependents = tuple(uow.roadmap.list_transfer_dependents(owner_id, goal_id))
    return {
        "goal_id": goal_id,
        "evidence_ids": sorted({evidence_id for evidence_id, _ in dependents}),
        "learning_state_ids": sorted({state_id for _, state_id in dependents}),
    }


def _audit(
    owner_id: str,
    goal_id: str,
    entity_type: str,
    entity_id: str,
    action: str,
    before_hash: str | None,
    after_hash: str | None,
    timestamp: str,
) -> AuditEvent:
    return AuditEvent(
        new_id(),
        owner_id,
        goal_id,
        "learner",
        entity_type,
        entity_id,
        action,
        before_hash,
        after_hash,
        None,
        None,
        None,
        timestamp,
    )
