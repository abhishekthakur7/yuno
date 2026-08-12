"""Owner-scoped SQLAlchemy repository for imports."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select, update

from yuno.modules.imports.domain import (
    ImportIdempotencyRecord,
    ImportRecord,
    ImportStatement,
    ImportStatementDecision,
    ImportStatementMapping,
    ImportStatus,
    ImportType,
    MappingDecision,
    MappingState,
    TopicImportHash,
    TrustState,
)
from yuno.modules.imports.models import (
    ImportRecordRow,
    ImportsIdempotencyRow,
    ImportStatementDecisionRow,
    ImportStatementMappingRow,
    ImportStatementRow,
    TopicImportHashRow,
)
from yuno.shared.infrastructure.repository import (
    SqlAlchemyRepository,
    owner_scoped_select,
)


class SqlAlchemyImportRepository(SqlAlchemyRepository):
    def add_import(self, record: ImportRecord) -> ImportRecord:
        self._session.add(
            ImportRecordRow(
                id=record.id,
                owner_id=record.owner_id,
                goal_id=record.goal_id,
                type=record.import_type.value,
                original_content=record.original_content,
                original_hash=record.original_hash,
                parser_version=record.parser_version,
                status=record.status.value,
                failure_code=record.failure_code,
                failure_reference=record.failure_reference,
                row_version=record.row_version,
                created_at=record.created_at,
                updated_at=record.updated_at,
            )
        )
        self._session.flush()
        return record

    def get_import(self, owner_id: str, import_id: str) -> ImportRecord | None:
        row = self._session.scalars(
            owner_scoped_select(ImportRecordRow, owner_id).where(
                ImportRecordRow.id == import_id
            )
        ).one_or_none()
        return _record(row) if row else None

    def list_imports(
        self, owner_id: str, goal_id: str | None = None
    ) -> Sequence[ImportRecord]:
        stmt = owner_scoped_select(ImportRecordRow, owner_id)
        if goal_id is not None:
            stmt = stmt.where(ImportRecordRow.goal_id == goal_id)
        rows = self._session.scalars(
            stmt.order_by(ImportRecordRow.created_at, ImportRecordRow.id)
        ).all()
        return tuple(_record(row) for row in rows)

    def update_import(
        self,
        owner_id: str,
        import_id: str,
        expected_version: int,
        changes: dict[str, object],
    ) -> ImportRecord | None:
        values = _enum_values(changes)
        values["row_version"] = expected_version + 1
        result = self._session.execute(
            update(ImportRecordRow)
            .where(
                ImportRecordRow.owner_id == owner_id,
                ImportRecordRow.id == import_id,
                ImportRecordRow.row_version == expected_version,
            )
            .values(**values)
        )
        if result.rowcount != 1:
            return None
        self._session.flush()
        return self.get_import(owner_id, import_id)

    def add_statement(self, statement: ImportStatement) -> ImportStatement:
        self._session.add(
            ImportStatementRow(
                id=statement.id,
                owner_id=statement.owner_id,
                import_id=statement.import_id,
                sequence=statement.sequence,
                parser_version=statement.parser_version,
                original_text=statement.original_text,
                original_hash=statement.original_hash,
                normalized_text=statement.normalized_text,
                normalized_hash=statement.normalized_hash,
                confidence=statement.confidence,
                duplicate_of_statement_id=statement.duplicate_of_statement_id,
                trust_state=statement.trust_state.value,
                mapping_state=statement.mapping_state.value,
                corrected_text=statement.corrected_text,
                row_version=statement.row_version,
                created_at=statement.created_at,
                updated_at=statement.updated_at,
            )
        )
        self._session.flush()
        return statement

    def get_statement(self, owner_id: str, statement_id: str) -> ImportStatement | None:
        row = self._session.scalars(
            owner_scoped_select(ImportStatementRow, owner_id).where(
                ImportStatementRow.id == statement_id
            )
        ).one_or_none()
        return _statement(row) if row else None

    def get_statement_for_occurrence(
        self, owner_id: str, import_id: str, sequence: int, parser_version: str
    ) -> ImportStatement | None:
        row = self._session.scalars(
            owner_scoped_select(ImportStatementRow, owner_id).where(
                ImportStatementRow.import_id == import_id,
                ImportStatementRow.sequence == sequence,
                ImportStatementRow.parser_version == parser_version,
            )
        ).one_or_none()
        return _statement(row) if row else None

    def get_unmapped_canonical_by_hash(
        self, owner_id: str, parser_version: str, normalized_hash: str
    ) -> ImportStatement | None:
        row = self._session.scalars(
            owner_scoped_select(ImportStatementRow, owner_id)
            .where(
                ImportStatementRow.parser_version == parser_version,
                ImportStatementRow.normalized_hash == normalized_hash,
                ImportStatementRow.mapping_state == MappingState.UNMAPPED.value,
            )
            .order_by(ImportStatementRow.created_at, ImportStatementRow.id)
            .limit(1)
        ).first()
        return _statement(row) if row else None

    def list_statements(
        self, owner_id: str, import_id: str
    ) -> Sequence[ImportStatement]:
        rows = self._session.scalars(
            owner_scoped_select(ImportStatementRow, owner_id)
            .where(ImportStatementRow.import_id == import_id)
            .order_by(
                ImportStatementRow.parser_version,
                ImportStatementRow.sequence,
                ImportStatementRow.id,
            )
        ).all()
        return tuple(_statement(row) for row in rows)

    def update_statement(
        self,
        owner_id: str,
        statement_id: str,
        expected_version: int,
        changes: dict[str, object],
    ) -> ImportStatement | None:
        values = _enum_values(changes)
        values["row_version"] = expected_version + 1
        result = self._session.execute(
            update(ImportStatementRow)
            .where(
                ImportStatementRow.owner_id == owner_id,
                ImportStatementRow.id == statement_id,
                ImportStatementRow.row_version == expected_version,
            )
            .values(**values)
        )
        if result.rowcount != 1:
            return None
        self._session.flush()
        return self.get_statement(owner_id, statement_id)

    def append_statement_decision(
        self, decision: ImportStatementDecision
    ) -> ImportStatementDecision:
        self._session.add(
            ImportStatementDecisionRow(
                id=decision.id,
                owner_id=decision.owner_id,
                statement_id=decision.statement_id,
                decision_type=decision.decision_type.value,
                value=decision.value,
                decided_at=decision.decided_at,
            )
        )
        self._session.flush()
        return decision

    def append_mapping(self, mapping: ImportStatementMapping) -> ImportStatementMapping:
        self._session.add(
            ImportStatementMappingRow(
                id=mapping.id,
                owner_id=mapping.owner_id,
                goal_id=mapping.goal_id,
                statement_id=mapping.statement_id,
                topic_stable_id=mapping.topic_stable_id,
                graph_version_id=mapping.graph_version_id,
                decision=mapping.decision.value,
                accepted_at=mapping.accepted_at,
                revoked_at=mapping.revoked_at,
            )
        )
        self._session.flush()
        return mapping

    def get_active_mapping(
        self, owner_id: str, statement_id: str
    ) -> ImportStatementMapping | None:
        row = self._session.scalars(
            owner_scoped_select(ImportStatementMappingRow, owner_id).where(
                ImportStatementMappingRow.statement_id == statement_id,
                ImportStatementMappingRow.decision == MappingDecision.APPROVED.value,
                ImportStatementMappingRow.revoked_at.is_(None),
            )
        ).one_or_none()
        return _mapping(row) if row else None

    def revoke_mapping(
        self, owner_id: str, mapping_id: str, revoked_at: str
    ) -> ImportStatementMapping | None:
        result = self._session.execute(
            update(ImportStatementMappingRow)
            .where(
                ImportStatementMappingRow.owner_id == owner_id,
                ImportStatementMappingRow.id == mapping_id,
                ImportStatementMappingRow.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        if result.rowcount != 1:
            return None
        self._session.flush()
        row = self._session.scalars(
            owner_scoped_select(ImportStatementMappingRow, owner_id).where(
                ImportStatementMappingRow.id == mapping_id
            )
        ).one()
        return _mapping(row)

    def list_approved_mappings(
        self, owner_id: str, goal_id: str, graph_version_id: str, topic_stable_id: str
    ) -> Sequence[tuple[ImportStatementMapping, ImportStatement]]:
        stmt = (
            select(ImportStatementMappingRow, ImportStatementRow)
            .join(
                ImportStatementRow,
                ImportStatementRow.id == ImportStatementMappingRow.statement_id,
            )
            .where(
                ImportStatementMappingRow.owner_id == owner_id,
                ImportStatementMappingRow.goal_id == goal_id,
                ImportStatementMappingRow.graph_version_id == graph_version_id,
                ImportStatementMappingRow.topic_stable_id == topic_stable_id,
                ImportStatementMappingRow.decision == MappingDecision.APPROVED.value,
                ImportStatementMappingRow.revoked_at.is_(None),
            )
            .order_by(ImportStatementMappingRow.id)
        )
        return tuple(
            (_mapping(mapping), _statement(statement))
            for mapping, statement in self._session.execute(stmt).all()
        )

    def upsert_topic_hash(self, topic_hash: TopicImportHash) -> TopicImportHash:
        existing = self.get_topic_hash(
            topic_hash.owner_id,
            topic_hash.goal_id,
            topic_hash.graph_version_id,
            topic_hash.topic_stable_id,
        )
        if existing is None:
            self._session.add(TopicImportHashRow(**topic_hash.__dict__))
        else:
            self._session.execute(
                update(TopicImportHashRow)
                .where(
                    TopicImportHashRow.owner_id == topic_hash.owner_id,
                    TopicImportHashRow.goal_id == topic_hash.goal_id,
                    TopicImportHashRow.graph_version_id == topic_hash.graph_version_id,
                    TopicImportHashRow.topic_stable_id == topic_hash.topic_stable_id,
                )
                .values(
                    imports_hash=topic_hash.imports_hash,
                    updated_at=topic_hash.updated_at,
                )
            )
        self._session.flush()
        return topic_hash

    def get_topic_hash(
        self, owner_id: str, goal_id: str, graph_version_id: str, topic_stable_id: str
    ) -> TopicImportHash | None:
        row = self._session.get(
            TopicImportHashRow, (owner_id, goal_id, graph_version_id, topic_stable_id)
        )
        return (
            TopicImportHash(
                row.owner_id,
                row.goal_id,
                row.graph_version_id,
                row.topic_stable_id,
                row.imports_hash,
                row.updated_at,
            )
            if row
            else None
        )

    def add_idempotency(
        self, record: ImportIdempotencyRecord
    ) -> ImportIdempotencyRecord:
        self._session.add(ImportsIdempotencyRow(**record.__dict__))
        self._session.flush()
        return record

    def get_idempotency(
        self, owner_id: str, operation: str, idempotency_key: str
    ) -> ImportIdempotencyRecord | None:
        row = self._session.scalars(
            owner_scoped_select(ImportsIdempotencyRow, owner_id).where(
                ImportsIdempotencyRow.operation == operation,
                ImportsIdempotencyRow.idempotency_key == idempotency_key,
            )
        ).one_or_none()
        return (
            ImportIdempotencyRecord(
                row.id,
                row.owner_id,
                row.operation,
                row.idempotency_key,
                row.request_hash,
                row.response_json,
                row.created_at,
            )
            if row
            else None
        )


def _record(row: ImportRecordRow) -> ImportRecord:
    return ImportRecord(
        row.id,
        row.owner_id,
        row.goal_id,
        ImportType(row.type),
        bytes(row.original_content),
        row.original_hash,
        row.parser_version,
        ImportStatus(row.status),
        row.failure_code,
        row.failure_reference,
        row.row_version,
        row.created_at,
        row.updated_at,
    )


def _statement(row: ImportStatementRow) -> ImportStatement:
    return ImportStatement(
        row.id,
        row.owner_id,
        row.import_id,
        row.sequence,
        row.parser_version,
        row.original_text,
        row.original_hash,
        row.normalized_text,
        row.normalized_hash,
        row.confidence,
        row.duplicate_of_statement_id,
        TrustState(row.trust_state),
        MappingState(row.mapping_state),
        row.corrected_text,
        row.row_version,
        row.created_at,
        row.updated_at,
    )


def _mapping(row: ImportStatementMappingRow) -> ImportStatementMapping:
    return ImportStatementMapping(
        row.id,
        row.owner_id,
        row.goal_id,
        row.statement_id,
        row.topic_stable_id,
        row.graph_version_id,
        MappingDecision(row.decision),
        row.accepted_at,
        row.revoked_at,
    )


def _enum_values(changes: dict[str, object]) -> dict[str, object]:
    return {
        key: value.value if hasattr(value, "value") else value
        for key, value in changes.items()
    }
