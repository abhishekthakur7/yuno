"""The thirteen independently versioned artifacts of spec §4.8.

Spec §4.8 requires these to be versioned *independently*: "Alembic schema,
canonical manifest, graph, content revision, overlay format, import parser,
prompt template, provider contract, derived-state rules, generated artifacts,
job payload/result, FTS projection and export format." Independence is the
whole point -- an import-parser change must not force a schema migration, and
a schema migration must not silently redate every generated artifact's
provenance. Before this inventory existed, the identifiers were scattered
across nine modules and two of them did not exist at all, so "are these
thirteen actually distinct?" could only be answered by grepping.

This is a composition-root module, not a `shared/` one: it deliberately
reaches across every module to collect their identifiers, which the
`api > modules > shared` layering contract forbids `shared/` from doing.

Two kinds of identifier appear here, and conflating them is the mistake this
module exists to prevent:

* `BUILD` -- a constant compiled into this build. Every record the build
  writes carries it, and it changes only when the code changes.
* `RECORD` -- supplied per row by the offline publisher's manifest, so there
  is no single build-wide value; the entry names the column that carries it.

The Alembic schema version is itself `RECORD`-shaped (it lives in
`alembic_version.version_num`) and is resolved from the installed migration
scripts rather than hardcoded, so this inventory can never drift from head.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from yuno.modules.canonical.domain import CONTENT_REVISION_FORMAT_VERSION
from yuno.modules.evidence_evaluation.domain import FIXTURE_DERIVATION_VERSION
from yuno.modules.imports.domain import PARSER_VERSION
from yuno.modules.learning_content.domain import (
    GENERATION_SCHEMA_VERSION,
    PROMPT_TEMPLATE_VERSION,
)
from yuno.modules.provider.claude import CLAUDE_CONTRACT_VERSION
from yuno.modules.provider.codex import CODEX_CONTRACT_VERSION
from yuno.modules.roadmap.domain import OVERLAY_FORMAT_VERSION
from yuno.modules.search.repository import PROJECTION_VERSION
from yuno.modules.settings_data.service import EXPORT_FORMAT, EXPORT_VERSION
from yuno.shared.application.jobs import JOB_PAYLOAD_SCHEMA_VERSION


class VersionSource(StrEnum):
    BUILD = "build"
    RECORD = "record"


@dataclass(frozen=True)
class VersionedArtifact:
    """One §4.8 artifact and the identifier that versions it."""

    name: str
    source: VersionSource
    #: For `BUILD`, the identifier(s) this build stamps -- a tuple because the
    #: provider contract is genuinely per-adapter. For `RECORD`, empty.
    identifiers: tuple[str, ...]
    #: `table.column` carrying the identifier, for `RECORD` artifacts.
    column: str | None
    #: Where the identifier is defined or recorded, for a human tracing it.
    defined_in: str


VERSIONED_ARTIFACTS: tuple[VersionedArtifact, ...] = (
    VersionedArtifact(
        name="Alembic schema",
        source=VersionSource.RECORD,
        identifiers=(),
        column="alembic_version.version_num",
        defined_in="yuno.migrations.versions",
    ),
    VersionedArtifact(
        name="canonical manifest",
        source=VersionSource.RECORD,
        identifiers=(),
        column="canonical_graph_versions.manifest_version",
        defined_in="yuno.modules.canonical.domain.CanonicalGraphManifest",
    ),
    VersionedArtifact(
        name="graph",
        source=VersionSource.RECORD,
        identifiers=(),
        column="canonical_graph_versions.version_label",
        defined_in="yuno.modules.canonical.models.CanonicalGraphVersionRow",
    ),
    VersionedArtifact(
        name="content revision",
        source=VersionSource.BUILD,
        identifiers=(CONTENT_REVISION_FORMAT_VERSION,),
        column=None,
        defined_in="yuno.modules.canonical.domain.CONTENT_REVISION_FORMAT_VERSION",
    ),
    VersionedArtifact(
        name="overlay format",
        source=VersionSource.BUILD,
        identifiers=(OVERLAY_FORMAT_VERSION,),
        column=None,
        defined_in="yuno.modules.roadmap.domain.OVERLAY_FORMAT_VERSION",
    ),
    VersionedArtifact(
        name="import parser",
        source=VersionSource.BUILD,
        identifiers=(PARSER_VERSION,),
        column=None,
        defined_in="yuno.modules.imports.domain.PARSER_VERSION",
    ),
    VersionedArtifact(
        name="prompt template",
        source=VersionSource.BUILD,
        identifiers=(PROMPT_TEMPLATE_VERSION,),
        column=None,
        defined_in="yuno.modules.learning_content.domain.PROMPT_TEMPLATE_VERSION",
    ),
    VersionedArtifact(
        name="provider contract",
        source=VersionSource.BUILD,
        identifiers=(CLAUDE_CONTRACT_VERSION, CODEX_CONTRACT_VERSION),
        column=None,
        defined_in="yuno.modules.provider.{claude,codex}",
    ),
    VersionedArtifact(
        name="derived-state rules",
        source=VersionSource.BUILD,
        identifiers=(FIXTURE_DERIVATION_VERSION,),
        column=None,
        defined_in="yuno.modules.evidence_evaluation.domain.FIXTURE_DERIVATION_VERSION",
    ),
    VersionedArtifact(
        name="generated artifacts",
        source=VersionSource.BUILD,
        identifiers=(GENERATION_SCHEMA_VERSION,),
        column=None,
        defined_in="yuno.modules.learning_content.domain.GENERATION_SCHEMA_VERSION",
    ),
    VersionedArtifact(
        name="job payload/result",
        source=VersionSource.BUILD,
        identifiers=(JOB_PAYLOAD_SCHEMA_VERSION,),
        column=None,
        defined_in="yuno.shared.application.jobs.JOB_PAYLOAD_SCHEMA_VERSION",
    ),
    VersionedArtifact(
        name="FTS projection",
        source=VersionSource.BUILD,
        identifiers=(PROJECTION_VERSION,),
        column=None,
        defined_in="yuno.modules.search.repository.PROJECTION_VERSION",
    ),
    VersionedArtifact(
        name="export format",
        source=VersionSource.BUILD,
        identifiers=(f"{EXPORT_FORMAT}/{EXPORT_VERSION}",),
        column=None,
        defined_in="yuno.modules.settings_data.service.{EXPORT_FORMAT,EXPORT_VERSION}",
    ),
)
