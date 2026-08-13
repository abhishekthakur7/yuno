"""Shared no-shell process and quarantine storage for approved CLI adapters."""

from __future__ import annotations

import hashlib
import json
import os
import selectors
import stat
import subprocess
import threading
import time
from collections.abc import Mapping
from pathlib import Path
from tempfile import mkdtemp

from yuno.modules.provider.domain import (
    ProcessOutcome,
    ProviderFailureClassification,
)
from yuno.modules.provider.ports import ProcessPort, ProcessSpec
from yuno.shared.infrastructure.processes import (
    process_identity,
    terminate_process_group,
)

PROVIDER_STDOUT_LIMIT_BYTES = 2 * 1024 * 1024
PROVIDER_STDERR_LIMIT_BYTES = 64 * 1024
PROVIDER_PROBE_OUTPUT_LIMIT_BYTES = 64 * 1024


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
            cwd=spec.cwd,
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
        heartbeat_offset = 0
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
                classification = ProviderFailureClassification.NO_FIRST_OUTPUT
            elif first_output and now - last_output >= spec.timers.inactivity_seconds:
                classification = ProviderFailureClassification.INACTIVITY_TIMEOUT
            if classification:
                _terminate_group(process, pgid)
                break
            for key, _ in selector.select(timeout=0.02):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if chunk:
                    limit = (
                        spec.stdout_limit_bytes
                        if key.data == "stdout"
                        else spec.stderr_limit_bytes
                    )
                    if not _append_bounded(buffers[key.data], chunk, limit):
                        classification = ProviderFailureClassification.OUTPUT_LIMIT
                        _terminate_group(process, pgid)
                        break
                    if key.data == "stdout":
                        if spec.json_event_heartbeat:
                            heartbeat, heartbeat_offset = _json_event_heartbeat(
                                buffers["stdout"], heartbeat_offset
                            )
                        else:
                            heartbeat = True
                        if heartbeat:
                            first_output = True
                            last_output = time.monotonic()
        drain_limited = _drain_pipes(
            selector,
            buffers,
            {
                "stdout": spec.stdout_limit_bytes,
                "stderr": spec.stderr_limit_bytes,
            },
            time.monotonic() + 0.2,
        )
        if drain_limited and classification is None:
            classification = ProviderFailureClassification.OUTPUT_LIMIT
            _terminate_group(process, pgid)
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
            truncated=(
                classification is not None
                and bool(buffers["stdout"] or buffers["stderr"])
            ),
        )


class FileSecureOutputStore:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = (
            Path(root) if root else Path(mkdtemp(prefix="yuno-provider-quarantine-"))
        )
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        status = self.root.lstat()
        if not stat.S_ISDIR(status.st_mode) or stat.S_ISLNK(status.st_mode):
            raise ValueError("Provider quarantine root must be a real directory.")
        if status.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            os.chmod(self.root, 0o700)
            status = self.root.lstat()
        if stat.S_IMODE(status.st_mode) != 0o700:
            raise ValueError("Provider quarantine root must be owner-only.")

    def put(self, raw_output: bytes) -> str:
        name = hashlib.sha256(raw_output).hexdigest()
        path = self.root / name
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags, 0o600)
        except FileExistsError:
            self._verify_existing(path, raw_output)
            return f"secure-provider-output:{name}"
        with os.fdopen(descriptor, "wb") as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(raw_output)
            output.flush()
            os.fsync(output.fileno())
        return f"secure-provider-output:{name}"

    @staticmethod
    def _verify_existing(path: Path, expected: bytes) -> None:
        before = path.lstat()
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or stat.S_IMODE(before.st_mode) != 0o600
        ):
            raise RuntimeError("Existing quarantine output is not a private file.")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as source:
            opened = os.fstat(source.fileno())
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_nlink != 1
                or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
                or source.read() != expected
            ):
                raise RuntimeError("Existing quarantine output failed validation.")


def remove_unreferenced_provider_outputs(root: Path, referenced: set[str]) -> int:
    """Remove content-addressed quarantine bodies with no committed DB record."""
    if not root.exists():
        return 0
    status = root.lstat()
    if not stat.S_ISDIR(status.st_mode) or stat.S_ISLNK(status.st_mode):
        raise ValueError("Provider quarantine root must be a real directory.")
    removed = 0
    for path in root.iterdir():
        name = path.name
        if len(name) != 64 or any(char not in "0123456789abcdef" for char in name):
            continue
        file_status = path.lstat()
        if (
            not stat.S_ISREG(file_status.st_mode)
            or file_status.st_nlink != 1
            or stat.S_IMODE(file_status.st_mode) != 0o600
        ):
            continue
        if f"secure-provider-output:{name}" in referenced:
            continue
        path.unlink()
        removed += 1
    return removed


def _write_stdin(process: subprocess.Popen[bytes], content: bytes) -> None:
    assert process.stdin is not None
    try:
        process.stdin.write(content)
        process.stdin.close()
    except (BrokenPipeError, OSError):
        pass


def _terminate_group(process: subprocess.Popen[bytes], pgid: int) -> None:
    try:
        terminate_process_group(pgid)
    except PermissionError:
        # macOS can report EPERM for a just-exited, unreaped group leader.
        # Reaping below is authoritative for this process-owned group.
        pass
    try:
        process.wait()
    except ChildProcessError:
        pass


def _drain_pipes(
    selector,
    buffers: dict[str, bytearray],
    limits: dict[str, int],
    deadline: float,
) -> bool:
    limited = False
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
                if not _append_bounded(buffers[key.data], chunk, limits[key.data]):
                    limited = True
            else:
                try:
                    selector.unregister(key.fileobj)
                except (AttributeError, KeyError):
                    return limited
    return limited


def _append_bounded(buffer: bytearray, chunk: bytes, limit: int) -> bool:
    remaining = limit - len(buffer)
    if remaining > 0:
        buffer.extend(chunk[:remaining])
    return len(chunk) <= remaining


def versioned_output_schema(
    payload_schema: Mapping[str, object], contract_version: str, schema_version: str
) -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "contract_version": {"const": contract_version, "type": "string"},
            "schema_version": {"const": schema_version, "type": "string"},
            "payload": payload_schema,
        },
        "required": ["contract_version", "schema_version", "payload"],
        "additionalProperties": False,
    }


def unwrap_versioned_output(
    value: object, contract_version: str, schema_version: str
) -> object:
    if not isinstance(value, dict) or set(value) != {
        "contract_version",
        "schema_version",
        "payload",
    }:
        raise ValueError("Provider output omitted the versioned envelope.")
    if value["contract_version"] != contract_version:
        raise ValueError("Provider output contract version does not match.")
    if value["schema_version"] != schema_version:
        raise ValueError("Provider output schema version does not match.")
    return value["payload"]


def strict_json_loads(value: str | bytes) -> object:
    def unique_object(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("JSON objects must not contain duplicate fields.")
            result[key] = item
        return result

    return json.loads(value, object_pairs_hook=unique_object)


def _json_event_heartbeat(buffer: bytearray, offset: int) -> tuple[bool, int]:
    heartbeat = False
    while True:
        end = buffer.find(b"\n", offset)
        if end < 0:
            break
        line = bytes(buffer[offset:end]).strip()
        offset = end + 1
        if not line:
            continue
        try:
            event = strict_json_loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            continue
        if isinstance(event, dict) and isinstance(event.get("type"), str):
            heartbeat = True
    return heartbeat, offset
