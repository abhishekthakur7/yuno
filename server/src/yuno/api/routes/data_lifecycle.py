from __future__ import annotations

import json
from typing import Annotated, Protocol

from fastapi import APIRouter, Depends, Response

from yuno.api.contracts import (
    DeleteOperationResponse,
    ExportCreateRequest,
    ExportOperationResponse,
    JobRefResponse,
    accepted_job,
)
from yuno.api.dependencies import (
    get_job_dispatcher,
    get_owner_id,
    get_settings_dependency,
    get_unit_of_work,
    idempotency_key,
)
from yuno.config import Settings
from yuno.modules.data_lifecycle.ports import DataLifecycleRepository
from yuno.modules.profiles_goals.ports import ProfilesGoalsUnitOfWork
from yuno.modules.settings_data.ports import SettingsUnitOfWork
from yuno.modules.settings_data.service import (
    EXPORT_FORMAT,
    get_export_download,
    get_export_status,
    require_supported_export_major,
    reserve_export,
)
from yuno.shared.application.jobs import JobDispatcher, JobLane, JobRequest
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.errors import (
    GoneError,
    NotFoundError,
    UnavailableError,
    UnsupportedExportVersionError,
)
from yuno.shared.domain.hashing import hash_payload

router = APIRouter(tags=["data-lifecycle"])


class DataLifecycleUnitOfWork(SettingsUnitOfWork, ProfilesGoalsUnitOfWork, Protocol):
    data_lifecycle: DataLifecycleRepository


