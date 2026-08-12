"""Lowest-useful-level IDK-302 Practice lifecycle test.

The in-memory repository keeps this test on the interview domain/service seam:
no HTTP, SQLAlchemy, job worker, or provider behavior is involved.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

import pytest

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
from yuno.modules.interview.service import (
    begin_evaluation,
    cancel_evaluation,
    complete_evaluation,
    create_practice_run,
    fail_evaluation,
    get_practice_run,
    request_hint,
    submit_answer,
)
from yuno.shared.domain.errors import ConflictError, DomainValidationError

FIXTURE_MARKER = "fixture-v0-non-production"
FIXTURE_QUESTION = (
    "Fixture-v0 only: explain why token A precedes token B under the "
    "stated synthetic ordering rule."
)
FIXTURE_HINT = "Fixture-v0 hint: name the missing ordering assumption."


class _FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


@dataclass
class _Goal:
    id: str


class _Goals:
    def get_goal(self, owner_id: str, goal_id: str):
        return _Goal(goal_id) if (owner_id, goal_id) == ("owner", "goal") else None


class _InterviewRepository:
    def __init__(self, bundle: InterviewBundle) -> None:
        self.bundles = {bundle.id: bundle}
        self.runs: dict[str, PracticeRun] = {}
        self.turns: dict[str, list[PracticeTurn]] = {}
        self.results: dict[str, list[PracticeTurnResult]] = {}

    def get_bundle(self, owner_id: str, bundle_id: str):
        value = self.bundles.get(bundle_id)
        return value if value is not None and value.owner_id == owner_id else None

    def add_run(self, run: PracticeRun) -> PracticeRun:
        self.runs[run.id] = replace(run, turns=(), results=())
        self.turns[run.id] = []
        self.results[run.id] = []
        return self.get_run(run.owner_id, run.id)  # type: ignore[return-value]

    def get_run(self, owner_id: str, run_id: str):
        run = self.runs.get(run_id)
        if run is None or run.owner_id != owner_id:
            return None
        return replace(
            run,
            turns=tuple(self.turns[run_id]),
            results=tuple(self.results[run_id]),
        )

    def add_turn(self, turn: PracticeTurn) -> PracticeTurn:
        self.turns[turn.run_id].append(turn)
        return turn

    def add_turn_result(self, result: PracticeTurnResult) -> PracticeTurnResult:
        self.results[result.run_id].append(result)
        return result

    def update_run(self, owner_id: str, run_id: str, changes: dict[str, object]):
        run = self.runs.get(run_id)
        if run is None or run.owner_id != owner_id:
            return None
        self.runs[run_id] = replace(run, **changes)
        return self.get_run(owner_id, run_id)


@dataclass
class _Uow:
    interview: _InterviewRepository
    profiles_goals: _Goals


def _uow() -> _Uow:
    item = InterviewBundleItem(
        "question-fixture-v0",
        "owner",
        "bundle-fixture-v0",
        BundleSubject.TECHNICAL,
        "topic-fixture-v0",
        FIXTURE_QUESTION,
        0,
        False,
        True,
    )
    bundle = InterviewBundle(
        "bundle-fixture-v0",
        "owner",
        "goal",
        "Practice fixture-v0 non-production bundle",
        "Backend Engineer",
        "Senior",
        FIXTURE_MARKER,
        None,
        "active",
        1,
        "2026-01-02T03:04:05.000000Z",
        "2026-01-02T03:04:05.000000Z",
        (item,),
    )
    return _Uow(_InterviewRepository(bundle), _Goals())


def _answer_turns(run: PracticeRun) -> tuple[PracticeTurn, ...]:
    return tuple(turn for turn in run.turns if turn.kind is InterviewTurnKind.ANSWER)


def test_practice_state_machine_keeps_feedback_terminal_and_attempts_append_only() -> (
    None
):
    uow = _uow()
    clock = _FixedClock()
    run = create_practice_run(
        uow,
        "owner",
        "goal",
        "bundle-fixture-v0",
        "question-fixture-v0",
        "rubric-fixture-v0",
        "fixture-v0",
        "implement",
        hint_text=FIXTURE_HINT,
        clock=clock,
    )
    assert run.state is PracticeRunState.READY
    assert [turn.kind for turn in run.turns] == [InterviewTurnKind.QUESTION]
    assert run.results == ()

    assert get_practice_run(uow, "owner", run.id).turns == run.turns
    hinted = request_hint(uow, "owner", run.id, clock=clock)
    assert [
        turn.body for turn in hinted.turns if turn.kind is InterviewTurnKind.HINT
    ] == [FIXTURE_HINT]
    repeated = request_hint(uow, "owner", run.id, clock=clock)
    assert repeated.turns == hinted.turns

    with pytest.raises(DomainValidationError, match="must not be blank"):
        submit_answer(
            uow, "owner", run.id, " \n\t", "evidence-blank", "job-blank", clock=clock
        )
    with pytest.raises(ConflictError, match="stale"):
        complete_evaluation(
            uow,
            "owner",
            run.id,
            "no-answer",
            "assessment-impossible",
            facts=("Must not appear.",),
            trade_offs=(),
            dimensions=(),
            feedback="Must not appear.",
            cross_question_candidate=None,
            clock=clock,
        )
    assert get_practice_run(uow, "owner", run.id).results == ()

    first_body = "\n  Fixture-v0 first answer exact bytes.\t"
    first = submit_answer(
        uow, "owner", run.id, first_body, "evidence-first", "job-first", clock=clock
    )
    submitted = get_practice_run(uow, "owner", run.id)
    assert submitted.state is PracticeRunState.SUBMITTED
    assert first.body == first_body
    assert submitted.results == ()

    evaluating = begin_evaluation(uow, "owner", run.id, first.id, clock=clock)
    assert evaluating.state is PracticeRunState.EVALUATING
    assert evaluating.results == ()

    cancelled = cancel_evaluation(uow, "owner", run.id, clock=clock)
    assert cancelled.state is PracticeRunState.FAILED_RECOVERABLE
    assert cancelled.failure_reference == "evaluation_cancelled"
    assert cancelled.retryable is True
    assert _answer_turns(cancelled) == (first,)

    retrying = begin_evaluation(uow, "owner", run.id, first.id, clock=clock)
    assert retrying.state is PracticeRunState.EVALUATING
    failed = fail_evaluation(
        uow,
        "owner",
        run.id,
        first.id,
        "fixture-v0-provider-failure",
        clock=clock,
    )
    assert failed.state is PracticeRunState.FAILED_RECOVERABLE
    assert _answer_turns(failed) == (first,)
    assert failed.results == ()

    begin_evaluation(uow, "owner", run.id, first.id, clock=clock)
    specific_follow_up = (
        "Which fixture-v0 ordering assumption would fail if token B arrived first?"
    )
    completed = complete_evaluation(
        uow,
        "owner",
        run.id,
        first.id,
        "assessment-first",
        facts=("Fixture fact: token A precedes token B.",),
        trade_offs=("Fixture trade-off: deterministic order limits flexibility.",),
        dimensions=(
            PracticeDimensionResult(
                "fixture-reasoning", "Fixture reasoning", "pass", "Named assumption."
            ),
            PracticeDimensionResult(
                "fixture-trade-offs",
                "Fixture trade-offs",
                "trade-off",
                "Named consequence.",
            ),
        ),
        feedback="Fixture-v0 terminal feedback.",
        cross_question_candidate=specific_follow_up,
        clock=clock,
    )
    assert completed.state is PracticeRunState.FEEDBACK_READY
    assert completed.results[0].facts != completed.results[0].trade_offs
    assert {item.name for item in completed.results[0].dimensions} == {
        "Fixture reasoning",
        "Fixture trade-offs",
    }
    assert [
        turn.body
        for turn in completed.turns
        if turn.kind is InterviewTurnKind.FOLLOW_UP
    ] == [specific_follow_up]

    second_body = "  Fixture-v0 repaired answer is a new attempt.\n"
    second = submit_answer(
        uow, "owner", run.id, second_body, "evidence-second", "job-second", clock=clock
    )
    repaired = get_practice_run(uow, "owner", run.id)
    assert second.id != first.id
    assert _answer_turns(repaired) == (first, second)
    assert _answer_turns(repaired)[0].body == first_body
    assert _answer_turns(repaired)[1].body == second_body
