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
from yuno.api.routes.events import router as events_router
from yuno.api.routes.evidence import router as evidence_router
from yuno.api.routes.evidence import run_assessment_job, run_reevaluation_job
from yuno.api.routes.imports import router as imports_router
from yuno.api.routes.imports import run_import_parse_job
from yuno.api.routes.interview import (
    router as interview_router,
)
from yuno.api.routes.interview import (
    run_mock_final_evaluation_job,
    run_mock_next_turn_job,
    run_practice_evaluation_job,
)
from yuno.api.routes.jobs import router as jobs_router
from yuno.api.routes.learning_content import router as learning_content_router
from yuno.api.routes.notebook_review import router as notebook_review_router
from yuno.api.routes.profiles_goals import router as profiles_goals_router
from yuno.api.routes.provenance import router as provenance_router
from yuno.api.routes.roadmap import router as roadmap_router
from yuno.api.routes.settings_data import router as settings_data_router
from yuno.api.routes.system import router as system_router
from yuno.config import Settings, get_settings
from yuno.modules.identity.service import ensure_local_owner
from yuno.modules.jobs_events.service import DurableJobDispatcher
from yuno.modules.learning_content.service import run_generation
from yuno.modules.notebook_review.service import FixtureReviewScheduler
from yuno.modules.profiles_goals.service import ensure_profile
from yuno.modules.settings_data.service import ensure_owner_settings
from yuno.shared.application.jobs import (
    JobCompletion,
    JobExecution,
    JobPreparedFailure,
    JobResult,
)
from yuno.shared.domain.clock import SystemClock
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.infrastructure.alembic_guard import require_single_head
from yuno.shared.infrastructure.database import (
    create_engine_for,
    create_session_factory,
)
from yuno.unit_of_work import (
    create_probe_unit_of_work_factory,
    create_transaction_unit_of_work_factory,
    create_unit_of_work_factory,
)

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

            dispatcher = DurableJobDispatcher(
                session_factory,
                pending_cap=lambda: resolved_settings.pending_job_cap,
                background_age_promotion_seconds=lambda: (
                    resolved_settings.background_job_age_promotion_seconds
                ),
                janitor_retention_seconds=lambda: (
                    resolved_settings.job_janitor_retention_seconds
                ),
            )

            def result_for(kind: str, execution: JobExecution) -> JobResult:
                result_ref = (
                    execution.request.request_ref
                    or f"{kind}:{execution.request.requested_job_id}"
                )
                return JobResult(
                    kind,
                    execution.request.schema_version,
                    result_ref,
                    hash_payload({"result_ref": result_ref}),
                )

            def job_handler(kind, operation):
                def handle(execution: JobExecution) -> JobCompletion:
                    execution.checkpoint()
                    return JobCompletion(
                        result_for(kind, execution),
                        lambda session: apply_operation(
                            kind, execution, session, operation
                        ),
                    )

                return handle

            def apply_operation(kind, execution, session, operation, adapter=None):
                try:
                    args = (
                        execution.request,
                        create_transaction_unit_of_work_factory(session),
                    )
                    published = (
                        operation(*args, adapter) if adapter else operation(*args)
                    )
                except JobPreparedFailure:
                    raise
                except Exception as exc:
                    raise JobPreparedFailure(f"{type(exc).__name__}: {exc}") from exc
                if published is None:
                    if not execution.request.request_ref:
                        raise RuntimeError(
                            f"Job {kind!r} did not publish an authoritative domain entity."
                        )
                    return JobResult(
                        kind,
                        execution.request.schema_version,
                        execution.request.request_ref,
                        hash_payload(execution.request.request_ref),
                    )
                return domain_result(kind, execution, published)

            class ExternalCallCaptured(BaseException):
                def __init__(self, call_args, call_kwargs) -> None:
                    self.call_args = call_args
                    self.call_kwargs = call_kwargs

            class CaptureAdapter:
                def __init__(self, method: str) -> None:
                    self.method = method

                def __getattr__(self, name: str):
                    if name != self.method:
                        raise AttributeError(name)

                    def capture(*args, **kwargs):
                        raise ExternalCallCaptured(args, kwargs)

                    return capture

            class ReplayAdapter:
                def __init__(
                    self, method: str, value: object, failure: Exception | None
                ) -> None:
                    self.method = method
                    self.value = value
                    self.failure = failure

                def __getattr__(self, name: str):
                    if name != self.method:
                        raise AttributeError(name)

                    def replay(*_args, **_kwargs):
                        if self.failure is not None:
                            raise JobPreparedFailure(
                                f"{type(self.failure).__name__}: {self.failure}"
                            ) from self.failure
                        return self.value

                    return replay

            def external_job_handler(kind, operation, adapter_provider, method):
                def handle(execution: JobExecution) -> JobCompletion:
                    execution.checkpoint()
                    captured = None
                    preparation_failure = None
                    try:
                        operation(
                            execution.request,
                            create_probe_unit_of_work_factory(session_factory),
                            CaptureAdapter(method),
                        )
                    except ExternalCallCaptured as call:
                        captured = call
                    except Exception as exc:  # noqa: BLE001 -- replay domain failure transactionally
                        preparation_failure = exc
                    execution.checkpoint()
                    external_failure = preparation_failure
                    external_result = None
                    if captured is not None:
                        try:
                            external_result = getattr(adapter_provider(), method)(
                                *captured.call_args, **captured.call_kwargs
                            )
                        except Exception as exc:  # noqa: BLE001 -- provider boundary
                            external_failure = exc
                    elif preparation_failure is None:
                        external_failure = RuntimeError(
                            f"Job {kind!r} did not reach its external operation."
                        )
                    execution.checkpoint()
                    return JobCompletion(
                        result_for(kind, execution),
                        lambda session: apply_operation(
                            kind,
                            execution,
                            session,
                            operation,
                            ReplayAdapter(method, external_result, external_failure),
                        ),
                    )

                return handle

            def domain_result(
                kind: str, execution: JobExecution, published: object
            ) -> JobResult:
                entity_id = getattr(published, "id", None)
                if not entity_id:
                    raise RuntimeError(
                        f"Job {kind!r} did not publish an authoritative domain entity."
                    )
                return JobResult(
                    kind,
                    execution.request.schema_version,
                    f"{type(published).__name__}:{entity_id}",
                    hash_payload(published),
                )

            class UnavailableGenerationAdapter:
                provider = "unavailable"
                model = "unavailable"

                def generate(self, _request: object) -> None:
                    raise RuntimeError("Live generation is not configured.")

            app.state.generation_adapter = UnavailableGenerationAdapter()
            dispatcher.register(
                "generate_topic_content",
                external_job_handler(
                    "generate_topic_content",
                    lambda request, completion_uow_factory, adapter: run_generation(
                        completion_uow_factory,
                        adapter,
                        request.owner_id,
                        str(request.payload["attempt_id"]),
                    ),
                    lambda: app.state.generation_adapter,
                    "generate",
                ),
            )
            dispatcher.register(
                "parse_import",
                job_handler(
                    "parse_import",
                    lambda request, completion_uow_factory: run_import_parse_job(
                        request, completion_uow_factory
                    ),
                ),
            )
            dispatcher.register(
                "reprocess_import",
                job_handler(
                    "reprocess_import",
                    lambda request, completion_uow_factory: run_import_parse_job(
                        request, completion_uow_factory
                    ),
                ),
            )

            class UnavailableEvaluationAdapter:
                def evaluate(self, _request: object) -> None:
                    raise RuntimeError("Live evaluation is not configured.")

            app.state.evaluation_adapter = UnavailableEvaluationAdapter()

            class UnavailableMockInterviewAdapter:
                def next_question(self, _run: object) -> str:
                    raise RuntimeError(
                        "Live Mock question generation is not configured."
                    )

            app.state.mock_interview_adapter = UnavailableMockInterviewAdapter()
            dispatcher.register(
                "assess_evidence",
                external_job_handler(
                    "assess_evidence",
                    lambda request, completion_uow_factory, adapter: run_assessment_job(
                        request, completion_uow_factory, adapter
                    ),
                    lambda: app.state.evaluation_adapter,
                    "evaluate",
                ),
            )
            dispatcher.register(
                "reevaluate_assessment",
                external_job_handler(
                    "reevaluate_assessment",
                    lambda request, completion_uow_factory, adapter: (
                        run_reevaluation_job(request, completion_uow_factory, adapter)
                    ),
                    lambda: app.state.evaluation_adapter,
                    "evaluate",
                ),
            )
            dispatcher.register(
                "evaluate_practice_answer",
                external_job_handler(
                    "evaluate_practice_answer",
                    lambda request, completion_uow_factory, adapter: (
                        run_practice_evaluation_job(
                            request, completion_uow_factory, adapter
                        )
                    ),
                    lambda: app.state.evaluation_adapter,
                    "evaluate",
                ),
            )
            dispatcher.register(
                "generate_mock_next_turn",
                external_job_handler(
                    "generate_mock_next_turn",
                    lambda request, completion_uow_factory, adapter: (
                        run_mock_next_turn_job(
                            request,
                            completion_uow_factory,
                            adapter,
                        )
                    ),
                    lambda: app.state.mock_interview_adapter,
                    "next_question",
                ),
            )
            dispatcher.register(
                "evaluate_mock_final",
                external_job_handler(
                    "evaluate_mock_final",
                    lambda request, completion_uow_factory, adapter: (
                        run_mock_final_evaluation_job(
                            request,
                            completion_uow_factory,
                            adapter,
                        )
                    ),
                    lambda: app.state.evaluation_adapter,
                    "evaluate",
                ),
            )
            dispatcher.start()

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
            durable_dispatcher = locals().get("dispatcher")
            if durable_dispatcher is not None:
                durable_dispatcher.stop()
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
    api_router.include_router(interview_router)
    api_router.include_router(roadmap_router)
    api_router.include_router(evidence_router)
    api_router.include_router(notebook_review_router)
    api_router.include_router(provenance_router)
    api_router.include_router(settings_data_router)
    api_router.include_router(jobs_router)
    api_router.include_router(events_router)
    app.include_router(api_router)

    register_exception_handlers(app)
    app.add_middleware(CorrelationIdMiddleware)

    return app
