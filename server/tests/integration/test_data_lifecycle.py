from __future__ import annotations

import hashlib
import json

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DatabaseError

from tests.integration.test_evidence_transfer_delete import _seed
from tests.integration.test_overlay_proposals import _create as _create_proposal
from tests.integration.test_overlay_proposals import _setup as _setup_proposal
from tests.integration.test_owner_isolation import _insert_second_owner
from tests.job_assertions import wait_for_job
from yuno.modules.evidence_evaluation.domain import TransferClassification
from yuno.modules.evidence_evaluation.service import transfer_evidence
from yuno.modules.settings_data.service import canonical_json, get_export_download
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.errors import NotFoundError
from yuno.shared.domain.ids import new_id


def test_export_remains_fail_closed_until_privacy_review_passes(
    client, settings, engine: Engine
) -> None:
    settings.export_privacy_review_approved = False
    response = client.post(
        "/api/v1/exports",
        headers={"Idempotency-Key": "export-before-privacy-review"},
        json={"version": "1.0"},
    )
    assert response.status_code == 503
    assert response.json()["code"] == "unavailable"
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM export_operations")) == 0


def test_export_rejects_unsupported_major_version(client) -> None:
    response = client.post(
        "/api/v1/exports",
        headers={"Idempotency-Key": "export-v2"},
        json={"version": "2.0"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "unsupported-export-version"


def test_configured_export_is_versioned_complete_and_marks_tombstoned_content_unavailable(
    client, engine: Engine, uow_factory: UnitOfWorkFactory, database_url: str
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
    disclosure_id = new_id()
    provider_request_id = new_id()
    quarantine_id = new_id()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO network_disclosures(id,owner_id,category,operation,destination,data_categories_json,disclosure_version,accepted_at) "
                "VALUES (:id,:owner,'model-provider','generate','local-test','[]','1.0',:at)"
            ),
            {
                "id": disclosure_id,
                "owner": owner_id,
                "at": "2026-08-13T00:00:00.000000Z",
            },
        )
        connection.execute(
            text(
                "INSERT INTO provider_requests(id,owner_id,goal_id,job_id,purpose,provider,adapter_version,contract_version,context_ref_hash,disclosure_id,lifecycle,diagnostic_classification,body_hash,created_at) "
                "VALUES (:id,:owner,:goal,:job,'export-test','codex','1.0','1.0',:hash,:disclosure,'quarantined','schema-invalid',:body_hash,:at)"
            ),
            {
                "id": provider_request_id,
                "owner": owner_id,
                "goal": goal_id,
                "job": deletion.json()["job_id"],
                "hash": "c" * 64,
                "body_hash": "b" * 64,
                "disclosure": disclosure_id,
                "at": "2026-08-13T00:00:01.000000Z",
            },
        )
        connection.execute(
            text(
                "INSERT INTO schema_quarantines(id,owner_id,provider_request_id,job_id,raw_output_hash,expected_schema_version,body_hash,created_at) "
                "VALUES (:id,:owner,:request,:job,:raw_hash,'1.0',:body_hash,:at)"
            ),
            {
                "id": quarantine_id,
                "owner": owner_id,
                "request": provider_request_id,
                "job": deletion.json()["job_id"],
                "raw_ref": "raw-output-secret-ref",
                "raw_hash": "d" * 64,
                "body_hash": "e" * 64,
                "at": "2026-08-13T00:00:02.000000Z",
            },
        )
        connection.execute(
            text(
                "INSERT INTO schema_quarantine_bodies(quarantine_id,owner_id,raw_output_ref,validation_errors_json) "
                "VALUES (:id,:owner,:raw_ref,:errors)"
            ),
            {
                "id": quarantine_id,
                "owner": owner_id,
                "raw_ref": "raw-output-secret-ref",
                "errors": json.dumps(["raw-validation-secret"]),
            },
        )
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
    assert body["format"] == "yuno-portable-export"
    assert body["version"] == "1.0"
    assert body["filename"].startswith("yuno-export-v1-")
    assert body["filename"].endswith("Z.json")
    assert len(body["package_hash"]) == 64
    assert body["completed_at"] < body["package_expires_at"]
    assert body["package_expires_at"] < body["metadata_expires_at"]
    assert body["download_available"] is True
    assert body["result_ref"] == f"ExportOperation:{body['id']}"

    download = client.get(f"/api/v1/exports/{body['id']}/download")
    assert download.status_code == 200, download.text
    assert download.content.decode("utf-8") == download.text
    assert not download.content.startswith(b"\xef\xbb\xbf")
    assert download.headers["content-disposition"] == (
        f'attachment; filename="{body["filename"]}"'
    )
    assert download.headers["etag"] == f'"{body["package_hash"]}"'
    assert hashlib.sha256(download.content).hexdigest() == body["package_hash"]
    assert download.text == canonical_json(json.loads(download.text))

    package = download.json()
    assert package["product"] == "Yuno"
    assert list(package) == sorted(package)
    assert set(package) == {
        "product",
        "format",
        "version",
        "exported_at",
        "scope",
        "data",
        "integrity",
    }
    assert package["format"] == "yuno-portable-export"
    assert package["version"] == "1.0"
    assert package["scope"] == {"kind": "goal", "goal_id": goal_id}
    assert package["integrity"] == {
        "algorithm": "sha256",
        "digest": hashlib.sha256(
            canonical_json(package["data"]).encode("utf-8")
        ).hexdigest(),
    }
    data = package["data"]
    assert set(data) == {
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
        "provider",
        "runner",
        "generated_artifacts",
        "artifact_provenance",
    }
    deleted_goal = next(item for item in data["goals"] if item["id"] == goal_id)
    assert deleted_goal["availability"] == "unavailable"
    assert deleted_goal["reason"] == "tombstoned"
    assert deleted_goal["name"] is None
    assert data["evidence"][0]["availability"] == "unavailable"
    assert data["evidence"][0]["reason"] == "tombstoned"
    assert data["evidence"][0]["content"] is None
    assert set(data["evidence"][0]) >= {
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
    encoded = download.text
    assert "Export tombstone fixture." not in encoded
    assert "policy-unconfigured" not in encoded
    assert "unreviewed-originals-excluded" not in encoded
    assert "raw-output-secret-ref" not in encoded
    assert "raw-validation-secret" not in encoded
    assert data["provider"]["quarantines"] == [
        {
            "availability": "unavailable",
            "created_at": "2026-08-13T00:00:02.000000Z",
            "expected_schema_version": "1.0",
            "failure_classification": "schema-invalid",
            "id": quarantine_id,
            "job_id": deletion.json()["job_id"],
            "provider_request_id": provider_request_id,
            "raw_output_hash": "d" * 64,
            "reason": "policy-excluded",
        }
    ]
    reasons = _all_values_for_key(package, "reason")
    assert reasons <= {
        "tombstoned",
        "source-missing",
        "raw-original-excluded",
        "policy-excluded",
        None,
    }

    second_owner_id = new_id()
    _insert_second_owner(
        database_url, owner_id=second_owner_id, display_name="Export Isolation Owner"
    )
    with uow_factory() as uow:
        assert uow.settings_data.get_export(second_owner_id, body["id"]) is None
        with pytest.raises(NotFoundError):
            get_export_download(uow, second_owner_id, body["id"])

    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE export_operations SET package_expires_at='2000-01-01T00:00:00.000000Z' WHERE id=:id"
            ),
            {"id": body["id"]},
        )
    expired = client.get(f"/api/v1/exports/{body['id']}/download")
    assert expired.status_code == 410
    assert expired.json()["code"] == "gone"
    status = client.get(f"/api/v1/exports/{body['id']}").json()
    assert status["status"] == "expired"
    assert status["download_available"] is False
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM export_package_bodies WHERE operation_id=:id"
                ),
                {"id": body["id"]},
            )
            == 0
        )


