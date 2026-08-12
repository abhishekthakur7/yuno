from __future__ import annotations

import base64
import hashlib
import subprocess
import sys
import time

import pytest
from fastapi.testclient import TestClient

from yuno.api.app import create_app
from yuno.config import Settings
from yuno.modules.runner.adapters import LocalRunnerProcessPort
from yuno.modules.runner.domain import (
    OutputChunk,
    ProcessLimits,
    RunnerProcessOutcome,
)
from yuno.modules.runner.ports import RunnerProcessSpec
from yuno.modules.runner.service import ACKNOWLEDGEMENT_VERSION, minimal_environment


def _enabled(database_url: str) -> Settings:
    return Settings(
        database_url=database_url,
        runner_enabled=True,
        runner_environment_policy_version="env-test-v1",
        runner_limits_config_version="limits-test-v1",
        runner_confirmation_ttl_seconds=60,
        runner_wall_time_seconds=2,
        runner_cpu_seconds=1,
        runner_memory_bytes=256_000_000,
        runner_process_limit=8,
        runner_output_bytes=4096,
        runner_file_bytes=1_000_000,
        runner_temp_bytes=1_000_000,
        runner_javac_command="/usr/bin/true",
        runner_java_command="/usr/bin/true",
        runner_java_version_prefix="",
    )


def test_runner_is_fail_closed_by_default(client) -> None:
    payload = client.get("/api/v1/runner/capabilities").json()
    assert payload["enabled"] is False
    assert payload["capabilities"] == []
    assert "IDK-005" in payload["disabled_reason"]


def test_runner_confirmation_exact_inputs_phases_and_fresh_retry(
    migrated_database_url: str,
) -> None:
    with TestClient(create_app(_enabled(migrated_database_url))) as client:
        content = b"public class Main {}"
        confirmed = client.post(
            "/api/v1/runner/confirmations",
            json={
                "language": "java",
                "capability": "compile-and-test",
                "operation": "compile",
                "inputs": [
                    {
                        "logical_path": "Main.java",
                        "declared_type": "java-source",
                        "content_ref": "inline-base64:"
                        + base64.b64encode(content).decode(),
                        "content_hash": hashlib.sha256(content).hexdigest(),
                    }
                ],
                "acknowledgement_version": ACKNOWLEDGEMENT_VERSION,
            },
        )
        assert confirmed.status_code == 201
        assert "content_ref" not in confirmed.json()["inputs"][0]
        confirmation_id = confirmed.json()["id"]
        started = client.post(
            "/api/v1/runner-runs",
            headers={"Idempotency-Key": "run-one"},
            json={"confirmation_id": confirmation_id},
        )
        assert started.status_code == 202
        run_id = started.json()["job_id"]
        for _ in range(100):
            result = client.get(f"/api/v1/runner-runs/{run_id}").json()
            if result["cleanup_state"] != "cleanup-pending":
                break
            time.sleep(0.01)
        assert result["id"] == run_id
        assert [
            result[f"{name}_phase"]["label"] for name in ("compile", "test", "static")
        ] == ["compile", "test", "static"]
        assert result["cleanup_state"] == "cleanup-complete"
        assert "not a sandbox" in result["limitation"]
        reused = client.post(
            "/api/v1/runner-runs",
            headers={"Idempotency-Key": "run-two"},
            json={"confirmation_id": confirmation_id},
        )
        assert reused.status_code == 409


def test_runner_environment_excludes_host_secrets() -> None:
    assert minimal_environment(
        {
            "PATH": "/bin",
            "LANG": "C",
            "AWS_ACCESS_KEY_ID": "bad",
            "DATABASE_URL": "bad",
            "MY_SECRET": "bad",
        }
    ) == {"PATH": "/bin", "LANG": "C"}


def test_runner_rejects_path_traversal_and_hash_mismatch(
    migrated_database_url: str,
) -> None:
    with TestClient(create_app(_enabled(migrated_database_url))) as client:
        for logical_path, digest in (
            ("../Main.java", hashlib.sha256(b"x").hexdigest()),
            ("C:\\Main.java", hashlib.sha256(b"x").hexdigest()),
            ("Main.java", "0" * 64),
        ):
            response = client.post(
                "/api/v1/runner/confirmations",
                json={
                    "language": "java",
                    "capability": "compile",
                    "operation": "compile",
                    "inputs": [
                        {
                            "logical_path": logical_path,
                            "declared_type": "java-source",
                            "content_ref": "inline-base64:eA==",
                            "content_hash": digest,
                        }
                    ],
                    "acknowledgement_version": ACKNOWLEDGEMENT_VERSION,
                },
            )
            assert response.status_code == 422


