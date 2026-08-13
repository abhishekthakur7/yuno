"""Topic content routes."""

from __future__ import annotations

from dataclasses import replace
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from yuno.api.contracts import (
    JobRefResponse,
    TopicCheckpointResponse,
    TopicConversationTurnResponse,
    TopicDetailResponse,
    TopicLayerResponse,
    TopicLayersResponse,
    TutorTurnRequest,
    accepted_job,
)
from yuno.api.dependencies import (
    get_job_dispatcher,
    get_owner_id,
    get_unit_of_work,
    idempotency_key,
)
from yuno.api.provider_selection import (
    authorize_provider_job,
    selected_provider_metadata,
)
from yuno.modules.learning_content.domain import (
    GenerationAttempt,
    LayerDocument,
    TopicLayer,
)
from yuno.modules.learning_content.ports import LearningContentUnitOfWork
from yuno.modules.learning_content.service import (
    find_generation_replay,
    get_topic,
    list_layers,
    list_topic_conversation,
    reserve_generation,
    reserve_tutor_turn,
)
from yuno.shared.application.jobs import JobDispatcher, JobLane, JobRef, JobRequest
from yuno.shared.domain.errors import NotFoundError
from yuno.shared.domain.ids import new_id

router = APIRouter(tags=["learning-content"])


@router.get("/topics/{topic_id}", response_model=TopicDetailResponse)
def get_topic_detail(
    topic_id: str,
    graph_version_id: Annotated[str, Query(alias="graph_version")],
    uow: Annotated[LearningContentUnitOfWork, Depends(get_unit_of_work)],
) -> TopicDetailResponse:
    topic = get_topic(uow, graph_version_id, topic_id)
    return TopicDetailResponse(
        graph_version_id=topic.graph_version_id,
        stable_id=topic.stable_id,
        title=topic.title,
        subject=topic.subject,
        scope_tags=list(topic.scope_tags),
        level_tag=topic.level_tag,
        target_capability=topic.target_capability,
        recommended_layer=topic.recommended_layer,
    )


@router.get(
    "/goals/{goal_id}/topics/{topic_id}/layers",
    response_model=TopicLayersResponse,
)
def get_topic_layers(
    goal_id: str,
    topic_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[LearningContentUnitOfWork, Depends(get_unit_of_work)],
    request: Request,
) -> TopicLayersResponse:
    goal = uow.profiles_goals.get_goal(owner_id, goal_id)
    if goal is None:
        raise NotFoundError(f"Goal '{goal_id}' was not found.")
    provider, model = selected_provider_metadata(
        uow, owner_id, request.app.state.provider_registry
    )
    layers = list_layers(
        uow,
        owner_id,
        goal_id,
        topic_id,
        provider,
        model,
    )
    return TopicLayersResponse(
        goal_id=goal_id,
        graph_version_id=goal.graph_version_id,
        topic_id=topic_id,
        conversation_scope=f"{goal_id}:{topic_id}",
        layers=[_layer_response(layer) for layer in layers],
    )


@router.get(
    "/goals/{goal_id}/topics/{topic_id}/layers/{layer}",
    response_model=TopicLayerResponse,
)
def get_topic_layer(
    goal_id: str,
    topic_id: str,
    layer: TopicLayer,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[LearningContentUnitOfWork, Depends(get_unit_of_work)],
    request: Request,
) -> TopicLayerResponse:
    provider, model = selected_provider_metadata(
        uow, owner_id, request.app.state.provider_registry
    )
    return _layer_response(
        next(
            item
            for item in list_layers(
                uow,
                owner_id,
                goal_id,
                topic_id,
                provider,
                model,
            )
            if item.layer is layer
        )
    )


@router.get(
    "/goals/{goal_id}/topics/{topic_id}/conversation",
    response_model=list[TopicConversationTurnResponse],
)
def get_topic_conversation(
    goal_id: str,
    topic_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[LearningContentUnitOfWork, Depends(get_unit_of_work)],
) -> list[TopicConversationTurnResponse]:
    return [
        _conversation_response(turn)
        for turn in list_topic_conversation(uow, owner_id, goal_id, topic_id)
    ]


