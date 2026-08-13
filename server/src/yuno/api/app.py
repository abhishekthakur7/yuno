"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from tempfile import gettempdir

from fastapi import APIRouter, FastAPI
from sqlalchemy import text

from yuno.api.contracts import ErrorResponse
from yuno.api.errors import register_exception_handlers
from yuno.api.middleware import CorrelationIdMiddleware
from yuno.api.provider_runtime import (
    ProviderEvaluationAdapter,
    ProviderGenerationAdapter,
    ProviderMockInterviewAdapter,
    ProviderTutorAdapter,
)
from yuno.api.provider_selection import ProviderAwareJobDispatcher
from yuno.api.routes.canonical import router as canonical_router
from yuno.api.routes.canonical_updates import router as canonical_updates_router
from yuno.api.routes.data_lifecycle import router as data_lifecycle_router
from yuno.api.routes.diagnostics import router as diagnostics_router
from yuno.api.routes.events import router as events_router
from yuno.api.routes.evidence import router as evidence_router
from yuno.api.routes.evidence import run_assessment_job, run_reevaluation_job
from yuno.api.routes.hands_on import router as hands_on_router
from yuno.api.routes.hands_on import run_hands_on_review_job
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
from yuno.api.routes.provider import router as provider_router
from yuno.api.routes.roadmap import router as roadmap_router
from yuno.api.routes.runner import router as runner_router
from yuno.api.routes.search import router as search_router
from yuno.api.routes.settings_data import router as settings_data_router
from yuno.api.routes.system import router as system_router
from yuno.config import Settings, get_settings
from yuno.modules.data_lifecycle.repository import SqlAlchemyDataLifecycleRepository
from yuno.modules.data_lifecycle.service import (
    ApprovedCleanupRoots,
    RetentionPolicy,
    execute_pending_cleanup,
    run_retention_cycle,
    runner_workspace_path_ref,
)
from yuno.modules.evidence_evaluation.service import delete_goal
from yuno.modules.identity.service import ensure_local_owner
from yuno.modules.jobs_events.service import DurableJobDispatcher
from yuno.modules.learning_content.service import run_generation, run_tutor_turn_job
from yuno.modules.notebook_review.service import FixtureReviewScheduler
from yuno.modules.profiles_goals.service import ensure_profile
from yuno.modules.provenance.adapters import (
    HttpSourceRetrievalAdapter,
    remove_unreferenced_snapshots,
)
from yuno.modules.provenance.service import run_source_retrieval_job
from yuno.modules.provider.adapters import (
    FileSecureOutputStore,
    LocalProcessPort,
    remove_unreferenced_provider_outputs,
)
from yuno.modules.provider.claude import (
    CLAUDE_ADAPTER_VERSION,
    CLAUDE_CONTRACT_VERSION,
    CLAUDE_ENVIRONMENT_ALLOWLIST,
    CLAUDE_MODEL,
    ClaudeCapabilityClassification,
    ClaudeCliAdapter,
    discover_claude,
)
from yuno.modules.provider.codex import (
    CODEX_ENVIRONMENT_ALLOWLIST,
    CodexProviderAdapter,
    discover_codex,
)
from yuno.modules.provider.domain import (
    ProviderCapability,
    ProviderCapabilityState,
    ProviderName,
    ProviderTimers,
)
from yuno.modules.provider.registry import (
    ProviderRegistry,
    authentication_capability,
    missing_capability,
    resolve_safe_executable,
)
from yuno.modules.runner.adapters import LocalRunnerProcessPort, LocalTempWorkspace
from yuno.modules.runner.repository import RunnerRepository
from yuno.modules.runner.service import execute_runner_job
from yuno.modules.search.service import rebuild_search_projection
from yuno.modules.settings_data.service import (
    build_export_package,
    ensure_owner_settings,
    publish_export_package,
)
from yuno.shared.application.jobs import (
    JobCompletion,
    JobExecution,
    JobLane,
    JobPreparedFailure,
    JobRequest,
    JobResult,
)
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.infrastructure.alembic_guard import require_single_head
from yuno.shared.infrastructure.database import (
    create_engine_for,
    create_session_factory,
)
from yuno.shared.infrastructure.structured_logging import (
    configure_file_structured_logging,
    expire_structured_log_files,
    log_event,
)
from yuno.unit_of_work import (
    create_probe_unit_of_work_factory,
    create_transaction_unit_of_work_factory,
    create_unit_of_work_factory,
)


