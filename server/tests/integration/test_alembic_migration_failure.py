"""Integration tests for IDK-501's failure/gate requirements: a
deliberately failing migration stops startup with a recoverable
diagnostic naming the failed revision and leaves no partially upgraded
readable service; the server and the offline publish tool both refuse a
non-head database, below head and above head; and an approved canonical
graph version cannot be data-migrated in place -- only publishing a new
version succeeds.

`test_alembic_head_guard.py` already covers `require_single_head` against
hand-crafted database states (corrupt file, missing parent directory,
never migrated, stamped at an unknown revision) and `create_app`'s
lifespan driving that guard against those states. This file adds what
that suite does not:

- A *real* Alembic upgrade that fails partway through a real chain, built
  by copying the installed `migrations/` tree into `tmp_path` and
  appending one deliberately-broken revision -- `command.upgrade`/
  `command.downgrade` are only ever run against these throwaway scratch
  copies, never against the real installed package's own
  `migrations/versions/`.
- The offline publisher's own head gate
  (`yuno.modules.canonical.publisher.publish_canonical_graph`), which had
  zero dedicated coverage anywhere before this file.
- A migration-shaped attempt to mutate a published canonical graph
  version's rows, as opposed to `test_canonical_immutability.py`'s
  raw-SQL `UPDATE`/`DELETE` coverage of the same triggers -- proving the
  trigger blocks a migration's `op.execute`, not just an application
  query.
"""

from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

import yuno
from tests.fixtures.canonical import CanonicalFixture, load_fixture
from yuno.api.app import create_app
from yuno.config import Settings
from yuno.modules.canonical.domain import CanonicalGraphVersion
from yuno.modules.canonical.publisher import publish_canonical_graph
from yuno.modules.identity.domain import Role
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.errors import MigrationUnavailableError
from yuno.shared.infrastructure import alembic_guard
from yuno.shared.infrastructure.database import (
    create_engine_for,
    create_session_factory,
)
from yuno.unit_of_work import create_unit_of_work_factory

_REAL_MIGRATIONS_DIR = Path(yuno.__file__).parent / "migrations"


# ---------------------------------------------------------------------------
# Shared scratch-migration-tree plumbing.
# ---------------------------------------------------------------------------


def _real_head_and_last_good_revision() -> tuple[str, str]:
    """The installed package's single head, and the revision directly
    beneath it -- read via `alembic_guard.build_alembic_config()`
    (the same real, unmodified `migrations/` directory `require_single_head`
    and the publisher's `require_single_head` call always resolve), never
    hand-typed, so this stays correct as revisions are added.
    """
    script = ScriptDirectory.from_config(alembic_guard.build_alembic_config())
    (head,) = script.get_heads()
    down_revision = script.get_revision(head).down_revision
    assert isinstance(down_revision, str)
    return head, down_revision


def _ordered_real_revisions() -> list[str]:
    """Every real revision id, base-to-head, by walking `down_revision`
    links backward from the single head. The installed chain is linear
    (one head, no branch points), so this is a total order.
    """
    script = ScriptDirectory.from_config(alembic_guard.build_alembic_config())
    (head,) = script.get_heads()
    order = [head]
    current = script.get_revision(head)
    while current.down_revision is not None:
        down_revision = current.down_revision
        assert isinstance(down_revision, str)
        current = script.get_revision(down_revision)
        order.append(current.revision)
    order.reverse()
    return order


def _copy_real_migrations(destination: Path) -> Path:
    """Copy the installed package's `migrations/` tree (env.py,
    script.py.mako, versions/) into `destination`, a throwaway scratch
    `script_location` a test can freely mutate without touching the real
    package on disk.
    """
    shutil.copytree(_REAL_MIGRATIONS_DIR, destination)
    return destination


def _scratch_config(script_location: Path, database_url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(script_location))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _rewire_down_revision(versions_dir: Path, revision: str, *, old: str, new: str) -> Path:
    """Rewrite `revision`'s own file in `versions_dir` so its `down_revision`
    reads `new` instead of `old` -- Alembic revision files are plain
    Python modules scanned by filename-independent content, so this is a
    straightforward text substitution on the one line declaring
    `down_revision`.
    """
    (file_path,) = versions_dir.glob(f"{revision}_*.py")
    original = file_path.read_text()
    updated = original.replace(old, new, 1)
    assert updated != original, f"expected {old!r} to appear in {file_path.name}"
    file_path.write_text(updated)
    return file_path


