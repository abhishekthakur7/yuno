"""Integration tests proving DAT-01 owner-scoped isolation: a record
written under owner A is unreachable through any repository call scoped to
owner B.

A note on how "owner B" gets created here. `owners.kind` carries both
`CheckConstraint("kind IN ('local_builtin')")` and `unique=True`
(`infrastructure/models/identity.py`; same in migration `442e2f56adb9`).
Combined, those two constraints make `owners` a true singleton under every
*normal* insert path -- application or raw SQL alike: a second row with
`kind='local_builtin'` violates UNIQUE, and a second row with any other
`kind` violates CHECK. So `SqlAlchemyOwnerRepository` (which only ever
writes `kind='local_builtin'`) can never produce a second owner, and
neither can a naive raw INSERT.

SQLite's `PRAGMA ignore_check_constraints = ON` disables CHECK enforcement
for the connection it is set on while leaving UNIQUE/FK/NOT NULL/PK
enforcement untouched -- the one documented escape hatch narrow enough for
a test fixture to use. `_insert_second_owner` below opens its own
short-lived raw `sqlite3` connection (never the pooled SQLAlchemy engine
other assertions in this module use) so the pragma cannot bleed into any
other connection. Production code (`infrastructure/database.py`'s
`create_engine_for`) never sets this pragma; the singleton-owner constraint
(spec §4.2) is a deliberate product rule that this module alone needs to
defeat, purely to prove isolation *would* hold if a second owner existed.
"""

from __future__ import annotations

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from yuno.modules.audit.domain import AuditEvent
from yuno.modules.audit.models import AuditEventRow
from yuno.modules.identity.domain import Owner, Role
from yuno.modules.identity.service import ensure_local_owner
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.errors import ConflictError
from yuno.shared.domain.ids import new_id
from yuno.shared.infrastructure.repository import owner_scoped_select

_SECOND_OWNER_KIND = "test_secondary_owner"


def _insert_second_owner(database_url: str, *, owner_id: str, display_name: str) -> None:
    """Insert a second `owners` row directly via raw SQL -- see module
    docstring for why `PRAGMA ignore_check_constraints=ON` is required and
    why it's safe (a dedicated, immediately-closed raw connection).
    """
    prefix = "sqlite+pysqlite:///"
    assert database_url.startswith(prefix), f"unexpected database URL scheme: {database_url!r}"
    path = database_url.removeprefix(prefix)

    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute(
            "INSERT INTO owners (id, kind, display_name, status, created_at) "
            "VALUES (?, ?, ?, 'active', ?)",
            (owner_id, _SECOND_OWNER_KIND, display_name, now_text(SystemClock())),
        )
        connection.commit()
    finally:
        connection.close()


# --- Behavioural isolation: repository calls scoped to B never see A's rows ---


def test_audit_events_under_owner_a_are_absent_from_owner_b_listing(
    uow_factory: UnitOfWorkFactory, database_url: str
) -> None:
    with uow_factory() as uow:
        owner_a = uow.owners.create_local_owner("Owner A")
        uow.commit()

    owner_b_id = new_id()
    _insert_second_owner(database_url, owner_id=owner_b_id, display_name="Owner B")

    with uow_factory() as uow:
        uow.audit.append(
            AuditEvent(
                id=new_id(),
                owner_id=owner_a.id,
                goal_id=None,
                actor_role=Role.LEARNER.value,
                entity_type="probe",
                entity_id="probe-1",
                action="probe_action",
                before_hash=None,
                after_hash=None,
                reason=None,
                request_id=None,
                correlation_id=None,
                occurred_at=now_text(SystemClock()),
            )
        )
        uow.commit()

    with uow_factory() as uow:
        owner_a_events = uow.audit.list_for_owner(owner_a.id)
        owner_b_events = uow.audit.list_for_owner(owner_b_id)

    assert len(owner_a_events) == 1
    assert owner_a_events[0].owner_id == owner_a.id
    assert owner_b_events == []


