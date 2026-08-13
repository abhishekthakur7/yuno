from __future__ import annotations

import pytest
from sqlalchemy import exc as sa_exc
from sqlalchemy import text

from tests.integration.test_interview_api import _create_goal
from tests.job_assertions import wait_for_job
from tests.provider_fakes import accept_provider_disclosure, install_provider_fake
from yuno.modules.interview.service import (
    cancel_mock_generation,
    submit_mock_answer,
)
from yuno.shared.domain.hashing import hash_payload


class FakeMockAdapter:
    def next_question(self, _run) -> str:
        return "Fixture next question?"


def _arrange(client, uow_factory, suffix: str) -> dict[str, str]:
    goal_id, topic_id = _create_goal(client, uow_factory, suffix=f"mock-{suffix}")
    bundle = client.post(
        "/api/v1/interview-bundles",
        headers={"Idempotency-Key": f"mock-bundle-{suffix}"},
        json={
            "goal_id": goal_id,
            "name": "Synthetic Mock fixture",
            "generic_role": "Synthetic role",
            "target_level": "Senior",
            "origin": "fixture-v0-non-production",
            "items": [
                {
                    "subject": "technical",
                    "topic_stable_id": topic_id,
                    "question": "Synthetic first Mock question?",
                    "position": 0,
                    "is_optional": False,
                    "included": True,
                }
            ],
        },
    )
    assert bundle.status_code == 201, bundle.text
    payload = bundle.json()
    return {
        "goal_id": goal_id,
        "bundle_id": payload["id"],
        "bundle_item_id": payload["items"][0]["id"],
    }


