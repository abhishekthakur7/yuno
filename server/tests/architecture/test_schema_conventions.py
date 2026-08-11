"""Schema-convention sweep proving DAT-01: every table in the SQLAlchemy
metadata outside an explicit allow-list carries `owner_id` (and `goal_id`
where goal-owned) with the composite FK.

Written as a data-driven sweep over `Base.metadata.tables` (see
`yuno.models`'s own docstring on why importing it is sufficient to
populate the metadata), so it needs no edits as later tables are added.
Nothing here hardcodes today's table names — see `ALL_TABLES`/
`OWNED_TABLES` below.
"""

from __future__ import annotations

import re

import pytest
from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKeyConstraint,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
)

import yuno.models  # noqa: F401 - side effect: populates Base.metadata
from yuno.shared.infrastructure.base import OWNERLESS_TABLES, Base

# ---------------------------------------------------------------------------
# Column-classification heuristics.
#
# SQLAlchemy has no first-class "this is a boolean"/"this is an enum"
# marker here — the project's convention (`yuno.shared.infrastructure.base`) is a
# plain TEXT/INTEGER column plus a CHECK constraint, not
# `sqlalchemy.Enum`/`Boolean`. So "boolean-ish"/"enum-ish" is necessarily a
# naming convention, matched narrowly (exact names, or is_/has_ prefixes)
# to avoid false positives: `audit_events.entity_type` and `.actor_role`
# reference an intentionally open-ended, cross-module vocabulary and would
# be wrongly flagged by a looser `_type`/`_role` suffix match.
# ---------------------------------------------------------------------------

_ID_OR_TIMESTAMP_SUFFIXES = ("_id", "_at")
_ID_OR_TIMESTAMP_EXACT = {"id"}


def _is_id_or_timestamp_column(name: str) -> bool:
    return name in _ID_OR_TIMESTAMP_EXACT or name.endswith(_ID_OR_TIMESTAMP_SUFFIXES)


_BOOLEAN_PREFIXES = ("is_", "has_")


def _is_boolean_ish_column(name: str) -> bool:
    return name.startswith(_BOOLEAN_PREFIXES)


_ENUM_EXACT = {"kind", "status", "role", "type"}


def _is_enum_ish_column(name: str) -> bool:
    return name in _ENUM_EXACT


# ---------------------------------------------------------------------------
# Constraint introspection helpers, reused by both the real sweep below
# and the self-test at the bottom of this file.
# ---------------------------------------------------------------------------


def _foreign_key_constraints(table: Table) -> list[ForeignKeyConstraint]:
    return [c for c in table.constraints if isinstance(c, ForeignKeyConstraint)]


def _unique_constraints(table: Table) -> list[UniqueConstraint]:
    return [c for c in table.constraints if isinstance(c, UniqueConstraint)]


def _check_constraint_texts(table: Table) -> list[str]:
    return [str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)]


def _has_direct_foreign_key(table: Table, column: str, target_table: str, target_column: str) -> bool:
    """Whether some FK constraint's local columns are *exactly* `{column}`
    (a genuine single-column FK, not incidentally part of a composite one)
    and it targets `target_table.target_column`.
    """
    for fk in _foreign_key_constraints(table):
        local_columns = {c.name for c in fk.columns}
        if local_columns != {column}:
            continue
        for element in fk.elements:
            if element.column.table.name == target_table and element.column.name == target_column:
                return True
    return False


def _has_composite_foreign_key_covering(table: Table, columns: set[str]) -> bool:
    """Whether some FK constraint is a genuine composite (more than one
    local column) whose local columns include all of `columns`.
    """
    for fk in _foreign_key_constraints(table):
        local_columns = {c.name for c in fk.columns}
        if len(local_columns) > 1 and columns.issubset(local_columns):
            return True
    return False


def _has_unique_constraint_exactly(table: Table, columns: set[str]) -> bool:
    return any({c.name for c in uc.columns} == columns for uc in _unique_constraints(table))


def _is_goal_owned(table: Table) -> bool:
    """A table is goal-owned (spec §4.1) when every row necessarily
    belongs to one goal, i.e. `goal_id` is NOT NULL. A nullable `goal_id`
    is an optional cross-reference, not ownership: `audit_events` carries
    a nullable `goal_id` (it logs both owner- and goal-scoped actions) and
    correctly omits it from its composite UNIQUE/FK. Detecting
    "goal-owned" by mere column presence would wrongly flag that table, so
    NOT NULL is the signal.
    """
    column = table.columns.get("goal_id")
    return column is not None and not column.nullable