def _write_broken_revision(versions_dir: Path, *, revision: str, down_revision: str) -> None:
    """Write a scratch revision whose `upgrade()` unconditionally raises,
    simulating a migration that never completes. Never present in the
    real installed `migrations/` directory `build_alembic_config()`
    resolves -- only ever written into a `tmp_path` scratch copy.
    """
    content = f'''"""Deliberately broken scratch revision injected by
tests/integration/test_alembic_migration_failure.py to simulate IDK-501's
"a failed migration stops startup" scenario.
"""
from __future__ import annotations

revision: str = {revision!r}
down_revision: str | None = {down_revision!r}
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    raise RuntimeError(
        "deliberately broken migration {revision}: simulated failure for "
        "IDK-501's recoverable-migration-failure test"
    )


def downgrade() -> None:
    raise NotImplementedError("scratch test revision: forward-only")
'''
    (versions_dir / f"{revision}_deliberately_broken.py").write_text(content)


def _write_sql_revision(versions_dir: Path, *, revision: str, down_revision: str, sql: str) -> None:
    """Write a scratch revision whose `upgrade()` runs exactly one raw
    `sql` statement via `op.execute`, appended after the real head -- used
    by the canonical-immutability-under-migration tests below (see their
    own docstrings for why).
    """
    content = f'''"""Scratch revision injected by
tests/integration/test_alembic_migration_failure.py: attempts an
in-place UPDATE on a row an approved canonical graph version's
immutability triggers (87af9746aec1_canonical_graph.py) protect.
"""
from __future__ import annotations

from alembic import op

revision: str = {revision!r}
down_revision: str | None = {down_revision!r}
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute({sql!r})


def downgrade() -> None:
    raise NotImplementedError("scratch test revision: forward-only")
'''
    (versions_dir / f"{revision}_scratch_tamper.py").write_text(content)


def _row_snapshot(engine: Engine, *, table: str, id_column: str, row_id: str) -> dict[str, object]:
    """Every column of the one row identified by `id_column = row_id`, as
    a plain dict -- compared before/after a rejected mutation attempt so
    "unchanged" means byte-identical, not just "still present".
    """
    with engine.connect() as connection:
        row = (
            connection.execute(
                text(f"SELECT * FROM {table} WHERE {id_column} = :row_id"),
                {"row_id": row_id},
            )
            .mappings()
            .one()
        )
    return dict(row)


# ---------------------------------------------------------------------------
# (a) A deliberately failing migration stops startup with a recoverable
# diagnostic naming the failed revision, and leaves no partially upgraded
# readable service.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _BrokenChain:
    """A scratch copy of the real migration chain with one extra revision
    inserted directly beneath the real head, whose `upgrade()`
    unconditionally raises. Rewiring the copied head file's
    `down_revision` (rather than simply appending the broken revision
    after the real head) is what makes the resulting "database behind
    head" state legible to the REAL, unmodified `migrations/` directory
    too: the real head file on disk is untouched, so
    `alembic_guard.require_single_head` (which always resolves the real
    package, never this scratch copy) still sees exactly one missing
    step -- `last_good_revision` -> `real_head` -- and can name
    `real_head` as the specific unapplied revision without knowing
    anything about this scratch chain's fictional broken revision.
    """

    database_url: str
    config: Config
    versions_dir: Path
    broken_revision: str
    real_head: str
    last_good_revision: str


