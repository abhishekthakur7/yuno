"""Owner-scoped SQLAlchemy settings repository."""

from __future__ import annotations

from sqlalchemy import update

from yuno.modules.settings_data.domain import OwnerSettings, ProgressDisplay
from yuno.modules.settings_data.models import OwnerSettingsRow
from yuno.shared.infrastructure.repository import (
    SqlAlchemyRepository,
    owner_scoped_select,
)


class SqlAlchemySettingsRepository(SqlAlchemyRepository):
    def get(self, owner_id: str) -> OwnerSettings | None:
        row = self._session.scalars(
            owner_scoped_select(OwnerSettingsRow, owner_id)
        ).one_or_none()
        return _settings(row) if row is not None else None

    def create(self, settings: OwnerSettings) -> OwnerSettings:
        self._session.add(
            OwnerSettingsRow(
                owner_id=settings.owner_id,
                progress_display=settings.progress_display.value,
                row_version=settings.row_version,
                updated_at=settings.updated_at,
            )
        )
        self._session.flush()
        created = self.get(settings.owner_id)
        assert created is not None
        return created

    def update(
        self,
        owner_id: str,
        expected_version: int,
        progress_display: ProgressDisplay,
        *,
        updated_at: str,
    ) -> OwnerSettings | None:
        result = self._session.execute(
            update(OwnerSettingsRow)
            .where(
                OwnerSettingsRow.owner_id == owner_id,
                OwnerSettingsRow.row_version == expected_version,
            )
            .values(
                progress_display=progress_display.value,
                row_version=expected_version + 1,
                updated_at=updated_at,
            )
        )
        if result.rowcount != 1:
            return None
        self._session.flush()
        return self.get(owner_id)


def _settings(row: OwnerSettingsRow) -> OwnerSettings:
    return OwnerSettings(
        owner_id=row.owner_id,
        progress_display=ProgressDisplay(row.progress_display),
        row_version=row.row_version,
        updated_at=row.updated_at,
    )
