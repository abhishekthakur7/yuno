from __future__ import annotations

import pytest
from sqlalchemy import text

from tests.integration.test_learning_content_api import _seed
from tests.job_assertions import wait_for_job
from tests.provider_fakes import accept_provider_disclosure, install_provider_fake
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
from yuno.modules.evidence_evaluation.service import (
    complete_reevaluation,
    create_dispute,
    create_evidence,
    perform_assessment,
    request_reevaluation,
)
from yuno.shared.application.jobs import JobRef, JobRequest, JobStatus
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.errors import (
    ConflictError,
    DomainValidationError,
    EvidenceCountLimitError,
    EvidenceTooLargeError,
)
from yuno.shared.domain.ids import new_id


class FakeEvaluationAdapter:
    def __init__(self, *, ambiguity: bool = False) -> None:
        self.ambiguity = ambiguity

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        del request
        unresolved = self.ambiguity
        return EvaluationResult(
            state=AssessmentState.AMBIGUITY_UNRESOLVED
            if unresolved
            else AssessmentState.FEEDBACK_READY,
            dimensions=(
                EvaluationDimensionResult(
                    "reasoning",
                    DimensionOutcome.AMBIGUITY_UNRESOLVED
                    if unresolved
                    else DimensionOutcome.PASS,
                    "The stated assumptions support this outcome.",
                    ("evidence:answer",),
                ),
                EvaluationDimensionResult(
                    "trade-offs",
                    DimensionOutcome.TRADE_OFF,
                    "The alternative is defensible and its consequence is explicit.",
                    ("evidence:answer",),
                ),
            ),
            facts=("The invariant is maintained.",),
            trade_offs=("This choice exchanges throughput for simpler ordering.",),
            citations=("source:fixture",),
            ambiguities=("The workload distribution is unspecified.",)
            if unresolved
            else (),
            feedback="A defensible solution with assumptions and consequences separated from facts.",
            cross_question_candidate=None,
            revision_invitation="Clarify the workload if it becomes available.",
            warnings=(),
            limitation_labels=("fixture-evaluator",),
        )


def _arrange(uow_factory: UnitOfWorkFactory):
    _graph_id, topic_id, goal_id = _seed(uow_factory)
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        timestamp = now_text(SystemClock())
        rubric = Rubric(
            new_id(),
            owner.id,
            "fixture-task",
            "implement",
            "backend",
            "senior",
            "fixture-v0",
            RubricStatus.FIXTURE,
            "IDK-204 test fixture",
            timestamp,
        )
        dimensions = (
            RubricDimension(
                new_id(),
                rubric.id,
                "reasoning",
                "Reasoning",
                "Correct reasoning under stated assumptions.",
                1,
                "Accept multiple defensible approaches.",
            ),
            RubricDimension(
                new_id(),
                rubric.id,
                "trade-offs",
                "Trade-offs",
                "Consequences are explicit.",
                2,
                "Separate trade-offs from factual corrections.",
            ),
        )
        uow.evidence.add_rubric(rubric, dimensions)
        evidence = create_evidence(
            uow,
            owner.id,
            goal_id,
            topic_stable_id=topic_id,
            evidence_type="answer",
            capability="implement",
            summary="Queue design",
            origin="learner-submit",
            content="Use a ring buffer; assumes bounded capacity.",
            content_version="v1",
        )
        uow.commit()
    request = EvaluationRequest(
        evidence.id,
        "fixture-task",
        rubric.id,
        rubric.version,
        ("Capacity is bounded.",),
        "implement",
        ("source:fixture",),
        ("fixture:v0",),
        "backend",
        "senior",
        "static",
    )
    return owner.id, evidence, rubric, request


