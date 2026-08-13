"""Ports for provider persistence, processes, validation, and secure output."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from yuno.modules.provider.domain import (
    NetworkDisclosure,
    ProcessOutcome,
    ProviderInput,
    ProviderResult,
    ProviderTimers,
    SchemaQuarantine,
)
from yuno.shared.application.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class ProcessSpec:
    argv: tuple[str, ...]
    stdin: bytes | None
    environment: Mapping[str, str]
    timers: ProviderTimers
    cwd: str | None = None
    json_event_heartbeat: bool = False
    stdout_limit_bytes: int = 2 * 1024 * 1024
    stderr_limit_bytes: int = 64 * 1024

    def __post_init__(self) -> None:
        if self.stdout_limit_bytes <= 0 or self.stderr_limit_bytes <= 0:
            raise ValueError("Process output limits must be positive.")


class ProcessPort(Protocol):
    def run(
        self,
        spec: ProcessSpec,
        *,
        on_spawn: Callable[[int, int, str], None],
        cancelled: Callable[[], bool],
    ) -> ProcessOutcome: ...


class OutputValidator(Protocol):
    def validate(self, value: object) -> Mapping[str, Any]: ...

    def json_schema(self) -> Mapping[str, Any]: ...


class SecureOutputStore(Protocol):
    def put(self, raw_output: bytes) -> str: ...


class ProviderPort(Protocol):
    provider: str
    adapter_version: str
    contract_version: str

    def invoke(
        self,
        request: ProviderInput,
        validator: OutputValidator,
        *,
        on_spawn: Callable[[int, int, str, str | None], None],
        cancelled: Callable[[], bool],
    ) -> ProviderResult: ...


class ProviderRepository(Protocol):
    def list_disclosures(self, owner_id: str) -> Sequence[NetworkDisclosure]: ...
    def get_active_disclosure(
        self, owner_id: str, category: str, disclosure_version: str
    ) -> NetworkDisclosure | None: ...
    def accept_disclosure(self, disclosure: NetworkDisclosure) -> NetworkDisclosure: ...
    def revoke_disclosure(
        self, owner_id: str, category: str, disclosure_version: str, revoked_at: str
    ) -> NetworkDisclosure | None: ...
    def create_request(self, **values: object) -> str: ...
    def mark_spawned(
        self,
        request_id: str,
        pid: int,
        pgid: int,
        process_identity: str,
        temp_path: str | None,
    ) -> None: ...
    def finish_request(
        self, request_id: str, lifecycle: str, diagnostic: str | None
    ) -> None: ...
    def add_quarantine(self, quarantine: SchemaQuarantine) -> SchemaQuarantine: ...
    def get_quarantine(
        self, owner_id: str, quarantine_id: str
    ) -> SchemaQuarantine | None: ...


class ProviderUnitOfWork(UnitOfWork, Protocol):
    provider: ProviderRepository
