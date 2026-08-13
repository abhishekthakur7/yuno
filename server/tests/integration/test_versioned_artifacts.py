"""The thirteen independently versioned artifacts of spec §4.8 (IDK-501).

IDK-501: "Confirm the thirteen artifacts in §4.8 ... each carry a distinct
version identifier that does not conflate with the Alembic schema version."

`yuno.versioned_artifacts` is the inventory under test. These tests exist
because the failure mode is silent: nothing breaks at runtime when two
artifacts accidentally share an identifier, or when an artifact's "version"
turns out to be the Alembic revision -- the damage only appears later, when
an upgrade is blamed for a provenance change it did not cause, or a cache is
not invalidated because its key never moved.
"""

from __future__ import annotations

from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect

from yuno.shared.infrastructure import alembic_guard
from yuno.versioned_artifacts import VERSIONED_ARTIFACTS, VersionSource

# Spec §4.8's list, verbatim and in spec order. Duplicated here on purpose:
# if someone edits the inventory, this literal is what makes the edit visible
# rather than self-approving.
SPEC_4_8_ARTIFACTS = (
    "Alembic schema",
    "canonical manifest",
    "graph",
    "content revision",
    "overlay format",
    "import parser",
    "prompt template",
    "provider contract",
    "derived-state rules",
    "generated artifacts",
    "job payload/result",
    "FTS projection",
    "export format",
)


def test_inventory_covers_exactly_the_thirteen_spec_artifacts() -> None:
    assert tuple(artifact.name for artifact in VERSIONED_ARTIFACTS) == (
        SPEC_4_8_ARTIFACTS
    )
    assert len(VERSIONED_ARTIFACTS) == 13


def test_every_artifact_carries_an_identifier() -> None:
    """No artifact may be listed without something that actually versions it.

    A `BUILD` artifact needs at least one non-blank constant; a `RECORD`
    artifact needs the column that carries its per-row value. An entry with
    neither is an artifact that is not independently versioned at all.
    """
    for artifact in VERSIONED_ARTIFACTS:
        if artifact.source is VersionSource.BUILD:
            assert artifact.identifiers, artifact.name
            assert all(value.strip() for value in artifact.identifiers), artifact.name
            assert artifact.column is None, artifact.name
        else:
            assert artifact.column, artifact.name
            assert not artifact.identifiers, artifact.name
        assert artifact.defined_in.strip(), artifact.name


def test_build_identifiers_are_distinct() -> None:
    """Distinct across artifacts, not merely distinct within one artifact.

    Two artifacts sharing a string would make them move together forever --
    the opposite of §4.8's "independently version" requirement.
    """
    identifiers = [
        value for artifact in VERSIONED_ARTIFACTS for value in artifact.identifiers
    ]
    assert len(identifiers) == len(set(identifiers)), sorted(identifiers)


def test_no_artifact_identifier_conflates_with_the_alembic_schema_version() -> None:
    """The one conflation §4.8 calls out by name.

    Checked against every revision in the chain, not just the current head:
    an identifier that happens to equal a *past* revision is the same latent
    confusion, and would silently become ambiguous in any log or diff that
    prints a bare version string.
    """
    script = ScriptDirectory.from_config(alembic_guard.build_alembic_config())
    revisions = {revision.revision for revision in script.walk_revisions()}
    assert revisions

    for artifact in VERSIONED_ARTIFACTS:
        for value in artifact.identifiers:
            assert value not in revisions, f"{artifact.name} -> {value}"


def test_alembic_schema_entry_resolves_to_the_installed_head(engine: Engine) -> None:
    """The inventory's schema entry must track the real head, not a copy of it.

    `require_single_head` reads the same `alembic_version.version_num` the
    inventory names, so this also proves the named column is the one actually
    consulted at startup.
    """
    (schema_artifact,) = [
        artifact
        for artifact in VERSIONED_ARTIFACTS
        if artifact.name == "Alembic schema"
    ]
    assert schema_artifact.source is VersionSource.RECORD
    assert schema_artifact.column == "alembic_version.version_num"

    script = ScriptDirectory.from_config(alembic_guard.build_alembic_config())
    assert alembic_guard.require_single_head(engine) == script.get_current_head()


def test_record_carried_identifiers_name_real_columns(engine: Engine) -> None:
    """Every `RECORD` entry must point at a column that exists at head.

    A stale `table.column` here is worse than no inventory: it reads as a
    verified claim while naming storage that no longer exists.
    """
    inspector = inspect(engine)
    for artifact in VERSIONED_ARTIFACTS:
        if artifact.source is not VersionSource.RECORD:
            continue
        table, _, column = (artifact.column or "").partition(".")
        assert table in inspector.get_table_names(), artifact.name
        columns = {entry["name"] for entry in inspector.get_columns(table)}
        assert column in columns, f"{artifact.name} -> {artifact.column}"
