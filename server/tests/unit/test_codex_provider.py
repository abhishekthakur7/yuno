from __future__ import annotations

import json
from pathlib import Path

import pytest

from yuno.modules.provider.codex import (
    CODEX_ADAPTER_VERSION,
    CODEX_CONTRACT_VERSION,
    CODEX_MAXIMUM_VERSION_EXCLUSIVE,
    CODEX_MINIMUM_VERSION,
    CODEX_MODEL,
    CodexCliVersion,
    CodexProviderAdapter,
    codex_environment,
    discover_codex,
    parse_codex_cli_version,
)
from yuno.modules.provider.domain import (
    ProcessOutcome,
    ProviderCapabilityState,
    ProviderFailureClassification,
    ProviderInput,
    ProviderResultState,
    ProviderTimers,
)


class FakeProcess:
    def __init__(self, *outcomes: ProcessOutcome) -> None:
        self.outcomes = list(outcomes)
        self.specs = []

    def run(self, spec, *, on_spawn, cancelled):
        self.specs.append(spec)
        outcome = self.outcomes.pop(0)
        on_spawn(outcome.pid, outcome.pgid, outcome.process_identity)
        return outcome


class MemoryStore:
    def __init__(self) -> None:
        self.values = []

    def put(self, value: bytes) -> str:
        self.values.append(value)
        return "secure-provider-output:fixture"


class AnswerValidator:
    def validate(self, value):
        if not isinstance(value, dict) or set(value) != {"answer"}:
            raise TypeError("answer is required")
        if not isinstance(value["answer"], str):
            raise TypeError("answer must be text")
        return value

    def json_schema(self):
        return {
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
            "additionalProperties": False,
        }


def outcome(
    stdout: bytes = b"", *, stderr: bytes = b"", exit_code: int = 0
) -> ProcessOutcome:
    return ProcessOutcome(7, 7, "7:start", stdout, stderr, exit_code, bool(stdout))


def request() -> ProviderInput:
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


def help_output() -> bytes:
    return b" ".join(
        flag.encode()
        for flag in (
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
    )


def root_help_output() -> bytes:
    return b"--ask-for-approval --config"


def executable(tmp_path: Path) -> str:
    path = tmp_path / "codex"
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o700)
    return str(path)


def envelope(payload, *, contract=CODEX_CONTRACT_VERSION, schema="evaluation-v1"):
    return json.dumps(
        {"contract_version": contract, "schema_version": schema, "payload": payload},
        separators=(",", ":"),
    )


def test_approved_codex_contract_is_pinned() -> None:
    assert CODEX_MINIMUM_VERSION == (0, 147, 0)
    assert CODEX_MAXIMUM_VERSION_EXCLUSIVE == (0, 148, 0)
    assert CODEX_MODEL == "gpt-5.6-terra"
    assert CODEX_ADAPTER_VERSION == "codex-cli-adapter-v1"
    assert CODEX_CONTRACT_VERSION == "codex-jsonl-agent-message-v1"


def test_version_parser_accepts_only_the_documented_cli_shape() -> None:
    assert parse_codex_cli_version(b"codex-cli 0.147.0\n") == CodexCliVersion(0, 147, 0)
    for invalid in (b"0.147.0", b"codex-cli 0.147", b"codex-cli 0.147.0-beta"):
        with pytest.raises(ValueError):
            parse_codex_cli_version(invalid)


@pytest.mark.parametrize(
    ("version", "state"),
    [
        ("0.146.999", ProviderCapabilityState.UNSUPPORTED_VERSION),
        ("0.147.0", ProviderCapabilityState.CONFIGURED),
        ("0.147.99", ProviderCapabilityState.CONFIGURED),
        ("0.148.0", ProviderCapabilityState.UNSUPPORTED_VERSION),
        ("1.0.0", ProviderCapabilityState.UNSUPPORTED_VERSION),
    ],
)
def test_discovery_range_flags_and_auth_are_fail_closed(version, state) -> None:
    process = FakeProcess(
        outcome(f"codex-cli {version}\n".encode()),
        outcome(root_help_output()),
        outcome(help_output()),
        outcome(b"secret-like authentication output"),
    )
    capability = discover_codex(
        "/approved/codex",
        process,
        timers=ProviderTimers(1, 2, 3),
        source_environment={"HOME": "/safe-home", "SECRET": "excluded"},
    )
    assert capability.state is state
    if state is ProviderCapabilityState.CONFIGURED:
        assert [spec.argv for spec in process.specs] == [
            ("/approved/codex", "--version"),
            ("/approved/codex", "--help"),
            ("/approved/codex", "exec", "--help"),
            ("/approved/codex", "login", "status"),
        ]
        assert capability.model == CODEX_MODEL
        assert all(spec.environment == {"HOME": "/safe-home"} for spec in process.specs)
    else:
        assert len(process.specs) == 1


def test_discovery_auth_failure_returns_only_fixed_classification() -> None:
    process = FakeProcess(
        outcome(b"codex-cli 0.147.0\n"),
        outcome(root_help_output()),
        outcome(help_output()),
        outcome(stderr=b"token=secret", exit_code=1),
    )
    capability = discover_codex(
        "/approved/codex",
        process,
        timers=ProviderTimers(1, 2, 3),
        source_environment={},
    )
    assert capability.state is ProviderCapabilityState.AUTHENTICATION_UNAVAILABLE
    assert "secret" not in (capability.reason or "")