def test_role_grants_under_owner_a_are_absent_from_owner_b_grants(
    uow_factory: UnitOfWorkFactory, database_url: str
) -> None:
    with uow_factory() as uow:
        owner_a = uow.owners.create_local_owner("Owner A")
        uow.owners.grant_role(owner_a.id, Role.LEARNER, assigned_by_owner_id=owner_a.id)
        uow.commit()

    owner_b_id = new_id()
    _insert_second_owner(database_url, owner_id=owner_b_id, display_name="Owner B")

    with uow_factory() as uow:
        owner_a_grants = uow.owners.grants(owner_a.id)
        owner_b_grants = uow.owners.grants(owner_b_id)

    assert owner_a_grants == frozenset({Role.LEARNER})
    assert owner_b_grants == frozenset()


# --- owner_scoped_select: proof by execution, not by reading source text ---

# A substring match on source text (asserting
# `"owner_scoped_select" in inspect.getsource(method)`) cannot verify
# dataflow: it doesn't know whether a returned query is actually the one
# that gets executed, is built once and thrown away, or ever had a `WHERE`
# clause at all. Coverage instead comes from two places: the behavioural
# cross-owner tests above, which prove the *callers* (`grants`,
# `list_for_owner`) return owner-scoped data end to end; and the test
# below, which proves the *helper* they both call compiles an owner_id
# filter, by compiling real SQL rather than reading source text. Any future
# owner-scoped method should come with its own behavioural isolation test
# in this style, not a generic source-text sweep.


def test_owner_scoped_select_compiles_a_where_clause_filtering_by_owner_id() -> None:
    stmt = owner_scoped_select(AuditEventRow, "owner-under-test")
    compiled_sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "owner_id" in compiled_sql
    assert "owner-under-test" in compiled_sql


# --- Database-level guard: FK enforcement backs the repository-level scoping ---


def test_foreign_keys_pragma_is_on_for_every_connection(engine: Engine) -> None:
    for _ in range(3):
        with engine.connect() as connection:
            assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_owner_owned_row_referencing_nonexistent_owner_is_rejected(engine: Engine) -> None:
    """Raw SQL, bypassing the repository entirely: even if application code
    were bypassed or buggy, SQLite itself refuses an `audit_events` row
    whose `owner_id` does not reference a real `owners.id`.
    """
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO audit_events "
                "(id, owner_id, actor_role, entity_type, entity_id, action, occurred_at) "
                "VALUES (:id, :owner_id, 'learner', 'probe', 'probe-1', 'probe_action', :occurred_at)"
            ),
            {
                "id": new_id(),
                "owner_id": "owner-does-not-exist",
                "occurred_at": now_text(SystemClock()),
            },
        )


# --- Regression tests ---


def _probe_event(
    *, owner_id: str, event_id: str | None = None, reason: str | None = None
) -> AuditEvent:
    return AuditEvent(
        id=event_id or new_id(),
        owner_id=owner_id,
        goal_id=None,
        actor_role=Role.LEARNER.value,
        entity_type="probe",
        entity_id="probe-1",
        action="probe_action",
        before_hash=None,
        after_hash=None,
        reason=reason,
        request_id=None,
        correlation_id=None,
        occurred_at=now_text(SystemClock()),
    )


# A public `.session` attribute would let any caller holding a
# `UnitOfWork` reach straight through a repository and read/write the
# session directly, bypassing every owner-scoped method -- e.g.
# `uow.audit.session.get(AuditEventRow, <owner A's event id>)` would return
# owner A's full row from inside owner B's UoW.


def test_repository_session_is_private_not_a_public_attribute(
    uow_factory: UnitOfWorkFactory,
) -> None:
    with uow_factory() as uow:
        assert not hasattr(uow.owners, "session")
        assert not hasattr(uow.audit, "session")
        # `_session` existing is an internal implementation detail, not an
        # invitation to use it -- see `repositories/__init__.py`'s docstring.
        assert hasattr(uow.owners, "_session")
        assert hasattr(uow.audit, "_session")