def _create(client, arranged):
    response = client.post(
        "/api/v1/interview-runs",
        json={"mode": "Mock", **arranged},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_mock_pause_resume_is_byte_exact_and_feedback_is_withheld(client, uow_factory):
    run = _create(client, _arrange(client, uow_factory, "exact"))
    exact = "\n  leading\ninternal\tspacing  \n"
    paused = client.post(
        f"/api/v1/interview-runs/{run['id']}/pause", json={"draft": exact}
    )
    assert paused.status_code == 200, paused.text
    assert paused.json()["state"] == "paused"
    assert paused.json()["draft"] == exact
    before = paused.json()["turns"]

    hinted = client.post(f"/api/v1/interview-runs/{run['id']}/hints")
    assert hinted.status_code == 409
    assert hinted.json()["code"] == "mock_feedback_withheld"
    report = client.get(f"/api/v1/interview-runs/{run['id']}/report")
    assert report.status_code == 409
    assert report.json()["code"] == "mock_feedback_withheld"

    resumed = client.post(f"/api/v1/interview-runs/{run['id']}/resume")
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["state"] == "answering"
    assert resumed.json()["draft"] == exact
    assert resumed.json()["turns"] == before


def test_mock_complete_rejects_blank_and_is_idempotent_after_enqueue_failure(
    client, uow_factory
):
    run = _create(client, _arrange(client, uow_factory, "complete"))
    evidence_before = client.get(f"/api/v1/goals/{run['goal_id']}/evidence").json()
    blank = client.post(
        f"/api/v1/interview-runs/{run['id']}/complete",
        headers={"Idempotency-Key": "mock-blank"},
        json={"draft": " \n\t "},
    )
    assert blank.status_code == 409
    assert len(client.get(f"/api/v1/interview-runs/{run['id']}").json()["turns"]) == 1
    assert (
        client.get(f"/api/v1/goals/{run['goal_id']}/evidence").json() == evidence_before
    )

    install_provider_fake(client, FakeMockAdapter())
    exact = "  Complete answer.\n"
    first = client.post(
        f"/api/v1/interview-runs/{run['id']}/complete",
        headers={"Idempotency-Key": "mock-complete-once"},
        json={"draft": exact},
    )
    assert first.status_code == 202, first.text
    wait_for_job(client, first, "failed")
    failed = client.get(f"/api/v1/interview-runs/{run['id']}").json()
    assert failed["state"] == "failed-recoverable"
    assert failed["draft"] == exact
    answers = [turn for turn in failed["turns"] if turn["kind"] == "answer"]
    assert [turn["body"] for turn in answers] == [exact]

    repeated = client.post(
        f"/api/v1/interview-runs/{run['id']}/complete",
        headers={"Idempotency-Key": "mock-complete-once"},
        json={"draft": exact},
    )
    assert repeated.status_code == 202
    assert repeated.json()["job_id"] == first.json()["job_id"]
    after = client.get(f"/api/v1/interview-runs/{run['id']}").json()
    assert after["turns"] == failed["turns"]
    conflicting_replay = client.post(
        f"/api/v1/interview-runs/{run['id']}/complete",
        headers={"Idempotency-Key": "mock-complete-once"},
        json={"draft": f"{exact}changed"},
    )
    assert conflicting_replay.status_code == 409
    assert conflicting_replay.json()["code"] == "idempotency_key_reused"

    retried = client.post(
        f"/api/v1/interview-runs/{run['id']}/retry-evaluation",
        headers={"Idempotency-Key": "mock-final-retry"},
    )
    assert retried.status_code == 202
    wait_for_job(client, retried, "failed")
    recovered_failure = client.get(f"/api/v1/interview-runs/{run['id']}").json()
    assert recovered_failure["state"] == "failed-recoverable"
    assert recovered_failure["turns"] == failed["turns"]
    repeated_retry = client.post(
        f"/api/v1/interview-runs/{run['id']}/retry-evaluation",
        headers={"Idempotency-Key": "mock-final-retry"},
    )
    assert repeated_retry.status_code == 202
    assert repeated_retry.json()["job_id"] == retried.json()["job_id"]
    after_retry_replay = client.get(f"/api/v1/interview-runs/{run['id']}").json()
    assert after_retry_replay["active_job_id"] == recovered_failure["active_job_id"]
    assert after_retry_replay["turns"] == failed["turns"]


def test_mock_next_turn_cancel_preserves_transcript_and_db_rejects_hint(
    client, uow_factory, engine
):
    run = _create(client, _arrange(client, uow_factory, "cancel"))
    exact = "  Submitted Mock turn.\n"
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        submitted = submit_mock_answer(uow, owner.id, run["id"], exact, "mock-next-job")
        before = tuple(
            (turn.id, turn.kind.value, turn.body) for turn in submitted.turns
        )
        cancelled = cancel_mock_generation(uow, owner.id, run["id"])
        after = tuple((turn.id, turn.kind.value, turn.body) for turn in cancelled.turns)
        assert after == before
        uow.commit()

    with engine.begin() as connection:
        owner_id = connection.execute(
            text("SELECT owner_id FROM interview_runs WHERE id=:id"), {"id": run["id"]}
        ).scalar_one()
        try:
            connection.execute(
                text("""
                INSERT INTO interview_turns
                  (id, owner_id, run_id, turn_number, kind, body_hash, created_at)
                VALUES ('illegal-hint', :owner, :run, 99, 'hint', :body_hash, 'now')
            """),
                {
                    "owner": owner_id,
                    "run": run["id"],
                    "body_hash": hash_payload("forbidden"),
                },
            )
        except sa_exc.IntegrityError as exc:
            assert "mock_feedback_withheld" in str(exc)
        else:
            raise AssertionError("database accepted a nonterminal Mock hint")


def test_mock_adaptive_turn_and_unchanged_completion_guard(client, uow_factory):
    run = _create(client, _arrange(client, uow_factory, "adaptive"))
    install_provider_fake(client, FakeMockAdapter())
    answer = "  First adaptive answer.\n"
    generated = client.post(
        f"/api/v1/interview-runs/{run['id']}/answers",
        headers={"Idempotency-Key": "mock-adaptive-answer"},
        json={"answer": answer},
    )
    assert generated.status_code == 202, generated.text
    wait_for_job(client, generated, "succeeded")
    after = client.get(f"/api/v1/interview-runs/{run['id']}").json()
    assert after["state"] == "answering"
    assert after["question"] == "Fixture next question?"
    assert [(turn["kind"], turn["body"]) for turn in after["turns"]] == [
        ("question", "Synthetic first Mock question?"),
        ("answer", answer),
        ("follow-up", "Fixture next question?"),
    ]

    unchanged = client.post(
        f"/api/v1/interview-runs/{run['id']}/complete",
        headers={"Idempotency-Key": "mock-unchanged-complete"},
        json={"draft": answer},
    )
    assert unchanged.status_code == 409
    assert (
        client.get(f"/api/v1/interview-runs/{run['id']}").json()["turns"]
        == after["turns"]
    )


@pytest.fixture(autouse=True)
def accepted_provider_disclosure(client):
    accept_provider_disclosure(client)
