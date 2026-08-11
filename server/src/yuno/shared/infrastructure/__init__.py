"""Cross-cutting infrastructure: engine/session construction, the
declarative base and shared column helpers, the Alembic single-head guard,
the base repository helper, and the in-process job dispatcher adapter.

Unlike `yuno.shared.domain`/`yuno.shared.application`, this package may
freely depend on SQLAlchemy and other frameworks, but the `yuno.shared`
package docstring's import rule still applies: module ORM models/
repositories depend on this package, never the reverse.
"""
