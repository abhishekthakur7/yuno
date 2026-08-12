from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import replace
from itertools import chain, repeat

import pytest

from yuno.api.provider_runtime import MappingValidator
from yuno.modules.provider import adapters as provider_adapters
from yuno.modules.provider.adapters import CliProviderAdapter, LocalProcessPort
from yuno.modules.provider.domain import (
    ProcessOutcome,
    ProviderFailureClassification,
    ProviderInput,
    ProviderName,
    ProviderResultState,
    ProviderTimers,
)
from yuno.modules.provider.ports import ProcessSpec


class MemoryStore:
    def __init__(self) -> None:
        self.values = []

    def put(self, raw_output: bytes) -> str:
        self.values.append(raw_output)
        return "secure-provider-output:hash"


class FakeProcess:
    def __init__(self, outcome: ProcessOutcome) -> None:
        self.outcome = outcome
        self.spec = None
        self.cancelled = False

    def run(self, spec, *, on_spawn, cancelled):
        self.spec = spec
        self.cancelled = cancelled()
        on_spawn(self.outcome.pid, self.outcome.pgid, self.outcome.process_identity)
        return self.outcome


class ObjectValidator:
    def validate(self, value):
        if not isinstance(value, dict) or "answer" not in value:
            raise ValueError("answer is required")
        return value


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


def _adapter(outcome: ProcessOutcome):
    process = FakeProcess(outcome)
    store = MemoryStore()
    adapter = CliProviderAdapter(
        provider=ProviderName.CODEX,
        model="fixture-model",
        argv=("fixture-provider", "--non-interactive"),
        adapter_version="fixture-adapter-v1",
        contract_version="final-json-v1",
        allowed_environment=("ALLOWED",),
        timers=ProviderTimers(1, 2, 3),
        process_port=process,
        secure_output_store=store,
        source_environment={"ALLOWED": "yes", "SECRET": "never"},
    )
    return adapter, process, store


def _outcome(**changes) -> ProcessOutcome:
    return replace(
        ProcessOutcome(7, 7, "7:start", b'{"answer":"ok"}\n', b"", 0, True),
        **changes,
    )


def test_adapter_uses_argv_stdin_and_allowlisted_environment() -> None:
    adapter, process, _ = _adapter(_outcome())
    result = adapter.invoke(
        _request(), ObjectValidator(), on_spawn=lambda *_: None, cancelled=lambda: False
    )
    assert result.state is ProviderResultState.SUCCEEDED
    assert process.spec.argv == ("fixture-provider", "--non-interactive")
    assert process.spec.environment == {"ALLOWED": "yes"}
    assert b"prompt body" in process.spec.stdin
    assert all("prompt body" not in argument for argument in process.spec.argv)


@pytest.mark.parametrize(
    ("classification", "first_output"),
    [
        (ProviderFailureClassification.CONFIGURATION_OR_AUTHENTICATION, False),
        (ProviderFailureClassification.INACTIVITY_TIMEOUT, True),
        (ProviderFailureClassification.ABSOLUTE_TIMEOUT, True),
    ],
)
def test_three_timer_failures_remain_distinct(classification, first_output) -> None:
    adapter, _, store = _adapter(
        _outcome(
            timed_out=classification, first_output_seen=first_output, truncated=True
        )
    )
    result = adapter.invoke(
        _request(), ObjectValidator(), on_spawn=lambda *_: None, cancelled=lambda: False
    )
    assert result.failure_classification is classification
    assert result.retryable is True
    assert result.diagnostic_ref == "secure-provider-output:hash"
    assert store.values


def test_invalid_output_is_stored_but_never_crosses_port() -> None:
    adapter, _, store = _adapter(_outcome(stdout=b'{"wrong":true}\n'))
    result = adapter.invoke(
        _request(), ObjectValidator(), on_spawn=lambda *_: None, cancelled=lambda: False
    )
    assert result.state is ProviderResultState.QUARANTINED
    assert result.payload is None
    assert result.quarantine is not None
    assert result.quarantine.raw_output_ref == "secure-provider-output:hash"
    assert store.values == [b'{"wrong":true}\n']


