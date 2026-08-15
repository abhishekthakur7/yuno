from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.integration.test_evidence_evaluation import FakeEvaluationAdapter
from tests.integration.test_learning_content_api import _seed
from tests.job_assertions import wait_for_job
from tests.provider_fakes import accept_provider_disclosure, install_provider_fake
from yuno.modules.evidence_evaluation.domain import (
    EvaluationResult,
    Rubric,
    RubricDimension,
    RubricStatus,
)
from yuno.modules.hands_on.domain import HandsOnWork
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.ids import new_id


class HandsOnEvaluationAdapter(FakeEvaluationAdapter):
    def evaluate(self, request):
        result = super().evaluate(request)
        return EvaluationResult(
            **{
                **result.__dict__,
                "cross_question_candidate": "Which ordering assumption in this artifact breaks under concurrent retries?",
                "limitation_labels": (
                    f"Static review of {request.task_ref} cannot compile or execute this revision.",
                ),
            }
        )


def _arrange(uow_factory):
    _graph, topic_id, goal_id = _seed(uow_factory)
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        rubric = Rubric(
            new_id(),
            owner.id,
            "hands-on",
            "implement",
            None,
            "Senior",
            "fixture-hands-on-v1",
            RubricStatus.FIXTURE,
            "IDK-405 fixture pending IDK-009",
            now_text(SystemClock()),
        )
        uow.evidence.add_rubric(
            rubric,
            (
                RubricDimension(
                    new_id(),
                    rubric.id,
                    "reasoning",
                    "Reasoning",
                    "Reasoning is explicit.",
                    1,
                    "Review stated assumptions.",
                ),
                RubricDimension(
                    new_id(),
                    rubric.id,
                    "trade-offs",
                    "Trade-offs",
                    "Trade-offs are explicit.",
                    2,
                    "Review consequences.",
                ),
            ),
        )
        uow.commit()
    return topic_id, goal_id


def test_submit_is_idempotent_and_full_revision_chain_is_queryable(
    client, uow_factory, engine
):
    topic_id, goal_id = _arrange(uow_factory)
    install_provider_fake(client, HandsOnEvaluationAdapter())
    accept_provider_disclosure(client)
    url = f"/api/v1/goals/{goal_id}/topics/{topic_id}/hands-on/submit"
    initial_evidence = client.get(f"/api/v1/goals/{goal_id}/evidence").json()
    submitted = client.post(
        url,
        headers={"Idempotency-Key": "hands-on-1"},
        json={"artifact": "Use a unique key and commit the result atomically."},
    )
    assert submitted.status_code == 202, submitted.text
    replay = client.post(
        url,
        headers={"Idempotency-Key": "hands-on-1"},
        json={"artifact": "Use a unique key and commit the result atomically."},
    )
    assert replay.status_code == 202
    assert replay.json()["job_id"] == submitted.json()["job_id"]
    conflict = client.post(
        url,
        headers={"Idempotency-Key": "hands-on-1"},
        json={"artifact": "Different revision"},
    )
    assert conflict.status_code == 409
    assert wait_for_job(client, submitted.json()["job_id"])["status"] == "succeeded"
    lifecycle = client.get(url.removesuffix("/submit")).json()
    assert lifecycle["scenario"]["status"] == "fixture"
    assert (
        len(lifecycle["artifacts"])
        == len(lifecycle["reviews"])
        == len(lifecycle["cross_questions"])
        == 1
    )
    assert lifecycle["reviews"][0]["review_mode"] == "static"
    assert lifecycle["reviews"][0]["limitation"].strip()
    evidence = client.get(f"/api/v1/goals/{goal_id}/evidence").json()
    assert len(evidence) == len(initial_evidence) + 1
    assert lifecycle["artifacts"][0]["evidence_id"] == evidence[-1]["id"]
    question = lifecycle["cross_questions"][0]
    revised = client.post(
        url,
        headers={"Idempotency-Key": "hands-on-2"},
        json={
            "artifact": "Use a unique key; concurrent retries converge on the committed row.",
            "cross_question_response": {
                "question_id": question["id"],
                "response": "The assumption breaks if uniqueness is checked outside the transaction.",
            },
        },
    )
    assert revised.status_code == 202, revised.text
    assert wait_for_job(client, revised.json()["job_id"])["status"] == "succeeded"
    chain = client.get(url.removesuffix("/submit")).json()
    assert [item["revision_number"] for item in chain["artifacts"]] == [1, 2]
    assert chain["artifacts"][1]["response_to_question_id"] == question["id"]

    preflight = client.post(
        f"/api/v1/goals/{goal_id}/delete-preflight",
        headers={"Idempotency-Key": "hands-on-delete-preflight"},
    ).json()
    deletion = client.post(
        f"/api/v1/goals/{goal_id}/delete",
        headers={"Idempotency-Key": "hands-on-delete"},
        json={
            "operation_id": preflight["operation_id"],
            "snapshot_id": preflight["snapshot_id"],
        },
    )
    assert wait_for_job(client, deletion)["status"] == "succeeded"
    goal_body_tables = (
        "evidence_summary_bodies",
        "evidence_payloads",
        "assessment_bodies",
        "assessment_dimension_result_bodies",
        "hands_on_work_bodies",
        "hands_on_artifact_bodies",
        "hands_on_review_bodies",
        "hands_on_cross_question_bodies",
    )
    with engine.connect() as connection:
        for table in goal_body_tables:
            assert (
                connection.scalar(
                    text(f"SELECT count(*) FROM {table} WHERE goal_id=:goal_id"),
                    {"goal_id": goal_id},
                )
                == 0
            )
        assert (
            connection.scalar(
                text("SELECT count(*) FROM hands_on_artifacts WHERE goal_id=:goal_id"),
                {"goal_id": goal_id},
            )
            == 2
        )
        assert (
            connection.scalar(
                text("SELECT count(*) FROM assessments WHERE goal_id=:goal_id"),
                {"goal_id": goal_id},
            )
            == 2
        )


