from __future__ import annotations

import os
import subprocess
import sys
import time
from itertools import chain, repeat

import pytest

from yuno.modules.provider import adapters as provider_adapters
from yuno.modules.provider.adapters import (
    FileSecureOutputStore,
    LocalProcessPort,
    remove_unreferenced_provider_outputs,
)
from yuno.modules.provider.domain import (
    ProviderFailureClassification,
    ProviderTimers,
)
from yuno.modules.provider.ports import ProcessSpec


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


def test_local_process_requires_a_valid_json_event_for_first_output() -> None:
    outcome = LocalProcessPort().run(
        ProcessSpec(
            (
                sys.executable,
                "-c",
                (
                    "import sys,time; print('not-json', flush=True); "
                    "print('token=must-not-count', file=sys.stderr, flush=True); "
                    "time.sleep(1)"
                ),
            ),
            None,
            {},
            ProviderTimers(0.05, 1, 2),
            json_event_heartbeat=True,
        ),
        on_spawn=lambda *_: None,
        cancelled=lambda: False,
    )
    assert outcome.first_output_seen is False
    assert outcome.timed_out is ProviderFailureClassification.NO_FIRST_OUTPUT


def test_local_process_classifies_inactivity_after_first_valid_json_event() -> None:
    outcome = LocalProcessPort().run(
        ProcessSpec(
            (
                sys.executable,
                "-c",
                (
                    'import time; print(\'{"type":"turn.started"}\', flush=True); '
                    "time.sleep(1)"
                ),
            ),
            None,
            {},
            ProviderTimers(1, 0.05, 2),
            json_event_heartbeat=True,
        ),
        on_spawn=lambda *_: None,
        cancelled=lambda: False,
    )
    assert outcome.first_output_seen is True
    assert outcome.timed_out is ProviderFailureClassification.INACTIVITY_TIMEOUT


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_local_process_enforces_per_stream_output_limits(stream) -> None:
    program = (
        "import sys; sys.stdout.buffer.write(b'x'*4096); sys.stdout.flush()"
        if stream == "stdout"
        else "import sys; sys.stderr.buffer.write(b'x'*4096); sys.stderr.flush()"
    )
    outcome = LocalProcessPort().run(
        ProcessSpec(
            (sys.executable, "-c", program),
            None,
            {},
            ProviderTimers(1, 2, 3),
            stdout_limit_bytes=1024,
            stderr_limit_bytes=1024,
        ),
        on_spawn=lambda *_: None,
        cancelled=lambda: False,
    )
    assert outcome.timed_out is ProviderFailureClassification.OUTPUT_LIMIT
    assert len(getattr(outcome, stream)) == 1024


def test_secure_output_store_validates_existing_private_content(tmp_path) -> None:
    root = tmp_path / "quarantine"
    store = FileSecureOutputStore(root)
    reference = store.put(b"invalid provider payload")
    assert store.put(b"invalid provider payload") == reference
    path = root / reference.removeprefix("secure-provider-output:")
    path.chmod(0o644)
    with pytest.raises(RuntimeError, match="not a private file"):
        store.put(b"invalid provider payload")


def test_secure_output_store_rejects_symlink_root(tmp_path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="real directory"):
        FileSecureOutputStore(link)


def test_unreferenced_quarantine_cleanup_preserves_committed_private_files(
    tmp_path,
) -> None:
    store = FileSecureOutputStore(tmp_path / "quarantine")
    retained = store.put(b"retained invalid provider payload")
    orphaned = store.put(b"orphaned invalid provider payload")

    assert remove_unreferenced_provider_outputs(store.root, {retained}) == 1
    assert (store.root / retained.rsplit(":", 1)[1]).read_bytes() == (
        b"retained invalid provider payload"
    )
    assert not (store.root / orphaned.rsplit(":", 1)[1]).exists()