def test_malformed_nested_evaluation_is_quarantined_inside_provider_port() -> None:
    raw = (
        b'{"state":"feedback-ready","dimensions":[{"dimension_id":"design",'
        b'"outcome":"pass","rationale":"ok","evidence_refs":"not-a-list"}],'
        b'"facts":[],"trade_offs":[],"citations":[],"ambiguities":[],'
        b'"feedback":"ok","warnings":[],"limitation_labels":[]}\n'
    )
    adapter, _, store = _adapter(_outcome(stdout=raw))
    result = adapter.invoke(
        _request(),
        MappingValidator("evaluation"),
        on_spawn=lambda *_: None,
        cancelled=lambda: False,
    )
    assert result.state is ProviderResultState.QUARANTINED
    assert result.payload is None
    assert store.values == [raw]


def test_evaluation_duplicate_dimensions_are_quarantined_inside_provider_port() -> None:
    raw = (
        b'{"state":"feedback-ready","dimensions":['
        b'{"dimension_id":"design","outcome":"pass","rationale":"ok","evidence_refs":[]},'
        b'{"dimension_id":"design","outcome":"pass","rationale":"ok","evidence_refs":[]}],'
        b'"facts":[],"trade_offs":[],"citations":[],"ambiguities":[],'
        b'"feedback":"ok","warnings":[],"limitation_labels":[]}\n'
    )
    adapter, _, store = _adapter(_outcome(stdout=raw))
    result = adapter.invoke(
        _request(),
        MappingValidator("evaluation", expected_dimension_ids=("design",)),
        on_spawn=lambda *_: None,
        cancelled=lambda: False,
    )
    assert result.state is ProviderResultState.QUARANTINED
    assert store.values == [raw]


def test_evaluation_wrong_expected_dimension_is_quarantined_inside_provider_port() -> (
    None
):
    raw = (
        b'{"state":"feedback-ready","dimensions":['
        b'{"dimension_id":"wrong","outcome":"pass","rationale":"ok","evidence_refs":[]}],'
        b'"facts":[],"trade_offs":[],"citations":[],"ambiguities":[],'
        b'"feedback":"ok","warnings":[],"limitation_labels":[]}\n'
    )
    adapter, _, store = _adapter(_outcome(stdout=raw))
    result = adapter.invoke(
        _request(),
        MappingValidator("evaluation", expected_dimension_ids=("design",)),
        on_spawn=lambda *_: None,
        cancelled=lambda: False,
    )
    assert result.state is ProviderResultState.QUARANTINED
    assert store.values == [raw]


def test_generation_accepts_json_provenance_pairs_and_typed_claims() -> None:
    raw = (
        b'{"body":"lesson","provenance_refs":[["source","snapshot"]],'
        b'"warnings":[],"claims":[{"claim_text":"Current fact",'
        b'"claim_type":"time-or-version-dependent","sensitive":false,'
        b'"citations":[{"source_id":"source","source_snapshot_id":"snapshot",'
        b'"locator":"p. 1","support_kind":"direct","note":null}]}]}\n'
    )
    adapter, _, store = _adapter(_outcome(stdout=raw))
    result = adapter.invoke(
        _request(),
        MappingValidator("topic-generation"),
        on_spawn=lambda *_: None,
        cancelled=lambda: False,
    )
    assert result.state is ProviderResultState.SUCCEEDED
    assert result.payload["provenance_refs"] == [["source", "snapshot"]]
    assert store.values == []


def test_generation_blank_duplicate_nested_values_are_quarantined() -> None:
    raw = (
        b'{"body":"lesson","provenance_refs":[["source","snapshot"],'
        b'["source","snapshot"]],"warnings":[],"claims":[]}\n'
    )
    adapter, _, store = _adapter(_outcome(stdout=raw))
    result = adapter.invoke(
        _request(),
        MappingValidator("topic-generation"),
        on_spawn=lambda *_: None,
        cancelled=lambda: False,
    )
    assert result.state is ProviderResultState.QUARANTINED
    assert store.values == [raw]


def test_malformed_tutor_payload_is_quarantined_inside_provider_port() -> None:
    raw = b'{"body":"   ","provenance_references":[],"warnings":[]}\n'
    adapter, _, store = _adapter(_outcome(stdout=raw))
    result = adapter.invoke(
        _request(),
        MappingValidator("tutor-turn"),
        on_spawn=lambda *_: None,
        cancelled=lambda: False,
    )
    assert result.state is ProviderResultState.QUARANTINED
    assert result.payload is None
    assert store.values == [raw]