class _FakeProcessPort:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.specs = []
        self.cancel_checks = []

    def run(self, spec, *, on_spawn, cancelled):
        self.specs.append(spec)
        self.cancel_checks.append(cancelled)
        return next(self.outcomes)


class _CleanupFails:
    def __init__(self, delegate):
        self.delegate = delegate

    def create(self):
        return self.delegate.create()

    def cleanup(self, _path):
        raise OSError("simulated cleanup failure")


def _confirm(client, *, operation="test"):
    content = b"public class Main { public static void main(String[] x) {} }"
    confirmation = client.post(
        "/api/v1/runner/confirmations",
        json={
            "language": "java",
            "capability": "compile-and-test",
            "operation": operation,
            "inputs": [
                {
                    "logical_path": "Main.java",
                    "declared_type": "java-source",
                    "content_ref": "inline-base64:"
                    + base64.b64encode(content).decode(),
                    "content_hash": hashlib.sha256(content).hexdigest(),
                }
            ],
            "acknowledgement_version": ACKNOWLEDGEMENT_VERSION,
        },
    )
    assert confirmation.status_code == 201
    return confirmation


def _confirm_and_start(client, *, operation="test", key="threat-run"):
    confirmation = _confirm(client, operation=operation)
    return client.post(
        "/api/v1/runner-runs",
        headers={"Idempotency-Key": key},
        json={"confirmation_id": confirmation.json()["id"]},
    )


def test_primary_runner_threat_model_with_fake_process_port(
    migrated_database_url: str,
) -> None:
    compile_outcome = RunnerProcessOutcome(
        1234,
        1234,
        0,
        None,
        False,
        False,
        (OutputChunk("compile", "stdout", 1, "compiled", False),),
        4,
    )
    test_outcome = RunnerProcessOutcome(
        1235,
        1235,
        0,
        None,
        False,
        False,
        (OutputChunk("test", "stdout", 1, "tested", False),),
        5,
    )
    fake = _FakeProcessPort((compile_outcome, test_outcome))
    app = create_app(_enabled(migrated_database_url))
    with TestClient(app) as client:
        app.state.runner_process_port = fake
        started = _confirm_and_start(client)
        assert started.status_code == 202
        run_id = started.json()["job_id"]
        for _ in range(100):
            result = client.get(f"/api/v1/runner-runs/{run_id}").json()
            if result["cleanup_state"] != "cleanup-pending":
                break
            time.sleep(0.01)
    assert [spec.phase for spec in fake.specs] == ["compile", "test"]
    assert fake.specs[0].argv == ("/usr/bin/true", "Main.java")
    assert fake.specs[1].argv == ("/usr/bin/true", "-cp", ".", "Main")
    assert all(
        not any(
            key.startswith("AWS_")
            or key
            in {
                "JAVA_TOOL_OPTIONS",
                "_JAVA_OPTIONS",
                "JDK_JAVA_OPTIONS",
                "HTTP_PROXY",
                "HTTPS_PROXY",
            }
            for key in spec.environment
        )
        for spec in fake.specs
    )
    assert [chunk["ordinal"] for chunk in result["output_chunks"]] == [1, 2]
    assert [chunk["phase"] for chunk in result["output_chunks"]] == ["compile", "test"]
    assert [chunk["sequence"] for chunk in result["output_chunks"]] == [1, 2]
    assert result["compile_phase"]["state"] == "completed"
    assert result["test_phase"]["state"] == "completed"
    assert result["static_phase"]["state"] == "not-run"


def test_limit_breach_is_structured_truncated_and_cleanup_complete(
    migrated_database_url: str,
) -> None:
    fake = _FakeProcessPort(
        (
            RunnerProcessOutcome(
                1234,
                1234,
                None,
                9,
                True,
                False,
                (OutputChunk("compile", "stdout", 1, "partial", True),),
                2000,
            ),
        )
    )
    app = create_app(_enabled(migrated_database_url))
    with TestClient(app) as client:
        app.state.runner_process_port = fake
        started = _confirm_and_start(client, operation="compile", key="limited")
        run_id = started.json()["job_id"]
        for _ in range(100):
            result = client.get(f"/api/v1/runner-runs/{run_id}").json()
            if result["cleanup_state"] != "cleanup-pending":
                break
            time.sleep(0.01)
    assert result["state"] == "timed-out-or-limited"
    assert result["compile_phase"]["state"] == "timed-out-or-limited"
    assert result["output_chunks"][0]["truncated"] is True
    assert result["cleanup_state"] == "cleanup-complete"


