"""Alembic environment (spec §4.8).

Resolves the database URL from `context.config`'s `sqlalchemy.url` if set,
otherwise from `yuno.config.get_settings()` -- `alembic.ini`'s
`sqlalchemy.url` is intentionally left unset. `build_alembic_config()`
(`yuno.shared.infrastructure.alembic_guard`) sets `sqlalchemy.url` from current
settings by default, but a caller may override it on the `Config` afterward
(Alembic's documented pattern for pointing `command.upgrade(config, ...)`
at a specific database); that override must win over `get_settings()`.

Targets `Base.metadata`, populated by importing `yuno.models`,
and runs every migration in SQLite batch mode (`render_as_batch=True`,
required since SQLite's `ALTER TABLE` can't perform most column/constraint
changes directly).
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context

from yuno import models  # noqa: F401  (import populates Base.metadata)
from yuno.config import get_settings
from yuno.shared.infrastructure.base import Base
from yuno.shared.infrastructure.database import create_engine_for

# The Alembic Config object, providing access to values within alembic.ini.
config = context.config

# Interpret the config file for Python logging (handler/formatter setup
# only -- never the database URL, which always comes from application
# settings, not alembic.ini).
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _include_object(
    obj, name: str | None, type_: str, reflected: bool, compare_to
) -> bool:
    # SQLite exposes an FTS5 virtual table and its implementation shadow
    # tables through reflection. They are created by the search migration's
    # explicit CREATE VIRTUAL TABLE and are intentionally absent from ORM
    # metadata.
    return not (
        type_ == "table" and reflected and (name or "").startswith("search_fts")
    )


def _resolve_database_url() -> str:
    """Resolve the target database URL: an explicitly configured `Config` wins over `get_settings()`."""
    configured_url = config.get_main_option("sqlalchemy.url")
    if configured_url:
        return configured_url
    return get_settings().database_url


def run_migrations_offline() -> None:
    """Emit migration SQL without opening a database connection."""
    url = _resolve_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        include_object=_include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection.

    Uses `create_engine_for`, the same factory the running application uses,
    so the migration connection gets the same `PRAGMA foreign_keys=ON`
    (plus WAL/busy_timeout) setup as every other connection.
    """
    connectable = create_engine_for(_resolve_database_url())

    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=True,
                include_object=_include_object,
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
