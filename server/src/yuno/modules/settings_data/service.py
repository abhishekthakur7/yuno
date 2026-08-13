from __future__ import annotations

import json
from typing import Any

from yuno.modules.audit.domain import AuditEvent
from yuno.modules.settings_data.domain import (
    DeleteOperation,
    ExportOperation,
    OwnerSettings,
    ProgressDisplay,
)
from yuno.modules.settings_data.ports import SettingsUnitOfWork
from yuno.shared.domain.clock import Clock, SystemClock, now_text
from yuno.shared.domain.errors import (
    PreconditionFailedError,
    UnavailableError,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id


def ensure_owner_settings(
    uow: SettingsUnitOfWork, owner_id: str, *, clock: Clock | None = None
) -> OwnerSettings:
    current = uow.settings_data.get(owner_id)
    if current is not None:
        return current
    return uow.settings_data.create(
        OwnerSettings(
            owner_id=owner_id,
            progress_display=ProgressDisplay.DETAILED,
            accessibility={"reduced_motion": False},
            provider_selection=None,
            row_version=1,
            updated_at=now_text(clock or SystemClock()),
        )
    )


def get_owner_settings(uow: SettingsUnitOfWork, owner_id: str) -> OwnerSettings:
    settings = uow.settings_data.get(owner_id)
    if settings is None:
        raise UnavailableError("Owner settings are unavailable; retry after recovery.")
    return settings


def patch_owner_settings(
    uow: SettingsUnitOfWork,
    owner_id: str,
    expected_version: int,
    progress_display: ProgressDisplay | None,
    accessibility: dict[str, Any] | None,
    provider_selection: str | None,
    provider_selection_set: bool,
    *,
    clock: Clock | None = None,
) -> OwnerSettings:
    before = get_owner_settings(uow, owner_id)
    if before.row_version != expected_version:
        raise PreconditionFailedError(
            "The owner settings have changed; reload them and retry."
        )
    active_clock = clock or SystemClock()
    updated = uow.settings_data.update(
        owner_id,
        expected_version,
        progress_display or before.progress_display,
        accessibility if accessibility is not None else before.accessibility,
        provider_selection if provider_selection_set else before.provider_selection,
        updated_at=now_text(active_clock),
    )
    if updated is None:
        raise PreconditionFailedError(
            "The owner settings have changed; reload them and retry."
        )
    uow.audit.append(
        AuditEvent(
            id=new_id(),
            owner_id=owner_id,
            goal_id=None,
            actor_role="learner",
            entity_type="owner_settings",
            entity_id=owner_id,
            action="updated",
            before_hash=hash_payload(before),
            after_hash=hash_payload(updated),
            reason=None,
            request_id=None,
            correlation_id=None,
            occurred_at=now_text(active_clock),
        )
    )
    return updated


def reserve_export(
    uow: SettingsUnitOfWork,
    owner_id: str,
    operation_id: str,
    goal_id: str | None,
    format_version: str,
    *,
    clock: Clock | None = None,
) -> ExportOperation:
    timestamp = now_text(clock or SystemClock())
    operation = ExportOperation(
        operation_id,
        owner_id,
        goal_id,
        "queued",
        format_version,
        None,
        operation_id,
        None,
        None,
        timestamp,
        timestamp,
    )
    uow.settings_data.add_export(operation)
    return operation


def complete_export(
    uow: SettingsUnitOfWork,
    owner_id: str,
    operation_id: str,
    *,
    clock: Clock | None = None,
) -> ExportOperation:
    operation = uow.settings_data.get_export(owner_id, operation_id)
    if operation is None:
        raise UnavailableError("The export operation is unavailable.")
    package = uow.settings_data.export_package(
        owner_id, operation.goal_id, operation.format_version
    )
    uow.settings_data.complete_export(
        owner_id, operation_id, package, now_text(clock or SystemClock())
    )
    completed = uow.settings_data.get_export(owner_id, operation_id)
    assert completed is not None
    return completed


def reserve_delete(
    uow: SettingsUnitOfWork,
    owner_id: str,
    operation_id: str,
    goal_id: str,
    snapshot_id: str,
    evidence_ids: tuple[str, ...],
    learning_state_ids: tuple[str, ...],
    *,
    clock: Clock | None = None,
) -> DeleteOperation:
    timestamp = now_text(clock or SystemClock())
    impact_json = json.dumps(
        {
            "goal_id": goal_id,
            "evidence_ids": list(evidence_ids),
            "learning_state_ids": list(learning_state_ids),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    operation = DeleteOperation(
        operation_id,
        owner_id,
        goal_id,
        snapshot_id,
        "goal",
        impact_json,
        hash_payload(json.loads(impact_json)),
        "preflight",
        None,
        None,
        None,
        None,
        timestamp,
        timestamp,
    )
    uow.settings_data.add_delete(operation)
    return operation
