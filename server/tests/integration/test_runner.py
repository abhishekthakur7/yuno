from __future__ import annotations

import base64
import hashlib
import signal
import subprocess
import sys
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect, text

from tests.conftest import build_isolated_settings
from yuno.api.app import create_app
from yuno.config import Settings
from yuno.modules.runner.adapters import LocalRunnerProcessPort, detect_command
from yuno.modules.runner.domain import (
    DeclaredInput,
    OutputChunk,
    ProcessLimits,
    RunnerProcessOutcome,
)
from yuno.modules.runner.platform_probe import (
    PLATFORM_UNVERIFIABLE,
    UNSUPPORTED_PLATFORM,
    PlatformSnapshot,
    evaluate_platform,
)
from yuno.modules.runner.ports import RunnerProcessSpec
from yuno.modules.runner.service import (
    ACKNOWLEDGEMENT_VERSION,
    minimal_environment,
    resolve_inputs_within_limits,
)
from yuno.shared.domain.errors import RunnerInputLimitError

# The exact IDK-005 section 1 approved row: Ubuntu 24.04 LTS on x86_64/arm64,
# no WSL/container marker. Tests that exercise execution behavior (limits,
# cleanup, cancellation, ...) fake this platform so they pass regardless of
# the actual host OS, mirroring how `app.state.runner_process_port` is
# overridden below instead of running real subprocess execution end to end.
_APPROVED_PLATFORM_SNAPSHOT = PlatformSnapshot(
    system_name="Linux",
    machine="x86_64",
    os_release={"ID": "ubuntu", "VERSION_ID": "24.04"},
)


def _enabled(database_url: str, tmp_path) -> Settings:
    return build_isolated_settings(tmp_path, database_url=database_url).model_copy(
        update={
            "runner_enabled": True,
            "runner_environment_policy_version": "env-test-v1",
            "runner_limits_config_version": "limits-test-v1",
            "runner_confirmation_ttl_seconds": 60,
            "runner_wall_time_seconds": 2,
            "runner_cpu_seconds": 1,
            "runner_memory_bytes": 256_000_000,
            "runner_process_limit": 8,
            "runner_stdout_bytes_limit": 4096,
            "runner_stderr_bytes_limit": 4096,
            "runner_output_bytes": 4096,
            "runner_file_bytes": 1_000_000,
            "runner_temp_bytes": 1_000_000,
            "runner_temp_files_limit": 100,
            "runner_javac_command": "/usr/bin/true",
            "runner_java_command": "/usr/bin/true",
            "runner_java_version_prefix": "",
        }
    )


def _enabled_app(database_url: str, tmp_path, **overrides):
    settings = _enabled(database_url, tmp_path)
    if overrides:
        settings = settings.model_copy(update=overrides)
    app = create_app(settings)
    app.state.runner_platform_probe = lambda: _APPROVED_PLATFORM_SNAPSHOT
    return app


def test_runner_is_fail_closed_by_default(client) -> None:
    payload = client.get("/api/v1/runner/capabilities").json()
    assert payload["enabled"] is False
    assert payload["capabilities"] == []
    assert "IDK-005" in payload["disabled_reason"]


def test_runner_confirmation_exact_inputs_phases_and_fresh_retry(
    migrated_database_url: str, tmp_path
) -> None:
    with TestClient(_enabled_app(migrated_database_url, tmp_path)) as client:
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


def test_runner_sensitive_content_exists_only_in_removable_body_tables(
    migrated_database_url: str,
) -> None:
    engine = create_engine(migrated_database_url)
    try:
        inspector = inspect(engine)
        assert "content_ref" not in {
            column["name"]
            for column in inspector.get_columns("runner_confirmation_inputs")
        }
        assert "resolved_content" not in {
            column["name"]
            for column in inspector.get_columns("runner_confirmation_inputs")
        }
        assert "content_ref" not in {
            column["name"] for column in inspector.get_columns("runner_inputs")
        }
        assert "content_ref" not in {
            column["name"] for column in inspector.get_columns("runner_output_chunks")
        }
        record_columns = {
            column["name"] for column in inspector.get_columns("runner_records")
        }
        assert {
            "argv_json",
            "pid",
            "pgid",
            "temp_path",
            "outcome_json",
            "cleanup_diagnostic",
        }.isdisjoint(record_columns)
        assert {
            "argv_hash",
            "outcome_hash",
            "temp_path_hash",
            "cleanup_classification",
        } <= record_columns
    finally:
        engine.dispose()