def test_evidence_requires_an_active_goal_and_nonblank_payload(
    client, uow_factory: UnitOfWorkFactory
) -> None:
    _graph_id, topic_id, goal_id = _seed(uow_factory)
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        goal = uow.profiles_goals.get_goal(owner.id, goal_id) if owner else None
        assert owner is not None and goal is not None
        with pytest.raises(DomainValidationError, match="content must not be blank"):
            create_evidence(
                uow,
                owner.id,
                goal_id,
                topic_stable_id=topic_id,
                evidence_type="answer",
                capability="implement",
                summary="Blank submission",
                origin="learner-submit",
                content="   ",
                content_version="v1",
            )
        row_version = goal.row_version

    archived = client.post(
        f"/api/v1/goals/{goal_id}/archive",
        headers={
            "If-Match": str(row_version),
            "Idempotency-Key": "archive-before-evidence",
        },
    )
    assert archived.status_code == 200, archived.text

    with uow_factory() as uow, pytest.raises(ConflictError, match="active goal"):
        create_evidence(
            uow,
            owner.id,
            goal_id,
            topic_stable_id=topic_id,
            evidence_type="answer",
            capability="implement",
            summary="Archived goal submission",
            origin="learner-submit",
            content="valid payload",
            content_version="v1",
        )


def test_evidence_limits_are_utf8_exact_and_fail_before_append(
    uow_factory: UnitOfWorkFactory,
) -> None:
    _graph_id, topic_id, goal_id = _seed(uow_factory)
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        exact = create_evidence(
            uow,
            owner.id,
            goal_id,
            topic_stable_id=topic_id,
            evidence_type="answer",
            capability="implement",
            summary="Exact UTF-8 boundary",
            origin="learner-submit",
            content="éé",
            content_version="v1",
            max_payload_bytes=4,
            retained_owner_limit=1,
        )
        assert exact.id
        with pytest.raises(EvidenceCountLimitError):
            create_evidence(
                uow,
                owner.id,
                goal_id,
                topic_stable_id=topic_id,
                evidence_type="answer",
                capability="implement",
                summary="Count overflow",
                origin="learner-submit",
                content="x",
                content_version="v1",
                max_payload_bytes=4,
                retained_owner_limit=1,
            )
        with pytest.raises(EvidenceTooLargeError):
            create_evidence(
                uow,
                owner.id,
                goal_id,
                topic_stable_id=topic_id,
                evidence_type="answer",
                capability="implement",
                summary="Byte overflow",
                origin="learner-submit",
                content="ééx",
                content_version="v1",
                max_payload_bytes=4,
                retained_owner_limit=2,
            )
        assert uow.evidence.count_live_evidence(owner.id) == 1


def test_reevaluation_creates_a_linear_successor_and_excludes_only_the_tip_atomically(
    client, uow_factory: UnitOfWorkFactory, engine
) -> None:
    del client
    owner_id, evidence, _rubric, evaluation_request = _arrange(uow_factory)
    adapter = FakeEvaluationAdapter()
    with uow_factory() as uow:
        first = perform_assessment(uow, adapter, owner_id, evaluation_request)
        dispute = create_dispute(
            uow, owner_id, first.id, "My bounded-capacity assumption was overlooked."
        )
        reevaluation = request_reevaluation(uow, owner_id, first.id, dispute.id)
        uow.commit()

    with uow_factory() as uow:
        second = complete_reevaluation(uow, adapter, owner_id, reevaluation.id)
        uow.commit()

    with uow_factory() as uow:
        preserved_first = uow.evidence.get_assessment(owner_id, first.id)
        preserved_second = uow.evidence.get_assessment(owner_id, second.id)
        assert (
            preserved_first is not None and preserved_first.derivation_excluded is True
        )
        assert (
            preserved_second is not None
            and preserved_second.derivation_excluded is False
        )
        assert preserved_second.predecessor_assessment_id == first.id
        assert preserved_first.feedback == first.feedback
        assert (
            uow.evidence.get_payload(owner_id, evidence.goal_id, evidence.id)
            is not None
        )
        with pytest.raises(ConflictError, match="active assessment tip"):
            request_reevaluation(uow, owner_id, first.id, dispute.id)

    with engine.begin() as connection:
        with pytest.raises(Exception, match="immutable"):
            connection.execute(
                text(
                    "UPDATE assessment_bodies SET feedback='rewritten' "
                    "WHERE assessment_id=:id"
                ),
                {"id": second.id},
            )
        with pytest.raises(Exception, match="immutable"):
            connection.execute(
                text("DELETE FROM assessments WHERE id=:id"), {"id": first.id}
            )