def test_submit_without_disclosure_does_not_create_artifact_or_evidence(
    client, uow_factory
):
    topic_id, goal_id = _arrange(uow_factory)
    initial_evidence = client.get(f"/api/v1/goals/{goal_id}/evidence").json()
    lifecycle_url = f"/api/v1/goals/{goal_id}/topics/{topic_id}/hands-on"

    response = client.post(
        f"{lifecycle_url}/submit",
        headers={"Idempotency-Key": "hands-on-without-disclosure"},
        json={"artifact": "This must remain a draft until disclosure is accepted."},
    )

    assert response.status_code == 412
    assert client.get(lifecycle_url).json()["artifacts"] == []
    assert client.get(f"/api/v1/goals/{goal_id}/evidence").json() == initial_evidence


def test_submit_rejects_combined_artifact_and_response_over_byte_limit_atomically(
    client, uow_factory, engine
):
    topic_id, goal_id = _arrange(uow_factory)
    accept_provider_disclosure(client)
    response = client.post(
        f"/api/v1/goals/{goal_id}/topics/{topic_id}/hands-on/submit",
        headers={"Idempotency-Key": "hands-on-combined-limit"},
        json={
            "artifact": "a" * (10 * 1024 * 1024),
            "cross_question_response": {
                "question_id": new_id(),
                "response": "b",
            },
        },
    )
    assert response.status_code == 413
    assert response.json()["code"] == "evidence-too-large"
    with engine.connect() as connection:
        for table in (
            "hands_on_work",
            "hands_on_artifacts",
            "evidence",
            "evidence_payloads",
        ):
            assert connection.scalar(text(f"SELECT count(*) FROM {table}")) == 0


def test_submit_job_reservation_failure_rolls_back_domain_writes(
    client, uow_factory, monkeypatch
):
    topic_id, goal_id = _arrange(uow_factory)
    install_provider_fake(client, HandsOnEvaluationAdapter())
    accept_provider_disclosure(client)
    lifecycle_url = f"/api/v1/goals/{goal_id}/topics/{topic_id}/hands-on"
    body = {"artifact": "Persist the immutable revision before durable dispatch."}
    original_reserve = client.app.state.dispatcher.reserve

    def fail_reserve(_uow, _request):
        raise RuntimeError("simulated reservation failure")

    monkeypatch.setattr(client.app.state.dispatcher, "reserve", fail_reserve)
    with pytest.raises(RuntimeError, match="simulated reservation failure"):
        client.post(
            f"{lifecycle_url}/submit",
            headers={"Idempotency-Key": "recover-submit"},
            json=body,
        )
    assert client.get(lifecycle_url).json()["artifacts"] == []
    assert client.get(f"/api/v1/goals/{goal_id}/evidence").json() == []
    monkeypatch.setattr(client.app.state.dispatcher, "reserve", original_reserve)

    recovered = client.post(
        f"{lifecycle_url}/submit",
        headers={"Idempotency-Key": "recover-submit"},
        json=body,
    )
    assert recovered.status_code == 202, recovered.text
    assert wait_for_job(client, recovered.json()["job_id"])["status"] == "succeeded"
    lifecycle = client.get(lifecycle_url).json()
    evidence = client.get(f"/api/v1/goals/{goal_id}/evidence").json()
    assert len(lifecycle["artifacts"]) == 1
    assert len(evidence) == 1


