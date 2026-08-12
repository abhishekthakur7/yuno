"""Cross-platform subprocess identity used before signalling recorded PIDs."""

from __future__ import annotations

import subprocess


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