# ---------------------------------------------------------------------------
# Table collections the parametrized tests sweep over. Computed once at
# import time from the real `Base.metadata` — not a fixed list of names.
# ---------------------------------------------------------------------------

ALL_TABLES = sorted(Base.metadata.tables.values(), key=lambda t: t.name)
OWNED_TABLES = [t for t in ALL_TABLES if t.name not in OWNERLESS_TABLES]

_ALL_TABLE_IDS = [t.name for t in ALL_TABLES]
_OWNED_TABLE_IDS = [t.name for t in OWNED_TABLES]

# Several §4.1 rules apply only to tables carrying a particular column or
# key shape. Parametrizing those over every table means one skip per table
# for a rule no table exercises yet — 18 skips for two rules, all carrying
# the single fact "no table has adopted this column". Parametrizing over
# the applicable subset instead keeps per-table granularity the moment a
# qualifying table lands, and reports one clearly-reasoned skip until then.
GOAL_OWNED_TABLES = [t for t in OWNED_TABLES if _is_goal_owned(t)]
ID_PK_OWNED_TABLES = [t for t in OWNED_TABLES if "id" in {c.name for c in t.primary_key.columns}]
BOOLEAN_COLUMN_TABLES = [t for t in ALL_TABLES if any(_is_boolean_ish_column(c.name) for c in t.columns)]
ROW_VERSION_TABLES = [t for t in ALL_TABLES if "row_version" in t.columns]


def _tables_or_skip(tables: list[Table], rule: str) -> list:
    if tables:
        return [pytest.param(t, id=t.name) for t in tables]
    return [
        pytest.param(
            None,
            id="no-such-table-yet",
            marks=pytest.mark.skip(reason=f"no table {rule} yet; this rule binds when one does"),
        )
    ]


def test_metadata_sweep_is_not_vacuous():
    """Guard against the sweep silently checking zero tables, e.g. if
    `yuno.models` stopped importing a module's model module.
    """
    assert len(Base.metadata.tables) > 0, "Base.metadata has no tables; did a model import get removed?"


# ---------------------------------------------------------------------------
# Ownership conventions (spec §4.1), for every table outside
# OWNERLESS_TABLES (`yuno.shared.infrastructure.base.OWNERLESS_TABLES`).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("table", OWNED_TABLES, ids=_OWNED_TABLE_IDS)
def test_owner_id_column_is_text_not_null(table: Table) -> None:
    assert "owner_id" in table.columns, f"{table.name}: missing owner_id column"
    column = table.columns["owner_id"]
    assert isinstance(column.type, Text), f"{table.name}.owner_id must be TEXT, got {column.type}"
    assert not column.nullable, f"{table.name}.owner_id must be NOT NULL"


@pytest.mark.parametrize("table", OWNED_TABLES, ids=_OWNED_TABLE_IDS)
def test_owner_id_has_foreign_key_to_owners(table: Table) -> None:
    assert _has_direct_foreign_key(table, "owner_id", "owners", "id"), (
        f"{table.name}.owner_id must carry a foreign key to owners.id"
    )


@pytest.mark.parametrize("table", _tables_or_skip(GOAL_OWNED_TABLES, "is goal-owned"))
def test_goal_owned_table_has_composite_owner_goal_foreign_key(table: Table) -> None:
    assert _has_composite_foreign_key_covering(table, {"owner_id", "goal_id"}), (
        f"{table.name} has a NOT NULL goal_id but no composite foreign key covering "
        f"(owner_id, goal_id) — spec §4.1: composite FKs prevent cross-owner/goal references"
    )


@pytest.mark.parametrize("table", _tables_or_skip(ID_PK_OWNED_TABLES, "has a standalone id primary key"))
def test_id_primary_key_table_has_composite_unique_with_owner(table: Table) -> None:
    expected = {"id", "owner_id"}
    if _is_goal_owned(table):
        expected.add("goal_id")
    found = [sorted(c.name for c in uc.columns) for uc in _unique_constraints(table)]
    assert _has_unique_constraint_exactly(table, expected), (
        f"{table.name}: expected a composite UNIQUE{tuple(sorted(expected))}, "
        f"found unique constraints: {found}"
    )


