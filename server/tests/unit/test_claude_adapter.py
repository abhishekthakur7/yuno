from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from typing import ClassVar

import pytest

from yuno.modules.provider.claude import (
    CLAUDE_ADAPTER_VERSION,
    CLAUDE_CONTRACT_VERSION,
    CLAUDE_MAXIMUM_VERSION_EXCLUSIVE,
    CLAUDE_MINIMUM_VERSION,
    CLAUDE_MODEL,
    CLAUDE_TIMERS,
    ClaudeCapabilityClassification,
    ClaudeCliAdapter,
    claude_argv,
    claude_environment,
    discover_claude,
    parse_claude_version,
    resolve_claude_executable,
)
from yuno.modules.provider.domain import (
    ProcessOutcome,
    ProviderFailureClassification,
    ProviderInput,
    ProviderName,
    ProviderResultState,
    ProviderTimers,
)


class MemoryStore:
    def __init__(self) -> None:
        self.values: list[bytes] = []

    def put(self, raw_output: bytes) -> str:
        self.values.append(raw_output)
        return "secure-provider-output:hash"


class QueueProcess:
    def __init__(self, *outcomes: ProcessOutcome) -> None:
        self.outcomes = list(outcomes)
        self.specs = []

    def run(self, spec, *, on_spawn, cancelled):
        self.specs.append(spec)
        outcome = self.outcomes.pop(0)
        on_spawn(outcome.pid, outcome.pgid, outcome.process_identity)
        assert cancelled() is False
        return outcome


class RequiredAnswerValidator:
    schema: ClassVar = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    }

    def json_schema(self):
        return self.schema

    def validate(self, value):
        if not isinstance(value, dict) or set(value) != {"answer"}:
            raise TypeError("answer is required")
        if not isinstance(value["answer"], str):
            raise TypeError("answer must be text")
        return value


def _outcome(
    stdout: bytes = b"",
    *,
    stderr: bytes = b"",
    exit_code: int = 0,
) -> ProcessOutcome:
    return ProcessOutcome(7, 7, "7:start", stdout, stderr, exit_code, bool(stdout))


def _request() -> ProviderInput:
    return ProviderInput(
        owner_id="owner",
        goal_id=None,
        job_id="job",
        purpose="evaluation",
        context={"private": "prompt body"},
        context_ref_hash="context-hash",
        disclosure_id="disclosure",
        output_schema_version="evaluation-v1",
    )


def _envelope(
    payload,
    *,
    contract_version: str = CLAUDE_CONTRACT_VERSION,
    schema_version: str = "evaluation-v1",
):
    return {
        "contract_version": contract_version,
        "schema_version": schema_version,
        "payload": payload,
    }


def _executable(tmp_path: Path) -> str:
    path = tmp_path / "claude"
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o700)
    return str(path)


def _root_help() -> bytes:
    return b"\n".join(
        (
            b"-p, --print",
            b"--input-format",
            b"--output-format",
            b"--verbose",
            b"--json-schema",
            b"--model",
            b"--tools",
            b"--strict-mcp-config",
            b"--no-session-persistence",
            b"--permission-mode",
            b"--safe-mode",
        )
    )


def test_approved_constants_are_pinned() -> None:
    assert CLAUDE_MINIMUM_VERSION == (2, 1, 220)
    assert CLAUDE_MAXIMUM_VERSION_EXCLUSIVE == (2, 2, 0)
    assert CLAUDE_MODEL == "claude-sonnet-4-6"
    assert CLAUDE_ADAPTER_VERSION == "claude-code-adapter-v1"
    assert CLAUDE_CONTRACT_VERSION == "claude-stream-json-structured-output-v1"
    assert CLAUDE_TIMERS == ProviderTimers(20, 180, 1_200)


