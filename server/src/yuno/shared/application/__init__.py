"""Cross-cutting application seams: the minimal unit-of-work protocol and
the async-operation (`JobDispatcher`) port.

Framework-free (spec §3.2), same rule as `yuno.shared.domain` -- see that
package's docstring. Declares no module repository: each module's
`ports.py` extends `UnitOfWork` with its own repository attribute(s)
(spec §3.3; see `yuno.modules.identity.ports.IdentityUnitOfWork` for the
pattern).
"""
