"""The D1 offline publisher: spec §6.1 steps 1-7, IDK-102's mechanism.

`publish_canonical_graph` is deliberately *not* an HTTP application
service (D1 forbids in-app authoring/publication -- spec §5.1's API
surface for `canonical` is read-only `GET /api/v1/canonical/versions[/…]`).
It never imports `yuno.unit_of_work` or FastAPI: it depends only on the
`UnitOfWork` shape it needs (`_PublisherUnitOfWork` below, mirroring
`yuno.modules.identity.service`'s `_EnsureLocalOwnerUnitOfWork`), and the
offline CLI (`scripts/publish_canonical.py`) wires the concrete SQLAlchemy
adapter in. Depending on `identity` and `audit` here is the same
cross-cutting edge `ensure_local_owner` takes on `audit`.

Order of operations: `require_single_head(engine)` before any session is
opened; `validate_manifest(manifest)`, which reports every violation, not
just the first; inside the UoW, the `Role.DESIGNATED_EDITORIAL_APPROVER`
grant check before any write; then `validate_basis_ref(basis_ref, ...)`
(IDK-002 §4), also before any write -- it needs
`uow.canonical.list_published_versions()` for its `review_kind`/
`diff_against_version_label` cross-check, which is why it cannot run
alongside `validate_manifest` outside the UoW; pre-write
`version_label`/`manifest_hash` conflict checks (spec §4.3's UNIQUE
constraints raised as `ConflictError`
instead of a raw `IntegrityError`); one insert per topic identity/topic/
relation/content revision; the `CanonicalGraphVersion` row inserted
directly as `PUBLISHED` (see `_build_version`); the `EditorialApproval`
row inserted last; one audit event; `uow.commit()`. All in one
`with uow_factory() as uow:` block, so it is one SQLite transaction --
any exception before `commit()` rolls the whole thing back
(`test_canonical_publish.py`'s mid-transaction-failure test).

Mutation/deletion of an already-published version is refused elsewhere,
not by this function: `CanonicalGraphRepository` (`ports.py`) exposes no
update/delete method, and the migration's SQLite triggers reject any
UPDATE/DELETE on a row belonging to a `published` version
(`test_canonical_immutability.py`). This function's own share of that
guarantee is refusing to *re-publish* under an already-used
`version_label`/`manifest_hash` -- a correction is always a new version.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Protocol

from sqlalchemy import Engine

from yuno.modules.audit.domain import AuditEvent
from yuno.modules.audit.ports import AuditRepository
from yuno.modules.canonical.domain import (
    CanonicalGraphManifest,
    CanonicalGraphVersion,
    CanonicalVersionStatus,
    EditorialApproval,
    TopicIdentity,
)
from yuno.modules.canonical.ports import CanonicalUnitOfWork
from yuno.modules.canonical.validation import validate_basis_ref, validate_manifest
from yuno.modules.identity.domain import Role, RolePolicy
from yuno.modules.identity.ports import OwnerRepository
from yuno.shared.domain.clock import Clock, SystemClock, now_text
from yuno.shared.domain.errors import ConflictError, DomainValidationError
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id
from yuno.shared.infrastructure.alembic_guard import require_single_head


class _PublisherUnitOfWork(CanonicalUnitOfWork, Protocol):
    """`canonical`'s own repository plus the cross-cutting `identity`
    (role check) and `audit` (publish event) repositories this function
    needs. Mirrors
    `yuno.modules.identity.service._EnsureLocalOwnerUnitOfWork`.
    """

    owners: OwnerRepository
    audit: AuditRepository


class _PublisherUnitOfWorkFactory(Protocol):
    """A zero-arg callable returning a `_PublisherUnitOfWork`, narrowed
    from `UnitOfWorkFactory` (`yuno.shared.application.unit_of_work`) so
    the body below can use `uow.owners`/`uow.canonical`/`uow.audit`
    directly instead of casting.
    """

    def __call__(self) -> _PublisherUnitOfWork: ...


def publish_canonical_graph(
    *,
    engine: Engine,
    uow_factory: _PublisherUnitOfWorkFactory,
    manifest: CanonicalGraphManifest,
    actor_owner_id: str,
    basis_ref: str,
    topic_identity_slugs: Mapping[str, str] | None = None,
    clock: Clock | None = None,
) -> CanonicalGraphVersion:
    """Run spec §6.1 steps 1-7 and return the newly published version.

    `uow_factory()` must return a `_PublisherUnitOfWork`; the concrete
    `SqlAlchemyUnitOfWork` (`yuno.unit_of_work`) satisfies this
    structurally.

    `topic_identity_slugs` maps `stable_id -> stable_slug` for any topic
    that needs a brand-new `topic_identities` row (a `stable_id` already
    known from a prior version reuses its existing identity/slug). No
    manifest-side field carries this slug (`CanonicalGraphManifest`'s
    `Topic` has none -- spec §4.3 doesn't distinguish it from `stable_id`),
    so a caller supplies it out of band. A `stable_id` missing from the
    mapping falls back to its own text as the slug.

    Raises `UnavailableError`, `DomainValidationError`, `RoleNotGrantedError`
    or `ConflictError` (reused label/hash) -- always before `uow.commit()`,
    so a caller catching any `YunoError` here knows nothing was written.
    """
    require_single_head(engine)

    validation_result = validate_manifest(manifest)
    if not validation_result.is_valid:
        raise DomainValidationError(
            f"Canonical graph manifest {manifest.version_label!r} failed validation with "
            f"{len(validation_result.violations)} violation(s).",
            field_errors=[
                {
                    "code": violation.code.value,
                    "message": violation.message,
                    "topic_stable_id": violation.topic_stable_id,
                    "relation_id": violation.relation_id,
                }
                for violation in validation_result.violations
            ],
        )

    resolved_clock = clock if clock is not None else SystemClock()
    resolved_slugs = topic_identity_slugs if topic_identity_slugs is not None else {}

    with uow_factory() as uow:
        grants = uow.owners.grants(actor_owner_id)
        RolePolicy.require(grants, Role.DESIGNATED_EDITORIAL_APPROVER)

        previous = uow.canonical.list_published_versions()
        basis_ref_result = validate_basis_ref(
            basis_ref,
            manifest_hash=manifest.manifest_hash,
            published_version_labels=[version.version_label for version in previous],
        )
        if not basis_ref_result.is_valid:
            raise DomainValidationError(
                f"Editorial approval basis_ref for canonical graph manifest "
                f"{manifest.version_label!r} failed validation with "
                f"{len(basis_ref_result.violations)} violation(s).",
                field_errors=[
                    {
                        "code": violation.code.value,
                        "message": violation.message,
                        "topic_stable_id": violation.topic_stable_id,
                        "relation_id": violation.relation_id,
                    }
                    for violation in basis_ref_result.violations
                ],
            )

        if uow.canonical.version_label_exists(manifest.version_label):
            raise ConflictError(
                f"Canonical graph version_label {manifest.version_label!r} has already been "
                "published; corrections require a new version_label."
            )
        if uow.canonical.manifest_hash_exists(manifest.manifest_hash):
            raise ConflictError(
                f"Canonical graph manifest_hash {manifest.manifest_hash!r} has already been "
                "published as a version."
            )

        published_at = now_text(resolved_clock)
        version = _build_version(
            manifest, actor_owner_id=actor_owner_id, published_at=published_at
        )
        if previous:
            version = replace(version, supersedes_version_id=previous[0].id)
        uow.canonical.create_version(version)

        for topic in manifest.topics:
            if not uow.canonical.topic_identity_exists(topic.stable_id):
                uow.canonical.create_topic_identity(
                    TopicIdentity(
                        stable_id=topic.stable_id,
                        stable_slug=resolved_slugs.get(
                            topic.stable_id, topic.stable_id
                        ),
                        created_at=published_at,
                        retired_at=None,
                    )
                )
            uow.canonical.add_topic(replace(topic, graph_version_id=version.id))

        for relation in manifest.relations:
            uow.canonical.add_relation(replace(relation, graph_version_id=version.id))

        for revision in manifest.content_revisions:
            # `creator_owner_id`/`created_at` only exist once this
            # transaction's own owner/version rows are real; a manifest's
            # `ContentRevision` carries placeholders for both until now.
            uow.canonical.add_content_revision(
                replace(
                    revision,
                    graph_version_id=version.id,
                    creator_owner_id=actor_owner_id,
                    created_at=published_at,
                )
            )

        approval = EditorialApproval(
            id=new_id(),
            graph_version_id=version.id,
            approver_owner_id=actor_owner_id,
            approver_role=Role.DESIGNATED_EDITORIAL_APPROVER.value,
            basis_ref=basis_ref,
            approved_at=published_at,
        )
        uow.canonical.record_approval(approval)

        uow.audit.append(
            AuditEvent(
                id=new_id(),
                owner_id=actor_owner_id,
                goal_id=None,
                # Recorded as editorial, not learner (spec §6.1 step 3) --
                # the grant just verified above, not the local owner's
                # other role.
                actor_role=Role.DESIGNATED_EDITORIAL_APPROVER.value,
                entity_type="canonical_graph_version",
                entity_id=version.id,
                action="canonical_graph_version_published",
                before_hash=None,
                after_hash=hash_payload(
                    {
                        "version_label": version.version_label,
                        "manifest_hash": version.manifest_hash,
                        "topic_count": len(manifest.topics),
                        "relation_count": len(manifest.relations),
                        "content_revision_count": len(manifest.content_revisions),
                    }
                ),
                reason=basis_ref,
                request_id=None,
                correlation_id=None,
                occurred_at=published_at,
            )
        )

        uow.commit()

    return version


def _build_version(
    manifest: CanonicalGraphManifest, *, actor_owner_id: str, published_at: str
) -> CanonicalGraphVersion:
    """Build the `CanonicalGraphVersion` to insert, already `PUBLISHED`.

    Not inserted as `PENDING_APPROVAL` and later updated: `ports.py`
    exposes no update method on any of the six tables, by design. Nothing
    outside this transaction can observe the row before commit, and the
    `EditorialApproval` row inserted right after is what actually makes a
    version readable (every read in `ports.py` is approval-gated) -- so
    inserting already-`PUBLISHED` is equivalent to insert-as-draft-then-
    update without needing a mutation method the immutability guarantee
    would rather not expose.
    """
    return CanonicalGraphVersion(
        id=new_id(),
        version_label=manifest.version_label,
        manifest_version=manifest.manifest_version,
        manifest_hash=manifest.manifest_hash,
        status=CanonicalVersionStatus.PUBLISHED,
        creator_owner_id=actor_owner_id,
        created_at=published_at,
        published_at=published_at,
        supersedes_version_id=None,
    )