def test_compile_and_test_share_wall_cpu_and_output_budgets(
    migrated_database_url: str,
) -> None:
    fake = _FakeProcessPort(
        (
            RunnerProcessOutcome(
                1234,
                1234,
                0,
                None,
                False,
                False,
                (OutputChunk("compile", "stdout", 1, "c" * 3000, False),),
                1200,
                400,
            ),
            RunnerProcessOutcome(
                1235,
                1235,
                0,
                None,
                False,
                False,
                (OutputChunk("test", "stdout", 1, "t" * 2000, False),),
                900,
                700,
            ),
        )
    )
    app = create_app(_enabled(migrated_database_url))
    with TestClient(app) as client:
        app.state.runner_process_port = fake
        started = _confirm_and_start(client, key="shared-budgets")
        run_id = started.json()["job_id"]
        for _ in range(100):
            result = client.get(f"/api/v1/runner-runs/{run_id}").json()
            if result["cleanup_state"] != "cleanup-pending":
                break
            time.sleep(0.01)

    assert len(fake.specs) == 2
    assert fake.specs[1].limits.wall_seconds == pytest.approx(0.8)
    assert fake.specs[1].limits.cpu_seconds == pytest.approx(0.6)
    assert fake.specs[1].limits.output_bytes == 1096
    assert result["state"] == "timed-out-or-limited"
    assert result["compile_phase"]["state"] == "completed"
    assert result["test_phase"]["state"] == "timed-out-or-limited"
    assert sum(len(chunk["content"].encode()) for chunk in result["output_chunks"]) == 4096
    assert result["output_chunks"][-1]["truncated"] is True


def test_exact_output_limit_still_allows_a_silent_test_phase(
    migrated_database_url: str,
) -> None:
    fake = _FakeProcessPort(
        (
            RunnerProcessOutcome(
                1234,
                1234,
                0,
                None,
                False,
                False,
                (OutputChunk("compile", "stdout", 1, "c" * 4096, False),),
                10,
            ),
            RunnerProcessOutcome(1235, 1235, 0, None, False, False, (), 10),
        )
    )
    app = create_app(_enabled(migrated_database_url))
    with TestClient(app) as client:
        app.state.runner_process_port = fake
        started = _confirm_and_start(client, key="exact-output-budget")
        run_id = started.json()["job_id"]
        for _ in range(100):
            result = client.get(f"/api/v1/runner-runs/{run_id}").json()
            if result["cleanup_state"] != "cleanup-pending":
                break
            time.sleep(0.01)

    assert [spec.phase for spec in fake.specs] == ["compile", "test"]
    assert fake.specs[1].limits.output_bytes == 0
    assert result["state"] == "completed"
    assert result["test_phase"]["state"] == "completed"
    assert result["output_chunks"][0]["truncated"] is False


class _ManySmallFilesProcessPort(_FakeProcessPort):
    def run(self, spec, *, on_spawn, cancelled):
        for index in range(40):
            (spec.working_directory / f"generated-{index}.bin").write_bytes(b"x" * 30_000)
        return super().run(spec, on_spawn=on_spawn, cancelled=cancelled)


def test_aggregate_workspace_limit_catches_many_small_generated_files(
    migrated_database_url: str,
) -> None:
    fake = _ManySmallFilesProcessPort(
        (RunnerProcessOutcome(1234, 1234, 0, None, False, False, (), 10, 1),)
    )
    app = create_app(_enabled(migrated_database_url))
    with TestClient(app) as client:
        app.state.runner_process_port = fake
        started = _confirm_and_start(client, key="aggregate-temp-limit")
        run_id = started.json()["job_id"]
        for _ in range(100):
            result = client.get(f"/api/v1/runner-runs/{run_id}").json()
            if result["cleanup_state"] != "cleanup-pending":
                break
            time.sleep(0.01)

    assert [spec.phase for spec in fake.specs] == ["compile"]
    assert result["state"] == "timed-out-or-limited"
    assert result["compile_phase"]["state"] == "timed-out-or-limited"
    assert "aggregate temporary-storage limit" in result["output_chunks"][-1]["content"]
    assert result["output_chunks"][-1]["truncated"] is True


def test_capabilities_detect_missing_and_incompatible(
    migrated_database_url: str,
) -> None:
    missing = _enabled(migrated_database_url).model_copy(
        update={"runner_javac_command": "definitely-not-a-java-command"}
    )
    with TestClient(create_app(missing)) as client:
        assert (
            client.get("/api/v1/runner/capabilities").json()["capabilities"][0]["state"]
            == "missing"
        )
    incompatible = _enabled(migrated_database_url).model_copy(
        update={"runner_java_version_prefix": "approved-java-never-matches"}
    )
    with TestClient(create_app(incompatible)) as client:
        assert (
            client.get("/api/v1/runner/capabilities").json()["capabilities"][0]["state"]
            == "incompatible"
        )


