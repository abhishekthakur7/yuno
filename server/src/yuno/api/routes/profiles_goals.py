"""Profile and goal workspace HTTP contracts (IDK-104)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from yuno.api.contracts import (
    GoalCreateRequest,
    GoalDeleteImpactResponse,
    GoalDeleteRequest,
    GoalPatchRequest,
    GoalResponse,
    LearnerProfilePatchRequest,
    LearnerProfileResponse,
)
from yuno.api.dependencies import (
    get_owner_id,
    get_unit_of_work,
    idempotency_key,
    if_match,
    parse_if_match,
)
from yuno.modules.evidence_evaluation.domain import DeleteImpact
from yuno.modules.evidence_evaluation.ports import EvidenceUnitOfWork
from yuno.modules.evidence_evaluation.service import (
    create_delete_preflight,
    delete_goal,
)
from yuno.modules.profiles_goals.domain import (
    GoalWorkspace,
    IdempotencyRecord,
    LearnerProfile,
)
from yuno.modules.profiles_goals.ports import ProfilesGoalsUnitOfWork
from yuno.modules.profiles_goals.service import (
    archive_goal,
    create_goal,
    patch_goal,
    patch_profile,
)
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.errors import (
    IdempotencyConflictError,
    NotFoundError,
    UnavailableError,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id

router = APIRouter(tags=["profiles-goals"])


@router.get("/profile", response_model=LearnerProfileResponse)
def get_profile(
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[ProfilesGoalsUnitOfWork, Depends(get_unit_of_work)],
) -> LearnerProfileResponse:
    return _profile_response(_profile_or_unavailable(uow, owner_id))


@router.patch("/profile", response_model=LearnerProfileResponse)
def update_profile(
    body: LearnerProfilePatchRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[ProfilesGoalsUnitOfWork, Depends(get_unit_of_work)],
    match: Annotated[str, Depends(if_match)],
) -> LearnerProfileResponse:
    profile = patch_profile(
        uow, owner_id, parse_if_match(match), body.model_dump(exclude_unset=True)
    )
    uow.commit()
    return _profile_response(profile)


@router.get("/goals", response_model=list[GoalResponse])
def list_goals(
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[ProfilesGoalsUnitOfWork, Depends(get_unit_of_work)],
) -> list[GoalResponse]:
    _profile_or_unavailable(uow, owner_id)
    return [
        _goal_response(uow, goal) for goal in uow.profiles_goals.list_goals(owner_id)
    ]


@router.post("/goals", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def post_goal(
    body: GoalCreateRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[ProfilesGoalsUnitOfWork, Depends(get_unit_of_work)],
    key: Annotated[str, Depends(idempotency_key)],
) -> GoalResponse:
    _profile_or_unavailable(uow, owner_id)
    uow.profiles_goals.lock_idempotency_commands(owner_id)
    request_hash = hash_payload(body.model_dump(mode="json"))
    prior = uow.profiles_goals.get_idempotency(owner_id, "create_goal", key)
    if prior is not None:
        if prior.request_hash != request_hash:
            raise IdempotencyConflictError(
                "The Idempotency-Key was reused with a different goal request."
            )
        return GoalResponse.model_validate_json(prior.response_json)
    approved_graph_exists = (
        uow.canonical.get_published_version(body.graph_version_id) is not None
    )
    goal = create_goal(
        uow, owner_id, **body.model_dump(), approved_graph_exists=approved_graph_exists
    )
    response = _goal_response(uow, goal)
    response_json = response.model_dump_json()
    uow.profiles_goals.add_idempotency(
        IdempotencyRecord(
            id=new_id(),
            owner_id=owner_id,
            operation="create_goal",
            idempotency_key=key,
            request_hash=request_hash,
            goal_id=goal.id,
            response_json=response_json,
            created_at=now_text(SystemClock()),
        )
    )
    uow.commit()
    return response


@router.get("/goals/{goal_id}", response_model=GoalResponse)
def get_goal(
    goal_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[ProfilesGoalsUnitOfWork, Depends(get_unit_of_work)],
) -> GoalResponse:
    _profile_or_unavailable(uow, owner_id)
    goal = uow.profiles_goals.get_goal(owner_id, goal_id)
    if goal is None:
        raise NotFoundError(f"Goal '{goal_id}' was not found.")
    return _goal_response(uow, goal)


@router.patch("/goals/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: str,
    body: GoalPatchRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[ProfilesGoalsUnitOfWork, Depends(get_unit_of_work)],
    match: Annotated[str, Depends(if_match)],
) -> GoalResponse:
    _profile_or_unavailable(uow, owner_id)
    stored_goal = uow.profiles_goals.get_goal(owner_id, goal_id)
    if stored_goal is None:
        raise NotFoundError(f"Goal '{goal_id}' was not found.")
    if uow.canonical.get_published_version(stored_goal.graph_version_id) is None:
        raise UnavailableError("The goal's approved canonical graph is unavailable.")
    changes = body.model_dump(
        exclude_unset=True,
        exclude={"set_current", "resume_destination", "dismiss_recommendation_key"},
    )
    goal = patch_goal(
        uow,
        owner_id,
        goal_id,
        parse_if_match(match),
        changes,
        set_current=body.set_current is True,
        resume_destination=body.resume_destination,
        dismiss_recommendation_key=body.dismiss_recommendation_key,
        published_topic_ids=frozenset(
            topic.stable_id
            for topic in uow.canonical.get_published_topics(
                stored_goal.graph_version_id
            )
        ),
    )
    response = _goal_response(uow, goal)
    uow.commit()
    return response


@router.post("/goals/{goal_id}/archive", response_model=GoalResponse)
def post_archive_goal(
    goal_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[ProfilesGoalsUnitOfWork, Depends(get_unit_of_work)],
    match: Annotated[str, Depends(if_match)],
    key: Annotated[str, Depends(idempotency_key)],
) -> GoalResponse:
    _profile_or_unavailable(uow, owner_id)
    uow.profiles_goals.lock_idempotency_commands(owner_id)
    expected_version = parse_if_match(match)
    operation = f"archive_goal:{goal_id}"
    request_hash = hash_payload(
        {"goal_id": goal_id, "expected_version": expected_version}
    )
    prior = uow.profiles_goals.get_idempotency(owner_id, operation, key)
    if prior is not None:
        if prior.request_hash != request_hash:
            raise IdempotencyConflictError(
                "The Idempotency-Key was reused with a different archive request."
            )
        return GoalResponse.model_validate_json(prior.response_json)
    goal = archive_goal(uow, owner_id, goal_id, expected_version)
    response = _goal_response(uow, goal)
    uow.profiles_goals.add_idempotency(
        IdempotencyRecord(
            id=new_id(),
            owner_id=owner_id,
            operation=operation,
            idempotency_key=key,
            request_hash=request_hash,
            goal_id=goal.id,
            response_json=response.model_dump_json(),
            created_at=now_text(SystemClock()),
        )
    )
    uow.commit()
    return response


@router.post(
    "/goals/{goal_id}/delete-preflight", response_model=GoalDeleteImpactResponse
)
def post_goal_delete_preflight(
    goal_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[EvidenceUnitOfWork, Depends(get_unit_of_work)],
    key: Annotated[str, Depends(idempotency_key)],
) -> GoalDeleteImpactResponse:
    uow.profiles_goals.lock_idempotency_commands(owner_id)
    operation = f"delete_preflight:{goal_id}"
    request_hash = hash_payload({"goal_id": goal_id})
    prior = uow.profiles_goals.get_idempotency(owner_id, operation, key)
    if prior is not None:
        if prior.request_hash != request_hash:
            raise IdempotencyConflictError(
                "The Idempotency-Key was reused with a different preflight request."
            )
        return GoalDeleteImpactResponse.model_validate_json(prior.response_json)
    impact = create_delete_preflight(uow, owner_id, goal_id)
    response = _delete_impact_response(impact)
    uow.profiles_goals.add_idempotency(
        IdempotencyRecord(
            id=new_id(),
            owner_id=owner_id,
            operation=operation,
            idempotency_key=key,
            request_hash=request_hash,
            goal_id=goal_id,
            response_json=response.model_dump_json(),
            created_at=now_text(SystemClock()),
        )
    )
    uow.commit()
    return response


@router.post("/goals/{goal_id}/delete", response_model=GoalDeleteImpactResponse)
def post_goal_delete(
    goal_id: str,
    body: GoalDeleteRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[EvidenceUnitOfWork, Depends(get_unit_of_work)],
    key: Annotated[str, Depends(idempotency_key)],
) -> GoalDeleteImpactResponse:
    uow.profiles_goals.lock_idempotency_commands(owner_id)
    operation = f"delete_goal:{goal_id}"
    request_hash = hash_payload({"goal_id": goal_id, "snapshot_id": body.snapshot_id})
    prior = uow.profiles_goals.get_idempotency(owner_id, operation, key)
    if prior is not None:
        if prior.request_hash != request_hash:
            raise IdempotencyConflictError(
                "The Idempotency-Key was reused with a different delete request."
            )
        return GoalDeleteImpactResponse.model_validate_json(prior.response_json)
    impact = delete_goal(uow, owner_id, goal_id, body.snapshot_id)
    response = _delete_impact_response(impact)
    uow.profiles_goals.add_idempotency(
        IdempotencyRecord(
            id=new_id(),
            owner_id=owner_id,
            operation=operation,
            idempotency_key=key,
            request_hash=request_hash,
            goal_id=goal_id,
            response_json=response.model_dump_json(),
            created_at=now_text(SystemClock()),
        )
    )
    uow.commit()
    return response


def _delete_impact_response(impact: DeleteImpact) -> GoalDeleteImpactResponse:
    return GoalDeleteImpactResponse(
        snapshot_id=impact.snapshot_id,
        goal_id=impact.goal_id,
        evidence_ids=list(impact.evidence_ids),
        learning_state_ids=list(impact.learning_state_ids),
    )


def _profile_response(profile: LearnerProfile) -> LearnerProfileResponse:
    return LearnerProfileResponse(
        experience=profile.experience,
        strengths=profile.strengths,
        weaknesses=profile.weaknesses,
        current_goal_id=profile.current_goal_id,
        profile_revision=profile.profile_revision,
        updated_at=profile.updated_at,
    )


def _profile_or_unavailable(
    uow: ProfilesGoalsUnitOfWork, owner_id: str
) -> LearnerProfile:
    profile = uow.profiles_goals.get_profile(owner_id)
    if profile is None:
        raise UnavailableError(
            "The learner profile is unavailable; retry after recovery."
        )
    return profile


def _goal_response(uow: ProfilesGoalsUnitOfWork, goal: GoalWorkspace) -> GoalResponse:
    dismissed = uow.profiles_goals.list_dismissals(goal.owner_id, goal.id)
    navigation = uow.profiles_goals.list_navigation(goal.owner_id, goal.id)
    return GoalResponse(
        id=goal.id,
        name=goal.name,
        path=goal.path,
        subject=goal.subject,
        role=goal.role,
        target_level=goal.target_level,
        target_capability=goal.target_capability,
        graph_version_id=goal.graph_version_id,
        status=goal.status,
        resume_position=goal.resume_position,
        resume_destination=navigation[-1].destination if navigation else None,
        last_accessed_at=goal.last_accessed_at,
        dismissed_recommendation_keys=[item.recommendation_key for item in dismissed],
        row_version=goal.row_version,
        created_at=goal.created_at,
        updated_at=goal.updated_at,
    )
