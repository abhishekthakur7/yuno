"""Atomic cached capability and adapter registry."""

from __future__ import annotations

import os
import stat
from collections.abc import Callable, Mapping
from pathlib import Path
from threading import RLock

from yuno.modules.provider.domain import (
    ProviderCapability,
    ProviderCapabilityState,
    ProviderName,
)
from yuno.modules.provider.ports import ProviderPort
from yuno.shared.domain.errors import UnavailableError

ProviderDiscovery = Callable[[], tuple[ProviderCapability, ProviderPort | None]]


class ProviderRegistry:
    def __init__(self, discoveries: Mapping[ProviderName, ProviderDiscovery]) -> None:
        if set(discoveries) != set(ProviderName):
            raise ValueError("Every provider must have exactly one discovery policy.")
        self._discoveries = dict(discoveries)
        self._lock = RLock()
        self._capabilities: dict[ProviderName, ProviderCapability] = {}
        self._adapters: dict[ProviderName, ProviderPort] = {}

    def refresh(self) -> tuple[ProviderCapability, ...]:
        capabilities = {}
        adapters = {}
        for name in ProviderName:
            capability, adapter = self._discoveries[name]()
            if capability.provider is not name:
                raise RuntimeError("Provider discovery returned the wrong provider.")
            if capability.state is ProviderCapabilityState.CONFIGURED:
                if adapter is None:
                    raise RuntimeError("Configured provider omitted its adapter.")
                adapters[name] = adapter
            elif adapter is not None:
                raise RuntimeError("Unavailable provider exposed an adapter.")
            capabilities[name] = capability
        with self._lock:
            self._capabilities = capabilities
            self._adapters = adapters
            return tuple(capabilities[name] for name in ProviderName)

    def capabilities(self) -> tuple[ProviderCapability, ...]:
        with self._lock:
            if not self._capabilities:
                raise RuntimeError("Provider capabilities were not discovered.")
            return tuple(self._capabilities[name] for name in ProviderName)

    def capability(self, provider: ProviderName) -> ProviderCapability:
        with self._lock:
            try:
                return self._capabilities[provider]
            except KeyError as exc:
                raise RuntimeError(
                    "Provider capabilities were not discovered."
                ) from exc

    def require_adapter(self, provider: ProviderName) -> ProviderPort:
        with self._lock:
            try:
                capability = self._capabilities[provider]
            except KeyError as exc:
                raise RuntimeError(
                    "Provider capabilities were not discovered."
                ) from exc
            if capability.state is not ProviderCapabilityState.CONFIGURED:
                raise UnavailableError(
                    "The selected provider is unavailable.",
                    current_state=capability.state.value,
                    recovery_action=capability.recovery_action,
                )
            return self._adapters[provider]


def resolve_safe_executable(value: Path) -> Path | None:
    """Resolve one configured absolute target without consulting PATH."""
    if not value.is_absolute():
        return None
    try:
        resolved = value.resolve(strict=True)
        details = resolved.stat()
    except (OSError, RuntimeError):
        return None
    if not stat.S_ISREG(details.st_mode) or details.st_mode & 0o022:
        return None
    if not os.access(resolved, os.X_OK):
        return None
    return resolved


def missing_capability(provider: ProviderName) -> ProviderCapability:
    return ProviderCapability(
        provider,
        ProviderCapabilityState.EXECUTABLE_MISSING,
        "The configured CLI executable is missing or unsafe.",
        "Install the supported CLI or correct its absolute path, then refresh.",
    )


def unsupported_capability(provider: ProviderName) -> ProviderCapability:
    return ProviderCapability(
        provider,
        ProviderCapabilityState.UNSUPPORTED_VERSION,
        "The installed CLI version or command surface is unsupported.",
        "Install a supported CLI version, then refresh.",
    )


def authentication_capability(provider: ProviderName) -> ProviderCapability:
    return ProviderCapability(
        provider,
        ProviderCapabilityState.AUTHENTICATION_UNAVAILABLE,
        "The CLI did not confirm local authentication and configuration.",
        "Complete the CLI's local sign-in, then refresh.",
    )
