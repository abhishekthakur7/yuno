"""Bounded-context modules (spec §3.3): each module owns its own tables.

Cross-module ORM mutation is forbidden -- modules read one another through
query interfaces and write through application commands or UoW-collected
domain events, never by importing another module's `models`/`repository`.
An import-linter `independence` contract (`server/pyproject.toml`) enforces
this mechanically; see `tests/architecture/test_import_boundaries.py` for
the self-test proving it actually bites.

`identity` and `audit` are the two exceptions: per IDK-101, both are
cross-cutting and are meant to be imported by every other module (identity
resolves the acting owner; audit is how any module records an audit
event). The independence contract's `modules` list and `ignore_imports`
reflect that explicitly -- see `pyproject.toml`'s comments on the contract
itself.
"""
