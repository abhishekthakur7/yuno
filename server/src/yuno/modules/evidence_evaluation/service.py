"""Evidence transfer and goal deletion."""

from __future__ import annotations

import json

from yuno.modules.audit.domain import AuditEvent
from yuno.modules.evidence_evaluation.domain import (
    DeleteImpact,
    EvidenceDeleteSnapshot,
    EvidenceTombstone,
    TransferClassification,
    TransferredEvidenceRef,
    TransferredLearningState,
)
from yuno.modules.evidence_evaluation.ports import EvidenceUnitOfWork
from yuno.shared.domain.clock import Clock, SystemClock, now_text
from yuno.shared.domain.errors import (
    ConflictError,
    DomainValidationError,
    NotFoundError,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id


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
