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
