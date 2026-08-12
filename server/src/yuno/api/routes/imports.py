from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from yuno.api.contracts import (
    ImportCreateRequest,
    ImportRecordResponse,
    ImportStatementMappingResponse,
    ImportStatementMapRequest,
    ImportStatementMapResponse,
    ImportStatementPatchRequest,
    ImportStatementResponse,
    JobRefResponse,
    TopicImportHashResponse,
    accepted_job,
)
from yuno.api.dependencies import (
    get_job_dispatcher,
    get_owner_id,
    get_unit_of_work,
    idempotency_key,
    if_match,
    parse_if_match,
)
from yuno.modules.imports.domain import (
    ImportIdempotencyRecord,
    ImportRecord,
    ImportStatement,
    ImportStatementMapping,
    ImportStatus,
    TopicImportHash,
)
from yuno.modules.imports.ports import ImportsUnitOfWork
from yuno.modules.imports.service import (
    correct_statement,
    create_import,
    dismiss_statement,
    get_active_mapping,
    get_import,
    list_imports,
    list_statements,
    map_statement,
    mark_import_parsing,
    parse_import,
    reprocess_import,
    verify_statement,
)
from yuno.shared.application.jobs import JobDispatcher, JobRequest
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.errors import IdempotencyConflictError
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id

router = APIRouter(tags=["imports"])


