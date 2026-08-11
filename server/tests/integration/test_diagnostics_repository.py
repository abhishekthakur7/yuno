"""Focused persistence guarantees for diagnostic sessions and answers."""

from __future__ import annotations

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from yuno.modules.canonical.domain import (
    CanonicalGraphVersion,
    CanonicalVersionStatus,
    EditorialApproval,
)
from yuno.modules.diagnostics.domain import (
    DiagnosticAnswer,
    DiagnosticConfidence,
    DiagnosticSession,
    DiagnosticState,
    UntrustedSeedKind,
)
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.ids import new_id


def _approved_graph(uow, owner_id: str) -> str:
    graph_id = new_id()
    timestamp = now_text(SystemClock())
    uow.canonical.create_version(
        CanonicalGraphVersion(
            id=graph_id,
            version_label=f"diagnostic-{graph_id}",
            manifest_version="v1",
            manifest_hash=f"diagnostic-hash-{graph_id}",
            status=CanonicalVersionStatus.PUBLISHED,
            creator_owner_id=owner_id,
            created_at=timestamp,
            published_at=timestamp,
            supersedes_version_id=None,
        )
    )
    uow.canonical.record_approval(
        EditorialApproval(
            id=new_id(),
            graph_version_id=graph_id,
            approver_owner_id=owner_id,
            approver_role="designated_editorial_approver",
            basis_ref="diagnostic-storage-test",
            approved_at=timestamp,
        )
    )
    return graph_id


def _session(*, owner_id: str, graph_id: str) -> DiagnosticSession:
    timestamp = now_text(SystemClock())
    return DiagnosticSession(
        id=new_id(),
        owner_id=owner_id,
        captured_graph_version_id=graph_id,
        question_set_version="diagnostic-fixture-v1",
        setup_inputs={"path": "learn", "subject": "RDB", "nested": {"level": 2}},
        state=DiagnosticState.IN_PROGRESS,
        untrusted_seed_kind=UntrustedSeedKind.LEARN_NOTES,
        untrusted_seed_text="# raw note\n\n`SELECT *` is always best?",
        seed_skipped=False,
        diagnostic_skipped=False,
        started_at=timestamp,
        paused_at=None,
        expires_at=None,
        failure_code=None,
        failure_reference=None,
        confirmed_goal_id=None,
        row_version=1,
        created_at=timestamp,
        updated_at=timestamp,
    )


def test_session_and_answers_survive_commit_and_reload(
    uow_factory: UnitOfWorkFactory,
) -> None:
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Owner")
        graph_id = _approved_graph(uow, owner.id)
        diagnostic = uow.diagnostics.create_session(
            _session(owner_id=owner.id, graph_id=graph_id)
        )
        for sequence, confidence in (
            (1, DiagnosticConfidence.LOW),
            (2, DiagnosticConfidence.HIGH),
        ):
            uow.diagnostics.append_answer(
                DiagnosticAnswer(
                    id=new_id(),
                    owner_id=owner.id,
                    session_id=diagnostic.id,
                    sequence=sequence,
                    question_ref=f"question-{sequence}",
                    answer=f"verbatim answer {sequence}",
                    confidence=confidence,
                    adaptive_context_version="diagnostic-fixture-v1",
                    answered_at=now_text(SystemClock()),
                )
            )
        paused = uow.diagnostics.update_session(
            owner.id,
            diagnostic.id,
            1,
            {"state": DiagnosticState.PAUSED, "paused_at": now_text(SystemClock())},
        )
        assert paused is not None
        uow.commit()

    with uow_factory() as uow:
        reloaded = uow.diagnostics.get_session(owner.id, diagnostic.id)
        answers = uow.diagnostics.list_answers(owner.id, diagnostic.id)

    assert reloaded is not None
    assert reloaded.state is DiagnosticState.PAUSED
    assert reloaded.row_version == 2
    assert reloaded.expires_at is None
    assert reloaded.setup_inputs == {
        "nested": {"level": 2},
        "path": "learn",
        "subject": "RDB",
    }
    assert reloaded.untrusted_seed_text == "# raw note\n\n`SELECT *` is always best?"
    assert [answer.sequence for answer in answers] == [1, 2]
    assert [answer.answer for answer in answers] == [
        "verbatim answer 1",
        "verbatim answer 2",
    ]


def test_captured_graph_must_have_an_approval(
    uow_factory: UnitOfWorkFactory,
) -> None:
    with pytest.raises(IntegrityError), uow_factory() as uow:
        owner = uow.owners.create_local_owner("Owner")
        timestamp = now_text(SystemClock())
        graph_id = new_id()
        uow.canonical.create_version(
            CanonicalGraphVersion(
                id=graph_id,
                version_label="unapproved-diagnostic-graph",
                manifest_version="v1",
                manifest_hash="unapproved-diagnostic-hash",
                status=CanonicalVersionStatus.PENDING_APPROVAL,
                creator_owner_id=owner.id,
                created_at=timestamp,
                published_at=None,
                supersedes_version_id=None,
            )
        )
        uow.diagnostics.create_session(_session(owner_id=owner.id, graph_id=graph_id))


def test_answer_rows_are_database_enforced_append_only(
    uow_factory: UnitOfWorkFactory, engine: Engine
) -> None:
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Owner")
        diagnostic = uow.diagnostics.create_session(
            _session(owner_id=owner.id, graph_id=_approved_graph(uow, owner.id))
        )
        answer = uow.diagnostics.append_answer(
            DiagnosticAnswer(
                id=new_id(),
                owner_id=owner.id,
                session_id=diagnostic.id,
                sequence=1,
                question_ref="question-1",
                answer="original",
                confidence=DiagnosticConfidence.MEDIUM,
                adaptive_context_version="diagnostic-fixture-v1",
                answered_at=now_text(SystemClock()),
            )
        )
        uow.commit()

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text("UPDATE diagnostic_answers SET answer = 'changed' WHERE id = :id"),
            {"id": answer.id},
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text("DELETE FROM diagnostic_answers WHERE id = :id"),
            {"id": answer.id},
        )
