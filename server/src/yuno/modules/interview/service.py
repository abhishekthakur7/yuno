"""Interview bundle application service."""

from __future__ import annotations

from yuno.modules.interview.domain import (
    BundleSubject,
    InterviewBundle,
    InterviewBundleItem,
    InterviewTurnKind,
    PracticeDimensionResult,
    PracticeRun,
    PracticeRunState,
    PracticeTurn,
    PracticeTurnResult,
)
from yuno.modules.interview.ports import InterviewUnitOfWork
from yuno.shared.domain.clock import Clock, SystemClock, now_text
from yuno.shared.domain.errors import (
    ConflictError,
    DomainValidationError,
    NotFoundError,
    PreconditionFailedError,
)
from yuno.shared.domain.ids import new_id


def require_goal(uow: InterviewUnitOfWork, owner_id: str, goal_id: str) -> None:
    if uow.profiles_goals.get_goal(owner_id, goal_id) is None:
        raise NotFoundError("Goal not found.")


def create_bundle(
    uow: InterviewUnitOfWork,
    owner_id: str,
    data: dict,
    *,
    clock: Clock | None = None,
    copy_source_id: str | None = None,
) -> InterviewBundle:
    for field in ("name", "generic_role", "origin"):
        data[field] = data[field].strip()
        if not data[field]:
            raise DomainValidationError(f"{field} must not be blank.")
    if data.get("goal_id") is not None:
        require_goal(uow, owner_id, data["goal_id"])
    timestamp = now_text(clock or SystemClock())
    bundle_id = new_id()
    items = tuple(_new_item(owner_id, bundle_id, item) for item in data["items"])
    _validate_items(items)
    return uow.interview.add_bundle(
        InterviewBundle(
            bundle_id,
            owner_id,
            data.get("goal_id"),
            data["name"],
            data["generic_role"],
            data["target_level"],
            data["origin"],
            copy_source_id,
            "active",
            1,
            timestamp,
            timestamp,
            items,
        )
    )


def copy_bundle(
    uow: InterviewUnitOfWork,
    owner_id: str,
    source_id: str,
    name: str,
    *,
    clock: Clock | None = None,
) -> InterviewBundle:
    source = get_bundle(uow, owner_id, source_id)
    name = name.strip()
    if not name:
        raise DomainValidationError("name must not be blank.")
    data = {
        "goal_id": source.goal_id,
        "name": name,
        "generic_role": source.generic_role,
        "target_level": source.target_level,
        "origin": "copied",
        "items": [
            {
                "subject": i.subject,
                "topic_stable_id": i.topic_stable_id,
                "question": i.question,
                "position": i.position,
                "is_optional": i.is_optional,
                "included": i.included,
            }
            for i in source.items
        ],
    }
    return create_bundle(uow, owner_id, data, clock=clock, copy_source_id=source.id)


def get_bundle(
    uow: InterviewUnitOfWork, owner_id: str, bundle_id: str
) -> InterviewBundle:
    value = uow.interview.get_bundle(owner_id, bundle_id)
    if value is None:
        raise NotFoundError("Interview bundle not found.")
    return value


def update_bundle(
    uow: InterviewUnitOfWork,
    owner_id: str,
    bundle_id: str,
    expected_version: int,
    changes: dict[str, object],
    item_changes: dict[str, bool],
    *,
    clock: Clock | None = None,
) -> InterviewBundle:
    current = get_bundle(uow, owner_id, bundle_id)
    known = {item.id: item for item in current.items}
    for item_id in item_changes:
        if item_id not in known:
            raise DomainValidationError(
                "The bundle item does not belong to this bundle."
            )
        if not known[item_id].is_optional:
            raise DomainValidationError("Only optional bundle items may be toggled.")
    changes["updated_at"] = now_text(clock or SystemClock())
    updated = uow.interview.update_bundle(
        owner_id, bundle_id, expected_version, changes, item_changes
    )
    if updated is None:
        raise PreconditionFailedError("The interview bundle changed since it was read.")
    return updated


