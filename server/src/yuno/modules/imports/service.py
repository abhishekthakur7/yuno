"""Original-preserving parsing and learner-controlled import review."""

from __future__ import annotations

from collections.abc import Sequence

from yuno.modules.audit.domain import AuditEvent
from yuno.modules.imports.domain import (
    PARSER_VERSION,
    ImportParseResult,
    ImportRecord,
    ImportStatement,
    ImportStatementDecision,
    ImportStatementMapping,
    ImportStatus,
    ImportType,
    MappingDecision,
    MappingState,
    StatementDecisionType,
    TopicImportHash,
    TrustState,
    normalize_statement,
    parse_source,
    sha256_bytes,
)
from yuno.modules.imports.ports import ImportsUnitOfWork
from yuno.shared.domain.clock import Clock, SystemClock, now_text
from yuno.shared.domain.errors import (
    ConflictError,
    DomainValidationError,
    ImportCountLimitError,
    ImportStatementLimitError,
    ImportTooLargeError,
    NotFoundError,
    PreconditionFailedError,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id


def create_import(
    uow: ImportsUnitOfWork,
    owner_id: str,
    *,
    goal_id: str | None,
    import_type: ImportType,
    source_text: str,
    parser_version: str = PARSER_VERSION,
    max_bytes: int = 10 * 1024 * 1024,
    retained_owner_limit: int = 100,
    clock: Clock | None = None,
) -> ImportRecord:
    source = source_text.encode("utf-8", errors="strict")
    if not source:
        raise DomainValidationError("Import source must not be empty.")
    if len(source) > max_bytes:
        raise ImportTooLargeError(
            f"Imports may contain at most {max_bytes} UTF-8 bytes.",
            recovery_action="Reduce the import size and try again.",
        )
    if parser_version != PARSER_VERSION:
        raise DomainValidationError(
            f"Unsupported import parser version '{parser_version}'."
        )
    if goal_id is not None and uow.profiles_goals.get_goal(owner_id, goal_id) is None:
        raise NotFoundError(f"Goal '{goal_id}' was not found.")
    if uow.imports.count_live_imports(owner_id) >= retained_owner_limit:
        raise ImportCountLimitError(
            f"An owner may retain at most {retained_owner_limit} imports.",
            recovery_action="Delete or export an existing import before adding another.",
        )
    timestamp = now_text(clock or SystemClock())
    record = ImportRecord(
        new_id(),
        owner_id,
        goal_id,
        import_type,
        source,
        sha256_bytes(source),
        parser_version,
        ImportStatus.SELECTED,
        None,
        None,
        1,
        timestamp,
        timestamp,
    )
    uow.imports.add_import(record)
    _audit(
        uow,
        owner_id,
        goal_id,
        "import_record",
        record.id,
        "created",
        None,
        record.original_hash,
        timestamp,
    )
    return record


def list_imports(
    uow: ImportsUnitOfWork, owner_id: str, *, goal_id: str | None = None
) -> Sequence[ImportRecord]:
    return uow.imports.list_imports(owner_id, goal_id)


def get_import(uow: ImportsUnitOfWork, owner_id: str, import_id: str) -> ImportRecord:
    record = uow.imports.get_import(owner_id, import_id)
    if record is None:
        raise NotFoundError(f"Import '{import_id}' was not found.")
    return record


def mark_import_parsing(
    uow: ImportsUnitOfWork,
    owner_id: str,
    import_id: str,
    *,
    expected_version: int | None = None,
    clock: Clock | None = None,
) -> ImportRecord:
    record = get_import(uow, owner_id, import_id)
    expected = record.row_version if expected_version is None else expected_version
    if record.status not in {
        ImportStatus.SELECTED,
        ImportStatus.FAILED,
        ImportStatus.PARSED_UNTRUSTED,
        ImportStatus.LEARNER_REVIEW,
        ImportStatus.APPLIED,
    }:
        raise ConflictError(
            "This import cannot enter parsing from its current state.",
            current_state=record.status.value,
        )
    updated = uow.imports.update_import(
        owner_id,
        import_id,
        expected,
        {
            "status": ImportStatus.PARSING,
            "failure_code": None,
            "failure_reference": None,
            "updated_at": now_text(clock or SystemClock()),
        },
    )
    if updated is None:
        raise PreconditionFailedError("The import changed; reload it and retry.")
    return updated


def parse_import(
    uow: ImportsUnitOfWork,
    owner_id: str,
    import_id: str,
    *,
    parser_version: str = PARSER_VERSION,
    statements_per_import_limit: int = 10_000,
    unreviewed_owner_limit: int = 50_000,
    clock: Clock | None = None,
) -> ImportParseResult:
    record = get_import(uow, owner_id, import_id)
    if record.status is not ImportStatus.PARSING:
        raise ConflictError(
            "The import must be in parsing state.", current_state=record.status.value
        )
    timestamp = now_text(clock or SystemClock())
    parsed = parse_source(record.original_content, parser_version=parser_version)
    if len(parsed) > statements_per_import_limit:
        raise ImportStatementLimitError(
            f"An import may contain at most {statements_per_import_limit} statements.",
            recovery_action="Split the source into smaller imports and try again.",
        )
    new_statement_count = sum(
        uow.imports.get_statement_for_occurrence(
            owner_id, import_id, item.sequence, parser_version
        )
        is None
        for item in parsed
    )
    if (
        uow.imports.count_unreviewed_statements(owner_id) + new_statement_count
        > unreviewed_owner_limit
    ):
        raise ImportStatementLimitError(
            f"An owner may retain at most {unreviewed_owner_limit} unreviewed statements.",
            recovery_action="Review or delete existing statements before parsing another import.",
        )
    duplicate_ids: list[str] = []
    for item in parsed:
        existing = uow.imports.get_statement_for_occurrence(
            owner_id, import_id, item.sequence, parser_version
        )
        if existing is not None:
            continue
        canonical = uow.imports.get_unmapped_canonical_by_hash(
            owner_id, parser_version, item.normalized_hash
        )
        duplicate_of = canonical.id if canonical is not None else None
        statement = ImportStatement(
            new_id(),
            owner_id,
            import_id,
            item.sequence,
            parser_version,
            item.original_text,
            item.original_hash,
            item.normalized_text,
            item.normalized_hash,
            item.confidence,
            duplicate_of,
            TrustState.UNTRUSTED,
            MappingState.DUPLICATE if duplicate_of else MappingState.UNMAPPED,
            None,
            1,
            timestamp,
            timestamp,
        )
        uow.imports.add_statement(statement)
        if duplicate_of:
            duplicate_ids.append(statement.id)
    statements = tuple(uow.imports.list_statements(owner_id, import_id))
    updated = uow.imports.update_import(
        owner_id,
        import_id,
        record.row_version,
        {
            "parser_version": parser_version,
            "status": ImportStatus.PARSED_UNTRUSTED,
            "failure_code": None,
            "failure_reference": None,
            "updated_at": timestamp,
        },
    )
    if updated is None:
        raise PreconditionFailedError("The import changed while parsing; retry.")
    _audit(
        uow,
        owner_id,
        record.goal_id,
        "import_record",
        record.id,
        "parsed",
        record.original_hash,
        hash_payload([s.normalized_hash for s in statements]),
        timestamp,
    )
    return ImportParseResult(
        parser_version, record.original_hash, statements, (), tuple(duplicate_ids)
    )


def reprocess_import(
    uow: ImportsUnitOfWork,
    owner_id: str,
    import_id: str,
    *,
    parser_version: str = PARSER_VERSION,
    statements_per_import_limit: int = 10_000,
    unreviewed_owner_limit: int = 50_000,
    clock: Clock | None = None,
) -> ImportParseResult:
    record = get_import(uow, owner_id, import_id)
    if record.status is not ImportStatus.PARSING:
        record = mark_import_parsing(
            uow, owner_id, import_id, expected_version=record.row_version, clock=clock
        )
    return parse_import(
        uow,
        owner_id,
        record.id,
        parser_version=parser_version,
        statements_per_import_limit=statements_per_import_limit,
        unreviewed_owner_limit=unreviewed_owner_limit,
        clock=clock,
    )


def list_statements(
    uow: ImportsUnitOfWork, owner_id: str, import_id: str
) -> Sequence[ImportStatement]:
    get_import(uow, owner_id, import_id)
    return uow.imports.list_statements(owner_id, import_id)


def correct_statement(
    uow: ImportsUnitOfWork,
    owner_id: str,
    statement_id: str,
    *,
    corrected_text: str,
    expected_version: int,
    clock: Clock | None = None,
) -> ImportStatement:
    if not corrected_text.strip():
        raise DomainValidationError("Corrected statement text must not be blank.")
    statement = _statement(uow, owner_id, statement_id)
    timestamp = now_text(clock or SystemClock())
    normalized = normalize_statement(corrected_text)
    collision = uow.imports.get_unmapped_canonical_by_hash(
        owner_id, statement.parser_version, sha256_bytes(normalized.encode("utf-8"))
    )
    duplicate_of = (
        collision.id
        if statement.mapping_state is not MappingState.MAPPED
        and collision is not None
        and collision.id != statement.id
        else None
    )
    next_mapping_state = (
        MappingState.MAPPED
        if statement.mapping_state is MappingState.MAPPED
        else MappingState.DUPLICATE
        if duplicate_of
        else MappingState.UNMAPPED
    )
    updated = uow.imports.update_statement(
        owner_id,
        statement_id,
        expected_version,
        {
            "corrected_text": corrected_text,
            "normalized_text": normalized,
            "normalized_hash": sha256_bytes(normalized.encode("utf-8")),
            "mapping_state": next_mapping_state,
            "duplicate_of_statement_id": duplicate_of,
            "updated_at": timestamp,
        },
    )
    if updated is None:
        raise PreconditionFailedError("The statement changed; reload it and retry.")
    uow.imports.append_statement_decision(
        ImportStatementDecision(
            new_id(),
            owner_id,
            statement_id,
            StatementDecisionType.CORRECTED,
            corrected_text,
            timestamp,
        )
    )
    active_mapping = uow.imports.get_active_mapping(owner_id, statement_id)
    if active_mapping is not None:
        _refresh_topic_hash(
            uow,
            owner_id,
            active_mapping.goal_id,
            active_mapping.graph_version_id,
            active_mapping.topic_stable_id,
            timestamp,
        )
    _advance_import_status(uow, updated, ImportStatus.LEARNER_REVIEW, timestamp)
    _audit(
        uow,
        owner_id,
        None,
        "import_statement",
        statement_id,
        "corrected",
        hash_payload(statement),
        hash_payload(updated),
        timestamp,
    )
    return updated


def verify_statement(
    uow: ImportsUnitOfWork,
    owner_id: str,
    statement_id: str,
    *,
    expected_version: int,
    clock: Clock | None = None,
) -> ImportStatement:
    return _trust_decision(
        uow,
        owner_id,
        statement_id,
        expected_version,
        TrustState.VERIFIED,
        StatementDecisionType.VERIFIED,
        clock,
    )


def dismiss_statement(
    uow: ImportsUnitOfWork,
    owner_id: str,
    statement_id: str,
    *,
    expected_version: int,
    clock: Clock | None = None,
) -> ImportStatement:
    active = uow.imports.get_active_mapping(owner_id, statement_id)
    updated = _trust_decision(
        uow,
        owner_id,
        statement_id,
        expected_version,
        TrustState.DISMISSED,
        StatementDecisionType.DISMISSED,
        clock,
    )
    if active is not None:
        if uow.imports.revoke_mapping(owner_id, active.id, updated.updated_at) is None:
            raise ConflictError(
                "The active mapping changed while dismissing the statement."
            )
        remapped = uow.imports.update_statement(
            owner_id,
            statement_id,
            updated.row_version,
            {"mapping_state": MappingState.UNMAPPED, "updated_at": updated.updated_at},
        )
        if remapped is None:
            raise PreconditionFailedError(
                "The statement changed while revoking its mapping."
            )
        updated = remapped
        _refresh_topic_hash(
            uow,
            owner_id,
            active.goal_id,
            active.graph_version_id,
            active.topic_stable_id,
            updated.updated_at,
        )
    return updated


def map_statement(
    uow: ImportsUnitOfWork,
    owner_id: str,
    statement_id: str,
    *,
    goal_id: str,
    topic_stable_id: str,
    expected_version: int,
    clock: Clock | None = None,
) -> tuple[ImportStatementMapping, TopicImportHash]:
    statement = _statement(uow, owner_id, statement_id)
    if statement.mapping_state is MappingState.DUPLICATE:
        raise ConflictError(
            "A duplicate occurrence cannot be mapped; review its original statement."
        )
    if uow.imports.get_active_mapping(owner_id, statement_id) is not None:
        raise ConflictError("This statement already has an approved mapping.")
    goal = uow.profiles_goals.get_goal(owner_id, goal_id)
    if goal is None:
        raise NotFoundError(f"Goal '{goal_id}' was not found.")
    published_ids = {
        topic.stable_id
        for topic in uow.canonical.get_published_topics(goal.graph_version_id)
    }
    if topic_stable_id not in published_ids:
        raise DomainValidationError(
            "The mapping target is not in the goal's current approved graph."
        )
    timestamp = now_text(clock or SystemClock())
    mapping = ImportStatementMapping(
        new_id(),
        owner_id,
        goal_id,
        statement_id,
        topic_stable_id,
        goal.graph_version_id,
        MappingDecision.APPROVED,
        timestamp,
        None,
    )
    uow.imports.append_mapping(mapping)
    updated = uow.imports.update_statement(
        owner_id,
        statement_id,
        expected_version,
        {"mapping_state": MappingState.MAPPED, "updated_at": timestamp},
    )
    if updated is None:
        raise PreconditionFailedError("The statement changed; reload it and retry.")
    topic_hash = _refresh_topic_hash(
        uow, owner_id, goal_id, goal.graph_version_id, topic_stable_id, timestamp
    )
    _advance_import_status(uow, updated, ImportStatus.APPLIED, timestamp)
    _audit(
        uow,
        owner_id,
        goal_id,
        "import_statement_mapping",
        mapping.id,
        "approved",
        None,
        topic_hash.imports_hash,
        timestamp,
    )
    return mapping, topic_hash


def get_active_mapping(
    uow: ImportsUnitOfWork, owner_id: str, statement_id: str
) -> ImportStatementMapping | None:
    _statement(uow, owner_id, statement_id)
    return uow.imports.get_active_mapping(owner_id, statement_id)


def _trust_decision(
    uow: ImportsUnitOfWork,
    owner_id: str,
    statement_id: str,
    expected_version: int,
    state: TrustState,
    decision: StatementDecisionType,
    clock: Clock | None,
) -> ImportStatement:
    before = _statement(uow, owner_id, statement_id)
    timestamp = now_text(clock or SystemClock())
    updated = uow.imports.update_statement(
        owner_id,
        statement_id,
        expected_version,
        {"trust_state": state, "updated_at": timestamp},
    )
    if updated is None:
        raise PreconditionFailedError("The statement changed; reload it and retry.")
    uow.imports.append_statement_decision(
        ImportStatementDecision(
            new_id(), owner_id, statement_id, decision, None, timestamp
        )
    )
    _advance_import_status(uow, updated, ImportStatus.LEARNER_REVIEW, timestamp)
    _audit(
        uow,
        owner_id,
        None,
        "import_statement",
        statement_id,
        decision.value,
        hash_payload(before),
        hash_payload(updated),
        timestamp,
    )
    return updated


def _refresh_topic_hash(
    uow: ImportsUnitOfWork,
    owner_id: str,
    goal_id: str,
    graph_version_id: str,
    topic_id: str,
    timestamp: str,
) -> TopicImportHash:
    approved = uow.imports.list_approved_mappings(
        owner_id, goal_id, graph_version_id, topic_id
    )
    digest = hash_payload(
        [
            {"mapping_id": mapping.id, "statement_hash": statement.normalized_hash}
            for mapping, statement in sorted(approved, key=lambda pair: pair[0].id)
        ]
    )
    return uow.imports.upsert_topic_hash(
        TopicImportHash(
            owner_id, goal_id, graph_version_id, topic_id, digest, timestamp
        )
    )


def _statement(
    uow: ImportsUnitOfWork, owner_id: str, statement_id: str
) -> ImportStatement:
    statement = uow.imports.get_statement(owner_id, statement_id)
    if statement is None:
        raise NotFoundError(f"Import statement '{statement_id}' was not found.")
    return statement


def _advance_import_status(
    uow: ImportsUnitOfWork,
    statement: ImportStatement,
    status: ImportStatus,
    timestamp: str,
) -> None:
    record = uow.imports.get_import(statement.owner_id, statement.import_id)
    if record is not None and record.status is not status:
        changed = uow.imports.update_import(
            statement.owner_id,
            statement.import_id,
            record.row_version,
            {"status": status, "updated_at": timestamp},
        )
        if changed is None:
            raise PreconditionFailedError(
                "The import changed while saving its review decision; retry."
            )


def _audit(
    uow: ImportsUnitOfWork,
    owner_id: str,
    goal_id: str | None,
    entity_type: str,
    entity_id: str,
    action: str,
    before_hash: str | None,
    after_hash: str | None,
    timestamp: str,
) -> None:
    uow.audit.append(
        AuditEvent(
            new_id(),
            owner_id,
            goal_id,
            "learner",
            entity_type,
            entity_id,
            action,
            before_hash,
            after_hash,
            None,
            None,
            None,
            timestamp,
        )
    )
