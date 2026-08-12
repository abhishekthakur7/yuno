"""Topic and layer queries."""

from __future__ import annotations

import json
from collections.abc import Sequence
from urllib.parse import unquote

from yuno.modules.learning_content.domain import (
    EMPTY_IMPORTS_HASH,
    FIXTURE_PROMPT_TEMPLATE_VERSION,
    GENERATION_CONTRACT_VERSION,
    GENERATION_SCHEMA_VERSION,
    ArtifactState,
    Capability,
    Checkpoint,
    D3CacheKey,
    GeneratedArtifact,
    GenerateRequest,
    GenerationAttempt,
    GenerationAttemptStatus,
    GenerationCitationRecord,
    GenerationClaimRecord,
    GenerationIdempotencyRecord,
    GenerationProvenanceRef,
    GenerationSnapshot,
    LayerDocument,
    LayerState,
    StaleReason,
    TopicLayer,
    d3_cache_key_hash,
    personalization_is_stale,
    validate_checkpoint,
)
from yuno.modules.learning_content.ports import (
    ContentRevisionView,
    LearningContentUnitOfWork,
    TopicView,
)
from yuno.shared.application.jobs import JobRef, JobStatus
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.errors import (
    DomainValidationError,
    IdempotencyConflictError,
    NotFoundError,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id


def get_topic(
    uow: LearningContentUnitOfWork, graph_version_id: str, topic_id: str
) -> TopicView:
    if uow.canonical.get_published_version(graph_version_id) is None:
        raise NotFoundError("The approved canonical graph version was not found.")
    topic = next(
        (
            item
            for item in uow.canonical.get_published_topics(graph_version_id)
            if item.stable_id == topic_id
        ),
        None,
    )
    if topic is None:
        raise NotFoundError(f"Topic '{topic_id}' was not found in the approved graph.")
    return topic


def list_layers(
    uow: LearningContentUnitOfWork,
    owner_id: str,
    goal_id: str,
    topic_id: str,
    current_provider: str | None = None,
    current_model: str | None = None,
) -> tuple[LayerDocument, ...]:
    goal = uow.profiles_goals.get_goal(owner_id, goal_id)
    if goal is None:
        raise NotFoundError(f"Goal '{goal_id}' was not found.")
    get_topic(uow, goal.graph_version_id, topic_id)
    revisions = uow.canonical.get_published_content_revisions(
        goal.graph_version_id, topic_id
    )
    documents = []
    for layer in TopicLayer:
        authored = _layer_document(layer, revisions)
        key, _, profile_hash, evidence_hash = resolve_generation_context(
            uow, owner_id, goal_id, topic_id, layer
        )
        artifact = uow.learning_content.get_artifact_by_key(
            owner_id,
            key.canonical_graph_version,
            key.topic_id,
            key.goal_id,
            layer.value,
            key.topic_mapped_approved_imports_hash,
            key.prompt_template_version,
        )
        current_attempt_artifact = artifact
        stale_reason = None
        if artifact is None or artifact.body is None:
            prior = uow.learning_content.get_latest_artifact(
                owner_id, goal_id, topic_id, layer.value
            )
            if prior is not None and (artifact is None or prior.id != artifact.id):
                artifact = prior
                stale_reason = StaleReason.CACHE_KEY_CHANGED
        if artifact is not None:
            if stale_reason is None and artifact.current_snapshot_id:
                snapshot = uow.provenance.get_artifact_snapshot(
                    owner_id, artifact.current_snapshot_id
                )
                current = hash_payload(
                    {
                        "profile_hash": profile_hash,
                        "evidence_state_hash": evidence_hash,
                        "provider": current_provider or snapshot.provider,
                        "model": current_model or snapshot.model,
                        "schema": snapshot.schema_version,
                        "contract": snapshot.contract_version,
                    }
                )
                if personalization_is_stale(snapshot.snapshot_hash, current):
                    stale_reason = StaleReason.PERSONALIZATION_SNAPSHOT_MISMATCH
            generation_artifact = current_attempt_artifact or artifact
            generation = {
                "job_id": generation_artifact.last_job_id,
                "status": generation_artifact.last_attempt_status.value
                if generation_artifact.last_attempt_status
                else None,
                "retryable": generation_artifact.retryable,
                "failure_reference": generation_artifact.failure_reference,
            }
            state = (
                LayerState.STALE
                if stale_reason
                else LayerState.GENERATING
                if artifact.body is None
                and artifact.last_attempt_status
                in {GenerationAttemptStatus.QUEUED, GenerationAttemptStatus.RUNNING}
                else LayerState.READY
                if artifact.body
                else LayerState.UNAVAILABLE
            )
            documents.append(
                LayerDocument(
                    layer,
                    state,
                    None,
                    artifact.body,
                    artifact.body_hash,
                    authored.checkpoint,
                    artifact.id,
                    "generated",
                    generation,
                    stale_reason,
                )
            )
            continue
        documents.append(
            LayerDocument(
                authored.layer,
                authored.state,
                authored.revision_id,
                authored.markdown,
                authored.markdown_hash,
                authored.checkpoint,
                None,
                "authored" if authored.markdown else None,
                None,
                None,
            )
        )
    return tuple(documents)


def _layer_document(
    layer: TopicLayer,
    revisions: Sequence[ContentRevisionView],
) -> LayerDocument:
    matches = [item for item in revisions if item.layer == layer.value]
    content = next((item for item in reversed(matches) if item.kind == "layer"), None)
    checkpoint_revision = next(
        (item for item in reversed(matches) if item.kind == "checkpoint"), None
    )
    if content is None:
        return LayerDocument(layer, LayerState.ABSENT, None, None, None, None)
    markdown = _inline_value(content)
    if markdown is None:
        return LayerDocument(
            layer, LayerState.UNAVAILABLE, content.id, None, content.markdown_hash, None
        )
    try:
        checkpoint = (
            _checkpoint(_inline_value(checkpoint_revision))
            if checkpoint_revision is not None
            else None
        )
    except DomainValidationError:
        return LayerDocument(
            layer,
            LayerState.UNAVAILABLE,
            content.id,
            markdown,
            content.markdown_hash,
            None,
        )
    return LayerDocument(
        layer,
        LayerState.READY,
        content.id,
        markdown,
        content.markdown_hash,
        checkpoint,
    )


def _inline_value(revision: ContentRevisionView | None) -> str | None:
    if revision is None or not revision.markdown_ref.startswith("inline:"):
        return None
    return unquote(revision.markdown_ref.removeprefix("inline:"))


def _checkpoint(raw: str | None) -> Checkpoint:
    if raw is None:
        raise DomainValidationError("Checkpoint content is unavailable.")
    try:
        data = json.loads(raw)
        checkpoint = Checkpoint(
            scenario=str(data["scenario"]),
            constraints=tuple(str(item) for item in data["constraints"]),
            target_capability=Capability(str(data["target_capability"])),
            expected_artifact=str(data["expected_artifact"]),
            estimated_minutes=int(data["estimated_minutes"]),
            rubric=tuple(str(item) for item in data["rubric"]),
            assumptions=tuple(str(item) for item in data["assumptions"]),
            evidence_criterion=str(data["evidence_criterion"]),
            limitation=str(data["limitation"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise DomainValidationError("Checkpoint content is invalid.") from exc
    validate_checkpoint(checkpoint)
    return checkpoint


def resolve_generation_context(
    uow, owner_id: str, goal_id: str, topic_id: str, layer: TopicLayer
):
    goal = uow.profiles_goals.get_goal(owner_id, goal_id)
    if goal is None:
        raise NotFoundError(f"Goal '{goal_id}' was not found.")
    topic = get_topic(uow, goal.graph_version_id, topic_id)
    import_row = uow.imports.get_topic_hash(
        owner_id, goal_id, goal.graph_version_id, topic_id
    )
    imports_hash = import_row.imports_hash if import_row else EMPTY_IMPORTS_HASH
    key = D3CacheKey(
        goal.graph_version_id,
        topic_id,
        goal_id,
        layer,
        imports_hash,
        FIXTURE_PROMPT_TEMPLATE_VERSION,
    )
    profile = uow.profiles_goals.get_profile(owner_id)
    evidence = uow.evidence.list_evidence(owner_id, goal_id)
    profile_hash = hash_payload(
        {
            "experience": profile.experience if profile else None,
            "strengths": profile.strengths if profile else None,
            "weaknesses": profile.weaknesses if profile else None,
        }
    )
    evidence_hash = hash_payload(
        {
            "evidence": sorted((item.id, item.payload_hash) for item in evidence),
            "corrections": sorted(
                (
                    item.id,
                    item.topic_stable_id,
                    getattr(item.correction_type, "value", item.correction_type),
                    item.value,
                    item.reason,
                    item.supersedes_correction_id,
                )
                for item in uow.roadmap.list_corrections(owner_id, goal_id)
            ),
            "learning_states": sorted(
                (
                    item.topic_stable_id,
                    getattr(item.classification, "value", item.classification),
                    item.origin,
                    item.input_hash,
                )
                for item in uow.roadmap.list_learning_states(owner_id, goal_id)
            ),
        }
    )
    return key, topic, profile_hash, evidence_hash


def reserve_generation(
    uow, owner_id, goal_id, topic_id, layer, idempotency_key, *, force=False
):
    key, _, _, _ = resolve_generation_context(uow, owner_id, goal_id, topic_id, layer)
    request_data = {
        "goal_id": goal_id,
        "topic_id": topic_id,
        "layer": layer.value,
        "force": force,
    }
    request_hash = hash_payload(request_data)
    operation = (
        "regenerate" if force else "generate"
    ) + f":{goal_id}:{topic_id}:{layer.value}"
    prior = uow.learning_content.get_idempotency(owner_id, operation, idempotency_key)
    if prior:
        if prior.request_hash != request_hash:
            raise IdempotencyConflictError(
                "The Idempotency-Key was reused with a different generation request."
            )
        attempt = uow.learning_content.get_attempt(owner_id, prior.attempt_id)
        return _job_ref(attempt, True), attempt, False
    if uow.learning_content.get_idempotency_by_key(owner_id, idempotency_key):
        raise IdempotencyConflictError(
            "The Idempotency-Key was reused for another generation operation."
        )
    artifact = uow.learning_content.get_artifact_by_key(
        owner_id,
        key.canonical_graph_version,
        key.topic_id,
        key.goal_id,
        key.layer.value,
        key.topic_mapped_approved_imports_hash,
        key.prompt_template_version,
    )
    timestamp = now_text(SystemClock())
    if artifact is None:
        artifact = GeneratedArtifact(
            new_id(),
            owner_id,
            goal_id,
            key.canonical_graph_version,
            topic_id,
            layer,
            "lesson-layer",
            key.topic_mapped_approved_imports_hash,
            key.prompt_template_version,
            d3_cache_key_hash(key),
            ArtifactState.GENERATING,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            False,
            1,
            timestamp,
            timestamp,
            None,
        )
        artifact = uow.learning_content.add_artifact(artifact)
    active = uow.learning_content.get_active_attempt(owner_id, artifact.id)
    if active:
        _persist_idempotency(
            uow,
            GenerationIdempotencyRecord(
                new_id(),
                owner_id,
                operation,
                idempotency_key,
                request_hash,
                active.id,
                active.job_id,
                "{}",
                timestamp,
            ),
        )
        return _job_ref(active, True), active, False
    if artifact.body is not None and not force:
        attempt = uow.learning_content.get_attempt(owner_id, artifact.last_attempt_id)
        _persist_idempotency(
            uow,
            GenerationIdempotencyRecord(
                new_id(),
                owner_id,
                operation,
                idempotency_key,
                request_hash,
                attempt.id,
                attempt.job_id,
                "{}",
                timestamp,
            ),
        )
        return _job_ref(attempt, True), attempt, False
    job_id = new_id()
    attempt = GenerationAttempt(
        new_id(),
        owner_id,
        goal_id,
        artifact.id,
        artifact.cache_key_hash,
        job_id,
        "regenerate" if force else "generate",
        GenerationAttemptStatus.QUEUED,
        request_hash,
        None,
        None,
        None,
        False,
        timestamp,
        None,
        None,
    )
    reserved = attempt
    attempt = uow.learning_content.add_attempt(attempt)
    created = attempt.id == reserved.id
    if not created:
        _persist_idempotency(
            uow,
            GenerationIdempotencyRecord(
                new_id(),
                owner_id,
                operation,
                idempotency_key,
                request_hash,
                attempt.id,
                attempt.job_id,
                "{}",
                timestamp,
            ),
        )
        return _job_ref(attempt, True), attempt, False
    uow.learning_content.update_artifact(
        owner_id,
        artifact.id,
        {
            "state": ArtifactState.READY if artifact.body else ArtifactState.GENERATING,
            "last_attempt_id": attempt.id,
            "last_job_id": job_id,
            "last_attempt_status": GenerationAttemptStatus.QUEUED,
            "failure_reference": None,
            "retryable": False,
            "updated_at": timestamp,
        },
    )
    ref = _job_ref(attempt, False)
    _persist_idempotency(
        uow,
        GenerationIdempotencyRecord(
            new_id(),
            owner_id,
            operation,
            idempotency_key,
            request_hash,
            attempt.id,
            job_id,
            "{}",
            timestamp,
        ),
    )
    return ref, attempt, created


def run_generation(uow_factory, adapter, owner_id, attempt_id):
    with uow_factory() as uow:
        attempt = uow.learning_content.get_attempt(owner_id, attempt_id)
        if attempt is None:
            raise NotFoundError("Generation attempt was not found.")
        artifact = uow.learning_content.get_artifact(owner_id, attempt.artifact_id)
        now = now_text(SystemClock())
        uow.learning_content.update_attempt(
            owner_id,
            attempt.id,
            "queued",
            {"status": GenerationAttemptStatus.RUNNING, "started_at": now},
        )
        uow.learning_content.update_artifact(
            owner_id,
            artifact.id,
            {"last_attempt_status": GenerationAttemptStatus.RUNNING, "updated_at": now},
        )
        uow.commit()
        _, _, profile_hash, evidence_hash = resolve_generation_context(
            uow, owner_id, artifact.goal_id, artifact.topic_stable_id, artifact.layer
        )
        request = GenerateRequest(
            owner_id,
            artifact.goal_id,
            artifact.topic_stable_id,
            artifact.layer,
            artifact.graph_version_id,
            artifact.imports_hash,
            artifact.prompt_template_version,
            profile_hash,
            evidence_hash,
        )
    try:
        result = adapter.generate(request)
        if not result.body.strip():
            raise DomainValidationError("Generated body must not be blank.")
        if (
            result.schema_version != GENERATION_SCHEMA_VERSION
            or result.contract_version != GENERATION_CONTRACT_VERSION
        ):
            timestamp = now_text(SystemClock())
            with uow_factory() as uow:
                uow.learning_content.add_quarantine(
                    id=new_id(),
                    owner_id=owner_id,
                    goal_id=attempt.goal_id,
                    attempt_id=attempt.id,
                    raw_output_hash=hash_payload(result.body),
                    schema_version=result.schema_version,
                    validation_errors_json=json.dumps(
                        ["unsupported generation schema or contract version"]
                    ),
                    created_at=timestamp,
                )
                uow.learning_content.update_attempt(
                    owner_id,
                    attempt.id,
                    "running",
                    {
                        "status": GenerationAttemptStatus.QUARANTINED,
                        "failure_classification": "schema-invalid",
                        "failure_reference": f"quarantine:{attempt.id}",
                        "retryable": True,
                        "completed_at": timestamp,
                    },
                )
                artifact = uow.learning_content.get_artifact(
                    owner_id, attempt.artifact_id
                )
                uow.learning_content.update_artifact(
                    owner_id,
                    artifact.id,
                    {
                        "state": ArtifactState.READY
                        if artifact.body
                        else ArtifactState.FAILED,
                        "last_attempt_status": GenerationAttemptStatus.QUARANTINED,
                        "failure_reference": f"quarantine:{attempt.id}",
                        "retryable": True,
                        "updated_at": timestamp,
                    },
                )
                uow.commit()
            raise DomainValidationError(
                "Generation output was quarantined because its schema was invalid."
            )
        with uow_factory() as uow:
            artifact = uow.learning_content.get_artifact(owner_id, attempt.artifact_id)
            timestamp = result.generated_at
            snapshot_id = new_id()
            snapshot_hash = hash_payload(
                {
                    "profile_hash": profile_hash,
                    "evidence_state_hash": evidence_hash,
                    "provider": result.provider,
                    "model": result.model,
                    "schema": result.schema_version,
                    "contract": result.contract_version,
                }
            )
            snapshot = GenerationSnapshot(
                snapshot_id,
                owner_id,
                artifact.goal_id,
                artifact.id,
                attempt.id,
                evidence_hash,
                profile_hash,
                result.provider,
                result.model,
                timestamp,
                result.schema_version,
                result.contract_version,
                artifact.prompt_template_version,
                snapshot_hash,
            )
            refs = tuple(
                GenerationProvenanceRef(
                    new_id(), owner_id, artifact.goal_id, artifact.id, snapshot_id, k, v
                )
                for k, v in result.provenance_refs
            )
            claim_rows = []
            for generated in result.claims:
                claim_id = new_id()
                claim = GenerationClaimRecord(
                    claim_id,
                    owner_id,
                    artifact.goal_id,
                    None,
                    artifact.id,
                    snapshot_id,
                    generated.claim_text,
                    generated.claim_type,
                    generated.sensitive,
                    "pending",
                )
                citations = tuple(
                    GenerationCitationRecord(
                        new_id(),
                        owner_id,
                        artifact.goal_id,
                        claim_id,
                        c.source_id,
                        c.source_snapshot_id,
                        c.locator,
                        c.support_kind,
                        c.note,
                    )
                    for c in generated.citations
                )
                claim_rows.append((claim, citations))
            uow.provenance.add_generation_result(snapshot, refs, claim_rows)
            body_hash = hash_payload(result.body)
            uow.learning_content.update_artifact(
                owner_id,
                artifact.id,
                {
                    "state": ArtifactState.READY,
                    "body_ref": "inline:" + result.body,
                    "body_hash": body_hash,
                    "current_snapshot_id": snapshot_id,
                    "producing_job_id": attempt.job_id,
                    "last_attempt_status": GenerationAttemptStatus.SUCCEEDED,
                    "failure_reference": None,
                    "retryable": False,
                    "updated_at": timestamp,
                    "generated_at": timestamp,
                },
            )
            uow.learning_content.update_attempt(
                owner_id,
                attempt.id,
                "running",
                {
                    "status": GenerationAttemptStatus.SUCCEEDED,
                    "result_hash": body_hash,
                    "completed_at": timestamp,
                },
            )
            uow.commit()
    except Exception as exc:
        with uow_factory() as uow:
            artifact = uow.learning_content.get_artifact(owner_id, attempt.artifact_id)
            current_attempt = uow.learning_content.get_attempt(owner_id, attempt.id)
            if current_attempt.status is GenerationAttemptStatus.QUARANTINED:
                raise
            timestamp = now_text(SystemClock())
            uow.learning_content.update_artifact(
                owner_id,
                artifact.id,
                {
                    "state": ArtifactState.READY
                    if artifact.body
                    else ArtifactState.FAILED,
                    "last_attempt_status": GenerationAttemptStatus.FAILED,
                    "failure_reference": f"generation:{attempt.id}",
                    "retryable": True,
                    "updated_at": timestamp,
                },
            )
            uow.learning_content.update_attempt(
                owner_id,
                attempt.id,
                "running",
                {
                    "status": GenerationAttemptStatus.FAILED,
                    "failure_classification": type(exc).__name__,
                    "failure_reference": f"generation:{attempt.id}",
                    "retryable": True,
                    "completed_at": timestamp,
                },
            )
            uow.commit()
        raise


def _job_ref(attempt, deduplicated):
    statuses = {
        GenerationAttemptStatus.QUEUED: JobStatus.QUEUED,
        GenerationAttemptStatus.RUNNING: JobStatus.RUNNING,
        GenerationAttemptStatus.SUCCEEDED: JobStatus.SUCCEEDED,
        GenerationAttemptStatus.FAILED: JobStatus.FAILED,
        GenerationAttemptStatus.QUARANTINED: JobStatus.FAILED,
    }
    return JobRef(
        attempt.job_id,
        "generate_topic_content",
        statuses[attempt.status],
        attempt.created_at,
        deduplicated,
    )


def _persist_idempotency(uow, record: GenerationIdempotencyRecord) -> None:
    persisted = uow.learning_content.add_idempotency(record)
    if (
        persisted.operation != record.operation
        or persisted.request_hash != record.request_hash
        or persisted.attempt_id != record.attempt_id
    ):
        raise IdempotencyConflictError(
            "The Idempotency-Key was reused for another generation operation."
        )