def test_goal_scoped_export_rejects_unknown_goal_before_reserving_operation(
    client, engine: Engine
) -> None:
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


def test_export_inventory_marks_missing_profile_and_overlay_bodies(
    client, engine: Engine, uow_factory: UnitOfWorkFactory
) -> None:
    owner_id, goal_id, graph_id = _setup_proposal(uow_factory)
    proposal_id = _create_proposal(
        client, goal_id, graph_id, key="export-missing-proposal"
    ).json()["id"]
    with engine.begin() as connection:
        connection.execute(
            text("DELETE FROM learner_profile_bodies WHERE owner_id=:owner_id"),
            {"owner_id": owner_id},
        )
        connection.execute(
            text(
                "DELETE FROM overlay_proposal_bodies "
                "WHERE proposal_id=:proposal_id AND owner_id=:owner_id"
            ),
            {"proposal_id": proposal_id, "owner_id": owner_id},
        )
    with uow_factory() as uow:
        data = uow.settings_data.read_export_data(owner_id, goal_id)
    profile = data["profile"][0]
    assert profile["availability"] == "unavailable"
    assert profile["reason"] == "source-missing"
    assert profile["experience"] is None
    assert profile["strengths"] is None
    assert profile["weaknesses"] is None
    proposal = data["overlays"]["proposals"][0]
    assert proposal["id"] == proposal_id
    assert proposal["availability"] == "unavailable"
    assert proposal["reason"] == "source-missing"
    assert proposal["payload"] is None


