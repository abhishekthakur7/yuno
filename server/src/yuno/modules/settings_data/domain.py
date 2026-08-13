from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ProgressDisplay(StrEnum):
    DETAILED = "detailed"
    SIMPLE = "simple"


@dataclass(frozen=True)
class OwnerSettings:
    owner_id: str
    progress_display: ProgressDisplay
    accessibility: dict[str, Any]
    provider_selection: str | None
    row_version: int
    updated_at: str


@dataclass(frozen=True)
class ExportOperation:
    id: str
    owner_id: str
    goal_id: str | None
    status: str
    format_version: str
    package_json: str | None
    job_id: str | None
    result_ref: str | None
    failure_reference: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class DeleteOperation:
    id: str
    owner_id: str
    goal_id: str
    snapshot_id: str
    scope: str
    impact_json: str
    impact_hash: str
    status: str
    job_id: str | None
    result_ref: str | None
    confirmed_at: str | None
    failure_reference: str | None
    created_at: str
    updated_at: str