# ---------------------------------------------------------------------------
# Mechanical spec §4.1 conventions across ALL tables (including
# OWNERLESS_TABLES, e.g. `owners` itself).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("table", ALL_TABLES, ids=_ALL_TABLE_IDS)
def test_id_and_timestamp_columns_are_text(table: Table) -> None:
    for column in table.columns:
        if _is_id_or_timestamp_column(column.name):
            assert isinstance(column.type, Text), (
                f"{table.name}.{column.name} looks like an id/timestamp column and must be "
                f"TEXT, got {column.type}"
            )


@pytest.mark.parametrize("table", _tables_or_skip(BOOLEAN_COLUMN_TABLES, "has an is_/has_ boolean column"))
def test_boolean_ish_columns_are_integer_with_01_check(table: Table) -> None:
    check_texts = _check_constraint_texts(table)
    for column in (c for c in table.columns if _is_boolean_ish_column(c.name)):
        assert isinstance(column.type, Integer), (
            f"{table.name}.{column.name} looks boolean (is_/has_ prefix) and must be "
            f"INTEGER, got {column.type}"
        )
        pattern = re.compile(rf"\b{re.escape(column.name)}\b\s+IN\s*\(\s*0\s*,\s*1\s*\)")
        assert any(pattern.search(text) for text in check_texts), (
            f"{table.name}.{column.name} looks boolean (is_/has_ prefix) and must carry a "
            f"CHECK({column.name} IN (0,1)) constraint; found checks: {check_texts}"
        )


@pytest.mark.parametrize("table", ALL_TABLES, ids=_ALL_TABLE_IDS)
def test_enum_ish_columns_have_check_constraint(table: Table) -> None:
    check_texts = _check_constraint_texts(table)
    for column in table.columns:
        if not _is_enum_ish_column(column.name):
            continue
        pattern = re.compile(rf"\b{re.escape(column.name)}\b")
        assert any(pattern.search(text) for text in check_texts), (
            f"{table.name}.{column.name} is an enumeration column (spec §4.1) and must carry "
            f"a CHECK constraint; found checks: {check_texts}"
        )


@pytest.mark.parametrize("table", _tables_or_skip(ROW_VERSION_TABLES, "has a row_version column"))
def test_row_version_column_is_integer_not_null_default_1(table: Table) -> None:
    column = table.columns["row_version"]
    assert isinstance(column.type, Integer), f"{table.name}.row_version must be INTEGER, got {column.type}"
    assert not column.nullable, f"{table.name}.row_version must be NOT NULL"
    assert column.server_default is not None and str(column.server_default.arg).strip() == "1", (
        f"{table.name}.row_version must have DEFAULT 1, got server_default={column.server_default!r}"
    )


# ---------------------------------------------------------------------------
# Self-test: no goal-owned table exists in the current schema, so the
# goal-owned composite-FK rule above is never exercised by real data.
# Prove the checker helper correctly flags a violation and correctly
# accepts a compliant schema.
# ---------------------------------------------------------------------------


def test_composite_owner_goal_fk_helper_detects_a_missing_composite_fk() -> None:
    scratch = MetaData()
    table = Table(
        "scratch_missing_composite_fk",
        scratch,
        Column("id", Text, primary_key=True),
        Column("owner_id", Text, nullable=False),
        Column("goal_id", Text, nullable=False),
    )
    assert _is_goal_owned(table)
    assert not _has_composite_foreign_key_covering(table, {"owner_id", "goal_id"}), (
        "self-test setup is wrong: this scratch table must not have a composite FK"
    )


def test_composite_owner_goal_fk_helper_accepts_a_present_composite_fk() -> None:
    scratch = MetaData()
    table = Table(
        "scratch_with_composite_fk",
        scratch,
        Column("id", Text, primary_key=True),
        Column("owner_id", Text, nullable=False),
        Column("goal_id", Text, nullable=False),
        ForeignKeyConstraint(["owner_id", "goal_id"], ["scratch_goals.owner_id", "scratch_goals.id"]),
    )
    assert _is_goal_owned(table)
    assert _has_composite_foreign_key_covering(table, {"owner_id", "goal_id"})
