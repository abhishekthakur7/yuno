"""Claude Code discovery and adapter policy approved by IDK-006 v1.0."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from tempfile import TemporaryDirectory, gettempdir
from typing import Any
from urllib.parse import urlsplit

from yuno.modules.provider.adapters import (
    PROVIDER_PROBE_OUTPUT_LIMIT_BYTES,
    PROVIDER_STDERR_LIMIT_BYTES,
    PROVIDER_STDOUT_LIMIT_BYTES,
    unwrap_versioned_output,
    versioned_output_schema,
)
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
    OutputValidator,
    ProcessPort,
    ProcessSpec,
    SecureOutputStore,
)
from yuno.shared.domain.hashing import hash_payload

CLAUDE_ADAPTER_VERSION = "claude-code-adapter-v1"
CLAUDE_CONTRACT_VERSION = "claude-stream-json-structured-output-v1"
CLAUDE_MODEL = "claude-sonnet-4-6"
CLAUDE_MINIMUM_VERSION = (2, 1, 220)
CLAUDE_MAXIMUM_VERSION_EXCLUSIVE = (2, 2, 0)
CLAUDE_TIMERS = ProviderTimers(20, 180, 1_200)
CLAUDE_DEFAULT_EXECUTABLE = "/opt/homebrew/bin/claude"
CLAUDE_ENVIRONMENT_ALLOWLIST = (
    "HOME",
    "PATH",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "NODE_EXTRA_CA_CERTS",
)

_VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+) \(Claude Code\)\n?$")
_ROOT_FLAGS = (
    "-p, --print",
    "--input-format",
    "--output-format",
    "--verbose",
    "--json-schema",
    "--model",
    "--tools",
    "--strict-mcp-config",
    "--no-session-persistence",
    "--permission-mode",
    "--safe-mode",
)
_MAX_PROBE_OUTPUT_BYTES = 64 * 1024


class ClaudeCapabilityClassification(StrEnum):
    EXECUTABLE_MISSING = "executable-missing"
    UNSUPPORTED_VERSION = "unsupported-version"
    AUTHENTICATION_UNAVAILABLE = "authentication-unavailable"
    CONFIGURED = "configured"


@dataclass(frozen=True)
class ClaudeCapability:
    classification: ClaudeCapabilityClassification
    version: str | None = None
    executable: str | None = None

    @property
    def configured(self) -> bool:
        return self.classification is ClaudeCapabilityClassification.CONFIGURED


class ClaudeCliAdapter:
    """Pinned stream-JSON Claude adapter using the shared process runner."""

    provider = ProviderName.CLAUDE.value
    model = CLAUDE_MODEL
    adapter_version = CLAUDE_ADAPTER_VERSION
    contract_version = CLAUDE_CONTRACT_VERSION

    def __init__(
        self,
        *,
        executable: str,
        process_port: ProcessPort,
        secure_output_store: SecureOutputStore,
        source_environment: Mapping[str, str],
        timers: ProviderTimers = CLAUDE_TIMERS,
        temp_root: Path | None = None,
        verify_auth_before_invoke: bool = True,
    ) -> None:
        self.executable = str(resolve_claude_executable(executable))
        self.environment = claude_environment(source_environment)
        self.timers = timers
        self.process_port = process_port
        self.secure_output_store = secure_output_store
        self.temp_root = temp_root or Path(gettempdir())
        self._executable_identity = _executable_identity(self.executable)
        self.verify_auth_before_invoke = verify_auth_before_invoke

    def invoke(self, request, validator, *, on_spawn, cancelled):
        current_identity = _executable_identity(self.executable)
        if current_identity is None:
            return _failed_result(
                request,
                self.contract_version,
                ProviderFailureClassification.EXECUTABLE_MISSING,
            )
        if current_identity != self._executable_identity:
            return _failed_result(
                request,
                self.contract_version,
                ProviderFailureClassification.UNSUPPORTED_VERSION,
            )
        if self.verify_auth_before_invoke:
            try:
                auth = _run_probe(
                    self.process_port,
                    (self.executable, "auth", "status", "--json"),
                    self.environment,
                    self.timers,
                )
            except (OSError, RuntimeError):
                auth = None
            if auth is None or not _authenticated(auth):
                return _failed_result(
                    request,
                    self.contract_version,
                    ProviderFailureClassification.AUTHENTICATION_UNAVAILABLE,
                )
        schema_json = _validator_schema(
            validator, self.contract_version, request.output_schema_version
        )
        stdin = json.dumps(
            {
                "purpose": request.purpose,
                "context": request.context,
                "output_schema_version": request.output_schema_version,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        with TemporaryDirectory(
            prefix="yuno-runner-provider-claude-", dir=self.temp_root
        ) as temp:
            outcome = self.process_port.run(
                ProcessSpec(
                    claude_argv(self.executable, schema_json),
                    stdin,
                    self.environment,
                    self.timers,
                    cwd=temp,
                    json_event_heartbeat=True,
                    stdout_limit_bytes=PROVIDER_STDOUT_LIMIT_BYTES,
                    stderr_limit_bytes=PROVIDER_STDERR_LIMIT_BYTES,
                ),
                on_spawn=lambda pid, pgid, identity: on_spawn(
                    pid, pgid, identity, temp
                ),
                cancelled=cancelled,
            )
        failure = _process_failure(outcome)
        if failure is not None:
            return ProviderResult(
                ProviderResultState.FAILED,
                ProviderName.CLAUDE,
                CLAUDE_MODEL,
                self.contract_version,
                request.output_schema_version,
                None,
                None,
                failure,
                retryable=failure is not ProviderFailureClassification.CANCELLED,
            )

        raw = outcome.stdout
        try:
            terminal = _terminal_result(raw)
            if terminal.get("is_error") is not False:
                return ProviderResult(
                    ProviderResultState.FAILED,
                    ProviderName.CLAUDE,
                    CLAUDE_MODEL,
                    self.contract_version,
                    request.output_schema_version,
                    None,
                    None,
                    ProviderFailureClassification.PROVIDER_REPORTED_FAILURE,
                    retryable=True,
                )
            envelope = terminal["structured_output"]
            payload = validator.validate(
                unwrap_versioned_output(
                    envelope, self.contract_version, request.output_schema_version
                )
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            secure_ref = self.secure_output_store.put(raw)
            return ProviderResult(
                ProviderResultState.QUARANTINED,
                ProviderName.CLAUDE,
                CLAUDE_MODEL,
                self.contract_version,
                request.output_schema_version,
                None,
                None,
                ProviderFailureClassification.SCHEMA_INVALID,
                retryable=True,
                quarantine=QuarantineDetails(
                    raw_output_ref=secure_ref,
                    raw_output_hash=hashlib.sha256(raw).hexdigest(),
                    validation_errors=(f"schema:{type(exc).__name__}",),
                ),
            )
        return ProviderResult(
            ProviderResultState.SUCCEEDED,
            ProviderName.CLAUDE,
            CLAUDE_MODEL,
            self.contract_version,
            request.output_schema_version,
            payload,
            hash_payload(payload),
        )


def claude_argv(executable: str, schema_json: str) -> tuple[str, ...]:
    """Return the exact IDK-006 argv; prompt/context are written to stdin."""
    if not schema_json:
        raise ValueError("Claude requires an operation-specific JSON Schema.")
    return (
        executable,
        "-p",
        "--input-format",
        "text",
        "--output-format",
        "stream-json",
        "--verbose",
        "--json-schema",
        schema_json,
        "--model",
        CLAUDE_MODEL,
        "--tools",
        "",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--permission-mode",
        "dontAsk",
        "--safe-mode",
    )


def resolve_claude_executable(executable: str) -> Path:
    candidate = Path(executable)
    if not candidate.is_absolute():
        raise FileNotFoundError("Claude executable must be an absolute path.")
    try:
        resolved = candidate.resolve(strict=True)
        metadata = resolved.stat()
    except (OSError, RuntimeError) as exc:
        raise FileNotFoundError("Claude executable is unavailable.") from exc
    if not stat.S_ISREG(metadata.st_mode) or not os.access(resolved, os.X_OK):
        raise FileNotFoundError("Claude executable is unavailable.")
    if metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise FileNotFoundError("Claude executable is unsafe.")
    return resolved


def claude_environment(source: Mapping[str, str]) -> dict[str, str]:
    environment = {
        key: source[key] for key in CLAUDE_ENVIRONMENT_ALLOWLIST if key in source
    }
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        value = environment.get(key)
        if value and _proxy_has_credentials(value):
            raise ValueError("Credentialed proxy URLs are not allowed.")
    return environment


def discover_claude(
    executable: str,
    *,
    process_port: ProcessPort,
    probe_timers: ProviderTimers,
    source_environment: Mapping[str, str],
) -> ClaudeCapability:
    """Use documented metadata commands; never inspect credential files."""
    try:
        resolved = resolve_claude_executable(executable)
    except FileNotFoundError:
        return ClaudeCapability(ClaudeCapabilityClassification.EXECUTABLE_MISSING)
    try:
        environment = claude_environment(source_environment)
    except ValueError:
        return ClaudeCapability(
            ClaudeCapabilityClassification.AUTHENTICATION_UNAVAILABLE,
            executable=str(resolved),
        )

    try:
        version_outcome = _run_probe(
            process_port, (str(resolved), "--version"), environment, probe_timers
        )
    except (OSError, RuntimeError):
        return ClaudeCapability(ClaudeCapabilityClassification.EXECUTABLE_MISSING)
    version = parse_claude_version(version_outcome.stdout)
    if not _successful_probe(version_outcome) or version is None:
        return ClaudeCapability(
            ClaudeCapabilityClassification.UNSUPPORTED_VERSION,
            executable=str(resolved),
        )
    version_text, version_tuple = version
    if not (CLAUDE_MINIMUM_VERSION <= version_tuple < CLAUDE_MAXIMUM_VERSION_EXCLUSIVE):
        return ClaudeCapability(
            ClaudeCapabilityClassification.UNSUPPORTED_VERSION,
            version_text,
            str(resolved),
        )

    try:
        root_help = _run_probe(
            process_port, (str(resolved), "--help"), environment, probe_timers
        )
        auth_help = _run_probe(
            process_port,
            (str(resolved), "auth", "status", "--help"),
            environment,
            probe_timers,
        )
    except (OSError, RuntimeError):
        return ClaudeCapability(
            ClaudeCapabilityClassification.UNSUPPORTED_VERSION,
            version_text,
            str(resolved),
        )
    if not _required_flags_present(root_help, auth_help):
        return ClaudeCapability(
            ClaudeCapabilityClassification.UNSUPPORTED_VERSION,
            version_text,
            str(resolved),
        )

    try:
        auth = _run_probe(
            process_port,
            (str(resolved), "auth", "status", "--json"),
            environment,
            probe_timers,
        )
    except (OSError, RuntimeError):
        auth = None
    if auth is None or not _authenticated(auth):
        return ClaudeCapability(
            ClaudeCapabilityClassification.AUTHENTICATION_UNAVAILABLE,
            version_text,
            str(resolved),
        )
    return ClaudeCapability(
        ClaudeCapabilityClassification.CONFIGURED, version_text, str(resolved)
    )


def parse_claude_version(
    output: bytes,
) -> tuple[str, tuple[int, int, int]] | None:
    try:
        text = output.decode("ascii", errors="strict")
    except UnicodeDecodeError:
        return None
    match = _VERSION_PATTERN.fullmatch(text)
    if match is None:
        return None
    parts = tuple(int(value) for value in match.groups())
    return ".".join(str(value) for value in parts), parts


def _validator_schema(
    validator: OutputValidator, contract_version: str, schema_version: str
) -> str:
    schema_factory = getattr(validator, "json_schema", None)
    if not callable(schema_factory):
        raise TypeError("Provider validator omitted its canonical JSON Schema.")
    parsed = schema_factory()
    if not isinstance(parsed, Mapping):
        raise TypeError("Provider JSON Schema must be an object.")
    return json.dumps(
        versioned_output_schema(parsed, contract_version, schema_version),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _terminal_result(raw: bytes) -> Mapping[str, Any]:
    events = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        event = _strict_json(line)
        if not isinstance(event, Mapping) or not isinstance(event.get("type"), str):
            raise TypeError("Claude stream events must be objects.")
        events.append(event)
    terminal = [event for event in events if event.get("type") == "result"]
    if len(terminal) != 1:
        raise ValueError("Claude stream requires exactly one terminal result event.")
    if events[-1] is not terminal[0]:
        raise ValueError("Claude returned an event after its terminal result.")
    structured = terminal[0].get("structured_output")
    if terminal[0].get("is_error") is False and not isinstance(structured, Mapping):
        raise TypeError("Claude success result omitted structured output.")
    return terminal[0]


def _strict_json(value: str | bytes) -> Any:
    def reject_duplicates(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("Duplicate JSON object member.")
            result[key] = item
        return result

    return json.loads(value, object_pairs_hook=reject_duplicates)


def _process_failure(
    outcome: ProcessOutcome,
) -> ProviderFailureClassification | None:
    if outcome.cancelled:
        return ProviderFailureClassification.CANCELLED
    if outcome.timed_out is not None:
        return outcome.timed_out
    if outcome.exit_code not in (0, None):
        return ProviderFailureClassification.NONZERO_EXIT
    return None


def _run_probe(
    process_port: ProcessPort,
    argv: Iterable[str],
    environment: Mapping[str, str],
    timers: ProviderTimers,
) -> ProcessOutcome:
    return process_port.run(
        ProcessSpec(
            tuple(argv),
            None,
            environment,
            timers,
            stdout_limit_bytes=PROVIDER_PROBE_OUTPUT_LIMIT_BYTES,
            stderr_limit_bytes=PROVIDER_PROBE_OUTPUT_LIMIT_BYTES,
        ),
        on_spawn=lambda _pid, _pgid, _identity: None,
        cancelled=lambda: False,
    )


def _successful_probe(outcome: ProcessOutcome) -> bool:
    return (
        outcome.exit_code == 0
        and outcome.timed_out is None
        and not outcome.cancelled
        and len(outcome.stdout) <= _MAX_PROBE_OUTPUT_BYTES
        and len(outcome.stderr) <= _MAX_PROBE_OUTPUT_BYTES
    )


def _required_flags_present(
    root_help: ProcessOutcome, auth_help: ProcessOutcome
) -> bool:
    if not _successful_probe(root_help) or not _successful_probe(auth_help):
        return False
    try:
        root = root_help.stdout.decode("utf-8", errors="strict")
        auth = auth_help.stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return False
    return all(flag in root for flag in _ROOT_FLAGS) and "--json" in auth


def _authenticated(outcome: ProcessOutcome) -> bool:
    if not _successful_probe(outcome):
        return False
    try:
        value = _strict_json(outcome.stdout)
    except (json.JSONDecodeError, TypeError, ValueError):
        return False
    return isinstance(value, Mapping) and value.get("loggedIn") is True


def _proxy_has_credentials(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return parsed.username is not None or parsed.password is not None
    except ValueError:
        return True


def _executable_identity(executable: str) -> tuple[int, int, int, int, int] | None:
    try:
        status = Path(executable).stat()
    except OSError:
        return None
    return (
        status.st_dev,
        status.st_ino,
        status.st_mtime_ns,
        status.st_size,
        status.st_mode,
    )


def _failed_result(request, contract_version, classification):
    return ProviderResult(
        ProviderResultState.FAILED,
        ProviderName.CLAUDE,
        CLAUDE_MODEL,
        contract_version,
        request.output_schema_version,
        None,
        None,
        classification,
        retryable=True,
    )