def test_missing_confirmation_body_rejects_run_without_partial_reservation(
    migrated_database_url: str, tmp_path
) -> None:
    app = _enabled_app(migrated_database_url, tmp_path)
    with TestClient(app) as client:
        confirmation = _confirm(client, operation="compile")
        confirmation_id = confirmation.json()["id"]
        with app.state.session_factory() as session:
            session.execute(
                text(
                    "DELETE FROM runner_confirmation_input_bodies "
                    "WHERE input_id IN (SELECT id FROM runner_confirmation_inputs "
                    "WHERE confirmation_id=:confirmation_id)"
                ),
                {"confirmation_id": confirmation_id},
            )
            session.commit()

        rejected = client.post(
            "/api/v1/runner-runs",
            headers={"Idempotency-Key": "missing-confirmation-body"},
            json={"confirmation_id": confirmation_id},
        )
        assert rejected.status_code == 409
        with app.state.session_factory() as session:
            confirmation_row = session.execute(
                text(
                    "SELECT consumed_at,reserved_run_id FROM runner_confirmations "
                    "WHERE id=:confirmation_id"
                ),
                {"confirmation_id": confirmation_id},
            ).one()
            assert tuple(confirmation_row) == (None, None)
            assert session.scalar(text("SELECT count(*) FROM runner_records")) == 0


def test_expired_output_body_is_unavailable_while_hash_metadata_survives(
    migrated_database_url: str, tmp_path
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
                (OutputChunk("compile", "stdout", 1, "private output", False),),
                1,
            ),
        )
    )
    app = _enabled_app(migrated_database_url, tmp_path)
    with TestClient(app) as client:
        app.state.runner_process_port = fake
        started = _confirm_and_start(
            client, operation="compile", key="expire-output-body"
        )
        run_id = started.json()["job_id"]
        for _ in range(100):
            result = client.get(f"/api/v1/runner-runs/{run_id}").json()
            if result["cleanup_state"] != "cleanup-pending":
                break
            time.sleep(0.01)
        assert result["output_chunks"][0]["content"] == "private output"

        with app.state.session_factory() as session:
            header = session.execute(
                text(
                    "SELECT id,content_hash FROM runner_output_chunks "
                    "WHERE runner_id=:run_id"
                ),
                {"run_id": run_id},
            ).one()
            session.execute(
                text("DELETE FROM runner_output_chunk_bodies WHERE chunk_id=:chunk_id"),
                {"chunk_id": header.id},
            )
            session.commit()

        expired = client.get(f"/api/v1/runner-runs/{run_id}").json()
        assert expired["output_chunks"] == [
            {
                "phase": "compile",
                "stream": "stdout",
                "sequence": 1,
                "ordinal": 1,
                "content": None,
                "availability": "unavailable",
                "reason": "policy-excluded",
                "truncated": False,
            }
        ]
        assert header.content_hash == hashlib.sha256(b"private output").hexdigest()


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
    migrated_database_url: str, tmp_path
) -> None:
    with TestClient(_enabled_app(migrated_database_url, tmp_path)) as client:
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


