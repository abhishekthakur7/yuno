from __future__ import annotations

import os
import resource
import selectors
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from math import ceil
from pathlib import Path
from tempfile import gettempdir, mkdtemp

from yuno.modules.runner.domain import OutputChunk, RunnerProcessOutcome
from yuno.modules.runner.platform_probe import (
    PlatformSnapshot,
    default_platform_snapshot,
    evaluate_platform,
)
from yuno.modules.runner.ports import RunnerProcessSpec
from yuno.shared.infrastructure.processes import process_identity

_PLATFORM_DIAGNOSTIC_DETAIL = {
    "unsupported-platform": (
        "Host platform, architecture, or virtualization layer is outside "
        "the IDK-005 approved runner matrix (Ubuntu 24.04 LTS, x86_64 or "
        "arm64, host or VM only)."
    ),
    "platform-unverifiable": (
        "Host platform identity could not be verified from local OS metadata."
    ),
}


def memory_limit_enforced() -> bool:
    return sys.platform != "darwin"


def workspace_usage(path: Path) -> tuple[int, int]:
    total_bytes = 0
    file_count = 0
    for root, directories, files in os.walk(path, followlinks=False):
        directories[:] = [
            name for name in directories if not (Path(root) / name).is_symlink()
        ]
        for name in files:
            total_bytes += (Path(root) / name).lstat().st_size
            file_count += 1
    return total_bytes, file_count


