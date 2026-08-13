from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from yuno.config import Settings
from yuno.modules.provider.domain import (
    ProviderCapability,
    ProviderCapabilityState,
    ProviderName,
)
from yuno.modules.provider.registry import ProviderRegistry, resolve_safe_executable


class Adapter:
    provider = "codex"
    model = "fixture-model"
    adapter_version = "fixture-adapter-v1"
    contract_version = "fixture-contract-v1"


def _capability(
    provider: ProviderName, state: ProviderCapabilityState
) -> ProviderCapability:
    return ProviderCapability(provider, state)


def test_registry_reads_cached_snapshot_until_explicit_atomic_refresh() -> None:
    calls = {ProviderName.CODEX: 0, ProviderName.CLAUDE: 0}
    codex = Adapter()

    def discover(provider: ProviderName):
        def run():
            calls[provider] += 1
            if provider is ProviderName.CODEX and calls[provider] == 1:
                return _capability(provider, ProviderCapabilityState.CONFIGURED), codex
            return (
                _capability(
                    provider, ProviderCapabilityState.AUTHENTICATION_UNAVAILABLE
                ),
                None,
            )

        return run

    registry = ProviderRegistry(
        {provider: discover(provider) for provider in ProviderName}
    )
    first = registry.refresh()
    assert calls == {ProviderName.CODEX: 1, ProviderName.CLAUDE: 1}
    assert registry.capabilities() == first
    assert registry.capability(ProviderName.CODEX).state is (
        ProviderCapabilityState.CONFIGURED
    )
    assert registry.require_adapter(ProviderName.CODEX) is codex
    assert calls == {ProviderName.CODEX: 1, ProviderName.CLAUDE: 1}

    second = registry.refresh()
    assert calls == {ProviderName.CODEX: 2, ProviderName.CLAUDE: 2}
    assert all(
        item.state is ProviderCapabilityState.AUTHENTICATION_UNAVAILABLE
        for item in second
    )


def test_safe_executable_resolution_ignores_path_and_handles_symlink_edges(
    tmp_path, monkeypatch
) -> None:
    executable = tmp_path / "provider-real"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o700)
    link = tmp_path / "provider-link"
    link.symlink_to(executable)
    path_substitute = tmp_path / "provider-from-path"
    path_substitute.write_text("#!/bin/sh\n", encoding="utf-8")
    path_substitute.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path))

    assert resolve_safe_executable(executable) == executable
    assert resolve_safe_executable(link) == executable
    assert resolve_safe_executable(type(tmp_path)(path_substitute.name)) is None

    executable.chmod(0o720)
    assert resolve_safe_executable(executable) is None
    executable.chmod(0o700)
    executable.unlink()
    assert resolve_safe_executable(link) is None

    cycle = tmp_path / "cycle"
    cycle.symlink_to(cycle)
    assert resolve_safe_executable(cycle) is None
    assert resolve_safe_executable(tmp_path) is None
    assert not os.path.exists(tmp_path / "missing")
    assert resolve_safe_executable(tmp_path / "missing") is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider_policy_version", "2.0"),
        ("provider_codex_model", "moving-alias"),
        ("provider_codex_reasoning_effort", "low"),
        ("provider_claude_model", "sonnet"),
        ("provider_first_output_seconds", 19),
        ("provider_inactivity_seconds", 181),
        ("provider_absolute_seconds", 1_201),
    ],
)
def test_provider_policy_configuration_rejects_unapproved_values(field, value) -> None:
    with pytest.raises(ValidationError):
        Settings(**{field: value})


def test_provider_configuration_rejects_relative_executable_paths() -> None:
    with pytest.raises(ValidationError, match="absolute"):
        Settings(provider_codex_executable="codex")
