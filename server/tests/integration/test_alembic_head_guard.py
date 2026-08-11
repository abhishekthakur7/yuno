"""Integration tests for the Alembic single-head startup gate (spec §4.8):
server and offline tooling both refuse to start against a non-head Alembic
database.

Covers `infrastructure.alembic_guard.require_single_head` directly against
real SQLite databases (migrated / never-migrated / partially-applied /
stamped-at-an-unknown-revision / corrupt / unopenable), then drives failures
through `api.app.create_app`'s real ASGI lifespan via `TestClient` -- proving
the *server* refuses to start, not just that the guard function would say so
if someone called it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import Engine, inspect, text

from yuno.api.app import create_app
from yuno.config import Settings, get_settings
from yuno.shared.domain.errors import UnavailableError
from yuno.shared.infrastructure import alembic_guard
from yuno.shared.infrastructure.database import create_engine_for

_ALEMBIC_VERSION_TABLE_SQL = (
    "CREATE TABLE alembic_version ("
    "version_num VARCHAR(32) NOT NULL, "
    "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
)


def _stamp_revision(engine: Engine, revision: str = "deadbeefcafe") -> None:
    """Hand-craft an `alembic_version` table stamped at `revision`. The
    package has only one migration (`442e2f56adb9`, `down_revision=None`),
    so any other value is unknown to `ScriptDirectory`, exercising the
    "stamped, but unresolvable" branch a deleted or foreign migration would.
    """
    with engine.begin() as connection:
        connection.execute(text(_ALEMBIC_VERSION_TABLE_SQL))
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
            {"revision": revision},
        )


def test_command_upgrade_honors_explicit_config_url_over_cached_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A caller whose `get_settings()` is already cached to database A
    builds a `Config` via `alembic_guard.build_alembic_config()`, overrides
    its `sqlalchemy.url` to database B (Alembic's documented programmatic
    pattern for pointing a `command` at a specific database), and calls
    `command.upgrade(config, "head")`. Only B may receive the migration; A
    must be untouched -- `migrations/env.py` must read the URL off
    `context.config` rather than `get_settings().database_url` directly, or
    the override has no effect and A gets silently migrated instead.
    """
    url_a = f"sqlite+pysqlite:///{tmp_path / 'a.db'}"
    url_b = f"sqlite+pysqlite:///{tmp_path / 'b.db'}"

    monkeypatch.setenv("YUNO_DATABASE_URL", url_a)
    get_settings.cache_clear()
    try:
        assert get_settings().database_url == url_a

        config = alembic_guard.build_alembic_config()
        assert config.get_main_option("sqlalchemy.url") == url_a
        config.set_main_option("sqlalchemy.url", url_b)

        command.upgrade(config, "head")
    finally:
        get_settings.cache_clear()

    engine_a = create_engine_for(url_a)
    engine_b = create_engine_for(url_b)
    try:
        with engine_a.connect() as connection:
            assert inspect(connection).get_table_names() == []
        with engine_b.connect() as connection:
            assert "owners" in inspect(connection).get_table_names()

        # The downstream symptom the ticket reports: B is now genuinely
        # usable, A genuinely is not -- not corrupt, just never migrated.
        assert alembic_guard.require_single_head(engine_b)
        with pytest.raises(UnavailableError) as excinfo:
            alembic_guard.require_single_head(engine_a)
        # A was never migrated -- not corrupt, just uninitialised.
        assert "not initialised" in excinfo.value.message.lower()
    finally:
        engine_a.dispose()
        engine_b.dispose()


def test_require_single_head_raises_on_corrupt_database_file(tmp_path: Path) -> None:
    """A corrupt / non-SQLite file at the configured path must surface as a
    clean `UnavailableError`, not a raw
    `sqlalchemy.exc.DatabaseError: file is not a database`.
    """
    db_path = tmp_path / "corrupt.db"
    db_path.write_bytes(b"not a sqlite database -- just garbage bytes")

    engine = create_engine_for(f"sqlite+pysqlite:///{db_path}")
    try:
        with pytest.raises(UnavailableError) as excinfo:
            alembic_guard.require_single_head(engine)

        assert excinfo.value.http_status == 503
        assert excinfo.value.retryable is True
        assert "not a valid sqlite database" in excinfo.value.message.lower()
        assert "corrupt" in excinfo.value.recovery_action.lower()
        assert "restore it from backup" in excinfo.value.recovery_action.lower()
    finally:
        engine.dispose()


def test_require_single_head_raises_on_missing_parent_directory(tmp_path: Path) -> None:
    """A path whose parent directory does not exist must surface as a clean
    `UnavailableError`, not a raw
    `sqlalchemy.exc.OperationalError: unable to open database file`.
    """
    missing_path = tmp_path / "no-such-directory" / "nested" / "yuno.db"

    engine = create_engine_for(f"sqlite+pysqlite:///{missing_path}")
    try:
        with pytest.raises(UnavailableError) as excinfo:
            alembic_guard.require_single_head(engine)

        assert excinfo.value.http_status == 503
        assert excinfo.value.retryable is True
        assert "could not open the database" in excinfo.value.message.lower()
        assert "parent directory" in excinfo.value.recovery_action.lower()

        assert "corrupt" not in excinfo.value.recovery_action.lower()
    finally:
        engine.dispose()


