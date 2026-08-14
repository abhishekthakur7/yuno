"""IDK-005 section 3 platform/architecture/WSL/container detection.

Reads are isolated behind `PlatformSnapshot` so `evaluate_platform` is a pure
function tests can exercise with a constructed snapshot instead of
monkeypatching `os.environ`, `pathlib.Path`, or the `platform` module.
`default_platform_snapshot` is the one real, production probe.
"""

from __future__ import annotations

import os
import platform as _platform
import re
from dataclasses import dataclass
from pathlib import Path

UNSUPPORTED_PLATFORM = "unsupported-platform"
PLATFORM_UNVERIFIABLE = "platform-unverifiable"

_BOUNDED_READ_BYTES = 8192
_APPROVED_OS_ID = "ubuntu"
_APPROVED_OS_VERSION_ID = "24.04"
_ARCH_ALIASES = {
    "x86_64": "x86_64",
    "amd64": "x86_64",
    "aarch64": "arm64",
    "arm64": "arm64",
}
_CONTAINER_CGROUP_MARKERS = ("docker", "containerd", "kubepods", "lxc")
_VERSION_PATTERN = re.compile(r"^[0-9]+(\.[0-9]+)*$")
_OS_DISPLAY = {"Darwin": "macOS", "Linux": "linux", "Windows": "windows"}


@dataclass(frozen=True)
class PlatformSnapshot:
    """Bounded, injectable platform facts.

    Deliberately does not carry the process environment: this is the runner
    module, whose own Appendix C row 4 control (`service.minimal_environment`)
    exists specifically to keep host secrets out of runner-adjacent data.
    Only the derived WSL-env-marker signal is captured, never raw env vars.
    """

    system_name: str
    machine: str
    os_release: dict[str, str] | None
    wsl_env_present: bool = False
    kernel_osrelease: str | None = None
    cgroup_text: str | None = None
    dockerenv_present: bool = False
    containerenv_present: bool = False


@dataclass(frozen=True)
class PlatformOutcome:
    """`diagnostic_code` is `None` only for the exact approved platform row."""

    diagnostic_code: str | None
    os: str
    version: str
    arch: str


def _bounded_read(path: Path) -> str | None:
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            return handle.read(_BOUNDED_READ_BYTES)
    except OSError:
        return None


def _parse_os_release(text: str | None) -> dict[str, str] | None:
    """Parses only `ID`/`VERSION_ID` -- the sole two keys `evaluate_platform`
    reads -- and drops the rest of the file (`PRETTY_NAME`, `HOME_URL`, ...)
    rather than carrying it into `PlatformSnapshot` unread."""
    if text is None:
        return None
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, raw_value = stripped.partition("=")
        key = key.strip()
        if key not in ("ID", "VERSION_ID"):
            continue
        values[key] = raw_value.strip().strip('"').strip("'")
    return values


def default_platform_snapshot() -> PlatformSnapshot:
    """The real production probe; every read is bounded and best-effort."""
    return PlatformSnapshot(
        system_name=_platform.system(),
        machine=_platform.machine(),
        os_release=_parse_os_release(_bounded_read(Path("/etc/os-release"))),
        wsl_env_present="WSL_INTEROP" in os.environ or "WSL_DISTRO_NAME" in os.environ,
        kernel_osrelease=_bounded_read(Path("/proc/sys/kernel/osrelease")),
        cgroup_text=_bounded_read(Path("/proc/1/cgroup")),
        dockerenv_present=Path("/.dockerenv").exists(),
        containerenv_present=Path("/run/.containerenv").exists(),
    )


def _normalize_arch(machine: str) -> str | None:
    return _ARCH_ALIASES.get(machine.lower())


def _safe_version(value: str | None) -> str:
    if value and _VERSION_PATTERN.fullmatch(value):
        return value
    return "unknown"


def _is_wsl(snapshot: PlatformSnapshot) -> bool:
    if snapshot.wsl_env_present:
        return True
    osrelease = snapshot.kernel_osrelease
    return bool(osrelease) and "microsoft" in osrelease.lower()


def _is_container(snapshot: PlatformSnapshot) -> bool:
    if snapshot.dockerenv_present or snapshot.containerenv_present:
        return True
    cgroup = snapshot.cgroup_text
    return bool(cgroup) and any(
        marker in cgroup for marker in _CONTAINER_CGROUP_MARKERS
    )


def evaluate_platform(snapshot: PlatformSnapshot) -> PlatformOutcome:
    """IDK-005 section 3: OS/version/architecture plus WSL/container gate.

    Precedence follows IDK-005 section 4's condition mapping: a positive
    WSL/container marker overrides everything else and fails closed even on
    an otherwise-approved-looking host; a definitively wrong (non-Linux)
    host or wrong Ubuntu identity/architecture is `unsupported-platform`;
    missing/malformed/unreadable OS identity on an actual Linux host is
    `platform-unverifiable`.
    """
    arch = _normalize_arch(snapshot.machine) or "unknown"
    os_display = _OS_DISPLAY.get(snapshot.system_name, "unknown")

    if _is_wsl(snapshot) or _is_container(snapshot):
        return PlatformOutcome(UNSUPPORTED_PLATFORM, os_display, "unknown", arch)

    if snapshot.system_name != "Linux":
        return PlatformOutcome(UNSUPPORTED_PLATFORM, os_display, "unknown", arch)

    if snapshot.os_release is None:
        return PlatformOutcome(PLATFORM_UNVERIFIABLE, "linux", "unknown", arch)

    os_id = snapshot.os_release.get("ID")
    version_id = snapshot.os_release.get("VERSION_ID")
    if not os_id or not version_id:
        return PlatformOutcome(
            PLATFORM_UNVERIFIABLE, "linux", _safe_version(version_id), arch
        )

    if (
        os_id != _APPROVED_OS_ID
        or version_id != _APPROVED_OS_VERSION_ID
        or arch == "unknown"
    ):
        return PlatformOutcome(
            UNSUPPORTED_PLATFORM, "linux", _safe_version(version_id), arch
        )

    return PlatformOutcome(None, "linux", version_id, arch)
