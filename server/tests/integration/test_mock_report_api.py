from __future__ import annotations

import json
from pathlib import Path

from tests.integration.test_mock_api import _arrange
from tests.job_assertions import wait_for_job
from yuno.modules.evidence_evaluation.domain import (
    AssessmentState,
    DimensionOutcome,
    EvaluationDimensionResult,
    EvaluationResult,
    Rubric,
    RubricDimension,
    RubricStatus,
)
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.ids import new_id

FIXTURE = json.loads(
    (
        Path(__file__).parents[1]
        / "fixtures"
        / "interview"
        / "data"
        / "mock_report_fixture_v0.json"
    ).read_text()
)
assert FIXTURE["fixture_marker"] == "fixture-v0-non-production"


class ControlledTranscriptEvaluationAdapter:
    def __init__(self, uow_factory, exact_content: str) -> None:
        self.uow_factory = uow_factory
        self.exact_content = exact_content

    def evaluate(self, request):
        with self.uow_factory() as uow:
            evidence = uow.evidence.get_evidence_by_id(
                uow.owners.get_local_owner().id, request.evidence_id
            )
            assert evidence is not None
            payload = uow.evidence.get_payload(
                evidence.owner_id, evidence.goal_id, evidence.id
            )
            assert payload is not None
        exact = payload.content == self.exact_content
        assessment = FIXTURE["assessment"]
        return EvaluationResult(
            state=(
                AssessmentState.FEEDBACK_READY
                if exact
                else AssessmentState.AMBIGUITY_UNRESOLVED
            ),
            dimensions=(
                EvaluationDimensionResult(
                    "reasoning",
                    DimensionOutcome.PASS
                    if exact
                    else DimensionOutcome.AMBIGUITY_UNRESOLVED,
                    "Exact controlled fixture shape."
                    if exact
                    else "Edited transcript follows the ordinary evaluator path.",
                    (request.evidence_id,),
                ),
            ),
            facts=tuple(assessment["facts"]) if exact else (),
            trade_offs=tuple(assessment["trade_offs"]) if exact else (),
            citations=(),
            ambiguities=() if exact else ("The edited claim requires review.",),
            feedback=(
                assessment["feedback"]
                if exact
                else "Edited transcript evaluated without fixture-equivalent scoring."
            ),
            cross_question_candidate=None,
            revision_invitation=assessment["next_action"],
            warnings=(),
            limitation_labels=("fixture-v0-non-production",),
        )


def _seed_rubric(uow_factory):
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        timestamp = now_text(SystemClock())
        rubric = Rubric(
            new_id(),
            owner.id,
            "mock-report-fixture-v0",
            "implement",
            "synthetic-role",
            "senior",
            "fixture-v0",
            RubricStatus.FIXTURE,
            "fixture-v0-non-production",
            timestamp,
        )
        uow.evidence.add_rubric(
            rubric,
            (
                RubricDimension(
                    new_id(),
                    rubric.id,
                    "reasoning",
                    "Reasoning",
                    "Synthetic controlled regression dimension.",
                    1,
                    "Accept only the controlled fixture shape as exact.",
                ),
            ),
        )
        uow.commit()
    return rubric


def _create_run(client, arranged, rubric):
    response = client.post(
        "/api/v1/interview-runs",
        json={
            "mode": "Mock",
            **arranged,
            "rubric_id": rubric.id,
            "rubric_version": rubric.version,
            "requested_capability": "implement",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _complete(client, run_id: str, answer: str, key: str):
    response = client.post(
        f"/api/v1/interview-runs/{run_id}/complete",
        headers={"Idempotency-Key": key},
        json={"draft": answer},
    )
    assert response.status_code == 202, response.text
    wait_for_job(client, response)
    report = client.get(f"/api/v1/interview-runs/{run_id}/report")
    assert report.status_code == 200, report.text
    return report.json()


def test_terminal_report_uses_immutable_assessment_and_edited_transcript_is_not_fixture_equivalent(
    client, uow_factory
):
    rubric = _seed_rubric(uow_factory)
    arranged = _arrange(client, uow_factory, "report-exact")
    exact_run = _create_run(client, arranged, rubric)
    answer = FIXTURE["answer"]
    exact_content = json.dumps(
        [
            {"kind": "question", "body": exact_run["question"]},
            {"kind": "answer", "body": answer},
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    client.app.state.evaluation_adapter = ControlledTranscriptEvaluationAdapter(
        uow_factory, exact_content
    )

    exact = _complete(client, exact_run["id"], answer, "mock-report-exact")
    expected = FIXTURE["assessment"]
    assert exact["state"] == "completed"
    assert exact["assessment"]["feedback"] == expected["feedback"]
    assert exact["assessment"]["revision_invitation"] == expected["next_action"]
    assert exact["assessment"]["assumptions"] == expected["assumptions"]
    assert exact["assessment"]["facts"] == expected["facts"]
    assert exact["assessment"]["trade_offs"] == expected["trade_offs"]
    assert exact["assessment"]["provenance_refs"] == expected["provenance_refs"]
    assert exact["assessment"]["run_id"] == exact_run["id"]
    terminal_run = client.get(
        f"/api/v1/interview-runs/{exact_run['id']}"
    ).json()
    assert terminal_run["final_assessment_id"] == exact["assessment"]["id"]

    edited_arranged = _arrange(client, uow_factory, "report-edited")
    edited_run = _create_run(client, edited_arranged, rubric)
    edited = _complete(
        client, edited_run["id"], answer + "!", "mock-report-edited"
    )
    assert edited["assessment"]["feedback"] != expected["feedback"]
    assert edited["assessment"]["facts"] != expected["facts"]
    assert edited["assessment"]["ambiguities"] == [
        "The edited claim requires review."
    ]


def test_report_is_withheld_without_completed_run_and_linked_assessment(
    client, uow_factory
):
    run = _create_run(
        client,
        _arrange(client, uow_factory, "report-gate"),
        _seed_rubric(uow_factory),
    )
    before = client.get(f"/api/v1/interview-runs/{run['id']}/report")
    assert before.status_code == 409
    assert before.json()["code"] == "mock_feedback_withheld"