def test_retired_relational_language_rejected_before_route_or_uow(client) -> None:
    """IDK-008 (`docs/decisions/IDK-008-database-exercise-posture.md:34,65`)
    requires that a `POST /runner/confirmations` body carrying the retired
    `"language":"relational"` value returns the standard `422` validation
    envelope *before the route/UoW* and creates no side effect.
    `RunnerLanguage` (`modules/runner/domain.py`) has no `relational` member
    at all, so this is closed-schema Pydantic validation, and FastAPI
    resolves every dependency -- including `get_owner_id` -- before
    checking body fields. Proving zero UoWs/SQL/pool-checkouts here proves
    `get_owner_id` (`api/dependencies.py`) never touches the database on
    this path, not merely that this one route happens not to.
    """
    app = client.app
    original_uow_factory = app.state.uow_factory
    uow_calls = 0

    def counting_uow_factory():
        nonlocal uow_calls
        uow_calls += 1
        return original_uow_factory()

    app.state.uow_factory = counting_uow_factory

    statements: list[str] = []
    checkouts: list[object] = []

    def _on_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    def _on_checkout(dbapi_conn, connection_record, connection_proxy):
        checkouts.append(connection_record)

    engine = app.state.engine
    event.listen(engine, "before_cursor_execute", _on_cursor_execute)
    event.listen(engine, "checkout", _on_checkout)
    try:
        content = b"public class Main {}"
        response = client.post(
            "/api/v1/runner/confirmations",
            json={
                "language": "relational",
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
    finally:
        event.remove(engine, "before_cursor_execute", _on_cursor_execute)
        event.remove(engine, "checkout", _on_checkout)
        app.state.uow_factory = original_uow_factory

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "request_validation_error"
    assert any(error["field"] == "body.language" for error in body["field_errors"])

    assert uow_calls == 0
    assert statements == []
    assert checkouts == []

    with app.state.session_factory() as session:
        assert (
            session.execute(text("SELECT count(*) FROM runner_confirmations")).scalar()
            == 0
        )
        assert session.execute(text("SELECT count(*) FROM jobs")).scalar() == 0


def test_job_retry_extra_field_422_opens_no_uow(client) -> None:
    """Documents that the `get_owner_id` fix (`api/dependencies.py`) is
    systemic, not special-cased to the runner route: `POST
    /jobs/{id}/retry` also depends on `get_owner_id` without declaring its
    own `get_unit_of_work`, so its `422` (a `JobRetryRequest` field the
    closed schema forbids) must open zero UoWs too.
    """
    app = client.app
    original_uow_factory = app.state.uow_factory
    uow_calls = 0

    def counting_uow_factory():
        nonlocal uow_calls
        uow_calls += 1
        return original_uow_factory()

    app.state.uow_factory = counting_uow_factory
    try:
        response = client.post(
            "/api/v1/jobs/does-not-exist/retry",
            json={"unexpected_field": True},
        )
    finally:
        app.state.uow_factory = original_uow_factory

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "request_validation_error"
    assert any(
        error["field"] == "body.unexpected_field" for error in body["field_errors"]
    )
    assert uow_calls == 0


def _declared(path: str, content: bytes) -> DeclaredInput:
    return DeclaredInput(
        path,
        "java-source",
        "inline-base64:" + base64.b64encode(content).decode(),
        hashlib.sha256(content).hexdigest(),
    )


def test_runner_input_limits_accept_exact_boundaries_and_reject_plus_one(
    tmp_path,
) -> None:
    settings = build_isolated_settings(tmp_path)
    exact_files = tuple(
        _declared(f"Source{index}.java", b"")
        for index in range(settings.runner_input_files_limit)
    )
    assert len(resolve_inputs_within_limits(exact_files, settings)) == 100
    with pytest.raises(RunnerInputLimitError, match="100-file"):
        resolve_inputs_within_limits(
            (*exact_files, _declared("Overflow.java", b"")), settings
        )

    exact_bytes = (_declared("Main.java", b"x" * settings.runner_input_bytes_limit),)
    assert (
        len(resolve_inputs_within_limits(exact_bytes, settings)[0][1])
        == 10 * 1024 * 1024
    )
    with pytest.raises(RunnerInputLimitError, match="10 MiB"):
        resolve_inputs_within_limits(
            (_declared("Main.java", b"x" * (settings.runner_input_bytes_limit + 1)),),
            settings,
        )


def test_runner_input_file_limit_is_checked_before_base64_decode(tmp_path) -> None:
    settings = build_isolated_settings(tmp_path)
    invalid = DeclaredInput("Bad.java", "java-source", "not-base64", "bad")
    with pytest.raises(RunnerInputLimitError, match="100-file"):
        resolve_inputs_within_limits(
            tuple(invalid for _ in range(settings.runner_input_files_limit + 1)),
            settings,
        )


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
    migrated_database_url: str, tmp_path
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
    app = _enabled_app(migrated_database_url, tmp_path)
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
    migrated_database_url: str, tmp_path
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
    app = _enabled_app(migrated_database_url, tmp_path)
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
    assert result["output_chunks"][-1]["truncated"] is True
    assert "YUNO runner output truncated" in result["output_chunks"][-1]["content"]
    assert result["cleanup_state"] == "cleanup-complete"


def test_compile_and_test_share_wall_cpu_and_output_budgets(
    migrated_database_url: str, tmp_path
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
    app = _enabled_app(migrated_database_url, tmp_path)
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
    assert (
        sum(len(chunk["content"].encode()) for chunk in result["output_chunks"]) == 4096
    )
    assert result["output_chunks"][-1]["truncated"] is True


def test_exact_output_limit_still_allows_a_silent_test_phase(
    migrated_database_url: str, tmp_path
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
    app = _enabled_app(migrated_database_url, tmp_path)
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
            (spec.working_directory / f"generated-{index}.bin").write_bytes(
                b"x" * 30_000
            )
        return super().run(spec, on_spawn=on_spawn, cancelled=cancelled)


def test_aggregate_workspace_limit_catches_many_small_generated_files(
    migrated_database_url: str, tmp_path
) -> None:
    fake = _ManySmallFilesProcessPort(
        (RunnerProcessOutcome(1234, 1234, 0, None, False, False, (), 10, 1),)
    )
    app = _enabled_app(migrated_database_url, tmp_path)
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
    assert "runner-temp-bytes-limit" in result["output_chunks"][-1]["content"]
    assert result["output_chunks"][-1]["truncated"] is True


def test_input_temp_limit_rejects_before_process_invocation(
    migrated_database_url: str, tmp_path
) -> None:
    fake = _FakeProcessPort(())
    app = _enabled_app(migrated_database_url, tmp_path, runner_temp_bytes=32)
    with TestClient(app) as client:
        app.state.runner_process_port = fake
        started = _confirm_and_start(client, operation="compile", key="pre-spawn-temp")
        run_id = started.json()["job_id"]
        for _ in range(100):
            result = client.get(f"/api/v1/runner-runs/{run_id}").json()
            if result["cleanup_state"] != "cleanup-pending":
                break
            time.sleep(0.01)
    assert fake.specs == []
    assert result["state"] == "timed-out-or-limited"
    assert "runner-temp-bytes-limit" in result["output_chunks"][-1]["content"]
    assert result["cleanup_state"] == "cleanup-complete"


def test_capabilities_detect_missing_and_incompatible(
    migrated_database_url: str, tmp_path
) -> None:
    missing = _enabled_app(
        migrated_database_url,
        tmp_path,
        runner_javac_command="definitely-not-a-java-command",
    )
    with TestClient(missing) as client:
        assert (
            client.get("/api/v1/runner/capabilities").json()["capabilities"][0]["state"]
            == "missing"
        )
    incompatible = _enabled_app(
        migrated_database_url,
        tmp_path,
        runner_java_version_prefix="approved-java-never-matches",
    )
    with TestClient(incompatible) as client:
        assert (
            client.get("/api/v1/runner/capabilities").json()["capabilities"][0]["state"]
            == "incompatible"
        )


@pytest.mark.parametrize(
    ("snapshot", "expected_code"),
    (
        (
            PlatformSnapshot(
                system_name="Linux",
                machine="x86_64",
                os_release={"ID": "fedora", "VERSION_ID": "24.04"},
            ),
            UNSUPPORTED_PLATFORM,
        ),
        (
            PlatformSnapshot(
                system_name="Linux",
                machine="x86_64",
                os_release={"ID": "ubuntu", "VERSION_ID": "22.04"},
            ),
            UNSUPPORTED_PLATFORM,
        ),
        (
            PlatformSnapshot(
                system_name="Linux",
                machine="riscv64",
                os_release={"ID": "ubuntu", "VERSION_ID": "24.04"},
            ),
            UNSUPPORTED_PLATFORM,
        ),
        (
            PlatformSnapshot(system_name="Darwin", machine="arm64", os_release=None),
            UNSUPPORTED_PLATFORM,
        ),
        (
            PlatformSnapshot(system_name="Windows", machine="AMD64", os_release=None),
            UNSUPPORTED_PLATFORM,
        ),
        (
            PlatformSnapshot(
                system_name="Linux",
                machine="x86_64",
                os_release={"ID": "ubuntu", "VERSION_ID": "24.04"},
                wsl_env_present=True,
            ),
            UNSUPPORTED_PLATFORM,
        ),
        (
            PlatformSnapshot(
                system_name="Linux",
                machine="x86_64",
                os_release={"ID": "ubuntu", "VERSION_ID": "24.04"},
                kernel_osrelease="5.15.0-microsoft-standard-WSL2",
            ),
            UNSUPPORTED_PLATFORM,
        ),
        (
            PlatformSnapshot(
                system_name="Linux",
                machine="x86_64",
                os_release={"ID": "ubuntu", "VERSION_ID": "24.04"},
                dockerenv_present=True,
            ),
            UNSUPPORTED_PLATFORM,
        ),
        (
            PlatformSnapshot(
                system_name="Linux",
                machine="x86_64",
                os_release={"ID": "ubuntu", "VERSION_ID": "24.04"},
                containerenv_present=True,
            ),
            UNSUPPORTED_PLATFORM,
        ),
        (
            PlatformSnapshot(
                system_name="Linux",
                machine="x86_64",
                os_release={"ID": "ubuntu", "VERSION_ID": "24.04"},
                cgroup_text="12:pids:/docker/abcdef0123456789",
            ),
            UNSUPPORTED_PLATFORM,
        ),
        (
            PlatformSnapshot(system_name="Linux", machine="x86_64", os_release=None),
            PLATFORM_UNVERIFIABLE,
        ),
        (
            PlatformSnapshot(
                system_name="Linux", machine="x86_64", os_release={"ID": "ubuntu"}
            ),
            PLATFORM_UNVERIFIABLE,
        ),
        (
            PlatformSnapshot(
                system_name="Linux",
                machine="x86_64",
                os_release={"VERSION_ID": "24.04"},
            ),
            PLATFORM_UNVERIFIABLE,
        ),
    ),
)
def test_evaluate_platform_rejects_every_unapproved_row(
    snapshot: PlatformSnapshot, expected_code: str
) -> None:
    outcome = evaluate_platform(snapshot)
    assert outcome.diagnostic_code == expected_code


def test_evaluate_platform_accepts_the_exact_approved_row() -> None:
    outcome = evaluate_platform(_APPROVED_PLATFORM_SNAPSHOT)
    assert outcome.diagnostic_code is None
    assert (outcome.os, outcome.version, outcome.arch) == ("linux", "24.04", "x86_64")


def test_evaluate_platform_accepts_normalized_arm64() -> None:
    outcome = evaluate_platform(
        PlatformSnapshot(
            system_name="Linux",
            machine="aarch64",
            os_release={"ID": "ubuntu", "VERSION_ID": "24.04"},
        )
    )
    assert outcome.diagnostic_code is None
    assert outcome.arch == "arm64"


def test_detect_command_gates_supported_on_platform_before_command_check() -> None:
    # `/usr/bin/true` always exits 0, so absent the platform gate this would
    # report `supported` on a host outside the approved matrix -- exactly
    # the IDK-005 section 1 violation this gate exists to close.
    result = detect_command(
        "java",
        "compile-and-test",
        "/usr/bin/true",
        None,
        platform_probe=lambda: PlatformSnapshot(
            system_name="Darwin", machine="arm64", os_release=None
        ),
    )
    assert result["state"] == "incompatible"
    assert result["diagnostic_code"] == UNSUPPORTED_PLATFORM

    unverifiable = detect_command(
        "java",
        "compile-and-test",
        "/usr/bin/true",
        None,
        platform_probe=lambda: PlatformSnapshot(
            system_name="Linux", machine="x86_64", os_release=None
        ),
    )
    assert unverifiable["state"] == "incompatible"
    assert unverifiable["diagnostic_code"] == PLATFORM_UNVERIFIABLE

    supported = detect_command(
        "java",
        "compile-and-test",
        "/usr/bin/true",
        None,
        platform_probe=lambda: _APPROVED_PLATFORM_SNAPSHOT,
    )
    assert supported["state"] == "supported"
    assert supported["diagnostic_code"] is None


def test_capabilities_endpoint_reports_unsupported_platform_and_platform_unverifiable(
    migrated_database_url: str, tmp_path
) -> None:
    unsupported = _enabled_app(migrated_database_url, tmp_path)
    unsupported.state.runner_platform_probe = lambda: PlatformSnapshot(
        system_name="Darwin", machine="arm64", os_release=None
    )
    with TestClient(unsupported) as client:
        item = client.get("/api/v1/runner/capabilities").json()["capabilities"][0]
        assert item["state"] == "incompatible"

    unverifiable = _enabled_app(migrated_database_url, tmp_path)
    unverifiable.state.runner_platform_probe = lambda: PlatformSnapshot(
        system_name="Linux", machine="x86_64", os_release=None
    )
    with TestClient(unverifiable) as client:
        item = client.get("/api/v1/runner/capabilities").json()["capabilities"][0]
        assert item["state"] == "incompatible"


def test_cancelled_outcome_records_cleanup_failure(
    migrated_database_url: str, tmp_path
) -> None:
    fake = _FakeProcessPort(
        (RunnerProcessOutcome(1234, 1234, None, 15, False, True, (), 1),)
    )
    app = _enabled_app(migrated_database_url, tmp_path)
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
        with app.state.session_factory() as session:
            cleanup = session.execute(
                text(
                    "SELECT i.kind,i.status,i.failure_classification,b.temp_path,"
                    "r.temp_path_hash FROM file_cleanup_intents i "
                    "JOIN runner_records r ON r.id=:run_id "
                    "LEFT JOIN runner_record_bodies b ON b.runner_id=r.id "
                    "WHERE i.owner_id=r.owner_id AND i.goal_id IS r.goal_id"
                ),
                {"run_id": run_id},
            ).one()
    assert result["state"] == "cancelled"
    assert result["cleanup_state"] == "cleanup-failed"
    assert result["cleanup_diagnostic"] == "runner-workspace-cleanup-failed"
    assert cleanup.kind == "runner-workspace"
    assert (cleanup.status, cleanup.failure_classification) in {
        ("pending", "runner-workspace-cleanup-failed"),
        ("complete", None),
    }
    assert cleanup.temp_path is None
    assert cleanup.temp_path_hash is not None
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


@pytest.mark.parametrize(
    ("stream", "size", "expected_classification"),
    (
        ("stdout", 128, None),
        ("stdout", 129, "runner-stdout-limit"),
        ("stderr", 129, "runner-stderr-limit"),
    ),
)
def test_local_process_enforces_independent_stream_boundaries(
    tmp_path, stream: str, size: int, expected_classification: str | None
) -> None:
    script = (
        f"import sys; sys.{stream}.buffer.write(b'x' * {size}); sys.{stream}.flush()"
    )
    outcome = LocalRunnerProcessPort().run(
        RunnerProcessSpec(
            (sys.executable, "-c", script),
            tmp_path,
            {"PATH": "/bin", "LANG": "C"},
            ProcessLimits(
                2, 1, 512_000_000, 16, 256, 1_000_000, 1_000_000, 128, 128, 100
            ),
            "compile",
        ),
        on_spawn=lambda *_args: None,
        cancelled=lambda: False,
    )
    assert outcome.limit_classification == expected_classification
    assert outcome.timed_out_or_limited is (expected_classification is not None)


def test_local_process_enforces_aggregate_output_across_streams(tmp_path) -> None:
    outcome = LocalRunnerProcessPort().run(
        RunnerProcessSpec(
            (
                sys.executable,
                "-c",
                "import sys; sys.stdout.write('o'*80); sys.stdout.flush(); sys.stderr.write('e'*80); sys.stderr.flush()",
            ),
            tmp_path,
            {"PATH": "/bin", "LANG": "C"},
            ProcessLimits(
                2, 1, 512_000_000, 16, 128, 1_000_000, 1_000_000, 128, 128, 100
            ),
            "compile",
        ),
        on_spawn=lambda *_args: None,
        cancelled=lambda: False,
    )
    assert outcome.limit_classification == "runner-output-limit"
    assert sum(len(chunk.content.encode()) for chunk in outcome.chunks) == 128


def test_local_process_cancels_process_group_on_live_temp_file_growth(tmp_path) -> None:
    outcome = LocalRunnerProcessPort().run(
        RunnerProcessSpec(
            (
                sys.executable,
                "-c",
                "import pathlib,time; [(pathlib.Path(f'f{i}').write_text('x')) for i in range(4)]; time.sleep(5)",
            ),
            tmp_path,
            {"PATH": "/bin", "LANG": "C"},
            ProcessLimits(
                2, 1, 512_000_000, 16, 4096, 1_000_000, 1_000_000, 4096, 4096, 3
            ),
            "compile",
        ),
        on_spawn=lambda *_args: None,
        cancelled=lambda: False,
    )
    assert outcome.timed_out_or_limited is True
    assert outcome.limit_classification == "runner-temp-files-limit"
    assert outcome.signal in (signal.SIGTERM, signal.SIGKILL)


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
    migrated_database_url: str, tmp_path
) -> None:
    app = _enabled_app(migrated_database_url, tmp_path)
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
    migrated_database_url: str, monkeypatch, tmp_path
) -> None:
    app = _enabled_app(migrated_database_url, tmp_path)
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
