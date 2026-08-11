"""Declarative base, constraint naming convention and shared column helpers
implementing spec §4.1's database conventions.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Integer, MetaData, Text
from sqlalchemy.orm import DeclarativeBase, MappedColumn, mapped_column

# Standard Alembic-recommended naming convention: every constraint/index
# gets a deterministic name so autogenerate diffs cleanly.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Shared declarative base. Every ORM model inherits from this."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


OWNERLESS_TABLES: frozenset[str] = frozenset(
    {
        "alembic_version",
        "owners",
        # `canonical` module (spec §4.3, IDK-102): global editorial/reference
        # content, not owner-scoped learner data. Every approved
        # `CanonicalGraphVersion` (and its topics/relations/content
        # revisions/approval) is authored once, offline, by the D1
        # publisher and then read by every owner's roadmap/topic/search/
        # generation/diff reads alike -- it is not a row any single
        # owner's UoW creates for itself, so it must not carry `owner_id`.
        # See `yuno.modules.canonical.models`'s module docstring for the
        # full reasoning.
        "canonical_graph_versions",
        "topic_identities",
        "topics",
        "topic_relations",
        "content_revisions",
        "editorial_approvals",
    }
)
"""Explicit allow-list of tables with no `owner_id` column, because
`owners.id` *is* the owner id and `alembic_version` isn't owner data. The
schema-sweep test asserts every other table in `Base.metadata` carries
`owner_id`.
"""


def id_column(*, primary_key: bool = True) -> MappedColumn[str]:
    """Opaque TEXT id column (ULID/UUID); primary key by default."""
    return mapped_column(Text, primary_key=primary_key)


def utc_timestamp_column(*, nullable: bool = False) -> MappedColumn[str]:
    """UTC TEXT timestamp column — format produced by `domain.clock.utc_text`."""
    return mapped_column(Text, nullable=nullable)


def boolean_column(name: str, *, default: bool, nullable: bool = False) -> MappedColumn[int]:
    """`INTEGER` column with `CHECK(value IN (0,1))` storing a boolean.

    `name` must match the attribute/column name it's assigned to, since it's
    used verbatim in the generated CHECK SQL, e.g.:

        is_active: Mapped[int] = boolean_column("is_active", default=True)
    """
    return mapped_column(
        Integer,
        CheckConstraint(f"{name} IN (0,1)", name=f"{name}_in_0_1"),
        nullable=nullable,
        default=int(default),
        server_default=str(int(default)),
    )


def row_version_column() -> MappedColumn[int]:
    """`row_version INTEGER NOT NULL DEFAULT 1` for mutable aggregates."""
    return mapped_column(Integer, nullable=False, default=1, server_default="1")
