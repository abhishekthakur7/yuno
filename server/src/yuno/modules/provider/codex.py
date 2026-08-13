"""Approved Codex CLI discovery and JSONL adapter."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from yuno.modules.provider.adapters import (
    PROVIDER_PROBE_OUTPUT_LIMIT_BYTES,
    PROVIDER_STDERR_LIMIT_BYTES,
    PROVIDER_STDOUT_LIMIT_BYTES,
    strict_json_loads,
    unwrap_versioned_output,
    versioned_output_schema,
)
from yuno.modules.provider.domain import (
    ProviderCapability,
    ProviderCapabilityState,
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
from yuno.modules.provider.registry import (
    authentication_capability,
    missing_capability,
    unsupported_capability,
)
from yuno.shared.domain.hashing import hash_payload

CODEX_MODEL = "gpt-5.6-terra"
CODEX_REASONING_EFFORT = "high"
CODEX_ADAPTER_VERSION = "codex-cli-adapter-v1"
CODEX_CONTRACT_VERSION = "codex-jsonl-agent-message-v1"
CODEX_MINIMUM_VERSION = (0, 147, 0)
CODEX_MAXIMUM_VERSION_EXCLUSIVE = (0, 148, 0)
CODEX_ENVIRONMENT_ALLOWLIST = (
    "HOME",
    "PATH",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "CODEX_HOME",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "CODEX_CA_CERTIFICATE",
)

_VERSION_PATTERN = re.compile(r"codex-cli (\d+)\.(\d+)\.(\d+)")
_REQUIRED_ROOT_FLAGS = ("--ask-for-approval", "--config")
_REQUIRED_EXEC_FLAGS = (
    "--ephemeral",
    "--ignore-user-config",
    "--ignore-rules",
    "--model",
    "--sandbox",
    "--json",
    "--output-schema",
    "--cd",
    "--skip-git-repo-check",
    "--color",
)


@dataclass(frozen=True, order=True)
class CodexCliVersion:
    major: int
    minor: int
    patch: int


def parse_codex_cli_version(output: bytes) -> CodexCliVersion:
    try:
        value = output.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise ValueError("Codex CLI version output is not ASCII.") from exc
    match = _VERSION_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError("Codex CLI version output has an unexpected shape.")
    return CodexCliVersion(*(int(part) for part in match.groups()))


def codex_environment(source: Mapping[str, str]) -> dict[str, str]:
    environment = {
        key: source[key] for key in CODEX_ENVIRONMENT_ALLOWLIST if key in source
    }
    for key, value in environment.items():
        if _credentialed_proxy(key, value):
            raise ValueError("Credentialed proxy URLs are not allowed.")
    return environment


def discover_codex(
    executable: str,
    process_port: ProcessPort,
    *,
    timers: ProviderTimers,
    source_environment: Mapping[str, str],
) -> ProviderCapability:
    try:
        environment = codex_environment(source_environment)
    except ValueError:
        return authentication_capability(ProviderName.CODEX)
    try:
        version_outcome = _probe(
            process_port, (executable, "--version"), environment, timers
        )
    except OSError:
        return missing_capability(ProviderName.CODEX)
    if not _probe_succeeded(version_outcome):
        return unsupported_capability(ProviderName.CODEX)
    try:
        version = parse_codex_cli_version(version_outcome.stdout)
    except ValueError:
        return unsupported_capability(ProviderName.CODEX)
    version_tuple = (version.major, version.minor, version.patch)
    if not (CODEX_MINIMUM_VERSION <= version_tuple < CODEX_MAXIMUM_VERSION_EXCLUSIVE):
        return unsupported_capability(ProviderName.CODEX)
    try:
        root_help_outcome = _probe(
            process_port, (executable, "--help"), environment, timers
        )
        help_outcome = _probe(
            process_port, (executable, "exec", "--help"), environment, timers
        )
    except OSError:
        return missing_capability(ProviderName.CODEX)
    if (
        not _probe_succeeded(root_help_outcome)
        or not _has_required_flags(root_help_outcome.stdout, _REQUIRED_ROOT_FLAGS)
        or not _probe_succeeded(help_outcome)
        or not _has_required_flags(help_outcome.stdout, _REQUIRED_EXEC_FLAGS)
    ):
        return unsupported_capability(ProviderName.CODEX)
    try:
        login_outcome = _probe(
            process_port,
            (executable, "login", "status"),
            environment,
            timers,
        )
    except OSError:
        return authentication_capability(ProviderName.CODEX)
    if not _probe_succeeded(login_outcome):
        return authentication_capability(ProviderName.CODEX)
    return ProviderCapability(
        ProviderName.CODEX,
        ProviderCapabilityState.CONFIGURED,
        model=CODEX_MODEL,
        adapter_version=CODEX_ADAPTER_VERSION,
        contract_version=CODEX_CONTRACT_VERSION,
    )


class CodexProviderAdapter:
    provider = ProviderName.CODEX.value
    model = CODEX_MODEL
    adapter_version = CODEX_ADAPTER_VERSION
    contract_version = CODEX_CONTRACT_VERSION

    def __init__(
        self,
        *,
        executable: str,
        temp_root: Path,
        timers: ProviderTimers,
        process_port: ProcessPort,
        secure_output_store: SecureOutputStore,
        source_environment: Mapping[str, str],
        verify_auth_before_invoke: bool = True,
    ) -> None:
        self.executable = executable
        self.temp_root = temp_root
        self.timers = timers
        self.process_port = process_port
        self.secure_output_store = secure_output_store
        self.environment = codex_environment(source_environment)
        self._executable_identity = _executable_identity(executable)
        self.verify_auth_before_invoke = verify_auth_before_invoke

    def invoke(self, request, validator: OutputValidator, *, on_spawn, cancelled):
        current_identity = _executable_identity(self.executable)
        if current_identity is None:
            return self._failed(
                request, None, ProviderFailureClassification.EXECUTABLE_MISSING
            )
        if current_identity != self._executable_identity:
            return self._failed(
                request, None, ProviderFailureClassification.UNSUPPORTED_VERSION
            )
        if self.verify_auth_before_invoke:
            try:
                auth = _probe(
                    self.process_port,
                    (self.executable, "login", "status"),
                    self.environment,
                    self.timers,
                )
            except OSError:
                auth = None
            if auth is None or not _probe_succeeded(auth):
                return self._failed(
                    request,
                    auth,
                    ProviderFailureClassification.AUTHENTICATION_UNAVAILABLE,
                )
        stdin = _request_stdin(request)
        with TemporaryDirectory(
            prefix="yuno-runner-provider-codex-", dir=self.temp_root
        ) as raw_temp:
            temp = Path(raw_temp)
            schema_path = temp / "output-schema.json"
            _write_schema(
                schema_path,
                versioned_output_schema(
                    validator.json_schema(),
                    self.contract_version,
                    request.output_schema_version,
                ),
            )
            argv = (
                self.executable,
                "--ask-for-approval",
                "never",
                "exec",
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
                "--model",
                CODEX_MODEL,
                "--config",
                f'model_reasoning_effort="{CODEX_REASONING_EFFORT}"',
                "--sandbox",
                "read-only",
                "--json",
                "--output-schema",
                str(schema_path),
                "--cd",
                str(temp),
                "--skip-git-repo-check",
                "--color",
                "never",
                "-",
            )
            outcome = self.process_port.run(
                ProcessSpec(
                    argv,
                    stdin,
                    self.environment,
                    self.timers,
                    cwd=str(temp),
                    json_event_heartbeat=True,
                    stdout_limit_bytes=PROVIDER_STDOUT_LIMIT_BYTES,
                    stderr_limit_bytes=PROVIDER_STDERR_LIMIT_BYTES,
                ),
                on_spawn=lambda pid, pgid, identity: on_spawn(
                    pid, pgid, identity, str(temp)
                ),
                cancelled=cancelled,
            )
        classification = _process_classification(outcome)
        if classification is not None:
            return self._failed(request, outcome, classification)
        try:
            final_message = _final_agent_message(outcome.stdout)
            envelope = strict_json_loads(final_message)
            payload = validator.validate(
                unwrap_versioned_output(
                    envelope, self.contract_version, request.output_schema_version
                )
            )
        except _CodexRunFailed:
            return self._failed(
                request,
                outcome,
                ProviderFailureClassification.PROVIDER_REPORTED_FAILURE,
            )
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            return self._quarantined(request, outcome.stdout, exc)
        return ProviderResult(
            ProviderResultState.SUCCEEDED,
            ProviderName.CODEX,
            self.model,
            self.contract_version,
            request.output_schema_version,
            payload,
            hash_payload(payload),
        )

    def _failed(self, request, outcome, classification):
        return ProviderResult(
            ProviderResultState.FAILED,
            ProviderName.CODEX,
            self.model,
            self.contract_version,
            request.output_schema_version,
            None,
            None,
            classification,
            retryable=classification is not ProviderFailureClassification.CANCELLED,
        )

    def _quarantined(self, request, raw: bytes, exc: Exception):
        secure_ref = self.secure_output_store.put(raw)
        return ProviderResult(
            ProviderResultState.QUARANTINED,
            ProviderName.CODEX,
            self.model,
            self.contract_version,
            request.output_schema_version,
            None,
            None,
            ProviderFailureClassification.SCHEMA_INVALID,
            retryable=True,
            quarantine=QuarantineDetails(
                secure_ref,
                hashlib.sha256(raw).hexdigest(),
                (f"schema:{type(exc).__name__}",),
            ),
        )


class _CodexRunFailed(ValueError):
    pass


def _final_agent_message(raw: bytes) -> str:
    final_message = None
    terminal_count = 0
    terminal_seen = False
    for line in raw.splitlines():
        if not line.strip():
            continue
        event = strict_json_loads(line)
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            raise TypeError("Codex JSONL event has an unexpected shape.")
        if terminal_seen:
            raise ValueError("Codex returned an event after turn completion.")
        if event["type"] in {"error", "turn.failed"}:
            raise _CodexRunFailed("Codex reported a failed run.")
        if event["type"] == "turn.completed":
            terminal_count += 1
            terminal_seen = True
        item = event.get("item")
        if (
            event["type"] == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == "agent_message"
            and isinstance(item.get("text"), str)
        ):
            if final_message is not None:
                raise ValueError("Codex returned duplicate final agent messages.")
            final_message = item["text"]
    if terminal_count != 1 or final_message is None:
        raise ValueError("Codex omitted a unique completed final agent message.")
    return final_message


def _request_stdin(request) -> bytes:
    return json.dumps(
        {
            "purpose": request.purpose,
            "context": request.context,
            "output_schema_version": request.output_schema_version,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _write_schema(path: Path, schema: Mapping[str, object]) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(schema, output, sort_keys=True, separators=(",", ":"))


def _probe(process_port, argv, environment, timers):
    return process_port.run(
        ProcessSpec(
            tuple(argv),
            None,
            environment,
            timers,
            stdout_limit_bytes=PROVIDER_PROBE_OUTPUT_LIMIT_BYTES,
            stderr_limit_bytes=PROVIDER_PROBE_OUTPUT_LIMIT_BYTES,
        ),
        on_spawn=lambda *_: None,
        cancelled=lambda: False,
    )


def _probe_succeeded(outcome) -> bool:
    return (
        outcome.exit_code == 0 and outcome.timed_out is None and not outcome.cancelled
    )


def _has_required_flags(raw: bytes, expected: tuple[str, ...]) -> bool:
    try:
        output = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return False
    return all(flag in output for flag in expected)


def _process_classification(outcome):
    if outcome.cancelled:
        return ProviderFailureClassification.CANCELLED
    if outcome.timed_out is not None:
        return outcome.timed_out
    if outcome.exit_code not in (0, None):
        return ProviderFailureClassification.NONZERO_EXIT
    return None


def _credentialed_proxy(key: str, value: str) -> bool:
    if key not in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}:
        return False
    parsed = urlsplit(value)
    return parsed.username is not None or parsed.password is not None


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
