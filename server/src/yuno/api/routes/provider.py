"""Provider capability and versioned disclosure API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from yuno.api.contracts import (
    DisclosureAcceptRequest,
    DisclosureResponse,
    ProviderCapabilityResponse,
)
from yuno.api.dependencies import get_clock, get_owner_id, get_unit_of_work
from yuno.modules.provider.ports import ProviderUnitOfWork
from yuno.modules.provider.service import accept_disclosure, revoke_disclosure
from yuno.shared.domain.clock import Clock
from yuno.shared.domain.errors import DomainValidationError

router = APIRouter(tags=["provider"])

_DISCLOSURES = {
    "provider-generation": {
        "operation": "Provider-backed generation and evaluation",
        "destination": "Selected local CLI provider and its network destination",
        "data_categories": (
            "required learner context",
            "selected evidence and answers",
            "approved import excerpts",
            "canonical and source context",
            "requested output schema",
            "operation metadata",
        ),
        "disclosure_version": "provider-network-v1",
    },
    "source-retrieval": {
        "operation": "Explicit authoritative source retrieval",
        "destination": "The selected source's approved canonical URL",
        "data_categories": ("source URL", "operation metadata"),
        "disclosure_version": "source-network-v1",
    },
}


@router.get("/disclosures", response_model=list[DisclosureResponse])
def disclosures(
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[ProviderUnitOfWork, Depends(get_unit_of_work)],
) -> list[DisclosureResponse]:
    accepted = {
        (value.category, value.disclosure_version): value
        for value in uow.provider.list_disclosures(owner_id)
    }
    return [
        _response(accepted[(category, definition["disclosure_version"])])
        if (category, definition["disclosure_version"]) in accepted
        else DisclosureResponse(
            id=None,
            category=category,
            operation=definition["operation"],
            destination=definition["destination"],
            data_categories=list(definition["data_categories"]),
            disclosure_version=definition["disclosure_version"],
            accepted_at=None,
            revoked_at=None,
        )
        for category, definition in _DISCLOSURES.items()
    ]


@router.post("/disclosures/{category}/accept", response_model=DisclosureResponse)
def accept(
    category: str,
    body: DisclosureAcceptRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[ProviderUnitOfWork, Depends(get_unit_of_work)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> DisclosureResponse:
    definition = _DISCLOSURES.get(category)
    if (
        definition is None
        or body.disclosure_version != definition["disclosure_version"]
    ):
        raise DomainValidationError(
            "The disclosure category or version is not current."
        )
    result = accept_disclosure(
        uow,
        owner_id,
        category=category,
        operation=str(definition["operation"]),
        destination=str(definition["destination"]),
        data_categories=definition["data_categories"],
        disclosure_version=str(definition["disclosure_version"]),
        clock=clock,
    )
    uow.commit()
    return _response(result)


@router.post("/disclosures/{category}/revoke", response_model=DisclosureResponse)
def revoke(
    category: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[ProviderUnitOfWork, Depends(get_unit_of_work)],
    clock: Annotated[Clock, Depends(get_clock)],
    disclosure_version: Annotated[str, Query(min_length=1)],
) -> DisclosureResponse:
    result = revoke_disclosure(uow, owner_id, category, disclosure_version, clock=clock)
    uow.commit()
    return _response(result)


@router.get("/provider-capabilities", response_model=list[ProviderCapabilityResponse])
def capabilities(
    request: Request, refresh: Annotated[bool, Query()] = False
) -> list[ProviderCapabilityResponse]:
    values = (
        request.app.state.provider_registry.refresh()
        if refresh
        else request.app.state.provider_registry.capabilities()
    )
    return [
        ProviderCapabilityResponse(
            provider=value.provider,
            state=value.state,
            reason=value.reason,
            recovery_action=value.recovery_action,
            model=value.model,
            adapter_version=value.adapter_version,
            contract_version=value.contract_version,
        )
        for value in values
    ]


def _response(value) -> DisclosureResponse:
    return DisclosureResponse(
        id=value.id,
        category=value.category,
        operation=value.operation,
        destination=value.destination,
        data_categories=list(value.data_categories),
        disclosure_version=value.disclosure_version,
        accepted_at=value.accepted_at,
        revoked_at=value.revoked_at,
    )