def test_require_single_head_returns_head_revision_on_migrated_database(
    engine: Engine,
) -> None:
    script = ScriptDirectory.from_config(alembic_guard.build_alembic_config())
    expected_head = script.get_current_head()
    assert expected_head is not None

    assert alembic_guard.require_single_head(engine) == expected_head


def test_require_single_head_raises_on_unmigrated_database(database_url: str) -> None:
    """`database_url` alone (not `migrated_database_url`) is a genuinely
    empty database -- no `alembic_version` table, no other tables either.
    """
    engine = create_engine_for(database_url)
    try:
        with pytest.raises(UnavailableError) as excinfo:
            alembic_guard.require_single_head(engine)
        assert excinfo.value.http_status == 503
        assert excinfo.value.retryable is True
        assert excinfo.value.recovery_action
    finally:
        engine.dispose()


def test_require_single_head_raises_on_partially_applied_database(
    migrated_database_url: str,
) -> None:
    """An application schema with no recorded Alembic version -- plausible
    since this SQLite setup runs non-transactional DDL (Alembic logs "Will
    assume non-transactional DDL" here), so a process killed mid-migration
    can leave exactly this. Must be diagnosed distinctly from "never
    initialised": that advice's "run `alembic upgrade head`" fails here
    with "table owners already exists", since the tables are already there.
    """
    engine = create_engine_for(migrated_database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM alembic_version"))

        with pytest.raises(UnavailableError) as excinfo:
            alembic_guard.require_single_head(engine)

        assert excinfo.value.http_status == 503
        assert excinfo.value.retryable is True
        assert "owners" in excinfo.value.message
        assert "not initialised" not in excinfo.value.message.lower()
        assert "manual inspection" in excinfo.value.recovery_action.lower()
        assert "already exists" in excinfo.value.recovery_action.lower()
        assert excinfo.value.recovery_action != (
            "Run `uv run alembic upgrade head` against this database."
        )
    finally:
        engine.dispose()


def test_require_single_head_raises_on_unknown_revision_database(database_url: str) -> None:
    """A database stamped at a revision that does not exist in the
    installed migration scripts (deleted, or from a different codebase
    version) must be diagnosed distinctly from "behind head": that advice's
    "run `alembic upgrade head`" fails here with "Can't locate revision
    identified by 'deadbeefcafe'".
    """
    engine = create_engine_for(database_url)
    try:
        _stamp_revision(engine, "deadbeefcafe")

        with pytest.raises(UnavailableError) as excinfo:
            alembic_guard.require_single_head(engine)

        assert excinfo.value.http_status == 503
        assert excinfo.value.retryable is True
        assert "deadbeefcafe" in excinfo.value.message
        assert "do not exist in the installed migration scripts" in excinfo.value.message
        assert "manual inspection" in excinfo.value.recovery_action.lower()
        assert "can't locate revision" in excinfo.value.recovery_action.lower()
        assert excinfo.value.recovery_action != (
            "Run `uv run alembic upgrade head` to bring the database to "
            "the current head."
        )
    finally:
        engine.dispose()


def test_unmigrated_and_unknown_revision_recovery_actions_are_distinguishable(
    database_url: str,
) -> None:
    """Both failure modes raise the same `UnavailableError` type, but an
    operator (or a log line) must be able to tell "never migrated" apart
    from "stamped at a revision unknown to the installed migration scripts"
    from the `recovery_action` alone.
    """
    engine = create_engine_for(database_url)
    try:
        with pytest.raises(UnavailableError) as unmigrated_excinfo:
            alembic_guard.require_single_head(engine)

        _stamp_revision(engine)

        with pytest.raises(UnavailableError) as unknown_excinfo:
            alembic_guard.require_single_head(engine)

        assert (
            unmigrated_excinfo.value.recovery_action != unknown_excinfo.value.recovery_action
        )
    finally:
        engine.dispose()


def test_create_app_lifespan_refuses_to_start_against_unmigrated_database(
    database_url: str,
) -> None:
    """Driven through `TestClient`/lifespan startup rather than calling
    `require_single_head` directly -- the guard being correct in isolation
    doesn't prove `create_app` actually invokes it before serving traffic.
    """
    settings = Settings(database_url=database_url)  # never migrated
    app = create_app(settings)

    with pytest.raises(UnavailableError), TestClient(app):
        pass


def test_create_app_lifespan_refuses_to_start_against_unknown_revision_database(
    database_url: str,
) -> None:
    engine = create_engine_for(database_url)
    try:
        _stamp_revision(engine)
    finally:
        engine.dispose()

    settings = Settings(database_url=database_url)
    app = create_app(settings)

    with pytest.raises(UnavailableError), TestClient(app):
        pass


def test_create_app_lifespan_starts_against_migrated_database(settings: Settings) -> None:
    """Control case: the same lifespan path succeeds once the database is
    genuinely at head, so the two refusal tests above are proven against a
    guard that isn't simply refusing unconditionally.
    """
    app = create_app(settings)

    with TestClient(app) as test_client:
        response = test_client.get("/api/v1/health")
        assert response.status_code == 200
