"""Forward-only migration discipline across the whole revision chain (IDK-501).

IDK-501: "Verify forward-only expand/backfill/contract discipline for every
migration accumulated across Phases 1-4: no destructive drop before backfill;
no in-place rewrite of an approved canonical version's rows."

Written as a source sweep over `migrations/versions/` rather than as a
behavioural test, because the property is about what the corpus *contains*,
not about what one run does: a migration that rewrites an approved canonical
row is a defect the moment it is committed, and waiting for a fixture that
happens to hold such a row to catch it is exactly the gap Appendix H's D1
("approved canonical versions are never data-migrated in place") warns about.

The canonical immutability triggers (`trg_<table>_no_update` and friends,
created in `87af9746aec1`) would abort such a write at runtime -- but only if
a database actually holds a published row when the migration runs, and only
if some later migration has not silently dropped the triggers through a batch
table rebuild. Neither is guaranteed, so the corpus is checked directly.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from alembic.script import ScriptDirectory

import yuno
from yuno.shared.infrastructure import alembic_guard

# Resolved off the installed package, exactly as `build_alembic_config` does,
# so the sweep reads the same scripts the guard and `alembic upgrade` do.
VERSIONS_DIRECTORY = Path(yuno.__file__).parent / "migrations" / "versions"

# Spec §4.3's approved-canonical tables. D1 makes these append-only across
# migrations: a correction publishes a *new* version and resolves it through
# D9, it never edits the rows of an approved one.
APPROVED_CANONICAL_TABLES = frozenset(
    {
        "canonical_graph_versions",
        "topics",
        "topic_relations",
        "content_revisions",
        "editorial_approvals",
    }
)

# DML, as opposed to DDL. `CREATE TRIGGER` bodies legitimately contain
# `UPDATE`/`DELETE` keywords (they are the statements being *guarded*), so
# trigger definitions are excluded before this is applied.
_DML = re.compile(
    r"\b(?:INSERT\s+INTO|INSERT\s+OR\s+REPLACE\s+INTO|UPDATE|DELETE\s+FROM)\b",
    re.IGNORECASE,
)
_CREATE_TRIGGER = re.compile(
    r"CREATE\s+TRIGGER\b.*?\bEND\b", re.IGNORECASE | re.DOTALL
)


def _migration_paths() -> list[Path]:
    return sorted(VERSIONS_DIRECTORY.glob("*.py"))


def _sql_literals(source: str) -> list[str]:
    """Every string constant in the module, which is where raw SQL lives.

    Migrations issue raw SQL through `op.execute(...)`/`sa.text(...)`, so the
    string constants are the statements. Parsing with `ast` rather than
    grepping the file keeps comments and docstrings that merely *discuss*
    a DELETE from registering as one.
    """
    tree = ast.parse(source)
    literals: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            literals.append(node.value)
    return literals


def test_migrations_directory_is_discoverable() -> None:
    """Guard against the sweeps below silently passing on an empty glob."""
    paths = _migration_paths()
    assert len(paths) >= 20, paths

    script = ScriptDirectory.from_config(alembic_guard.build_alembic_config())
    assert len(list(script.walk_revisions())) == len(paths)


@pytest.mark.parametrize(
    "path", _migration_paths(), ids=lambda path: path.stem[:20]
)
def test_no_migration_writes_to_an_approved_canonical_table(path: Path) -> None:
    """D1, enforced against the migration corpus itself.

    Only DML is a violation. A migration may freely `CREATE TABLE topics` or
    attach a trigger to `canonical_graph_versions` -- what it may never do is
    `UPDATE`/`DELETE`/`INSERT` a row of an already-approved version.
    """
    source = path.read_text()
    for literal in _sql_literals(source):
        statement = _CREATE_TRIGGER.sub("", literal)
        if not _DML.search(statement):
            continue
        for table in APPROVED_CANONICAL_TABLES:
            assert not re.search(rf"\b{table}\b", statement), (
                f"{path.name} issues DML against approved-canonical table "
                f"{table!r}: {statement.strip()[:200]}"
            )


@pytest.mark.parametrize(
    "path", _migration_paths(), ids=lambda path: path.stem[:20]
)
def test_downgrade_is_either_a_real_inverse_or_an_explicit_refusal(
    path: Path,
) -> None:
    """Forward-only is a stance a migration must take deliberately.

    Spec §4.8 mandates forward-only migrations. A revision whose data
    movement genuinely cannot be inverted must say so by raising -- the
    failure this catches is the silently *wrong* `downgrade()` that appears
    to work and quietly discards backfilled data. A refusal must also state
    why in its module docstring: "this migration cannot be reversed" is an
    operational fact that belongs where an operator reads it, not only in
    the body of a function nobody reads until it is too late.
    """
    tree = ast.parse(path.read_text())
    downgrades = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "downgrade"
    ]
    assert len(downgrades) == 1, path.name
    (downgrade,) = downgrades

    body = [node for node in downgrade.body if not _is_docstring(node)]
    assert body, f"{path.name} has an empty downgrade()"

    raises_only = len(body) == 1 and isinstance(body[0], ast.Raise)
    if raises_only:
        # An explicit refusal is the other legal shape; it must be a
        # NotImplementedError, not a bare `raise` or an arbitrary exception.
        raised = body[0].exc
        assert isinstance(raised, ast.Call), path.name
        assert isinstance(raised.func, ast.Name), path.name
        assert raised.func.id == "NotImplementedError", path.name

        docstring = (ast.get_docstring(tree) or "").lower()
        assert "forward-only" in docstring, (
            f"{path.name} refuses to downgrade but its module docstring does "
            "not say it is forward-only"
        )


def _is_docstring(node: ast.stmt) -> bool:
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
