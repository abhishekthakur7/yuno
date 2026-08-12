"""Application services for durable owner settings."""

from __future__ import annotations

from yuno.modules.audit.domain import AuditEvent
from yuno.modules.settings_data.domain import OwnerSettings, ProgressDisplay
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
            row_version=1,
            updated_at=now_text(clock or SystemClock()),
        )
    )


def get_owner_settings(
    uow: SettingsUnitOfWork, owner_id: str
) -> OwnerSettings:
    settings = uow.settings_data.get(owner_id)
    if settings is None:
        raise UnavailableError("Owner settings are unavailable; retry after recovery.")
    return settings


def patch_owner_settings(
    uow: SettingsUnitOfWork,
    owner_id: str,
    expected_version: int,
    progress_display: ProgressDisplay,
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
        progress_display,
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
