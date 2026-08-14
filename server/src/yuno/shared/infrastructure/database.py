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

    `pool_size=20, max_overflow=30` (ceiling 50) replaces SQLAlchemy's
    stock default (5 + 10 = 15), which is just the library's generic
    default and was never sized for this app. This is a capacity fix, not
    a leak workaround -- IDK-504 traced a `QueuePool limit ... reached`
    failure to `GET /api/v1/events` (`api/routes/events.py`) blocking the
    ASGI event loop on a synchronous per-poll DB read; that starvation bug
    is fixed at the source (the read now runs via
    `starlette.concurrency.run_in_threadpool`). With that fix applied, a
    burst of 50 concurrent short-lived SSE connections (the shape of the
    IDK-504 perf sweep: many browser contexts opening `/events` at once,
    each independently resolving `get_owner_id` and then polling) still
    peaked at exactly 15 concurrently checked-out connections against the
    stock 5+10 pool, with 46/50 connections timing out; raising the
    ceiling to 50 carried the same burst with 0 errors and a measured peak
    of 45 concurrent checkouts, then returned to 0 once every client
    disconnected. Every connection here is a short-lived WAL reader, which
    SQLite serves cheaply and concurrently, so sizing for this burst adds
    memory/thread headroom, not contention risk.
    """
    engine = create_engine(url, pool_size=20, max_overflow=30)

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(
        dbapi_connection: sqlite3.Connection, _connection_record: object
    ) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
