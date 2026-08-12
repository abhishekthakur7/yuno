"""Interfaces owned by the imports bounded context."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from yuno.modules.audit.ports import AuditRepository
from yuno.modules.imports.domain import (
    ImportIdempotencyRecord,
    ImportRecord,
    ImportStatement,
    ImportStatementDecision,
    ImportStatementMapping,
    TopicImportHash,
)
from yuno.shared.application.unit_of_work import UnitOfWork


class ImportRepository(Protocol):
    def add_import(self, record: ImportRecord) -> ImportRecord: ...
    def get_import(self, owner_id: str, import_id: str) -> ImportRecord | None: ...
    def list_imports(
        self, owner_id: str, goal_id: str | None = None
    ) -> Sequence[ImportRecord]: ...
    def update_import(
        self,
        owner_id: str,
        import_id: str,
        expected_version: int,
        changes: dict[str, object],
    ) -> ImportRecord | None: ...
    def add_statement(self, statement: ImportStatement) -> ImportStatement: ...
    def get_statement(
        self, owner_id: str, statement_id: str
    ) -> ImportStatement | None: ...
    def get_statement_for_occurrence(
        self, owner_id: str, import_id: str, sequence: int, parser_version: str
    ) -> ImportStatement | None: ...
    def get_unmapped_canonical_by_hash(
        self, owner_id: str, parser_version: str, normalized_hash: str
    ) -> ImportStatement | None: ...
    def list_statements(
        self, owner_id: str, import_id: str
    ) -> Sequence[ImportStatement]: ...
    def update_statement(
        self,
        owner_id: str,
        statement_id: str,
        expected_version: int,
        changes: dict[str, object],
    ) -> ImportStatement | None: ...
    def append_statement_decision(
        self, decision: ImportStatementDecision
    ) -> ImportStatementDecision: ...
    def append_mapping(
        self, mapping: ImportStatementMapping
    ) -> ImportStatementMapping: ...
    def get_active_mapping(
        self, owner_id: str, statement_id: str
    ) -> ImportStatementMapping | None: ...
    def revoke_mapping(
        self, owner_id: str, mapping_id: str, revoked_at: str
    ) -> ImportStatementMapping | None: ...
    def list_approved_mappings(
        self, owner_id: str, goal_id: str, graph_version_id: str, topic_stable_id: str
    ) -> Sequence[tuple[ImportStatementMapping, ImportStatement]]: ...
    def upsert_topic_hash(self, topic_hash: TopicImportHash) -> TopicImportHash: ...
    def get_topic_hash(
        self, owner_id: str, goal_id: str, graph_version_id: str, topic_stable_id: str
    ) -> TopicImportHash | None: ...
    def add_idempotency(
        self, record: ImportIdempotencyRecord
    ) -> ImportIdempotencyRecord: ...
    def get_idempotency(
        self, owner_id: str, operation: str, idempotency_key: str
    ) -> ImportIdempotencyRecord | None: ...


class GoalView(Protocol):
    graph_version_id: str
    status: object


class GoalRepository(Protocol):
    def get_goal(self, owner_id: str, goal_id: str) -> GoalView | None: ...


class TopicView(Protocol):
    stable_id: str


class CanonicalReadRepository(Protocol):
    def get_published_topics(self, version_id: str) -> Sequence[TopicView]: ...


class ImportsUnitOfWork(UnitOfWork, Protocol):
    imports: ImportRepository
    audit: AuditRepository
    profiles_goals: GoalRepository
    canonical: CanonicalReadRepository
