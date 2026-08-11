"""Alembic single-head startup/offline-tooling gate (spec §4.8; ticket
IDK-101: "server and offline tooling both refuse to start against a
non-head Alembic database").

`require_single_head` is the one check the HTTP server's startup path and
offline CLI tooling both call before touching the database further. It
never runs migrations itself, only diagnoses. Every failure raises
`UnavailableError` (503, retryable) with a `recovery_action`: the command
that fixes it, or -- where no command can safely fix it, e.g. a corrupt
file or a schema Alembic doesn't recognise -- a statement that the
database needs manual inspection rather than a command that would itself
fail.
"""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import Engine, inspect
from sqlalchemy.exc import DatabaseError, OperationalError

import yuno
from yuno.config import get_settings
from yuno.shared.domain.errors import UnavailableError


def build_alembic_config() -> Config:
    """Build an Alembic `Config` from the installed package's location.

    Uses `Path(yuno.__file__).parent / "migrations"` rather than any path
    relative to the process's current working directory: offline tooling
    (and the server) may be launched from anywhere, unlike the bare
    `alembic` CLI, which resolves `alembic.ini`'s `script_location`
    relative to that ini file.
    """
    config = Config()
    config.set_main_option("script_location", str(Path(yuno.__file__).parent / "migrations"))
    config.set_main_option("sqlalchemy.url", get_settings().database_url)
    return config


def _revision_known(script: ScriptDirectory, revision: str) -> bool:
    """Whether `revision` resolves against the installed migration scripts.

    A stamped `alembic_version` row can hold a revision id that simply
    doesn't exist in this package's `migrations/versions/` -- a migration
    deleted after the database was stamped, or a database from a different
    version of the codebase. `ScriptDirectory.get_revision` is Alembic's own
    resolution mechanism (the same one `alembic upgrade <rev>` uses), and
    raises `CommandError` for exactly this case.
    """
    try:
        script.get_revision(revision)
    except CommandError:
        return False
    return True


def require_single_head(engine: Engine) -> str:
    """Raise unless `engine`'s database is at the single expected Alembic head.

    Checks, in order: whether the migration scripts themselves have more
    than one head -- a property of the installed package, so checked
    before any database connection is opened; whether the database file
    can be read at all; whether an existing, non-empty schema has no
    recorded Alembic version (a migration interrupted partway through, or
    a schema created outside Alembic), diagnosed separately from "never
    initialised" because that state's "run `alembic upgrade head`" advice
    would fail here with "table ... already exists"; and whether the
    stamped revision exists in the installed migration scripts, diagnosed
    separately from "behind head" because "run `alembic upgrade head`"
    would fail here with "Can't locate revision" instead.

    Returns the head revision string on success.
    """
    script = ScriptDirectory.from_config(build_alembic_config())
    script_heads = script.get_heads()

    if not script_heads:
        raise UnavailableError(
            "No Alembic migrations were found in the installed `yuno` package.",
            recovery_action=(
                "Reinstall or rebuild the `yuno` package -- its "
                "migrations/versions directory is missing or empty."
            ),
        )
    if len(script_heads) > 1:
        raise UnavailableError(
            "Multiple Alembic heads are present in the migration scripts: "
            f"{', '.join(sorted(script_heads))}.",
            recovery_action=(
                "Run `uv run alembic merge heads -m <message>` to create a "
                "merge revision, then `uv run alembic upgrade head`."
            ),
        )
    (expected_head,) = script_heads

    try:
        with engine.connect() as connection:
            current_heads = MigrationContext.configure(connection).get_current_heads()
            existing_tables: set[str] = set()
            if not current_heads:
                existing_tables = set(inspect(connection).get_table_names()) - {
                    "alembic_version"
                }
    except OperationalError as exc:
        raise UnavailableError(
            "Could not open the database to check its Alembic version: "
            f"{exc.orig}",
            recovery_action=(
                "Verify `YUNO_DATABASE_URL` is correct and that its parent "
                "directory exists and is writable, then restart -- this "
                "database file could not be opened at all."
            ),
        ) from exc
    except DatabaseError as exc:
        raise UnavailableError(
            "The database at the configured URL is not a valid SQLite "
            f"database: {exc.orig}",
            recovery_action=(
                "This file is corrupt or is not a SQLite database and "
                "cannot be repaired automatically -- restore it from "
                "backup or point `YUNO_DATABASE_URL` at a fresh database "
                "file, then run `uv run alembic upgrade head`."
            ),
        ) from exc

    if not current_heads:
        if existing_tables:
            raise UnavailableError(
                "Database has an existing schema "
                f"({', '.join(sorted(existing_tables))}) but no Alembic "
                "version is recorded: a migration may have been "
                "interrupted partway through, or this schema was created "
                "outside Alembic.",
                recovery_action=(
                    "This database needs manual inspection before any "
                    "Alembic command is run against it -- compare its "
                    "existing tables to migrations/versions/ to determine "
                    "what happened. Running `alembic upgrade head` here "
                    "will fail with \"table ... already exists\"."
                ),
            )
        raise UnavailableError(
            "Database is not initialised: no Alembic version is recorded.",
            recovery_action="Run `uv run alembic upgrade head` against this database.",
        )

    unknown_revisions = sorted(
        revision for revision in current_heads if not _revision_known(script, revision)
    )
    if unknown_revisions:
        raise UnavailableError(
            "Database is stamped at Alembic revision(s) "
            f"{', '.join(unknown_revisions)}, which do not exist in the "
            "installed migration scripts: deleted, or from a different "
            "version of the codebase.",
            recovery_action=(
                "This database needs manual inspection before any Alembic "
                "command is run against it -- confirm `YUNO_DATABASE_URL` "
                "points at the intended database file, and reconcile its "
                "`alembic_version` table against the installed migrations "
                "in migrations/versions/. Running `alembic upgrade head` "
                "here will fail with \"Can't locate revision\"."
            ),
        )

    if set(current_heads) != {expected_head}:
        raise UnavailableError(
            "Database is behind the current Alembic head (database at "
            f"{sorted(current_heads)}, expected {expected_head!r}).",
            recovery_action=(
                "Run `uv run alembic upgrade head` to bring the database to "
                "the current head."
            ),
        )

    return expected_head
