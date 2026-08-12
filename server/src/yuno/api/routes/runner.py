from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import text

from yuno.api.contracts import (
    JobRefResponse,
    RunnerCapabilitiesResponse,
    RunnerConfirmationRequest,
    RunnerConfirmationResponse,
    RunnerRunRequest,
    RunnerRunResponse,
    accepted_job,
)
from yuno.api.dependencies import (
    get_job_dispatcher,
    get_owner_id,
    get_settings_dependency,
    idempotency_key,
)
from yuno.config import Settings
from yuno.modules.runner.adapters import detect_command, memory_limit_enforced
from yuno.modules.runner.domain import RUNNER_LIMITATION, DeclaredInput
from yuno.modules.runner.models import RunnerInputRow, RunnerRecordRow
from yuno.modules.runner.repository import RunnerRepository
from yuno.modules.runner.service import (
    capabilities,
    create_confirmation,
    require_policy,
)
from yuno.shared.application.jobs import JobDispatcher, JobLane, JobRequest
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.errors import (
    ConflictError,
    IdempotencyConflictError,
    NotFoundError,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id

router = APIRouter(tags=["runner"])


@router.get("/runner/capabilities", response_model=RunnerCapabilitiesResponse)
def get_capabilities(settings: Annotated[Settings, Depends(get_settings_dependency)]):
    return capabilities(
        settings,
        detect_command,
        memory_limit_is_enforced=memory_limit_enforced(),
    )


@router.post(
    "/runner/confirmations",
    response_model=RunnerConfirmationResponse,
    status_code=status.HTTP_201_CREATED,
)
def confirm_runner(
    body: RunnerConfirmationRequest,
    request: Request,
    owner_id: Annotated[str, Depends(get_owner_id)],
    settings: Annotated[Settings, Depends(get_settings_dependency)],
):
    inputs = tuple(
        DeclaredInput(
            item.logical_path, item.declared_type, item.content_ref, item.content_hash
        )
        for item in body.inputs
    )
    with request.app.state.session_factory() as session:
        detected = detect_command(
            "java",
            body.capability,
            settings.runner_javac_command,
            settings.runner_java_version_prefix,
        )
        row = create_confirmation(
            session,
            settings,
            owner_id,
            goal_id=body.goal_id,
            artifact_id=body.artifact_id,
            language=body.language.value,
            capability=body.capability,
            operation=body.operation.value,
            inputs=inputs,
            acknowledgement_version=body.acknowledgement_version,
            detected_state=detected["state"],
        )
        session.commit()
        return {
            "id": row.id,
            "language": row.language,
            "capability": row.capability,
            "operation": row.operation,
            "inputs": [
                {
                    "logical_path": item.logical_path,
                    "declared_type": item.declared_type,
                    "content_hash": item.content_hash,
                }
                for item in inputs
            ],
            "confirmed_at": row.confirmed_at,
            "expires_at": row.expires_at,
            "consumed_at": row.consumed_at,
        }


@router.post(
    "/runner-runs",
    response_model=JobRefResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={202: {"model": JobRefResponse}},
)
def start_runner(
    body: RunnerRunRequest,
    request: Request,
    owner_id: Annotated[str, Depends(get_owner_id)],
    settings: Annotated[Settings, Depends(get_settings_dependency)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
    key: Annotated[str, Depends(idempotency_key)],
):
    require_policy(settings)
    request_hash = hash_payload(body.model_dump(mode="json"))
    with request.app.state.session_factory() as session:
        if session.get_bind().dialect.name == "sqlite":
            session.execute(text("BEGIN IMMEDIATE"))
        repo = RunnerRepository(session)
        replay = repo.confirmation_by_idempotency(owner_id, key)
        if replay is not None:
            if replay.request_hash != request_hash:
                raise IdempotencyConflictError(
                    "The Idempotency-Key was reused with a different runner request."
                )
            if replay.reserved_run_id is None:
                raise RuntimeError("The runner idempotency reservation is invalid.")
            current = dispatcher.get(owner_id, replay.reserved_run_id)
            if current is not None:
                return accepted_job(current)
            confirmation = replay
            run_id = replay.reserved_run_id
        else:
            run_id = new_id()
            confirmation = repo.confirmation(owner_id, body.confirmation_id)
            if confirmation is None:
                raise NotFoundError("Runner confirmation was not found.")
            if confirmation.consumed_at is not None:
                raise ConflictError(
                    "Runner confirmation has already been consumed; confirm a fresh run."
                )
            if confirmation.expires_at <= now_text(SystemClock()):
                raise ConflictError("Runner confirmation expired; confirm a fresh run.")
            if (
                confirmation.environment_policy_version
                != settings.runner_environment_policy_version
                or confirmation.limits_config_version
                != settings.runner_limits_config_version
            ):
                raise ConflictError(
                    "Runner policy changed; confirm the exact inputs again."
                )
            if not repo.reserve_confirmation(
                owner_id,
                confirmation.id,
                key=key,
                request_hash=request_hash,
                run_id=run_id,
                consumed_at=now_text(SystemClock()),
            ):
                raise ConflictError(
                    "Runner confirmation has already been consumed; confirm a fresh run."
                )
            confirmed_inputs = repo.confirmation_inputs(owner_id, confirmation.id)
            record = RunnerRecordRow(
                id=run_id,
                owner_id=owner_id,
                goal_id=confirmation.goal_id,
                artifact_id=confirmation.artifact_id,
                job_id=run_id,
                confirmation_id=confirmation.id,
                language=confirmation.language,
                capability=confirmation.capability,
                operation=confirmation.operation,
                toolchain=str(settings.runner_javac_command),
                argv_json="[]",
                working_directory_policy="isolated-temporary-workspace-v1",
                environment_policy_version=confirmation.environment_policy_version,
                limits_config_version=confirmation.limits_config_version,
                state="queued",
                cleanup_state="cleanup-pending",
                created_at=now_text(SystemClock()),
                updated_at=now_text(SystemClock()),
            )
            session.add(record)
            session.flush()
            for item in confirmed_inputs:
                content_ref = "confirmed-base64:" + item.resolved_content
                session.add(
                    RunnerInputRow(
                        id=new_id(),
                        owner_id=owner_id,
                        runner_id=run_id,
                        logical_path=item.logical_path,
                        declared_type=item.declared_type,
                        content_ref=content_ref,
                        content_hash=item.content_hash,
                    )
                )
        session.commit()
    ref = dispatcher.enqueue(
        JobRequest(
            "java_runner",
            owner_id,
            {"run_id": run_id},
            run_id,
            key,
            requested_job_id=run_id,
            goal_id=confirmation.goal_id,
            lane=JobLane.INTERACTIVE,
            schema_version="runner-v1",
            request_ref=f"RunnerRun:{run_id}",
            confirmation_ref=confirmation.id,
            run_id=run_id,
        )
    )
    return accepted_job(ref)


@router.get("/runner-runs/{run_id}", response_model=RunnerRunResponse)
def get_runner_run(
    run_id: str, request: Request, owner_id: Annotated[str, Depends(get_owner_id)]
):
    with request.app.state.session_factory() as session:
        repo = RunnerRepository(session)
        row = repo.record(owner_id, run_id)
        if row is None:
            raise NotFoundError("Runner run was not found.")
        inputs = repo.inputs(owner_id, run_id)
        chunks = repo.chunks(owner_id, run_id)
        result = json.loads(row.outcome_json) if row.outcome_json else {}
        phase = lambda name: result.get(
            f"{name}_phase", {"label": name, "state": "not-run"}
        )
        return {
            "id": row.id,
            "job_id": row.job_id,
            "state": row.state,
            "inputs": [
                {
                    "logical_path": item.logical_path,
                    "declared_type": item.declared_type,
                    "content_hash": item.content_hash,
                }
                for item in inputs
            ],
            "output_chunks": [
                {
                    "phase": item.phase,
                    "stream": item.stream,
                    "sequence": item.sequence,
                    "ordinal": item.ordinal,
                    "content": item.content_ref,
                    "truncated": bool(item.truncated),
                }
                for item in chunks
            ],
            "compile_phase": phase("compile"),
            "test_phase": phase("test"),
            "static_phase": phase("static"),
            "cleanup_state": row.cleanup_state,
            "cleanup_diagnostic": row.cleanup_diagnostic,
            "limitation": RUNNER_LIMITATION,
        }


@router.post("/runner-runs/{run_id}/cancel", response_model=RunnerRunResponse)
def cancel_runner_run(
    run_id: str,
    request: Request,
    owner_id: Annotated[str, Depends(get_owner_id)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
    _key: Annotated[str, Depends(idempotency_key)],
):
    job = dispatcher.cancel(owner_id, run_id)
    with request.app.state.session_factory() as session:
        row = RunnerRepository(session).record(owner_id, run_id)
        if row is None:
            raise NotFoundError("Runner run was not found.")
        if row.state in ("queued", "preparing", "running"):
            if job.status.value == "cancelled":
                row.state = "cancelled"
                row.cleanup_state = "cleanup-complete"
            else:
                row.state = "cancel-requested"
            session.commit()
    return get_runner_run(run_id, request, owner_id)
