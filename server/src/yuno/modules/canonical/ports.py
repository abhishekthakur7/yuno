"""`canonical` module ports (spec §3.3: `CanonicalGraphRepository`).

Protocols only -- no implementation lives here. `yuno.modules.canonical.repository`
provides the SQLAlchemy-backed adapter that satisfies `CanonicalGraphRepository`
structurally (see `yuno.modules.identity.ports`'s docstring for the same
pattern this mirrors).

Every write method here is a single-table insert, deliberately: spec
§6.1 step 4's "insert a new version and all dependent material, insert
`EditorialApproval` last, commit" is an application-service concern
(`PublicationService`), not a repository one -- the repository exposes
the individual inserts the service sequences inside one
`CanonicalUnitOfWork`, so the atomicity/ordering guarantee lives in one
place. No method here updates or deletes a row belonging to an approved
version; the migration's SQLite triggers are the enforcement backstop
(spec §4.3), and this protocol offers no such method to call in the
first place (matching `AuditRepository`'s "no update/delete" precedent).

Read methods are named so the "every read path gated on approval-record
existence" invariant is obvious at the call site:
`get_published_version`/`list_published_versions`/`get_published_topics`
return only material belonging to a version with an `EditorialApproval`
row -- a half-seeded version (no approval) is invisible through all of
them, by construction of the adapter (join or gate on
`editorial_approvals`, not a loose `status` filter).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from yuno.modules.canonical.domain import (
    CanonicalGraphVersion,
    ContentRevision,
    EditorialApproval,
    Topic,
    TopicIdentity,
    TopicRelation,
)
from yuno.shared.application.unit_of_work import UnitOfWork


class CanonicalGraphRepository(Protocol):
    # --- Writes: one insert per method; a caller sequences and commits
    # these inside one `CanonicalUnitOfWork` (spec §3.4's atomic-UoW rule
    # for D1 publication). None of these updates/deletes an existing row.

    def create_topic_identity(self, identity: TopicIdentity) -> None: ...

    def create_version(self, version: CanonicalGraphVersion) -> None: ...

    def add_topic(self, topic: Topic) -> None: ...

    def add_relation(self, relation: TopicRelation) -> None: ...

    def add_content_revision(self, revision: ContentRevision) -> None: ...

    def record_approval(self, approval: EditorialApproval) -> None: ...

    # --- Reads: approval-gated. See module docstring.

    def get_published_version(self, version_id: str) -> CanonicalGraphVersion | None: ...

    def list_published_versions(self) -> Sequence[CanonicalGraphVersion]: ...

    def get_published_topics(self, version_id: str) -> Sequence[Topic]: ...

    def get_published_relations(self, version_id: str) -> Sequence[TopicRelation]: ...

    # --- Publish-time lookups: pre-write checks the publisher needs before
    # opening (or while inside) the write transaction -- e.g. rejecting a
    # reused `version_label`/`manifest_hash` (spec §4.3's UNIQUE
    # constraints) with a typed error before attempting the insert.

    def version_label_exists(self, version_label: str) -> bool: ...

    def manifest_hash_exists(self, manifest_hash: str) -> bool: ...

    def topic_identity_exists(self, stable_id: str) -> bool: ...


class CanonicalUnitOfWork(UnitOfWork, Protocol):
    """A `UnitOfWork` that also carries the `canonical` module's
    repository. See `yuno.modules.identity.ports.IdentityUnitOfWork`'s
    docstring for why this exists as its own protocol rather than a
    concrete dependency.
    """

    canonical: CanonicalGraphRepository
