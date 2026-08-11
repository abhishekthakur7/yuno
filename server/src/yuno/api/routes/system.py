"""`GET /api/v1/health` (spec §5.2)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from yuno.api.contracts import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    """Liveness/readiness probe. The server only starts once
    `api.app.create_app` has confirmed a single Alembic head, so a `200`
    here implies the schema is at a known revision.
    """
    return HealthResponse(status="ok", schema_revision=request.app.state.head_revision)