def test_invalid_or_incomplete_evaluation_result_is_never_persisted(
    client, uow_factory: UnitOfWorkFactory
) -> None:
    del client
    owner_id, _evidence, _rubric, evaluation_request = _arrange(uow_factory)

    class MissingDimensionAdapter(FakeEvaluationAdapter):
        def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
            result = super().evaluate(request)
            return EvaluationResult(
                **{**result.__dict__, "dimensions": result.dimensions[:1]}
            )

    with (
        uow_factory() as uow,
        pytest.raises(DomainValidationError, match="exactly one result"),
    ):
        perform_assessment(uow, MissingDimensionAdapter(), owner_id, evaluation_request)

    with uow_factory() as uow:
        assert (
            uow.evidence.get_active_assessment_for_evidence(
                owner_id, evaluation_request.evidence_id
            )
            is None
        )


def test_evidence_and_assessment_api_use_real_storage_and_fake_adapter(
    client, uow_factory: UnitOfWorkFactory
) -> None:
    _owner_id, _evidence, rubric, _request = _arrange(uow_factory)
    install_provider_fake(client, FakeEvaluationAdapter(ambiguity=True))
    goal_id = _evidence.goal_id
    topic_id = _evidence.topic_stable_id
    submitted = client.post(
        f"/api/v1/goals/{goal_id}/evidence",
        headers={"Idempotency-Key": "evidence-api"},
        json={
            "topic_stable_id": topic_id,
            "evidence_type": "answer",
            "capability": "implement",
            "summary": "Alternative answer",
            "origin": "learner-submit",
            "content": "Use two stacks; amortized dequeue is acceptable.",
            "content_version": "v1",
        },
    )
    assert submitted.status_code == 201, submitted.text
    evidence_id = submitted.json()["id"]
    submitted_replay = client.post(
        f"/api/v1/goals/{goal_id}/evidence",
        headers={"Idempotency-Key": "evidence-api"},
        json={
            "topic_stable_id": topic_id,
            "evidence_type": "answer",
            "capability": "implement",
            "summary": "Alternative answer",
            "origin": "learner-submit",
            "content": "Use two stacks; amortized dequeue is acceptable.",
            "content_version": "v1",
        },
    )
    assert submitted_replay.json() == submitted.json()
    submitted_conflict = client.post(
        f"/api/v1/goals/{goal_id}/evidence",
        headers={"Idempotency-Key": "evidence-api"},
        json={
            "topic_stable_id": topic_id,
            "evidence_type": "answer",
            "capability": "implement",
            "summary": "Changed",
            "origin": "learner-submit",
            "content": "Different",
            "content_version": "v1",
        },
    )
    assert submitted_conflict.status_code == 409
    assessed = client.post(
        f"/api/v1/evidence/{evidence_id}/assess",
        headers={"Idempotency-Key": "assess-api"},
        json={
            "rubric_id": rubric.id,
            "rubric_version": rubric.version,
            "task_ref": "fixture-task",
            "assumptions": ["Amortized cost is acceptable."],
            "requested_capability": "implement",
            "source_refs": ["source:fixture"],
            "provenance_refs": ["fixture:v0"],
            "role": "backend",
            "level": "senior",
            "evaluation_method": "static",
        },
    )
    assert assessed.status_code == 202, assessed.text
    assert assessed.json()["status"] == "queued"
    wait_for_job(client, assessed)
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        assessment = uow.evidence.get_active_assessment_for_evidence(
            owner.id, evidence_id
        )
        assert assessment is not None
    response = client.get(f"/api/v1/assessments/{assessment.id}")
    assert response.status_code == 200
    assert response.json()["state"] == "ambiguity-unresolved"
    assert {item["dimension_id"] for item in response.json()["dimensions"]} == {
        "reasoning",
        "trade-offs",
    }

    # A terminal replay does not require a disclosure because it does not
    # dispatch another provider request.
    revoked = client.post(
        "/api/v1/disclosures/provider-generation/revoke",
        params={"disclosure_version": "provider-network-v1"},
    )
    assert revoked.status_code == 200
    replay = client.post(
        f"/api/v1/evidence/{evidence_id}/assess",
        headers={"Idempotency-Key": "assess-api"},
        json={
            "rubric_id": rubric.id,
            "rubric_version": rubric.version,
            "task_ref": "fixture-task",
            "assumptions": ["Amortized cost is acceptable."],
            "requested_capability": "implement",
            "source_refs": ["source:fixture"],
            "provenance_refs": ["fixture:v0"],
            "role": "backend",
            "level": "senior",
            "evaluation_method": "static",
        },
    )
    assert replay.status_code == 202
    assert replay.json()["job_id"] == assessed.json()["job_id"]
    assert replay.json()["deduplicated"] is True
    conflict = client.post(
        f"/api/v1/evidence/{evidence_id}/assess",
        headers={"Idempotency-Key": "assess-api"},
        json={
            "rubric_id": rubric.id,
            "rubric_version": rubric.version,
            "task_ref": "changed",
            "assumptions": [],
            "requested_capability": "implement",
            "source_refs": [],
            "provenance_refs": [],
            "evaluation_method": "static",
        },
    )
    assert conflict.status_code == 409
    reaccepted = client.post(
        "/api/v1/disclosures/provider-generation/accept",
        json={"disclosure_version": "provider-network-v1"},
    )
    assert reaccepted.status_code == 200

    dispute = client.post(
        f"/api/v1/assessments/{assessment.id}/disputes",
        headers={"Idempotency-Key": "dispute-api"},
        json={"reason": "Please revisit ambiguity."},
    )
    assert dispute.status_code == 201
    dispute_replay = client.post(
        f"/api/v1/assessments/{assessment.id}/disputes",
        headers={"Idempotency-Key": "dispute-api"},
        json={"reason": "Please revisit ambiguity."},
    )
    assert dispute_replay.json() == dispute.json()
    dispute_conflict = client.post(
        f"/api/v1/assessments/{assessment.id}/disputes",
        headers={"Idempotency-Key": "dispute-api"},
        json={"reason": "Different reason."},
    )
    assert dispute_conflict.status_code == 409

    reevaluated = client.post(
        f"/api/v1/assessments/{assessment.id}/reevaluate",
        headers={"Idempotency-Key": "reevaluate-api"},
        json={"dispute_id": dispute.json()["id"]},
    )
    assert reevaluated.status_code == 202
    wait_for_job(client, reevaluated)
    reevaluation_replay = client.post(
        f"/api/v1/assessments/{assessment.id}/reevaluate",
        headers={"Idempotency-Key": "reevaluate-api"},
        json={"dispute_id": dispute.json()["id"]},
    )
    assert reevaluation_replay.json()["job_id"] == reevaluated.json()["job_id"]
    reevaluation_conflict = client.post(
        f"/api/v1/assessments/{assessment.id}/reevaluate",
        headers={"Idempotency-Key": "reevaluate-api"},
        json={"dispute_id": "different"},
    )
    assert reevaluation_conflict.status_code == 409
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        actions = {
            (event.entity_id, event.action)
            for event in uow.audit.list_for_owner(owner.id)
        }
        request_row = uow.evidence.get_reevaluation_for_dispute(
            owner.id, dispute.json()["id"]
        )
        assert request_row is not None
        assert request_row.job_id == reevaluated.json()["job_id"]
        assert (request_row.id, "requested") in actions
        assert (request_row.id, "completed") in actions


