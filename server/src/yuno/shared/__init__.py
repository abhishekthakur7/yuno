"""Cross-cutting primitives shared by every module (spec §3.3).

Only genuinely module-agnostic code lives here: error taxonomy, id/clock
primitives, the minimal `UnitOfWork`/`JobDispatcher` seams, and framework
plumbing (engine/session construction, the declarative base, the Alembic
guard). `yuno.shared` must NEVER import from `yuno.modules` -- doing so
would invert spec §3.2's dependency direction. See `yuno.shared.domain`
and `yuno.shared.application` for the framework-free rule that binds
those two subpackages specifically.
"""
