# IDK-503 (re-run, round 3) gate 3 — Source licensing, snapshot and withdrawal (CNT-04)

- Gate: Source licensing, snapshot and withdrawal (CNT-04)
- Reviewer role required: designated editorial approver
- Inspection date: 2026-08-15
- Disposition: blocking-finding
- Attestation: pending -- designated editorial approver has not signed this gate. No attestation was sought or recorded during this inspection.

This is a fresh, independent re-inspection of `main` at HEAD `7b805bd`, round 3 of the re-run. It is not an amendment of `docs/approvals/IDK-503/gate-3-sources-licensing.md` (2026-08-14) or `docs/approvals/IDK-503-rerun-2026-08-15/gate-3-sources-licensing.md` (round 2, HEAD `2621d29`) -- both are read only for scope recovery and neither is edited here; round 2's citations are stale by construction (line numbers shift once the frontend file is edited) and every claim below is re-derived from the tree as it stands today, not copied forward. The inspection below was originally carried out at `796fa306b6eb69745c4aad3b3a3ac64997c845d6`; see the "HEAD delta check" section immediately below the commit list for the explicit re-verification performed after HEAD moved to `7b805bd`.

Commits since round 2 (`git log 2621d29..HEAD`), assessed individually for whether they touch this gate:

- `bd05da6` (feat, B5, third-surface attribution) -- mine, inspected in depth.
- `5596654` (feat, B7, withdrawal production entry point) -- mine, inspected in depth.
- `796fa30` (fix, module-independence contract + `TopicTools` prop collapse) -- mine, a follow-up correction to the two commits above; inspected in depth. The task brief is explicit that the resources-tab rendering must be re-checked at this commit, not at `bd05da6`, because the prop shape changed afterward; done below.
- `cbd4c16` (fix, B17, onboarding target-level fail-closed) -- **not mine**. `git show --stat cbd4c16` touches only `src/selected/core/CorePages.tsx` (the onboarding/interview-bundle level `<select>`), `InterviewHub.test.tsx`, `ProfileGoalsPages.test.tsx`, `tests/e2e/harness.ts`, `tests/e2e/selected-app.spec.ts` -- none of it is `provenance`, sources, citations, or withdrawal. Confirmed out of scope for this gate.
- `0a6e7c9` (docs, `is_critical` exposure decision + ticket-status reconciliation) -- **not mine**. Touches `IMPLEMENTATION_TICKETS.md`, `docs/assessment/IDK-009-critical-dimension-exposure.md`, and `server/src/yuno/modules/evidence_evaluation/models.py` -- assessment/rubric domain, not `provenance`. Confirmed out of scope for this gate.

**Confirmed nothing else in the provenance surface moved.** `git diff 2621d29..796fa30 -- server/src/yuno/migrations/ server/src/yuno/modules/provenance/models.py server/src/yuno/modules/provenance/repository.py server/src/yuno/modules/provenance/adapters.py server/src/yuno/api/contracts.py server/src/yuno/api/routes/provenance.py` returns nothing. Only `provenance/service.py` (the `withdraw_source` grant check, `5596654`) and `CorePages.tsx`/its tests (`bd05da6`, `796fa30`, and unrelated `cbd4c16`) changed among files this gate's findings rest on. `server/src/yuno/api/provider_runtime.py` (excerpt-length validation, §12 item 5) is absent from the full `git diff --stat 2621d29..796fa30` file list entirely, confirming it is untouched.

**HEAD delta check (`796fa30` → `7b805bd`), performed explicitly rather than silently restamped.** One commit landed after this inspection began: `7b805bd`, "fix: three defects the round-3 gate inspections found," fixing findings gates 4, 5, and 7 raised -- not gate 3. Verified rather than assumed:

- `git diff 796fa30 7b805bd --stat` touches exactly four files: `docs/assessment/IDK-009-critical-dimension-exposure.md` (2 lines), `server/tests/integration/test_runner.py` (20 lines), `src/selected/core/CorePages.tsx` (11 lines), `src/selected/core/InterviewHub.test.tsx` (11 lines). The first two are gate 5/gate 7 territory (`is_critical` exposure, runner posture) -- not `provenance`, sources, citations, or withdrawal. `InterviewHub.test.tsx` covers the interview-bundle UI, not the Sources/Topic Studio surface this gate inspects.
- `git diff 796fa30 7b805bd -- server/src/yuno/modules/provenance/ server/scripts/ server/src/yuno/api/contracts.py` is **empty** -- B7's closure (migration, CHECK constraints, `withdraw_source`'s grant check, `scripts/withdraw_source.py`) and B4/B6's evidence (`SourceResponse` still lacking `withdrawal_reason`) are byte-identical to what was verified above and unaffected by this commit.
- `src/selected/core/CorePages.tsx`'s only change (`git diff -U0 796fa30 7b805bd -- src/selected/core/CorePages.tsx`) is inside `BundleEditor` (gate 4's target-level/bundle-name fix), a hunk inserting 4 lines after old line 815 and 1 more line after old line 858 -- both well below every citation this gate makes into `ArtifactProvenanceDetails` (lines 574-598), the `Topic`/`TopicTools` wiring (lines 690-782), and the resources-tab render itself, all of which sit at line 574-782, i.e. entirely before the shifted region. Re-read directly at `7b805bd`: lines 574, 576, 581, 586, 588-592, 692-696, 706, 709, 713, 718, 780-781 are byte-identical to what was cited above. The one citation that does shift is the Reports tombstone banner, previously at line 1089 (below the BundleEditor edit): `grep -n "Tombstoned source warning" src/selected/core/CorePages.tsx` now returns **line 1094** (+5, matching the two inserted-line counts summed). Both citations of `CorePages.tsx:1089` in this file (Finding 3 and Blocking finding 3) are corrected to `CorePages.tsx:1094` below.
- Re-ran the behavioral check, not just a diff check: `npx vitest run src/selected/TopicContent.test.tsx src/selected/core/ReportsPresentation.test.tsx` → **PASS (16) FAIL (0)**, identical result to the `796fa30` run.

**Conclusion: no finding, verdict, or disposition changes.** `7b805bd` is a gate-4/gate-5/gate-7 fix with no effect on source licensing, the registry, attribution rendering (beyond a line-number shift in one unrelated citation), the withdrawal/availability state machine, or which code paths can call `withdraw_source`. All findings below are stated as of `7b805bd` and were re-verified to hold at that commit, not merely carried forward from `796fa30` unexamined.

## Inspected artifacts