@router.post(
    "/goals/{goal_id}/topics/{topic_id}/conversation",
    response_model=JobRefResponse,
    status_code=202,
)
def post_topic_conversation(
    goal_id: str,
    topic_id: str,
    body: TutorTurnRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[LearningContentUnitOfWork, Depends(get_unit_of_work)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
    key: Annotated[str, Depends(idempotency_key)],
) -> JSONResponse:
    prior = uow.learning_content.get_conversation_turn_by_idempotency(owner_id, key)
    if prior is not None:
        turn, _ = reserve_tutor_turn(
            uow,
            owner_id,
            goal_id,
            topic_id,
            body.message,
            key,
            prior.job_id or new_id(),
        )
        assert turn.job_id is not None
        current = dispatcher.get(owner_id, turn.job_id)
        if current is not None:
            return accepted_job(current)
    list_topic_conversation(uow, owner_id, goal_id, topic_id)
    authorization = authorize_provider_job(dispatcher, uow, owner_id)
    disclosure = authorization.disclosure
    turn, _ = reserve_tutor_turn(
        uow,
        owner_id,
        goal_id,
        topic_id,
        body.message,
        key,
        new_id(),
    )
    assert turn.job_id is not None
    ref = dispatcher.reserve(
        uow,
        JobRequest(
            "tutor_turn",
            owner_id,
            {"learner_turn_id": turn.id},
            dedupe_key=turn.id,
            idempotency_key=key,
            requested_job_id=turn.job_id,
            goal_id=goal_id,
            lane=JobLane.INTERACTIVE,
            schema_version="tutor-turn-v1",
            request_ref=f"TopicConversationTurn:{turn.id}",
            disclosure_ref=disclosure.id,
            provider_name=authorization.provider.value,
            run_id=f"{goal_id}:{topic_id}",
        ),
    )
    uow.commit()
    return accepted_job(ref)


@router.post(
    "/goals/{goal_id}/topics/{topic_id}/generate",
    response_model=JobRefResponse,
    status_code=202,
)
def generate_topic_layer(
    goal_id: str,
    topic_id: str,
    layer: TopicLayer,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[LearningContentUnitOfWork, Depends(get_unit_of_work)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
    key: Annotated[str, Depends(idempotency_key)],
) -> JSONResponse:
    replay = find_generation_replay(uow, owner_id, goal_id, topic_id, layer, key)
    if replay is not None:
        if replay[2]:
            current = dispatcher.get(owner_id, replay[0].job_id)
            if current is not None:
                return accepted_job(replace(current, deduplicated=True))
            authorization = authorize_provider_job(dispatcher, uow, owner_id)
            ref = _reserve_generation_job(
                uow,
                replay[0],
                replay[1],
                True,
                dispatcher,
                owner_id,
                key,
                authorization.disclosure.id,
                authorization.provider.value,
            )
            uow.commit()
            return accepted_job(ref)
        return accepted_job(replay[0])
    authorization = authorize_provider_job(dispatcher, uow, owner_id)
    ref, attempt, dispatch = reserve_generation(
        uow, owner_id, goal_id, topic_id, layer, key
    )
    accepted = _reserve_generation_job(
        uow,
        ref,
        attempt,
        dispatch,
        dispatcher,
        owner_id,
        key,
        authorization.disclosure.id,
        authorization.provider.value,
    )
    uow.commit()
    return accepted_job(accepted)


@router.post(
    "/artifacts/{artifact_id}/regenerate",
    response_model=JobRefResponse,
    status_code=202,
)
def regenerate_artifact(
    artifact_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[LearningContentUnitOfWork, Depends(get_unit_of_work)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
    key: Annotated[str, Depends(idempotency_key)],
) -> JSONResponse:
    artifact = uow.learning_content.get_artifact(owner_id, artifact_id)
    if artifact is None:
        raise NotFoundError("The generated artifact was not found.")
    replay = find_generation_replay(
        uow,
        owner_id,
        artifact.goal_id,
        artifact.topic_stable_id,
        artifact.layer,
        key,
        force=True,
    )
    if replay is not None:
        if replay[2]:
            current = dispatcher.get(owner_id, replay[0].job_id)
            if current is not None:
                return accepted_job(replace(current, deduplicated=True))
            authorization = authorize_provider_job(dispatcher, uow, owner_id)
            ref = _reserve_generation_job(
                uow,
                replay[0],
                replay[1],
                True,
                dispatcher,
                owner_id,
                key,
                authorization.disclosure.id,
                authorization.provider.value,
            )
            uow.commit()
            return accepted_job(ref)
        return accepted_job(replay[0])
    authorization = authorize_provider_job(dispatcher, uow, owner_id)
    ref, attempt, dispatch = reserve_generation(
        uow,
        owner_id,
        artifact.goal_id,
        artifact.topic_stable_id,
        artifact.layer,
        key,
        force=True,
    )
    accepted = _reserve_generation_job(
        uow,
        ref,
        attempt,
        dispatch,
        dispatcher,
        owner_id,
        key,
        authorization.disclosure.id,
        authorization.provider.value,
    )
    uow.commit()
    return accepted_job(accepted)


def _reserve_generation_job(
    uow: LearningContentUnitOfWork,
    ref: JobRef,
    attempt: GenerationAttempt,
    dispatch: bool,
    dispatcher: JobDispatcher,
    owner_id: str,
    key: str,
    disclosure_ref: str,
    provider_name: str,
) -> JobRef:
    if not dispatch:
        return ref
    return dispatcher.reserve(
        uow,
        JobRequest(
            "generate_topic_content",
            owner_id,
            {"attempt_id": attempt.id},
            attempt.artifact_id,
            key,
            requested_job_id=attempt.job_id,
            goal_id=attempt.goal_id,
            lane=JobLane.BACKGROUND,
            schema_version="provider-job-v1",
            request_ref=f"GenerationAttempt:{attempt.id}",
            disclosure_ref=disclosure_ref,
            provider_name=provider_name,
        ),
    )


def _layer_response(layer: LayerDocument) -> TopicLayerResponse:
    checkpoint = layer.checkpoint
    return TopicLayerResponse(
        layer=layer.layer,
        state=layer.state,
        revision_id=layer.revision_id,
        markdown=layer.markdown,
        markdown_hash=layer.markdown_hash,
        checkpoint=(
            TopicCheckpointResponse(
                scenario=checkpoint.scenario,
                constraints=list(checkpoint.constraints),
                target_capability=checkpoint.target_capability,
                expected_artifact=checkpoint.expected_artifact,
                estimated_minutes=checkpoint.estimated_minutes,
                rubric=list(checkpoint.rubric),
                assumptions=list(checkpoint.assumptions),
                evidence_criterion=checkpoint.evidence_criterion,
                limitation=checkpoint.limitation,
            )
            if checkpoint is not None
            else None
        ),
        artifact_id=layer.artifact_id,
        content_origin=layer.content_origin,
        generation=layer.generation,
        stale_reason=layer.stale_reason,
    )


def _conversation_response(turn) -> TopicConversationTurnResponse:
    return TopicConversationTurnResponse(
        id=turn.id,
        goal_id=turn.goal_id,
        topic_id=turn.topic_stable_id,
        role=turn.role,
        body=turn.body,
        response_to_id=turn.response_to_id,
        job_id=turn.job_id,
        created_at=turn.created_at,
    )
