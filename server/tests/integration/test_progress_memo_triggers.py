from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from tests.integration.test_evidence_evaluation import FakeEvaluationAdapter, _arrange
from yuno.modules.evidence_evaluation.domain import TransferClassification
from yuno.modules.evidence_evaluation.service import (
    perform_assessment,
    transfer_evidence,
)
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import Clock


class FixedProgressClock(Clock):
    def now(self) -> datetime:
        # Keep this safely after repository-generated timestamps so the fixture
        # cannot become invalid merely because the suite runs later in the day.
        return datetime(2099, 1, 1, 12, tzinfo=UTC)


def _create_peer_goal(client: TestClient, graph_version_id: str, suffix: str) -> str:
    response = client.post(
        "/api/v1/goals",
        headers={"Idempotency-Key": f"progress-trigger-goal-{suffix}"},
        json={
            "name": f"Progress trigger {suffix}",
            "path": "learn",
            "subject": "backend",
            "target_level": "Senior",
            "target_capability": "implement",
            "graph_version_id": graph_version_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _warm(client: TestClient, *goal_ids: str) -> None:
    for goal_id in goal_ids:
        response = client.get(f"/api/v1/goals/{goal_id}/progress")
        assert response.status_code == 200, response.text


def _memo_counts(engine: Engine, goal_ids: tuple[str, ...]) -> dict[str, int]:
    with engine.connect() as connection:
        return {
            goal_id: connection.execute(
                text("SELECT count(*) FROM goal_progress_memos WHERE goal_id=:goal_id"),
                {"goal_id": goal_id},
            ).scalar_one()
            for goal_id in goal_ids
        }


def test_progress_memo_invalidation_is_scoped_fanned_out_and_atomic(
    client: TestClient,
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
) -> None:
    client.app.state.clock = FixedProgressClock()
    owner_id, evidence, _rubric, evaluation_request = _arrange(uow_factory)
    with uow_factory() as uow:
        source_goal = uow.profiles_goals.get_goal(owner_id, evidence.goal_id)
        assert source_goal is not None
        graph_version_id = source_goal.graph_version_id

    source_id = evidence.goal_id
    target_id = _create_peer_goal(client, graph_version_id, "target")
    unrelated_id = _create_peer_goal(client, graph_version_id, "unrelated")
    all_goals = (source_id, target_id, unrelated_id)

    _warm(client, *all_goals)
    assert _memo_counts(engine, all_goals) == dict.fromkeys(all_goals, 1)

    # Assessment and dimension inserts invalidate the source memo, not peer memos.
    with uow_factory() as uow:
        perform_assessment(
            uow,
            FakeEvaluationAdapter(),
            owner_id,
            evaluation_request,
            clock=FixedProgressClock(),
        )
        uow.commit()
    assert _memo_counts(engine, all_goals) == {
        source_id: 0,
        target_id: 1,
        unrelated_id: 1,
    }

    _warm(client, source_id)
    with uow_factory() as uow:
        transfer_evidence(
            uow,
            owner_id,
            source_goal_id=source_id,
            source_evidence_id=evidence.id,
            target_goal_id=target_id,
            classification=TransferClassification.UNVERIFIED,
            rationale="Fixture transfer for memo invalidation.",
            recommended_depth="essential",
            clock=FixedProgressClock(),
        )
        uow.commit()
    assert _memo_counts(engine, all_goals) == {
        source_id: 1,
        target_id: 0,
        unrelated_id: 1,
    }

    # Rolling back the correction restores the memo deleted by its trigger.
    _warm(client, target_id)
    connection = engine.connect()
    transaction = connection.begin()
    try:
        connection.execute(
            text(
                "INSERT INTO learner_corrections "
                "(id,owner_id,goal_id,topic_stable_id,correction_type,body_hash,"
                "created_at,supersedes_correction_id) "
                "VALUES ('rolled-back-correction',:owner_id,:goal_id,:topic_id,"
                "'correction','rollback-hash',:created_at,NULL)"
            ),
            {
                "owner_id": owner_id,
                "goal_id": source_id,
                "topic_id": evidence.topic_stable_id,
                "created_at": "2026-08-12T12:00:00.000000Z",
            },
        )
        connection.execute(
            text(
                "INSERT INTO learner_correction_bodies "
                "(correction_id,owner_id,goal_id,value,reason) VALUES "
                "('rolled-back-correction',:owner_id,:goal_id,'partial',"
                "'rollback fixture')"
            ),
            {"owner_id": owner_id, "goal_id": source_id},
        )
        assert (
            connection.execute(
                text("SELECT count(*) FROM goal_progress_memos WHERE goal_id=:goal_id"),
                {"goal_id": source_id},
            ).scalar_one()
            == 0
        )
        transaction.rollback()
    finally:
        connection.close()
    assert _memo_counts(engine, all_goals) == dict.fromkeys(all_goals, 1)

    # A source tombstone invalidates transfer targets but not unrelated goals.
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO evidence_tombstones "
                "(evidence_id,owner_id,goal_id,delete_operation_id,reason,tombstoned_at) "
                "VALUES (:evidence_id,:owner_id,:goal_id,'trigger-fixture-delete',"
                "'trigger fixture',:tombstoned_at)"
            ),
            {
                "evidence_id": evidence.id,
                "owner_id": owner_id,
                "goal_id": source_id,
                "tombstoned_at": "2026-08-12T12:00:00.000000Z",
            },
        )
    assert _memo_counts(engine, all_goals) == {
        source_id: 0,
        target_id: 0,
        unrelated_id: 1,
    }


def test_progress_memo_schema_has_closed_states_and_required_triggers(
    client: TestClient,
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
) -> None:
    client.app.state.clock = FixedProgressClock()
    _owner_id, evidence, _rubric, _request = _arrange(uow_factory)
    _warm(client, evidence.goal_id)

    expected_triggers = {
        "trg_progress_invalidate_evidence",
        "trg_progress_invalidate_assessment_insert",
        "trg_progress_invalidate_dimension_insert",
        "trg_progress_invalidate_assessment_update",
        "trg_progress_invalidate_correction",
        "trg_progress_invalidate_transfer",
        "trg_progress_invalidate_state_update",
        "trg_progress_invalidate_tombstone",
    }
    with engine.connect() as connection:
        actual_triggers = set(
            connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='trigger'")
            ).scalars()
        )
    assert expected_triggers <= actual_triggers

    with (
        pytest.raises(IntegrityError, match="coverage_valid"),
        engine.begin() as connection,
    ):
        connection.execute(
            text(
                "UPDATE goal_progress_memo_bodies SET coverage='completed' "
                "WHERE goal_id=:goal_id"
            ),
            {"goal_id": evidence.goal_id},
        )