def test_claude_adapter_uses_exact_argv_stdin_and_minimal_environment(
    tmp_path,
) -> None:
    schema = RequiredAnswerValidator.schema
    events = [
        {"type": "system", "subtype": "init"},
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "structured_output": _envelope({"answer": "ok"}),
        },
    ]
    raw = b"\n".join(json.dumps(event).encode() for event in events) + b"\n"
    process = QueueProcess(_outcome(raw))
    executable = _executable(tmp_path)
    adapter = ClaudeCliAdapter(
        executable=executable,
        process_port=process,
        secure_output_store=MemoryStore(),
        source_environment={
            "HOME": "/safe-home",
            "PATH": "/approved-path",
            "HTTPS_PROXY": "https://proxy.example",
            "ANTHROPIC_API_KEY": "not-forwarded",
            "SECRET": "not-forwarded",
        },
        temp_root=tmp_path,
        verify_auth_before_invoke=False,
    )

    result = adapter.invoke(
        _request(),
        RequiredAnswerValidator(),
        on_spawn=lambda *_args: None,
        cancelled=lambda: False,
    )

    expected_schema = json.dumps(
        {
            "type": "object",
            "properties": {
                "contract_version": {
                    "const": CLAUDE_CONTRACT_VERSION,
                    "type": "string",
                },
                "schema_version": {"const": "evaluation-v1", "type": "string"},
                "payload": schema,
            },
            "required": ["contract_version", "schema_version", "payload"],
            "additionalProperties": False,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    assert result.state is ProviderResultState.SUCCEEDED
    assert result.provider is ProviderName.CLAUDE
    assert result.model == CLAUDE_MODEL
    assert result.payload == {"answer": "ok"}
    assert process.specs[0].argv == claude_argv(
        str(Path(executable).resolve()), expected_schema
    )
    assert process.specs[0].stdin is not None
    assert b"prompt body" in process.specs[0].stdin
    assert all("prompt body" not in value for value in process.specs[0].argv)
    assert process.specs[0].environment == {
        "HOME": "/safe-home",
        "PATH": "/approved-path",
        "HTTPS_PROXY": "https://proxy.example",
    }
    assert process.specs[0].cwd is not None
    assert process.specs[0].cwd.startswith(str(tmp_path))
    assert process.specs[0].timers == CLAUDE_TIMERS


@pytest.mark.parametrize(
    "raw",
    [
        b'{"type":"result","is_error":false,"structured_output":{"contract_version":"claude-stream-json-structured-output-v1","schema_version":"evaluation-v1","payload":{"answer":"a","answer":"b"}}}\n',
        b'{"type":"result","is_error":false,"structured_output":{}}\n',
        b'{"type":"result","is_error":false,"structured_output":{"contract_version":"wrong","schema_version":"evaluation-v1","payload":{"answer":"ok"}}}\n',
        b'{"type":"result","is_error":false,"structured_output":{"contract_version":"claude-stream-json-structured-output-v1","schema_version":"wrong","payload":{"answer":"ok"}}}\n',
        b'{"type":"result","is_error":false,"structured_output":{"contract_version":"claude-stream-json-structured-output-v1","schema_version":"evaluation-v1","payload":{"answer":7}}}\n',
        b'{}\n{"type":"result","is_error":false,"structured_output":{"contract_version":"claude-stream-json-structured-output-v1","schema_version":"evaluation-v1","payload":{"answer":"ok"}}}\n',
        b'{"type":"result","is_error":false,"structured_output":{"contract_version":"claude-stream-json-structured-output-v1","schema_version":"evaluation-v1","payload":{"answer":"ok"}}}\nnot-json\n',
        (
            b'{"type":"result","is_error":false,"structured_output":{"answer":"a"}}\n'
            b'{"type":"result","is_error":false,"structured_output":{"answer":"b"}}\n'
        ),
    ],
)
def test_malformed_duplicate_or_domain_invalid_stream_is_quarantined(
    tmp_path, raw
) -> None:
    process = QueueProcess(_outcome(raw))
    store = MemoryStore()
    adapter = ClaudeCliAdapter(
        executable=_executable(tmp_path),
        process_port=process,
        secure_output_store=store,
        source_environment={},
        verify_auth_before_invoke=False,
    )
    result = adapter.invoke(
        _request(),
        RequiredAnswerValidator(),
        on_spawn=lambda *_args: None,
        cancelled=lambda: False,
    )
    assert result.state is ProviderResultState.QUARANTINED
    assert result.payload is None
    assert store.values == [raw]


def test_provider_error_event_is_retryable_failure_not_quarantine(tmp_path) -> None:
    raw = b'{"type":"result","subtype":"error","is_error":true}\n'
    store = MemoryStore()
    adapter = ClaudeCliAdapter(
        executable=_executable(tmp_path),
        process_port=QueueProcess(_outcome(raw)),
        secure_output_store=store,
        source_environment={},
        verify_auth_before_invoke=False,
    )
    result = adapter.invoke(
        _request(),
        RequiredAnswerValidator(),
        on_spawn=lambda *_args: None,
        cancelled=lambda: False,
    )
    assert result.state is ProviderResultState.FAILED
    assert result.failure_classification is (
        ProviderFailureClassification.PROVIDER_REPORTED_FAILURE
    )
    assert result.quarantine is None
    assert store.values == []


@pytest.mark.parametrize(
    ("outcome", "classification", "retryable"),
    [
        (
            replace(
                _outcome(),
                timed_out=ProviderFailureClassification.NO_FIRST_OUTPUT,
            ),
            ProviderFailureClassification.NO_FIRST_OUTPUT,
            True,
        ),
        (
            replace(
                _outcome(b'{"type":"system"}\n'),
                timed_out=ProviderFailureClassification.INACTIVITY_TIMEOUT,
                truncated=True,
            ),
            ProviderFailureClassification.INACTIVITY_TIMEOUT,
            True,
        ),
        (
            replace(
                _outcome(),
                timed_out=ProviderFailureClassification.ABSOLUTE_TIMEOUT,
            ),
            ProviderFailureClassification.ABSOLUTE_TIMEOUT,
            True,
        ),
        (
            replace(_outcome(), cancelled=True),
            ProviderFailureClassification.CANCELLED,
            False,
        ),
        (
            _outcome(stderr=b"safe diagnostic", exit_code=2),
            ProviderFailureClassification.NONZERO_EXIT,
            True,
        ),
    ],
)
def test_process_outcomes_keep_distinct_safe_classifications(
    tmp_path, outcome, classification, retryable
) -> None:
    adapter = ClaudeCliAdapter(
        executable=_executable(tmp_path),
        process_port=QueueProcess(outcome),
        secure_output_store=MemoryStore(),
        source_environment={},
        verify_auth_before_invoke=False,
    )
    result = adapter.invoke(
        _request(),
        RequiredAnswerValidator(),
        on_spawn=lambda *_args: None,
        cancelled=lambda: False,
    )
    assert result.state is ProviderResultState.FAILED
    assert result.failure_classification is classification
    assert result.retryable is retryable
    assert result.quarantine is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b"2.1.220 (Claude Code)\n", ("2.1.220", (2, 1, 220))),
        (b"2.1.221 (Claude Code)\n", ("2.1.221", (2, 1, 221))),
        (b"2.1.220", None),
        (b"2.1.220-beta.1 (Claude Code)\n", None),
        (b"v2.1.220 (Claude Code)\n", None),
        (b"2.1.220 extra (Claude Code)\n", None),
        (b"2.1\n", None),
        (b"\xff", None),
    ],
)
def test_parse_claude_version_is_strict_ascii(raw, expected) -> None:
    assert parse_claude_version(raw) == expected


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("2.1.219", ClaudeCapabilityClassification.UNSUPPORTED_VERSION),
        ("2.1.220", ClaudeCapabilityClassification.CONFIGURED),
        ("2.1.221", ClaudeCapabilityClassification.CONFIGURED),
        ("2.1.999", ClaudeCapabilityClassification.CONFIGURED),
        ("2.2.0", ClaudeCapabilityClassification.UNSUPPORTED_VERSION),
        ("3.0.0", ClaudeCapabilityClassification.UNSUPPORTED_VERSION),
    ],
)
def test_discovery_enforces_range_flags_and_bounded_auth_json(
    tmp_path, version, expected
) -> None:
    executable = _executable(tmp_path)
    process = QueueProcess(
        _outcome(f"{version} (Claude Code)\n".encode()),
        _outcome(_root_help()),
        _outcome(b"--json\n"),
        _outcome(b'{"loggedIn":true,"email":"discarded"}\n'),
    )
    result = discover_claude(
        executable,
        process_port=process,
        probe_timers=ProviderTimers(1, 2, 3),
        source_environment={"HOME": "/safe-home", "SECRET": "not-forwarded"},
    )
    assert result.classification is expected
    assert process.specs[0].argv == (str(Path(executable).resolve()), "--version")
    if expected is ClaudeCapabilityClassification.CONFIGURED:
        assert [spec.argv[1:] for spec in process.specs] == [
            ("--version",),
            ("--help",),
            ("auth", "status", "--help"),
            ("auth", "status", "--json"),
        ]
        assert all(spec.stdin is None for spec in process.specs)
        assert all("SECRET" not in spec.environment for spec in process.specs)
    else:
        assert len(process.specs) == 1


