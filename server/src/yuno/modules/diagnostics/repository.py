"""Owner-scoped SQLAlchemy adapter for diagnostic persistence."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from sqlalchemy import delete, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from yuno.modules.diagnostics.domain import (
    DiagnosticAnswer,
    DiagnosticConfidence,
    DiagnosticPreviewEdit,
    DiagnosticSession,
    DiagnosticsIdempotencyRecord,
    DiagnosticState,
    UntrustedSeedKind,
)
from yuno.modules.diagnostics.models import (
    DiagnosticAnswerRow,
    DiagnosticPreviewEditRow,
    DiagnosticsCommandLockRow,
    DiagnosticSessionRow,
    DiagnosticsIdempotencyRow,
)
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.infrastructure.repository import (
    SqlAlchemyRepository,
    owner_scoped_select,
)


class SqlAlchemyDiagnosticsRepository(SqlAlchemyRepository):
    __slots__ = ("_clock",)

    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self._clock = SystemClock()

    def create_session(self, session: DiagnosticSession) -> DiagnosticSession:
        row = DiagnosticSessionRow(
            id=session.id,
            owner_id=session.owner_id,
            captured_graph_version_id=session.captured_graph_version_id,
            question_set_version=session.question_set_version,
            setup_inputs_json=_encode_setup_inputs(session.setup_inputs),
            untrusted_seed_kind=(
                session.untrusted_seed_kind.value
                if session.untrusted_seed_kind is not None
                else None
            ),
            untrusted_seed_text=session.untrusted_seed_text,
            seed_skipped=int(session.seed_skipped),
            diagnostic_skipped=int(session.diagnostic_skipped),
            state=session.state.value,
            started_at=session.started_at,
            paused_at=session.paused_at,
            expires_at=session.expires_at,
            failure_code=session.failure_code,
            failure_reference=session.failure_reference,
            confirmed_goal_id=session.confirmed_goal_id,
            row_version=session.row_version,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )
        self._session.add(row)
        self._session.flush()
        return _session_to_domain(row)

    def get_session(self, owner_id: str, session_id: str) -> DiagnosticSession | None:
        row = self._session.scalars(
            owner_scoped_select(DiagnosticSessionRow, owner_id).where(
                DiagnosticSessionRow.id == session_id
            )
        ).one_or_none()
        return _session_to_domain(row) if row is not None else None

    def get_latest_unconfirmed_session(
        self, owner_id: str
    ) -> DiagnosticSession | None:
        row = self._session.scalars(
            owner_scoped_select(DiagnosticSessionRow, owner_id)
            .where(DiagnosticSessionRow.state != DiagnosticState.CONFIRMED.value)
            .order_by(
                DiagnosticSessionRow.updated_at.desc(),
                DiagnosticSessionRow.id.desc(),
            )
            .limit(1)
        ).one_or_none()
        return _session_to_domain(row) if row is not None else None

    def update_session(
        self,
        owner_id: str,
        session_id: str,
        expected_row_version: int,
        changes: Mapping[str, object],
    ) -> DiagnosticSession | None:
        values = _session_changes_to_storage(changes)
        values.update(
            row_version=expected_row_version + 1,
            updated_at=now_text(self._clock),
        )
        result = self._session.execute(
            update(DiagnosticSessionRow)
            .where(
                DiagnosticSessionRow.owner_id == owner_id,
                DiagnosticSessionRow.id == session_id,
                DiagnosticSessionRow.row_version == expected_row_version,
            )
            .values(**values)
        )
        if result.rowcount != 1:
            return None
        self._session.flush()
        return self.get_session(owner_id, session_id)

    def append_answer(self, answer: DiagnosticAnswer) -> DiagnosticAnswer:
        row = DiagnosticAnswerRow(
            id=answer.id,
            owner_id=answer.owner_id,
            session_id=answer.session_id,
            sequence=answer.sequence,
            question_ref=answer.question_ref,
            answer=answer.answer,
            confidence=answer.confidence.value,
            adaptive_context_version=answer.adaptive_context_version,
            answered_at=answer.answered_at,
        )
        self._session.add(row)
        self._session.flush()
        return _answer_to_domain(row)

    def list_answers(
        self, owner_id: str, session_id: str
    ) -> Sequence[DiagnosticAnswer]:
        rows = self._session.scalars(
            owner_scoped_select(DiagnosticAnswerRow, owner_id)
            .where(DiagnosticAnswerRow.session_id == session_id)
            .order_by(DiagnosticAnswerRow.sequence)
        ).all()
        return tuple(_answer_to_domain(row) for row in rows)

    def replace_preview_edits(
        self,
        owner_id: str,
        session_id: str,
        edits: Sequence[DiagnosticPreviewEdit],
    ) -> None:
        self._session.execute(
            delete(DiagnosticPreviewEditRow).where(
                DiagnosticPreviewEditRow.owner_id == owner_id,
                DiagnosticPreviewEditRow.session_id == session_id,
            )
        )
        self._session.add_all(
            DiagnosticPreviewEditRow(
                id=edit.id,
                owner_id=edit.owner_id,
                session_id=edit.session_id,
                sequence=edit.sequence,
                topic_stable_id=edit.topic_stable_id,
                entry_type=edit.entry_type,
                value_json=json.dumps(edit.value, sort_keys=True, separators=(",", ":")),
                reason=edit.reason,
                updated_at=edit.updated_at,
            )
            for edit in edits
        )
        self._session.flush()

    def list_preview_edits(
        self, owner_id: str, session_id: str
    ) -> Sequence[DiagnosticPreviewEdit]:
        rows = self._session.scalars(
            owner_scoped_select(DiagnosticPreviewEditRow, owner_id)
            .where(DiagnosticPreviewEditRow.session_id == session_id)
            .order_by(DiagnosticPreviewEditRow.sequence)
        ).all()
        return tuple(
            DiagnosticPreviewEdit(
                id=row.id,
                owner_id=row.owner_id,
                session_id=row.session_id,
                sequence=row.sequence,
                topic_stable_id=row.topic_stable_id,
                entry_type=row.entry_type,
                value=json.loads(row.value_json),
                reason=row.reason,
                updated_at=row.updated_at,
            )
            for row in rows
        )

    def get_idempotency(
        self, owner_id: str, operation: str, key: str
    ) -> DiagnosticsIdempotencyRecord | None:
        row = self._session.scalars(
            owner_scoped_select(DiagnosticsIdempotencyRow, owner_id).where(
                DiagnosticsIdempotencyRow.operation == operation,
                DiagnosticsIdempotencyRow.idempotency_key == key,
            )
        ).one_or_none()
        if row is None:
            return None
        return DiagnosticsIdempotencyRecord(
            id=row.id,
            owner_id=row.owner_id,
            operation=row.operation,
            idempotency_key=row.idempotency_key,
            request_hash=row.request_hash,
            session_id=row.session_id,
            response_json=row.response_json,
            created_at=row.created_at,
        )

    def lock_idempotency_commands(self, owner_id: str) -> None:
        # Materialize a stable per-owner target before taking the no-op
        # write lock. Concurrent first commands serialize on the insert;
        # later commands serialize on the update.
        self._session.execute(
            sqlite_insert(DiagnosticsCommandLockRow)
            .values(
                owner_id=owner_id,
                created_at=now_text(self._clock),
            )
            .on_conflict_do_nothing(index_elements=["owner_id"])
        )
        self._session.execute(
            update(DiagnosticsCommandLockRow)
            .where(DiagnosticsCommandLockRow.owner_id == owner_id)
            .values(owner_id=owner_id)
        )

    def add_idempotency(self, record: DiagnosticsIdempotencyRecord) -> None:
        self._session.add(DiagnosticsIdempotencyRow(**record.__dict__))
        self._session.flush()


def _encode_setup_inputs(inputs: Mapping[str, object]) -> str:
    return json.dumps(dict(inputs), sort_keys=True, separators=(",", ":"))


def _session_changes_to_storage(changes: Mapping[str, object]) -> dict[str, object]:
    values = dict(changes)
    if "setup_inputs" in values:
        values["setup_inputs_json"] = _encode_setup_inputs(values.pop("setup_inputs"))  # type: ignore[arg-type]
    for name in ("state", "untrusted_seed_kind"):
        value = values.get(name)
        if value is not None:
            values[name] = value.value  # type: ignore[union-attr]
    for name in ("seed_skipped", "diagnostic_skipped"):
        if name in values:
            values[name] = int(bool(values[name]))
    return values


def _session_to_domain(row: DiagnosticSessionRow) -> DiagnosticSession:
    return DiagnosticSession(
        id=row.id,
        owner_id=row.owner_id,
        captured_graph_version_id=row.captured_graph_version_id,
        question_set_version=row.question_set_version,
        setup_inputs=json.loads(row.setup_inputs_json),
        untrusted_seed_kind=(
            UntrustedSeedKind(row.untrusted_seed_kind)
            if row.untrusted_seed_kind is not None
            else None
        ),
        untrusted_seed_text=row.untrusted_seed_text,
        seed_skipped=bool(row.seed_skipped),
        diagnostic_skipped=bool(row.diagnostic_skipped),
        state=DiagnosticState(row.state),
        started_at=row.started_at,
        paused_at=row.paused_at,
        expires_at=row.expires_at,
        failure_code=row.failure_code,
        failure_reference=row.failure_reference,
        confirmed_goal_id=row.confirmed_goal_id,
        row_version=row.row_version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _answer_to_domain(row: DiagnosticAnswerRow) -> DiagnosticAnswer:
    return DiagnosticAnswer(
        id=row.id,
        owner_id=row.owner_id,
        session_id=row.session_id,
        sequence=row.sequence,
        question_ref=row.question_ref,
        answer=row.answer,
        confidence=DiagnosticConfidence(row.confidence),
        adaptive_context_version=row.adaptive_context_version,
        answered_at=row.answered_at,
    )
