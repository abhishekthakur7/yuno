"""The API layer: FastAPI adapters over the modules' application seams
(spec §3.2).

Only modules under `yuno.api` and `yuno.main` may import FastAPI or
Starlette — an import-linter contract fails the build if `yuno.shared.domain`,
`yuno.shared.application`, or a module's `domain.py`/`ports.py`/`service.py`
gains one.
"""

from __future__ import annotations
