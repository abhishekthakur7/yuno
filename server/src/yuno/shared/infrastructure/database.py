"""SQLAlchemy engine/session-factory construction (spec §4.1).

`create_engine_for` is the only place SQLite pragmas are configured, so
every connection — regardless of which repository or module opens it —
gets foreign-key enforcement.
"""

from __future__ import annotations

import sqlite3

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def create_engine_for(url: str) -> Engine:
    """Create the SQLAlchemy engine for `url`.

    Registers a `connect` event listener that issues `PRAGMA
    foreign_keys=ON` on every new DBAPI connection, plus `journal_mode=WAL`
    and a `busy_timeout` so concurrent readers don't fail immediately
    against a writer.

    WAL permits exactly one writer, so a contended write waits rather than
    failing. `busy_timeout` bounds that wait: on expiry SQLite raises
    "database is locked", which the provider service classifies as
    `storage-contention` and surfaces as a failed job. 30s is chosen over
    the previous 5s because a wait is recoverable and a failed job is not
    -- the job the learner started is lost either way at expiry, so the
    only thing a short timeout buys is losing it sooner. It is a ceiling,
    not a delay: an uncontended write never waits at all.
    """
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: sqlite3.Connection, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
