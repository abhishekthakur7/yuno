"""Topic content routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from yuno.api.contracts import (
    JobRefResponse,
    TopicCheckpointResponse,
    TopicDetailResponse,
    TopicLayerResponse,
    TopicLayersResponse,
    accepted_job,
)
from yuno.api.dependencies import (
    get_job_dispatcher,
    get_owner_id,
    get_unit_of_work,
    idempotency_key,
)
from yuno.modules.learning_content.domain import LayerDocument, TopicLayer
from yuno.modules.learning_content.ports import LearningContentUnitOfWork
from yuno.modules.learning_content.service import get_layer, get_topic, list_layers
from yuno.shared.application.jobs import JobDispatcher, JobRequest
from yuno.shared.domain.errors import NotFoundError

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
) -> TopicLayersResponse:
    goal = uow.profiles_goals.get_goal(owner_id, goal_id)
    if goal is None:
        raise NotFoundError(f"Goal '{goal_id}' was not found.")
    layers = list_layers(uow, owner_id, goal_id, topic_id)
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
) -> TopicLayerResponse:
    return _layer_response(get_layer(uow, owner_id, goal_id, topic_id, layer))


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
    list_layers(uow, owner_id, goal_id, topic_id)
    return accepted_job(
        dispatcher.enqueue(
            JobRequest(
                kind="generate_topic_content",
                owner_id=owner_id,
                payload={
                    "goal_id": goal_id,
                    "topic_id": topic_id,
                    "layer": layer.value,
                },
                dedupe_key=f"{goal_id}:{topic_id}:{layer.value}",
                idempotency_key=key,
            )
        )
    )


@router.post(
    "/artifacts/{artifact_id}/regenerate",
    response_model=JobRefResponse,
    status_code=202,
)
def regenerate_artifact(
    artifact_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
    key: Annotated[str, Depends(idempotency_key)],
) -> JSONResponse:
    return accepted_job(
        dispatcher.enqueue(
            JobRequest(
                kind="regenerate_artifact",
                owner_id=owner_id,
                payload={"artifact_id": artifact_id},
                dedupe_key=artifact_id,
                idempotency_key=key,
            )
        )
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
    )
