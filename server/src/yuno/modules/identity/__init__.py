"""`identity` module (spec §3.3): the built-in local owner, role grants,
and the future identity seam.

Cross-cutting: every other module may depend on `yuno.modules.identity`
(mainly its `service.ensure_local_owner` and `ports.OwnerRepository`) --
see `yuno.modules`'s docstring.
"""
