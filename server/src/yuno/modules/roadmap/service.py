"""Application services for explicit, learner-controlled roadmap proposals."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from yuno.modules.audit.domain import AuditEvent
from yuno.modules.roadmap.domain import (
    OverlayDecisionType,
    OverlayEntry,
    OverlayEntryType,
    OverlayProposal,
    OverlayProposalDecision,
    OverlayProposalState,
    OverlayProposalType,
    ProposalStaleError,
    RoadmapRelation,
    RoadmapTopic,
    validate_order_constraint,
    validate_proposal_payload,
)
from yuno.modules.roadmap.ports import CanonicalRelationView, RoadmapUnitOfWork
from yuno.shared.domain.clock import Clock, SystemClock, now_text
from yuno.shared.domain.errors import (
    ConflictError,
    DomainValidationError,
    NotFoundError,
    OverlayPendingCapError,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id


def create_proposal(
    uow: RoadmapUnitOfWork,
    owner_id: str,
    goal_id: str,
    *,
    generated_against_graph_version_id: str,
    topic_stable_id: str | None,
    proposal_type: OverlayProposalType,
    payload: Mapping[str, object],
    pending_cap: int,
    clock: Clock | None = None,
) -> tuple[OverlayProposal, bool]:
    """Persist an annotation only. Creation never mutates the accepted overlay."""
    if pending_cap < 1:
        raise DomainValidationError(
            "The configured overlay proposal cap must be positive."
        )
    goal = _require_goal(uow, owner_id, goal_id)
    if uow.canonical.get_published_version(generated_against_graph_version_id) is None:
        raise NotFoundError("The proposal's approved canonical graph was not found.")
    topics = uow.canonical.get_published_topics(generated_against_graph_version_id)
    if topic_stable_id is not None and all(
        topic.stable_id != topic_stable_id for topic in topics
    ):
        raise NotFoundError("The proposal topic is outside its approved graph.")
    validate_proposal_payload(proposal_type, topic_stable_id, payload)
    content_hash = hash_payload(
        {
            "generated_against_graph_version_id": generated_against_graph_version_id,
            "topic_stable_id": topic_stable_id,
            "proposal_type": proposal_type.value,
            "payload": dict(payload),
        }
    )
    existing = uow.roadmap.get_pending_proposal_by_hash(owner_id, goal_id, content_hash)
    if existing is not None:
        return existing, True
    if uow.roadmap.count_pending_proposals(owner_id, goal_id) >= pending_cap:
        raise OverlayPendingCapError(
            "This goal has reached its pending overlay proposal limit. "
            "Accept, postpone, or dismiss a proposal before adding another.",
            current_state=OverlayProposalState.AWAITING_DECISION.value,
            recovery_action="Review existing pending proposals.",
        )
    timestamp = now_text(clock or SystemClock())
    proposal = OverlayProposal(
        id=new_id(),
        owner_id=owner_id,
        goal_id=goal.id,
        generated_against_graph_version_id=generated_against_graph_version_id,
        topic_stable_id=topic_stable_id,
        proposal_type=proposal_type,
        payload=dict(payload),
        content_hash=content_hash,
        state=OverlayProposalState.AWAITING_DECISION,
        state_reason=None,
        created_at=timestamp,
    )
    created = uow.roadmap.add_proposal(proposal)
    _audit(uow, created, "created", None, created, clock)
    return created, False


def decide_proposal(
    uow: RoadmapUnitOfWork,
    owner_id: str,
    proposal_id: str,
    *,
    decision: OverlayDecisionType,
    reason: str | None,
    bridge_endpoint: bool,
    clock: Clock | None = None,
) -> tuple[OverlayProposal, ProposalStaleError | None]:
    proposal = uow.roadmap.get_proposal(owner_id, proposal_id)
    if proposal is None:
        raise NotFoundError("Overlay proposal not found.")
    is_bridge = proposal.proposal_type is OverlayProposalType.BRIDGE
    if bridge_endpoint != is_bridge:
        raise NotFoundError("Bridge proposal not found.")
    allowed = (
        {
            OverlayDecisionType.ADD,
            OverlayDecisionType.POSTPONE,
            OverlayDecisionType.DISMISS,
        }
        if is_bridge
        else {
            OverlayDecisionType.ACCEPT,
            OverlayDecisionType.POSTPONE,
            OverlayDecisionType.DISMISS,
        }
    )
    if decision not in allowed:
        raise DomainValidationError("That decision is invalid for this proposal type.")
    if proposal.state not in {
        OverlayProposalState.AWAITING_DECISION,
        OverlayProposalState.POSTPONED,
    }:
        raise ConflictError(
            "This proposal has already reached a terminal decision.",
            current_state=proposal.state.value,
        )
    timestamp = now_text(clock or SystemClock())
    decision_record = OverlayProposalDecision(
        id=new_id(),
        owner_id=owner_id,
        goal_id=proposal.goal_id,
        proposal_id=proposal.id,
        decision=decision,
        reason=reason.strip() if reason and reason.strip() else None,
        decided_at=timestamp,
    )
    accepting = decision in {OverlayDecisionType.ACCEPT, OverlayDecisionType.ADD}
    goal = _require_goal(uow, owner_id, proposal.goal_id)
    if (
        accepting
        and goal.graph_version_id != proposal.generated_against_graph_version_id
    ):
        stale_reason = (
            "The proposal was generated against graph "
            f"'{proposal.generated_against_graph_version_id}', but this goal now uses "
            f"'{goal.graph_version_id}'."
        )
        uow.roadmap.append_proposal_decision(decision_record)
        rejected = _update_state(
            uow,
            proposal,
            OverlayProposalState.REJECTED_STALE,
            stale_reason,
            timestamp,
        )
        _audit(uow, rejected, "rejected_stale", proposal, rejected, clock)
        return rejected, ProposalStaleError(
            stale_reason,
            current_state=rejected.state.value,
            recovery_action="Create a new proposal against the goal's current graph.",
        )

    if accepting:
        _apply_proposal(
            uow, proposal, reason=decision_record.reason, timestamp=timestamp
        )
        next_state = OverlayProposalState.ACCEPTED
    elif decision is OverlayDecisionType.POSTPONE:
        next_state = OverlayProposalState.POSTPONED
    else:
        next_state = OverlayProposalState.DISMISSED
    uow.roadmap.append_proposal_decision(decision_record)
    updated = _update_state(
        uow, proposal, next_state, decision_record.reason, timestamp
    )
    _audit(uow, updated, f"decision_{decision.value}", proposal, updated, clock)
    return updated, None


def _apply_proposal(
    uow: RoadmapUnitOfWork,
    proposal: OverlayProposal,
    *,
    reason: str | None,
    timestamp: str,
) -> None:
    goal = _require_goal(uow, proposal.owner_id, proposal.goal_id)
    topics = uow.canonical.get_published_topics(goal.graph_version_id)
    if proposal.topic_stable_id is not None and all(
        topic.stable_id != proposal.topic_stable_id for topic in topics
    ):
        raise ProposalStaleError("The proposal topic is no longer in the goal's graph.")
    if proposal.proposal_type is OverlayProposalType.ORDERING:
        before = str(proposal.payload["before_topic_id"])
        after = str(proposal.payload["after_topic_id"])
        relations = uow.canonical.get_published_relations(goal.graph_version_id)
        existing = [
            RoadmapRelation(
                str(entry.value["before_topic_id"]),
                str(entry.value["after_topic_id"]),
            )
            for entry in uow.roadmap.list_overlay_entries(proposal.owner_id, goal.id)
            if entry.entry_type is OverlayEntryType.ORDER_CONSTRAINT
        ]
        validate_order_constraint(
            tuple(
                RoadmapTopic(
                    topic.stable_id,
                    topic.title,
                    topic.subject,
                    topic.scope_tags,
                    topic.level_tag,
                    topic.target_capability,
                    topic.recommended_layer,
                )
                for topic in topics
            ),
            _prerequisites(relations),
            existing,
            RoadmapRelation(before, after),
        )
        entry_type = OverlayEntryType.ORDER_CONSTRAINT
    elif proposal.proposal_type is OverlayProposalType.BRIDGE:
        entry_type = OverlayEntryType.BRIDGE
    else:
        entry_type = OverlayEntryType.RECOMMENDATION
    overlay = uow.roadmap.get_or_create_overlay(
        proposal.owner_id, goal.id, goal.graph_version_id
    )
    uow.roadmap.append_overlay_entry(
        OverlayEntry(
            id=new_id(),
            owner_id=proposal.owner_id,
            goal_id=goal.id,
            overlay_id=overlay.id,
            graph_version_id=goal.graph_version_id,
            topic_stable_id=proposal.topic_stable_id,
            entry_type=entry_type,
            value=dict(proposal.payload),
            reason=reason,
            source="overlay_proposal",
            approved_at=timestamp,
            content_hash=proposal.content_hash,
        )
    )


def _update_state(
    uow: RoadmapUnitOfWork,
    proposal: OverlayProposal,
    state: OverlayProposalState,
    reason: str | None,
    timestamp: str,
) -> OverlayProposal:
    updated = uow.roadmap.update_proposal_state(
        proposal.owner_id,
        proposal.id,
        proposal.state.value,
        state=state.value,
        state_reason=reason,
        decided_at=timestamp,
    )
    if updated is None:
        raise ConflictError("The proposal changed; reload it and retry.")
    return updated


def _require_goal(uow: RoadmapUnitOfWork, owner_id: str, goal_id: str):
    goal = uow.profiles_goals.get_goal(owner_id, goal_id)
    if goal is None:
        raise NotFoundError("Goal workspace not found.")
    return goal


def _prerequisites(
    relations: Sequence[CanonicalRelationView],
) -> tuple[RoadmapRelation, ...]:
    return tuple(
        RoadmapRelation(relation.from_stable_id, relation.to_stable_id)
        for relation in relations
        if str(relation.relation_type) == "prerequisite"
    )


def _audit(
    uow: RoadmapUnitOfWork,
    proposal: OverlayProposal,
    action: str,
    before: object | None,
    after: object,
    clock: Clock | None,
) -> None:
    uow.audit.append(
        AuditEvent(
            id=new_id(),
            owner_id=proposal.owner_id,
            goal_id=proposal.goal_id,
            actor_role="learner",
            entity_type="overlay_proposal",
            entity_id=proposal.id,
            action=action,
            before_hash=hash_payload(before) if before is not None else None,
            after_hash=hash_payload(after),
            reason=None,
            request_id=None,
            correlation_id=None,
            occurred_at=now_text(clock or SystemClock()),
        )
    )
