"""Shared fixtures for the SQLite integration suite: a real, isolated
database per test, migrated to head.

Fixtures build the schema by running `alembic_guard.build_alembic_config()`
+ `command.upgrade(cfg, "head")`, never `Base.metadata.create_all`: the
`audit_events` append-only triggers are created by the migration's raw
`op.execute(...)` calls, not by anything in `Base.metadata`, so
`create_all()` would produce a schema missing exactly the guarantee
`test_audit_append_only.py` exists to prove.

`migrated_database_url` points the upgrade at the tmp database by setting
`sqlalchemy.url` directly on the `Config` (`set_main_option`), rather than
via `YUNO_DATABASE_URL` + `get_settings()`. `migrations/env.py` honours an
explicitly configured `Config` over the process-wide `get_settings()`
cache, so no fixture here needs to mutate the environment or call
`get_settings.cache_clear()`.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from yuno.api.app import create_app
from yuno.config import Settings
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.infrastructure import alembic_guard
from yuno.shared.infrastructure.database import (
    create_engine_for,
    create_session_factory,
)
from yuno.unit_of_work import create_unit_of_work_factory


@pytest.fixture
def database_url(tmp_path) -> str:
    """A scratch SQLite URL under `tmp_path`, deliberately left unmigrated
    (SQLite creates the file lazily on first connection, so this is a
    genuinely empty database). Most tests want `migrated_database_url`
    instead; the Alembic-guard tests use this fixture directly.
    """
    db_path = tmp_path / "yuno-test.db"
    return f"sqlite+pysqlite:///{db_path}"


@pytest.fixture
def migrated_database_url(database_url: str) -> str:
    """`database_url`, migrated to head via the real upgrade path -- see
    module docstring for why this must not be `Base.metadata.create_all`.
    """
    config = alembic_guard.build_alembic_config()
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    return database_url


@pytest.fixture
def settings(migrated_database_url: str, tmp_path) -> Settings:
    return Settings(
        database_url=migrated_database_url,
        structured_log_directory=tmp_path / "logs",
        export_privacy_review_approved=True,
        provider_capability_discovery_enabled=False,
    )


@pytest.fixture
def engine(migrated_database_url: str) -> Iterator[Engine]:
    """A real `Engine` bound to the migrated tmp database, built through
    `create_engine_for` so it carries the same pragma setup every
    production connection gets.
    """
    eng = create_engine_for(migrated_database_url)
    yield eng
    eng.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(engine)


@pytest.fixture
def uow_factory(session_factory: sessionmaker[Session]) -> UnitOfWorkFactory:
    return create_unit_of_work_factory(session_factory)


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """A `TestClient` over `create_app()`, driven through the real ASGI
    lifespan (Alembic head check plus local-owner provisioning).
    """
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client