def create_practice_run(
    uow: InterviewUnitOfWork,
    owner_id: str,
    goal_id: str,
    bundle_id: str,
    bundle_item_id: str,
    rubric_id: str,
    rubric_version: str,
    requested_capability: str,
    *,
    hint_text: str | None = None,
    clock: Clock | None = None,
) -> PracticeRun:
    require_goal(uow, owner_id, goal_id)
    bundle = get_bundle(uow, owner_id, bundle_id)
    if bundle.goal_id != goal_id:
        raise DomainValidationError(
            "The interview bundle does not belong to this goal."
        )
    item = next((value for value in bundle.items if value.id == bundle_item_id), None)
    if item is None or not item.included or item.question is None:
        raise DomainValidationError(
            "The selected bundle item is not an included question."
        )
    if item.topic_stable_id is None:
        raise DomainValidationError(
            "A Practice question must reference an approved topic."
        )
    required = {
        "rubric_id": rubric_id,
        "rubric_version": rubric_version,
        "requested_capability": requested_capability,
    }
    if any(not value.strip() for value in required.values()):
        raise DomainValidationError("Practice evaluation references must not be blank.")
    if hint_text is not None and not hint_text.strip():
        raise DomainValidationError("A configured hint must not be blank.")
    timestamp = now_text(clock or SystemClock())
    run_id = new_id()
    run = PracticeRun(
        run_id,
        owner_id,
        goal_id,
        bundle_id,
        bundle_item_id,
        "Practice",
        PracticeRunState.READY,
        item.question,
        hint_text,
        rubric_id.strip(),
        rubric_version.strip(),
        requested_capability.strip(),
        None,
        None,
        None,
        False,
        timestamp,
        timestamp,
        (),
        (),
    )
    uow.interview.add_run(run)
    uow.interview.add_turn(
        PracticeTurn(
            new_id(),
            owner_id,
            run_id,
            1,
            InterviewTurnKind.QUESTION,
            item.question,
            None,
            None,
            timestamp,
        )
    )
    return get_practice_run(uow, owner_id, run_id)


def get_practice_run(
    uow: InterviewUnitOfWork, owner_id: str, run_id: str
) -> PracticeRun:
    run = uow.interview.get_run(owner_id, run_id)
    if run is None:
        raise NotFoundError("Practice run not found.")
    return run


def request_hint(
    uow: InterviewUnitOfWork, owner_id: str, run_id: str, *, clock: Clock | None = None
) -> PracticeRun:
    run = get_practice_run(uow, owner_id, run_id)
    if run.state not in {PracticeRunState.READY, PracticeRunState.ANSWERING}:
        raise ConflictError("A hint cannot be requested after an answer was submitted.")
    existing = next(
        (turn for turn in reversed(run.turns) if turn.kind is InterviewTurnKind.HINT),
        None,
    )
    if existing is not None:
        return run
    if run.hint_text is None:
        raise ConflictError("No reviewed hint is configured for this fixture question.")
    timestamp = now_text(clock or SystemClock())
    uow.interview.add_turn(
        PracticeTurn(
            new_id(),
            owner_id,
            run.id,
            _next_number(run),
            InterviewTurnKind.HINT,
            run.hint_text,
            run.active_answer_turn_id,
            None,
            timestamp,
        )
    )
    uow.interview.update_run(
        owner_id, run.id, {"state": PracticeRunState.ANSWERING, "updated_at": timestamp}
    )
    return get_practice_run(uow, owner_id, run.id)


def submit_answer(
    uow: InterviewUnitOfWork,
    owner_id: str,
    run_id: str,
    answer: str,
    evidence_id: str,
    job_id: str,
    *,
    clock: Clock | None = None,
) -> PracticeTurn:
    run = get_practice_run(uow, owner_id, run_id)
    if not answer.strip():
        raise DomainValidationError("An answer must not be blank.")
    if run.state in {PracticeRunState.SUBMITTED, PracticeRunState.EVALUATING}:
        raise ConflictError("The active answer is already being evaluated.")
    timestamp = now_text(clock or SystemClock())
    turn = PracticeTurn(
        new_id(),
        owner_id,
        run.id,
        _next_number(run),
        InterviewTurnKind.ANSWER,
        answer,
        None,
        evidence_id,
        timestamp,
    )
    uow.interview.add_turn(turn)
    uow.interview.update_run(
        owner_id,
        run.id,
        {
            "state": PracticeRunState.SUBMITTED,
            "active_job_id": job_id,
            "active_answer_turn_id": turn.id,
            "failure_reference": None,
            "retryable": False,
            "updated_at": timestamp,
        },
    )
    return turn


def begin_evaluation(
    uow: InterviewUnitOfWork,
    owner_id: str,
    run_id: str,
    answer_turn_id: str,
    *,
    clock: Clock | None = None,
) -> PracticeRun:
    run = get_practice_run(uow, owner_id, run_id)
    if run.active_answer_turn_id != answer_turn_id:
        raise ConflictError(
            "The evaluation does not match the active submitted attempt."
        )
    if run.state is PracticeRunState.EVALUATING:
        return run
    if run.state not in {
        PracticeRunState.SUBMITTED,
        PracticeRunState.FAILED_RECOVERABLE,
    }:
        raise ConflictError("The submitted attempt is not available for evaluation.")
    timestamp = now_text(clock or SystemClock())
    updated = uow.interview.update_run(
        owner_id,
        run.id,
        {
            "state": PracticeRunState.EVALUATING,
            "failure_reference": None,
            "retryable": False,
            "updated_at": timestamp,
        },
    )
    assert updated is not None
    return updated


