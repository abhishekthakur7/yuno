"""Repository and unit-of-work protocols for owner settings."""

from __future__ import annotations

from typing import Protocol

from yuno.modules.audit.ports import AuditRepository
from yuno.modules.settings_data.domain import OwnerSettings, ProgressDisplay
from yuno.shared.application.unit_of_work import UnitOfWork


class SettingsRepository(Protocol):
    def get(self, owner_id: str) -> OwnerSettings | None: ...
    def create(self, settings: OwnerSettings) -> OwnerSettings: ...
    def update(
        self,
        owner_id: str,
        expected_version: int,
        progress_display: ProgressDisplay,
        *,
        updated_at: str,
    ) -> OwnerSettings | None: ...


class SettingsUnitOfWork(UnitOfWork, Protocol):
    settings_data: SettingsRepository
    audit: AuditRepository