def test_repository_slots_reject_reintroducing_a_public_session_attribute(
    uow_factory: UnitOfWorkFactory,
) -> None:
    """`__slots__` on `SqlAlchemyRepository` and both concrete repositories
    turns resurrecting a public `.session` (or any other undeclared
    attribute) into an immediate `AttributeError` instead of a silent
    success.
    """
    with uow_factory() as uow:
        # The assigned value is irrelevant -- only the attribute name is
        # under test, so a dummy value keeps this from being (another)
        # external read of `_session`.
        with pytest.raises(AttributeError):
            uow.audit.session = "irrelevant"
        with pytest.raises(AttributeError):
            uow.owners.session = "irrelevant"


def test_owner_b_cannot_reach_owner_a_audit_row_via_session_escape_hatch(
    uow_factory: UnitOfWorkFactory, database_url: str
) -> None:
    """Reaching for `.session` to read another owner's row directly --
    bypassing `list_for_owner`/`owner_scoped_select` entirely -- must fail
    with `AttributeError` before it ever touches the database.
    """
    with uow_factory() as uow:
        owner_a = uow.owners.create_local_owner("Owner A")
        uow.commit()

    secret_event = _probe_event(owner_id=owner_a.id, reason="top-secret-reason")
    with uow_factory() as uow:
        uow.audit.append(secret_event)
        uow.commit()

    owner_b_id = new_id()
    _insert_second_owner(database_url, owner_id=owner_b_id, display_name="Owner B")

    # Owner B's own UoW/repositories -- `.session` bypasses owner-scoped
    # methods (and therefore owner_id) entirely, regardless of which
    # owner's UoW it's reached from.
    with uow_factory() as uow, pytest.raises(AttributeError):
        uow.audit.session.get(AuditEventRow, secret_event.id)


# `ensure_local_owner` must not be check-then-act with no retry: a race
# between concurrent callers must not let a raw `sqlalchemy.exc.
# IntegrityError` escape the framework-free `yuno.application` layer
# (spec §3.2).


def test_ensure_local_owner_is_concurrency_safe_under_a_real_race(
    uow_factory: UnitOfWorkFactory,
) -> None:
    """Real threads against the real migrated SQLite database this
    module's fixtures already provide -- no mocking. Every thread opens
    its own fresh UoW (matching every real call site: server startup in
    `api/app.py`, `test_api_contract.py`'s `probe_client` fixture) and
    calls `ensure_local_owner` concurrently; all threads must converge on
    one owner with no uncaught `IntegrityError`.
    """
    thread_count = 8
    barrier = threading.Barrier(thread_count)

    def _race() -> Owner:
        barrier.wait(timeout=5)
        with uow_factory() as uow:
            owner = ensure_local_owner(uow, "Race Owner")
            uow.commit()
        return owner

    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        futures = [executor.submit(_race) for _ in range(thread_count)]
        owners = [future.result(timeout=10) for future in futures]

    owner_ids = {owner.id for owner in owners}
    assert len(owner_ids) == 1, f"expected exactly one owner, got {owner_ids!r}"

    with uow_factory() as uow:
        grants = uow.owners.grants(owner_ids.pop())
    assert grants == frozenset({Role.LEARNER, Role.DESIGNATED_EDITORIAL_APPROVER})


# `audit_events.id` is the table's real PRIMARY KEY, not owner-scoped, so a
# same-id collision from a *different* owner must fail exactly like a
# same-owner collision -- see `audit.py`'s `append` docstring.


