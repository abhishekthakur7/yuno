# IDK-010 policy 1.0 privacy-review evidence

- Policy: `docs/decisions/IDK-010-data-lifecycle-policy.md`
- Approval commit: `1aa6be0`
- Prior IDK-408/409 implementation: `d57d7e7`
- Engineering enforcement commit: `20f0ea45eee875ba671628c26b9c216ff37303c5`
- Manual review result: passed on 2026-08-13 by the product/privacy owner through explicit user attestation; recorded by the activation commit containing this update.

This artifact separates automated engineering evidence from the manual product/privacy review required by section 10. A checked engineering row means the cited automated evidence ran successfully against policy 1.0. The separate manual result below records the product/privacy owner's explicit acceptance. It does not claim regulatory compliance, forensic media sanitization, or backup recovery.

## Representative local dataset requirement

The automated suite demonstrates the required record categories across focused fixtures:

- Two goals, transferred evidence, and a dependent LearningState.
- Available evidence and D5-tombstoned evidence.
- An import original, parsed statements, corrections, decisions, and mappings.
- A generated artifact with provenance/source/claim/citation references.
- Completed and cancelled or inactive transcript-bearing interview sessions.
- Successful and failed jobs with safe diagnostics and provider quarantine metadata.
- Runner input/output metadata and temporary-workspace cleanup records when the configured runner is enabled.

The current lifecycle export fixture itself covers the canonical envelope, a two-goal transfer, D5 tombstoning, safe quarantine metadata, exclusions, download, ownership, and expiry. Other focused fixtures demonstrate available evidence, import review, generated provenance, terminal transcript sessions, provider job outcomes, and runner cleanup. These fixtures are the automated evidence presented for the separate product/privacy review recorded below.

Raw import originals, interview bodies, quarantined output, runner inputs/output, internal paths, and arbitrary diagnostics are deliberately not copied into this evidence document.

## Section 10 engineering evidence

| Review item | Engineering result | Demonstration |
| --- | --- | --- |
| Sample export checked field by field against the approved inventory and exclusions | [x] Automated contract and integration evidence passed | `server/tests/integration/test_data_lifecycle.py` verifies the canonical `yuno-portable-export` 1.0 envelope, complete inventory shape, exact exclusions, UTF-8 bytes, UTC filename, and SHA-256 over canonical `data`. Focused import, generated-content, interview, provider, and runner tests create the additional record categories. |
| Unavailable/tombstoned content is marked, not fabricated or silently omitted | [x] Automated adversarial evidence passed | Export tests cover the approved reason vocabulary and scan the package for prohibited raw bodies. Body-expiry and deletion tests verify live APIs do not reconstruct deleted content. |
| Delete preflight and completed delete show approved live-data, audit, recovery, and backup behavior | [x] Automated integration evidence passed | Goal-deletion integration coverage verifies an immutable fresh impact, atomic D5 tombstones/downgrades/body purge/audit, retained hashes/IDs/provenance, and the absence of any recovery or backup path. |
| Structured logs preserve correlations and exclude every prohibited category | [x] Automated integration evidence passed | `server/tests/integration/test_structured_logging.py` covers strict allowlisting/redaction, representative provider and runner failures, owner-only local files, rotation/expiry, and absence of remote handlers. |
| Configured size, count, expiry, rotation, and cleanup limits match the approved tables | [x] Automated boundary evidence passed | `server/tests/unit/test_config.py`, boundary tests in each owning module, and lifecycle-retention tests verify the adopted values and exact/equal-plus-one behavior. |
| Learner-facing Settings copy matches the approved guarantees | [x] Automated UI and E2E evidence passed | `src/selected/operations/OperationalPages.test.tsx` and `tests/e2e/selected-app.spec.ts` verify the configured limits, irreversible deletion, no recovery window, no Yuno-managed backup, external-backup caveat, and no remote support access. |

## Required release validation

Record the exact results from the implementation commit here before handoff:

- Server pytest: 1,208 passed with one dependency deprecation warning in 570.13 seconds.
- Ruff check: passed for `server/src` and `server/tests`.
- Ruff format check: 109 changed/new Python files already formatted.
- Import-linter architecture contracts: 4 kept, 0 broken; 213 files and 1,140 dependencies analyzed.
- Alembic single-head and migration/metadata parity: one head (`e10d1a0c0100`); fresh upgrade and `alembic check` passed; head/schema suites passed 764 tests with one dependency deprecation warning.
- OpenAPI drift: `server/openapi.json` is current and generated TypeScript matches.
- TypeScript typecheck: passed.
- Frontend Vitest: 16 files, 88 tests passed; one existing React list-key warning was emitted.
- Production frontend build: passed; 1,806 modules transformed, with Vite's existing chunk-size advisory.
- Playwright E2E: 28 tests passed.
- `git diff --check`: passed before staging and is repeated against the staged diff before commit.
- Obsolete-policy/prototype residue scans: no obsolete implementation path or placeholder remains; the only matches are intentional negative guard assertions and historical forward-migration column names.

## Manual product/privacy review

- [x] A product/privacy reviewer has inspected one representative local dataset and a downloaded canonical export field by field.
- [x] The reviewer has inspected the delete preflight/completion record and local rotated logs.
- [x] The reviewer has confirmed the Settings wording in the running product.

Result: passed. This records the product/privacy owner's explicit statement, “IDK-010 section 10 privacy review passed,” received on 2026-08-13. Production export may now activate without changing any policy 1.0 limit or guarantee.
