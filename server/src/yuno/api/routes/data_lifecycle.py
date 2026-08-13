from __future__ import annotations

import json
from typing import Annotated, Protocol

from fastapi import APIRouter, Depends

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
from yuno.modules.profiles_goals.ports import ProfilesGoalsUnitOfWork
from yuno.modules.settings_data.ports import SettingsUnitOfWork
from yuno.modules.settings_data.service import reserve_export
from yuno.shared.application.jobs import JobDispatcher, JobLane, JobRequest
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.errors import NotFoundError, UnavailableError
from yuno.shared.domain.hashing import hash_payload

router = APIRouter(tags=["data-lifecycle"])


class DataLifecycleUnitOfWork(SettingsUnitOfWork, ProfilesGoalsUnitOfWork, Protocol):
    pass


@router.post("/exports", response_model=JobRefResponse, status_code=202)
def create_export(
    body: ExportCreateRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[DataLifecycleUnitOfWork, Depends(get_unit_of_work)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
    settings: Annotated[Settings, Depends(get_settings_dependency)],
    key: Annotated[str, Depends(idempotency_key)],
):
    if settings.export_format_version is None:
        raise UnavailableError(
            "Export is disabled until an export format policy is configured."
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
            "format_version": settings.export_format_version,
        }
    )
    if uow.settings_data.get_export(owner_id, operation_id) is None:
        reserve_export(
            uow, owner_id, operation_id, body.goal_id, settings.export_format_version
        )
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
    uow: Annotated[SettingsUnitOfWork, Depends(get_unit_of_work)],
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
    return ExportOperationResponse(
        id=operation.id,
        goal_id=operation.goal_id,
        status=operation.status,
        format_version=operation.format_version,
        package=json.loads(operation.package_json) if operation.package_json else None,
        job_id=operation.job_id,
        result_ref=operation.result_ref,
        failure_reference=operation.failure_reference,
        created_at=operation.created_at,
        updated_at=operation.updated_at,
    )


@router.get("/delete-operations/{operation_id}", response_model=DeleteOperationResponse)
def get_delete_operation(
    operation_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[SettingsUnitOfWork, Depends(get_unit_of_work)],
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
    return DeleteOperationResponse(
        id=operation.id,
        goal_id=operation.goal_id,
        snapshot_id=operation.snapshot_id,
        scope=operation.scope,
        evidence_ids=impact["evidence_ids"],
        learning_state_ids=impact["learning_state_ids"],
        status=operation.status,
        job_id=operation.job_id,
        result_ref=operation.result_ref,
        confirmed_at=operation.confirmed_at,
        failure_reference=operation.failure_reference,
        created_at=operation.created_at,
        updated_at=operation.updated_at,
    )
