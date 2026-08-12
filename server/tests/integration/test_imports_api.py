from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.integration.test_learning_content_api import _seed
from tests.job_assertions import wait_for_job
from yuno.api.routes import imports as imports_routes
from yuno.shared.application.unit_of_work import UnitOfWorkFactory


def _create(client: TestClient, *, key: str = "create-notes") -> dict[str, object]:
    response = client.post(
        "/api/v1/imports",
        headers={"Idempotency-Key": key},
        json={
            "goal_id": None,
            "import_type": "markdown",
            "original_content": "# Transactions\n- Locks prevent duplicate writers",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_import_api_preserves_original_lists_parses_and_guards_statement_writes(
    client: TestClient,
) -> None:
    missing_key = client.post(
        "/api/v1/imports",
        json={"import_type": "plain_text", "original_content": "seed"},
    )
    assert missing_key.status_code == 400
    assert missing_key.json()["code"] == "malformed_request"

    created = _create(client)
    assert created["original_content"] == (
        "# Transactions\n- Locks prevent duplicate writers"
    )
    assert created["status"] == "selected"
    assert created["row_version"] == 1

    replay = _create(client)
    assert replay["id"] == created["id"]
    conflict = client.post(
        "/api/v1/imports",
        headers={"Idempotency-Key": "create-notes"},
        json={"import_type": "plain_text", "original_content": "different"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_key_reused"

    listed = client.get("/api/v1/imports")
    assert listed.status_code == 200
    assert [record["id"] for record in listed.json()] == [created["id"]]

    parsed = client.post(
        f"/api/v1/imports/{created['id']}/parse",
        headers={"Idempotency-Key": "parse-notes"},
    )
    assert parsed.status_code == 202, parsed.text
    assert parsed.json()["kind"] == "parse_import"
    wait_for_job(client, parsed)

    parsed_replay = client.post(
        f"/api/v1/imports/{created['id']}/parse",
        headers={"Idempotency-Key": "parse-notes"},
    )
    assert parsed_replay.status_code == 202
    assert parsed_replay.json()["job_id"] == parsed.json()["job_id"]
    assert parsed_replay.json()["deduplicated"] is True

    statements_response = client.get(
        f"/api/v1/imports/{created['id']}/statements"
    )
    assert statements_response.status_code == 200
    statements = statements_response.json()
    assert [statement["sequence"] for statement in statements] == [1, 2]
    assert all(statement["trust_state"] == "untrusted" for statement in statements)
    statement = statements[0]

    missing_match = client.patch(
        f"/api/v1/import-statements/{statement['id']}",
        headers={"Idempotency-Key": "correct-one"},
        json={"corrected_text": "Transactions are atomic."},
    )
    assert missing_match.status_code == 412

    corrected = client.patch(
        f"/api/v1/import-statements/{statement['id']}",
        headers={"Idempotency-Key": "correct-one", "If-Match": "1"},
        json={"corrected_text": "Transactions are atomic."},
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["row_version"] == 2
    assert corrected.json()["corrected_text"] == "Transactions are atomic."

    correction_replay = client.patch(
        f"/api/v1/import-statements/{statement['id']}",
        headers={"Idempotency-Key": "correct-one", "If-Match": "1"},
        json={"corrected_text": "Transactions are atomic."},
    )
    assert correction_replay.status_code == 200
    assert correction_replay.json() == corrected.json()

    stale = client.patch(
        f"/api/v1/import-statements/{statement['id']}",
        headers={"Idempotency-Key": "stale-correction", "If-Match": "1"},
        json={"corrected_text": "A stale overwrite."},
    )
    assert stale.status_code == 412
    assert stale.json()["code"] == "precondition_failed"

    verified = client.post(
        f"/api/v1/import-statements/{statement['id']}/verify",
        headers={"Idempotency-Key": "verify-one", "If-Match": "2"},
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["trust_state"] == "verified"
    assert verified.json()["row_version"] == 3


def test_failed_parse_preserves_original_and_can_retry(
    client: TestClient, monkeypatch
) -> None:
    created = _create(client, key="create-retry")
    real_parse = imports_routes.parse_import

    def fail_parse(*_args, **_kwargs):
        raise RuntimeError("fixture parser failure")

    monkeypatch.setattr(imports_routes, "parse_import", fail_parse)
    failed = client.post(
        f"/api/v1/imports/{created['id']}/parse",
        headers={"Idempotency-Key": "parse-fails"},
    )
    assert failed.status_code == 202
    wait_for_job(client, failed, "failed")
    after_failure = client.get(f"/api/v1/imports/{created['id']}").json()
    assert after_failure["status"] == "failed"
    assert after_failure["failure_code"] == "import_parse_failed"
    assert after_failure["original_content"] == created["original_content"]

    monkeypatch.setattr(imports_routes, "parse_import", real_parse)
    retried = client.post(
        f"/api/v1/imports/{created['id']}/parse",
        headers={"Idempotency-Key": "parse-retry"},
    )
    assert retried.status_code == 202
    wait_for_job(client, retried)
    assert client.get(f"/api/v1/imports/{created['id']}").json()["status"] == (
        "parsed-untrusted"
    )


def test_map_response_exposes_atomic_topic_imports_hash(
    client: TestClient, uow_factory: UnitOfWorkFactory, engine: Engine
) -> None:
    graph_id, topic_id, goal_id = _seed(uow_factory)
    created = client.post(
        "/api/v1/imports",
        headers={"Idempotency-Key": "create-mapped"},
        json={
            "goal_id": goal_id,
            "import_type": "plain_text",
            "original_content": "Use an atomic idempotency boundary.",
        },
    ).json()
    parsed = client.post(
        f"/api/v1/imports/{created['id']}/parse",
        headers={"Idempotency-Key": "parse-mapped"},
    )
    assert parsed.status_code == 202
    wait_for_job(client, parsed)
    statement = client.get(
        f"/api/v1/imports/{created['id']}/statements"
    ).json()[0]
    with engine.connect() as connection:
        before_side_effects = {
            table: connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
            for table in ("topics", "evidence", "learning_states")
        }

    mapped = client.post(
        f"/api/v1/import-statements/{statement['id']}/map",
        headers={"Idempotency-Key": "map-one", "If-Match": "1"},
        json={"goal_id": goal_id, "topic_id": topic_id},
    )
    assert mapped.status_code == 200, mapped.text
    body = mapped.json()
    assert body["statement"]["mapping_state"] == "mapped"
    assert body["statement"]["row_version"] == 2
    assert body["mapping"] == body["statement"]["mapping"]
    assert body["mapping"]["graph_version_id"] == graph_id
    assert body["topic_imports_hash"]["topic_id"] == topic_id
    assert body["topic_imports_hash"]["graph_version_id"] == graph_id
    assert len(body["topic_imports_hash"]["imports_hash"]) == 64
    with engine.connect() as connection:
        after_side_effects = {
            table: connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
            for table in ("topics", "evidence", "learning_states")
        }
    assert after_side_effects == before_side_effects

    replay = client.post(
        f"/api/v1/import-statements/{statement['id']}/map",
        headers={"Idempotency-Key": "map-one", "If-Match": "1"},
        json={"goal_id": goal_id, "topic_id": topic_id},
    )
    assert replay.status_code == 200
    assert replay.json() == body
