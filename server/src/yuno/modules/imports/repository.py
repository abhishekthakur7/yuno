"""Owner-scoped SQLAlchemy repository for imports."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select, update

from yuno.modules.data_lifecycle.models import (
    ImportRecordBodyRow,
    ImportsIdempotencyBodyRow,
    ImportStatementBodyRow,
    ImportStatementDecisionBodyRow,
)
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
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.infrastructure.repository import (
    SqlAlchemyRepository,
    owner_scoped_select,
)


class SqlAlchemyImportRepository(SqlAlchemyRepository):
    def count_live_imports(self, owner_id: str) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(ImportRecordBodyRow)
                .where(ImportRecordBodyRow.owner_id == owner_id)
            )
            or 0
        )

    def count_unreviewed_statements(self, owner_id: str) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(ImportStatementBodyRow)
                .join(
                    ImportStatementRow,
                    ImportStatementRow.id == ImportStatementBodyRow.statement_id,
                )
                .where(
                    ImportStatementBodyRow.owner_id == owner_id,
                    ImportStatementRow.trust_state == "untrusted",
                )
            )
            or 0
        )

    def add_import(self, record: ImportRecord) -> ImportRecord:
        self._session.add(
            ImportRecordRow(
                id=record.id,
                owner_id=record.owner_id,
                goal_id=record.goal_id,
                type=record.import_type.value,
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
        self._session.add(
            ImportRecordBodyRow(
                import_id=record.id,
                owner_id=record.owner_id,
                original_content=record.original_content,
            )
        )
        self._session.flush()
        return record

    def get_import(self, owner_id: str, import_id: str) -> ImportRecord | None:
        pair = self._session.execute(
            select(ImportRecordRow, ImportRecordBodyRow)
            .join(
                ImportRecordBodyRow,
                ImportRecordBodyRow.import_id == ImportRecordRow.id,
            )
            .where(
                ImportRecordRow.owner_id == owner_id,
                ImportRecordBodyRow.owner_id == owner_id,
                ImportRecordRow.id == import_id,
            )
        ).one_or_none()
        return _record(pair[0], bytes(pair[1].original_content)) if pair else None

    def list_imports(
        self, owner_id: str, goal_id: str | None = None
    ) -> Sequence[ImportRecord]:
        stmt = (
            select(ImportRecordRow, ImportRecordBodyRow)
            .join(
                ImportRecordBodyRow,
                ImportRecordBodyRow.import_id == ImportRecordRow.id,
            )
            .where(
                ImportRecordRow.owner_id == owner_id,
                ImportRecordBodyRow.owner_id == owner_id,
            )
        )
        if goal_id is not None:
            stmt = stmt.where(ImportRecordRow.goal_id == goal_id)
        pairs = self._session.execute(
            stmt.order_by(ImportRecordRow.created_at, ImportRecordRow.id)
        ).all()
        return tuple(_record(row, bytes(body.original_content)) for row, body in pairs)

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
                original_hash=statement.original_hash,
                normalized_hash=statement.normalized_hash,
                confidence=statement.confidence,
                duplicate_of_statement_id=statement.duplicate_of_statement_id,
                trust_state=statement.trust_state.value,
                mapping_state=statement.mapping_state.value,
                corrected_hash=statement.normalized_hash
                if statement.corrected_text
                else None,
                row_version=statement.row_version,
                created_at=statement.created_at,
                updated_at=statement.updated_at,
            )
        )
        self._session.flush()
        self._session.add(
            ImportStatementBodyRow(
                statement_id=statement.id,
                owner_id=statement.owner_id,
                original_text=statement.original_text,
                normalized_text=statement.normalized_text,
                corrected_text=statement.corrected_text,
            )
        )
        self._session.flush()
        return statement

    def get_statement(self, owner_id: str, statement_id: str) -> ImportStatement | None:
        pair = self._session.execute(
            self._live_statement_select(owner_id).where(
                ImportStatementRow.id == statement_id
            )
        ).one_or_none()
        return _statement(*pair) if pair else None

    def get_statement_for_occurrence(
        self, owner_id: str, import_id: str, sequence: int, parser_version: str
    ) -> ImportStatement | None:
        pair = self._session.execute(
            self._live_statement_select(owner_id).where(
                ImportStatementRow.import_id == import_id,
                ImportStatementRow.sequence == sequence,
                ImportStatementRow.parser_version == parser_version,
            )
        ).one_or_none()
        return _statement(*pair) if pair else None

    def get_unmapped_canonical_by_hash(
        self, owner_id: str, parser_version: str, normalized_hash: str
    ) -> ImportStatement | None:
        pair = self._session.execute(
            self._live_statement_select(owner_id)
            .where(
                ImportStatementRow.parser_version == parser_version,
                ImportStatementRow.normalized_hash == normalized_hash,
                ImportStatementRow.mapping_state == MappingState.UNMAPPED.value,
            )
            .order_by(ImportStatementRow.created_at, ImportStatementRow.id)
            .limit(1)
        ).first()
        return _statement(*pair) if pair else None

    def list_statements(
        self, owner_id: str, import_id: str
    ) -> Sequence[ImportStatement]:
        pairs = self._session.execute(
            self._live_statement_select(owner_id)
            .where(ImportStatementRow.import_id == import_id)
            .order_by(
                ImportStatementRow.parser_version,
                ImportStatementRow.sequence,
                ImportStatementRow.id,
            )
        ).all()
        return tuple(_statement(*pair) for pair in pairs)

    def update_statement(
        self,
        owner_id: str,
        statement_id: str,
        expected_version: int,
        changes: dict[str, object],
    ) -> ImportStatement | None:
        values = _enum_values(changes)
        body_values = {
            key: values.pop(key)
            for key in ("original_text", "normalized_text", "corrected_text")
            if key in values
        }
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
        if body_values:
            self._session.execute(
                update(ImportStatementBodyRow)
                .where(
                    ImportStatementBodyRow.owner_id == owner_id,
                    ImportStatementBodyRow.statement_id == statement_id,
                )
                .values(**body_values)
            )
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
                value_hash=decision.value
                and __import__("hashlib").sha256(decision.value.encode()).hexdigest(),
                decided_at=decision.decided_at,
            )
        )
        self._session.flush()
        self._session.add(
            ImportStatementDecisionBodyRow(
                decision_id=decision.id,
                owner_id=decision.owner_id,
                value=decision.value,
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
            select(
                ImportStatementMappingRow,
                ImportStatementRow,
                ImportStatementBodyRow,
            )
            .join(
                ImportStatementRow,
                ImportStatementRow.id == ImportStatementMappingRow.statement_id,
            )
            .join(
                ImportStatementBodyRow,
                ImportStatementBodyRow.statement_id == ImportStatementRow.id,
            )
            .where(
                ImportStatementMappingRow.owner_id == owner_id,
                ImportStatementBodyRow.owner_id == owner_id,
                ImportStatementMappingRow.goal_id == goal_id,
                ImportStatementMappingRow.graph_version_id == graph_version_id,
                ImportStatementMappingRow.topic_stable_id == topic_stable_id,
                ImportStatementMappingRow.decision == MappingDecision.APPROVED.value,
                ImportStatementMappingRow.revoked_at.is_(None),
            )
            .order_by(ImportStatementMappingRow.id)
        )
        return tuple(
            (_mapping(mapping), _statement(statement, body))
            for mapping, statement, body in self._session.execute(stmt).all()
        )

    @staticmethod
    def _live_statement_select(owner_id: str):
        return (
            select(ImportStatementRow, ImportStatementBodyRow)
            .join(
                ImportStatementBodyRow,
                ImportStatementBodyRow.statement_id == ImportStatementRow.id,
            )
            .where(
                ImportStatementRow.owner_id == owner_id,
                ImportStatementBodyRow.owner_id == owner_id,
            )
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
        values = record.__dict__.copy()
        response_json = values.pop("response_json")
        values["response_hash"] = hash_payload(response_json)
        self._session.add(ImportsIdempotencyRow(**values))
        self._session.flush()
        self._session.add(
            ImportsIdempotencyBodyRow(
                idempotency_id=record.id,
                owner_id=record.owner_id,
                response_json=response_json,
            )
        )
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
        body = self._session.get(ImportsIdempotencyBodyRow, row.id) if row else None
        return (
            ImportIdempotencyRecord(
                row.id,
                row.owner_id,
                row.operation,
                row.idempotency_key,
                row.request_hash,
                body.response_json,
                row.created_at,
            )
            if row and body
            else None
        )


def _record(row: ImportRecordRow, original_content: bytes) -> ImportRecord:
    return ImportRecord(
        row.id,
        row.owner_id,
        row.goal_id,
        ImportType(row.type),
        original_content,
        row.original_hash,
        row.parser_version,
        ImportStatus(row.status),
        row.failure_code,
        row.failure_reference,
        row.row_version,
        row.created_at,
        row.updated_at,
    )


def _statement(
    row: ImportStatementRow, body: ImportStatementBodyRow
) -> ImportStatement:
    return ImportStatement(
        row.id,
        row.owner_id,
        row.import_id,
        row.sequence,
        row.parser_version,
        body.original_text,
        row.original_hash,
        body.normalized_text,
        row.normalized_hash,
        row.confidence,
        row.duplicate_of_statement_id,
        TrustState(row.trust_state),
        MappingState(row.mapping_state),
        body.corrected_text,
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