def test_discovery_fails_closed_for_missing_flag_and_auth_shapes(tmp_path) -> None:
    executable = _executable(tmp_path)
    missing_flag = discover_claude(
        executable,
        process_port=QueueProcess(
            _outcome(b"2.1.220 (Claude Code)\n"),
            _outcome(b"--safe-mode\n"),
            _outcome(b"--json\n"),
        ),
        probe_timers=ProviderTimers(1, 2, 3),
        source_environment={},
    )
    auth_false = discover_claude(
        executable,
        process_port=QueueProcess(
            _outcome(b"2.1.220 (Claude Code)\n"),
            _outcome(_root_help()),
            _outcome(b"--json\n"),
            _outcome(b'{"loggedIn":false}\n', exit_code=1),
        ),
        probe_timers=ProviderTimers(1, 2, 3),
        source_environment={},
    )
    auth_duplicate = discover_claude(
        executable,
        process_port=QueueProcess(
            _outcome(b"2.1.220 (Claude Code)\n"),
            _outcome(_root_help()),
            _outcome(b"--json\n"),
            _outcome(b'{"loggedIn":true,"loggedIn":false}\n'),
        ),
        probe_timers=ProviderTimers(1, 2, 3),
        source_environment={},
    )
    assert missing_flag.classification is (
        ClaudeCapabilityClassification.UNSUPPORTED_VERSION
    )
    assert auth_false.classification is (
        ClaudeCapabilityClassification.AUTHENTICATION_UNAVAILABLE
    )
    assert auth_duplicate.classification is (
        ClaudeCapabilityClassification.AUTHENTICATION_UNAVAILABLE
    )