def test_goal_delete_expires_existing_export_package(
    client, engine: Engine, uow_factory: UnitOfWorkFactory
) -> None:
    _owner_id, goal_id, _target_id, _evidence_id = _seed(uow_factory)
    created = client.post(
        "/api/v1/exports",
        headers={"Idempotency-Key": "pre-delete-export"},
        json={"goal_id": goal_id},
    )
    assert created.status_code == 202, created.text
    wait_for_job(client, created)
    operation_id = created.json()["job_id"]
    assert client.get(f"/api/v1/exports/{operation_id}/download").status_code == 200

    preflight = client.post(
        f"/api/v1/goals/{goal_id}/delete-preflight",
        headers={"Idempotency-Key": "package-delete-preflight"},
    ).json()
    deletion = client.post(
        f"/api/v1/goals/{goal_id}/delete",
        headers={"Idempotency-Key": "package-delete"},
        json={
            "operation_id": preflight["operation_id"],
            "snapshot_id": preflight["snapshot_id"],
        },
    )
    wait_for_job(client, deletion)

    status = client.get(f"/api/v1/exports/{operation_id}")
    assert status.status_code == 200, status.text
    assert status.json()["status"] == "expired"
    assert status.json()["download_available"] is False
    expired = client.get(f"/api/v1/exports/{operation_id}/download")
    assert expired.status_code == 410
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM export_package_bodies "
                    "WHERE operation_id=:operation_id"
                ),
                {"operation_id": operation_id},
            )
            == 0
        )


def _all_values_for_key(value: object, key: str) -> set[object]:
    found: set[object] = set()
    if isinstance(value, dict):
        if key in value:
            found.add(value[key])
        for child in value.values():
            found.update(_all_values_for_key(child, key))
    elif isinstance(value, list):
        for child in value:
            found.update(_all_values_for_key(child, key))
    return found


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


def test_goal_delete_removes_interview_bundle_and_replay_secret_from_whole_database(
    client, engine: Engine, uow_factory: UnitOfWorkFactory
) -> None:
    owner_id, goal_id, _target_id, _evidence_id = _seed(uow_factory)
    sentinel = "IDK-010-SECRET-BUNDLE-7dcbf90a"
    created = client.post(
        "/api/v1/interview-bundles",
        headers={"Idempotency-Key": "secret-bundle-body"},
        json={
            "goal_id": goal_id,
            "name": sentinel,
            "generic_role": f"role-{sentinel}",
            "target_level": "Senior",
            "origin": f"origin-{sentinel}",
            "items": [
                {
                    "subject": "technical",
                    "topic_stable_id": "queues",
                    "question": f"question-{sentinel}",
                    "position": 0,
                    "is_optional": False,
                    "included": True,
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    preflight = client.post(
        f"/api/v1/goals/{goal_id}/delete-preflight",
        headers={"Idempotency-Key": "secret-bundle-delete-preflight"},
    ).json()
    deletion = client.post(
        f"/api/v1/goals/{goal_id}/delete",
        headers={"Idempotency-Key": "secret-bundle-delete"},
        json={
            "operation_id": preflight["operation_id"],
            "snapshot_id": preflight["snapshot_id"],
        },
    )
    wait_for_job(client, deletion)

    with engine.connect() as connection:
        tables = connection.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ).scalars()
        residues: list[tuple[str, str]] = []
        for table in tables:
            columns = connection.execute(
                text(f'PRAGMA table_info("{table}")')
            ).mappings()
            for column in columns:
                if column["type"].upper() not in {"TEXT", "BLOB"}:
                    continue
                count = connection.scalar(
                    text(
                        f'SELECT count(*) FROM "{table}" '
                        f'WHERE instr(CAST("{column["name"]}" AS TEXT), :sentinel) > 0'
                    ),
                    {"sentinel": sentinel},
                )
                if count:
                    residues.append((table, column["name"]))
        assert residues == []
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM interview_bundles WHERE owner_id=:owner AND id=:id"
                ),
                {"owner": owner_id, "id": created.json()["id"]},
            )
            == 1
        )
