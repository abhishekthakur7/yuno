"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from yuno.api.contracts import ErrorResponse
from yuno.api.errors import register_exception_handlers
from yuno.api.middleware import CorrelationIdMiddleware
from yuno.api.routes.canonical import router as canonical_router
from yuno.api.routes.diagnostics import router as diagnostics_router
from yuno.api.routes.evidence import router as evidence_router
from yuno.api.routes.evidence import run_assessment_job, run_reevaluation_job
from yuno.api.routes.imports import router as imports_router
from yuno.api.routes.imports import run_import_parse_job
from yuno.api.routes.learning_content import router as learning_content_router
from yuno.api.routes.notebook_review import router as notebook_review_router
from yuno.api.routes.profiles_goals import router as profiles_goals_router
from yuno.api.routes.provenance import router as provenance_router
from yuno.api.routes.roadmap import router as roadmap_router
from yuno.api.routes.settings_data import router as settings_data_router
from yuno.api.routes.system import router as system_router
from yuno.config import Settings, get_settings
from yuno.modules.identity.service import ensure_local_owner
from yuno.modules.learning_content.service import run_generation
from yuno.modules.notebook_review.service import FixtureReviewScheduler
from yuno.modules.profiles_goals.service import ensure_profile
from yuno.modules.settings_data.service import ensure_owner_settings
from yuno.shared.domain.clock import SystemClock
from yuno.shared.infrastructure.alembic_guard import require_single_head
from yuno.shared.infrastructure.database import (
    create_engine_for,
    create_session_factory,
)
from yuno.shared.infrastructure.jobs import InProcessJobDispatcher
from yuno.unit_of_work import create_unit_of_work_factory

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application; tests may inject scratch-database settings."""
    resolved_settings = settings if settings is not None else get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # The server refuses to start against a non-head database.
        engine = create_engine_for(resolved_settings.database_url)
        try:
            head_revision = require_single_head(engine)

            session_factory = create_session_factory(engine)
            uow_factory = create_unit_of_work_factory(session_factory)

            # Provision the singleton local owner before accepting traffic.
            with uow_factory() as uow:
                owner = ensure_local_owner(uow, resolved_settings.owner_display_name)
                ensure_profile(uow, owner.id)
                ensure_owner_settings(uow, owner.id)
                uow.commit()

            dispatcher = InProcessJobDispatcher()

            class UnavailableGenerationAdapter:
                provider = "unavailable"
                model = "unavailable"

                def generate(self, _request: object) -> None:
                    raise RuntimeError("Live generation is not configured.")

            app.state.generation_adapter = UnavailableGenerationAdapter()
            dispatcher.register(
                "generate_topic_content",
                lambda request: run_generation(
                    uow_factory,
                    app.state.generation_adapter,
                    request.owner_id,
                    str(request.payload["attempt_id"]),
                ),
            )
            dispatcher.register(
                "parse_import",
                lambda request: run_import_parse_job(request, uow_factory),
            )
            dispatcher.register(
                "reprocess_import",
                lambda request: run_import_parse_job(request, uow_factory),
            )

            class UnavailableEvaluationAdapter:
                def evaluate(self, _request: object) -> None:
                    raise RuntimeError("Live evaluation is not configured.")

            app.state.evaluation_adapter = UnavailableEvaluationAdapter()
            dispatcher.register(
                "assess_evidence",
                lambda request: run_assessment_job(
                    request, uow_factory, app.state.evaluation_adapter
                ),
            )
            dispatcher.register(
                "reevaluate_assessment",
                lambda request: run_reevaluation_job(
                    request, uow_factory, app.state.evaluation_adapter
                ),
            )

            app.state.engine = engine
            app.state.session_factory = session_factory
            app.state.uow_factory = uow_factory
            app.state.dispatcher = dispatcher
            app.state.settings = resolved_settings
            app.state.head_revision = head_revision
            app.state.clock = SystemClock()
            app.state.review_scheduler = FixtureReviewScheduler()

            yield
        finally:
            # Dispose the pool even when startup fails.
            engine.dispose()

    app = FastAPI(title="Yuno", version="0.1.0", lifespan=lifespan)

    # Router responses apply to every route. Async routes declare their own
    # 202 response so synchronous routes do not advertise a phantom status.
    api_router = APIRouter(
        prefix=API_PREFIX,
        responses={"default": {"model": ErrorResponse}},
    )
    api_router.include_router(system_router)
    api_router.include_router(canonical_router)
    api_router.include_router(profiles_goals_router)
    api_router.include_router(diagnostics_router)
    api_router.include_router(learning_content_router)
    api_router.include_router(imports_router)
    api_router.include_router(roadmap_router)
    api_router.include_router(evidence_router)
    api_router.include_router(notebook_review_router)
    api_router.include_router(provenance_router)
    api_router.include_router(settings_data_router)
    app.include_router(api_router)

    register_exception_handlers(app)
    app.add_middleware(CorrelationIdMiddleware)

    return app
