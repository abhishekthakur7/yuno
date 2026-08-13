from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.integration.test_evidence_evaluation import (
    FakeEvaluationAdapter,
    _arrange,
)
from tests.integration.test_progress import FixedClock
from yuno.modules.evidence_evaluation.service import perform_assessment
from yuno.shared.application.unit_of_work import UnitOfWorkFactory


def _stored_learning_rows(engine: Engine) -> dict[str, list[tuple[object, ...]]]:
    with engine.connect() as connection:
        return {
            table: [
                tuple(row)
                for row in connection.execute(text(f"SELECT * FROM {table} ORDER BY 1"))
            ]
            for table in ("evidence", "assessments", "goal_progress_memos")
        }


def test_progress_display_setting_persists_without_mutating_learning_data(
    client: TestClient,
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
) -> None:
    clock = FixedClock()
    clock.instant = datetime(2027, 1, 1, tzinfo=UTC)
    client.app.state.clock = clock
    owner_id, evidence, _rubric, evaluation_request = _arrange(uow_factory)
    with uow_factory() as uow:
        assessment = perform_assessment(
            uow, FakeEvaluationAdapter(), owner_id, evaluation_request
        )
        uow.commit()

    evidence_before = client.get(f"/api/v1/goals/{evidence.goal_id}/evidence").json()
    assessment_before = client.get(f"/api/v1/assessments/{assessment.id}").json()
    progress_before = client.get(f"/api/v1/goals/{evidence.goal_id}/progress").json()
    rows_before = _stored_learning_rows(engine)

    initial = client.get("/api/v1/settings")
    assert initial.status_code == 200
    assert initial.json()["progress_display"] == "detailed"
    assert initial.json()["row_version"] == 1
    assert initial.json()["provider_selection"] is None
    assert initial.json()["accessibility"] == {"reduced_motion": False}

    changed = client.patch(
        "/api/v1/settings",
        headers={"If-Match": "1"},
        json={
            "progress_display": "simple",
            "accessibility": {"reduced_motion": True},
            "provider_selection": "claude",
        },
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["progress_display"] == "simple"
    assert changed.json()["accessibility"] == {"reduced_motion": True}
    assert changed.json()["provider_selection"] == "claude"
    assert changed.json()["row_version"] == 2
    assert client.get("/api/v1/settings").json() == changed.json()

    assert (
        client.get(f"/api/v1/goals/{evidence.goal_id}/evidence").json()
        == evidence_before
    )
    assert (
        client.get(f"/api/v1/assessments/{assessment.id}").json() == assessment_before
    )
    assert (
        client.get(f"/api/v1/goals/{evidence.goal_id}/progress").json()
        == progress_before
    )
    assert _stored_learning_rows(engine) == rows_before

    stale = client.patch(
        "/api/v1/settings",
        headers={"If-Match": "1"},
        json={"progress_display": "detailed"},
    )
    assert stale.status_code == 412
    assert stale.json()["code"] == "precondition_failed"
    assert client.get("/api/v1/settings").json() == changed.json()
    assert _stored_learning_rows(engine) == rows_before


def test_invalid_settings_are_rejected_without_changing_stored_version(
    client: TestClient,
) -> None:
    initial = client.get("/api/v1/settings").json()
    invalid_bodies = (
        {"progress_display": "verbose"},
        {"progress_display": None},
        {"accessibility": None},
        {"accessibility": {"reduced_motion": "sometimes"}},
        {"provider_selection": "unknown"},
    )

    for body in invalid_bodies:
        response = client.patch(
            "/api/v1/settings",
            headers={"If-Match": str(initial["row_version"])},
            json=body,
        )
        assert response.status_code == 422, (body, response.text)

    assert client.get("/api/v1/settings").json() == initial


def test_data_lifecycle_policy_endpoint_exposes_enforced_approved_values(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/settings/data-lifecycle-policy")

    assert response.status_code == 200
    policy = response.json()
    assert policy == {
        "policy_version": "1.0",
        "import_original_max_bytes": 10 * 1024 * 1024,
        "import_retained_owner_limit": 100,
        "import_statements_per_import_limit": 10_000,
        "import_unreviewed_owner_limit": 50_000,
        "evidence_payload_max_bytes": 10 * 1024 * 1024,
        "evidence_retained_owner_limit": 10_000,
        "generated_body_max_bytes": 2 * 1024 * 1024,
        "generated_retained_owner_limit": 5_000,
        "interview_turns_per_session_limit": 1_000,
        "interview_bytes_per_session_limit": 10 * 1024 * 1024,
        "interview_sessions_owner_limit": 200,
        "runner_input_files_limit": 100,
        "runner_input_bytes_limit": 10 * 1024 * 1024,
        "runner_stdout_bytes_limit": 1024 * 1024,
        "runner_stderr_bytes_limit": 1024 * 1024,
        "runner_output_bytes_limit": 2 * 1024 * 1024,
        "runner_temp_bytes_limit": 256 * 1024 * 1024,
        "runner_temp_files_limit": 10_000,
        "overlay_proposal_pending_cap": 25,
        "pending_job_cap": 100,
        "diagnostic_abandoned_retention_days": 30,
        "interview_inactive_retention_days": 30,
        "terminal_job_retention_days": 30,
        "job_event_retention_days": 7,
        "job_event_owner_limit": 10_000,
        "runner_output_retention_days": 7,
        "runner_workspace_retention_seconds": 3_600,
        "export_package_retention_seconds": 86_400,
        "export_operation_retention_days": 30,
        "structured_log_file_count": 5,
        "structured_log_file_max_bytes": 10 * 1024 * 1024,
        "structured_log_total_max_bytes": 50 * 1024 * 1024,
        "structured_log_retention_days": 14,
        "export_format": "yuno-portable-export",
        "export_version": "1.0",
        "export_available": True,
        "recovery_window_days": 0,
        "yuno_managed_backups": False,
        "remote_support_access": False,
    }
