"""API composition helpers for owner-selected provider operations."""

from __future__ import annotations

from dataclasses import dataclass, replace

from yuno.modules.provider.domain import NetworkDisclosure, ProviderName
from yuno.modules.provider.registry import ProviderRegistry
from yuno.modules.provider.service import require_disclosure
from yuno.shared.domain.errors import UnavailableError


@dataclass(frozen=True)
class ProviderOperation:
    provider: ProviderName
    disclosure: NetworkDisclosure


PROVIDER_JOB_KINDS = frozenset(
    {
        "generate_topic_content",
        "assess_evidence",
        "reevaluate_assessment",
        "evaluate_practice_answer",
        "review_hands_on_artifact",
        "generate_mock_next_turn",
        "evaluate_mock_final",
        "tutor_turn",
    }
)


class ProviderAwareJobDispatcher:
    """Pin the configured owner selection before durable provider enqueue."""

    def __init__(self, dispatcher, uow_factory, registry: ProviderRegistry) -> None:
        self._dispatcher = dispatcher
        self._uow_factory = uow_factory
        self._registry = registry

    def enqueue(self, request):
        if request.kind not in PROVIDER_JOB_KINDS:
            return self._dispatcher.enqueue(request)
        if not request.disclosure_ref:
            raise RuntimeError("Provider-backed jobs require a disclosure reference.")
        if not request.provider_name:
            raise RuntimeError("Provider-backed jobs require an authorization pin.")
        with self._uow_factory() as uow:
            provider = require_selected_provider(uow, request.owner_id, self._registry)
        if request.provider_name != provider.value:
            raise UnavailableError(
                "The selected provider changed before enqueue.",
                recovery_action="Retry the action with the current provider selection.",
            )
        return self._dispatcher.enqueue(replace(request, provider_name=provider.value))

    def reserve(self, uow, request):
        if request.kind not in PROVIDER_JOB_KINDS:
            return self._dispatcher.reserve(uow.session, request)
        if not request.disclosure_ref or not request.provider_name:
            raise RuntimeError(
                "Provider-backed job reservations require disclosure and provider pins."
            )
        provider = require_selected_provider(uow, request.owner_id, self._registry)
        if request.provider_name != provider.value:
            raise UnavailableError(
                "The selected provider changed before reservation.",
                recovery_action="Retry with the current provider selection.",
            )
        return self._dispatcher.reserve(uow.session, request)

    def authorize(self, uow, owner_id: str) -> ProviderOperation:
        """Validate the disclosure and selected cached capability before writes."""
        return require_provider_operation(uow, owner_id, self._registry)

    def retry(
        self,
        owner_id: str,
        job_id: str,
        *,
        substitution_ref: str | None = None,
        confirmation_ref: str | None = None,
    ):
        current = self._dispatcher.get(owner_id, job_id)
        if current is None or current.kind not in PROVIDER_JOB_KINDS:
            return self._dispatcher.retry(
                owner_id,
                job_id,
                substitution_ref=substitution_ref,
                confirmation_ref=confirmation_ref,
            )
        with self._uow_factory() as uow:
            operation = require_provider_operation(uow, owner_id, self._registry)
        return self._dispatcher.retry(
            owner_id,
            job_id,
            substitution_ref=substitution_ref,
            confirmation_ref=confirmation_ref,
            provider_name=operation.provider.value,
            disclosure_ref=operation.disclosure.id,
        )

    def __getattr__(self, name: str):
        return getattr(self._dispatcher, name)


def authorize_provider_job(dispatcher, uow, owner_id: str) -> ProviderOperation:
    authorize = getattr(dispatcher, "authorize", None)
    if not callable(authorize):
        raise TypeError("Provider-aware job authorization is unavailable.")
    return authorize(uow, owner_id)


def require_provider_operation(
    uow, owner_id: str, registry: ProviderRegistry
) -> ProviderOperation:
    disclosure = require_disclosure(uow, owner_id)
    provider = require_selected_provider(uow, owner_id, registry)
    return ProviderOperation(provider, disclosure)


def require_selected_provider(
    uow, owner_id: str, registry: ProviderRegistry
) -> ProviderName:
    settings = uow.settings_data.get(owner_id)
    if settings is None or settings.provider_selection is None:
        raise UnavailableError(
            "No provider is selected.",
            current_state="provider-not-selected",
            recovery_action="Select a configured provider in Settings, then retry.",
        )
    try:
        provider = ProviderName(settings.provider_selection)
    except ValueError as exc:
        raise UnavailableError(
            "The selected provider is unavailable.",
            recovery_action="Select a configured provider in Settings, then retry.",
        ) from exc
    registry.require_adapter(provider)
    return provider


def selected_provider_metadata(
    uow, owner_id: str, registry: ProviderRegistry
) -> tuple[str | None, str | None]:
    settings = uow.settings_data.get(owner_id)
    if settings is None or settings.provider_selection is None:
        return None, None
    try:
        provider = ProviderName(settings.provider_selection)
        adapter = registry.require_adapter(provider)
    except (ValueError, UnavailableError):
        return None, None
    return provider.value, getattr(adapter, "model", None)
