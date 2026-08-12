from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from datetime import timedelta
from pathlib import PurePosixPath

from yuno.config import Settings
from yuno.modules.runner.domain import (
    RUNNER_LIMITATION,
    DeclaredInput,
    OutputChunk,
    ProcessLimits,
    RunnerProcessOutcome,
)
from yuno.modules.runner.models import (
    RunnerConfirmationInputRow,
    RunnerConfirmationRow,
    RunnerOutputChunkRow,
)
from yuno.modules.runner.ports import ProcessPort, RunnerProcessSpec, TempWorkspacePort
from yuno.modules.runner.repository import RunnerRepository
from yuno.shared.application.jobs import JobCompletion, JobExecution, JobResult
from yuno.shared.domain.clock import Clock, SystemClock, utc_text
from yuno.shared.domain.errors import (
    DomainValidationError,
    NotFoundError,
    UnavailableError,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id

ACKNOWLEDGEMENT_VERSION = "runner-not-a-sandbox-v1"
WORKING_DIRECTORY_POLICY = "isolated-temporary-workspace-v1"
_SAFE_PATH = re.compile(r"^[A-Za-z0-9._/-]+$")
_FORBIDDEN_ENV = (
    "AWS_",
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "CREDENTIAL",
    "CONNECTION_STRING",
    "DATABASE_URL",
)


def policy_ready(settings: Settings) -> bool:
    required = (
        settings.runner_environment_policy_version,
        settings.runner_limits_config_version,
        settings.runner_confirmation_ttl_seconds,
        settings.runner_wall_time_seconds,
        settings.runner_cpu_seconds,
        settings.runner_memory_bytes,
        settings.runner_process_limit,
        settings.runner_output_bytes,
        settings.runner_file_bytes,
        settings.runner_temp_bytes,
        settings.runner_javac_command,
        settings.runner_java_command,
        settings.runner_java_version_prefix,
    )
    return settings.runner_enabled and all(value is not None for value in required)


def require_policy(settings: Settings) -> None:
    if not policy_ready(settings):
        raise UnavailableError(
            "Runner is disabled pending IDK-005 and IDK-007 approval and complete configuration."
        )


def capabilities(
    settings: Settings, detect_command, *, memory_limit_is_enforced: bool
) -> dict[str, object]:
    if not policy_ready(settings):
        return {
            "enabled": False,
            "disabled_reason": "Blocked by IDK-005 and IDK-007: approved toolchain matrix and complete limits are required.",
            "environment_policy_version": None,
            "limits_config_version": None,
            "limitation": RUNNER_LIMITATION,
            "capabilities": [],
        }
    items = [
        detect_command(
            "java",
            "compile-and-test",
            settings.runner_javac_command,
            settings.runner_java_version_prefix,
        )
    ]
    if not memory_limit_is_enforced and items[0]["state"] == "supported":
        items[0] = {
            **items[0],
            "detail": (
                f"{items[0]['detail']} Address-space memory limits are not "
                "enforceable on this platform; other configured limits remain active."
            ),
        }
    if settings.runner_python_command:
        items.append(
            detect_command(
                "python", "compile-and-test", settings.runner_python_command, None
            )
        )
    if settings.runner_relational_connector == "configured":
        items.append(
            {
                "language": "relational",
                "capability": "connector",
                "state": "supported",
                "detail": "Explicitly configured connector; no database is provisioned.",
            }
        )
    return {
        "enabled": True,
        "disabled_reason": None,
        "environment_policy_version": settings.runner_environment_policy_version,
        "limits_config_version": settings.runner_limits_config_version,
        "limitation": RUNNER_LIMITATION,
        "capabilities": items,
    }


def validate_input(value: DeclaredInput) -> bytes:
    path = PurePosixPath(value.logical_path)
    if (
        path.is_absolute()
        or ".." in path.parts
        or not value.logical_path
        or not _SAFE_PATH.fullmatch(value.logical_path)
    ):
        raise DomainValidationError(
            "Runner logical paths must be safe relative POSIX paths."
        )
    if not value.content_ref.startswith("inline-base64:"):
        raise DomainValidationError("Unsupported runner content reference.")
    try:
        content = base64.b64decode(
            value.content_ref.removeprefix("inline-base64:"), validate=True
        )
    except ValueError as exc:
        raise DomainValidationError(
            "Runner content reference is invalid base64."
        ) from exc
    if hashlib.sha256(content).hexdigest() != value.content_hash:
        raise DomainValidationError(
            "Declared runner input content hash does not match resolved content."
        )
    return content


def create_confirmation(
    session,
    settings: Settings,
    owner_id: str,
    *,
    goal_id: str | None,
    artifact_id: str | None,
    language: str,
    capability: str,
    operation: str,
    inputs: tuple[DeclaredInput, ...],
    acknowledgement_version: str,
    detected_state: str,
    clock: Clock | None = None,
):
    require_policy(settings)
    if language != "java":
        raise DomainValidationError(
            "Only explicitly configured Java execution is implemented."
        )
    if acknowledgement_version != ACKNOWLEDGEMENT_VERSION:
        raise DomainValidationError(
            "The current runner limitation acknowledgement is required."
        )
    if not inputs or len({item.logical_path for item in inputs}) != len(inputs):
        raise DomainValidationError(
            "Runner inputs must be non-empty with unique logical paths."
        )
    resolved = [(item, validate_input(item)) for item in inputs]
    if detected_state != "supported":
        raise UnavailableError(
            "The configured Java toolchain is not currently supported."
        )
    effective_clock = clock or SystemClock()
    confirmed = effective_clock.now()
    row = RunnerConfirmationRow(
        id=new_id(),
        owner_id=owner_id,
        goal_id=goal_id,
        artifact_id=artifact_id,
        language=language,
        capability=capability,
        operation=operation,
        inputs_hash=hash_payload([item.__dict__ for item in inputs]),
        acknowledgement_version=acknowledgement_version,
        idempotency_key=None,
        request_hash=None,
        reserved_run_id=None,
        environment_policy_version=str(settings.runner_environment_policy_version),
        limits_config_version=str(settings.runner_limits_config_version),
        confirmed_at=utc_text(confirmed),
        expires_at=utc_text(
            confirmed
            + timedelta(seconds=int(settings.runner_confirmation_ttl_seconds or 0))
        ),
    )
    session.add(row)
    session.flush()
    for item, content in resolved:
        session.add(
            RunnerConfirmationInputRow(
                id=new_id(),
                owner_id=owner_id,
                confirmation_id=row.id,
                logical_path=item.logical_path,
                declared_type=item.declared_type,
                content_ref=item.content_ref,
                content_hash=item.content_hash,
                resolved_content=base64.b64encode(content).decode("ascii"),
            )
        )
    return row


def minimal_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    source = source or dict(os.environ)
    environment = {
        key: source[key] for key in ("PATH", "LANG", "LC_ALL", "TZ") if key in source
    }
    return {
        key: value
        for key, value in environment.items()
        if not any(marker in key.upper() for marker in _FORBIDDEN_ENV)
    }


def _workspace_bytes(workspace) -> int:
    return sum(path.stat().st_size for path in workspace.rglob("*") if path.is_file())


def _bounded_chunks(
    chunks: tuple[OutputChunk, ...], remaining_bytes: int
) -> tuple[list[OutputChunk], int, bool]:
    bounded: list[OutputChunk] = []
    used = 0
    breached = False
    for chunk in chunks:
        encoded = chunk.content.encode("utf-8")
        available = max(0, remaining_bytes - used)
        kept = encoded[:available]
        truncated = chunk.truncated or len(kept) < len(encoded)
        if kept or truncated:
            bounded.append(
                OutputChunk(
                    chunk.phase,
                    chunk.stream,
                    chunk.sequence,
                    kept.decode("utf-8", errors="ignore"),
                    truncated,
                )
            )
        used += len(kept)
        breached = breached or truncated
    return bounded, used, breached


def _limit_chunk(phase: str, message: str) -> OutputChunk:
    return OutputChunk(phase, "stderr", 1, message, True)


def execute_runner_job(
    execution: JobExecution,
    session_factory,
    settings: Settings,
    process_port: ProcessPort,
    workspace_port: TempWorkspacePort,
) -> JobCompletion:
    run_id = str(execution.request.run_id)
    with session_factory() as session:
        repo = RunnerRepository(session)
        row = repo.record(execution.request.owner_id, run_id)
        if row is None:
            raise NotFoundError("Runner record was not found.")
        inputs = repo.inputs(execution.request.owner_id, run_id)
        row.state = "preparing"
        session.commit()
    workspace = None
    cleanup_state = "cleanup-pending"
    try:
        workspace = workspace_port.create()
        with session_factory() as session:
            row = RunnerRepository(session).record(execution.request.owner_id, run_id)
            assert row is not None
            row.temp_path = str(workspace)
            session.commit()
        for item in inputs:
            if not item.content_ref.startswith("confirmed-base64:"):
                raise DomainValidationError(
                    "Runner input is not an authoritative confirmed snapshot."
                )
            content = base64.b64decode(
                item.content_ref.removeprefix("confirmed-base64:"), validate=True
            )
            if hashlib.sha256(content).hexdigest() != item.content_hash:
                raise DomainValidationError(
                    "Confirmed runner input hash changed before execution."
                )
            target = workspace / item.logical_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        java_sources = sorted(
            item.logical_path for item in inputs if item.logical_path.endswith(".java")
        )
        if not java_sources:
            raise DomainValidationError(
                "Java execution requires at least one declared .java input."
            )
        argv = (str(settings.runner_javac_command), *java_sources)
        limits = ProcessLimits(
            float(settings.runner_wall_time_seconds),
            int(settings.runner_cpu_seconds),
            int(settings.runner_memory_bytes),
            int(settings.runner_process_limit),
            int(settings.runner_output_bytes),
            int(settings.runner_file_bytes),
            int(settings.runner_temp_bytes),
        )
        workspace_bytes = _workspace_bytes(workspace)
        with session_factory() as session:
            row = RunnerRepository(session).record(execution.request.owner_id, run_id)
            assert row is not None
            row.argv_json = json.dumps(argv)
            row.state = "running"
            session.commit()
        initial_workspace_breached = workspace_bytes > limits.temp_bytes
        if initial_workspace_breached:
            outcome = RunnerProcessOutcome(
                0,
                0,
                None,
                None,
                True,
                False,
                (
                    OutputChunk(
                        "compile",
                        "stderr",
                        1,
                        "Configured aggregate temporary-storage limit was exceeded.",
                        True,
                    ),
                ),
                0,
            )
        else:
            outcome = process_port.run(
                RunnerProcessSpec(
                    argv, workspace, minimal_environment(), limits, "compile"
                ),
                on_spawn=lambda pid, pgid, identity: execution.record_runtime(
                    pid=pid,
                    pgid=pgid,
                    process_identity=identity,
                    temp_path=str(workspace),
                ),
                cancelled=execution.cancel_requested,
            )
        chunks, output_bytes, output_breached = _bounded_chunks(
            outcome.chunks, limits.output_bytes
        )
        wall_ms = outcome.duration_ms
        cpu_ms = outcome.cpu_ms or 0
        cpu_observed = outcome.cpu_ms is not None
        workspace_breached = _workspace_bytes(workspace) > limits.temp_bytes
        compile_limited = (
            outcome.timed_out_or_limited
            or output_breached
            or wall_ms > limits.wall_seconds * 1000
            or (cpu_observed and cpu_ms > limits.cpu_seconds * 1000)
            or workspace_breached
        )
        if workspace_breached and not initial_workspace_breached:
            extra, added, _ = _bounded_chunks(
                (
                    _limit_chunk(
                        "compile",
                        "Configured aggregate temporary-storage limit was exceeded.",
                    ),
                ),
                max(0, limits.output_bytes - output_bytes),
            )
            chunks.extend(extra)
            output_bytes += added
        compile_state = (
            "cancelled"
            if outcome.cancelled
            else "timed-out-or-limited"
            if compile_limited
            else "completed"
            if outcome.exit_code == 0
            else "failed"
        )
        test_result = None
        if row.operation == "test" and compile_state == "completed":
            main_class = PurePosixPath(java_sources[0]).stem
            test_argv = (str(settings.runner_java_command), "-cp", ".", main_class)
            remaining_wall = limits.wall_seconds - wall_ms / 1000
            remaining_cpu = limits.cpu_seconds - cpu_ms / 1000
            remaining_output = limits.output_bytes - output_bytes
            if remaining_wall <= 0 or (cpu_observed and remaining_cpu <= 0):
                test_result = RunnerProcessOutcome(
                    0,
                    0,
                    None,
                    None,
                    True,
                    False,
                    (),
                    0,
                    0 if cpu_observed else None,
                )
            else:
                test_limits = ProcessLimits(
                    remaining_wall,
                    remaining_cpu if cpu_observed else limits.cpu_seconds,
                    limits.memory_bytes,
                    limits.process_count,
                    remaining_output,
                    limits.file_bytes,
                    limits.temp_bytes,
                )
                test_result = process_port.run(
                    RunnerProcessSpec(
                        test_argv,
                        workspace,
                        minimal_environment(),
                        test_limits,
                        "test",
                    ),
                    on_spawn=lambda pid, pgid, identity: execution.record_runtime(
                        pid=pid,
                        pgid=pgid,
                        process_identity=identity,
                        temp_path=str(workspace),
                    ),
                    cancelled=execution.cancel_requested,
                )
                test_chunks, added, test_output_breached = _bounded_chunks(
                    test_result.chunks, remaining_output
                )
                chunks.extend(test_chunks)
                output_bytes += added
                wall_ms += test_result.duration_ms
                if test_result.cpu_ms is not None:
                    cpu_ms += test_result.cpu_ms
                    cpu_observed = True
                workspace_breached = _workspace_bytes(workspace) > limits.temp_bytes
                test_limited = (
                    test_result.timed_out_or_limited
                    or test_output_breached
                    or wall_ms > limits.wall_seconds * 1000
                    or (cpu_observed and cpu_ms > limits.cpu_seconds * 1000)
                    or workspace_breached
                )
                if workspace_breached:
                    extra, _added, _ = _bounded_chunks(
                        (
                            _limit_chunk(
                                "test",
                                "Configured aggregate temporary-storage limit was exceeded.",
                            ),
                        ),
                        max(0, limits.output_bytes - output_bytes),
                    )
                    chunks.extend(extra)
                if test_limited and not test_result.timed_out_or_limited:
                    test_result = RunnerProcessOutcome(
                        test_result.pid,
                        test_result.pgid,
                        test_result.exit_code,
                        test_result.signal,
                        True,
                        test_result.cancelled,
                        test_result.chunks,
                        test_result.duration_ms,
                        test_result.cpu_ms,
                    )
        terminal = test_result or outcome
        state = compile_state
        if test_result is not None:
            state = (
                "cancelled"
                if terminal.cancelled
                else "timed-out-or-limited"
                if terminal.timed_out_or_limited
                else "completed"
                if terminal.exit_code == 0
                else "failed"
            )
        result = {
            "compile_phase": {
                "label": "compile",
                "state": compile_state,
                "exit_code": outcome.exit_code,
                "signal": outcome.signal,
                "duration_ms": outcome.duration_ms,
            },
            "test_phase": (
                {
                    "label": "test",
                    "state": state,
                    "exit_code": test_result.exit_code,
                    "signal": test_result.signal,
                    "duration_ms": test_result.duration_ms,
                }
                if test_result
                else {"label": "test", "state": "not-run"}
            ),
            "static_phase": {"label": "static", "state": "not-run"},
            "limit_state": (
                "breached"
                if state == "timed-out-or-limited"
                else "within-limits"
            ),
            "limitation": RUNNER_LIMITATION,
        }
        with session_factory() as session:
            row = RunnerRepository(session).record(execution.request.owner_id, run_id)
            assert row is not None
            row.state = state
            row.outcome_json = json.dumps(result, sort_keys=True)
            stream_sequences: dict[str, int] = {}
            for ordinal, chunk in enumerate(chunks, 1):
                sequence = stream_sequences.get(chunk.stream, 0) + 1
                stream_sequences[chunk.stream] = sequence
                session.add(
                    RunnerOutputChunkRow(
                        id=new_id(),
                        owner_id=row.owner_id,
                        runner_id=row.id,
                        phase=chunk.phase,
                        stream=chunk.stream,
                        sequence=sequence,
                        ordinal=ordinal,
                        content_ref=chunk.content,
                        truncated=int(chunk.truncated),
                        created_at=utc_text(SystemClock().now()),
                    )
                )
            session.commit()
    except Exception as exc:
        failure = {
            "compile_phase": {"label": "compile", "state": "failed"},
            "test_phase": {"label": "test", "state": "not-run"},
            "static_phase": {"label": "static", "state": "not-run"},
            "limit_state": "unknown",
            "limitation": RUNNER_LIMITATION,
            "diagnostic": f"{type(exc).__name__}: {exc}",
        }
        with session_factory() as session:
            row = RunnerRepository(session).record(execution.request.owner_id, run_id)
            if row:
                row.state = "failed"
                row.outcome_json = json.dumps(failure, sort_keys=True)
                session.commit()
        raise
    finally:
        diagnostic = None
        if workspace is not None:
            try:
                workspace_port.cleanup(workspace)
                cleanup_state = "cleanup-complete"
            except Exception as exc:  # noqa: BLE001
                cleanup_state = "cleanup-failed"
                diagnostic = f"{type(exc).__name__}: {exc}"
        else:
            cleanup_state = "cleanup-complete"
        with session_factory() as session:
            row = RunnerRepository(session).record(execution.request.owner_id, run_id)
            if row:
                row.cleanup_state = cleanup_state
                row.cleanup_diagnostic = diagnostic
                session.commit()
    result_ref = f"RunnerRun:{run_id}"
    job_result = JobResult(
        "java_runner",
        "runner-v1",
        result_ref,
        hash_payload({"run_id": run_id, "cleanup_state": cleanup_state}),
    )
    return JobCompletion(job_result, lambda _session: job_result)