@router.post("/exports", response_model=JobRefResponse, status_code=202)
def create_export(
    body: ExportCreateRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[DataLifecycleUnitOfWork, Depends(get_unit_of_work)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
    settings: Annotated[Settings, Depends(get_settings_dependency)],
    key: Annotated[str, Depends(idempotency_key)],
):
    if not settings.export_privacy_review_approved:
        raise UnavailableError(
            "Portable export remains disabled until the required privacy review passes."
        )
    require_supported_export_major(body.version)
    require_supported_export_major(settings.export_format_version)
    if body.version != settings.export_format_version:
        raise UnsupportedExportVersionError(
            "The requested portable export version is not available for writing."
        )
    if (
        body.goal_id is not None
        and uow.profiles_goals.get_goal_for_lifecycle(owner_id, body.goal_id) is None
    ):
        raise NotFoundError("The export goal was not found.")
    operation_id = hash_payload(
        {
            "owner_id": owner_id,
            "idempotency_key": key,
            "operation": "export",
            "goal_id": body.goal_id,
            "format_version": body.version,
        }
    )
    if uow.settings_data.get_export(owner_id, operation_id) is None:
        reserve_export(uow, owner_id, operation_id, body.goal_id, body.version)
        uow.commit()
    try:
        ref = dispatcher.enqueue(
            JobRequest(
                "export_data",
                owner_id,
                {"operation_id": operation_id},
                operation_id,
                key,
                requested_job_id=operation_id,
                goal_id=body.goal_id,
                lane=JobLane.BACKGROUND,
                schema_version=settings.export_format_version,
                request_ref=f"ExportOperation:{operation_id}",
            )
        )
    except Exception as exc:
        uow.settings_data.fail_export(
            owner_id, operation_id, type(exc).__name__, now_text(SystemClock())
        )
        uow.commit()
        raise
    return accepted_job(ref)


@router.get("/exports/{operation_id}", response_model=ExportOperationResponse)
def get_export(
    operation_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[DataLifecycleUnitOfWork, Depends(get_unit_of_work)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
) -> ExportOperationResponse:
    operation = uow.settings_data.get_export(owner_id, operation_id)
    if operation is None:
        raise NotFoundError("The export operation was not found.")
    job = dispatcher.get(owner_id, operation.job_id or operation.id)
    if job and operation.status != "complete":
        if job.status.value in {"failed", "cancelled"}:
            uow.settings_data.fail_export(
                owner_id,
                operation.id,
                f"job:{job.job_id}:{job.status.value}",
                now_text(SystemClock()),
            )
        elif job.status.value in {"running", "cancel-requested"}:
            uow.settings_data.set_export_status(
                owner_id, operation.id, "running", now_text(SystemClock())
            )
        elif job.status.value == "queued":
            uow.settings_data.set_export_status(
                owner_id, operation.id, "queued", now_text(SystemClock())
            )
        uow.commit()
        operation = uow.settings_data.get_export(owner_id, operation.id) or operation
    operation, download_available = get_export_status(
        uow, owner_id, operation.id, clock=SystemClock()
    )
    uow.commit()
    return ExportOperationResponse(
        id=operation.id,
        goal_id=operation.goal_id,
        status=operation.status,
        format=EXPORT_FORMAT,
        version=operation.format_version,
        filename=operation.filename,
        package_hash=operation.package_hash,
        completed_at=operation.completed_at,
        package_expires_at=operation.package_expires_at,
        metadata_expires_at=operation.metadata_expires_at,
        download_available=download_available,
        job_id=operation.job_id,
        result_ref=operation.result_ref,
        failure_reference=operation.failure_reference,
        created_at=operation.created_at,
        updated_at=operation.updated_at,
    )


@router.get("/exports/{operation_id}/download")
def download_export(
    operation_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[SettingsUnitOfWork, Depends(get_unit_of_work)],
) -> Response:
    try:
        operation, document = get_export_download(uow, owner_id, operation_id)
    except GoneError:
        uow.commit()
        raise
    assert operation.filename is not None
    assert operation.package_hash is not None
    return Response(
        content=document.encode("utf-8"),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{operation.filename}"',
            "ETag": f'"{operation.package_hash}"',
        },
    )


@router.get("/delete-operations/{operation_id}", response_model=DeleteOperationResponse)
def get_delete_operation(
    operation_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[DataLifecycleUnitOfWork, Depends(get_unit_of_work)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
) -> DeleteOperationResponse:
    operation = uow.settings_data.get_delete(owner_id, operation_id)
    if operation is None:
        raise NotFoundError("The delete operation was not found.")
    job = dispatcher.get(owner_id, operation.job_id or operation.id)
    if job and operation.status != "complete":
        if job.status.value in {"failed", "cancelled"}:
            uow.settings_data.fail_delete(
                owner_id,
                operation.id,
                f"job:{job.job_id}:{job.status.value}",
                now_text(SystemClock()),
            )
        elif job.status.value in {"running", "cancel-requested"}:
            uow.settings_data.set_delete_status(
                owner_id, operation.id, "running", now_text(SystemClock())
            )
        elif job.status.value == "queued":
            uow.settings_data.set_delete_status(
                owner_id, operation.id, "queued", now_text(SystemClock())
            )
        uow.commit()
        operation = uow.settings_data.get_delete(owner_id, operation.id) or operation
    impact = json.loads(operation.impact_json)
    cleanup_intents = tuple(
        intent
        for intent in uow.data_lifecycle.list_pending_cleanup_intents(owner_id)
        if intent.goal_id == operation.goal_id
    )
    cleanup_failures = sorted(
        {
            intent.failure_classification
            for intent in cleanup_intents
            if intent.failure_classification is not None
        }
    )
    visible_status = operation.status
    if operation.status == "complete" and cleanup_failures:
        visible_status = "cleanup-failed"
    elif operation.status == "complete" and cleanup_intents:
        visible_status = "cleanup-pending"
    return DeleteOperationResponse(
        id=operation.id,
        goal_id=operation.goal_id,
        snapshot_id=operation.snapshot_id,
        scope=operation.scope,
        evidence_ids=impact["evidence_ids"],
        learning_state_ids=impact["learning_state_ids"],
        status=visible_status,
        cleanup_pending_count=len(cleanup_intents),
        cleanup_failure_classifications=cleanup_failures,
        job_id=operation.job_id,
        result_ref=operation.result_ref,
        confirmed_at=operation.confirmed_at,
        failure_reference=operation.failure_reference,
        created_at=operation.created_at,
        updated_at=operation.updated_at,
    )
