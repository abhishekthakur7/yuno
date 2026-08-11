"""Deterministic roadmap reads and explicit append-only overlay commands."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends

from yuno.api.contracts import (
    DepthOverrideRequest,
    LearnerCorrectionRequest,
    LearningStateResponse,
    OrderConstraintRequest,
    RoadmapMutationResponse,
    RoadmapResponse,
    RoadmapTopicResponse,
    SkipDecisionRequest,
)
from yuno.api.dependencies import get_owner_id, get_unit_of_work, idempotency_key
from yuno.modules.roadmap.domain import (
    LearnerCorrection,
    OverlayEntry,
    OverlayEntryType,
    RoadmapIdempotencyRecord,
    RoadmapRelation,
    RoadmapTopic,
    project_roadmap,
    validate_order_constraint,
)
from yuno.modules.roadmap.ports import (
    CanonicalRelationView,
    CanonicalTopicView,
    GoalView,
    RoadmapUnitOfWork,
)
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.errors import IdempotencyConflictError, NotFoundError
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id

router = APIRouter(tags=["roadmap"])


@router.get("/goals/{goal_id}/roadmap", response_model=RoadmapResponse)
def get_goal_roadmap(
    goal_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[RoadmapUnitOfWork, Depends(get_unit_of_work)],
) -> RoadmapResponse:
    return _projection_response(uow, owner_id, goal_id)


@router.get(
    "/goals/{goal_id}/learning-states", response_model=list[LearningStateResponse]
)
def get_learning_states(
    goal_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[RoadmapUnitOfWork, Depends(get_unit_of_work)],
) -> list[LearningStateResponse]:
    _goal(uow, owner_id, goal_id)
    corrections = {
        item.topic_stable_id: item
        for item in uow.roadmap.list_corrections(owner_id, goal_id)
    }
    return [
        LearningStateResponse(
            topic_stable_id=item.topic_stable_id,
            classification=item.classification,
            origin=item.origin,
            recommended_depth=item.recommended_depth,
            explanation=item.explanation,
            corrected_classification=(
                corrections[item.topic_stable_id].value
                if item.topic_stable_id in corrections
                else None
            ),
        )
        for item in uow.roadmap.list_learning_states(owner_id, goal_id)
    ]


@router.post("/goals/{goal_id}/corrections", response_model=RoadmapMutationResponse)
def post_correction(
    goal_id: str,
    body: LearnerCorrectionRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[RoadmapUnitOfWork, Depends(get_unit_of_work)],
    key: Annotated[str, Depends(idempotency_key)],
) -> RoadmapMutationResponse:
    uow.profiles_goals.lock_idempotency_commands(owner_id)
    operation, request_hash = (
        f"correction:{goal_id}",
        hash_payload(body.model_dump(mode="json")),
    )
    if replay := _replay(uow, owner_id, operation, key, request_hash):
        return replay
    _goal_value, topics, _relations = _graph(uow, owner_id, goal_id)
    _require_topic(topics, body.topic_stable_id)
    prior = [
        item
        for item in uow.roadmap.list_corrections(owner_id, goal_id)
        if item.topic_stable_id == body.topic_stable_id
    ]
    uow.roadmap.append_correction(
        LearnerCorrection(
            id=new_id(),
            owner_id=owner_id,
            goal_id=goal_id,
            topic_stable_id=body.topic_stable_id,
            correction_type=body.correction_type,
            value=body.classification.value,
            reason=body.reason,
            created_at=now_text(SystemClock()),
            supersedes_correction_id=prior[-1].id if prior else None,
        )
    )
    return _save(uow, owner_id, goal_id, operation, key, request_hash)


@router.post(
    "/goals/{goal_id}/order-constraints", response_model=RoadmapMutationResponse
)
def post_order_constraint(
    goal_id: str,
    body: OrderConstraintRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[RoadmapUnitOfWork, Depends(get_unit_of_work)],
    key: Annotated[str, Depends(idempotency_key)],
) -> RoadmapMutationResponse:
    uow.profiles_goals.lock_idempotency_commands(owner_id)
    operation, request_hash = (
        f"order:{goal_id}",
        hash_payload(body.model_dump(mode="json")),
    )
    if replay := _replay(uow, owner_id, operation, key, request_hash):
        return replay
    goal, topics, relations = _graph(uow, owner_id, goal_id)
    entries = uow.roadmap.list_overlay_entries(owner_id, goal_id)
    superseded_ids = {
        item.supersedes_entry_id
        for item in entries
        if item.supersedes_entry_id is not None
    }
    active_order_entries = [
        item
        for item in entries
        if item.entry_type is OverlayEntryType.ORDER_CONSTRAINT
        and item.id not in superseded_ids
    ]
    replacement = next(
        (
            item
            for item in reversed(active_order_entries)
            if {
                str(item.value["before_topic_id"]),
                str(item.value["after_topic_id"]),
            }
            == {body.before_topic_id, body.after_topic_id}
        ),
        None,
    )
    existing = [
        RoadmapRelation(
            str(item.value["before_topic_id"]), str(item.value["after_topic_id"])
        )
        for item in active_order_entries
        if item is not replacement
    ]
    candidate = RoadmapRelation(body.before_topic_id, body.after_topic_id)
    validate_order_constraint(
        _topics(topics), _prerequisites(relations), existing, candidate
    )
    _append_entry(
        uow,
        owner_id,
        goal,
        OverlayEntryType.ORDER_CONSTRAINT,
        None,
        {
            "before_topic_id": body.before_topic_id,
            "after_topic_id": body.after_topic_id,
        },
        body.reason,
        supersedes_entry_id=replacement.id if replacement is not None else None,
    )
    return _save(uow, owner_id, goal_id, operation, key, request_hash)


@router.post("/goals/{goal_id}/skip-decisions", response_model=RoadmapMutationResponse)
def post_skip(
    goal_id: str,
    body: SkipDecisionRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[RoadmapUnitOfWork, Depends(get_unit_of_work)],
    key: Annotated[str, Depends(idempotency_key)],
) -> RoadmapMutationResponse:
    uow.profiles_goals.lock_idempotency_commands(owner_id)
    operation, request_hash = (
        f"skip:{goal_id}",
        hash_payload(body.model_dump(mode="json")),
    )
    if replay := _replay(uow, owner_id, operation, key, request_hash):
        return replay
    goal, topics, _ = _graph(uow, owner_id, goal_id)
    _require_topic(topics, body.topic_stable_id)
    _append_entry(
        uow,
        owner_id,
        goal,
        OverlayEntryType.SKIP,
        body.topic_stable_id,
        {"skipped": body.skipped},
        body.reason,
    )
    return _save(uow, owner_id, goal_id, operation, key, request_hash)


@router.post("/goals/{goal_id}/depth-overrides", response_model=RoadmapMutationResponse)
def post_depth(
    goal_id: str,
    body: DepthOverrideRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[RoadmapUnitOfWork, Depends(get_unit_of_work)],
    key: Annotated[str, Depends(idempotency_key)],
) -> RoadmapMutationResponse:
    uow.profiles_goals.lock_idempotency_commands(owner_id)
    operation, request_hash = (
        f"depth:{goal_id}",
        hash_payload(body.model_dump(mode="json")),
    )
    if replay := _replay(uow, owner_id, operation, key, request_hash):
        return replay
    goal, topics, _ = _graph(uow, owner_id, goal_id)
    _require_topic(topics, body.topic_stable_id)
    _append_entry(
        uow,
        owner_id,
        goal,
        OverlayEntryType.DEPTH,
        body.topic_stable_id,
        {"depth": body.depth},
        body.reason,
    )
    return _save(uow, owner_id, goal_id, operation, key, request_hash)


def _replay(
    uow: RoadmapUnitOfWork, owner_id: str, operation: str, key: str, request_hash: str
) -> RoadmapMutationResponse | None:
    prior = uow.roadmap.get_idempotency(owner_id, operation, key)
    if prior is None:
        return None
    if prior.request_hash != request_hash:
        raise IdempotencyConflictError(
            "The Idempotency-Key was reused with a different roadmap command."
        )
    return RoadmapMutationResponse.model_validate_json(prior.response_json)


def _save(
    uow: RoadmapUnitOfWork,
    owner_id: str,
    goal_id: str,
    operation: str,
    key: str,
    request_hash: str,
) -> RoadmapMutationResponse:
    response = RoadmapMutationResponse(
        projection=_projection_response(uow, owner_id, goal_id)
    )
    uow.roadmap.add_idempotency(
        RoadmapIdempotencyRecord(
            id=new_id(),
            owner_id=owner_id,
            goal_id=goal_id,
            operation=operation,
            idempotency_key=key,
            request_hash=request_hash,
            response_json=response.model_dump_json(),
            created_at=now_text(SystemClock()),
        )
    )
    uow.commit()
    return response


def _append_entry(
    uow: RoadmapUnitOfWork,
    owner_id: str,
    goal: GoalView,
    entry_type: OverlayEntryType,
    topic_id: str | None,
    value: dict[str, object],
    reason: str | None,
    *,
    supersedes_entry_id: str | None = None,
) -> None:
    overlay = uow.roadmap.get_or_create_overlay(
        owner_id, goal.id, goal.graph_version_id
    )
    now = now_text(SystemClock())
    prior = [
        item
        for item in uow.roadmap.list_overlay_entries(owner_id, goal.id)
        if item.entry_type is entry_type and item.topic_stable_id == topic_id
    ]
    payload = {
        "entry_type": entry_type.value,
        "topic_stable_id": topic_id,
        "value": value,
        "approved_at": now,
    }
    uow.roadmap.append_overlay_entry(
        OverlayEntry(
            id=new_id(),
            owner_id=owner_id,
            goal_id=goal.id,
            overlay_id=overlay.id,
            graph_version_id=goal.graph_version_id,
            topic_stable_id=topic_id,
            entry_type=entry_type,
            value=dict(value),
            reason=reason,
            source="learner",
            approved_at=now,
            supersedes_entry_id=(
                supersedes_entry_id
                if entry_type is OverlayEntryType.ORDER_CONSTRAINT
                else prior[-1].id
                if prior
                else None
            ),
            content_hash=hash_payload(payload),
        )
    )


def _projection_response(
    uow: RoadmapUnitOfWork, owner_id: str, goal_id: str
) -> RoadmapResponse:
    goal, topics, relations = _graph(uow, owner_id, goal_id)
    projection = project_roadmap(
        graph_version_id=goal.graph_version_id,
        topics=_topics(topics),
        prerequisite_relations=_prerequisites(relations),
        overlay_entries=uow.roadmap.list_overlay_entries(owner_id, goal_id),
        learning_states=uow.roadmap.list_learning_states(owner_id, goal_id),
        corrections=uow.roadmap.list_corrections(owner_id, goal_id),
        transferred_evidence_topic_ids=uow.roadmap.list_transferred_evidence_topic_ids(
            owner_id, goal_id
        ),
    )
    versions = uow.canonical.list_published_versions()
    stale = bool(versions and versions[0].id != goal.graph_version_id)
    return RoadmapResponse(
        goal_id=goal_id,
        graph_version_id=projection.graph_version_id,
        projection_version=projection.projection_version,
        state="stale-canonical-version" if stale else "ready",
        topics=[
            RoadmapTopicResponse(
                **{
                    **item.__dict__,
                    "scope_tags": list(item.scope_tags),
                    "pending_proposals": list(item.pending_proposals),
                    "conflicts": list(item.conflicts),
                }
            )
            for item in projection.topics
        ],
    )


def _goal(uow: RoadmapUnitOfWork, owner_id: str, goal_id: str) -> GoalView:
    goal = uow.profiles_goals.get_goal(owner_id, goal_id)
    if goal is None:
        raise NotFoundError("Goal workspace not found.")
    return goal


def _graph(
    uow: RoadmapUnitOfWork, owner_id: str, goal_id: str
) -> tuple[GoalView, Sequence[CanonicalTopicView], Sequence[CanonicalRelationView]]:
    goal = _goal(uow, owner_id, goal_id)
    if uow.canonical.get_published_version(goal.graph_version_id) is None:
        raise NotFoundError("The goal's approved canonical graph is unavailable.")
    return (
        goal,
        uow.canonical.get_published_topics(goal.graph_version_id),
        uow.canonical.get_published_relations(goal.graph_version_id),
    )


def _topics(topics: Sequence[CanonicalTopicView]) -> tuple[RoadmapTopic, ...]:
    return tuple(
        RoadmapTopic(
            item.stable_id,
            item.title,
            item.subject,
            item.scope_tags,
            item.level_tag,
            item.target_capability,
            item.recommended_layer,
        )
        for item in topics
    )


def _prerequisites(
    relations: Sequence[CanonicalRelationView],
) -> tuple[RoadmapRelation, ...]:
    return tuple(
        RoadmapRelation(item.from_stable_id, item.to_stable_id)
        for item in relations
        if str(item.relation_type) == "prerequisite"
    )


def _require_topic(topics: Sequence[CanonicalTopicView], topic_id: str) -> None:
    if all(item.stable_id != topic_id for item in topics):
        raise NotFoundError("Topic not found in the goal's pinned graph.")
