# IDK-403/404 acceptance evidence map

Authority: `docs/decisions/IDK-006-provider-cli-support.md`, PRD D3/D4/D7/D8, and IDK-403/404 in `IMPLEMENTATION_TICKETS.md`.

This map is the implementation checklist. The implementation commit is recorded in the final delivery after the staged-diff review.

| Requirement | Implementation owner | Evidence |
| --- | --- | --- |
| Safe per-provider executable/version/flag/auth discovery with fixed classifications | provider discovery modules and cached registry | Codex/Claude discovery unit tests; capability API integration tests |
| Typed fixed commands, models, ranges, environment policy, and three timers | `yuno.config`, provider adapters, composition root | configuration boundary tests and exact-argv/environment tests |
| Direct argv, `shell=False`, stdin context, restricted temp schema/cwd | provider process/adapter boundary | adapter tests and process-spawn assertions |
| PID/PGID/start identity/temp persistence before request delivery | provider request repository plus durable attempt runtime record; API response masks runtime identity | provider API/job integration assertions |
| Full process-group cancellation and distinct no-first/inactivity/absolute/nonzero outcomes | shared local process port | deterministic timer tests and real descendant termination test |
| Strict versioned event envelopes and operation schemas | Codex/Claude adapters plus `MappingValidator` | malformed, truncated, duplicate, wrong-version, extra-field, nested-adversarial tests |
| Quarantine isolation and IDK-010 cleanup | secure output store, provider repository, lifecycle coordinator | quarantine publication-negative and retention/deletion tests |
| Disclosure accepted before reservation/enqueue | provider gate used by every provider-backed API path | missing/revoked/wrong-version no-write tests; category-isolation tests |
| Owner selection is configured, pinned to each job, and has no automatic fallback | Settings API, provider-aware enqueue/runtime registry | no-selection/unavailable selection/enqueue/retry/owner-isolation tests |
| No SQLite write transaction spans provider/source execution | external job capture/execute/replay composition | transaction probe integration tests |
| Domain intent and queued job survive one atomic reservation transaction | dispatcher transaction reservation used by every provider/source POST | reservation rollback tests and startup queued-job reconciliation |
| Topic generation/regeneration and D3 cache/single-flight/staleness | learning-content routes/services through provider job | cache hit/stale/explicit regeneration/concurrency integration tests |
| Evidence, Practice, hands-on, Mock next-turn/final evaluation | evidence/interview handlers through provider job | end-to-end deterministic fake-registry integration tests |
| Tutor conversation and Interview refresher publication | tutor job plus published Interview-layer artifact reads | tutor/refresher integration tests |
| Explicit, independently disclosed source retrieval; GET/page views are inert | provenance POST job and source adapter | disclosure separation and no-side-effect route tests |
| Validated results publish provenance/claims/citations/assessment/transcript atomically | short authoritative completion transactions | result visibility and invalid-output negative integration tests |
| Truthful Settings and provider/action states with safe guidance | Settings hooks/pages and shared job state UI | Vitest plus Playwright configured/unavailable/disclosure/job-state/accessibility tests |
| No production fake/unavailable provider stand-ins | composition root and residue scan | static scans plus wiring integration tests |
| Explicit source HTTP boundary is SSRF/size/cancellation safe | pinned public DNS address, no redirects/proxy environment, bounded streaming | IPv4/IPv6/rebinding/redirect/limit/cancellation tests |

## IDK-006 row-to-code map

| Decision row | Code/config contract | Boundary evidence |
| --- | --- | --- |
| Codex version range | fixed typed range `>=0.147.0,<0.148.0` | exact minimum, newer patch, below minimum, upper/later major, malformed |
| Claude version range | fixed typed range `>=2.1.220,<2.2.0` | exact minimum, newer patch, below minimum, upper/later major, malformed |
| Exact argv per operation | provider-specific immutable argv builders | full tuple equality for every schema purpose |
| Model selection | fixed Codex Terra/high and fixed Claude Sonnet 4.6 ID | settings rejects any alternate value; adapter properties asserted |
| Executable discovery | absolute-path resolution and safe target checks | missing, PATH substitution, broken/cyclic symlink, unsafe/non-regular target |
| Version discovery/parsing | fixed `--version` probes and strict ASCII shapes | arbitrary output discarded; parser boundary matrix |
| Authentication discovery | Codex exit-only status; Claude bounded `loggedIn: true` JSON | success/failure and secret-like stderr absence from API/logs |
| Per-provider environment | exact immutable allowlists and credentialed-proxy rejection | exact mapping equality and prohibited-key scan |
| Prohibited environment | all non-allowlisted keys and named auth/cloud/connection secrets | adversarial source environment test |
| Adapter/output versions | fixed adapter and event-contract constants | capability and persisted provider-request assertions |
| Three timers | 20/180/1200 seconds | exact/equal boundary classification tests |
| Process-group cancellation | TERM/grace/KILL against PGID | child-process termination and cancellation tests |
| Schema/quarantine | strict duplicate-rejecting JSON plus Pydantic schema | malformed/truncated/extra/wrong/nested/duplicate tests and domain-negative queries |
| Learner classifications | fixed capability and job diagnostic vocabulary | API/UI recovery-state tests; raw error exclusion |
| Upgrade mismatch | provider disabled until supported adapter update | refresh changes configured to unsupported without fallback |
| Evidence/approval/version | decision document version 1.0, 2026-08-13, engineering owner | official links, safe local inspection record, full validation record |

## Completed validation record

- Server: 1,286 pytest tests passed; Ruff check passed; Ruff formatting passed for all 50 changed/new Python files; all 4 import-linter contracts passed.
- Database: one Alembic head; fresh migration, representative prior-database upgrade, downgrade/re-upgrade, and migration/metadata parity all passed.
- Contracts: OpenAPI regeneration and drift check passed; generated TypeScript declarations are current.
- Frontend: TypeScript typecheck passed; all 105 Vitest tests passed; production build passed; all 29 Playwright E2E tests passed.
- Operational: `git diff --check` and provider-security residue scans passed; `pnpm dev` started the migrated API and frontend together and served a healthy API.
- Isolation: automated tests used deterministic adapters or local HTTP mocks. No real provider/model invocation occurred, and ordinary route rendering caused no provider or source-network request.
