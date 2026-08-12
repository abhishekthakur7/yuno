"""FastAPI application factory (spec §5.1).

Wires persistence, the Alembic single-head guard, the built-in local
owner, the in-process job dispatcher, and the API's exception/middleware
stack together. `yuno.main` is the only importer of `create_app`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from yuno.api.contracts import ErrorResponse
from yuno.api.errors import register_exception_handlers
from yuno.api.middleware import CorrelationIdMiddleware
from yuno.api.routes.canonical import router as canonical_router
from yuno.api.routes.diagnostics import router as diagnostics_router
from yuno.api.routes.learning_content import router as learning_content_router
from yuno.api.routes.profiles_goals import router as profiles_goals_router
from yuno.api.routes.roadmap import router as roadmap_router
from yuno.api.routes.system import router as system_router
from yuno.config import Settings, get_settings
from yuno.modules.identity.service import ensure_local_owner
from yuno.modules.profiles_goals.service import ensure_profile
from yuno.shared.infrastructure.alembic_guard import require_single_head
from yuno.shared.infrastructure.database import (
    create_engine_for,
    create_session_factory,
)
from yuno.shared.infrastructure.jobs import InProcessJobDispatcher
from yuno.unit_of_work import create_unit_of_work_factory

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the Yuno FastAPI application.

    `settings` is injectable so tests can point at a scratch database;
    production (`yuno.main`) always calls this with no argument.
    """
    resolved_settings = settings if settings is not None else get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # The server refuses to start against a non-head database.
        engine = create_engine_for(resolved_settings.database_url)
        try:
            head_revision = require_single_head(engine)

            session_factory = create_session_factory(engine)
            uow_factory = create_unit_of_work_factory(session_factory)

            # One UoW, one commit: provisions the singleton local owner
            # (idempotent) before the app accepts any traffic (DAT-01).
            with uow_factory() as uow:
                owner = ensure_local_owner(uow, resolved_settings.owner_display_name)
                ensure_profile(uow, owner.id)
                uow.commit()

            dispatcher = InProcessJobDispatcher()

            def unavailable_generation(_request: object) -> None:
                raise RuntimeError("Live generation is not configured.")

            dispatcher.register("generate_topic_content", unavailable_generation)
            dispatcher.register("regenerate_artifact", unavailable_generation)

            app.state.engine = engine
            app.state.session_factory = session_factory
            app.state.uow_factory = uow_factory
            app.state.dispatcher = dispatcher
            app.state.head_revision = head_revision

            yield
        finally:
            # In `try`/`finally` (matching `migrations/env.py`) so a startup
            # failure above still disposes the engine's connection pool
            # instead of leaking it until GC.
            engine.dispose()

    app = FastAPI(title="Yuno", version="0.1.0", lifespan=lifespan)

    # FastAPI merges router-level `responses` into every nested route's
    # OpenAPI and can't subtract them back out per-route, so only `default`
    # (universally true: any route can fail) goes here. `202` stays off —
    # most routes can only ever return `200`, so a router-level `202` would
    # be a phantom response degrading the generated TypeScript client's type
    # narrowing across the whole API surface. Each async endpoint instead
    # declares `responses={202: {"model": JobRefResponse}}` itself.
    api_router = APIRouter(
        prefix=API_PREFIX,
        responses={"default": {"model": ErrorResponse}},
    )
    api_router.include_router(system_router)
    api_router.include_router(canonical_router)
    api_router.include_router(profiles_goals_router)
    api_router.include_router(diagnostics_router)
    api_router.include_router(learning_content_router)
    api_router.include_router(roadmap_router)
    app.include_router(api_router)

    register_exception_handlers(app)
    app.add_middleware(CorrelationIdMiddleware)

    return app
