"""IDK-302 Practice API and persistence contracts.

All authored content in this module comes from the explicitly synthetic
``fixture-v0-non-production`` fixture.  Nothing here is a production scenario.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.integration.test_interview_api import _create_goal
from yuno.modules.evidence_evaluation.domain import (
    AssessmentState,
    DimensionOutcome,
    EvaluationDimensionResult,
    EvaluationRequest,
    EvaluationResult,
    Rubric,
    RubricDimension,
    RubricStatus,
)
from yuno.modules.interview.service import begin_evaluation, submit_answer
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.ids import new_id

FIXTURE = json.loads(
    (
        Path(__file__).parents[1]
        / "fixtures"
        / "interview"
        / "data"
        / "practice_fixture_v0.json"
    ).read_text()
)
assert FIXTURE["fixture_marker"] == "fixture-v0-non-production"


@dataclass
class FixtureV0EvaluationAdapter:
    """Deterministic test double; not a production evaluator or scenario."""

    calls: int = 0

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        self.calls += 1
        assert request.rubric_version == "fixture-v0"
        evaluation = FIXTURE["evaluation"]
        return EvaluationResult(
            state=AssessmentState.FEEDBACK_READY,
            dimensions=(
                EvaluationDimensionResult(
                    "fixture-reasoning",
                    DimensionOutcome.PASS,
                    "Fixture-v0 rationale for the named ordering assumption.",
                    (request.evidence_id,),
                ),
                EvaluationDimensionResult(
                    "fixture-trade-offs",
                    DimensionOutcome.TRADE_OFF,
                    "Fixture-v0 rationale for the named synthetic consequence.",
                    (request.evidence_id,),
                ),
            ),
            facts=tuple(evaluation["facts"]),
            trade_offs=tuple(evaluation["trade_offs"]),
            citations=("fixture-v0:synthetic",),
            ambiguities=(),
            feedback=evaluation["feedback"],
            cross_question_candidate=evaluation["cross_question_candidate"],
            revision_invitation="Revise the fixture-v0 ordering assumption.",
            warnings=(),
            limitation_labels=("fixture-v0-non-production",),
        )


class _FailingFixtureV0EvaluationAdapter:
    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        assert request.rubric_version == "fixture-v0"
        raise RuntimeError("fixture-v0 synthetic evaluation failure")


def _arrange_practice(
    client: TestClient,
    uow_factory: UnitOfWorkFactory,
    *,
    suffix: str,
) -> dict[str, str]:
    goal_id, topic_id = _create_goal(
        client, uow_factory, suffix=f"practice-fixture-v0-{suffix}"
    )
    bundle_fixture = FIXTURE["bundle"]
    bundle = client.post(
        "/api/v1/interview-bundles",
        headers={"Idempotency-Key": f"practice-fixture-v0-bundle-{suffix}"},
        json={
            "goal_id": goal_id,
            **bundle_fixture,
            "items": [
                {
                    "subject": "technical",
                    "topic_stable_id": topic_id,
                    "question": FIXTURE["question"],
                    "position": 0,
                    "is_optional": False,
                    "included": True,
                }
            ],
        },
    )
    assert bundle.status_code == 201, bundle.text
    bundle_payload = bundle.json()

    rubric_fixture = FIXTURE["rubric"]
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        timestamp = now_text(SystemClock())
        rubric = Rubric(
            new_id(),
            owner.id,
            rubric_fixture["task_context"],
            rubric_fixture["capability"],
            rubric_fixture["role"],
            rubric_fixture["level"],
            rubric_fixture["version"],
            RubricStatus.FIXTURE,
            rubric_fixture["provenance"],
            timestamp,
        )
        dimensions = tuple(
            RubricDimension(
                new_id(),
                rubric.id,
                value["stable_dimension_id"],
                value["name"],
                value["description"],
                value["ordinal"],
                value["evaluation_guidance"],
            )
            for value in rubric_fixture["dimensions"]
        )
        uow.evidence.add_rubric(rubric, dimensions)
        uow.commit()
    return {
        "goal_id": goal_id,
        "topic_id": topic_id,
        "bundle_id": bundle_payload["id"],
        "bundle_item_id": bundle_payload["items"][0]["id"],
        "rubric_id": rubric.id,
    }


def _create_run(client: TestClient, arranged: dict[str, str]):
    return client.post(
        "/api/v1/interview-runs",
        json={
            "goal_id": arranged["goal_id"],
            "bundle_id": arranged["bundle_id"],
            "bundle_item_id": arranged["bundle_item_id"],
            "rubric_id": arranged["rubric_id"],
            "rubric_version": "fixture-v0",
            "requested_capability": "implement",
            "hint": FIXTURE["hint"],
        },
    )


def _turns(run: dict, kind: str) -> list[dict]:
    return [turn for turn in run["turns"] if turn["kind"] == kind]


def _walk_keys(value: object):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def test_practice_feedback_and_adaptive_follow_up_exist_only_after_explicit_actions(
    client: TestClient,
    uow_factory: UnitOfWorkFactory,
) -> None:
    arranged = _arrange_practice(client, uow_factory, suffix="timing")
    created = _create_run(client, arranged)
    assert created.status_code == 201, created.text
    run = created.json()
    assert run["state"] == "ready"
    assert run["question"] == FIXTURE["question"]
    assert _turns(run, "hint") == []
    assert _turns(run, "answer") == []
    assert run["results"] == []

    untouched = client.get(f"/api/v1/interview-runs/{run['id']}")
    assert untouched.status_code == 200
    assert _turns(untouched.json(), "hint") == []
    hinted = client.post(f"/api/v1/interview-runs/{run['id']}/hints")
    assert hinted.status_code == 200, hinted.text
    assert [turn["body"] for turn in _turns(hinted.json(), "hint")] == [FIXTURE["hint"]]
    repeated_hint = client.post(f"/api/v1/interview-runs/{run['id']}/hints")
    assert repeated_hint.status_code == 200, repeated_hint.text
    assert len(_turns(repeated_hint.json(), "hint")) == 1
    assert repeated_hint.json()["results"] == []

    blank = client.post(
        f"/api/v1/interview-runs/{run['id']}/answers",
        headers={"Idempotency-Key": "practice-fixture-v0-blank"},
        json={"answer": " \n\t "},
    )
    assert blank.status_code == 422
    assert client.get(f"/api/v1/interview-runs/{run['id']}").json()["results"] == []

    adapter = FixtureV0EvaluationAdapter()
    client.app.state.evaluation_adapter = adapter
    submitted = client.post(
        f"/api/v1/interview-runs/{run['id']}/answers",
        headers={"Idempotency-Key": "practice-fixture-v0-first-answer"},
        json={"answer": "Fixture-v0 first answer."},
    )
    assert submitted.status_code == 202, submitted.text
    assert {"feedback", "facts", "trade_offs", "results"}.isdisjoint(
        set(_walk_keys(submitted.json()))
    )

    terminal = client.get(f"/api/v1/interview-runs/{run['id']}")
    assert terminal.status_code == 200, terminal.text
    payload = terminal.json()
    assert payload["state"] == "feedback-ready"
    assert len(payload["results"]) == 1
    result = payload["results"][0]
    assert result["facts"] == FIXTURE["evaluation"]["facts"]
    assert result["trade_offs"] == FIXTURE["evaluation"]["trade_offs"]
    assert result["facts"] != result["trade_offs"]
    assert {item["dimension_id"] for item in result["dimensions"]} == {
        "fixture-reasoning",
        "fixture-trade-offs",
    }
    assert {item["name"] for item in result["dimensions"]} == {
        "Fixture reasoning",
        "Fixture trade-offs",
    }
    assert [turn["body"] for turn in _turns(payload, "follow-up")] == [
        FIXTURE["evaluation"]["cross_question_candidate"]
    ]
    assert "ordering assumption" in _turns(payload, "follow-up")[0]["body"]
    assert adapter.calls == 1


def test_practice_repair_appends_byte_exact_answers_and_turns_are_db_immutable(
    client: TestClient,
    uow_factory: UnitOfWorkFactory,
    engine,
) -> None:
    arranged = _arrange_practice(client, uow_factory, suffix="append-only")
    created = _create_run(client, arranged)
    assert created.status_code == 201, created.text
    run_id = created.json()["id"]
    client.app.state.evaluation_adapter = FixtureV0EvaluationAdapter()
    first_text = "\n  Fixture-v0 first answer with exact bytes.\t"
    second_text = "  Fixture-v0 repaired answer remains distinct.\n"

    first = client.post(
        f"/api/v1/interview-runs/{run_id}/answers",
        headers={"Idempotency-Key": "practice-fixture-v0-append-first"},
        json={"answer": first_text},
    )
    assert first.status_code == 202, first.text
    after_first = client.get(f"/api/v1/interview-runs/{run_id}").json()
    first_turn = _turns(after_first, "answer")[0]
    assert first_turn["body"] == first_text

    second = client.post(
        f"/api/v1/interview-runs/{run_id}/answers",
        headers={"Idempotency-Key": "practice-fixture-v0-append-second"},
        json={"answer": second_text},
    )
    assert second.status_code == 202, second.text
    after_second = client.get(f"/api/v1/interview-runs/{run_id}").json()
    answers = _turns(after_second, "answer")
    assert len(answers) == 2
    assert answers[0]["id"] == first_turn["id"]
    assert answers[0]["body"] == first_text
    assert answers[1]["id"] != answers[0]["id"]
    assert answers[1]["body"] == second_text
    assert len(after_second["results"]) == 2
    assert {value["answer_turn_id"] for value in after_second["results"]} == {
        answers[0]["id"],
        answers[1]["id"],
    }

    with engine.begin() as connection:
        with pytest.raises(Exception, match="append-only|immutable"):
            connection.execute(
                text("UPDATE interview_turns SET body='rewritten' WHERE id=:id"),
                {"id": answers[0]["id"]},
            )
        with pytest.raises(Exception, match="append-only|immutable"):
            connection.execute(
                text("DELETE FROM interview_turns WHERE id=:id"),
                {"id": answers[1]["id"]},
            )


def test_practice_cancel_and_failed_retry_preserve_the_existing_attempt(
    client: TestClient,
    uow_factory: UnitOfWorkFactory,
) -> None:
    arranged = _arrange_practice(client, uow_factory, suffix="recovery")

    cancel_created = _create_run(client, arranged)
    assert cancel_created.status_code == 201, cancel_created.text
    cancel_run_id = cancel_created.json()["id"]
    cancel_body = "\n Fixture-v0 attempt survives cancellation.\t"
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        attempt = submit_answer(
            uow,
            owner.id,
            cancel_run_id,
            cancel_body,
            "fixture-v0-evidence-cancel",
            "fixture-v0-job-cancel",
        )
        begin_evaluation(uow, owner.id, cancel_run_id, attempt.id)
        uow.commit()

    while_evaluating = client.get(f"/api/v1/interview-runs/{cancel_run_id}")
    assert while_evaluating.status_code == 200
    assert while_evaluating.json()["state"] == "evaluating"
    assert while_evaluating.json()["results"] == []
    cancelled = client.post(f"/api/v1/interview-runs/{cancel_run_id}/cancel-evaluation")
    assert cancelled.status_code == 200, cancelled.text
    cancelled_payload = cancelled.json()
    assert cancelled_payload["state"] == "failed-recoverable"
    assert cancelled_payload["failure_reference"] == "evaluation_cancelled"
    assert cancelled_payload["retryable"] is True
    assert [
        (turn["id"], turn["body"]) for turn in _turns(cancelled_payload, "answer")
    ] == [(attempt.id, cancel_body)]

    failed_created = _create_run(client, arranged)
    assert failed_created.status_code == 201, failed_created.text
    failed_run_id = failed_created.json()["id"]
    failed_body = "  Fixture-v0 failed attempt is retried in place.\n"
    client.app.state.evaluation_adapter = _FailingFixtureV0EvaluationAdapter()
    failed_job = client.post(
        f"/api/v1/interview-runs/{failed_run_id}/answers",
        headers={"Idempotency-Key": "practice-fixture-v0-failed-answer"},
        json={"answer": failed_body},
    )
    assert failed_job.status_code == 202, failed_job.text
    assert failed_job.json()["status"] == "failed"
    failed_run = client.get(f"/api/v1/interview-runs/{failed_run_id}").json()
    failed_attempt = _turns(failed_run, "answer")[0]
    assert failed_run["state"] == "failed-recoverable"
    assert failed_run["retryable"] is True
    assert failed_run["results"] == []
    assert failed_attempt["body"] == failed_body

    client.app.state.evaluation_adapter = FixtureV0EvaluationAdapter()
    retried = client.post(
        f"/api/v1/interview-runs/{failed_run_id}/retry-evaluation",
        headers={"Idempotency-Key": "practice-fixture-v0-retry"},
    )
    assert retried.status_code == 202, retried.text
    assert retried.json()["status"] == "succeeded"
    recovered = client.get(f"/api/v1/interview-runs/{failed_run_id}").json()
    assert recovered["state"] == "feedback-ready"
    assert [(turn["id"], turn["body"]) for turn in _turns(recovered, "answer")] == [
        (failed_attempt["id"], failed_body)
    ]
    assert len(recovered["results"]) == 1
    assert recovered["results"][0]["answer_turn_id"] == failed_attempt["id"]
