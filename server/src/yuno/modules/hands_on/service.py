from __future__ import annotations

from dataclasses import replace

from yuno.modules.evidence_evaluation.domain import EvaluationRequest, RubricStatus
from yuno.modules.evidence_evaluation.service import create_evidence, perform_assessment
from yuno.modules.hands_on.domain import (
    HandsOnArtifact,
    HandsOnCrossQuestion,
    HandsOnReview,
    HandsOnWork,
    ReviewMode,
)
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.errors import (
    ConflictError,
    DomainValidationError,
    EvidenceTooLargeError,
    NotFoundError,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id


def scenario_for(uow, owner_id: str, goal_id: str, topic_id: str):
    goal = uow.profiles_goals.get_goal(owner_id, goal_id)
    if goal is None:
        raise NotFoundError(f"Goal '{goal_id}' was not found.")
    topic = next(
        (
            item
            for item in uow.canonical.get_published_topics(goal.graph_version_id)
            if item.stable_id == topic_id
        ),
        None,
    )
    if topic is None:
        raise NotFoundError(f"Topic '{topic_id}' was not found in the goal graph.")
    role = goal.role or "Software Engineer"
    level = getattr(goal.target_level, "value", goal.target_level)
    constraints = (
        f"Address the approved topic boundary for {topic.title}.",
        f"Demonstrate the {topic.target_capability} capability.",
        "State assumptions and trade-offs explicitly.",
    )
    return goal, topic, role, str(level), constraints


def get_lifecycle(uow, owner_id: str, goal_id: str, topic_id: str):
    _goal, topic, role, level, constraints = scenario_for(
        uow, owner_id, goal_id, topic_id
    )
    work = uow.hands_on.get_work(owner_id, goal_id, topic_id)
    if work is None:
        return None, topic, role, level, constraints, (), (), ()
    artifacts = tuple(
        _with_artifact_content(uow, owner_id, artifact)
        for artifact in uow.hands_on.list_artifacts(owner_id, work.id)
    )
    return (
        work,
        topic,
        role,
        level,
        constraints,
        artifacts,
        uow.hands_on.list_reviews(owner_id, work.id),
        uow.hands_on.list_questions(owner_id, work.id),
    )


def _with_artifact_content(uow, owner_id: str, artifact: HandsOnArtifact):
    payload = uow.evidence.get_payload(owner_id, artifact.goal_id, artifact.evidence_id)
    return replace(artifact, content=payload.content if payload is not None else "")


def prepare_submission(
    uow,
    owner_id: str,
    goal_id: str,
    topic_id: str,
    artifact_content: str,
    question_id: str | None,
    question_response: str | None,
    *,
    max_payload_bytes: int,
    retained_owner_limit: int,
):
    content, response = validate_submission_payload(
        artifact_content,
        question_id,
        question_response,
        max_payload_bytes=max_payload_bytes,
    )
    _goal, topic, role, level, constraints = scenario_for(
        uow, owner_id, goal_id, topic_id
    )
    work = uow.hands_on.get_work(owner_id, goal_id, topic_id)
    timestamp = now_text(SystemClock())
    if work is None:
        if question_id is not None:
            raise ConflictError(
                "The first revision cannot answer a prior cross-question."
            )
        work = HandsOnWork(
            new_id(),
            owner_id,
            goal_id,
            topic_id,
            f"{topic.title} hands-on scenario",
            f"Create and defend a solution for the approved {topic.title} topic boundary.",
            role,
            level,
            constraints,
            "fixture",
            "fixture-pending-idk-009",
            timestamp,
        )
        uow.hands_on.add_work(work)
    artifacts = uow.hands_on.list_artifacts(owner_id, work.id)
    if artifacts and question_id is None:
        raise ConflictError("A revision must answer the prior review's cross-question.")
    if question_id is not None:
        question = uow.hands_on.get_question(owner_id, question_id)
        if question is None or question.work_id != work.id:
            raise ConflictError(
                "The cross-question does not belong to this hands-on work."
            )
        if any(item.response_to_question_id == question_id for item in artifacts):
            raise ConflictError("The cross-question has already been answered.")
        questions = uow.hands_on.list_questions(owner_id, work.id)
        if not questions or questions[-1].id != question_id:
            raise ConflictError("Only the latest cross-question may be answered.")
    rubrics = [
        item
        for item in uow.evidence.list_rubrics(owner_id)
        if item.status is not RubricStatus.RETIRED
        and item.capability == topic.target_capability
    ]
    if not rubrics:
        raise NotFoundError("No active rubric is available for this hands-on scenario.")
    rubric = rubrics[-1]
    revision = len(artifacts) + 1
    evidence = create_evidence(
        uow,
        owner_id,
        goal_id,
        topic_stable_id=topic_id,
        evidence_type="hands-on-artifact",
        capability=topic.target_capability,
        summary=f"{topic.title} hands-on revision {revision}",
        origin="hands-on-submit",
        content=content,
        content_version=f"revision-{revision}",
        max_payload_bytes=max_payload_bytes,
        retained_owner_limit=retained_owner_limit,
    )
    artifact = HandsOnArtifact(
        new_id(),
        owner_id,
        goal_id,
        work.id,
        revision,
        content,
        hash_payload(content),
        question_id,
        response if question_response is not None else None,
        evidence.id,
        timestamp,
    )
    uow.hands_on.add_artifact(artifact)
    return artifact, rubric


def validate_submission_payload(
    artifact_content: str,
    question_id: str | None,
    question_response: str | None,
    *,
    max_payload_bytes: int,
) -> tuple[str, str]:
    content = artifact_content.strip()
    if not content:
        raise DomainValidationError("artifact must not be blank.")
    if (question_id is None) != (question_response is None):
        raise DomainValidationError(
            "question_id and response must be supplied together."
        )
    if question_response is not None and not question_response.strip():
        raise DomainValidationError("cross-question response must not be blank.")
    response = question_response.strip() if question_response is not None else ""
    retained_bytes = len(content.encode("utf-8", errors="strict")) + len(
        response.encode("utf-8", errors="strict")
    )
    if retained_bytes > max_payload_bytes:
        raise EvidenceTooLargeError(
            "A hands-on revision and its cross-question response may contain at most "
            f"{max_payload_bytes} UTF-8 bytes in total."
        )
    return content, response


def complete_static_review(
    uow, adapter, owner_id: str, artifact_id: str, rubric_id: str
):
    artifact = uow.hands_on.get_artifact(owner_id, artifact_id)
    if artifact is None:
        raise NotFoundError("The submitted hands-on artifact was not found.")
    goal = uow.profiles_goals.get_goal(owner_id, artifact.goal_id)
    if goal is None:
        raise NotFoundError("The hands-on goal was not found.")
    work = next(
        (
            uow.hands_on.get_work(owner_id, artifact.goal_id, topic.stable_id)
            for topic in uow.canonical.get_published_topics(goal.graph_version_id)
            if (
                candidate := uow.hands_on.get_work(
                    owner_id, artifact.goal_id, topic.stable_id
                )
            )
            is not None
            and candidate.id == artifact.work_id
        ),
        None,
    )
    if work is None:
        raise NotFoundError("The hands-on work was not found.")
    rubric = uow.evidence.get_rubric(owner_id, rubric_id)
    if rubric is None or rubric.status is RubricStatus.RETIRED:
        raise NotFoundError("The hands-on rubric is no longer active.")
    timestamp = now_text(SystemClock())
    assessment = perform_assessment(
        uow,
        adapter,
        owner_id,
        EvaluationRequest(
            artifact.evidence_id,
            f"hands-on:{work.id}:revision:{artifact.revision_number}",
            rubric.id,
            rubric.version,
            work.constraints,
            rubric.capability,
            (),
            (f"hands-on-artifact:{artifact.id}",),
            work.role,
            work.level,
            "static",
        ),
    )
    limitations = tuple(
        item.strip() for item in assessment.limitation_labels if item.strip()
    )
    if not limitations:
        raise DomainValidationError(
            "A static review must include a non-empty limitation."
        )
    if (
        not assessment.cross_question_candidate
        or not assessment.cross_question_candidate.strip()
    ):
        raise DomainValidationError(
            "A hands-on review must include an artifact-specific cross-question."
        )
    review = HandsOnReview(
        new_id(),
        owner_id,
        artifact.goal_id,
        work.id,
        artifact.id,
        assessment.id,
        ReviewMode.STATIC,
        limitations[0],
        timestamp,
    )
    uow.hands_on.add_review(review)
    gap = (
        assessment.ambiguities[0]
        if assessment.ambiguities
        else assessment.trade_offs[0]
        if assessment.trade_offs
        else "the submitted artifact's stated assumptions"
    )
    uow.hands_on.add_question(
        HandsOnCrossQuestion(
            new_id(),
            owner_id,
            artifact.goal_id,
            work.id,
            review.id,
            artifact.id,
            assessment.cross_question_candidate.strip(),
            gap,
            timestamp,
        )
    )
    uow.commit()
    return review
