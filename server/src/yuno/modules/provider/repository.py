"""Owner-scoped SQLAlchemy provider repository."""

from __future__ import annotations

import json
from collections.abc import Sequence

from sqlalchemy import select

from yuno.modules.provider.domain import NetworkDisclosure, SchemaQuarantine
from yuno.modules.provider.models import (
    NetworkDisclosureRow,
    ProviderRequestRow,
    SchemaQuarantineRow,
)
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.errors import ConflictError
from yuno.shared.infrastructure.repository import SqlAlchemyRepository


class SqlAlchemyProviderRepository(SqlAlchemyRepository):
    def list_disclosures(self, owner_id: str) -> Sequence[NetworkDisclosure]:
        rows = self._session.scalars(
            select(NetworkDisclosureRow)
            .where(NetworkDisclosureRow.owner_id == owner_id)
            .order_by(
                NetworkDisclosureRow.category, NetworkDisclosureRow.disclosure_version
            )
        ).all()
        return tuple(_disclosure(row) for row in rows)

    def get_active_disclosure(
        self, owner_id: str, category: str, disclosure_version: str
    ) -> NetworkDisclosure | None:
        row = self._session.scalars(
            select(NetworkDisclosureRow).where(
                NetworkDisclosureRow.owner_id == owner_id,
                NetworkDisclosureRow.category == category,
                NetworkDisclosureRow.disclosure_version == disclosure_version,
                NetworkDisclosureRow.revoked_at.is_(None),
            )
        ).one_or_none()
        return _disclosure(row) if row else None

    def accept_disclosure(self, disclosure: NetworkDisclosure) -> NetworkDisclosure:
        row = self._session.scalars(
            select(NetworkDisclosureRow).where(
                NetworkDisclosureRow.owner_id == disclosure.owner_id,
                NetworkDisclosureRow.category == disclosure.category,
                NetworkDisclosureRow.disclosure_version
                == disclosure.disclosure_version,
            )
        ).one_or_none()
        values = {
            "operation": disclosure.operation,
            "destination": disclosure.destination,
            "data_categories_json": json.dumps(disclosure.data_categories),
            "accepted_at": disclosure.accepted_at,
            "revoked_at": None,
        }
        if row is None:
            row = NetworkDisclosureRow(
                id=disclosure.id,
                owner_id=disclosure.owner_id,
                category=disclosure.category,
                disclosure_version=disclosure.disclosure_version,
                **values,
            )
            self._session.add(row)
        else:
            same_content = (
                row.operation == disclosure.operation
                and row.destination == disclosure.destination
                and tuple(json.loads(row.data_categories_json))
                == disclosure.data_categories
            )
            if not same_content:
                raise ConflictError(
                    "A disclosure version is immutable; publish and accept a new version."
                )
            if row.revoked_at is not None:
                row.accepted_at = disclosure.accepted_at
                row.revoked_at = None
                self._session.flush()
            return _disclosure(row)
        self._session.flush()
        return _disclosure(row)

    def revoke_disclosure(
        self, owner_id: str, category: str, disclosure_version: str, revoked_at: str
    ) -> NetworkDisclosure | None:
        row = self._session.scalars(
            select(NetworkDisclosureRow).where(
                NetworkDisclosureRow.owner_id == owner_id,
                NetworkDisclosureRow.category == category,
                NetworkDisclosureRow.disclosure_version == disclosure_version,
            )
        ).one_or_none()
        if row is None:
            return None
        row.revoked_at = revoked_at
        self._session.flush()
        return _disclosure(row)

    def create_request(self, **values: object) -> str:
        row = ProviderRequestRow(**values)
        self._session.add(row)
        self._session.flush()
        return row.id

    def mark_spawned(
        self, request_id: str, pid: int, pgid: int, process_identity: str
    ) -> None:
        row = self._session.get(ProviderRequestRow, request_id)
        if row is None:
            raise RuntimeError(
                "Provider request disappeared before spawn was recorded."
            )
        row.pid = pid
        row.pgid = pgid
        row.process_identity = process_identity
        row.lifecycle = "running"
        row.started_at = now_text(SystemClock())
        self._session.flush()

    def finish_request(
        self, request_id: str, lifecycle: str, diagnostic: str | None
    ) -> None:
        row = self._session.get(ProviderRequestRow, request_id)
        if row is None:
            raise RuntimeError("Provider request disappeared before completion.")
        row.lifecycle = lifecycle
        row.diagnostic_classification = diagnostic
        row.completed_at = now_text(SystemClock())
        self._session.flush()

    def add_quarantine(self, quarantine: SchemaQuarantine) -> SchemaQuarantine:
        self._session.add(
            SchemaQuarantineRow(
                id=quarantine.id,
                owner_id=quarantine.owner_id,
                provider_request_id=quarantine.provider_request_id,
                job_id=quarantine.job_id,
                raw_output_ref=quarantine.raw_output_ref,
                raw_output_hash=quarantine.raw_output_hash,
                expected_schema_version=quarantine.expected_schema_version,
                validation_errors_json=json.dumps(quarantine.validation_errors),
                created_at=quarantine.created_at,
            )
        )
        self._session.flush()
        return quarantine

    def get_quarantine(
        self, owner_id: str, quarantine_id: str
    ) -> SchemaQuarantine | None:
        row = self._session.scalars(
            select(SchemaQuarantineRow).where(
                SchemaQuarantineRow.owner_id == owner_id,
                SchemaQuarantineRow.id == quarantine_id,
            )
        ).one_or_none()
        return _quarantine(row) if row else None


def _disclosure(row: NetworkDisclosureRow) -> NetworkDisclosure:
    return NetworkDisclosure(
        id=row.id,
        owner_id=row.owner_id,
        category=row.category,
        operation=row.operation,
        destination=row.destination,
        data_categories=tuple(json.loads(row.data_categories_json)),
        disclosure_version=row.disclosure_version,
        accepted_at=row.accepted_at,
        revoked_at=row.revoked_at,
    )


def _quarantine(row: SchemaQuarantineRow) -> SchemaQuarantine:
    return SchemaQuarantine(
        id=row.id,
        owner_id=row.owner_id,
        provider_request_id=row.provider_request_id,
        job_id=row.job_id,
        raw_output_ref=row.raw_output_ref,
        raw_output_hash=row.raw_output_hash,
        expected_schema_version=row.expected_schema_version,
        validation_errors=tuple(json.loads(row.validation_errors_json)),
        created_at=row.created_at,
    )
