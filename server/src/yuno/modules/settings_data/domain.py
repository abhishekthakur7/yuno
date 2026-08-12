"""Framework-free owner progress-display settings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProgressDisplay(StrEnum):
    DETAILED = "detailed"
    SIMPLE = "simple"


@dataclass(frozen=True)
class OwnerSettings:
    owner_id: str
    progress_display: ProgressDisplay
    row_version: int
    updated_at: str