def test_audit_append_rejects_id_collision_even_across_different_owners(
    uow_factory: UnitOfWorkFactory, database_url: str
) -> None:
    """The conflict is real (SQLite cannot honour two distinct rows sharing
    one primary key regardless of `owner_id`), but no data crosses -- owner
    B's attempt is rejected outright, and owner A's original row is
    untouched and remains invisible to B.
    """
    with uow_factory() as uow:
        owner_a = uow.owners.create_local_owner("Owner A")
        uow.commit()

    owner_b_id = new_id()
    _insert_second_owner(database_url, owner_id=owner_b_id, display_name="Owner B")

    shared_id = new_id()
    with uow_factory() as uow:
        uow.audit.append(
            _probe_event(owner_id=owner_a.id, event_id=shared_id, reason="owner a's event")
        )
        uow.commit()

    with uow_factory() as uow, pytest.raises(ConflictError):
        uow.audit.append(
            _probe_event(owner_id=owner_b_id, event_id=shared_id, reason="owner b's event")
        )

    with uow_factory() as uow:
        owner_a_events = uow.audit.list_for_owner(owner_a.id)
        owner_b_events = uow.audit.list_for_owner(owner_b_id)
    assert len(owner_a_events) == 1
    assert owner_a_events[0].reason == "owner a's event"
    assert owner_b_events == []


# `UnitOfWork.__exit__`'s `session.rollback()` must be guarded: an
# unguarded rollback failure would replace whatever exception was already
# propagating -- e.g. a route's `NotFoundError` (a typed 404) surfacing as
# a generic `500 internal_error` instead.


def test_original_exception_survives_a_failing_rollback(
    uow_factory: UnitOfWorkFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _RouteError(RuntimeError):
        """Stands in for a typed domain error (e.g. `NotFoundError`) that
        a route raises inside its UoW's `with` block.
        """

    closed: list[Session] = []
    original_close = Session.close

    def _boom_rollback(self: Session) -> None:
        raise RuntimeError("rollback exploded")

    def _spy_close(self: Session, *args: object, **kwargs: object) -> None:
        closed.append(self)
        original_close(self, *args, **kwargs)

    monkeypatch.setattr(Session, "rollback", _boom_rollback)
    monkeypatch.setattr(Session, "close", _spy_close)

    with pytest.raises(_RouteError) as excinfo, uow_factory() as uow:
        uow.owners.create_local_owner("Doomed")
        raise _RouteError("original failure")

    # The original exception -- type and message -- must win.
    assert str(excinfo.value) == "original failure"
    # The rollback failure must not vanish silently either.
    notes = "\n".join(getattr(excinfo.value, "__notes__", None) or [])
    assert "rollback exploded" in notes
    # And the session must still have been closed despite the failure.
    assert len(closed) == 1


def test_uncommitted_uow_exit_rolls_back_and_does_not_persist(
    uow_factory: UnitOfWorkFactory,
) -> None:
    """The headline spec §3.4 promise (also documented on
    `api/dependencies.py`'s `get_unit_of_work`): exiting a UoW without
    `.commit()` must roll back rather than persist.
    """
    with uow_factory() as uow:
        uow.owners.create_local_owner("Never Committed")
        # No uow.commit() -- exit the block as-is.

    with uow_factory() as uow:
        assert uow.owners.get_local_owner() is None


def test_ensure_local_owner_grants_both_roles_exactly_once(
    uow_factory: UnitOfWorkFactory,
) -> None:
    with uow_factory() as uow:
        owner = ensure_local_owner(uow, "Grants Owner")
        uow.commit()

    with uow_factory() as uow:
        grants = uow.owners.grants(owner.id)
    assert grants == frozenset({Role.LEARNER, Role.DESIGNATED_EDITORIAL_APPROVER})

    # A second call is a true no-op: same owner, no duplicate grants. (A
    # regression here would raise `IntegrityError` on the second insert
    # attempt -- `owner_role_grants`'s primary key is `(owner_id, role)` --
    # rather than silently duplicating anything.)
    with uow_factory() as uow:
        second_call_owner = ensure_local_owner(uow, "Grants Owner")
        uow.commit()
    assert second_call_owner == owner

    with uow_factory() as uow:
        grants_after_second_call = uow.owners.grants(owner.id)
    assert grants_after_second_call == frozenset(
        {Role.LEARNER, Role.DESIGNATED_EDITORIAL_APPROVER}
    )