| Artifact | What it is | How inspected |
| --- | --- | --- |
| `server/yuno.db`, `server/.e2e.db` | Review-artifact SQLite DBs, read-only | `sqlite3 -readonly server/yuno.db "SELECT * FROM alembic_version;"` → `4747447ccaa3`; same on `.e2e.db` → `a9d4e6f1b208`; `SELECT count(*) FROM sources;` → `0` on both |
| Scratch DB migrated to head | `/private/tmp/.../scratchpad/gate3_scratch.db`, built fresh this round (`YUNO_DATABASE_URL=sqlite+pysqlite:////.../gate3_scratch.db uv run --directory server alembic upgrade head`) | Ran the full 28-revision chain cleanly to `be4d11f03666` (confirmed via `alembic heads`); used raw `sqlite3` INSERT/DELETE against the migrated `sources` table to independently re-verify every CHECK constraint and trigger the B7 migration (`4cb74877e4ba`) adds, rather than trusting round 2's record of the same exercise |
| `server/src/yuno/modules/provenance/service.py` | `withdraw_source` (lines 142-214) | Full read; verified the new grant check (lines 189-191) and its placement before any state read |
| `server/scripts/withdraw_source.py` | New offline editorial CLI (this round's B7 remainder fix) | Full read, all 175 lines |
| `server/src/yuno/modules/identity/domain.py` | `Role`, `RolePolicy` | Full read -- confirmed `RolePolicy.require` raises `RoleNotGrantedError` and no new `Role` value was added |
| `server/src/yuno/shared/domain/errors.py` | `RoleNotGrantedError` | Read lines 189-200 -- confirmed it subclasses `YunoError` (422), so the CLI's `except YunoError` catches it |
| `server/src/yuno/modules/canonical/publisher.py` | `publish_canonical_graph`'s D1 offline-publisher precedent | Read lines 59, 139-140 -- confirmed the grant-check pattern `withdraw_source` claims to mirror is real and identical (`uow.owners.grants` / `RolePolicy.require`) |
| `server/pyproject.toml` | import-linter contract config | Read lines 160-224; ran `uv run lint-imports` |
| `src/selected/core/CorePages.tsx` | `ArtifactProvenanceDetails` (lines 574-598), `TopicTools` resources tab (lines 709-782), `Topic` wiring (lines 690-706), Reports tombstone banner (line 1094) | Full read of every citation/source-rendering call site at HEAD `796fa30`, re-confirmed line-for-line at `7b805bd` (see HEAD delta check above; only the tombstone-banner line number shifted, 1089→1094) |
| `src/shared/use-topic-content.ts` | `useArtifactProvenance` | Read lines 31-46 |
| `src/selected/TopicContent.test.tsx` | Vitest coverage for the third surface | Full read; ran `npx vitest run src/selected/TopicContent.test.tsx src/selected/core/ReportsPresentation.test.tsx` |
| `server/src/yuno/api/contracts.py` | `SourceResponse` | Read lines 1135-1155 |
| `server/src/yuno/api/routes/provenance.py` | `_source()` helper, all `provenance` routes | Full read -- confirmed no route calls `withdraw_source` |
| `server/tests/integration/test_provenance_withdrawal.py`, `test_provenance_license_purge.py`, `test_provenance_availability_transitions.py`, `test_provenance_source_updates.py` | Withdrawal/purge/transition/CHECK tests | Ran together: `pytest` (see Tests run below) |
| `server/tests/integration/test_withdraw_source_script.py` | New file, drives `scripts/withdraw_source.py`'s `main()` directly via `importlib` | Full read, all 369 lines; ran standalone |
| `docs/decisions/IDK-003-source-licensing-and-snapshot-policy.md` | The decision under review | Full read (unchanged since round 2 -- it is an approved document and was not edited) |
| `scripts/check-review-records.mjs` | Mechanical scan of this gate file | Read -- confirmed its `ROUNDS` array now includes `docs/approvals/IDK-503-rerun-2026-08-15-b`, so this file will be scanned; this addition was present in the working tree before this inspection started and was not made by this inspection |

## Findings

### 1. B4 -- no production source registry: still fully open, unchanged

- `sqlite3 -readonly server/yuno.db "SELECT count(*) FROM sources;"` and the same on `server/.e2e.db` and on the freshly-migrated scratch DB all return `0`.
- `grep -rn "add_source(" server/ --include="*.py"` (excluding `.venv`) shows every non-test call site is `server/scripts/seed_performance_dataset.py:447`, the IDK-504 perf-harness fixture builder -- unchanged from round 2, still not a production registry-population path.
- `server/src/yuno/api/routes/provenance.py`, read in full: no route inserts a `sources` row.
- Verdict: **still blocking, unchanged.** Neither `bd05da6`, `5596654`, nor `796fa30` touches this.

### 2. B5 -- learner-facing attribution, third surface: the resources tab now genuinely carries five of six §7 fields, re-verified at `796fa30` (post prop-collapse), not at `bd05da6`

`bd05da6` wired `TopicTools`' resources tab to `ArtifactProvenanceDetails` via six new optional props with defaults (including a `new Map()` rebuilt every render). `796fa30` replaced that with one required `sourcesProvenance: ReturnType<typeof useArtifactProvenance> | null` prop, and every call site (`CorePages.tsx:706`, plus four test files) was updated to pass it explicitly -- confirmed by reading all five diffs (`git show 796fa30 --stat`: `CorePages.tsx`, `TopicContent.test.tsx`, `NotebookReview.test.tsx`, `TopicConversation.test.tsx`). No default remains on `sourcesProvenance` itself.

Wiring at HEAD (`CorePages.tsx:692-696, 706`): `sourcesLayer` is found from `topicContent.data?.layers`; `sourcesProvenance = useArtifactProvenance(sourcesLayer?.artifact_id ?? null)` is computed unconditionally (hooks can't be conditional), then gated to `null` at the call site (`CorePages.tsx:706`, `sourcesProvenance={sourcesLayer?.artifact_id ? sourcesProvenance : null}`) when there is no artifact yet -- so `TopicTools` itself never has to know about the artifact-id gate, it only checks its one prop for null (`CorePages.tsx:781`, `{sourcesProvenance && <ArtifactProvenanceDetails ... />}`).

**Field-by-field, re-read directly against `ArtifactProvenanceDetails` (`CorePages.tsx:574-598`), the same component this surface now reuses (no separate rendering logic was written for the resources tab):**

- **Publisher / title (fields 1-2).** `CorePages.tsx:586`, `citation.source.publisher ?? 'Publisher unavailable'` and `citation.source.title`. Present.
- **Canonical URL as a link (field 3, `IDK-003:96`).** `CorePages.tsx:588`, `citation.source.canonical_url && <div><dt>Canonical URL</dt><dd><a href={citation.source.canonical_url} target="_blank" rel="noreferrer">...</a></dd></div>`. Confirmed the null case is an omission via `&&` short-circuit, not a broken `href=""` anchor.
- **Retrieval timestamp (field 4, `IDK-003:97`).** `CorePages.tsx:589-591`: when `citation.source_snapshot_id === null`, renders the fixed fallback string; otherwise looks up `snapshotsById.get(citation.source_snapshot_id)` and renders `snapshot.retrieved_at` when found.
- **License identifier (field 5, `IDK-003:98`) -- deliberately absent, confirmed still unbuilt anywhere below the UI.** `grep -rn "PostgreSQL License|link-only, no reproduction|license_basis|resolved license|named basis" src/ server/src/` returns **zero matches**. `grep -n "license_status" src/selected/core/CorePages.tsx` also returns **zero matches** -- the raw `license_status` string is never read by this component at all, on any surface, so it can neither leak nor be resolved to a named basis. The commit message's own claim ("the resolved license identifier... remains out of scope") holds.
- **Version label (field 6, `IDK-003:99`).** `CorePages.tsx:592`, `snapshot?.version_label && <div>...</div>`, omitted when null rather than rendered blank.

**Tests, run fresh this round:** `npx vitest run src/selected/TopicContent.test.tsx src/selected/core/ReportsPresentation.test.tsx` → **PASS (16) FAIL (0)**. `TopicContent.test.tsx:125`, `it('renders IDK-003 §7 attribution alongside the Sources layer markdown on the resources tab (IDK-503 B5, third surface)', ...)`, asserts the canonical-URL link, the retrieval timestamp, the version label, the no-snapshot fallback string, and the absence of the raw `license_status`/tier strings, all against the resources tab specifically (not the generated-content panel). `TopicContent.test.tsx:153`, `it('omits the resources-tab attribution panel when the Sources layer has no artifact yet', ...)` -- this is the test `796fa30`'s commit message says it strengthened; confirmed by reading it: it now renders real `sourcesMarkdown` text with `sourcesProvenance={null}` (`TopicContent.test.tsx` diff in `796fa30`), so it exercises the artifact-absent branch inside the truthy-markdown path rather than the separate empty-tab branch a null `sourcesMarkdown` would take. Both assertions (`'Approved fixture sources for this topic.'` is shown, `'About this content'` is not) pass.

**Null `canonical_url` fallback gap -- still open, confirmed unchanged.** `IDK-003:101` requires fields 1-3 "for every citation without exception," but the code at `CorePages.tsx:588` omits the entire "Canonical URL" row when null rather than rendering any fallback. This is the same gap round 2 recorded and neither `bd05da6` nor `796fa30` touches it -- they reuse `ArtifactProvenanceDetails` unmodified in this respect.

**Verdict: partially closed, third-surface half now genuinely shipped.** Round 2's blocking finding 2 had three parts: (a) the license-identifier mapping does not exist below the UI, (b) the resources tab carried zero of the six fields, (c) the null-`canonical_url` fallback gap. This round's commits close (b) completely -- verified by direct code read and passing tests, not by taking the commit message's word -- and leave (a) and (c) exactly as they were. (a) and (c) are carried forward below as the residual half of blocking finding 2.

### 3. B6 -- `unavailable`/`withdrawn` undifferentiated copy: still open, unchanged, re-checked at current line numbers

Line numbers shifted since round 2 because `bd05da6`/`796fa30` added code above these call sites; re-derived fresh rather than trusting round 2's `579`/`1066`:

- `CorePages.tsx:581` (generated-content/provenance panel, now inside `ArtifactProvenanceDetails`): `` unavailableSources.map(source => `${source.title} is ${source.availability_status}`).join(' · ') `` -- one template string, `unavailableSources` (`line 576`) merges `unavailable` and `withdrawn` into one filtered list with no branch on which applies.
- `CorePages.tsx:1094` (Reports tombstone banner): `<strong>Tombstoned source warning: cited source withdrawn or unavailable</strong>` -- one combined header regardless of which state actually applies.
- `SourceResponse` (`server/src/yuno/api/contracts.py:1135-1145`) still declares no `withdrawal_reason`/`superseded_by_source_id` field. `_source()` (`server/src/yuno/api/routes/provenance.py:43-44`, `SourceResponse(**{k: v for k, v in s.__dict__.items() if k != "owner_id"})`) still silently drops both rather than erroring -- unchanged, confirmed by direct read this round.
- Verdict: **still blocking, unchanged.** None of this round's three commits touches either rendering line or `SourceResponse`.

### 4. B7 -- explicit withdrawal now has a real, independently-verified production entry point; the purge fires end-to-end through it

**`server/scripts/withdraw_source.py` (new, 175 lines) is the CLI.** Modeled explicitly on `scripts/publish_canonical.py`'s D1 offline-publisher lane -- verified the analogy is real, not asserted: `canonical/publisher.py:139-140` performs the identical `uow.owners.grants(actor_owner_id)` / `RolePolicy.require(grants, Role.DESIGNATED_EDITORIAL_APPROVER)` sequence the new code claims to mirror. `require_single_head(engine)` is called in the script (`withdraw_source.py:142`) before `create_session_factory`/`create_unit_of_work_factory` are ever built -- confirmed by reading the ordering, and confirmed behaviorally (see tests below). No FastAPI import, no route: `grep -rn "withdraw_source" server/src/yuno/api/` returns nothing.

**Grant check moved into `withdraw_source` itself, not just the CLI (`provenance/service.py:189-191`):**
```python
grants = uow.owners.grants(owner_id)
RolePolicy.require(grants, Role.DESIGNATED_EDITORIAL_APPROVER)
```
placed before `uow.provenance.get_source` is even called, i.e. before any read or write of the target source. `RolePolicy.require` (`identity/domain.py:50-53`) raises `RoleNotGrantedError` when the role is absent; `RoleNotGrantedError` (`shared/domain/errors.py:189`) is a `YunoError` subclass with `http_status = 422`, so it fails closed -- there is no code path where a missing grant is silently ignored or defaults to permit. No new `Role` value was added (`identity/domain.py:28-30` still declares exactly `LEARNER` and `DESIGNATED_EDITORIAL_APPROVER`), matching the commit message's "no new role vocabulary" claim.

**`--reason` accepts exactly IDK-003 §11's five values and no others.** `SourceWithdrawalReason` (`provenance/domain.py:15-20`): `license-revoked`, `license-changed-incompatible`, `publisher-retracted`, `factually-superseded`, `registry-declined` -- matches `IDK-003:169-173` verbatim. `withdraw_source.py:124-132` constructs `SourceWithdrawalReason(args.reason)` inside a `try/except ValueError`, printing to stderr and returning exit code 2 (usage error) for anything else, rejected before the service layer is ever called.

**Migration/CHECK constraints, re-verified this round against a freshly-built scratch DB (not round 2's DB, not `server/yuno.db`, which is still behind head at `4747447ccaa3`, two revisions short of head `be4d11f03666`; `server/.e2e.db` is further behind at `a9d4e6f1b208`):**
- `INSERT ... availability_status='withdrawn', withdrawal_reason=NULL` → `CHECK constraint failed: ck_sources_withdrawal_reason_required_iff_withdrawn`.
- `INSERT ... availability_status='available', withdrawal_reason='license-revoked'` → same CHECK failure (the biconditional blocks both directions).
- `INSERT ... availability_status='withdrawn', withdrawal_reason='license-revoked'` → succeeds.
- `INSERT ... license_status='fixture-approved'` → `CHECK constraint failed: ck_sources_license_status_valid` (closed vocabulary enforced at the DB level).
- `INSERT ... withdrawal_reason='not-a-real-reason'` (with `availability_status='withdrawn'`) → `CHECK constraint failed: ck_sources_withdrawal_reason_valid`.
- `DELETE FROM sources WHERE id='s3'` → `sources are retained` (`trg_sources_no_delete`).
- Re-`INSERT`ing the same `id='s3'` → `source replacement is not permitted` (`trg_sources_no_insert_replace`).
All seven checks match the CHECK/trigger definitions read directly from `.schema sources` on the scratch DB and match round 2's record of the same migration -- independently reproduced this round, not copied forward.

**Tests run this round:**
- `pytest tests/integration/test_provenance_withdrawal.py tests/integration/test_provenance_license_purge.py tests/integration/test_provenance_availability_transitions.py tests/integration/test_provenance_source_updates.py -q` → **34 passed** (round 2 recorded 33 on the same four files; the delta is `test_provenance_withdrawal.py`'s new `test_withdrawal_is_refused_when_the_actor_lacks_the_approver_grant`, added by `5596654`, which asserts a learner-only owner is refused with `RoleNotGrantedError` and the source is left `available` with `withdrawal_reason is None` -- the grant check's negative case).
- `pytest tests/integration/test_withdraw_source_script.py -v` → **7 passed**. This file (`server/tests/integration/test_withdraw_source_script.py`, new, 369 lines) loads the script via `importlib` and drives `main()` directly against a real migrated scratch database (`tests/conftest.py`'s `migrated_database_url` fixture) -- never `server/yuno.db`/`.e2e.db`. Coverage read directly, not taken on faith:
  - `test_license_revoked_withdrawal_purges_body_and_retains_snapshot_metadata` -- creates a source + a snapshot with a real `source_snapshot_bodies` row, calls `main([...,"--reason","license-revoked",...])`, asserts the body-pointer row count drops from 1 to 0 while `source_snapshots` metadata (`content_hash`/`retrieved_at`/`status`) is retained, and the source is `WITHDRAWN` with `withdrawal_reason.value == "license-revoked"`. This is the purge firing **through the CLI's `main()`**, not through a direct `withdraw_source` call -- the specific gap round 2 identified.
  - `test_non_license_reason_withdrawal_leaves_body_intact` -- `publisher-retracted` through the same CLI path leaves the body pointer row count at 1, proving the reason-gate applies end-to-end through the script too.
  - `test_withdrawal_with_superseded_by_source_id_records_lineage` -- old→new lineage via `--superseded-by-source-id`, confirms the new row is untouched (`AVAILABLE`).
  - `test_withdrawal_refused_when_actor_lacks_the_grant_exits_1` -- learner-only owner via the CLI → exit code 1, stderr contains `[role_not_granted]`, source left `AVAILABLE`/`withdrawal_reason is None`.
  - `test_withdrawal_of_a_missing_source_exits_1`, `test_unrecognized_reason_value_exits_2` -- exit codes 1 and 2 respectively, matching the documented exit-code contract.
  - `test_unmigrated_database_exits_1_via_require_single_head` -- points `--database-url` at the deliberately-unmigrated `database_url` fixture (not `migrated_database_url`), proving `require_single_head` is wired into the CLI and fires before any session opens, not merely documented in the module docstring.

**import-linter, re-run this round:** `uv run lint-imports` → `Contracts: 4 kept, 0 broken.` `server/pyproject.toml:178-186` adds a comment explaining the new edge and `:211`, `"yuno.modules.provenance.service -> yuno.modules.identity.**"`, added to `ignore_imports` -- confirmed present and the contract passes with it. This is the fix `796fa30` shipped after `5596654` broke the "Module independence" contract by having `provenance.service` import `identity.domain` without the corresponding `ignore_imports` entry (the commit message states `lint-imports` reported "3 kept, 1 broken" before the fix; re-running now shows 4/0, i.e. the fix holds).

**Verdict: closed.** Round 2's blocking finding 4 ("explicit source withdrawal -- and the purge it gates -- has no production entry point") is resolved: a real, non-test caller of `withdraw_source` exists (`server/scripts/withdraw_source.py`), the grant check is real and fails closed, the CLI honours exactly IDK-003 §11's five `withdrawal_reason` values, and the license-revocation purge is proven to fire end-to-end through that caller by a dedicated integration test that never calls `withdraw_source` directly. This is the strongest closure of any finding in this gate this round -- every claim in the commit messages was independently reproduced (migration DDL against a fresh scratch DB, both pytest files, `lint-imports`), not taken on the commits' word.

## Other §12 items (not in scope for this round's commits; reported for completeness)

| Item | Requirement | Status | Evidence |
| --- | --- | --- | --- |
| §12 item 3 | Tier A/B branching in `HttpSourceRetrievalAdapter.retrieve` | **Not shipped, unchanged** | `git diff 2621d29..HEAD -- server/src/yuno/modules/provenance/adapters.py` is empty |
| §12 item 5 | 400-character excerpt cap on `CitationPayload`/`ClaimPayload` | **Not shipped, unchanged** | `server/src/yuno/api/provider_runtime.py` does not appear anywhere in `git diff --stat 2621d29..HEAD` |
| §12 item 9 (staleness) | 180-day re-check job | **Not shipped, unchanged** | Same -- no `provenance` module file implementing it changed |
| §12 item 9 (janitor) | 20-per-source retained-snapshot janitor | **Not shipped, unchanged** | `adapters.py` unchanged per the diff above |

## Blocking findings

### 1. No production source registry exists -- every shipped claim would still be fixture-sourced
- Missing: any `sources`/`source_snapshots` row outside test fixtures and the IDK-504 perf-dataset seed script; a real registry-population path per §12 item 7.
- Owning ticket: none, per decision doc §12's own preamble ("IDK-201/IDK-207/IDK-404/IDK-408 (or a dedicated `provenance` follow-up ticket)"). None has shipped it.
- Evidence of absence: `sqlite3 -readonly server/yuno.db "SELECT count(*) FROM sources;"` → `0`; same on `server/.e2e.db` and the fresh scratch DB; `server/scripts/seed_performance_dataset.py:447` is the only non-test `add_source(` call site and is itself fixture-shaped.
- What would clear it: ship §12 item 7 (a real seed/publish step attributed to a content-owner role, replacing every test-only `add_source` call site) and re-run this gate against the resulting rows.

### 2. Learner-facing attribution: license identifier field remains unbuildable and the null-canonical_url gap remains (third-surface half closed this round)
- Missing: (a) any resolved-license-basis mapping anywhere in the schema, contracts, or API for §7 field 5; (b) a fallback for a null `canonical_url` despite §7 field 3 being "required... without exception" (`IDK-003:101`).
- Not missing anymore, closed this round: the `TopicTools` resources tab (`CorePages.tsx:709-782`) now renders `ArtifactProvenanceDetails` for the Sources layer's own artifact and carries fields 1, 2, 3, 4, and 6 of §7, verified against passing tests (`TopicContent.test.tsx:125`) -- this closes the "third surface carries none of the six fields" half of round 2's finding 2.
- Owning ticket: IDK-201/IDK-207 per decision doc §12.8 for the surfaces; no ticket currently owns supplying the named license basis itself, since that requires a `license_status` → §4 registry "License basis (named)" mapping that exists nowhere in the codebase.
- Evidence of absence: `grep -rn "PostgreSQL License|link-only, no reproduction|license_basis|resolved license|named basis" src/ server/src/` returns nothing; `grep -n "license_status" src/selected/core/CorePages.tsx` returns nothing (confirms the raw string is never even read by the frontend, on any of the three surfaces); `CorePages.tsx:588` omits the entire "Canonical URL" row rather than rendering any fallback when `canonical_url` is null.
- What would clear it: build the license-basis-resolution data path (schema → contract → API → frontend) for field 5; add fallback wording for a null `canonical_url` or amend the decision (a new decision version, since it is approved and immutable per §14) to explicitly permit omission.

### 3. `unavailable` and `withdrawn` render with shared/undifferentiated copy, and the API contract still cannot support reason-aware copy
- Missing: distinct learner-facing copy per §8's "different facts" requirement; a `withdrawal_reason` field on `SourceResponse` for the frontend to key differentiated copy on.
- Owning ticket: IDK-201/IDK-207 per decision doc §12.8.
- Evidence of absence: `CorePages.tsx:581` (one template string keyed only on the interpolated `availability_status` word) and `CorePages.tsx:1094` (one combined "withdrawn or unavailable" header); `SourceResponse` (`server/src/yuno/api/contracts.py:1135-1145`) declares no `withdrawal_reason` field, and `_source()` (`server/src/yuno/api/routes/provenance.py:43-44`) silently drops it from the domain object rather than surfacing it, unchanged since round 2.
- What would clear it: two distinct copy templates per §8, backed by exposing `withdrawal_reason` through `SourceResponse` if reason-aware copy is desired; re-inspect against shipped strings.

## Notes and residual risk

- **This round closed round 2's blocking finding 4 outright** (explicit withdrawal now has a real, tested, fail-closed production entry point with the purge proven to fire end-to-end through it) and **closed the "third surface" half of round 2's blocking finding 2** (the resources tab now carries five of the six §7 fields, tested). Both closures were independently re-verified this round -- fresh migration replay, fresh pytest runs (34 + 7 passed), fresh `lint-imports` run, fresh `grep` searches -- not accepted on the commit messages' word. One genuine defect was caught and fixed within this round's own work before this inspection: `5596654` broke the import-linter "Module independence" contract, and `796fa30` fixed it with a scoped `ignore_imports` entry; `lint-imports` now reports 4/0.
- `docs/decisions/IDK-003-source-licensing-and-snapshot-policy.md` remains approved and was **not edited** by this inspection, per the hard rule against editing an approved decision document. It still records, at §6's "License-revocation purge" row, "Not implemented — no purge-by-license-event path exists," which is now stale text given `withdraw_source`'s purge is real and production-reachable as of this round -- recorded here as an observation only, not corrected in the document itself.
- Because zero `sources` rows exist in production-shaped form in either real database, none of this gate's positive findings (constraint correctness, grant-check correctness, join correctness, test passage) constitute evidence of compliant *shipped, populated* behavior -- they are evidence the mechanism is correct when exercised, which is a narrower claim. Blocking finding 1 (no registry) remains the dominant blocker: nothing in §12 items 3, 5, or 9 (also unshipped, see table above) or the license-identifier gap can be fully assessed against real data until real rows exist.
- Not independently re-verified this round: the Playwright e2e assertions in `tests/e2e/selected-app.spec.ts` that cover the generated-content attribution surface (unrelated to this round's changes, and `tests/e2e/selected-app.spec.ts` was touched only by the unrelated `cbd4c16` this round, not by any gate-3 commit) -- consistent with the task's test list, which does not name a Playwright target for this gate this round.
- This gate cannot reach `inspection-passed-pending-attestation`: three independent blocking findings remain (registry, attribution completeness for the license identifier and null-URL cases, and withdrawal-copy differentiation), on top of §12 items 3, 5, and 9 still outstanding. Re-inspection is required after the owning tickets close before this gate can be re-attempted.
