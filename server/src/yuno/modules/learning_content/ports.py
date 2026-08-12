"""Structural ports for authored and generated learning content."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from yuno.modules.learning_content.domain import (
    GeneratedArtifact,
    GenerateRequest,
    GenerateResult,
    GenerationAttempt,
    GenerationIdempotencyRecord,
)
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
    prompt_template_version: str | None


class GoalView(Protocol):
    graph_version_id: str


class ProfileView(Protocol):
    profile_revision: int
    experience: str | None
    strengths: str | None
    weaknesses: str | None


class ImportHashView(Protocol):
    imports_hash: str


class EvidenceView(Protocol):
    id: str
    payload_hash: str


class StateView(Protocol):
    input_hash: str


class CanonicalContentRepository(Protocol):
    def get_published_version(self, version_id: str) -> object | None: ...
    def get_published_topics(self, version_id: str) -> Sequence[TopicView]: ...
    def get_published_content_revisions(
        self, version_id: str, topic_stable_id: str
    ) -> Sequence[ContentRevisionView]: ...


class GoalRepository(Protocol):
    def get_goal(self, owner_id: str, goal_id: str) -> GoalView | None: ...
    def get_profile(self, owner_id: str) -> ProfileView | None: ...


class ImportRepository(Protocol):
    def get_topic_hash(
        self, owner_id: str, goal_id: str, graph_version_id: str, topic_stable_id: str
    ) -> ImportHashView | None: ...


class EvidenceRepository(Protocol):
    def list_evidence(self, owner_id: str, goal_id: str) -> Sequence[EvidenceView]: ...
    def get_progress_memo(self, owner_id: str, goal_id: str) -> StateView | None: ...


class RoadmapRepository(Protocol):
    def list_corrections(self, owner_id: str, goal_id: str) -> Sequence[object]: ...
    def list_learning_states(self, owner_id: str, goal_id: str) -> Sequence[object]: ...


class LearningContentRepository(Protocol):
    def get_artifact_by_key(
        self,
        owner_id: str,
        graph_version_id: str,
        topic_id: str,
        goal_id: str,
        layer: str,
        imports_hash: str,
        template_version: str,
    ) -> GeneratedArtifact | None: ...
    def get_artifact(
        self, owner_id: str, artifact_id: str
    ) -> GeneratedArtifact | None: ...
    def get_latest_artifact(
        self, owner_id: str, goal_id: str, topic_id: str, layer: str
    ) -> GeneratedArtifact | None: ...
    def list_artifacts(
        self, owner_id: str, goal_id: str, layer: str
    ) -> Sequence[GeneratedArtifact]: ...
    def add_artifact(self, artifact: GeneratedArtifact) -> GeneratedArtifact: ...
    def update_artifact(
        self, owner_id: str, artifact_id: str, changes: dict[str, object]
    ) -> GeneratedArtifact: ...
    def add_attempt(self, attempt: GenerationAttempt) -> GenerationAttempt: ...
    def get_attempt(
        self, owner_id: str, attempt_id: str
    ) -> GenerationAttempt | None: ...
    def get_active_attempt(
        self, owner_id: str, artifact_id: str
    ) -> GenerationAttempt | None: ...
    def update_attempt(
        self,
        owner_id: str,
        attempt_id: str,
        expected_status: str,
        changes: dict[str, object],
    ) -> GenerationAttempt: ...
    def get_idempotency(
        self, owner_id: str, operation: str, key: str
    ) -> GenerationIdempotencyRecord | None: ...
    def get_idempotency_by_key(
        self, owner_id: str, key: str
    ) -> GenerationIdempotencyRecord | None: ...
    def add_idempotency(
        self, record: GenerationIdempotencyRecord
    ) -> GenerationIdempotencyRecord: ...
    def add_quarantine(self, **values: object) -> None: ...


class GenerationAdapter(Protocol):
    def generate(self, request: GenerateRequest) -> GenerateResult: ...


class ProvenanceRepository(Protocol):
    def add_generation_result(
        self,
        snapshot: object,
        refs: Sequence[object],
        claims: Sequence[tuple[object, Sequence[object]]],
    ) -> None: ...
    def get_artifact_snapshot(
        self, owner_id: str, snapshot_id: str
    ) -> object | None: ...


class LearningContentUnitOfWork(UnitOfWork, Protocol):
    canonical: CanonicalContentRepository
    profiles_goals: GoalRepository
    imports: ImportRepository
    evidence: EvidenceRepository
    roadmap: RoadmapRepository
    learning_content: LearningContentRepository
    provenance: ProvenanceRepository