def detect_command(
    language: str,
    capability: str,
    command: str | None,
    prefix: str | None,
    *,
    platform_probe: Callable[[], PlatformSnapshot] = default_platform_snapshot,
) -> dict[str, str]:
    # IDK-005 section 1/3: a Java item may only report `supported` on the
    # approved Ubuntu 24.04 x86_64/arm64 host-or-VM row. This gate runs
    # before any command/version check and is independent of the separate
    # `runner_enabled` activation gate in `service.policy_ready`.
    platform_outcome = evaluate_platform(platform_probe())
    if platform_outcome.diagnostic_code is not None:
        return {
            "language": language,
            "capability": capability,
            "state": "incompatible",
            "diagnostic_code": platform_outcome.diagnostic_code,
            "detail": _PLATFORM_DIAGNOSTIC_DETAIL[platform_outcome.diagnostic_code],
        }
    path = shutil.which(command) if command else None
    if path is None:
        return {
            "language": language,
            "capability": capability,
            "state": "missing",
            "diagnostic_code": None,
            "detail": "Configured toolchain command is not present.",
        }
    if prefix:
        probe = subprocess.run(
            [path, "-version"],
            shell=False,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        version = (probe.stderr or probe.stdout).strip()
        if probe.returncode or not version.startswith(prefix):
            return {
                "language": language,
                "capability": capability,
                "state": "incompatible",
                "diagnostic_code": None,
                "detail": "Detected toolchain does not match the approved version prefix.",
            }
    return {
        "language": language,
        "capability": capability,
        "state": "supported",
        "diagnostic_code": None,
        "detail": "Configured toolchain detected at request time.",
    }


class LocalTempWorkspace:
    def create(self) -> Path:
        return Path(mkdtemp(prefix="yuno-runner-"))

    def cleanup(self, path: Path) -> None:
        if (
            not path.name.startswith("yuno-runner-")
            or path.parent.resolve() != Path(gettempdir()).resolve()
        ):
            raise ValueError("Refusing to clean a path outside a runner workspace.")
        shutil.rmtree(path)


class LocalRunnerProcessPort:
    """Runner-specific direct-argv process policy; never invokes a shell."""

    def run(self, spec: RunnerProcessSpec, *, on_spawn, cancelled):
        def apply_limits() -> None:
            cpu_seconds = max(1, ceil(spec.limits.cpu_seconds))
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds,) * 2)
            if memory_limit_enforced():
                resource.setrlimit(resource.RLIMIT_AS, (spec.limits.memory_bytes,) * 2)
            resource.setrlimit(resource.RLIMIT_NPROC, (spec.limits.process_count,) * 2)
            resource.setrlimit(resource.RLIMIT_FSIZE, (spec.limits.file_bytes,) * 2)

        started = time.monotonic()
        process = subprocess.Popen(
            list(spec.argv),
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=spec.working_directory,
            env=dict(spec.environment),
            start_new_session=True,
            preexec_fn=apply_limits,  # noqa: PLW1509 -- required local rlimits; runner is gated to approved platform
        )
        pgid = os.getpgid(process.pid)
        identity = process_identity(process.pid)
        on_spawn(process.pid, pgid, identity)
        selector = selectors.DefaultSelector()
        assert process.stdout is not None and process.stderr is not None
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        chunks: list[OutputChunk] = []
        sizes = {"stdout": 0, "stderr": 0}
        total_output_bytes = 0
        sequences = {"stdout": 0, "stderr": 0}
        limited = was_cancelled = False
        child_usage = None
        termination_started = None
        killed = False
        limit_classification = None

        def request_termination() -> None:
            nonlocal termination_started
            if termination_started is not None:
                return
            termination_started = time.monotonic()
            try:
                os.killpg(pgid, signal.SIGTERM)
            except ProcessLookupError:
                pass

        while True:
            if child_usage is None:
                waited_pid, status, usage = os.wait4(process.pid, os.WNOHANG)
                if waited_pid:
                    process.returncode = os.waitstatus_to_exitcode(status)
                    child_usage = usage
            if cancelled():
                was_cancelled = True
                request_termination()
            elif time.monotonic() - started >= spec.limits.wall_seconds:
                limited = True
                limit_classification = "runner-wall-time-limit"
                request_termination()
            elif termination_started is None:
                try:
                    temp_bytes, temp_files = workspace_usage(spec.working_directory)
                except OSError:
                    limited = True
                    limit_classification = "runner-temp-inspection-limit"
                    request_termination()
                else:
                    if temp_bytes > spec.limits.temp_bytes:
                        limited = True
                        limit_classification = "runner-temp-bytes-limit"
                        request_termination()
                    elif (
                        spec.limits.temp_files is not None
                        and temp_files > spec.limits.temp_files
                    ):
                        limited = True
                        limit_classification = "runner-temp-files-limit"
                        request_termination()
            if (
                termination_started is not None
                and not killed
                and time.monotonic() - termination_started >= 0.5
            ):
                killed = True
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            ready = selector.select(timeout=0.02 if child_usage is None else 0)
            for key, _ in ready:
                data = os.read(key.fileobj.fileno(), 65536)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                stream = str(key.data)
                stream_limit = (
                    spec.limits.stdout_bytes
                    if stream == "stdout"
                    else spec.limits.stderr_bytes
                )
                if stream_limit is None:
                    stream_limit = spec.limits.output_bytes
                stream_remaining = max(0, stream_limit - sizes[stream])
                total_remaining = max(0, spec.limits.output_bytes - total_output_bytes)
                remaining = min(stream_remaining, total_remaining)
                kept = data[:remaining]
                sizes[stream] += len(kept)
                total_output_bytes += len(kept)
                sequences[stream] += 1
                chunks.append(
                    OutputChunk(
                        spec.phase,
                        stream,
                        sequences[stream],
                        kept.decode("utf-8", errors="replace"),
                        len(kept) < len(data),
                    )
                )
                if len(kept) < len(data):
                    limited = True
                    limit_classification = (
                        f"runner-{stream}-limit"
                        if stream_remaining <= total_remaining
                        else "runner-output-limit"
                    )
                    request_termination()
            if child_usage is not None and not selector.get_map():
                break
        selector.close()
        assert process.returncode is not None and child_usage is not None
        code = process.returncode
        cpu_ms = int(max(0.0, child_usage.ru_utime + child_usage.ru_stime) * 1000)
        return RunnerProcessOutcome(
            process.pid,
            pgid,
            code,
            -code if code is not None and code < 0 else None,
            limited,
            was_cancelled,
            tuple(chunks),
            int((time.monotonic() - started) * 1000),
            cpu_ms,
            limit_classification,
        )