def test_cancelled_outcome_records_cleanup_failure(migrated_database_url: str) -> None:
    fake = _FakeProcessPort(
        (RunnerProcessOutcome(1234, 1234, None, 15, False, True, (), 1),)
    )
    app = create_app(_enabled(migrated_database_url))
    with TestClient(app) as client:
        app.state.runner_process_port = fake
        app.state.runner_workspace_port = _CleanupFails(app.state.runner_workspace_port)
        started = _confirm_and_start(
            client, operation="compile", key="cancelled-cleanup"
        )
        run_id = started.json()["job_id"]
        for _ in range(100):
            result = client.get(f"/api/v1/runner-runs/{run_id}").json()
            if result["cleanup_state"] != "cleanup-pending":
                break
            time.sleep(0.01)
    assert result["state"] == "cancelled"
    assert result["cleanup_state"] == "cleanup-failed"
    assert "OSError" in result["cleanup_diagnostic"]
    assert callable(fake.cancel_checks[0])


def test_local_process_port_drains_fast_exit_output(tmp_path) -> None:
    outcome = LocalRunnerProcessPort().run(
        RunnerProcessSpec(
            ("/bin/echo", "fast-exit-output"),
            tmp_path,
            {"PATH": "/bin", "LANG": "C"},
            ProcessLimits(2, 1, 512_000_000, 16, 4096, 1_000_000, 1_000_000),
            "compile",
        ),
        on_spawn=lambda *_args: None,
        cancelled=lambda: False,
    )
    assert outcome.exit_code == 0
    assert "fast-exit-output" in "".join(chunk.content for chunk in outcome.chunks)


def test_local_process_cpu_usage_excludes_unrelated_children(tmp_path) -> None:
    unrelated = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import time; end = time.monotonic() + 0.15; "
                "exec('while time.monotonic() < end:\\n pass')"
            ),
        ]
    )
    try:
        outcome = LocalRunnerProcessPort().run(
            RunnerProcessSpec(
                ("/bin/sleep", "0.4"),
                tmp_path,
                {"PATH": "/bin", "LANG": "C"},
                ProcessLimits(2, 1, 512_000_000, 16, 4096, 1_000_000, 1_000_000),
                "compile",
            ),
            on_spawn=lambda *_args: None,
            cancelled=lambda: False,
        )
    finally:
        unrelated.wait(timeout=2)

    assert unrelated.returncode == 0
    assert outcome.exit_code == 0
    assert outcome.cpu_ms is not None
    assert outcome.cpu_ms < 50


class _CreateFails:
    def create(self):
        raise OSError("simulated workspace creation failure")

    def cleanup(self, _path):
        raise AssertionError("No workspace was created.")


def test_runner_failure_is_terminal_and_cleanup_resolved(
    migrated_database_url: str,
) -> None:
    app = create_app(_enabled(migrated_database_url))
    with TestClient(app) as client:
        app.state.runner_workspace_port = _CreateFails()
        started = _confirm_and_start(client, operation="compile", key="create-fails")
        assert started.status_code == 202
        run_id = started.json()["job_id"]
        for _ in range(100):
            result = client.get(f"/api/v1/runner-runs/{run_id}").json()
            if result["cleanup_state"] != "cleanup-pending":
                break
            time.sleep(0.01)
    assert result["state"] == "failed"
    assert result["cleanup_state"] == "cleanup-complete"
    assert result["compile_phase"]["state"] == "failed"


def test_runner_reservation_replays_after_enqueue_failure(
    migrated_database_url: str, monkeypatch
) -> None:
    app = create_app(_enabled(migrated_database_url))
    with TestClient(app) as client:
        confirmation = _confirm(client, operation="compile")
        body = {"confirmation_id": confirmation.json()["id"]}
        original_enqueue = app.state.dispatcher.enqueue

        def fail_enqueue(_request):
            raise RuntimeError("simulated runner enqueue failure")

        monkeypatch.setattr(app.state.dispatcher, "enqueue", fail_enqueue)
        with pytest.raises(RuntimeError, match="simulated runner enqueue failure"):
            client.post(
                "/api/v1/runner-runs",
                headers={"Idempotency-Key": "recover-runner"},
                json=body,
            )
        monkeypatch.setattr(app.state.dispatcher, "enqueue", original_enqueue)

        recovered = client.post(
            "/api/v1/runner-runs",
            headers={"Idempotency-Key": "recover-runner"},
            json=body,
        )
        assert recovered.status_code == 202, recovered.text
        run_id = recovered.json()["job_id"]
        for _ in range(100):
            result = client.get(f"/api/v1/runner-runs/{run_id}").json()
            if result["cleanup_state"] != "cleanup-pending":
                break
            time.sleep(0.01)
    assert result["cleanup_state"] == "cleanup-complete"
