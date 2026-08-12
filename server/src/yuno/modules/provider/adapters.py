"""No-shell CLI adapter and local process implementation.

Exact provider commands are deliberately supplied by configuration only after
IDK-006; this module does not claim a supported Codex/Claude invocation.
"""

from __future__ import annotations

import hashlib
import json
import os
import selectors
import signal
import subprocess
import threading
import time
from collections.abc import Iterable, Mapping
from pathlib import Path
from tempfile import mkdtemp

from yuno.modules.provider.domain import (
    ProcessOutcome,
    ProviderFailureClassification,
    ProviderName,
    ProviderResult,
    ProviderResultState,
    ProviderTimers,
    QuarantineDetails,
)
from yuno.modules.provider.ports import (
    ProcessPort,
    ProcessSpec,
    SecureOutputStore,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.infrastructure.processes import process_identity


class LocalProcessPort(ProcessPort):
    """Direct argv execution with process-group timeout/cancellation."""

    def run(self, spec: ProcessSpec, *, on_spawn, cancelled) -> ProcessOutcome:
        process = subprocess.Popen(
            list(spec.argv),
            shell=False,
            stdin=subprocess.PIPE if spec.stdin is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=dict(spec.environment),
            start_new_session=True,
        )
        try:
            pgid = os.getpgid(process.pid)
            identity = process_identity(process.pid)
            on_spawn(process.pid, pgid, identity)
        except BaseException:
            _terminate_group(process, process.pid)
            raise
        if spec.stdin is not None:
            threading.Thread(
                target=_write_stdin,
                args=(process, spec.stdin),
                name=f"provider-stdin-{process.pid}",
                daemon=True,
            ).start()

        selector = selectors.DefaultSelector()
        assert process.stdout is not None and process.stderr is not None
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        buffers = {"stdout": bytearray(), "stderr": bytearray()}
        started = last_output = time.monotonic()
        first_output = False
        classification = None
        was_cancelled = False
        while process.poll() is None:
            now = time.monotonic()
            if cancelled():
                was_cancelled = True
                classification = ProviderFailureClassification.CANCELLED
            elif now - started >= spec.timers.absolute_seconds:
                classification = ProviderFailureClassification.ABSOLUTE_TIMEOUT
            elif not first_output and now - started >= spec.timers.first_output_seconds:
                classification = (
                    ProviderFailureClassification.CONFIGURATION_OR_AUTHENTICATION
                )
            elif first_output and now - last_output >= spec.timers.inactivity_seconds:
                classification = ProviderFailureClassification.INACTIVITY_TIMEOUT
            if classification:
                _terminate_group(process, pgid)
                break
            for key, _ in selector.select(timeout=0.02):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if chunk:
                    buffers[key.data].extend(chunk)
                    first_output = True
                    last_output = time.monotonic()
        _drain_pipes(selector, buffers, time.monotonic() + 0.2)
        selector.close()
        if classification is None:
            # The CLI may exit while descendants retain inherited pipes. The
            # provider contract never permits orphan descendants after return.
            _terminate_group(process, pgid)
        return ProcessOutcome(
            pid=process.pid,
            pgid=pgid,
            process_identity=identity,
            stdout=bytes(buffers["stdout"]),
            stderr=bytes(buffers["stderr"]),
            exit_code=process.poll(),
            first_output_seen=first_output,
            timed_out=classification if not was_cancelled else None,
            cancelled=was_cancelled,
            truncated=classification is not None and bool(buffers["stdout"]),
        )


class CliProviderAdapter:
    """Pinned final-line JSON contract over a provider-specific argv/env policy."""

    def __init__(
        self,
        *,
        provider: ProviderName,
        model: str,
        argv: Iterable[str],
        adapter_version: str,
        contract_version: str,
        allowed_environment: Iterable[str],
        timers: ProviderTimers,
        process_port: ProcessPort,
        secure_output_store: SecureOutputStore,
        source_environment: Mapping[str, str] | None = None,
    ) -> None:
        command = tuple(argv)
        if not command or any(not part for part in command):
            raise ValueError("A direct, non-empty provider argv is required.")
        self.provider = provider.value
        self.model = model
        self.argv = command
        self.adapter_version = adapter_version
        self.contract_version = contract_version
        source = source_environment if source_environment is not None else os.environ
        self.environment = {
            key: source[key] for key in allowed_environment if key in source
        }
        self.timers = timers
        self.process_port = process_port
        self.secure_output_store = secure_output_store

    def invoke(self, request, validator, *, on_spawn, cancelled):
        stdin = json.dumps(
            {
                "purpose": request.purpose,
                "context": request.context,
                "output_schema_version": request.output_schema_version,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        outcome = self.process_port.run(
            ProcessSpec(self.argv, stdin, self.environment, self.timers),
            on_spawn=on_spawn,
            cancelled=cancelled,
        )
        classification = (
            ProviderFailureClassification.CANCELLED
            if outcome.cancelled
            else outcome.timed_out
        )
        if classification is None and outcome.exit_code not in (0, None):
            classification = ProviderFailureClassification.PROCESS_FAILED
        if classification is not None:
            diagnostic_ref = None
            if outcome.stdout or outcome.stderr:
                diagnostic_ref = self.secure_output_store.put(
                    outcome.stdout + b"\n" + outcome.stderr
                )
            return ProviderResult(
                ProviderResultState.FAILED,
                ProviderName(self.provider),
                self.model,
                self.contract_version,
                request.output_schema_version,
                None,
                None,
                classification,
                diagnostic_ref=diagnostic_ref,
                retryable=classification is not ProviderFailureClassification.CANCELLED,
            )
        raw = outcome.stdout
        try:
            final_line = next(
                line for line in reversed(raw.splitlines()) if line.strip()
            )
            payload = validator.validate(json.loads(final_line))
        except (json.JSONDecodeError, StopIteration, TypeError, ValueError) as exc:
            secure_ref = self.secure_output_store.put(raw)
            return ProviderResult(
                ProviderResultState.QUARANTINED,
                ProviderName(self.provider),
                self.model,
                self.contract_version,
                request.output_schema_version,
                None,
                None,
                ProviderFailureClassification.SCHEMA_INVALID,
                retryable=True,
                quarantine=QuarantineDetails(
                    raw_output_ref=secure_ref,
                    raw_output_hash=hashlib.sha256(raw).hexdigest(),
                    validation_errors=_validation_errors(exc),
                ),
            )
        return ProviderResult(
            ProviderResultState.SUCCEEDED,
            ProviderName(self.provider),
            self.model,
            self.contract_version,
            request.output_schema_version,
            payload,
            hash_payload(payload),
        )


class FileSecureOutputStore:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = (
            Path(root) if root else Path(mkdtemp(prefix="yuno-provider-quarantine-"))
        )
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def put(self, raw_output: bytes) -> str:
        name = hashlib.sha256(raw_output).hexdigest()
        path = self.root / name
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags, 0o600)
        except FileExistsError:
            return f"secure-provider-output:{name}"
        with os.fdopen(descriptor, "wb") as output:
            output.write(raw_output)
        return f"secure-provider-output:{name}"


def _write_stdin(process: subprocess.Popen[bytes], content: bytes) -> None:
    assert process.stdin is not None
    try:
        process.stdin.write(content)
        process.stdin.close()
    except (BrokenPipeError, OSError):
        pass


def _terminate_group(process: subprocess.Popen[bytes], pgid: int) -> None:
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 0.5
    while time.monotonic() < deadline and _group_exists(pgid):
        try:
            process.wait(timeout=0.02)
        except subprocess.TimeoutExpired:
            pass
    if _group_exists(pgid):
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait()
    except ChildProcessError:
        pass


def _group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _drain_pipes(selector, buffers: dict[str, bytearray], deadline: float) -> None:
    for item in selector.get_map().values():
        try:
            os.set_blocking(item.fileobj.fileno(), False)
        except (AttributeError, OSError):
            pass
    while selector.get_map() and time.monotonic() < deadline:
        ready = selector.select(timeout=0.01)
        if not ready:
            continue
        for key, _ in ready:
            try:
                chunk = os.read(key.fileobj.fileno(), 65536)
            except BlockingIOError:
                continue
            except OSError:
                chunk = b""
            if chunk:
                buffers[key.data].extend(chunk)
            else:
                try:
                    selector.unregister(key.fileobj)
                except (AttributeError, KeyError):
                    return


def _validation_errors(exc: Exception) -> tuple[str, ...]:
    errors = getattr(exc, "errors", None)
    if callable(errors):
        try:
            return tuple(
                f"{'.'.join(str(part) for part in item.get('loc', ()))}:{item.get('type', 'invalid')}"
                for item in errors(include_input=False)
            ) or ("schema:invalid",)
        except TypeError:
            pass
    return (f"schema:{type(exc).__name__}",)