def complete_evaluation(
    uow: InterviewUnitOfWork,
    owner_id: str,
    run_id: str,
    answer_turn_id: str,
    assessment_id: str,
    *,
    facts: tuple[str, ...],
    trade_offs: tuple[str, ...],
    dimensions: tuple[PracticeDimensionResult, ...],
    feedback: str,
    cross_question_candidate: str | None,
    clock: Clock | None = None,
) -> PracticeRun:
    run = get_practice_run(uow, owner_id, run_id)
    if (
        run.active_answer_turn_id != answer_turn_id
        or run.state is not PracticeRunState.EVALUATING
    ):
        raise ConflictError("The evaluation result is stale for this Practice run.")
    if any(result.answer_turn_id == answer_turn_id for result in run.results):
        return run
    timestamp = now_text(clock or SystemClock())
    uow.interview.add_turn_result(
        PracticeTurnResult(
            new_id(),
            owner_id,
            run.id,
            answer_turn_id,
            assessment_id,
            timestamp,
            facts,
            trade_offs,
            dimensions,
            feedback,
            cross_question_candidate,
        )
    )
    if cross_question_candidate is not None and cross_question_candidate.strip():
        uow.interview.add_turn(
            PracticeTurn(
                new_id(),
                owner_id,
                run.id,
                _next_number(run),
                InterviewTurnKind.FOLLOW_UP,
                cross_question_candidate,
                answer_turn_id,
                None,
                timestamp,
            )
        )
    uow.interview.update_run(
        owner_id,
        run.id,
        {
            "state": PracticeRunState.FEEDBACK_READY,
            "active_job_id": None,
            "failure_reference": None,
            "retryable": False,
            "updated_at": timestamp,
        },
    )
    return get_practice_run(uow, owner_id, run.id)


def fail_evaluation(
    uow: InterviewUnitOfWork,
    owner_id: str,
    run_id: str,
    answer_turn_id: str,
    failure_reference: str,
    *,
    clock: Clock | None = None,
) -> PracticeRun:
    run = get_practice_run(uow, owner_id, run_id)
    if run.active_answer_turn_id != answer_turn_id:
        return run
    timestamp = now_text(clock or SystemClock())
    updated = uow.interview.update_run(
        owner_id,
        run.id,
        {
            "state": PracticeRunState.FAILED_RECOVERABLE,
            "active_job_id": None,
            "failure_reference": failure_reference,
            "retryable": True,
            "updated_at": timestamp,
        },
    )
    assert updated is not None
    return updated


def cancel_evaluation(
    uow: InterviewUnitOfWork, owner_id: str, run_id: str, *, clock: Clock | None = None
) -> PracticeRun:
    run = get_practice_run(uow, owner_id, run_id)
    if run.state not in {PracticeRunState.SUBMITTED, PracticeRunState.EVALUATING}:
        raise ConflictError("There is no in-flight Practice evaluation to cancel.")
    assert run.active_answer_turn_id is not None
    return fail_evaluation(
        uow,
        owner_id,
        run.id,
        run.active_answer_turn_id,
        "evaluation_cancelled",
        clock=clock,
    )


def reserve_evaluation_retry(
    uow: InterviewUnitOfWork,
    owner_id: str,
    run_id: str,
    job_id: str,
    *,
    clock: Clock | None = None,
) -> PracticeRun:
    run = get_practice_run(uow, owner_id, run_id)
    if run.state is not PracticeRunState.FAILED_RECOVERABLE or not run.retryable:
        raise ConflictError("This Practice evaluation is not retryable.")
    if run.active_answer_turn_id is None:
        raise ConflictError("The failed evaluation has no preserved attempt.")
    timestamp = now_text(clock or SystemClock())
    updated = uow.interview.update_run(
        owner_id,
        run.id,
        {
            "state": PracticeRunState.SUBMITTED,
            "active_job_id": job_id,
            "failure_reference": None,
            "retryable": False,
            "updated_at": timestamp,
        },
    )
    assert updated is not None
    return updated


def _next_number(run: PracticeRun) -> int:
    return 1 + max((turn.turn_number for turn in run.turns), default=0)


def _new_item(owner_id: str, bundle_id: str, data: dict) -> InterviewBundleItem:
    return InterviewBundleItem(
        new_id(),
        owner_id,
        bundle_id,
        BundleSubject(data["subject"]),
        data.get("topic_stable_id"),
        data.get("question"),
        data["position"],
        data["is_optional"],
        data["included"],
    )


def _validate_items(items: tuple[InterviewBundleItem, ...]) -> None:
    if len({item.position for item in items}) != len(items):
        raise DomainValidationError("Bundle item positions must be unique.")
    for item in items:
        if item.subject != BundleSubject.TECHNICAL and not item.is_optional:
            raise DomainValidationError(
                "Behavioral and leadership items must be optional."
            )