def _build_broken_chain(tmp_path: Path) -> _BrokenChain:
    real_head, last_good_revision = _real_head_and_last_good_revision()

    scratch_location = _copy_real_migrations(tmp_path / "scratch-migrations")
    versions_dir = scratch_location / "versions"

    broken_revision = f"br{uuid.uuid4().hex[:10]}"
    _rewire_down_revision(versions_dir, real_head, old=last_good_revision, new=broken_revision)
    _write_broken_revision(versions_dir, revision=broken_revision, down_revision=last_good_revision)

    database_url = f"sqlite+pysqlite:///{tmp_path / 'failing-migration.db'}"
    config = _scratch_config(scratch_location, database_url)

    return _BrokenChain(
        database_url=database_url,
        config=config,
        versions_dir=versions_dir,
        broken_revision=broken_revision,
        real_head=real_head,
        last_good_revision=last_good_revision,
    )


def test_deliberately_failing_migration_raises_and_leaves_database_at_last_good_revision(
    tmp_path: Path,
) -> None:
    """`command.upgrade(config, "head")` must raise, and the database's
    `alembic_version` must still hold `last_good_revision` -- the
    revision immediately before the broken one, which committed and was
    stamped before the broken revision ever ran. The broken revision
    itself must never be stamped: an upgrade that fails partway through
    must not claim to have reached a revision it never finished.
    """
    chain = _build_broken_chain(tmp_path)

    with pytest.raises(RuntimeError, match=chain.broken_revision):
        command.upgrade(chain.config, "head")

    engine = create_engine_for(chain.database_url)
    try:
        with engine.connect() as connection:
            stamped = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert stamped == chain.last_good_revision
        assert stamped != chain.broken_revision
    finally:
        engine.dispose()


def test_require_single_head_against_real_scripts_names_the_unapplied_revision_after_failed_migration(
    tmp_path: Path,
) -> None:
    """After the failed upgrade above, the database is stamped one
    revision short of the REAL head -- not the scratch chain's fictional
    broken revision, but `real_head` itself, since the real head file's
    own `down_revision` was never touched on disk. Calling
    `alembic_guard.require_single_head` (which always resolves the real,
    unmodified `migrations/` directory, never this test's scratch copy)
    must therefore name `real_head` as the specific unapplied revision,
    not just say "behind head" -- an operator reading the diagnostic
    needs to know exactly which revision to inspect.
    """
    chain = _build_broken_chain(tmp_path)
    with pytest.raises(RuntimeError):
        command.upgrade(chain.config, "head")

    engine = create_engine_for(chain.database_url)
    try:
        with pytest.raises(MigrationUnavailableError) as excinfo:
            alembic_guard.require_single_head(engine)

        assert excinfo.value.retryable is False
        assert excinfo.value.recovery_action
        assert chain.real_head in excinfo.value.message
        assert chain.real_head in excinfo.value.recovery_action
    finally:
        engine.dispose()


def test_create_app_lifespan_refuses_to_start_after_failed_migration(tmp_path: Path) -> None:
    """Driven through `TestClient`/lifespan startup, as
    `test_alembic_head_guard.py`'s equivalent tests are -- proving the
    *server* refuses to expose a partially upgraded database, not just
    that `require_single_head` would object if asked.
    """
    chain = _build_broken_chain(tmp_path)
    with pytest.raises(RuntimeError):
        command.upgrade(chain.config, "head")

    settings = Settings(database_url=chain.database_url)
    app = create_app(settings)

    with pytest.raises(MigrationUnavailableError), TestClient(app):
        pass


def test_fixed_rerun_resumes_to_head_without_duplicating_work(tmp_path: Path) -> None:
    """Once the broken revision is removed and the real head's own
    `down_revision` restored, `command.upgrade(config, "head")` against
    the SAME already-partially-migrated database must succeed and reach
    the real head. If this re-applied `last_good_revision`'s own DDL
    instead of resuming from where it left off, it would fail with
    "table ... already exists" -- succeeding here proves the resumed run
    only applies what is actually still pending.
    """
    chain = _build_broken_chain(tmp_path)
    with pytest.raises(RuntimeError):
        command.upgrade(chain.config, "head")

    (broken_file,) = chain.versions_dir.glob(f"{chain.broken_revision}_*.py")
    broken_file.unlink()
    _rewire_down_revision(
        chain.versions_dir, chain.real_head, old=chain.broken_revision, new=chain.last_good_revision
    )

    command.upgrade(chain.config, "head")

    engine = create_engine_for(chain.database_url)
    try:
        assert alembic_guard.require_single_head(engine) == chain.real_head
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# (b) Both the server AND the offline publish tool refuse a non-head
# database, below head and above head.
# ---------------------------------------------------------------------------


