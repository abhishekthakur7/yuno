"""Repository and unit-of-work protocols for diagnostics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from yuno.modules.audit.ports import AuditRepository
from yuno.modules.diagnostics.domain import (
    DiagnosticAnswer,
    DiagnosticPreviewEdit,
    DiagnosticSession,
    DiagnosticsIdempotencyRecord,
)
from yuno.shared.application.unit_of_work import UnitOfWork


class DiagnosticsRepository(Protocol):
    def create_session(self, session: DiagnosticSession) -> DiagnosticSession: ...

    def get_session(
        self, owner_id: str, session_id: str
    ) -> DiagnosticSession | None: ...

    def get_latest_unconfirmed_session(
        self, owner_id: str
    ) -> DiagnosticSession | None: ...

    def update_session(
        self,
        owner_id: str,
        session_id: str,
        expected_row_version: int,
        changes: Mapping[str, object],
    ) -> DiagnosticSession | None: ...

    def append_answer(self, answer: DiagnosticAnswer) -> DiagnosticAnswer: ...

    def list_answers(
        self, owner_id: str, session_id: str
    ) -> Sequence[DiagnosticAnswer]: ...

    def replace_preview_edits(
        self,
        owner_id: str,
        session_id: str,
        edits: Sequence[DiagnosticPreviewEdit],
    ) -> None: ...

    def list_preview_edits(
        self, owner_id: str, session_id: str
    ) -> Sequence[DiagnosticPreviewEdit]: ...

    def get_idempotency(
        self, owner_id: str, operation: str, key: str
    ) -> DiagnosticsIdempotencyRecord | None: ...

    def lock_idempotency_commands(self, owner_id: str) -> None: ...

    def add_idempotency(self, record: DiagnosticsIdempotencyRecord) -> None: ...


class DiagnosticsUnitOfWork(UnitOfWork, Protocol):
    diagnostics: DiagnosticsRepository
    audit: AuditRepository
