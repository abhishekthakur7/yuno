from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from io import StringIO

from yuno.api.contracts import safe_job_diagnostic
from yuno.api.routes.jobs import _attempt_response
from yuno.modules.identity.service import ensure_local_owner
from yuno.modules.jobs_events.service import DurableJobDispatcher
from yuno.modules.provider.domain import ProviderInput, ProviderName
from yuno.modules.provider.service import execute_provider
from yuno.shared.application.jobs import (
    JobAttempt,
    JobCompletion,
    JobRef,
    JobRequest,
    JobResult,
    JobStatus,
)
from yuno.shared.domain.errors import UnavailableError
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.infrastructure.structured_logging import (
    LOGGER_NAME,
    REDACTED,
    configure_structured_logging,
    log_event,
    redact_log_data,
)


class SecretBearingUnavailableAdapter:
    provider = ProviderName.CODEX.value
    adapter_version = "test-adapter-v1"
    contract_version = "final-json-v1"

    def __init__(self, secret: str) -> None:
        self.secret = secret
        self.source_environment = {
            "CODEX_API_TOKEN": secret,
            "AWS_SECRET_ACCESS_KEY": "aws-secret-never-log",
            "UNRELATED": "unrelated-environment-never-log",
        }

    def invoke(self, *_args, **_kwargs):
        raise UnavailableError(f"provider rejected auth value {self.secret}")


def _json_events(caplog) -> list[dict[str, object]]:
    return [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == LOGGER_NAME
    ]


@contextmanager
def _capture_logs(caplog):
    logger = logging.getLogger(LOGGER_NAME)
    logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            yield
    finally:
        logger.removeHandler(caplog.handler)


def test_recursive_redaction_covers_sensitive_categories_and_paths() -> None:
    sanitized = redact_log_data(
        {
            "authorization": "Bearer credential",
            "headers": {"Cookie": "session-cookie"},
            "provider_auth_env": {"CODEX_API_TOKEN": "provider-token"},
            "env": {"UNRELATED": "environment-value"},
            "aws_secret_access_key": "aws-secret",
            "workspace": "/Users/example/private/project",
            "nested": [
                {"raw_prompt": "prompt body"},
                {"transcript_body": "transcript body"},
                {"artifact_body": "artifact body"},
                {"quarantined_raw_output": b"invalid provider output"},
            ],
            "safe": "diagnostic-classification",
        }
    )

    serialized = json.dumps(sanitized)
    for forbidden in (
        "credential",
        "session-cookie",
        "provider-token",
        "environment-value",
        "aws-secret",
        "/Users/example",
        "prompt body",
        "transcript body",
        "artifact body",
        "invalid provider output",
    ):
        assert forbidden not in serialized
    assert sanitized["authorization"] == REDACTED
    assert sanitized["safe"] == "diagnostic-classification"


def test_ordinary_log_events_drop_non_allowlisted_payload_fields(caplog) -> None:
    with _capture_logs(caplog):
        log_event(
            "test.safe-event",
            owner_id="owner-safe",
            job_id="job-safe",
            diagnostic_classification="schema-invalid",
            raw_prompt="raw prompt must not appear",
            arbitrary={"authorization": "Bearer secret"},
        )

    event = _json_events(caplog)[-1]
    assert event["owner_id"] == "owner-safe"
    assert event["job_id"] == "job-safe"
    assert event["diagnostic_classification"] == "schema-invalid"
    assert "raw_prompt" not in event
    assert "arbitrary" not in event
    assert "secret" not in json.dumps(event)


def test_request_log_is_structured_and_correlates_response_headers(
    client, caplog
) -> None:
    with _capture_logs(caplog):
        response = client.get(
            "/api/v1/provider-capabilities",
            headers={"X-Correlation-Id": "correlation-test-409"},
        )

    assert response.status_code == 200
    event = next(
        item
        for item in reversed(_json_events(caplog))
        if item["event"] == "http.request.completed"
    )
    assert event == {
        "timestamp": event["timestamp"],
        "level": "info",
        "event": "http.request.completed",
        "request_id": response.headers["X-Request-Id"],
        "correlation_id": "correlation-test-409",
        "method": "GET",
        "route": "/api/v1/provider-capabilities",
        "status_code": 200,
    }


