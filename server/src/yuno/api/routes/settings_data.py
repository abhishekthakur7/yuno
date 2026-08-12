"""Durable owner settings HTTP API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from yuno.api.contracts import (
    OwnerSettingsPatchRequest,
    OwnerSettingsResponse,
)
from yuno.api.dependencies import (
    get_clock,
    get_owner_id,
    get_unit_of_work,
    if_match,
    parse_if_match,
)
from yuno.modules.settings_data.domain import OwnerSettings
from yuno.modules.settings_data.ports import SettingsUnitOfWork
from yuno.modules.settings_data.service import (
    get_owner_settings,
    patch_owner_settings,
)
from yuno.shared.domain.clock import Clock

router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=OwnerSettingsResponse)
def get_settings(
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[SettingsUnitOfWork, Depends(get_unit_of_work)],
) -> OwnerSettingsResponse:
    return _response(get_owner_settings(uow, owner_id))


@router.patch("/settings", response_model=OwnerSettingsResponse)
def update_settings(
    body: OwnerSettingsPatchRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[SettingsUnitOfWork, Depends(get_unit_of_work)],
    match: Annotated[str, Depends(if_match)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> OwnerSettingsResponse:
    updated = patch_owner_settings(
        uow,
        owner_id,
        parse_if_match(match),
        body.progress_display,
        clock=clock,
    )
    uow.commit()
    return _response(updated)


def _response(settings: OwnerSettings) -> OwnerSettingsResponse:
    return OwnerSettingsResponse(
        progress_display=settings.progress_display,
        row_version=settings.row_version,
    )
