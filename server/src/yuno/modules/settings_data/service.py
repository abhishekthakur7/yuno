from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from yuno.modules.audit.domain import AuditEvent
from yuno.modules.settings_data.domain import (
    BuiltExportPackage,
    DeleteOperation,
    ExportOperation,
    OwnerSettings,
    ProgressDisplay,
)
from yuno.modules.settings_data.ports import SettingsUnitOfWork
from yuno.shared.domain.clock import Clock, SystemClock, now_text, utc_text
from yuno.shared.domain.errors import (
    GoneError,
    NotFoundError,
    PreconditionFailedError,
    UnavailableError,
    UnsupportedExportVersionError,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id

EXPORT_FORMAT = "yuno-portable-export"
EXPORT_VERSION = "1.0"
_SEMANTIC_VERSION = re.compile(r"^(?P<major>0|[1-9][0-9]*)\.(?P<minor>0|[1-9][0-9]*)$")


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def require_supported_export_major(version: str) -> None:
    match = _SEMANTIC_VERSION.fullmatch(version)
    if match is None or int(match.group("major")) != 1:
        raise UnsupportedExportVersionError(
            "The requested portable export major version is unsupported."
        )


def portable_export_filename(exported_at: str) -> str:
    instant = datetime.fromisoformat(exported_at).astimezone(UTC)
    return f"yuno-export-v1-{instant.strftime('%Y%m%dT%H%M%SZ')}.json"


def portable_export_document(
    data: dict[str, object], *, exported_at: str, goal_id: str | None
) -> str:
    digest = hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()
    envelope = {
        "product": "Yuno",
        "format": EXPORT_FORMAT,
        "version": EXPORT_VERSION,
        "exported_at": exported_at,
        "scope": (
            {"kind": "goal", "goal_id": goal_id}
            if goal_id is not None
            else {"kind": "owner"}
        ),
        "data": data,
        "integrity": {"algorithm": "sha256", "digest": digest},
    }
    return canonical_json(envelope)


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
    require_supported_export_major(format_version)
    timestamp = now_text(clock or SystemClock())
    operation = ExportOperation(
        id=operation_id,
        owner_id=owner_id,
        goal_id=goal_id,
        status="queued",
        format_version=format_version,
        filename=None,
        package_hash=None,
        job_id=operation_id,
        result_ref=None,
        failure_reference=None,
        completed_at=None,
        package_expires_at=None,
        metadata_expires_at=None,
        created_at=timestamp,
        updated_at=timestamp,
    )
    uow.settings_data.add_export(operation)
    return operation


def build_export_package(
    uow: SettingsUnitOfWork,
    owner_id: str,
    operation_id: str,
    *,
    package_retention_seconds: int,
    metadata_retention_days: int,
    clock: Clock | None = None,
) -> BuiltExportPackage:
    operation = uow.settings_data.get_export(owner_id, operation_id)
    if operation is None:
        raise NotFoundError("The export operation was not found.")
    require_supported_export_major(operation.format_version)
    active_clock = clock or SystemClock()
    completed = active_clock.now().astimezone(UTC)
    completed_at = utc_text(completed)
    document = portable_export_document(
        uow.settings_data.read_export_data(owner_id, operation.goal_id),
        exported_at=completed_at,
        goal_id=operation.goal_id,
    )
    return BuiltExportPackage(
        operation_id=operation.id,
        owner_id=owner_id,
        document=document,
        filename=portable_export_filename(completed_at),
        package_hash=hashlib.sha256(document.encode("utf-8")).hexdigest(),
        completed_at=completed_at,
        package_expires_at=utc_text(
            completed + timedelta(seconds=package_retention_seconds)
        ),
        metadata_expires_at=utc_text(
            completed + timedelta(days=metadata_retention_days)
        ),
    )


def publish_export_package(
    uow: SettingsUnitOfWork, package: BuiltExportPackage
) -> ExportOperation:
    operation = uow.settings_data.get_export(package.owner_id, package.operation_id)
    if operation is None:
        raise UnavailableError("The export operation is unavailable.")
    uow.settings_data.publish_export(package)
    published = uow.settings_data.get_export(package.owner_id, package.operation_id)
    assert published is not None
    return published


def get_export_download(
    uow: SettingsUnitOfWork,
    owner_id: str,
    operation_id: str,
    *,
    clock: Clock | None = None,
) -> tuple[ExportOperation, str]:
    operation = uow.settings_data.get_export(owner_id, operation_id)
    if operation is None:
        raise NotFoundError("The export operation was not found.")
    active_clock = clock or SystemClock()
    now = now_text(active_clock)
    if operation.status == "expired" or (
        operation.package_expires_at is not None
        and datetime.fromisoformat(operation.package_expires_at)
        <= active_clock.now().astimezone(UTC)
    ):
        uow.settings_data.expire_export_package(owner_id, operation_id, now)
        raise GoneError("The export package has expired; create a fresh export.")
    if operation.status != "complete":
        raise UnavailableError("The export package is not ready for download.")
    document = uow.settings_data.get_export_package(owner_id, operation_id)
    if document is None:
        raise UnavailableError("The export package body is unavailable.")
    return operation, document


def get_export_status(
    uow: SettingsUnitOfWork,
    owner_id: str,
    operation_id: str,
    *,
    clock: Clock | None = None,
) -> tuple[ExportOperation, bool]:
    operation = uow.settings_data.get_export(owner_id, operation_id)
    if operation is None:
        raise UnavailableError("The export operation is unavailable.")
    active_clock = clock or SystemClock()
    if (
        operation.status == "complete"
        and operation.package_expires_at is not None
        and datetime.fromisoformat(operation.package_expires_at)
        <= active_clock.now().astimezone(UTC)
    ):
        uow.settings_data.expire_export_package(
            owner_id, operation_id, now_text(active_clock)
        )
        operation = uow.settings_data.get_export(owner_id, operation_id) or operation
    return operation, (
        operation.status == "complete"
        and uow.settings_data.get_export_package(owner_id, operation_id) is not None
    )


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
