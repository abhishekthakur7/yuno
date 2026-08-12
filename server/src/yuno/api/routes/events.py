from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, sessionmaker

from yuno.api.contracts import JobEventResponse
from yuno.api.dependencies import get_owner_id
from yuno.modules.jobs_events.models import JobEventRow
from yuno.modules.jobs_events.repository import JobRepository
from yuno.shared.domain.clock import Clock

router = APIRouter(tags=["events"])
KEEPALIVE_FRAME = ": keepalive\n\n"


def event_payload(row: JobEventRow) -> JobEventResponse:
    return JobEventResponse(
        event_id=row.event_id,
        job_id=row.job_id,
        owner_id=row.owner_id,
        goal_id=row.goal_id,
        state=row.state,
        event_type=row.type,
        timestamp=row.created_at,
        progress=row.progress,
        result_ref=row.result_ref,
        retryable=bool(row.retryable),
        request_id=row.request_id,
        correlation_id=row.correlation_id,
        run_id=row.run_id,
    )


def event_frame(row: JobEventRow) -> str:
    payload = event_payload(row).model_dump_json()
    return f"id: {row.event_id}\nevent: job\ndata: {payload}\n\n"


def retained_event_frames(
    session_factory: sessionmaker[Session],
    clock: Clock,
    owner_id: str,
    last_event_id: str | None,
) -> tuple[tuple[str, str], ...]:
    with session_factory() as session:
        rows = JobRepository(session, clock).list_events_after(owner_id, last_event_id)
        return tuple((row.event_id, event_frame(row)) for row in rows)


async def stream_events(
    request: Request,
    owner_id: str,
    last_event_id: str | None,
) -> AsyncIterator[str]:
    cursor = last_event_id
    while not await request.is_disconnected():
        frames = retained_event_frames(
            request.app.state.session_factory,
            request.app.state.clock,
            owner_id,
            cursor,
        )
        if frames:
            for cursor, frame in frames:
                yield frame
        else:
            # Comments keep the connection alive without creating MessageEvents.
            yield KEEPALIVE_FRAME
        await asyncio.sleep(1)


@router.get(
    "/events",
    response_class=StreamingResponse,
    responses={
        200: {
            "model": JobEventResponse,
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        }
    },
)
def get_events(
    request: Request,
    owner_id: Annotated[str, Depends(get_owner_id)],
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    return StreamingResponse(
        stream_events(request, owner_id, last_event_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
