from __future__ import annotations

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DatabaseError

from tests.integration.test_evidence_transfer_delete import _seed
from tests.integration.test_owner_isolation import _insert_second_owner
from tests.job_assertions import wait_for_job
from yuno.modules.evidence_evaluation.domain import TransferClassification
from yuno.modules.evidence_evaluation.service import transfer_evidence
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.ids import new_id


def test_export_is_fail_closed_without_policy(client) -> None:
    response = client.post(
        "/api/v1/exports", headers={"Idempotency-Key": "export-disabled"}, json={}
    )
    assert response.status_code == 503
    assert response.json()["code"] == "unavailable"


def test_configured_export_is_versioned_complete_and_marks_tombstoned_content_unavailable(
    client, uow_factory: UnitOfWorkFactory, database_url: str
) -> None:
    owner_id, goal_id, target_id, evidence_id = _seed(uow_factory)
    with uow_factory() as uow:
        transfer_evidence(
            uow,
            owner_id,
            source_goal_id=goal_id,
            source_evidence_id=evidence_id,
            target_goal_id=target_id,
            classification=TransferClassification.PARTIAL,
            rationale="Export tombstone fixture.",
            recommended_depth="Implementation",
        )
        uow.commit()
    preflight = client.post(
        f"/api/v1/goals/{goal_id}/delete-preflight",
        headers={"Idempotency-Key": "export-delete-preflight"},
    ).json()
    deletion = client.post(
        f"/api/v1/goals/{goal_id}/delete",
        headers={"Idempotency-Key": "export-delete"},
        json={
            "operation_id": preflight["operation_id"],
            "snapshot_id": preflight["snapshot_id"],
        },
    )
    wait_for_job(client, deletion)
    client.app.state.settings.export_format_version = "test-export-v1"
    created = client.post(
        "/api/v1/exports",
        headers={"Idempotency-Key": "export-enabled"},
        json={"goal_id": goal_id},
    )
    assert created.status_code == 202, created.text
    wait_for_job(client, created)
    operation = client.get(f"/api/v1/exports/{created.json()['job_id']}")
    assert operation.status_code == 200, operation.text
    body = operation.json()
    assert body["status"] == "complete"
    assert body["format_version"] == "test-export-v1"
    assert body["result_ref"] == f"ExportOperation:{body['id']}"
    package = body["package"]
    assert package["product"] == "Yuno"
    assert set(package) >= {
        "profile",
        "goals",
        "graph_pins",
        "overlays",
        "evidence",
        "notebook",
        "review",
        "diagnostics",
        "imports",
        "provenance",
        "interview_transcripts",
    }
    assert package["evidence"][0]["availability"] == "unavailable"
    assert package["evidence"][0]["content"] is None
    assert set(package["evidence"][0]) >= {
        "id",
        "goal_id",
        "topic_stable_id",
        "evidence_type",
        "capability",
        "payload_hash",
        "summary",
        "origin",
        "content_version",
        "created_at",
    }
    assert package["interview_transcripts"] == {
        "availability": "unavailable",
        "reason": "policy-unconfigured",
    }

    second_owner_id = new_id()
    _insert_second_owner(
        database_url, owner_id=second_owner_id, display_name="Export Isolation Owner"
    )
    with uow_factory() as uow:
        assert uow.settings_data.get_export(second_owner_id, body["id"]) is None


def test_goal_scoped_export_rejects_unknown_goal_before_reserving_operation(
    client, engine: Engine
) -> None:
    client.app.state.settings.export_format_version = "test-export-v1"
    response = client.post(
        "/api/v1/exports",
        headers={"Idempotency-Key": "unknown-goal-export"},
        json={"goal_id": new_id()},
    )
    assert response.status_code == 404
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM export_operations")
            ).scalar_one()
            == 0
        )


def test_delete_preflight_snapshot_and_operation_impact_are_database_immutable(
    client, engine: Engine, uow_factory: UnitOfWorkFactory
) -> None:
    _owner_id, goal_id, _target_id, _evidence_id = _seed(uow_factory)
    preflight = client.post(
        f"/api/v1/goals/{goal_id}/delete-preflight",
        headers={"Idempotency-Key": "immutable-delete-preflight"},
    ).json()
    with engine.begin() as connection, pytest.raises(DatabaseError):
        connection.execute(
            text(
                "UPDATE evidence_delete_snapshots SET impact_hash='changed' "
                "WHERE id=:id"
            ),
            {"id": preflight["snapshot_id"]},
        )
    with engine.begin() as connection, pytest.raises(DatabaseError):
        connection.execute(
            text("UPDATE delete_operations SET scope='other' WHERE id=:id"),
            {"id": preflight["operation_id"]},
        )
