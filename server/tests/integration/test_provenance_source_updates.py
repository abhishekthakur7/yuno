"""Integration coverage for `SqlAlchemySourceRepository.update_source`
(IDK-003 section 12 item 2 / IDK-503 finding B7): the write primitive that
transitions `sources.availability_status`, `withdrawal_reason`, and
`superseded_by_source_id`.

Every assertion here runs against a real, migrated SQLite database so the
constraints `4cb74877e4ba_source_license_withdrawal_supersession.py` added --
`withdrawal_reason_valid`, `withdrawal_reason_required_iff_withdrawn`, and
`fk_sources_superseded_by_source_owner` -- are exercised for real, not just
asserted about. `update_source` itself implements no state-machine rules (no
3-failure threshold, no terminal-`withdrawn` check, no purge trigger); those
belong to the service layer. This file only proves the write primitive
persists what it's given and that the database-level guarantees hold.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from tests.integration.test_owner_isolation import _insert_second_owner
from yuno.modules.provenance.domain import (
    Source,
    SourceAvailability,
    SourceWithdrawalReason,
)
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.ids import new_id

_ALL_WITHDRAWAL_REASONS = tuple(SourceWithdrawalReason)


def _ts(day: int) -> str:
    return f"2026-08-{day:02d}T00:00:00.000000Z"


def _source(
    owner_id: str,
    *,
    suffix: str,
    availability: SourceAvailability = SourceAvailability.AVAILABLE,
    withdrawal_reason: SourceWithdrawalReason | None = None,
    superseded_by_source_id: str | None = None,
    timestamp: str = _ts(1),
) -> Source:
    return Source(
        id=new_id(),
        owner_id=owner_id,
        origin="fixture",
        source_type="documentation",
        title=f"Source {suffix}",
        publisher="Fixture publisher",
        canonical_url=f"https://example.invalid/{suffix}",
        license_status="approved-open-license",
        availability_status=availability,
        withdrawal_reason=withdrawal_reason,
        superseded_by_source_id=superseded_by_source_id,
        created_at=timestamp,
        updated_at=timestamp,
    )


def test_available_to_unavailable_and_back_bumps_updated_at(
    uow_factory: UnitOfWorkFactory,
) -> None:
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Owner")
        source = _source(owner.id, suffix="round-trip")
        uow.provenance.add_source(source)
        uow.commit()

    with uow_factory() as uow:
        made_unavailable = uow.provenance.update_source(
            owner.id,
            source.id,
            _ts(2),
            {"availability_status": SourceAvailability.UNAVAILABLE},
        )
        uow.commit()
    assert made_unavailable is not None
    assert made_unavailable.availability_status is SourceAvailability.UNAVAILABLE
    assert made_unavailable.updated_at == _ts(2)
    assert made_unavailable.updated_at != source.updated_at
    assert made_unavailable.created_at == source.created_at

    with uow_factory() as uow:
        made_available_again = uow.provenance.update_source(
            owner.id,
            source.id,
            _ts(3),
            {"availability_status": SourceAvailability.AVAILABLE},
        )
        uow.commit()
    assert made_available_again is not None
    assert made_available_again.availability_status is SourceAvailability.AVAILABLE
    assert made_available_again.updated_at == _ts(3)


@pytest.mark.parametrize("reason", _ALL_WITHDRAWAL_REASONS)
def test_withdrawn_with_a_valid_reason_succeeds_for_every_section_11_literal(
    uow_factory: UnitOfWorkFactory, reason: SourceWithdrawalReason
) -> None:
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Owner")
        source = _source(owner.id, suffix=f"withdraw-{reason.value}")
        uow.provenance.add_source(source)
        uow.commit()

    with uow_factory() as uow:
        withdrawn = uow.provenance.update_source(
            owner.id,
            source.id,
            _ts(2),
            {
                "availability_status": SourceAvailability.WITHDRAWN,
                "withdrawal_reason": reason,
            },
        )
        uow.commit()

    assert withdrawn is not None
    assert withdrawn.availability_status is SourceAvailability.WITHDRAWN
    assert withdrawn.withdrawal_reason is reason
    assert withdrawn.updated_at == _ts(2)


def test_withdrawn_with_a_null_reason_is_rejected_by_the_database(
    uow_factory: UnitOfWorkFactory,
) -> None:
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Owner")
        source = _source(owner.id, suffix="withdraw-null-reason")
        uow.provenance.add_source(source)
        uow.commit()

    with pytest.raises(IntegrityError), uow_factory() as uow:
        uow.provenance.update_source(
            owner.id,
            source.id,
            _ts(2),
            {"availability_status": SourceAvailability.WITHDRAWN},
        )


def test_non_withdrawn_status_with_a_reason_is_rejected_by_the_database(
    uow_factory: UnitOfWorkFactory,
) -> None:
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Owner")
        source = _source(owner.id, suffix="non-withdrawn-with-reason")
        uow.provenance.add_source(source)
        uow.commit()

    with pytest.raises(IntegrityError), uow_factory() as uow:
        uow.provenance.update_source(
            owner.id,
            source.id,
            _ts(2),
            {
                "availability_status": SourceAvailability.UNAVAILABLE,
                "withdrawal_reason": SourceWithdrawalReason.PUBLISHER_RETRACTED,
            },
        )


def test_invalid_withdrawal_reason_literal_is_rejected_by_the_database(
    uow_factory: UnitOfWorkFactory,
) -> None:
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Owner")
        source = _source(owner.id, suffix="invalid-reason-literal")
        uow.provenance.add_source(source)
        uow.commit()

    with pytest.raises(IntegrityError), uow_factory() as uow:
        uow.provenance.update_source(
            owner.id,
            source.id,
            _ts(2),
            {
                "availability_status": SourceAvailability.WITHDRAWN,
                "withdrawal_reason": "not-a-real-reason",
            },
        )


def test_superseded_by_source_id_enforces_same_owner_via_composite_fk(
    uow_factory: UnitOfWorkFactory, database_url: str
) -> None:
    with uow_factory() as uow:
        owner_a = uow.owners.create_local_owner("Owner A")
        original = _source(owner_a.id, suffix="superseded-original")
        replacement = _source(owner_a.id, suffix="superseded-replacement")
        uow.provenance.add_source(original)
        uow.provenance.add_source(replacement)
        uow.commit()

    owner_b_id = new_id()
    _insert_second_owner(database_url, owner_id=owner_b_id, display_name="Owner B")
    with uow_factory() as uow:
        foreign_source = _source(owner_b_id, suffix="superseded-foreign")
        uow.provenance.add_source(foreign_source)
        uow.commit()

    with uow_factory() as uow:
        updated = uow.provenance.update_source(
            owner_a.id,
            original.id,
            _ts(2),
            {"superseded_by_source_id": replacement.id},
        )
        uow.commit()
    assert updated is not None
    assert updated.superseded_by_source_id == replacement.id

    with pytest.raises(IntegrityError), uow_factory() as uow:
        uow.provenance.update_source(
            owner_a.id,
            original.id,
            _ts(3),
            {"superseded_by_source_id": foreign_source.id},
        )


def test_update_source_for_unknown_id_or_wrong_owner_returns_none_and_writes_nothing(
    uow_factory: UnitOfWorkFactory, database_url: str
) -> None:
    with uow_factory() as uow:
        owner_a = uow.owners.create_local_owner("Owner A")
        source = _source(owner_a.id, suffix="no-such-row")
        uow.provenance.add_source(source)
        uow.commit()

    owner_b_id = new_id()
    _insert_second_owner(database_url, owner_id=owner_b_id, display_name="Owner B")

    with uow_factory() as uow:
        missing = uow.provenance.update_source(
            owner_a.id,
            new_id(),
            _ts(2),
            {"availability_status": SourceAvailability.UNAVAILABLE},
        )
        uow.commit()
    assert missing is None

    with uow_factory() as uow:
        wrong_owner = uow.provenance.update_source(
            owner_b_id,
            source.id,
            _ts(2),
            {"availability_status": SourceAvailability.UNAVAILABLE},
        )
        uow.commit()
    assert wrong_owner is None

    with uow_factory() as uow:
        unchanged = uow.provenance.get_source(owner_a.id, source.id)
    assert unchanged is not None
    assert unchanged.availability_status is SourceAvailability.AVAILABLE
    assert unchanged.updated_at == source.updated_at