def test_provider_backed_logs_emit_safe_ids_and_never_auth_environment_or_bodies(
    client, caplog
) -> None:
    provider_secret = "codex-auth-secret-value"
    raw_prompt = "private raw learner prompt"
    transcript = "private transcript body"
    accepted = client.post(
        "/api/v1/disclosures/provider-generation/accept",
        json={"disclosure_version": "provider-network-v1"},
    )
    assert accepted.status_code == 200
    with client.app.state.uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        owner_id = owner.id
    job = client.app.state.dispatcher.enqueue(
        JobRequest("parse_import", owner_id, {"import_id": "logging-provider-job"})
    )

    with _capture_logs(caplog):
        result = execute_provider(
            client.app.state.uow_factory,
            SecretBearingUnavailableAdapter(provider_secret),
            ProviderInput(
                owner_id=owner_id,
                goal_id=None,
                job_id=job.job_id,
                purpose="evaluation",
                context={"raw_prompt": raw_prompt, "transcript": transcript},
                context_ref_hash="safe-context-hash",
                disclosure_id=accepted.json()["id"],
                output_schema_version="evaluation-v1",
                request_id="provider-request-correlation-test",
                correlation_id="provider-job-correlation-test",
            ),
            validator=None,
        )

    events = [
        item
        for item in _json_events(caplog)
        if str(item["event"]).startswith("provider.request.")
    ]
    assert [item["event"] for item in events] == [
        "provider.request.started",
        "provider.request.completed",
    ]
    assert len({item["provider_request_id"] for item in events}) == 1
    assert all(item["owner_id"] == owner_id for item in events)
    assert all(item["job_id"] == job.job_id for item in events)
    assert all(
        item["request_id"] == "provider-request-correlation-test" for item in events
    )
    assert all(
        item["correlation_id"] == "provider-job-correlation-test" for item in events
    )
    assert events[-1]["diagnostic_classification"] == (
        "provider-configuration-or-authentication"
    )
    serialized = "\n".join(json.dumps(item) for item in events)
    for forbidden in (
        provider_secret,
        "aws-secret-never-log",
        "unrelated-environment-never-log",
        raw_prompt,
        transcript,
    ):
        assert forbidden not in serialized
    assert result.failure_classification is not None


def test_runner_job_lifecycle_logs_preserve_safe_cross_process_correlation(
    session_factory, uow_factory, caplog
) -> None:
    with uow_factory() as uow:
        owner = ensure_local_owner(uow, "Logging test owner")
        uow.commit()
        owner_id = owner.id
    dispatcher = DurableJobDispatcher(
        session_factory,
        pending_cap=10,
        background_age_promotion_seconds=60,
        janitor_retention_seconds=60,
    )
    dispatcher.register(
        "java_runner",
        lambda _execution: JobCompletion(
            JobResult(
                "java_runner",
                "runner-v1",
                "RunnerRun:run-safe-409",
                hash_payload("RunnerRun:run-safe-409"),
            ),
            lambda _session: None,
        ),
    )
    request = JobRequest(
        "java_runner",
        owner_id,
        {"raw_prompt": "runner-payload-never-log", "authorization": "secret"},
        goal_id=None,
        schema_version="runner-v1",
        request_id="request-safe-409",
        correlation_id="correlation-safe-409",
        run_id="run-safe-409",
    )
    try:
        with _capture_logs(caplog):
            dispatcher.start()
            ref = dispatcher.enqueue(request)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                current = dispatcher.get(owner_id, ref.job_id)
                if current and current.status is JobStatus.SUCCEEDED:
                    break
                time.sleep(0.01)
            else:
                raise AssertionError("runner job did not complete")
    finally:
        dispatcher.stop()

    events = [
        event
        for event in _json_events(caplog)
        if event["event"] in {"job.enqueued", "job.started", "job.succeeded"}
        and event.get("job_id") == ref.job_id
    ]
    assert [event["event"] for event in events] == [
        "job.enqueued",
        "job.started",
        "job.succeeded",
    ]
    assert all(event["request_id"] == "request-safe-409" for event in events)
    assert all(event["correlation_id"] == "correlation-safe-409" for event in events)
    assert all(event["owner_id"] == owner_id for event in events)
    assert all(event["run_id"] == "run-safe-409" for event in events)
    serialized = "\n".join(json.dumps(event) for event in events)
    assert "runner-payload-never-log" not in serialized
    assert "secret" not in serialized


def test_app_logging_configuration_emits_info_once_to_local_stream() -> None:
    logger = logging.getLogger(LOGGER_NAME)
    original_handlers = list(logger.handlers)
    original_level = logger.level
    original_propagate = logger.propagate
    stream = StringIO()
    try:
        logger.handlers.clear()
        configure_structured_logging(stream)
        configure_structured_logging(stream)
        log_event("runtime.output.probe", request_id="request-output-409")
    finally:
        logger.handlers.clear()
        logger.handlers.extend(original_handlers)
        logger.setLevel(original_level)
        logger.propagate = original_propagate

    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["event"] == "runtime.output.probe"


def test_learner_job_diagnostic_is_a_safe_classification() -> None:
    internal_secret = "Traceback /Users/private token=never-return"
    ref = JobRef(
        "job-safe-diagnostic",
        "rebuild_index",
        JobStatus.FAILED,
        "2026-08-13T00:00:00Z",
        diagnostic=internal_secret,
    )
    assert safe_job_diagnostic(ref) == "job-execution-failure"
    assert internal_secret not in safe_job_diagnostic(ref)
    attempt = JobAttempt(
        1,
        "process-identity",
        10,
        10,
        "/Users/private/runner-temp",
        "2026-08-13T00:00:00Z",
        "2026-08-13T00:00:01Z",
        "failed",
        internal_secret,
        None,
        None,
    )
    public = _attempt_response(attempt)
    assert public.diagnostic == "job-attempt-failure"
    assert public.temp_path is None
    assert internal_secret not in public.model_dump_json()