def test_evidence_reads_link_active_assessment_and_dispute_reevaluation_history(
    client, uow_factory: UnitOfWorkFactory
) -> None:
    owner_id, evidence, _rubric, evaluation_request = _arrange(uow_factory)
    with uow_factory() as uow:
        assessment = perform_assessment(
            uow, FakeEvaluationAdapter(), owner_id, evaluation_request
        )
        dispute = create_dispute(
            uow, owner_id, assessment.id, "The assumption needs another review."
        )
        reevaluation = request_reevaluation(uow, owner_id, assessment.id, dispute.id)
        uow.commit()

    evidence_list = client.get(f"/api/v1/goals/{evidence.goal_id}/evidence")
    assert evidence_list.status_code == 200
    assert evidence_list.json()[0]["active_assessment_id"] == assessment.id

    detail = client.get(f"/api/v1/evidence/{evidence.id}")
    assert detail.status_code == 200
    assert detail.json()["active_assessment_id"] == assessment.id
    assert detail.json()["transfers"] == []

    assessment_read = client.get(f"/api/v1/assessments/{assessment.id}")
    assert assessment_read.status_code == 200
    history = assessment_read.json()["disputes"]
    assert history == [
        {
            "id": dispute.id,
            "reason": dispute.reason,
            "status": "requested",
            "requested_at": dispute.requested_at,
            "resolved_at": None,
            "resolution_note": None,
            "reevaluation": {
                "id": reevaluation.id,
                "dispute_id": dispute.id,
                "status": "requested",
                "job_id": reevaluation.job_id,
                "resulting_assessment_id": None,
                "failure_reference": None,
                "requested_at": reevaluation.requested_at,
                "completed_at": None,
            },
        }
    ]