def test_cancellation_is_non_retryable() -> None:
    adapter, _, _ = _adapter(_outcome(cancelled=True))
    result = adapter.invoke(
        _request(), ObjectValidator(), on_spawn=lambda *_: None, cancelled=lambda: True
    )
    assert result.failure_classification is ProviderFailureClassification.CANCELLED
    assert result.retryable is False


@pytest.mark.parametrize("trigger", ["cancel", "absolute-timeout"])
def test_local_process_cancel_and_timeout_terminate_the_spawned_process_group(
    monkeypatch,
    trigger,
) -> None:
    class FakePipe:
        pass

    class FakePopen:
        pid = 71
        stdin = None
        stdout = FakePipe()
        stderr = FakePipe()

        def __init__(self, argv, **kwargs) -> None:
            self.argv = argv
            self.kwargs = kwargs
            self.returncode = None

        def poll(self):
            return self.returncode

    class FakeSelector:
        def register(self, *_args) -> None:
            pass

        def get_map(self):
            return {}

        def select(self, timeout=0):
            return []

        def close(self) -> None:
            pass

    spawned = []
    terminated = []

    def fake_popen(argv, **kwargs):
        process = FakePopen(argv, **kwargs)
        spawned.append(process)
        return process

    def fake_terminate(process, pgid):
        terminated.append(pgid)
        process.returncode = -15

    monkeypatch.setattr(provider_adapters.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(provider_adapters.os, "getpgid", lambda _pid: 7100)
    monkeypatch.setattr(provider_adapters, "process_identity", lambda _pid: "71:start")
    monkeypatch.setattr(provider_adapters, "_terminate_group", fake_terminate)
    monkeypatch.setattr(provider_adapters.selectors, "DefaultSelector", FakeSelector)
    if trigger == "absolute-timeout":
        ticks = chain((0.0, 0.0), repeat(4.0))
        monkeypatch.setattr(provider_adapters.time, "monotonic", lambda: next(ticks))

    outcome = LocalProcessPort().run(
        ProcessSpec(
            ("provider-cli", "--non-interactive"), None, {}, ProviderTimers(1, 2, 3)
        ),
        on_spawn=lambda *_: None,
        cancelled=lambda: trigger == "cancel",
    )

    assert spawned[0].argv == ["provider-cli", "--non-interactive"]
    assert spawned[0].kwargs["shell"] is False
    assert spawned[0].kwargs["start_new_session"] is True
    assert terminated == [7100]
    assert outcome.pgid == 7100
    assert outcome.cancelled is (trigger == "cancel")
    if trigger == "absolute-timeout":
        assert outcome.timed_out is ProviderFailureClassification.ABSOLUTE_TIMEOUT


@pytest.mark.parametrize("trigger", ["cancel", "absolute-timeout"])
def test_local_process_kills_real_descendant_that_ignores_sigterm(trigger) -> None:
    program = """
import signal
import subprocess
import sys
import time

descendant = subprocess.Popen([
    sys.executable,
    "-c",
    "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)",
])
print(descendant.pid, flush=True)
time.sleep(60)
"""
    started = time.monotonic()
    outcome = LocalProcessPort().run(
        ProcessSpec(
            (sys.executable, "-c", program),
            None,
            {"PATH": os.environ.get("PATH", "")},
            ProviderTimers(1, 2, 0.25),
        ),
        on_spawn=lambda *_: None,
        cancelled=lambda: trigger == "cancel" and time.monotonic() - started > 0.1,
    )

    descendant_pid = int(outcome.stdout.splitlines()[0])
    deadline = time.monotonic() + 1
    status = ""
    while time.monotonic() < deadline:
        status = subprocess.run(
            ("ps", "-o", "stat=", "-p", str(descendant_pid)),
            check=False,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if not status or status.startswith("Z"):
            break
        time.sleep(0.02)
    assert not status or status.startswith("Z")
    if trigger == "cancel":
        assert outcome.cancelled is True
    else:
        assert outcome.timed_out is ProviderFailureClassification.ABSOLUTE_TIMEOUT


def test_local_process_bounded_drain_reads_more_than_one_chunk() -> None:
    expected = b"x" * 100_000
    outcome = LocalProcessPort().run(
        ProcessSpec(
            (sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'x'*100000)"),
            None,
            {"PATH": os.environ.get("PATH", "")},
            ProviderTimers(1, 2, 3),
        ),
        on_spawn=lambda *_: None,
        cancelled=lambda: False,
    )
    assert outcome.stdout == expected
