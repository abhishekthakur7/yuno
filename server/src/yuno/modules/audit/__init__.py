"""`audit` module (spec §3.3: `audit_observability`): append-only audit
events, structured diagnostics and correlations.

Cross-cutting: every other module may depend on `yuno.modules.audit`
(mainly its `ports.AuditRepository`) to append its own audit events -- see
`yuno.modules`'s docstring.
"""