def test_static_limitation_and_artifact_immutability_are_database_enforced(engine):
    with engine.connect() as connection:
        triggers = (
            connection.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='hands_on_artifacts'"
                )
            )
            .scalars()
            .all()
        )
    assert len(triggers) == 2
    assert any("update" in name for name in triggers)
    assert any("delete" in name for name in triggers)
    with engine.connect() as connection:
        header_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(hands_on_artifacts)"))
        }
        body_columns = {
            row[1]
            for row in connection.execute(
                text("PRAGMA table_info(hands_on_artifact_bodies)")
            )
        }
    assert "content" not in header_columns
    assert "cross_question_response" not in header_columns
    assert body_columns == {
        "artifact_id",
        "owner_id",
        "goal_id",
        "cross_question_response",
    }


def test_scenario_status_check_admits_approved_and_scenario_id_is_a_nullable_header_column(
    client, uow_factory, engine
):
    """IDK-503 findings B10/B12: the CHECK on `hands_on_work.scenario_status`
    is widened from `IN ('fixture')` to `IN ('fixture','approved')`, and a
    nullable `scenario_id` header column is added. `'approved'` is a naming
    choice this migration makes -- IDK-009 never names a `scenario_status`
    field and supplies no literal for it -- not a value the decision
    specifies.
    """
    topic_id, goal_id = _arrange(uow_factory)
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        owner_id = owner.id

    with engine.connect() as connection:
        columns = {
            row[1]: row
            for row in connection.execute(text("PRAGMA table_info(hands_on_work)"))
        }
    assert "scenario_id" in columns
    assert columns["scenario_id"][3] == 0, "scenario_id must be nullable (notnull=0)"

    with engine.connect() as connection:
        triggers = set(
            connection.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='hands_on_work'"
                )
            )
            .scalars()
            .all()
        )
    assert triggers == {
        "hands_on_work_immutable_update",
        "hands_on_work_immutable_delete",
    }

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO hands_on_work "
                "(id, owner_id, goal_id, topic_stable_id, scenario_status, scenario_id, created_at, body_hash) "
                "VALUES (:id, :owner_id, :goal_id, :topic_id, 'approved', "
                "'test-scenario-id-not-real-content', '2026-08-15T00:00:00Z', 'hash-approved-check')"
            ),
            {
                "id": new_id(),
                "owner_id": owner_id,
                "goal_id": goal_id,
                "topic_id": topic_id,
            },
        )

    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).fetchall() == []

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO hands_on_work "
                "(id, owner_id, goal_id, topic_stable_id, scenario_status, scenario_id, created_at, body_hash) "
                "VALUES (:id, :owner_id, :goal_id, :topic_id, 'bogus', NULL, "
                "'2026-08-15T00:00:01Z', 'hash-bogus-check')"
            ),
            {
                "id": new_id(),
                "owner_id": owner_id,
                "goal_id": goal_id,
                "topic_id": topic_id,
            },
        )


def test_approved_scenario_status_and_scenario_id_round_trip_through_repository(
    client,
    uow_factory,
):
    """A work row persisted with `scenario_status='approved'` and a
    non-null `scenario_id` reads back correctly through
    `SqlAlchemyHandsOnRepository`. The scenario_id used here is an
    obviously synthetic identifier, not one of IDK-009's twelve approved
    scenario ids -- shipping one of those would imply approved content
    exists, which is out of scope for this schema-shape change.
    """
    topic_id, goal_id = _arrange(uow_factory)
    timestamp = now_text(SystemClock())
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        work = HandsOnWork(
            new_id(),
            owner.id,
            goal_id,
            topic_id,
            "Round-trip test scenario title",
            "Round-trip test scenario prompt.",
            "Software Engineer",
            "Senior",
            ("State assumptions and trade-offs explicitly.",),
            "approved",
            "schema-shape-round-trip-not-a-real-scenario-id",
            "fixture-pending-idk-009",
            timestamp,
        )
        uow.hands_on.add_work(work)
        uow.commit()

    with uow_factory() as uow:
        read_back = uow.hands_on.get_work(owner.id, goal_id, topic_id)

    assert read_back is not None
    assert read_back.scenario_status == "approved"
    assert read_back.scenario_id == "schema-shape-round-trip-not-a-real-scenario-id"
    assert read_back.scenario_title == "Round-trip test scenario title"