@router.post(
    "/imports",
    response_model=ImportRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_import(
    body: ImportCreateRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[ImportsUnitOfWork, Depends(get_unit_of_work)],
    key: Annotated[str, Depends(idempotency_key)],
) -> ImportRecordResponse:
    return _idempotent(
        uow,
        owner_id,
        operation="create_import",
        key=key,
        request={"body": body.model_dump(mode="json")},
        response_type=ImportRecordResponse,
        execute=lambda: _import_response(
            create_import(
                uow,
                owner_id,
                goal_id=body.goal_id,
                import_type=body.import_type,
                source_text=body.original_content,
            )
        ),
    )


@router.get("/imports", response_model=list[ImportRecordResponse])
def get_imports(
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[ImportsUnitOfWork, Depends(get_unit_of_work)],
    goal_id: Annotated[str | None, Query()] = None,
) -> list[ImportRecordResponse]:
    return [
        _import_response(record)
        for record in list_imports(uow, owner_id, goal_id=goal_id)
    ]


@router.get("/imports/{import_id}", response_model=ImportRecordResponse)
def get_import_record(
    import_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[ImportsUnitOfWork, Depends(get_unit_of_work)],
) -> ImportRecordResponse:
    return _import_response(get_import(uow, owner_id, import_id))


@router.post(
    "/imports/{import_id}/parse",
    response_model=JobRefResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def post_import_parse(
    import_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[ImportsUnitOfWork, Depends(get_unit_of_work)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
    key: Annotated[str, Depends(idempotency_key)],
):
    return _enqueue_import_job(
        uow, dispatcher, owner_id, import_id, "parse_import", key
    )


@router.get(
    "/imports/{import_id}/statements",
    response_model=list[ImportStatementResponse],
)
def get_import_statements(
    import_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[ImportsUnitOfWork, Depends(get_unit_of_work)],
) -> list[ImportStatementResponse]:
    return [
        _statement_response(statement, get_active_mapping(uow, owner_id, statement.id))
        for statement in list_statements(uow, owner_id, import_id)
    ]


@router.patch(
    "/import-statements/{statement_id}", response_model=ImportStatementResponse
)
def patch_import_statement(
    statement_id: str,
    body: ImportStatementPatchRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[ImportsUnitOfWork, Depends(get_unit_of_work)],
    match: Annotated[str, Depends(if_match)],
    key: Annotated[str, Depends(idempotency_key)],
) -> ImportStatementResponse:
    expected = parse_if_match(match)
    return _statement_command(
        uow,
        owner_id,
        statement_id,
        "correct_statement",
        key,
        {"corrected_text": body.corrected_text, "expected_version": expected},
        lambda: correct_statement(
            uow,
            owner_id,
            statement_id,
            corrected_text=body.corrected_text,
            expected_version=expected,
        ),
    )


@router.post(
    "/import-statements/{statement_id}/map",
    response_model=ImportStatementMapResponse,
)
def post_import_statement_map(
    statement_id: str,
    body: ImportStatementMapRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[ImportsUnitOfWork, Depends(get_unit_of_work)],
    match: Annotated[str, Depends(if_match)],
    key: Annotated[str, Depends(idempotency_key)],
) -> ImportStatementMapResponse:
    expected = parse_if_match(match)

    operation = f"map_statement:{statement_id}"
    request = {**body.model_dump(mode="json"), "expected_version": expected}
    prior = _prior(uow, owner_id, operation, key, request, ImportStatementMapResponse)
    if prior is not None:
        return prior
    mapping, topic_hash = map_statement(
        uow,
        owner_id,
        statement_id,
        goal_id=body.goal_id,
        topic_stable_id=body.topic_id,
        expected_version=expected,
    )
    statement = uow.imports.get_statement(owner_id, statement_id)
    assert statement is not None
    response = ImportStatementMapResponse(
        statement=_statement_response(statement, mapping),
        mapping=_mapping_response(mapping),
        topic_imports_hash=_topic_hash_response(topic_hash),
    )
    _store_idempotency(uow, owner_id, operation, key, request, response)
    uow.commit()
    return response


@router.post(
    "/import-statements/{statement_id}/verify",
    response_model=ImportStatementResponse,
)
def post_import_statement_verify(
    statement_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[ImportsUnitOfWork, Depends(get_unit_of_work)],
    match: Annotated[str, Depends(if_match)],
    key: Annotated[str, Depends(idempotency_key)],
) -> ImportStatementResponse:
    expected = parse_if_match(match)
    return _statement_command(
        uow,
        owner_id,
        statement_id,
        "verify_statement",
        key,
        {"expected_version": expected},
        lambda: verify_statement(
            uow, owner_id, statement_id, expected_version=expected
        ),
    )


@router.post(
    "/import-statements/{statement_id}/dismiss",
    response_model=ImportStatementResponse,
)
def post_import_statement_dismiss(
    statement_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[ImportsUnitOfWork, Depends(get_unit_of_work)],
    match: Annotated[str, Depends(if_match)],
    key: Annotated[str, Depends(idempotency_key)],
) -> ImportStatementResponse:
    expected = parse_if_match(match)
    return _statement_command(
        uow,
        owner_id,
        statement_id,
        "dismiss_statement",
        key,
        {"expected_version": expected},
        lambda: dismiss_statement(
            uow, owner_id, statement_id, expected_version=expected
        ),
    )


@router.post(
    "/imports/{import_id}/reprocess",
    response_model=JobRefResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def post_import_reprocess(
    import_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[ImportsUnitOfWork, Depends(get_unit_of_work)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
    key: Annotated[str, Depends(idempotency_key)],
):
    return _enqueue_import_job(
        uow, dispatcher, owner_id, import_id, "reprocess_import", key
    )


def run_import_parse_job(request: JobRequest, uow_factory: UnitOfWorkFactory):
    """Parse an import and persist a recoverable failure state."""
    import_id = str(request.payload["import_id"])
    try:
        with uow_factory() as uow:
            if request.kind == "reprocess_import":
                reprocess_import(uow, request.owner_id, import_id)
            else:
                parse_import(uow, request.owner_id, import_id)
            record = get_import(uow, request.owner_id, import_id)
            uow.commit()
            return record
    except Exception:
        with uow_factory() as failure_uow:
            record = get_import(failure_uow, request.owner_id, import_id)
            if record.status is ImportStatus.PARSING:
                failure_uow.imports.update_import(
                    request.owner_id,
                    import_id,
                    record.row_version,
                    {
                        "status": ImportStatus.FAILED,
                        "failure_code": "import_parse_failed",
                        "failure_reference": f"import-job:{import_id}",
                        "updated_at": now_text(SystemClock()),
                    },
                )
                failure_uow.commit()
        raise


def _enqueue_import_job(
    uow: ImportsUnitOfWork,
    dispatcher: JobDispatcher,
    owner_id: str,
    import_id: str,
    kind: str,
    key: str,
):
    operation = f"{kind}:{import_id}"
    request_data = {"import_id": import_id, "operation": kind}
    prior = _prior(uow, owner_id, operation, key, request_data, JobRefResponse)
    if prior is not None:
        return accepted_job(_job_ref(prior))

    mark_import_parsing(uow, owner_id, import_id)
    uow.commit()
    ref = dispatcher.enqueue(
        JobRequest(
            kind=kind,
            owner_id=owner_id,
            payload=request_data,
            dedupe_key=import_id,
            idempotency_key=key,
            request_ref=f"ImportRecord:{import_id}",
        )
    )
    response = JobRefResponse(
        job_id=ref.job_id,
        kind=ref.kind,
        status=ref.status,
        enqueued_at=ref.enqueued_at,
        deduplicated=ref.deduplicated,
    )
    _store_idempotency(uow, owner_id, operation, key, request_data, response)
    uow.commit()
    return accepted_job(ref)


def _statement_command(
    uow: ImportsUnitOfWork,
    owner_id: str,
    statement_id: str,
    operation_name: str,
    key: str,
    request: dict[str, object],
    execute: Callable[[], ImportStatement],
) -> ImportStatementResponse:
    operation = f"{operation_name}:{statement_id}"
    return _idempotent(
        uow,
        owner_id,
        operation=operation,
        key=key,
        request=request,
        response_type=ImportStatementResponse,
        execute=lambda: _statement_response(
            execute(), get_active_mapping(uow, owner_id, statement_id)
        ),
    )


def _idempotent[ResponseModel: BaseModel](
    uow: ImportsUnitOfWork,
    owner_id: str,
    *,
    operation: str,
    key: str,
    request: dict[str, object],
    response_type: type[ResponseModel],
    execute: Callable[[], ResponseModel],
) -> ResponseModel:
    prior = _prior(uow, owner_id, operation, key, request, response_type)
    if prior is not None:
        return prior
    response = execute()
    _store_idempotency(uow, owner_id, operation, key, request, response)
    uow.commit()
    return response


def _prior[ResponseModel: BaseModel](
    uow: ImportsUnitOfWork,
    owner_id: str,
    operation: str,
    key: str,
    request: dict[str, object],
    response_type: type[ResponseModel],
) -> ResponseModel | None:
    prior = uow.imports.get_idempotency(owner_id, operation, key)
    if prior is None:
        return None
    if prior.request_hash != hash_payload(request):
        raise IdempotencyConflictError(
            "The Idempotency-Key was reused with a different import request."
        )
    return response_type.model_validate_json(prior.response_json)


def _store_idempotency(
    uow: ImportsUnitOfWork,
    owner_id: str,
    operation: str,
    key: str,
    request: dict[str, object],
    response: BaseModel,
) -> None:
    uow.imports.add_idempotency(
        ImportIdempotencyRecord(
            id=new_id(),
            owner_id=owner_id,
            operation=operation,
            idempotency_key=key,
            request_hash=hash_payload(request),
            response_json=response.model_dump_json(),
            created_at=now_text(SystemClock()),
        )
    )


def _import_response(record: ImportRecord) -> ImportRecordResponse:
    return ImportRecordResponse(
        id=record.id,
        goal_id=record.goal_id,
        import_type=record.import_type,
        original_content=record.original_content.decode("utf-8", errors="strict"),
        original_hash=record.original_hash,
        parser_version=record.parser_version,
        status=record.status,
        failure_code=record.failure_code,
        failure_reference=record.failure_reference,
        row_version=record.row_version,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _statement_response(
    statement: ImportStatement, mapping: ImportStatementMapping | None
) -> ImportStatementResponse:
    return ImportStatementResponse(
        id=statement.id,
        import_id=statement.import_id,
        sequence=statement.sequence,
        parser_version=statement.parser_version,
        original_text=statement.original_text,
        original_hash=statement.original_hash,
        normalized_text=statement.normalized_text,
        normalized_hash=statement.normalized_hash,
        confidence=statement.confidence,
        duplicate_of_statement_id=statement.duplicate_of_statement_id,
        trust_state=statement.trust_state,
        mapping_state=statement.mapping_state,
        corrected_text=statement.corrected_text,
        row_version=statement.row_version,
        created_at=statement.created_at,
        updated_at=statement.updated_at,
        mapping=(_mapping_response(mapping) if mapping is not None else None),
    )


def _mapping_response(
    mapping: ImportStatementMapping,
) -> ImportStatementMappingResponse:
    return ImportStatementMappingResponse(
        goal_id=mapping.goal_id,
        topic_id=mapping.topic_stable_id,
        graph_version_id=mapping.graph_version_id,
        decision=mapping.decision,
        accepted_at=mapping.accepted_at,
        revoked_at=mapping.revoked_at,
    )


def _topic_hash_response(topic_hash: TopicImportHash) -> TopicImportHashResponse:
    return TopicImportHashResponse(
        goal_id=topic_hash.goal_id,
        graph_version_id=topic_hash.graph_version_id,
        topic_id=topic_hash.topic_stable_id,
        imports_hash=topic_hash.imports_hash,
        updated_at=topic_hash.updated_at,
    )


def _job_ref(response: JobRefResponse):
    from yuno.shared.application.jobs import JobRef

    return JobRef(
        job_id=response.job_id,
        kind=response.kind,
        status=response.status,
        enqueued_at=response.enqueued_at,
        deduplicated=True,
    )
