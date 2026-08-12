"""Topic and layer queries."""

from __future__ import annotations

import json
from collections.abc import Sequence
from urllib.parse import unquote

from yuno.modules.learning_content.domain import (
    Capability,
    Checkpoint,
    LayerDocument,
    LayerState,
    TopicLayer,
    validate_checkpoint,
)
from yuno.modules.learning_content.ports import (
    ContentRevisionView,
    LearningContentUnitOfWork,
    TopicView,
)
from yuno.shared.domain.errors import DomainValidationError, NotFoundError


def get_topic(
    uow: LearningContentUnitOfWork, graph_version_id: str, topic_id: str
) -> TopicView:
    if uow.canonical.get_published_version(graph_version_id) is None:
        raise NotFoundError("The approved canonical graph version was not found.")
    topic = next(
        (
            item
            for item in uow.canonical.get_published_topics(graph_version_id)
            if item.stable_id == topic_id
        ),
        None,
    )
    if topic is None:
        raise NotFoundError(f"Topic '{topic_id}' was not found in the approved graph.")
    return topic


def list_layers(
    uow: LearningContentUnitOfWork,
    owner_id: str,
    goal_id: str,
    topic_id: str,
) -> tuple[LayerDocument, ...]:
    goal = uow.profiles_goals.get_goal(owner_id, goal_id)
    if goal is None:
        raise NotFoundError(f"Goal '{goal_id}' was not found.")
    get_topic(uow, goal.graph_version_id, topic_id)
    revisions = uow.canonical.get_published_content_revisions(
        goal.graph_version_id, topic_id
    )
    return tuple(_layer_document(layer, revisions) for layer in TopicLayer)


def get_layer(
    uow: LearningContentUnitOfWork,
    owner_id: str,
    goal_id: str,
    topic_id: str,
    layer: TopicLayer,
) -> LayerDocument:
    return next(
        item
        for item in list_layers(uow, owner_id, goal_id, topic_id)
        if item.layer is layer
    )


def _layer_document(
    layer: TopicLayer,
    revisions: Sequence[ContentRevisionView],
) -> LayerDocument:
    matches = [item for item in revisions if item.layer == layer.value]
    content = next((item for item in reversed(matches) if item.kind == "layer"), None)
    checkpoint_revision = next(
        (item for item in reversed(matches) if item.kind == "checkpoint"), None
    )
    if content is None:
        return LayerDocument(layer, LayerState.EMPTY, None, None, None, None)
    markdown = _inline_value(content)
    if markdown is None:
        return LayerDocument(
            layer, LayerState.UNAVAILABLE, content.id, None, content.markdown_hash, None
        )
    try:
        checkpoint = (
            _checkpoint(_inline_value(checkpoint_revision))
            if checkpoint_revision is not None
            else None
        )
    except DomainValidationError:
        return LayerDocument(
            layer,
            LayerState.UNAVAILABLE,
            content.id,
            markdown,
            content.markdown_hash,
            None,
        )
    return LayerDocument(
        layer,
        LayerState.READY,
        content.id,
        markdown,
        content.markdown_hash,
        checkpoint,
    )


def _inline_value(revision: ContentRevisionView | None) -> str | None:
    if revision is None or not revision.markdown_ref.startswith("inline:"):
        return None
    return unquote(revision.markdown_ref.removeprefix("inline:"))


def _checkpoint(raw: str | None) -> Checkpoint:
    if raw is None:
        raise DomainValidationError("Checkpoint content is unavailable.")
    try:
        data = json.loads(raw)
        checkpoint = Checkpoint(
            scenario=str(data["scenario"]),
            constraints=tuple(str(item) for item in data["constraints"]),
            target_capability=Capability(str(data["target_capability"])),
            expected_artifact=str(data["expected_artifact"]),
            estimated_minutes=int(data["estimated_minutes"]),
            rubric=tuple(str(item) for item in data["rubric"]),
            assumptions=tuple(str(item) for item in data["assumptions"]),
            evidence_criterion=str(data["evidence_criterion"]),
            limitation=str(data["limitation"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise DomainValidationError("Checkpoint content is invalid.") from exc
    validate_checkpoint(checkpoint)
    return checkpoint