def _mid_chain_below_head_database_url(tmp_path: Path) -> str:
    """A fresh database migrated only to the revision at the midpoint of
    the real chain -- genuinely "below head", and clearly distinct from
    part (a)'s "one revision short" scenario.
    """
    order = _ordered_real_revisions()
    mid_revision = order[len(order) // 2]

    database_url = f"sqlite+pysqlite:///{tmp_path / 'below-head.db'}"
    config = alembic_guard.build_alembic_config()
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, mid_revision)
    return database_url


def _stamped_above_head_database_url(migrated_database_url: str) -> str:
    """`migrated_database_url`, fully at the real head, then hand-stamped
    at a revision id absent from the installed migration scripts --
    simulating a newer codebase having migrated this database further
    than the current build knows about. `require_single_head` diagnoses
    this via the same "unknown revision" branch a deleted-migration
    database would hit; nothing distinguishes "ahead" from "unknown" at
    the database level, since neither this build's scripts nor
    `alembic_version` alone can tell them apart.
    """
    engine = create_engine_for(migrated_database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE alembic_version SET version_num = :revision"),
                {"revision": "future0000001"},
            )
    finally:
        engine.dispose()
    return migrated_database_url


def _grant_editorial_approver(database_url: str) -> tuple[str, UnitOfWorkFactory, Engine]:
    """A local owner holding `designated_editorial_approver`, granted the
    same way `test_canonical_publish.py`'s `approver_owner_id` fixture
    does -- so a below/above-head publish test that still raises proves
    the head gate fired first, not that the call failed on an unrelated
    missing grant.
    """
    engine = create_engine_for(database_url)
    session_factory = create_session_factory(engine)
    uow_factory = create_unit_of_work_factory(session_factory)
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Fixture Approver")
        uow.owners.grant_role(
            owner.id, Role.DESIGNATED_EDITORIAL_APPROVER, assigned_by_owner_id=owner.id
        )
        uow.commit()
    return owner.id, uow_factory, engine


def test_create_app_lifespan_refuses_below_head_mid_chain_database(tmp_path: Path) -> None:
    database_url = _mid_chain_below_head_database_url(tmp_path)
    settings = Settings(database_url=database_url)
    app = create_app(settings)

    with pytest.raises(MigrationUnavailableError), TestClient(app):
        pass


def test_create_app_lifespan_refuses_above_head_unknown_revision_database(
    migrated_database_url: str,
) -> None:
    database_url = _stamped_above_head_database_url(migrated_database_url)
    settings = Settings(database_url=database_url)
    app = create_app(settings)

    with pytest.raises(MigrationUnavailableError), TestClient(app):
        pass


def test_publish_canonical_graph_refuses_below_head_before_authorization_or_write_work(
    tmp_path: Path,
) -> None:
    """`publish_canonical_graph` calls `require_single_head(engine)` as its
    very first line, before `validate_manifest`, the
    `designated_editorial_approver` grant check, or any row insert. The
    acting owner here already holds that grant (see
    `_grant_editorial_approver`), so a `MigrationUnavailableError` --
    not a `RoleNotGrantedError` or a successful publish -- proves the
    head gate is what actually fired.
    """
    database_url = _mid_chain_below_head_database_url(tmp_path)
    owner_id, uow_factory, engine = _grant_editorial_approver(database_url)
    try:
        fixture = load_fixture("v1_approved")
        assert fixture.approval is not None

        with pytest.raises(MigrationUnavailableError):
            publish_canonical_graph(
                engine=engine,
                uow_factory=uow_factory,
                manifest=fixture.manifest,
                actor_owner_id=owner_id,
                basis_ref=fixture.approval.basis_ref,
                topic_identity_slugs=fixture.topic_identity_slugs,
            )
    finally:
        engine.dispose()