def test_adapter_uses_exact_argv_stdin_schema_temp_and_minimized_env(tmp_path) -> None:
    events = b"\n".join(
        (
            b'{"type":"thread.started","thread_id":"thread"}',
            b'{"type":"turn.started"}',
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "type": "agent_message",
                        "text": envelope({"answer": "ok"}),
                    },
                },
                separators=(",", ":"),
            ).encode(),
            b'{"type":"turn.completed","usage":{}}',
        )
    )
    process = FakeProcess(outcome(events))
    approved_executable = executable(tmp_path)
    adapter = CodexProviderAdapter(
        executable=approved_executable,
        temp_root=tmp_path,
        timers=ProviderTimers(1, 2, 3),
        process_port=process,
        secure_output_store=MemoryStore(),
        verify_auth_before_invoke=False,
        source_environment={
            "HOME": "/safe-home",
            "HTTPS_PROXY": "https://proxy.invalid",
            "OPENAI_API_KEY": "excluded",
        },
    )
    spawned = []
    result = adapter.invoke(
        request(),
        AnswerValidator(),
        on_spawn=lambda *values: spawned.append(values),
        cancelled=lambda: False,
    )
    spec = process.specs[0]
    assert result.state is ProviderResultState.SUCCEEDED
    assert result.payload == {"answer": "ok"}
    schema_path = spec.argv[spec.argv.index("--output-schema") + 1]
    work_dir = spec.argv[spec.argv.index("--cd") + 1]
    assert spec.argv == (
        approved_executable,
        "--ask-for-approval",
        "never",
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--model",
        "gpt-5.6-terra",
        "--config",
        'model_reasoning_effort="high"',
        "--sandbox",
        "read-only",
        "--json",
        "--output-schema",
        schema_path,
        "--cd",
        work_dir,
        "--skip-git-repo-check",
        "--color",
        "never",
        "-",
    )
    assert spec.cwd == spawned[0][3]
    assert spec.json_event_heartbeat is True
    assert b"prompt body" in spec.stdin
    assert all("prompt body" not in value for value in spec.argv)
    assert spec.environment == {
        "HOME": "/safe-home",
        "HTTPS_PROXY": "https://proxy.invalid",
    }


@pytest.mark.parametrize(
    ("raw", "state", "classification"),
    [
        (
            b'{"type":"error","message":"provider unavailable"}\n',
            ProviderResultState.FAILED,
            ProviderFailureClassification.PROVIDER_REPORTED_FAILURE,
        ),
        (
            (
                b'{"type":"item.completed","item":{"type":"agent_message","text":"{\\"wrong\\":true}"}}\n'
                b'{"type":"turn.completed"}\n'
            ),
            ProviderResultState.QUARANTINED,
            ProviderFailureClassification.SCHEMA_INVALID,
        ),
        (
            (
                b'{"type":"item.completed","item":{"type":"agent_message","text":"{\\"answer\\":\\"a\\",\\"answer\\":\\"b\\"}"}}\n'
                b'{"type":"turn.completed"}\n'
            ),
            ProviderResultState.QUARANTINED,
            ProviderFailureClassification.SCHEMA_INVALID,
        ),
    ],
)
def test_error_invalid_and_duplicate_outputs_never_cross_port(
    tmp_path, raw, state, classification
) -> None:
    result = CodexProviderAdapter(
        executable=executable(tmp_path),
        temp_root=tmp_path,
        timers=ProviderTimers(1, 2, 3),
        process_port=FakeProcess(outcome(raw)),
        secure_output_store=MemoryStore(),
        verify_auth_before_invoke=False,
        source_environment={},
    ).invoke(
        request(), AnswerValidator(), on_spawn=lambda *_: None, cancelled=lambda: False
    )
    assert result.state is state
    assert result.failure_classification is classification
    assert result.payload is None


def test_environment_excludes_auth_keys_and_credentialed_proxy() -> None:
    with pytest.raises(ValueError, match="Credentialed proxy"):
        codex_environment(
            {
                "HOME": "/safe-home",
                "OPENAI_API_KEY": "secret",
                "CODEX_ACCESS_TOKEN": "secret",
                "HTTPS_PROXY": "https://user:password@proxy.example",
            }
        )
    assert codex_environment(
        {
            "HOME": "/safe-home",
            "OPENAI_API_KEY": "secret",
            "CODEX_ACCESS_TOKEN": "secret",
        }
    ) == {"HOME": "/safe-home"}


def test_adapter_rechecks_auth_before_request_delivery(tmp_path) -> None:
    process = FakeProcess(outcome(stderr=b"token=must-not-be-stored", exit_code=1))
    store = MemoryStore()
    result = CodexProviderAdapter(
        executable=executable(tmp_path),
        temp_root=tmp_path,
        timers=ProviderTimers(1, 2, 3),
        process_port=process,
        secure_output_store=store,
        source_environment={},
    ).invoke(
        request(), AnswerValidator(), on_spawn=lambda *_: None, cancelled=lambda: False
    )
    assert result.failure_classification is (
        ProviderFailureClassification.AUTHENTICATION_UNAVAILABLE
    )
    assert [spec.argv[1:] for spec in process.specs] == [("login", "status")]
    assert store.values == []
