"""ASGI entrypoint: `uvicorn yuno.main:app`."""

from __future__ import annotations

from yuno.api.app import create_app

app = create_app()
