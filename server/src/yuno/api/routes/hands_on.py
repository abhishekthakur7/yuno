from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from yuno.api.contracts import (
    HandsOnLifecycleResponse,
    HandsOnSubmitRequest,
    JobRefResponse,
    accepted_job,
)
from yuno.api.dependencies import (
    get_job_dispatcher,
    get_owner_id,
    get_unit_of_work,
    idempotency_key,
)
from yuno.modules.evidence_evaluation.domain import EvidenceEvaluationIdempotencyRecord
from yuno.modules.hands_on.ports import HandsOnUnitOfWork
from yuno.modules.hands_on.service import (
    complete_static_review,
    get_lifecycle,
    prepare_submission,
)
from yuno.modules.provider.service import require_disclosure
from yuno.shared.application.jobs import JobDispatcher, JobLane, JobRequest
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.errors import IdempotencyConflictError
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id

router = APIRouter(tags=["hands-on"])


@router.get(
    "/goals/{goal_id}/topics/{topic_id}/hands-on",
    response_model=HandsOnLifecycleResponse,
)
def read_hands_on(
    goal_id: str,
    topic_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[HandsOnUnitOfWork, Depends(get_unit_of_work)],
):
    work, topic, role, level, constraints, artifacts, reviews, questions = (
        get_lifecycle(uow, owner_id, goal_id, topic_id)
    )
    review_items = []
    for review in reviews:
        assessment = uow.evidence.get_assessment(owner_id, review.assessment_id)
        review_items.append(
            {
                "id": review.id,
                "artifact_id": review.artifact_id,
                "assessment_id": review.assessment_id,
                "rubric_id": assessment.rubric_id if assessment else "",
                "rubric_version": assessment.rubric_version if assessment else "",
                "rubric_status": (
                    rubric.status.value
                    if assessment
                    and (
                        rubric := uow.evidence.get_rubric(
                            owner_id, assessment.rubric_id
                        )
                    )
                    else "unavailable"
                ),
                "review_mode": review.review_mode.value,
                "limitation": review.required_limitation_label,
                "feedback": assessment.feedback if assessment else "",
                "created_at": review.created_at,
            }
        )
    return {
        "work_id": work.id if work else None,
        "goal_id": goal_id,
        "topic_id": topic_id,
        "scenario": {
            "title": work.scenario_title
            if work
            else f"{topic.title} hands-on scenario",
            "prompt": work.scenario_prompt
            if work
            else f"Create and defend a solution for the approved {topic.title} topic boundary.",
            "role": role,
            "level": level,
            "constraints": list(constraints),
            "status": work.scenario_status if work else "fixture",
            "source": work.scenario_source if work else "fixture-pending-idk-009",
        },
        "artifacts": [item.__dict__ for item in artifacts],
        "reviews": review_items,
        "cross_questions": [item.__dict__ for item in questions],
    }


@router.post(
    "/goals/{goal_id}/topics/{topic_id}/hands-on/submit",
    response_model=JobRefResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={202: {"model": JobRefResponse}},
)
def submit_hands_on(
    goal_id: str,
    topic_id: str,
    body: HandsOnSubmitRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[HandsOnUnitOfWork, Depends(get_unit_of_work)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
    key: Annotated[str, Depends(idempotency_key)],
):
    operation = f"submit_hands_on:{goal_id}:{topic_id}"
    request_data = body.model_dump(mode="json")
    request_hash = hash_payload(request_data)
    uow.profiles_goals.lock_idempotency_commands(owner_id)
    prior = uow.evidence.get_idempotency(owner_id, operation, key)
    needs_completion = prior is None or not prior.completed
    if prior is not None:
        if prior.request_hash != request_hash:
            raise IdempotencyConflictError(
                "The Idempotency-Key was reused with a different hands-on submission."
            )
        if prior.request_ref is None:
            raise RuntimeError("The hands-on idempotency reservation is invalid.")
        saved = JobRefResponse.model_validate_json(prior.response_json)
        current = dispatcher.get(owner_id, saved.job_id)
        if current is not None:
            if not prior.completed:
                uow.evidence.complete_idempotency(
                    owner_id,
                    operation,
                    key,
                    saved.model_copy(
                        update={"deduplicated": True}
                    ).model_dump_json(),
                )
                uow.commit()
            return accepted_job(current)
        artifact = uow.hands_on.get_artifact_by_evidence(
            owner_id, prior.request_ref
        )
        if artifact is None:
            raise RuntimeError("The reserved hands-on artifact is unavailable.")
        if saved.result_ref is None:
            raise RuntimeError("The reserved hands-on rubric is unavailable.")
        rubric_id = saved.result_ref
        disclosure = require_disclosure(uow, owner_id)
        uow.commit()
    else:
        disclosure = require_disclosure(uow, owner_id)
        answer = body.cross_question_response
        artifact, rubric = prepare_submission(
            uow,
            owner_id,
            goal_id,
            topic_id,
            body.artifact,
            answer.question_id if answer else None,
            answer.response if answer else None,
        )
        rubric_id = rubric.id
        job_id = new_id()
        response = JobRefResponse(
            job_id=job_id,
            kind="review_hands_on_artifact",
            status="queued",
            enqueued_at=now_text(SystemClock()),
            lane=JobLane.INTERACTIVE,
            goal_id=goal_id,
            schema_version="hands-on-review-v1",
            result_ref=rubric_id,
        )
        uow.evidence.add_idempotency(
            EvidenceEvaluationIdempotencyRecord(
                new_id(),
                owner_id,
                operation,
                key,
                request_hash,
                response.model_dump_json(),
                now_text(SystemClock()),
                artifact.evidence_id,
                False,
            )
        )
        uow.commit()
        saved = response
    ref = dispatcher.enqueue(
        JobRequest(
            "review_hands_on_artifact",
            owner_id,
            {"artifact_id": artifact.id, "rubric_id": rubric_id},
            artifact.id,
            key,
            requested_job_id=saved.job_id,
            goal_id=goal_id,
            lane=JobLane.INTERACTIVE,
            schema_version="hands-on-review-v1",
            request_ref=f"HandsOnArtifact:{artifact.id}",
            disclosure_ref=disclosure.id,
        )
    )
    if needs_completion:
        uow.evidence.complete_idempotency(
            owner_id,
            operation,
            key,
            saved.model_copy(update={"deduplicated": True}).model_dump_json(),
        )
        uow.commit()
    return accepted_job(ref)


def run_hands_on_review_job(request, uow_factory, adapter):
    with uow_factory() as uow:
        return complete_static_review(
            uow,
            adapter,
            request.owner_id,
            str(request.payload["artifact_id"]),
            str(request.payload["rubric_id"]),
        )
