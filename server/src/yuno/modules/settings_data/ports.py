from __future__ import annotations

from typing import Any, Protocol

from yuno.modules.audit.ports import AuditRepository
from yuno.modules.settings_data.domain import (
    BuiltExportPackage,
    DeleteOperation,
    ExportOperation,
    OwnerSettings,
    ProgressDisplay,
)
from yuno.shared.application.unit_of_work import UnitOfWork


class SettingsRepository(Protocol):
    def get(self, owner_id: str) -> OwnerSettings | None: ...
    def create(self, settings: OwnerSettings) -> OwnerSettings: ...
    def update(
        self,
        owner_id: str,
        expected_version: int,
        progress_display: ProgressDisplay,
        accessibility: dict[str, Any],
        provider_selection: str | None,
        *,
        updated_at: str,
    ) -> OwnerSettings | None: ...
    def add_export(self, operation: ExportOperation) -> None: ...
    def get_export(
        self, owner_id: str, operation_id: str
    ) -> ExportOperation | None: ...
    def publish_export(self, package: BuiltExportPackage) -> None: ...
    def fail_export(
        self, owner_id: str, operation_id: str, diagnostic: str, updated_at: str
    ) -> None: ...
    def set_export_status(
        self, owner_id: str, operation_id: str, status: str, updated_at: str
    ) -> None: ...
    def read_export_data(
        self, owner_id: str, goal_id: str | None
    ) -> dict[str, object]: ...
    def get_export_package(self, owner_id: str, operation_id: str) -> str | None: ...
    def expire_export_package(
        self, owner_id: str, operation_id: str, updated_at: str
    ) -> None: ...
    def add_delete(self, operation: DeleteOperation) -> None: ...
    def get_delete(
        self, owner_id: str, operation_id: str
    ) -> DeleteOperation | None: ...
    def queue_delete(
        self, owner_id: str, operation_id: str, job_id: str, updated_at: str
    ) -> None: ...
    def complete_delete(
        self, owner_id: str, operation_id: str, updated_at: str
    ) -> None: ...
    def fail_delete(
        self, owner_id: str, operation_id: str, diagnostic: str, updated_at: str
    ) -> None: ...
    def set_delete_status(
        self, owner_id: str, operation_id: str, status: str, updated_at: str
    ) -> None: ...


class SettingsUnitOfWork(UnitOfWork, Protocol):
    settings_data: SettingsRepository
    audit: AuditRepository
