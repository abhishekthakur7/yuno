"""Interfaces for reading topic content."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from yuno.shared.application.unit_of_work import UnitOfWork


class TopicView(Protocol):
    graph_version_id: str
    stable_id: str
    title: str
    subject: str
    scope_tags: tuple[str, ...]
    level_tag: str
    target_capability: str
    recommended_layer: str


class ContentRevisionView(Protocol):
    id: str
    layer: str
    kind: str
    markdown_ref: str
    markdown_hash: str


class GoalView(Protocol):
    graph_version_id: str


class CanonicalContentRepository(Protocol):
    def get_published_version(self, version_id: str) -> object | None: ...
    def get_published_topics(self, version_id: str) -> Sequence[TopicView]: ...
    def get_published_content_revisions(
        self, version_id: str, topic_stable_id: str
    ) -> Sequence[ContentRevisionView]: ...


class GoalRepository(Protocol):
    def get_goal(self, owner_id: str, goal_id: str) -> GoalView | None: ...


class LearningContentUnitOfWork(UnitOfWork, Protocol):
    canonical: CanonicalContentRepository
    profiles_goals: GoalRepository