def test_publish_canonical_graph_refuses_above_head_before_authorization_or_write_work(
    migrated_database_url: str,
) -> None:
    database_url = _stamped_above_head_database_url(migrated_database_url)
    owner_id, uow_factory, engine = _grant_editorial_approver(database_url)
    try:
        fixture = load_fixture("v1_approved")
        assert fixture.approval is not None

        with pytest.raises(MigrationUnavailableError):
            publish_canonical_graph(
                engine=engine,
                uow_factory=uow_factory,
                manifest=fixture.manifest,
                actor_owner_id=owner_id,
                basis_ref=fixture.approval.basis_ref,
                topic_identity_slugs=fixture.topic_identity_slugs,
            )
    finally:
        engine.dispose()


def test_below_and_above_head_publisher_diagnostics_are_distinguishable(
    tmp_path: Path, migrated_database_url: str
) -> None:
    """Both directions raise the same `MigrationUnavailableError` type
    and are both non-retryable, but an operator (or a log line) must be
    able to tell "behind head" apart from "ahead of / unknown to this
    build" from the `recovery_action` alone -- mirroring
    `test_alembic_head_guard.py`'s
    `test_unmigrated_and_unknown_revision_recovery_actions_are_distinguishable`,
    here through the publisher's own call site rather than
    `require_single_head` directly.
    """
    below_database_url = _mid_chain_below_head_database_url(tmp_path)
    below_owner_id, below_uow_factory, below_engine = _grant_editorial_approver(below_database_url)

    above_database_url = _stamped_above_head_database_url(migrated_database_url)
    above_owner_id, above_uow_factory, above_engine = _grant_editorial_approver(above_database_url)

    try:
        fixture = load_fixture("v1_approved")
        assert fixture.approval is not None

        with pytest.raises(MigrationUnavailableError) as below_excinfo:
            publish_canonical_graph(
                engine=below_engine,
                uow_factory=below_uow_factory,
                manifest=fixture.manifest,
                actor_owner_id=below_owner_id,
                basis_ref=fixture.approval.basis_ref,
                topic_identity_slugs=fixture.topic_identity_slugs,
            )
        with pytest.raises(MigrationUnavailableError) as above_excinfo:
            publish_canonical_graph(
                engine=above_engine,
                uow_factory=above_uow_factory,
                manifest=fixture.manifest,
                actor_owner_id=above_owner_id,
                basis_ref=fixture.approval.basis_ref,
                topic_identity_slugs=fixture.topic_identity_slugs,
            )

        assert below_excinfo.value.retryable is False
        assert above_excinfo.value.retryable is False
        assert below_excinfo.value.recovery_action != above_excinfo.value.recovery_action
    finally:
        below_engine.dispose()
        above_engine.dispose()


# ---------------------------------------------------------------------------
# (c) An approved canonical version cannot be data-migrated in place; only
# publishing a new version succeeds (Appendix H decision D1).
# ---------------------------------------------------------------------------


def _publish_v1_approved(
    engine: Engine, uow_factory: UnitOfWorkFactory
) -> tuple[str, CanonicalGraphVersion, CanonicalFixture]:
    """Grant the acting owner `designated_editorial_approver` and publish
    `v1_approved` through the real publisher, returning
    `(owner_id, version, fixture)` -- callers need `version.id` and
    `fixture.manifest.content_revisions` for byte-identical comparisons
    after a rejected in-place mutation attempt.
    """
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Fixture Approver")
        uow.owners.grant_role(
            owner.id, Role.DESIGNATED_EDITORIAL_APPROVER, assigned_by_owner_id=owner.id
        )
        uow.commit()

    fixture = load_fixture("v1_approved")
    assert fixture.approval is not None
    version = publish_canonical_graph(
        engine=engine,
        uow_factory=uow_factory,
        manifest=fixture.manifest,
        actor_owner_id=owner.id,
        basis_ref=fixture.approval.basis_ref,
        topic_identity_slugs=fixture.topic_identity_slugs,
    )
    return owner.id, version, fixture


