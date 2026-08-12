"""Disclosure and quarantine application services."""

from __future__ import annotations

from dataclasses import replace

from yuno.modules.audit.domain import AuditEvent
from yuno.modules.provider.domain import (
    NetworkDisclosure,
    ProviderFailureClassification,
    ProviderInput,
    ProviderName,
    ProviderResult,
    ProviderResultState,
    SchemaQuarantine,
)
from yuno.modules.provider.ports import (
    OutputValidator,
    ProviderPort,
    ProviderUnitOfWork,
)
from yuno.shared.application.jobs import JobDispatcher, JobRef, JobRequest
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import Clock, SystemClock, now_text
from yuno.shared.domain.errors import (
    DomainValidationError,
    NotFoundError,
    PreconditionFailedError,
    UnavailableError,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id


def accept_disclosure(
    uow: ProviderUnitOfWork,
    owner_id: str,
    *,
    category: str,
    operation: str,
    destination: str,
    data_categories: tuple[str, ...],
    disclosure_version: str,
    clock: Clock | None = None,
) -> NetworkDisclosure:
    if not all(
        value.strip()
        for value in (category, operation, destination, disclosure_version)
    ):
        raise DomainValidationError("Disclosure fields must be non-blank.")
    if not data_categories or any(not value.strip() for value in data_categories):
        raise DomainValidationError("At least one non-blank data category is required.")
    disclosure = uow.provider.accept_disclosure(
        NetworkDisclosure(
            id=new_id(),
            owner_id=owner_id,
            category=category,
            operation=operation,
            destination=destination,
            data_categories=data_categories,
            disclosure_version=disclosure_version,
            accepted_at=now_text(clock or SystemClock()),
            revoked_at=None,
        )
    )
    uow.audit.append(
        AuditEvent(
            id=new_id(),
            owner_id=owner_id,
            goal_id=None,
            actor_role="learner",
            entity_type="network_disclosure",
            entity_id=disclosure.id,
            action="accepted",
            before_hash=None,
            after_hash=hash_payload(disclosure),
            reason=None,
            request_id=None,
            correlation_id=None,
            occurred_at=disclosure.accepted_at,
        )
    )
    return disclosure


def revoke_disclosure(
    uow: ProviderUnitOfWork,
    owner_id: str,
    category: str,
    disclosure_version: str,
    *,
    clock: Clock | None = None,
) -> NetworkDisclosure:
    disclosure = uow.provider.revoke_disclosure(
        owner_id, category, disclosure_version, now_text(clock or SystemClock())
    )
    if disclosure is None:
        raise NotFoundError("The requested disclosure was not found.")
    uow.audit.append(
        AuditEvent(
            id=new_id(),
            owner_id=owner_id,
            goal_id=None,
            actor_role="learner",
            entity_type="network_disclosure",
            entity_id=disclosure.id,
            action="revoked",
            before_hash=None,
            after_hash=hash_payload(disclosure),
            reason=None,
            request_id=None,
            correlation_id=None,
            occurred_at=disclosure.revoked_at or now_text(clock or SystemClock()),
        )
    )
    return disclosure


def enqueue_with_disclosure(
    uow: ProviderUnitOfWork,
    dispatcher: JobDispatcher,
    request: JobRequest,
    *,
    category: str,
    disclosure_version: str,
) -> JobRef:
    disclosure = uow.provider.get_active_disclosure(
        request.owner_id, category, disclosure_version
    )
    if disclosure is None:
        raise PreconditionFailedError(
            "Accept the current network/provider disclosure before starting this operation.",
            recovery_action="Review and accept the disclosure, then retry.",
        )
    return dispatcher.enqueue(replace(request, disclosure_ref=disclosure.id))


def require_disclosure(
    uow: ProviderUnitOfWork,
    owner_id: str,
    category: str = "provider-generation",
    disclosure_version: str = "provider-network-v1",
) -> NetworkDisclosure:
    disclosure = uow.provider.get_active_disclosure(
        owner_id, category, disclosure_version
    )
    if disclosure is None:
        raise PreconditionFailedError(
            "Accept the current network/provider disclosure before starting this operation.",
            recovery_action="Review and accept the disclosure, then retry.",
        )
    return disclosure


def execute_provider(
    uow_factory: UnitOfWorkFactory,
    adapter: ProviderPort,
    request: ProviderInput,
    validator: OutputValidator,
    *,
    cancelled=lambda: False,
    record_runtime=lambda **_values: None,
    clock: Clock | None = None,
) -> ProviderResult:
    """Execute outside a DB transaction; persist only safe metadata around it."""
    active_clock = clock or SystemClock()
    provider_request_id = new_id()
    with uow_factory() as raw_uow:
        uow = raw_uow
        uow.provider.create_request(
            id=provider_request_id,
            owner_id=request.owner_id,
            goal_id=request.goal_id,
            job_id=request.job_id,
            purpose=request.purpose,
            provider=adapter.provider,
            adapter_version=adapter.adapter_version,
            contract_version=adapter.contract_version,
            context_ref_hash=request.context_ref_hash,
            disclosure_id=request.disclosure_id,
            lifecycle="preparing",
            created_at=now_text(active_clock),
        )
        uow.commit()

    def record_spawn(pid: int, pgid: int, identity: str) -> None:
        with uow_factory() as uow:
            uow.provider.mark_spawned(provider_request_id, pid, pgid, identity)
            uow.commit()
        record_runtime(pid=pid, pgid=pgid, process_identity=identity)

    try:
        result = adapter.invoke(
            replace(request, provider_request_id=provider_request_id),
            validator,
            on_spawn=record_spawn,
            cancelled=cancelled,
        )
    except (FileNotFoundError, UnavailableError):
        result = ProviderResult(
            state=ProviderResultState.FAILED,
            provider=ProviderName(adapter.provider),
            model=None,
            contract_version=adapter.contract_version,
            schema_version=request.output_schema_version,
            payload=None,
            result_hash=None,
            failure_classification=(
                ProviderFailureClassification.CONFIGURATION_OR_AUTHENTICATION
            ),
            retryable=True,
        )
    except Exception:  # noqa: BLE001 -- external provider boundary is fail-closed
        result = ProviderResult(
            state=ProviderResultState.FAILED,
            provider=ProviderName(adapter.provider),
            model=None,
            contract_version=adapter.contract_version,
            schema_version=request.output_schema_version,
            payload=None,
            result_hash=None,
            failure_classification=ProviderFailureClassification.PROCESS_FAILED,
            retryable=True,
        )
    with uow_factory() as uow:
        if result.state is ProviderResultState.QUARANTINED:
            if result.quarantine is None:
                raise RuntimeError(
                    "Quarantined provider result omitted safe quarantine metadata."
                )
            quarantine = SchemaQuarantine(
                id=new_id(),
                owner_id=request.owner_id,
                provider_request_id=provider_request_id,
                job_id=request.job_id,
                raw_output_ref=result.quarantine.raw_output_ref,
                raw_output_hash=result.quarantine.raw_output_hash,
                expected_schema_version=request.output_schema_version,
                validation_errors=result.quarantine.validation_errors,
                created_at=now_text(active_clock),
            )
            uow.provider.add_quarantine(quarantine)
            result = replace(result, quarantine_id=quarantine.id)
        uow.provider.finish_request(
            provider_request_id,
            result.state.value,
            result.failure_classification.value
            if result.failure_classification
            else None,
        )
        uow.commit()
    return result