def test_reevaluation_persists_job_identity_before_dispatch(
    client, uow_factory: UnitOfWorkFactory
) -> None:
    owner_id, _evidence, _rubric, evaluation_request = _arrange(uow_factory)
    adapter = FakeEvaluationAdapter()
    with uow_factory() as uow:
        assessment = perform_assessment(uow, adapter, owner_id, evaluation_request)
        dispute = create_dispute(uow, owner_id, assessment.id, "Recheck this.")
        uow.commit()

    class InspectingDispatcher:
        def enqueue(self, request: JobRequest) -> JobRef:
            assert request.requested_job_id is not None
            with uow_factory() as uow:
                persisted = uow.evidence.get_reevaluation_request(
                    request.owner_id, str(request.payload["request_id"])
                )
                assert persisted is not None
                assert persisted.status.value == "requested"
                assert persisted.job_id == request.requested_job_id
            return JobRef(
                request.requested_job_id,
                request.kind,
                JobStatus.QUEUED,
                "2026-08-12T00:00:00Z",
            )

        def get(self, owner_id: str, job_id: str) -> JobRef | None:
            del owner_id, job_id
            return None

    client.app.state.dispatcher = InspectingDispatcher()
    response = client.post(
        f"/api/v1/assessments/{assessment.id}/reevaluate",
        headers={"Idempotency-Key": "persist-job-before-dispatch"},
        json={"dispute_id": dispute.id},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    with uow_factory() as uow:
        persisted = uow.evidence.get_reevaluation_for_dispute(owner_id, dispute.id)
        assert persisted is not None
        assert persisted.job_id == response.json()["job_id"]
        assert persisted.status.value == "requested"


def test_reevaluation_retry_redispatches_a_durable_request_after_enqueue_failure(
    client, uow_factory: UnitOfWorkFactory
) -> None:
    owner_id, _evidence, _rubric, evaluation_request = _arrange(uow_factory)
    with uow_factory() as uow:
        assessment = perform_assessment(
            uow, FakeEvaluationAdapter(), owner_id, evaluation_request
        )
        dispute = create_dispute(uow, owner_id, assessment.id, "Retry dispatch.")
        uow.commit()

    class RecoveringDispatcher:
        def __init__(self) -> None:
            self.requests: list[JobRequest] = []

        def enqueue(self, request: JobRequest) -> JobRef:
            self.requests.append(request)
            if len(self.requests) == 1:
                raise RuntimeError("dispatcher unavailable before enqueue")
            assert request.requested_job_id is not None
            return JobRef(
                request.requested_job_id,
                request.kind,
                JobStatus.QUEUED,
                "2026-08-12T00:00:00Z",
            )

        def get(self, owner_id: str, job_id: str) -> JobRef | None:
            del owner_id, job_id
            return None

    dispatcher = RecoveringDispatcher()
    client.app.state.dispatcher = dispatcher
    path = f"/api/v1/assessments/{assessment.id}/reevaluate"
    headers = {"Idempotency-Key": "recover-reevaluation-dispatch"}
    body = {"dispute_id": dispute.id}

    with pytest.raises(RuntimeError, match="dispatcher unavailable"):
        client.post(path, headers=headers, json=body)

    with uow_factory() as uow:
        durable = uow.evidence.get_reevaluation_for_dispute(owner_id, dispute.id)
        assert durable is not None and durable.status.value == "requested"
        durable_id = durable.id
        job_id = durable.job_id

    with uow_factory() as uow:
        second_dispute = create_dispute(
            uow, owner_id, assessment.id, "Changed request body."
        )
        uow.commit()
    changed = client.post(path, headers=headers, json={"dispute_id": second_dispute.id})
    assert changed.status_code == 409

    recovered = client.post(path, headers=headers, json=body)
    assert recovered.status_code == 202
    assert recovered.json()["job_id"] == job_id
    assert [request.payload["request_id"] for request in dispatcher.requests] == [
        durable_id,
        durable_id,
    ]
    with uow_factory() as uow:
        assert (
            len(
                [
                    item
                    for item in (
                        uow.evidence.get_reevaluation_for_dispute(owner_id, dispute.id),
                    )
                    if item is not None
                ]
            )
            == 1
        )


def test_reevaluation_rollback_tombstone_rejection_and_terminal_history_guards(
    client, uow_factory: UnitOfWorkFactory, engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    del client
    owner_id, evidence, _rubric, evaluation_request = _arrange(uow_factory)
    adapter = FakeEvaluationAdapter()
    with uow_factory() as uow:
        first = perform_assessment(uow, adapter, owner_id, evaluation_request)
        dispute = create_dispute(uow, owner_id, first.id, "Recheck this.")
        request = request_reevaluation(uow, owner_id, first.id, dispute.id)
        uow.commit()

    with uow_factory() as uow:

        def fail_terminal(*_args, **_kwargs):
            raise RuntimeError("forced terminal write failure")

        monkeypatch.setattr(
            type(uow.evidence), "update_reevaluation_request", fail_terminal
        )
        with pytest.raises(RuntimeError, match="forced terminal"):
            complete_reevaluation(uow, adapter, owner_id, request.id)

    with uow_factory() as uow:
        preserved = uow.evidence.get_assessment(owner_id, first.id)
        assert preserved is not None and not preserved.derivation_excluded
        assert (
            uow.evidence.get_active_assessment_for_evidence(owner_id, evidence.id).id
            == first.id
        )

    monkeypatch.undo()
    with uow_factory() as uow:
        completed = complete_reevaluation(uow, adapter, owner_id, request.id)
        assert completed.predecessor_assessment_id == first.id
        uow.commit()

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO evidence_tombstones (evidence_id,owner_id,goal_id,delete_operation_id,reason,tombstoned_at) VALUES (:e,:o,:g,'fixture-delete','test',:at)"
            ),
            {
                "e": evidence.id,
                "o": owner_id,
                "g": evidence.goal_id,
                "at": now_text(SystemClock()),
            },
        )
        connection.execute(
            text("DELETE FROM evidence_payloads WHERE evidence_id=:e"),
            {"e": evidence.id},
        )
    with uow_factory() as uow, pytest.raises(ConflictError, match="Tombstoned"):
        perform_assessment(uow, adapter, owner_id, evaluation_request)

    with (
        engine.begin() as connection,
        pytest.raises(Exception, match="invalid reevaluation request mutation"),
    ):
        connection.execute(
            text(
                "UPDATE reevaluation_requests SET failure_reference='rewrite' WHERE id=:id"
            ),
            {"id": request.id},
        )

    with (
        engine.begin() as connection,
        pytest.raises(Exception, match="invalid reevaluation request mutation"),
    ):
        connection.execute(
            text("UPDATE reevaluation_requests SET job_id='rewritten' WHERE id=:id"),
            {"id": request.id},
        )

    with uow_factory() as uow:
        actions = {
            (event.entity_id, event.action)
            for event in uow.audit.list_for_owner(owner_id)
        }
        assert (request.id, "requested") in actions


@pytest.fixture(autouse=True)
def accepted_provider_disclosure(client):
    accept_provider_disclosure(client)
