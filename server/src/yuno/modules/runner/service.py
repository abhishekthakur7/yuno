from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path, PurePosixPath

from yuno.config import Settings
from yuno.modules.runner.domain import (
    RUNNER_LIMITATION,
    DeclaredInput,
    OutputChunk,
    ProcessLimits,
    RunnerProcessOutcome,
)
from yuno.modules.runner.models import (
    RunnerConfirmationInputBodyRow,
    RunnerConfirmationInputRow,
    RunnerConfirmationRow,
    RunnerOutputChunkBodyRow,
    RunnerOutputChunkRow,
)
from yuno.modules.runner.ports import (
    ProcessPort,
    RunnerProcessSpec,
    TempWorkspacePort,
    WorkspaceCleanupIntentFactory,
)
from yuno.modules.runner.repository import RunnerRepository
from yuno.shared.application.jobs import JobCompletion, JobExecution, JobResult
from yuno.shared.domain.clock import Clock, SystemClock, utc_text
from yuno.shared.domain.errors import (
    DomainValidationError,
    NotFoundError,
    RunnerInputLimitError,
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


class _RunnerLimitBreach(RunnerInputLimitError):
    def __init__(self, message: str, classification: str) -> None:
        super().__init__(message)
        self.classification = classification


def policy_ready(settings: Settings) -> bool:
    required = (
        settings.runner_environment_policy_version,
        settings.runner_limits_config_version,
        settings.runner_confirmation_ttl_seconds,
        settings.runner_wall_time_seconds,
        settings.runner_cpu_seconds,
        settings.runner_memory_bytes,
        settings.runner_process_limit,
        settings.runner_input_files_limit,
        settings.runner_input_bytes_limit,
        settings.runner_stdout_bytes_limit,
        settings.runner_stderr_bytes_limit,
        settings.runner_output_bytes,
        settings.runner_file_bytes,
        settings.runner_temp_bytes,
        settings.runner_temp_files_limit,
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


def resolve_inputs_within_limits(
    inputs: tuple[DeclaredInput, ...], settings: Settings
) -> tuple[tuple[DeclaredInput, bytes], ...]:
    if len(inputs) > settings.runner_input_files_limit:
        raise _RunnerLimitBreach(
            f"Runner inputs exceed the {settings.runner_input_files_limit}-file limit.",
            "runner-input-files-limit",
        )
    resolved: list[tuple[DeclaredInput, bytes]] = []
    total_bytes = 0
    for item in inputs:
        content = validate_input(item)
        total_bytes += len(content)
        if total_bytes > settings.runner_input_bytes_limit:
            raise _RunnerLimitBreach(
                "Runner inputs exceed the 10 MiB aggregate decoded-byte limit.",
                "runner-input-bytes-limit",
            )
        resolved.append((item, content))
    return tuple(resolved)


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
    resolved = resolve_inputs_within_limits(inputs, settings)
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
        input_id = new_id()
        session.add_all(
            (
                RunnerConfirmationInputRow(
                    id=input_id,
                    owner_id=owner_id,
                    confirmation_id=row.id,
                    logical_path=item.logical_path,
                    declared_type=item.declared_type,
                    content_hash=item.content_hash,
                ),
                RunnerConfirmationInputBodyRow(
                    input_id=input_id,
                    owner_id=owner_id,
                    resolved_content=base64.b64encode(content).decode("ascii"),
                ),
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


def _workspace_usage(workspace) -> tuple[int, int]:
    total_bytes = 0
    file_count = 0
    for root, directories, files in os.walk(workspace, followlinks=False):
        directories[:] = [
            name
            for name in directories
            if not (workspace / Path(root).relative_to(workspace) / name).is_symlink()
        ]
        for name in files:
            total_bytes += (Path(root) / name).lstat().st_size
            file_count += 1
    return total_bytes, file_count


def _trim_chunks(
    chunks: list[OutputChunk], byte_count: int, *, stream: str | None = None
) -> None:
    remaining = byte_count
    for index in range(len(chunks) - 1, -1, -1):
        chunk = chunks[index]
        if stream is not None and chunk.stream != stream:
            continue
        encoded = chunk.content.encode("utf-8")
        removed = min(remaining, len(encoded))
        kept = encoded[: len(encoded) - removed].decode("utf-8", errors="ignore")
        chunks[index] = OutputChunk(
            chunk.phase, chunk.stream, chunk.sequence, kept, chunk.truncated
        )
        remaining -= len(encoded) - len(kept.encode("utf-8"))
        if remaining <= 0:
            break


def _bounded_chunks(
    chunks: tuple[OutputChunk, ...], limits: ProcessLimits, classification: str | None
) -> tuple[list[OutputChunk], str | None]:
    bounded: list[OutputChunk] = []
    stream_bytes = {"stdout": 0, "stderr": 0}
    total_bytes = 0
    for chunk in chunks:
        encoded = chunk.content.encode("utf-8")
        stream_limit = (
            limits.stdout_bytes if chunk.stream == "stdout" else limits.stderr_bytes
        )
        assert stream_limit is not None
        stream_remaining = max(0, stream_limit - stream_bytes[chunk.stream])
        total_remaining = max(0, limits.output_bytes - total_bytes)
        available = min(stream_remaining, total_remaining)
        kept = encoded[:available]
        breached = chunk.truncated or len(kept) < len(encoded)
        if kept:
            bounded.append(
                OutputChunk(
                    chunk.phase,
                    chunk.stream,
                    chunk.sequence,
                    kept.decode("utf-8", errors="ignore"),
                    False,
                )
            )
            kept_size = len(bounded[-1].content.encode("utf-8"))
            stream_bytes[chunk.stream] += kept_size
            total_bytes += kept_size
        if not breached:
            continue
        effective = classification or (
            f"runner-{chunk.stream}-limit"
            if stream_remaining <= total_remaining
            else "runner-output-limit"
        )
        marker = f"\n[YUNO runner output truncated: {effective}]\n"
        marker_size = len(marker.encode("utf-8"))
        stream_shortfall = max(
            0, stream_bytes[chunk.stream] + marker_size - stream_limit
        )
        if stream_shortfall:
            _trim_chunks(bounded, stream_shortfall, stream=chunk.stream)
        current_total = sum(len(item.content.encode("utf-8")) for item in bounded)
        total_shortfall = max(0, current_total + marker_size - limits.output_bytes)
        if total_shortfall:
            _trim_chunks(bounded, total_shortfall)
        bounded.append(
            OutputChunk(chunk.phase, chunk.stream, chunk.sequence + 1, marker, True)
        )
        return bounded, effective
    return bounded, classification


def _output_usage(chunks: list[OutputChunk]) -> tuple[dict[str, int], int]:
    streams = {"stdout": 0, "stderr": 0}
    for chunk in chunks:
        streams[chunk.stream] += len(chunk.content.encode("utf-8"))
    return streams, sum(streams.values())


def _workspace_limit_classification(workspace, limits: ProcessLimits) -> str | None:
    temp_bytes, temp_files = _workspace_usage(workspace)
    if temp_bytes > limits.temp_bytes:
        return "runner-temp-bytes-limit"
    if limits.temp_files is not None and temp_files > limits.temp_files:
        return "runner-temp-files-limit"
    return None


def _resolve_authoritative_inputs(inputs, settings: Settings):
    if len(inputs) > settings.runner_input_files_limit:
        raise _RunnerLimitBreach(
            f"Runner inputs exceed the {settings.runner_input_files_limit}-file limit.",
            "runner-input-files-limit",
        )
    resolved = []
    total_bytes = 0
    for item in inputs:
        if item.content_ref is None:
            raise DomainValidationError("Confirmed runner input body is unavailable.")
        if not item.content_ref.startswith("confirmed-base64:"):
            raise DomainValidationError(
                "Runner input is not an authoritative confirmed snapshot."
            )
        try:
            content = base64.b64decode(
                item.content_ref.removeprefix("confirmed-base64:"), validate=True
            )
        except ValueError as exc:
            raise DomainValidationError(
                "Confirmed runner input is invalid base64."
            ) from exc
        total_bytes += len(content)
        if total_bytes > settings.runner_input_bytes_limit:
            raise _RunnerLimitBreach(
                "Runner inputs exceed the 10 MiB aggregate decoded-byte limit.",
                "runner-input-bytes-limit",
            )
        if hashlib.sha256(content).hexdigest() != item.content_hash:
            raise DomainValidationError(
                "Confirmed runner input hash changed before execution."
            )
        resolved.append((item, content))
    return resolved


def execute_runner_job(
    execution: JobExecution,
    session_factory,
    settings: Settings,
    process_port: ProcessPort,
    workspace_port: TempWorkspacePort,
    cleanup_intents: WorkspaceCleanupIntentFactory,
    workspace_reference: Callable[[Path], str | None],
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
    workspace_ref = None
    cleanup_state = "cleanup-pending"
    try:
        authoritative_inputs = _resolve_authoritative_inputs(inputs, settings)
        workspace = workspace_port.create()
        workspace_ref = workspace_reference(workspace)
        if workspace_ref is None:
            raise DomainValidationError(
                "Runner workspace is outside the approved temporary root."
            )
        with session_factory() as session:
            row = RunnerRepository(session).record(execution.request.owner_id, run_id)
            assert row is not None
            row.temp_path = str(workspace)
            row.temp_path_hash = hash_payload(str(workspace))
            session.commit()
        for item, content in authoritative_inputs:
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
            int(settings.runner_stdout_bytes_limit),
            int(settings.runner_stderr_bytes_limit),
            int(settings.runner_temp_files_limit),
        )
        initial_limit_classification = _workspace_limit_classification(
            workspace, limits
        )
        with session_factory() as session:
            row = RunnerRepository(session).record(execution.request.owner_id, run_id)
            assert row is not None
            row.argv_json = json.dumps(argv)
            row.argv_hash = hash_payload(argv)
            row.state = "running"
            session.commit()
        if initial_limit_classification is not None:
            outcome = RunnerProcessOutcome(
                0,
                0,
                None,
                None,
                True,
                False,
                (OutputChunk("compile", "stderr", 1, "", True),),
                0,
                None,
                initial_limit_classification,
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
        chunks, output_limit_classification = _bounded_chunks(
            outcome.chunks, limits, outcome.limit_classification
        )
        output_usage, output_bytes = _output_usage(chunks)
        wall_ms = outcome.duration_ms
        cpu_ms = outcome.cpu_ms or 0
        cpu_observed = outcome.cpu_ms is not None
        workspace_limit_classification = _workspace_limit_classification(
            workspace, limits
        )
        limit_classification = (
            outcome.limit_classification
            or output_limit_classification
            or workspace_limit_classification
        )
        if limit_classification is None and outcome.timed_out_or_limited:
            limit_classification = "runner-resource-limit"
        if wall_ms > limits.wall_seconds * 1000:
            limit_classification = "runner-wall-time-limit"
        elif cpu_observed and cpu_ms > limits.cpu_seconds * 1000:
            limit_classification = "runner-cpu-time-limit"
        compile_limited = (
            outcome.timed_out_or_limited
            or output_limit_classification is not None
            or wall_ms > limits.wall_seconds * 1000
            or (cpu_observed and cpu_ms > limits.cpu_seconds * 1000)
            or workspace_limit_classification is not None
        )
        if workspace_limit_classification and not outcome.limit_classification:
            chunks, limit_classification = _bounded_chunks(
                (*chunks, OutputChunk("compile", "stderr", 1, "", True)),
                limits,
                workspace_limit_classification,
            )
            output_usage, output_bytes = _output_usage(chunks)
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
                    int(limits.stdout_bytes or 0) - output_usage["stdout"],
                    int(limits.stderr_bytes or 0) - output_usage["stderr"],
                    limits.temp_files,
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
                raw_chunks = (*chunks, *test_result.chunks)
                chunks, test_output_limit_classification = _bounded_chunks(
                    raw_chunks,
                    limits,
                    test_result.limit_classification,
                )
                output_usage, output_bytes = _output_usage(chunks)
                wall_ms += test_result.duration_ms
                if test_result.cpu_ms is not None:
                    cpu_ms += test_result.cpu_ms
                    cpu_observed = True
                workspace_limit_classification = _workspace_limit_classification(
                    workspace, limits
                )
                limit_classification = (
                    limit_classification
                    or test_result.limit_classification
                    or test_output_limit_classification
                    or workspace_limit_classification
                )
                if limit_classification is None and test_result.timed_out_or_limited:
                    limit_classification = "runner-resource-limit"
                if wall_ms > limits.wall_seconds * 1000:
                    limit_classification = "runner-wall-time-limit"
                elif cpu_observed and cpu_ms > limits.cpu_seconds * 1000:
                    limit_classification = "runner-cpu-time-limit"
                test_limited = (
                    test_result.timed_out_or_limited
                    or test_output_limit_classification is not None
                    or wall_ms > limits.wall_seconds * 1000
                    or (cpu_observed and cpu_ms > limits.cpu_seconds * 1000)
                    or workspace_limit_classification is not None
                )
                if (
                    workspace_limit_classification
                    and not test_result.limit_classification
                ):
                    chunks, limit_classification = _bounded_chunks(
                        (*chunks, OutputChunk("test", "stderr", 1, "", True)),
                        limits,
                        workspace_limit_classification,
                    )
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
                        limit_classification,
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
                "breached" if state == "timed-out-or-limited" else "within-limits"
            ),
            "limit_classification": limit_classification,
            "limitation": RUNNER_LIMITATION,
        }
        with session_factory() as session:
            row = RunnerRepository(session).record(execution.request.owner_id, run_id)
            assert row is not None
            row.state = state
            row.limit_classification = limit_classification
            row.outcome_json = json.dumps(result, sort_keys=True)
            row.outcome_hash = hash_payload(result)
            stream_sequences: dict[str, int] = {}
            for ordinal, chunk in enumerate(chunks, 1):
                sequence = stream_sequences.get(chunk.stream, 0) + 1
                stream_sequences[chunk.stream] = sequence
                content_hash = hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()
                chunk_id = new_id()
                session.add_all(
                    (
                        RunnerOutputChunkRow(
                            id=chunk_id,
                            owner_id=row.owner_id,
                            runner_id=row.id,
                            phase=chunk.phase,
                            stream=chunk.stream,
                            sequence=sequence,
                            ordinal=ordinal,
                            content_hash=content_hash,
                            truncated=int(chunk.truncated),
                            created_at=utc_text(SystemClock().now()),
                        ),
                        RunnerOutputChunkBodyRow(
                            chunk_id=chunk_id,
                            owner_id=row.owner_id,
                            content_ref=chunk.content,
                        ),
                    )
                )
            session.commit()
    except Exception as exc:
        failure = {
            "compile_phase": {"label": "compile", "state": "failed"},
            "test_phase": {"label": "test", "state": "not-run"},
            "static_phase": {"label": "static", "state": "not-run"},
            "limit_state": "unknown",
            "limit_classification": getattr(exc, "classification", None),
            "limitation": RUNNER_LIMITATION,
            "diagnostic": "runner-execution-failed",
        }
        with session_factory() as session:
            row = RunnerRepository(session).record(execution.request.owner_id, run_id)
            if row:
                row.state = "failed"
                row.limit_classification = getattr(exc, "classification", None)
                row.outcome_json = json.dumps(failure, sort_keys=True)
                row.outcome_hash = hash_payload(failure)
                session.commit()
        raise
    finally:
        diagnostic = None
        if workspace is not None:
            try:
                workspace_port.cleanup(workspace)
                cleanup_state = "cleanup-complete"
            except Exception:  # noqa: BLE001
                cleanup_state = "cleanup-failed"
                diagnostic = "runner-workspace-cleanup-failed"
        else:
            cleanup_state = "cleanup-complete"
        with session_factory() as session:
            row = RunnerRepository(session).record(execution.request.owner_id, run_id)
            if row:
                if cleanup_state == "cleanup-failed" and workspace_ref is not None:
                    timestamp = utc_text(SystemClock().now())
                    cleanup_intents(session).record_workspace(
                        owner_id=row.owner_id,
                        goal_id=row.goal_id,
                        path_ref=workspace_ref,
                        failure_classification=diagnostic,
                        created_at=timestamp,
                    )
                row.temp_path = None
                row.cleanup_state = cleanup_state
                row.cleanup_classification = diagnostic
                session.commit()
    result_ref = f"RunnerRun:{run_id}"
    job_result = JobResult(
        "java_runner",
        "runner-v1",
        result_ref,
        hash_payload({"run_id": run_id, "cleanup_state": cleanup_state}),
    )
    return JobCompletion(job_result, lambda _session: job_result)
