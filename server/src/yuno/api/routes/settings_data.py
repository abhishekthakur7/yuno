"""Durable owner settings HTTP API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from yuno.api.contracts import (
    DataLifecyclePolicyResponse,
    OwnerSettingsPatchRequest,
    OwnerSettingsResponse,
)
from yuno.api.dependencies import (
    get_clock,
    get_owner_id,
    get_settings_dependency,
    get_unit_of_work,
    if_match,
    parse_if_match,
)
from yuno.config import Settings
from yuno.modules.provider.domain import ProviderName
from yuno.modules.settings_data.domain import OwnerSettings
from yuno.modules.settings_data.ports import SettingsUnitOfWork
from yuno.modules.settings_data.service import (
    get_owner_settings,
    patch_owner_settings,
)
from yuno.shared.domain.clock import Clock

router = APIRouter(tags=["settings"])


@router.get(
    "/settings/data-lifecycle-policy", response_model=DataLifecyclePolicyResponse
)
def get_data_lifecycle_policy(
    settings: Annotated[Settings, Depends(get_settings_dependency)],
) -> DataLifecyclePolicyResponse:
    return DataLifecyclePolicyResponse(
        policy_version=settings.data_lifecycle_policy_version,
        import_original_max_bytes=settings.import_original_max_bytes,
        import_retained_owner_limit=settings.import_retained_owner_limit,
        import_statements_per_import_limit=settings.import_statements_per_import_limit,
        import_unreviewed_owner_limit=settings.import_unreviewed_owner_limit,
        evidence_payload_max_bytes=settings.evidence_payload_max_bytes,
        evidence_retained_owner_limit=settings.evidence_retained_owner_limit,
        generated_body_max_bytes=settings.generated_body_max_bytes,
        generated_retained_owner_limit=settings.generated_retained_owner_limit,
        interview_turns_per_session_limit=(settings.interview_turns_per_session_limit),
        interview_bytes_per_session_limit=settings.interview_bytes_per_session_limit,
        interview_sessions_owner_limit=settings.interview_sessions_owner_limit,
        runner_input_files_limit=settings.runner_input_files_limit,
        runner_input_bytes_limit=settings.runner_input_bytes_limit,
        runner_stdout_bytes_limit=settings.runner_stdout_bytes_limit,
        runner_stderr_bytes_limit=settings.runner_stderr_bytes_limit,
        runner_output_bytes_limit=settings.runner_output_bytes,
        runner_temp_bytes_limit=settings.runner_temp_bytes,
        runner_temp_files_limit=settings.runner_temp_files_limit,
        overlay_proposal_pending_cap=settings.overlay_proposal_pending_cap,
        pending_job_cap=settings.pending_job_cap,
        diagnostic_abandoned_retention_days=(
            settings.diagnostic_abandoned_retention_days
        ),
        interview_inactive_retention_days=settings.interview_inactive_retention_days,
        terminal_job_retention_days=settings.terminal_job_retention_days,
        job_event_retention_days=settings.job_event_retention_days,
        job_event_owner_limit=settings.job_event_owner_limit,
        runner_output_retention_days=settings.runner_output_retention_days,
        runner_workspace_retention_seconds=settings.runner_workspace_retention_seconds,
        export_package_retention_seconds=settings.export_package_retention_seconds,
        export_operation_retention_days=settings.export_operation_retention_days,
        structured_log_file_count=settings.structured_log_file_count,
        structured_log_file_max_bytes=settings.structured_log_file_max_bytes,
        structured_log_total_max_bytes=settings.structured_log_total_max_bytes,
        structured_log_retention_days=settings.structured_log_retention_days,
        export_format=settings.export_format,
        export_version=settings.export_format_version,
        export_available=settings.export_privacy_review_approved,
        recovery_window_days=0,
        yuno_managed_backups=False,
        remote_support_access=False,
    )


@router.get("/settings", response_model=OwnerSettingsResponse)
def get_settings(
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[SettingsUnitOfWork, Depends(get_unit_of_work)],
) -> OwnerSettingsResponse:
    return _response(get_owner_settings(uow, owner_id))


@router.patch("/settings", response_model=OwnerSettingsResponse)
def update_settings(
    body: OwnerSettingsPatchRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[SettingsUnitOfWork, Depends(get_unit_of_work)],
    match: Annotated[str, Depends(if_match)],
    clock: Annotated[Clock, Depends(get_clock)],
    request: Request,
) -> OwnerSettingsResponse:
    if body.provider_selection is not None:
        request.app.state.provider_registry.require_adapter(
            ProviderName(body.provider_selection.value)
        )
    updated = patch_owner_settings(
        uow,
        owner_id,
        parse_if_match(match),
        body.progress_display,
        body.accessibility.model_dump() if body.accessibility else None,
        body.provider_selection.value if body.provider_selection else None,
        "provider_selection" in body.model_fields_set,
        clock=clock,
    )
    uow.commit()
    return _response(updated)


def _response(settings: OwnerSettings) -> OwnerSettingsResponse:
    return OwnerSettingsResponse(
        progress_display=settings.progress_display,
        accessibility=settings.accessibility,
        provider_selection=settings.provider_selection,
        row_version=settings.row_version,
    )
