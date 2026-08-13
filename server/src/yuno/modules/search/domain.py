from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SearchIndexStatus(StrEnum):
    READY = "ready"
    STALE = "stale"
    REBUILDING = "rebuilding"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class SearchDocument:
    id: str
    entity_type: str
    entity_id: str
    goal_id: str
    topic_stable_id: str | None
    title: str
    body: str
    tags: str
    projection_version: str
    updated_at: str


@dataclass(frozen=True)
class SearchResult:
    entity_type: str
    entity_id: str
    goal_id: str
    topic_stable_id: str | None
    title: str
    body: str
    tags: str
    degraded: bool


@dataclass(frozen=True)
class SearchIndexState:
    status: SearchIndexStatus
    source_watermark: str
    active_generation: str | None
    rebuild_job_id: str | None
    failure_reference: str | None
    updated_at: str | None


@dataclass(frozen=True)
class SearchRebuild:
    id: str
    generation: str