class _CancellableSourceAdapter:
    def __init__(self, adapter, cancelled: Callable[[], bool]) -> None:
        self._adapter = adapter
        self._cancelled = cancelled

    def retrieve(self, request):
        return self._adapter.retrieve(request, cancelled=self._cancelled)


API_PREFIX = "/api/v1"
RETENTION_INTERVAL_SECONDS = 3600


def _rebuild_search(request: JobRequest, uow_factory):
    return rebuild_search_projection(
        uow_factory, request.owner_id, request.requested_job_id or "unknown"
    )


def _build_export(request: JobRequest, uow_factory, settings: Settings):
    with uow_factory() as read_uow:
        return build_export_package(
            read_uow,
            request.owner_id,
            str(request.payload["operation_id"]),
            package_retention_seconds=settings.export_package_retention_seconds,
            metadata_retention_days=settings.export_operation_retention_days,
        )


def _publish_export(package, uow_factory):
    with uow_factory() as write_uow:
        operation = publish_export_package(write_uow, package)
        write_uow.commit()
        return operation


def _complete_delete(request: JobRequest, uow_factory):
    with uow_factory() as uow:
        operation_id = str(request.payload["operation_id"])
        delete_goal(
            uow,
            request.owner_id,
            str(request.goal_id),
            str(request.payload["snapshot_id"]),
        )
        uow.settings_data.complete_delete(
            request.owner_id, operation_id, now_text(SystemClock())
        )
        uow.commit()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application; tests may inject scratch-database settings."""
    resolved_settings = settings if settings is not None else get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # The server refuses to start against a non-head database.
        engine = create_engine_for(resolved_settings.database_url)
        try:
            head_revision = require_single_head(engine)
            configure_file_structured_logging(
                resolved_settings.structured_log_directory,
                max_bytes=resolved_settings.structured_log_file_max_bytes,
                backup_count=resolved_settings.structured_log_file_count - 1,
                max_age=timedelta(days=resolved_settings.structured_log_retention_days),
            )

            session_factory = create_session_factory(engine)
            uow_factory = create_unit_of_work_factory(session_factory)

            # Provision the singleton local owner before accepting traffic.
            with uow_factory() as uow:
                owner = ensure_local_owner(uow, resolved_settings.owner_display_name)
                ensure_profile(uow, owner.id)
                ensure_owner_settings(uow, owner.id)
                uow.commit()

            retention_policy = RetentionPolicy(
                diagnostic_days=resolved_settings.diagnostic_abandoned_retention_days,
                interview_days=resolved_settings.interview_inactive_retention_days,
                terminal_job_days=resolved_settings.terminal_job_retention_days,
                job_event_days=resolved_settings.job_event_retention_days,
                job_event_owner_limit=resolved_settings.job_event_owner_limit,
                runner_output_days=resolved_settings.runner_output_retention_days,
            )
            cleanup_roots = ApprovedCleanupRoots(
                runner=Path(gettempdir()),
                source=resolved_settings.source_snapshot_root,
                quarantine=resolved_settings.provider_quarantine_root,
            )

            def apply_retention() -> None:
                expire_structured_log_files()
                try:
                    retained, cleaned = run_retention_cycle(
                        uow_factory,
                        owner.id,
                        now=SystemClock().now(),
                        roots=cleanup_roots,
                        policy=retention_policy,
                    )
                except Exception:  # noqa: BLE001 -- safe classification is visible
                    app.state.retention_failure_classification = (
                        "retention-cycle-failed"
                    )
                    log_event(
                        "retention.cycle.failed",
                        owner_id=owner.id,
                        lifecycle="failed",
                        diagnostic_classification="retention-cycle-failed",
                    )
                    return
                app.state.retention_failure_classification = (
                    "external-cleanup-failed" if cleaned.failed else None
                )
                app.state.last_retention_result = retained
                app.state.last_cleanup_result = cleaned
                log_event(
                    "retention.cycle.completed",
                    owner_id=owner.id,
                    lifecycle="complete" if not cleaned.failed else "failed",
                    diagnostic_classification=(
                        "external-cleanup-failed" if cleaned.failed else None
                    ),
                )

            def apply_external_cleanup(owner_id: str) -> None:
                execute_pending_cleanup(
                    uow_factory,
                    owner_id,
                    roots=cleanup_roots,
                    completed_at=now_text(SystemClock()),
                )

            def record_workspace_cleanup(
                session, owner_id: str, goal_id: str | None, raw_path: str
            ) -> str | None:
                path_ref = runner_workspace_path_ref(raw_path, cleanup_roots.runner)
                if path_ref is None:
                    return "cleanup-reference-invalid"
                SqlAlchemyDataLifecycleRepository(session).record_workspace(
                    owner_id=owner_id,
                    goal_id=goal_id,
                    path_ref=path_ref,
                    failure_classification=None,
                    created_at=now_text(SystemClock()),
                )
                return None

            async def periodically_apply_retention() -> None:
                while True:
                    await asyncio.sleep(RETENTION_INTERVAL_SECONDS)
                    await asyncio.to_thread(apply_retention)

            dispatcher = DurableJobDispatcher(
                session_factory,
                pending_cap=lambda: resolved_settings.pending_job_cap,
                background_age_promotion_seconds=lambda: (
                    resolved_settings.background_job_age_promotion_seconds
                ),
                janitor_retention_seconds=lambda: (
                    resolved_settings.job_janitor_retention_seconds
                ),
                record_workspace_cleanup=record_workspace_cleanup,
                execute_external_cleanup=apply_external_cleanup,
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

            def export_job_handler(execution: JobExecution) -> JobCompletion:
                execution.checkpoint()
                package = _build_export(
                    execution.request, uow_factory, resolved_settings
                )
                execution.checkpoint()
                return JobCompletion(
                    result_for("export_data", execution),
                    lambda session: apply_operation(
                        "export_data",
                        execution,
                        session,
                        lambda _request, completion_uow_factory: _publish_export(
                            package, completion_uow_factory
                        ),
                    ),
                )

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
                    raise JobPreparedFailure("job-operation-failed") from exc
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
                                "external-operation-failed"
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
                            external_result = getattr(
                                adapter_provider(execution), method
                            )(*captured.call_args, **captured.call_kwargs)
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

            provider_process = LocalProcessPort()
            provider_store = FileSecureOutputStore(
                resolved_settings.provider_quarantine_root
            )
            provider_timers = ProviderTimers(
                resolved_settings.provider_first_output_seconds,
                resolved_settings.provider_inactivity_seconds,
                resolved_settings.provider_absolute_seconds,
            )
            provider_environment = {
                key: value
                for key in set(
                    CODEX_ENVIRONMENT_ALLOWLIST + CLAUDE_ENVIRONMENT_ALLOWLIST
                )
                if (value := os.getenv(key)) is not None
            }

            def codex_discovery():
                if not resolved_settings.provider_capability_discovery_enabled:
                    return authentication_capability(ProviderName.CODEX), None
                executable = resolve_safe_executable(
                    resolved_settings.provider_codex_executable
                )
                if executable is None:
                    return missing_capability(ProviderName.CODEX), None
                capability = discover_codex(
                    str(executable),
                    provider_process,
                    timers=provider_timers,
                    source_environment=provider_environment,
                )
                if capability.state is not ProviderCapabilityState.CONFIGURED:
                    return capability, None
                return capability, CodexProviderAdapter(
                    executable=str(executable),
                    temp_root=Path(gettempdir()),
                    timers=provider_timers,
                    process_port=provider_process,
                    secure_output_store=provider_store,
                    source_environment=provider_environment,
                )

            def claude_discovery():
                if not resolved_settings.provider_capability_discovery_enabled:
                    return authentication_capability(ProviderName.CLAUDE), None
                discovered = discover_claude(
                    str(resolved_settings.provider_claude_executable),
                    process_port=provider_process,
                    probe_timers=provider_timers,
                    source_environment=provider_environment,
                )
                state = {
                    ClaudeCapabilityClassification.EXECUTABLE_MISSING: (
                        ProviderCapabilityState.EXECUTABLE_MISSING
                    ),
                    ClaudeCapabilityClassification.UNSUPPORTED_VERSION: (
                        ProviderCapabilityState.UNSUPPORTED_VERSION
                    ),
                    ClaudeCapabilityClassification.AUTHENTICATION_UNAVAILABLE: (
                        ProviderCapabilityState.AUTHENTICATION_UNAVAILABLE
                    ),
                    ClaudeCapabilityClassification.CONFIGURED: (
                        ProviderCapabilityState.CONFIGURED
                    ),
                }[discovered.classification]
                if state is ProviderCapabilityState.EXECUTABLE_MISSING:
                    return missing_capability(ProviderName.CLAUDE), None
                if state is ProviderCapabilityState.UNSUPPORTED_VERSION:
                    return ProviderCapability(
                        ProviderName.CLAUDE,
                        state,
                        "The executable could not be identified or lacks the required command surface.",
                        "Install a CLI build with the required command surface, then refresh.",
                    ), None
                if state is ProviderCapabilityState.AUTHENTICATION_UNAVAILABLE:
                    return authentication_capability(ProviderName.CLAUDE), None
                assert discovered.executable is not None
                capability = ProviderCapability(
                    ProviderName.CLAUDE,
                    state,
                    model=CLAUDE_MODEL,
                    adapter_version=CLAUDE_ADAPTER_VERSION,
                    contract_version=CLAUDE_CONTRACT_VERSION,
                )
                return capability, ClaudeCliAdapter(
                    executable=discovered.executable,
                    process_port=provider_process,
                    secure_output_store=provider_store,
                    source_environment=provider_environment,
                    timers=provider_timers,
                    temp_root=Path(gettempdir()),
                )

            app.state.provider_registry = ProviderRegistry(
                {
                    ProviderName.CODEX: codex_discovery,
                    ProviderName.CLAUDE: claude_discovery,
                }
            )
            app.state.provider_registry.refresh()
            provider_dispatcher = ProviderAwareJobDispatcher(
                dispatcher, uow_factory, app.state.provider_registry
            )
            source_retrieval_adapter = HttpSourceRetrievalAdapter(
                resolved_settings.source_snapshot_root
            )
            app.state.source_retrieval_adapter = source_retrieval_adapter
            dispatcher.register(
                "generate_topic_content",
                external_job_handler(
                    "generate_topic_content",
                    lambda request, completion_uow_factory, adapter: run_generation(
                        completion_uow_factory,
                        adapter,
                        request.owner_id,
                        str(request.payload["attempt_id"]),
                        max_body_bytes=resolved_settings.generated_body_max_bytes,
                        retained_owner_limit=(
                            resolved_settings.generated_retained_owner_limit
                        ),
                    ),
                    lambda execution: ProviderGenerationAdapter(app, execution),
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

            dispatcher.register(
                "assess_evidence",
                external_job_handler(
                    "assess_evidence",
                    lambda request, completion_uow_factory, adapter: run_assessment_job(
                        request, completion_uow_factory, adapter
                    ),
                    lambda execution: ProviderEvaluationAdapter(app, execution),
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
                    lambda execution: ProviderEvaluationAdapter(app, execution),
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
                    lambda execution: ProviderEvaluationAdapter(app, execution),
                    "evaluate",
                ),
            )
            dispatcher.register(
                "review_hands_on_artifact",
                external_job_handler(
                    "review_hands_on_artifact",
                    lambda request, completion_uow_factory, adapter: (
                        run_hands_on_review_job(
                            request, completion_uow_factory, adapter
                        )
                    ),
                    lambda execution: ProviderEvaluationAdapter(app, execution),
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
                    lambda execution: ProviderMockInterviewAdapter(app, execution),
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
                    lambda execution: ProviderEvaluationAdapter(app, execution),
                    "evaluate",
                ),
            )
            dispatcher.register(
                "tutor_turn",
                external_job_handler(
                    "tutor_turn",
                    lambda request, completion_uow_factory, adapter: run_tutor_turn_job(
                        request, completion_uow_factory, adapter
                    ),
                    lambda execution: ProviderTutorAdapter(app, execution),
                    "respond",
                ),
            )
            dispatcher.register(
                "retrieve_source_snapshot",
                external_job_handler(
                    "retrieve_source_snapshot",
                    lambda request, completion_uow_factory, adapter: (
                        run_source_retrieval_job(
                            request, completion_uow_factory, adapter
                        )
                    ),
                    lambda execution: _CancellableSourceAdapter(
                        app.state.source_retrieval_adapter,
                        execution.cancel_requested,
                    ),
                    "retrieve",
                ),
            )
            app.state.runner_process_port = LocalRunnerProcessPort()
            app.state.runner_workspace_port = LocalTempWorkspace()
            dispatcher.register(
                "java_runner",
                lambda execution: execute_runner_job(
                    execution,
                    session_factory,
                    resolved_settings,
                    app.state.runner_process_port,
                    app.state.runner_workspace_port,
                    SqlAlchemyDataLifecycleRepository,
                    lambda path: runner_workspace_path_ref(path, cleanup_roots.runner),
                ),
            )
            dispatcher.register(
                "rebuild_index",
                job_handler(
                    "rebuild_index",
                    lambda request, completion_uow_factory: _rebuild_search(
                        request, completion_uow_factory
                    ),
                ),
            )
            dispatcher.register("export_data", export_job_handler)
            dispatcher.register(
                "delete_goal", job_handler("delete_goal", _complete_delete)
            )

            with session_factory() as runner_session:
                runner_repo = RunnerRepository(runner_session)
                pending_runner = tuple(
                    (
                        record,
                        runner_repo.confirmation(
                            record.owner_id, record.confirmation_id
                        ),
                    )
                    for record in runner_repo.pending_dispatch_records()
                )
            for record, confirmation in pending_runner:
                if confirmation is None or confirmation.idempotency_key is None:
                    continue
                try:
                    dispatcher.enqueue(
                        JobRequest(
                            "java_runner",
                            record.owner_id,
                            {"run_id": record.id},
                            record.id,
                            confirmation.idempotency_key,
                            requested_job_id=record.id,
                            goal_id=record.goal_id,
                            lane=JobLane.INTERACTIVE,
                            schema_version="runner-v1",
                            request_ref=f"RunnerRun:{record.id}",
                            confirmation_ref=confirmation.id,
                            run_id=record.id,
                        )
                    )
                except Exception:  # noqa: BLE001,S112 - durable reservation remains queued
                    continue
            with session_factory() as reconciliation_session:
                referenced_snapshots = set(
                    reconciliation_session.scalars(
                        text("SELECT content_ref FROM source_snapshot_bodies")
                    )
                )
                referenced_provider_outputs = set(
                    reconciliation_session.scalars(
                        text("SELECT raw_output_ref FROM schema_quarantine_bodies")
                    )
                )
            remove_unreferenced_snapshots(
                resolved_settings.source_snapshot_root, referenced_snapshots
            )
            remove_unreferenced_provider_outputs(
                resolved_settings.provider_quarantine_root,
                referenced_provider_outputs,
            )
            dispatcher.start()

            # Startup reconciliation and its one-hour runner janitor run first;
            # retention still completes before the app accepts traffic.
            apply_retention()
            retention_task = asyncio.create_task(periodically_apply_retention())

            with uow_factory() as followup_uow:
                pending_followups = (
                    followup_uow.canonical_merges.list_pending_merge_followups()
                )
            for followup in pending_followups:
                if followup.kind != "reprocess_import":
                    continue
                try:
                    ref = dispatcher.enqueue(
                        JobRequest(
                            kind="reprocess_import",
                            owner_id=followup.owner_id,
                            goal_id=followup.goal_id,
                            payload=followup.payload,
                            dedupe_key=str(followup.payload["import_id"]),
                            idempotency_key=f"canonical-merge:{followup.proposal_id}:{followup.id}",
                            request_ref=f"ImportRecord:{followup.payload['import_id']}",
                        )
                    )
                except Exception:  # noqa: BLE001,S112 - durable intent remains pending
                    continue
                with uow_factory() as followup_uow:
                    followup_uow.canonical_merges.mark_followup_dispatched(
                        followup.owner_id, followup.id, ref.job_id
                    )
                    followup_uow.commit()

            app.state.engine = engine
            app.state.session_factory = session_factory
            app.state.uow_factory = uow_factory
            app.state.dispatcher = provider_dispatcher
            app.state.settings = resolved_settings
            app.state.head_revision = head_revision
            app.state.clock = SystemClock()
            app.state.review_scheduler = FixtureReviewScheduler()

            yield
        finally:
            periodic_retention = locals().get("retention_task")
            if periodic_retention is not None:
                periodic_retention.cancel()
                try:
                    await periodic_retention
                except asyncio.CancelledError:
                    pass
            durable_dispatcher = locals().get("dispatcher")
            if durable_dispatcher is not None:
                durable_dispatcher.stop()
            retrieval_adapter = locals().get("source_retrieval_adapter")
            if retrieval_adapter is not None:
                retrieval_adapter.close()
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
    api_router.include_router(data_lifecycle_router)
    api_router.include_router(canonical_updates_router)
    api_router.include_router(profiles_goals_router)
    api_router.include_router(diagnostics_router)
    api_router.include_router(learning_content_router)
    api_router.include_router(imports_router)
    api_router.include_router(interview_router)
    api_router.include_router(roadmap_router)
    api_router.include_router(evidence_router)
    api_router.include_router(hands_on_router)
    api_router.include_router(notebook_review_router)
    api_router.include_router(provenance_router)
    api_router.include_router(provider_router)
    api_router.include_router(settings_data_router)
    api_router.include_router(search_router)
    api_router.include_router(jobs_router)
    api_router.include_router(runner_router)
    api_router.include_router(events_router)
    app.include_router(api_router)

    register_exception_handlers(app)
    app.add_middleware(CorrelationIdMiddleware)

    return app
