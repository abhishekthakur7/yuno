import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from yuno.modules.canonical.domain import (
    CanonicalGraphVersion,
    CanonicalVersionStatus,
    EditorialApproval,
    Topic,
    TopicIdentity,
)
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import Clock
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id


class FixedClock(Clock):
    instant = datetime(2026, 8, 12, 12, tzinfo=UTC)

    def now(self) -> datetime:
        return self.instant


def _goal(client: TestClient, uow_factory: UnitOfWorkFactory) -> str:
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        graph = new_id()
        timestamp = "2026-08-01T00:00:00.000000Z"
        uow.canonical.create_topic_identity(TopicIdentity("progress-topic", "progress-topic", timestamp, None))
        uow.canonical.create_version(CanonicalGraphVersion(graph, f"progress-{graph}", "v1", new_id(), CanonicalVersionStatus.PUBLISHED, owner.id, timestamp, timestamp, None))
        uow.canonical.add_topic(Topic(graph, "progress-topic", "Progress", "backend", ("fixture",), "senior", "implement", "essential", 0, 1))
        uow.canonical.record_approval(EditorialApproval(new_id(), graph, owner.id, "designated_editorial_approver", "test", timestamp))
        uow.commit()
    response = client.post(
        "/api/v1/goals",
        headers={"Idempotency-Key": "progress-goal"},
        json={"name": "Progress", "path": "learn", "subject": "backend", "target_level": "Senior", "target_capability": "implement", "graph_version_id": graph},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_progress_uses_injected_authoritative_clock_and_exposes_fixture_status(client: TestClient, uow_factory: UnitOfWorkFactory):
    client.app.state.clock = FixedClock()
    goal_id = _goal(client, uow_factory)
    response = client.get(f"/api/v1/goals/{goal_id}/progress", params={"now": "1999-01-01T00:00:00Z"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["effective_now"] == "2026-08-12T12:00:00.000000Z"
    assert body["rule_version"] == "fixture-v0"
    assert body["authoritative"] is False
    assert "completion" not in body
    details = client.get(f"/api/v1/goals/{goal_id}/learning-state-explanations").json()
    assert details["effective_now"] == body["effective_now"]
    assert details["input_hash"] == body["input_hash"]


def test_database_invalidates_memo_and_rejects_correction_branches(client: TestClient, engine: Engine, uow_factory: UnitOfWorkFactory):
    client.app.state.clock = FixedClock()
    goal_id = _goal(client, uow_factory)
    with engine.connect() as connection:
        owner_id = connection.execute(text("SELECT id FROM owners")).scalar_one()
    assert client.get(f"/api/v1/goals/{goal_id}/progress").status_code == 200
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM goal_progress_memos WHERE goal_id=:g"), {"g": goal_id}).scalar_one() == 1
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO learner_corrections(id,owner_id,goal_id,topic_stable_id,correction_type,value,reason,created_at) SELECT 'c1',:o,:g,t.stable_id,'correction','partial',NULL,:at FROM topics t JOIN goal_workspaces w ON w.graph_version_id=t.graph_version_id WHERE w.id=:g LIMIT 1"), {"o": owner_id, "g": goal_id, "at": "2026-08-01T00:00:00.000000Z"})
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM goal_progress_memos WHERE goal_id=:g"), {"g": goal_id}).scalar_one() == 0
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO learner_corrections(id,owner_id,goal_id,topic_stable_id,correction_type,value,reason,created_at,supersedes_correction_id) SELECT 'c2',:o,:g,topic_stable_id,'gap','new',NULL,:at,'c1' FROM learner_corrections WHERE id='c1'"), {"o": owner_id, "g": goal_id, "at": "2026-08-02T00:00:00.000000Z"})
    with engine.begin() as connection, pytest.raises(IntegrityError, match="active same-scope leaf"):
            connection.execute(text("INSERT INTO learner_corrections(id,owner_id,goal_id,topic_stable_id,correction_type,value,reason,created_at,supersedes_correction_id) SELECT 'c3',:o,:g,topic_stable_id,'gap','partial',NULL,:at,'c1' FROM learner_corrections WHERE id='c1'"), {"o": owner_id, "g": goal_id, "at": "2026-08-03T00:00:00.000000Z"})
    states = client.get(f"/api/v1/goals/{goal_id}/learning-state-explanations").json()["learning_states"]
    assert states[0]["classification"] == "new"
    with engine.begin() as connection:
        assert connection.execute(text("SELECT count(*) FROM learner_corrections WHERE goal_id=:g"), {"g": goal_id}).scalar_one() == 2
        connection.execute(text("UPDATE goal_progress_memos SET input_hash='stale' WHERE goal_id=:g"), {"g": goal_id})
    recovered = client.get(f"/api/v1/goals/{goal_id}/progress").json()
    assert recovered["input_hash"] != "stale"


def test_progress_display_is_presentation_only_no_data_loss(client: TestClient, engine: Engine, uow_factory: UnitOfWorkFactory):
    client.app.state.clock = FixedClock()
    goal_id = _goal(client, uow_factory)
    assert client.get(f"/api/v1/goals/{goal_id}/progress").status_code == 200
    with engine.connect() as connection:
        before = {
            table: connection.execute(text(f"SELECT * FROM {table} ORDER BY 1")).all()
            for table in ("evidence", "assessments", "goal_progress_memos")
        }
    assert client.get(f"/api/v1/goals/{goal_id}/progress", params={"progress_display": "simple"}).status_code == 200
    assert client.get(f"/api/v1/goals/{goal_id}/progress", params={"progress_display": "detailed"}).status_code == 200
    with engine.connect() as connection:
        after = {
            table: connection.execute(text(f"SELECT * FROM {table} ORDER BY 1")).all()
            for table in ("evidence", "assessments", "goal_progress_memos")
        }
    assert before == after


def test_memo_hits_within_fixture_day_and_invalidates_at_day_boundary(
    client: TestClient, engine: Engine, uow_factory: UnitOfWorkFactory
):
    clock = FixedClock()
    client.app.state.clock = clock
    goal_id = _goal(client, uow_factory)
    first = client.get(f"/api/v1/goals/{goal_id}/progress").json()
    with engine.connect() as connection:
        first_stored_at = connection.execute(
            text("SELECT computed_at FROM goal_progress_memos WHERE goal_id=:g"), {"g": goal_id}
        ).scalar_one()
    clock.instant = datetime(2026, 8, 12, 23, tzinfo=UTC)
    same_day = client.get(f"/api/v1/goals/{goal_id}/progress").json()
    assert same_day["input_hash"] == first["input_hash"]
    assert same_day["effective_now"] == "2026-08-12T23:00:00.000000Z"
    with engine.connect() as connection:
        assert connection.execute(text("SELECT computed_at FROM goal_progress_memos WHERE goal_id=:g"), {"g": goal_id}).scalar_one() == first_stored_at
    clock.instant = datetime(2026, 8, 13, 0, tzinfo=UTC)
    next_day = client.get(f"/api/v1/goals/{goal_id}/progress").json()
    assert next_day["input_hash"] != first["input_hash"]
    assert next_day["effective_now"] == "2026-08-13T00:00:00.000000Z"


def test_matching_hash_corrupt_memo_is_recomputed(
    client: TestClient, engine: Engine, uow_factory: UnitOfWorkFactory
):
    client.app.state.clock = FixedClock()
    goal_id = _goal(client, uow_factory)
    expected = client.get(f"/api/v1/goals/{goal_id}/progress").json()
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE goal_progress_memos SET explanation_json='{}' WHERE goal_id=:g"),
            {"g": goal_id},
        )
    recovered = client.get(f"/api/v1/goals/{goal_id}/progress").json()
    assert recovered == expected
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE goal_progress_memos SET coverage='partial' WHERE goal_id=:g"),
            {"g": goal_id},
        )
    recovered_metric = client.get(f"/api/v1/goals/{goal_id}/progress").json()
    assert recovered_metric == expected
    with engine.begin() as connection:
        raw = connection.execute(
            text("SELECT explanation_json FROM goal_progress_memos WHERE goal_id=:g"),
            {"g": goal_id},
        ).scalar_one()
        corrupted = raw.replace("Fixture-only derivation", "Corrupt but schema-valid definition", 1)
        connection.execute(
            text("UPDATE goal_progress_memos SET explanation_json=:value WHERE goal_id=:g"),
            {"g": goal_id, "value": corrupted},
        )
    recovered_payload = client.get(f"/api/v1/goals/{goal_id}/progress").json()
    assert recovered_payload == expected
    with engine.begin() as connection:
        raw = connection.execute(
            text("SELECT explanation_json FROM goal_progress_memos WHERE goal_id=:g"),
            {"g": goal_id},
        ).scalar_one()
        payload = json.loads(raw)
        payload["learning_states"] = []
        payload_without_digest = {key: value for key, value in payload.items() if key != "integrity_digest"}
        payload["integrity_digest"] = hash_payload(payload_without_digest)
        connection.execute(
            text("UPDATE goal_progress_memos SET explanation_json=:value WHERE goal_id=:g"),
            {"g": goal_id, "value": json.dumps(payload)},
        )
    recovered_topics = client.get(f"/api/v1/goals/{goal_id}/progress").json()
    assert recovered_topics == expected
    with engine.connect() as connection:
        assert connection.execute(text("SELECT coverage FROM goal_progress_memos WHERE goal_id=:g"), {"g": goal_id}).scalar_one() == expected["coverage"]["classification"]
