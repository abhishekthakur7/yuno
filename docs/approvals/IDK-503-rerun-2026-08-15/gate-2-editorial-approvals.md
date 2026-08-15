# IDK-503 (re-run) gate 2 — Editorial approval evidence and criteria

- Gate: Editorial approval evidence and criteria (CORE-02/INT-02, Appendix H D1)
- Reviewer role required: designated editorial approver
- Inspection date: 2026-08-15
- Disposition: blocking-finding
- Attestation: pending -- designated editorial approver has not signed this gate.

This is a fresh, independent re-inspection against the tree as of 2026-08-15
(HEAD `2621d29`), not an amendment of `docs/approvals/IDK-503/gate-2-editorial-approvals.md`
(inspection date 2026-08-14). That prior document was read only to scope this
re-inspection; none of its citations were carried forward unverified. Every
claim below was independently re-derived: by reading the current source at
the cited lines, by migrating a throwaway database and inspecting its actual
schema, by running the test suite, and by executing
`scripts/publish_canonical.py` against real manifest files.

**HEAD delta check (2621d29).** The body of this inspection was performed at
`92f2a85`. One further commit, `2621d29` ("resolve the local owner without
opening a UnitOfWork", IDK-503 B14), has since landed and was checked before
finalizing this record — not assumed clean. `git show --stat 2621d29` touches
only `server/src/yuno/api/app.py`, `server/src/yuno/api/dependencies.py`, and
two API-layer test files; no migration, no `canonical` module file, no
`scripts/publish_canonical.py`. The change replaces `get_owner_id`'s body
(previously: open a `UnitOfWork`, `SELECT` the local owner row; now: read
`request.app.state.owner_id`, cached at lifespan startup) — a request-path
performance/side-effect fix (IDK-008) unrelated to this gate's subject.
Verified directly, not assumed:
- `grep -rn "get_owner_id" server/src/yuno/modules/canonical/ server/scripts/publish_canonical.py` → zero hits. `publish_canonical_graph`'s `actor_owner_id` (`publisher.py:94`, used at `:139` for the role-grant check that findings 3/6 above rely on) is a plain function parameter, sourced from the CLI's own `--actor-owner-id` argument (`scripts/publish_canonical.py:257`, `args.actor_owner_id`) — confirmed by reading both call sites, not assumed from the docstring. D1 has no HTTP entry point at all (spec §5.1; confirmed no `canonical`-prefixed write route exists under `server/src/yuno/api/routes/`), so `get_owner_id` was never in the dependency graph for the role-grant check, the `record_approval` call, or any other write this gate's findings rest on.
- `server/src/yuno/api/routes/canonical.py` (the two read-only `GET /canonical/versions[...]` endpoints findings 7/9 in the prior gate reference for approval-gated reads) does not depend on `get_owner_id` at all — its own module docstring states these reads need no authentication. `2621d29` does not touch this file.
- `server/src/yuno/api/routes/canonical_updates.py` does depend on `get_owner_id` (its `decide`/`accept`/`get_update` routes), but this is IDK-407/CUR-04 diff-merge overlay machinery, explicitly out of IDK-002's boundary (`IDK-002:29`, "this decision does not redesign that mechanism") and out of this gate's scope.
- Re-ran the full set of tests this record's findings depend on at the new HEAD: `pytest tests/integration/test_canonical_basis_ref_constraint.py tests/integration/test_canonical_publish.py tests/unit/test_canonical_basis_ref_validation.py` → 60 passed, same as at `92f2a85`.

**Conclusion: nothing in `2621d29` bears on gate 2's subject matter. No finding below changes. Disposition and attestation are unchanged from the `92f2a85` inspection.** The HEAD this record is stamped against has been advanced to `2621d29` only after this check confirmed the delta is inert for this gate's purposes — not as a silent restamp.

## Inspected artifacts

| Artifact | What it is | How inspected |
| --- | --- | --- |
| `docs/decisions/IDK-002-editorial-approval-criteria.md` | Decision under review | Read in full; §4 (`:53-75`, 15-field `basis_ref` contract) and §8 (`:110-128`, required removal/implementation evidence) walked field-by-field |
| `docs/approvals/IDK-503/gate-2-editorial-approvals.md` | Previous round's gate record | Read for scope only, per instruction; its citations treated as stale and re-derived independently |
| `server/src/yuno/modules/canonical/models.py:418-445` | `EditorialApprovalRow` ORM model | Read; confirmed `CheckConstraint("json_valid(basis_ref)", name="basis_ref_valid")` at line 432 |
| `server/src/yuno/migrations/versions/4747447ccaa3_basis_ref_valid.py` | Migration adding the CHECK constraint | Read in full (139 lines); confirms drop-triggers → `batch_alter_table` (with `PRAGMA foreign_keys` toggled via `autocommit_block`) → recreate-triggers sequence for both `upgrade()`/`downgrade()` |
| Scratch DB `idk503-gate2-scratch.db` | Fresh SQLite DB migrated to head | Created under this session's scratchpad directory; `alembic upgrade head` run against it (exit 0, ran all 30 migrations including `4747447ccaa3`); never touched `server/yuno.db` or `server/.e2e.db` |
| Scratch DB schema dump | Real migrated `editorial_approvals` DDL | `sqlite3 <scratch>.db ".schema editorial_approvals"` — shows `CONSTRAINT ck_editorial_approvals_basis_ref_valid CHECK (json_valid(basis_ref))` present at the actual database layer, not just in the ORM |
| Scratch DB trigger dump | Immutability triggers post-migration | `SELECT name, sql FROM sqlite_master WHERE type='trigger' AND tbl_name='editorial_approvals'` — all three (`trg_editorial_approvals_no_update`, `_no_delete`, `_no_insert_replace`) present, bodies unchanged from `87af9746aec1` |
| Scratch DB live INSERT test | CHECK constraint actually enforced | `INSERT INTO editorial_approvals (...) VALUES (..., 'not-json', ...)` against the scratch DB → `Error: CHECK constraint failed: ck_editorial_approvals_basis_ref_valid` |
| `server/src/yuno/modules/canonical/validation.py:379-879` | `validate_basis_ref` and its helpers | Read in full; every §4 field traced to its enforcement code (see Findings table) |
| `server/src/yuno/modules/canonical/publisher.py:89-254` | `publish_canonical_graph` | Read in full; traced ordering: `require_single_head` → `validate_manifest` (outside UoW) → open UoW → role-grant check (`:140`) → `validate_basis_ref` (`:143-162`, before any of `:164` conflict checks or `:181` first insert) |
| `server/scripts/publish_canonical.py:118-272` | `load_manifest`/`main` | Read in full, then **executed** against two hand-built malformed manifests (see below) |
| `server/tests/integration/test_canonical_basis_ref_constraint.py` | CHECK constraint + trigger-survival tests | Read and run: `pytest tests/integration/test_canonical_basis_ref_constraint.py` |
| `server/tests/integration/test_canonical_publish.py` | Publisher wiring tests, incl. `basis_ref` rejection-before-write | Read (esp. `:69-146` fixture builder, `:312-437` four basis_ref rejection tests) and run |
| `server/tests/unit/test_canonical_basis_ref_validation.py` | Exhaustive `validate_basis_ref` unit tests (46 tests) | Read test names in full and run |
| `server/tests/fixtures/canonical/data/v1_approved.json` | Fixture manifest + approval | Read; loaded via `load_fixture("v1_approved")` and cross-checked `reviewed_manifest_hash` against `compute_manifest_hash(fixture.manifest)` programmatically |
| `server/yuno.db` | Local dev SQLite DB | `sqlite3 server/yuno.db "SELECT * FROM alembic_version"` / row counts / `.schema editorial_approvals` — read-only queries only |
| `server/.e2e.db` | E2E-run SQLite DB | Same read-only queries |
| `alembic heads` / `alembic history` | Current migration head | Run against `server/` with `.venv` activated |
| Residue scan | Single write path to `editorial_approvals` | `grep -rn "record_approval"` and `grep -rn "editorial_approvals"` across `server/src` |

## Findings

| # | Decision requirement | Shipped reality (with citation) | Verdict |
| --- | --- | --- | --- |
| 1 | §8 item 1: `CheckConstraint("json_valid(basis_ref)", name="basis_ref_valid")` on `EditorialApprovalRow`, mirroring `payload_json_valid` | `models.py:432` carries exactly this constraint. Verified independently at the database layer, not just the ORM: a scratch DB migrated fresh to head (`be4d11f03666`) shows `CONSTRAINT ck_editorial_approvals_basis_ref_valid CHECK (json_valid(basis_ref))` in `.schema editorial_approvals`, and a live `INSERT ... VALUES (..., 'not-json', ...)` against that DB was rejected with `CHECK constraint failed: ck_editorial_approvals_basis_ref_valid` | **closed** |
| 2 | §8 (docstring, `4747447ccaa3`): the batch-rebuild triggering this constraint must not silently drop `editorial_approvals`'s three raw-SQL immutability triggers | All three triggers (`trg_editorial_approvals_no_update`, `_no_delete`, `_no_insert_replace`) present at head in the scratch DB, bodies identical to `87af9746aec1`'s originals. `test_basis_ref_valid_trigger_survives_the_batch_alter_rebuild` (`test_canonical_basis_ref_constraint.py:95-114`) asserts the same and passes | **closed** |
| 3 | §8 item 2: framework-free schema validation of the parsed `basis_ref` object against §4, invoked by `publish_canonical_graph` before `record_approval`, analogous to `validate_manifest` before the transaction opens | `validation.py:468-697` `validate_basis_ref` implements this. `publisher.py:143-162` calls it inside the UoW, after the role-grant check (`:140`) and before the version_label/manifest_hash conflict checks (`:164-173`) and every subsequent write (`:181` `create_version` is the first insert) — confirmed by reading the function top to bottom, not by the docstring's own claim | **closed** |
| 4 | §4's 15-field contract, field by field | See per-field breakdown below | **closed for presence; see documented deliberate gaps** |
| 5 | §4 item 3 (`:73`): `reviewed_manifest_hash` recomputed and compared against the row's actual `manifest_hash`, closing reuse across versions | `validation.py:590-598` compares `reviewed_manifest_hash` against a `manifest_hash` parameter that `publisher.py:145` passes as `manifest.manifest_hash` — itself independently recomputed by `validate_manifest`/`compute_manifest_hash`, never file-trusted. Load-bearing, not vacuous: `v1_approved.json`'s fixture `reviewed_manifest_hash` (`c76bc6...dda24`, 64 hex chars) was independently recomputed via `compute_manifest_hash(fixture.manifest)` in this session and matches exactly. `test_basis_ref_reviewed_manifest_hash_mismatch_rejected_before_any_write` (`test_canonical_publish.py:361-387`) asserts rejection AND that all six canonical tables remain empty afterward — run, passed | **closed** |
| 6 | §4 item 4 (`:73`): `review_kind`/`diff_against_version_label`/`diff_review` cross-checked against `list_published_versions()` | `validation.py:613-684`; `publisher.py:142-147` supplies the real `list_published_versions()` result. `test_basis_ref_review_kind_published_state_mismatch_rejected_before_any_write` (`test_canonical_publish.py:390-437`) publishes a real v1, then attempts a v2 with `review_kind` forced back to `"initial"`, asserts rejection, and asserts row counts are unchanged from immediately after v1 — run, passed | **closed** |
| 7 | §8 item 3 (`:116`): `scripts/publish_canonical.py`'s `load_manifest` must construct/validate the §4 object and reject a mismatched shape via the existing exit-code-2 path | **Verified by running the script**, not by reading it. Built two manifests from the `v1_approved` fixture: (a) `approval.basis_ref` set to the old-style non-JSON placeholder `"fixture-approval-basis-v1"`, (b) valid JSON with `reviewed_manifest_hash` deleted. `python scripts/publish_canonical.py <manifest> --actor-owner-id nonexistent-owner` against a real (migrated-to-head) scratch DB: both exited **2**, with stderr naming `basis_ref_not_valid_json` / `basis_ref_missing_field` respectively. `editorial_approvals`/`canonical_graph_versions` row counts in the scratch DB were 0 before and after both attempts (expected: `load_manifest` runs and raises before any `Engine`/session is even created) | **closed** |
| 8 | §8 item 4 (`:117`): residue scan — `record_approval` is the only write path to `editorial_approvals`, called only from `publish_canonical_graph` | `grep -rn "record_approval" server/src` → three hits: the `Protocol` declaration (`ports.py:62`), its one implementation (`repository.py:152-162`, a plain `session.add(EditorialApprovalRow(...)); session.flush()`), and its one call site (`publisher.py:221`). A second grep for `editorial_approvals` across `server/src` turns up only FK/JOIN references (`roadmap`, `diagnostics`, `imports`, `search` modules) and migration DDL — no other INSERT path | **closed** |
| 9 | §6 (`:92`): no placeholder `basis_ref` on a production version | `editorial_approvals` is empty in both inspectable databases (finding 10) — nothing to violate yet. Placeholder strings only appear in `server/tests/fixtures/canonical/data/*.json`, all now real §4-shaped JSON objects carrying `"notes": "SYNTHETIC FIXTURE basis_ref -- NOT a real editorial review..."`, not bare placeholder strings | **matches (nothing to violate yet)** |
| 10 | §8 (`:119`) / previous round's blocking finding 2: no production `editorial_approvals` row exists | Re-checked directly: `SELECT COUNT(*) FROM editorial_approvals` = 0 in both `server/yuno.db` and `server/.e2e.db`. `server/yuno.db`'s `alembic_version` = `4747447ccaa3` (the basis_ref-valid migration itself, confirming the CHECK constraint is live on that file) but **not** current head — `alembic heads` on this tree reports `be4d11f03666`, two revisions later (`4cb74877e4ba` source-license work, `be4d11f03666` scenario-status work; neither touches `editorial_approvals`). `server/.e2e.db`'s `alembic_version` = `a9d4e6f1b208`, several revisions before `4747447ccaa3` — no `basis_ref_valid` constraint present there, confirming it is untouched by this work, consistent with the task framing | **still open — see blocking finding 1 below** |

### §4 field-by-field enforcement

Walked every row of §4's table (`IDK-002:53-75`) against `validation.py`:

| Field | Enforced? | Where | Note |
| --- | --- | --- | --- |
| `basis_ref_version` | Yes | `:564-575` | Literal match against `"editorial-approval-basis-v1"` |
| `policy_identifier` | Yes | `:577-588` | Literal match against `"editorial-approval-criteria-v1"` |
| `reviewed_manifest_hash` | Yes | `:590-598` | Cross-checked against caller-supplied recomputed `manifest_hash` |
| `checklist_completed_at` | Partial | `:600-601` | Only "non-blank string" — no UTC-timestamp format/parse check. **Deliberate gap, confirmed true** (see below) |
| `review_kind` | Yes | `:603-627` | Enum `{"initial","diff"}`, plus published-state cross-check when DB state is supplied |
| `diff_against_version_label` | Yes | `:629-658` | Nullable-string shape + non-null/blank when `"diff"`, null when `"initial"`, equality against latest published label |
| `curriculum_boundary_review` | Yes | `:660-663` via `_COUNTED_REVIEW_SPECS` | `result` present/non-blank; `topics_reviewed == topics_total` |
| `dsa_scenario_review` | Yes | same | `dsa_topics_reviewed == dsa_topics_total` |
| `dag_identity_review` | Yes | same | `reused_stable_ids_confirmed == reused_stable_ids_total` |
| `source_citation_review` | Yes | same | `structural_result`/`live_check_result` present; `structural_claims_reviewed == structural_claims_total` (exhaustive per §5); `live_check_sample_size`/`live_check_population_size` type-checked only, **not** equality-checked — correct per §5's sampling rule, not a gap |
| `layer_reversal_review` | Yes | same | `topics_reviewed == topics_total` |
| `half_seed_immutability_check` | Yes | same | `result` present/non-blank |
| `diff_review` | Yes | `:665-684` | Nullable object; non-null with equal counts iff `review_kind == "diff"`; null iff `"initial"` |
| `approver_is_sole_content_author` | Partial | `:686` | Type-checked (`bool`) only — **not** cross-checked against actual `creator_owner_id`/`approver_owner_id` authorship data. **Deliberate gap, confirmed true** (see below) |
| `notes` | Yes | `:688-695` | Optional; if present, must be `str` |

Every one of the 15 fields has at least presence/type enforcement; none is silently unenforced. The two "partial" rows above are the deliberate, documented gaps this task asked to be verified.

### Verifying the four named deliberate gaps

1. **Nested `result`/`structural_result`/`live_check_result` not constrained to an enum.** Confirmed: `_nested_string` (`validation.py:805-834`) only checks "present, non-blank string." §4's table (`:63-69`) never states a value domain for these sub-fields — only §3.1-3.6's prose uses "Pass"/"Fail" as English words describing outcomes, not a declared JSON enum. §4's own "Minimum mechanical validation required" list (`:73`, items 1-5) does not include a result-value enum either. **Assessment: true, and not required by §4's literal text** — a reasonable, honestly-documented gap, not a shortfall against the decision as written.
2. **`checklist_completed_at`'s timestamp format not validated.** Confirmed: `:600-601` calls `_string_field`, non-blank-string only. §4 states the type as `"string, UTC timestamp"` (`:60`), which is arguably more specific than "any non-blank string" — a stricter reading of "correctly typed" (§4 minimum-validation item 2, `:73`) could ask for format validation. `validation.py`'s own docstring (`:514-518`) states no UTC-timestamp parser exists elsewhere in the codebase (`yuno.shared.domain.clock` only produces the format, doesn't validate an arbitrary string against it) as the reason this wasn't built. **Assessment: true; a genuine, if narrow, interpretive gap** — flagged as residual risk below, not elevated to blocking because §4's explicit five-item minimum-validation list doesn't separately name timestamp-format checking, and no reusable parser exists to build it on.
3. **Count fields inferred as non-negative int.** Confirmed: `_nested_count` (`:837-858`) requires `isinstance(value, int)` (with `bool` explicitly excluded, since `bool` is a subtype of `int` in Python) and `value >= 0`. §4 never states an explicit type for these sub-fields either. **Assessment: true, and a reasonable inference, not a shortfall.**
4. **`approver_is_sole_content_author` type-checked only, no authorship cross-check.** Confirmed: `_bool_field` (`:725-737`) checks `isinstance(value, bool)` only. §4's own "Meaning" column (`:70`) describes the field as making an existing comparison "an explicit recorded fact" — i.e., a human attestation, not a field the validator is asked to derive or verify against `creator_owner_id`/`approver_owner_id`. §8's four implementation items (`:114-117`) do not list an authorship cross-check as required. **Assessment: true, and correctly scoped to what §8 actually requires** — not a shortfall.

## Blocking findings

### 1. No production `editorial_approvals` row exists to inspect against §4's criteria

- What is missing: any row in `editorial_approvals` on either database available for inspection.
- Owning ticket: IDK-102 (production seed run) — IDK-002 §8 (`:119`) itself states no production canonical graph version has ever been published, and names IDK-503 as the check that must run once one is.
- Evidence of absence: `sqlite3 server/yuno.db "SELECT COUNT(*) FROM editorial_approvals"` → `0`; same query against `server/.e2e.db` → `0`. Both re-verified directly in this session, read-only.
- Status vs. previous round: **still open, unchanged.** This is the same gap the 2026-08-14 round recorded; c3409df's work (which closed the *mechanism* gap, previous round's finding 1) did not and could not close this one — it requires an actual production publish under IDK-102, not more validation code.
- What would clear it: run IDK-102's production seed against a real manifest under this policy, producing a `basis_ref` conforming to §4 (now mechanically enforced, per findings 1-8 above), then re-inspect the row's actual field content against §4/§5's exhaustiveness and sampling rules — not merely that a row exists.

## Notes and residual risk

- **Previous round's blocking finding 1 ("`basis_ref` mechanical/schema validation entirely unimplemented") is closed.** Verified independently across all four of its named sub-parts: (a) `json_valid` CHECK constraint — confirmed at the ORM layer and, more strongly, on an actually-migrated database schema plus a live rejected INSERT; (b) parsed-object validation against §4's 15-field contract — every field walked and confirmed enforced (with two narrow, honestly-documented gaps, neither of which the decision's minimum-validation clause requires); (c) `reviewed_manifest_hash` cross-check — confirmed load-bearing against a fixture with a genuinely recomputed hash, not a vacuous stub; (d) `review_kind`/`diff_against_version_label` consistency check — confirmed against real `list_published_versions()` state in a passing integration test that also asserts no partial rows survive. All three immutability triggers on `editorial_approvals` were independently confirmed to survive the migration's batch rebuild.
- **60 tests examined were actually run in this session** (14 in `test_canonical_basis_ref_constraint.py` + `test_canonical_publish.py`'s relevant subset, 46 in `test_canonical_basis_ref_validation.py`), all passing. The rejection-before-write tests were read closely enough to confirm they assert row-count/table-emptiness after the exception, not merely that an exception was raised.
- **`scripts/publish_canonical.py`'s exit-code-2 path was verified by execution**, not by reading the source: two independently constructed malformed manifests (non-JSON `basis_ref`; valid-JSON-but-missing-required-field `basis_ref`) both produced exit code 2 with the expected violation code named in stderr, and left a real migrated scratch database untouched.
- **`server/yuno.db` is not at the current migration head.** Its `alembic_version` is `4747447ccaa3` — the basis_ref-valid migration itself, so it does carry the CHECK constraint this gate cares about — but `alembic heads` on this tree reports `be4d11f03666`, two revisions ahead (`4cb74877e4ba`, source-license fields; `be4d11f03666`, scenario-status/id widening). Neither of the two missing migrations touches `editorial_approvals` or `basis_ref`, so this does not change this gate's disposition, but it means `server/yuno.db` is presently behind the tree's actual migration head and should be re-migrated before any production seed run is attempted against it. `server/.e2e.db` remains several revisions further behind (`a9d4e6f1b208`), confirmed untouched by this work, with no `basis_ref_valid` constraint present — consistent with the task's framing that it is a separate, older-revision database not implicated in this change.
- **Two narrow, honestly-flagged gaps remain in `validate_basis_ref`** (checklist_completed_at's timestamp format; the nested review sub-fields' unconstrained result-value domain) — neither is required by §4's explicit five-item minimum-mechanical-validation list (`:73`), and the codebase has no reusable UTC-timestamp parser to build the first on. Flagged as residual risk for a future decision-version tightening (§10), not as a blocking finding against `editorial-approval-criteria-v1` as actually written.
- **This gate still cannot reach "inspection-passed" status.** The mechanism previous round's finding 1 blocked on is now shipped and independently verified; the only thing standing between this gate and a genuine "inspection-passed-pending-attestation" disposition is the absence of any production `editorial_approvals` row to inspect against §4 — which requires an actual IDK-102 production seed run, not further engineering work on this ticket's scope.
- `server/yuno.pre-idk010-partial.db`, a third local db file observed in `server/`, was not queried — out of scope per the previous round's note (predates IDK-010 work, unrelated to this gate), and this re-inspection found no reason to revisit that scoping.
