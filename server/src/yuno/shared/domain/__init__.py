"""Cross-cutting domain primitives: entities, value objects and policies.

Framework-free (spec §3.2): this package and `yuno.shared.application` (and
every module's `domain.py`/`ports.py`/`service.py`) may import only the
standard library and `typing`, plus `python-ulid` in
`yuno.shared.domain.ids` specifically. No FastAPI, Starlette, SQLAlchemy,
Pydantic, `subprocess`, FTS syntax, or imports from `yuno.shared.infrastructure`,
`yuno.modules.*.models`/`.repository`, or `yuno.api`.
"""
