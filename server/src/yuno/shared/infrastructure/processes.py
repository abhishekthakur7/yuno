"""Cross-platform subprocess identity used before signalling recorded PIDs."""

from __future__ import annotations

import os
import signal
import subprocess
import time


def process_identity(pid: int) -> str:
    """Return a stable process-start identity, or fail closed as unavailable."""
    try:
        started = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        started = ""
    return f"{pid}:{started or 'unavailable'}"


def terminate_process_group(pgid: int, *, grace_seconds: float = 0.5) -> None:
    """Terminate an owned process group, escalating after a bounded grace."""
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if not process_group_exists(pgid):
            return
        time.sleep(0.02)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def process_group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