def test_migration_cannot_update_published_canonical_graph_version_row(
    engine: Engine, uow_factory: UnitOfWorkFactory, migrated_database_url: str, tmp_path: Path
) -> None:
    """`test_canonical_immutability.py` already proves a raw application
    `UPDATE` against a published `canonical_graph_versions` row is
    rejected. This proves the same trigger blocks a *migration's*
    `op.execute` identically -- IDK-501's "an approved canonical version
    cannot be data-migrated in place" is about Alembic revisions
    specifically, not just the application's own repository layer.
    """
    _, version, _ = _publish_v1_approved(engine, uow_factory)
    before = _row_snapshot(engine, table="canonical_graph_versions", id_column="id", row_id=version.id)

    real_head, _ = _real_head_and_last_good_revision()
    scratch_location = _copy_real_migrations(tmp_path / "scratch-tamper-version")
    tamper_revision = f"tp{uuid.uuid4().hex[:10]}"
    _write_sql_revision(
        scratch_location / "versions",
        revision=tamper_revision,
        down_revision=real_head,
        sql="UPDATE canonical_graph_versions SET version_label = 'tampered-by-migration' "
        "WHERE status = 'published'",
    )
    scratch_config = _scratch_config(scratch_location, migrated_database_url)

    with pytest.raises(IntegrityError, match="UPDATE is not permitted"):
        command.upgrade(scratch_config, "head")

    after = _row_snapshot(engine, table="canonical_graph_versions", id_column="id", row_id=version.id)
    assert after == before


def test_migration_cannot_update_published_content_revision_row(
    engine: Engine, uow_factory: UnitOfWorkFactory, migrated_database_url: str, tmp_path: Path
) -> None:
    """The same trigger family also guards `content_revisions` rows
    belonging to a published version (`test_canonical_immutability.py`
    covers `topics`/`editorial_approvals`/`canonical_graph_versions`, not
    this table) -- and again, here via a migration's `op.execute`, not a
    raw application query.
    """
    _, _version, fixture = _publish_v1_approved(engine, uow_factory)
    content_revision_id = fixture.manifest.content_revisions[0].id
    before = _row_snapshot(
        engine, table="content_revisions", id_column="id", row_id=content_revision_id
    )

    real_head, _ = _real_head_and_last_good_revision()
    scratch_location = _copy_real_migrations(tmp_path / "scratch-tamper-content")
    tamper_revision = f"tp{uuid.uuid4().hex[:10]}"
    _write_sql_revision(
        scratch_location / "versions",
        revision=tamper_revision,
        down_revision=real_head,
        sql="UPDATE content_revisions SET markdown_ref = 'tampered-by-migration' "
        "WHERE status = 'published'",
    )
    scratch_config = _scratch_config(scratch_location, migrated_database_url)

    with pytest.raises(IntegrityError, match="UPDATE is not permitted"):
        command.upgrade(scratch_config, "head")

    after = _row_snapshot(
        engine, table="content_revisions", id_column="id", row_id=content_revision_id
    )
    assert after == before


def test_publishing_new_version_succeeds_and_leaves_v1_untouched(
    engine: Engine, uow_factory: UnitOfWorkFactory
) -> None:
    """The approved correction path: publishing `v2_approved` as a brand
    new version succeeds -- v1's row is byte-identical before and after,
    proving the only way to "correct" a published version is a new one,
    never an edit of the old one in place.
    """
    owner_id, v1_version, _ = _publish_v1_approved(engine, uow_factory)
    v1_snapshot = _row_snapshot(
        engine, table="canonical_graph_versions", id_column="id", row_id=v1_version.id
    )

    v2_fixture = load_fixture("v2_approved")
    assert v2_fixture.approval is not None

    v2_version = publish_canonical_graph(
        engine=engine,
        uow_factory=uow_factory,
        manifest=v2_fixture.manifest,
        actor_owner_id=owner_id,
        basis_ref=v2_fixture.approval.basis_ref,
        topic_identity_slugs=v2_fixture.topic_identity_slugs,
    )

    assert v2_version.id != v1_version.id
    assert v2_version.supersedes_version_id == v1_version.id
    assert (
        _row_snapshot(engine, table="canonical_graph_versions", id_column="id", row_id=v1_version.id)
        == v1_snapshot
    )