def test_executable_and_environment_policy_fail_closed(tmp_path) -> None:
    relative = "claude"
    unsafe = tmp_path / "unsafe-claude"
    unsafe.write_text("#!/bin/sh\n", encoding="utf-8")
    unsafe.chmod(0o722)

    with pytest.raises(FileNotFoundError):
        resolve_claude_executable(relative)
    with pytest.raises(FileNotFoundError):
        resolve_claude_executable(str(unsafe))
    with pytest.raises(ValueError, match="Credentialed proxy"):
        claude_environment({"HTTPS_PROXY": "https://user:secret@proxy.example"})

    environment = claude_environment(
        {
            "HOME": "/safe-home",
            "PATH": "/approved-path",
            "ANTHROPIC_API_KEY": "prohibited",
            "ANTHROPIC_AUTH_TOKEN": "prohibited",
            "AWS_SECRET_ACCESS_KEY": "prohibited",
        }
    )
    assert environment == {"HOME": "/safe-home", "PATH": "/approved-path"}


def test_adapter_rechecks_auth_before_request_delivery(tmp_path) -> None:
    process = QueueProcess(
        _outcome(b'{"loggedIn":false}\n', stderr=b"secret-like", exit_code=1)
    )
    store = MemoryStore()
    result = ClaudeCliAdapter(
        executable=_executable(tmp_path),
        process_port=process,
        secure_output_store=store,
        source_environment={},
    ).invoke(
        _request(),
        RequiredAnswerValidator(),
        on_spawn=lambda *_: None,
        cancelled=lambda: False,
    )
    assert result.failure_classification is (
        ProviderFailureClassification.AUTHENTICATION_UNAVAILABLE
    )
    assert [spec.argv[1:] for spec in process.specs] == [("auth", "status", "--json")]
    assert store.values == []
    assert os.path.isabs(_executable(tmp_path))
