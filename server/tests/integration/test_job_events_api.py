"""IDK-402 persisted replay and wire-contract coverage."""

from __future__ import annotations

import json

from sqlalchemy import select

from yuno.api.routes.events import KEEPALIVE_FRAME, event_frame, event_payload
from yuno.modules.identity.models import OwnerRow
from yuno.modules.jobs_events.repository import JobRepository
from yuno.shared.application.jobs import JobLane, JobRequest
from yuno.shared.domain.clock import SystemClock


def test_owner_scoped_replay_is_strictly_after_cursor_in_event_id_order(
    client, session_factory
):
    assert client.get("/api/v1/jobs").status_code == 200
    with session_factory() as session:
        owner_id = session.scalar(select(OwnerRow.id))
        assert owner_id is not None
        repo = JobRepository(session, SystemClock())
        repo.enqueue(
            JobRequest(
                kind="index-search",
                owner_id=owner_id,
                payload={"fixture": 1},
                lane=JobLane.BACKGROUND,
                request_id="request-1",
                correlation_id="correlation-1",
            ),
            JobLane.BACKGROUND,
        )
        second_job = repo.enqueue(
            JobRequest(
                kind="tutor_turn",
                owner_id=owner_id,
                payload={"fixture": 2},
                lane=JobLane.INTERACTIVE,
                request_id="request-2",
                correlation_id="correlation-2",
                run_id="run-2",
            ),
            JobLane.INTERACTIVE,
        )
        session.commit()
        all_events = repo.list_events_after(owner_id, None)
        cursor = all_events[-2].event_id
        replay = repo.list_events_after(owner_id, cursor)
        assert [row.job_id for row in replay] == [second_job.id]
        assert repo.list_events_after("not-the-owner", None) == ()

        payload = event_payload(replay[0]).model_dump(mode="json")
        assert set(payload) == {
            "event_id", "job_id", "owner_id", "goal_id", "state",
            "event_type", "timestamp", "progress", "result_ref", "retryable",
            "request_id", "correlation_id", "run_id",
        }
        assert payload["request_id"] == "request-2"
        assert payload["correlation_id"] == "correlation-2"
        assert payload["run_id"] == "run-2"

        frame = event_frame(replay[0])
        assert frame.startswith(f"id: {replay[0].event_id}\nevent: job\ndata: ")
        encoded = json.loads(frame.split("data: ", 1)[1].strip())
        assert encoded == payload


def test_unknown_replay_cursor_replays_retained_events_and_keepalive_is_transport_only(
    client, session_factory
):
    assert client.get("/api/v1/jobs").status_code == 200
    with session_factory() as session:
        owner_id = session.scalar(select(OwnerRow.id))
        assert owner_id is not None
        replay = JobRepository(session, SystemClock()).list_events_after(
            owner_id, "expired-event-id"
        )
        assert tuple(row.event_id for row in replay) == tuple(
            sorted(row.event_id for row in replay)
        )
    assert KEEPALIVE_FRAME.startswith(":")
    assert "event:" not in KEEPALIVE_FRAME
    assert "data:" not in KEEPALIVE_FRAME
