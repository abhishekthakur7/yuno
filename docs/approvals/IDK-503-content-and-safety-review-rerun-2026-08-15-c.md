# IDK-503 — Consolidated content-and-safety approval review (RE-RUN, round 4)

- Review date: 2026-08-15
- Scope: the same seven content-and-safety gates IDK-503 names, checked against PRD Appendix C's six threat/limitation rows, re-inspected fresh against the tree as it stands today.
- Per-gate evidence: `docs/approvals/IDK-503-rerun-2026-08-15-c/gate-1-curriculum-boundary.md` … `gate-7-runner-posture.md`.
- Mechanical field scan: `node scripts/check-review-records.mjs`.

## What this record is, and what it is not

This is a **re-run of IDK-503, not an amendment.** The three prior rounds stand untouched and are superseded by nothing here: 2026-08-14 (`docs/approvals/IDK-503-content-and-safety-review.md`, gates under `docs/approvals/IDK-503/`), the first 2026-08-15 round (`…-rerun-2026-08-15.md`, gates under `IDK-503-rerun-2026-08-15/`, `HEAD=2621d29`), and the second (`…-rerun-2026-08-15-b.md`, gates under `IDK-503-rerun-2026-08-15-b/`, `HEAD=7b805bd`). This document stands beside all three as an independent, later inspection of a tree that has moved again.

**Three rounds now share the date 2026-08-15.** A round is identified by the tree it inspected, not by the calendar day. The `-c` suffix on this record and its gate directory exists solely to keep same-day rounds addressable as separate artifacts, and the `ROUNDS` array in `scripts/check-review-records.mjs` now carries all four.

Each of the seven gates below was walked again from scratch against the artifact actually shipped today — disposable scratch databases built with a real `alembic upgrade head`, read-only queries against `server/yuno.db`/`server/.e2e.db` (never a write to either), source lines, and named tests actually executed. The prior rounds' gate files were consulted only to recover scope, never as a source of citations; every line number, row count and test result below was re-derived. Where a decision's requirement is not shipped, or is shipped only in part, that is recorded as a finding against the owning ticket rather than softened.

It grants **no approval**. IDK-503's approvals belong to the designated editorial approver (gates 1–5), the product/privacy owner (gate 6), and the security/engineering owner (gate 7). Every gate below is `pending` on that signature. No checkbox in this document is checked, and no gate's disposition reads `approved`.

**How the seven gates were brought to one commit.** All seven were first inspected at `HEAD = 825a01f`. Two further commits then landed — `636bf26` (five stale line citations this round's own commits invalidated) and `0f3219f` (a declaration-parity test restored to green). Rather than publish a record spanning three commits, or restamp the gates silently, **every one of the seven re-checked itself against `0f3219f` explicitly** and carries a "HEAD delta check (`825a01f` → `0f3219f`)" section recording what it examined, what it re-derived, and what it re-ran. That pass was not cosmetic: gates 2 and 5 independently re-derived the corrected citation targets and confirmed them; gate 5 found and corrected the identical drift inside its own file; gate 7 judged the `docs/runner/IDK-406-execution-deferral.md` edit on its merits and separately verified a *pre-existing* stale citation in the same sentence that this round deliberately did not touch; and gate 2 reproduced the round-3 test failure in a detached worktree at `93103cd` rather than accepting it as reported. All seven therefore state `HEAD = 0f3219f`.

## Gate dispositions

| # | Gate | Reviewer role | Disposition | Evidence |
| --- | --- | --- | --- | --- |
| 1 | Curriculum boundary (CUR-01/02/03) | designated editorial approver | blocking-finding | `gate-1-curriculum-boundary.md` |
| 2 | Editorial approval evidence and criteria (CORE-02/INT-02, D1) | designated editorial approver | blocking-finding | `gate-2-editorial-approvals.md` |
| 3 | Source licensing, snapshot and withdrawal (CNT-04) | designated editorial approver | blocking-finding | `gate-3-sources-licensing.md` |
| 4 | Learner-facing role copy and taxonomy | designated editorial approver | blocking-finding | `gate-4-role-copy.md` |
| 5 | Assessment scenarios and rubric versions (HND-03, DEP-03) | designated editorial approver | blocking-finding | `gate-5-rubrics-scenarios.md` |
| 6 | Size/retention and export/delete/logging lifecycle | product/privacy owner | inspection-passed-pending-attestation | `gate-6-privacy-lifecycle.md` |
| 7 | Runner posture and relational absence (RUN-03) | security/engineering owner | blocking-finding | `gate-7-runner-posture.md` |

One gate reached inspection-passed. Six did not — the same split as all three prior rounds. Gate 3 closes two mechanism halves and gains three new findings; gate 5 closes one mechanism half; gate 2's B21 widens.

## Database state — stated plainly so it is not mistaken for current

Both inspectable databases are **inspection artifacts, not production, and neither reflects the shipped schema**. Neither moved this round, because this round adds no migration — verified directly: `git diff --name-only 93103cd..0f3219f -- server/src/yuno/migrations/` is empty.

- `server/yuno.db`: `alembic_version` = `4747447ccaa3`, still two revisions behind the code's head `be4d11f03666`.
- `server/.e2e.db`: `alembic_version` = `a9d4e6f1b208`, further behind still.

Every gate's DB-level verification (CHECK constraints, triggers, schema shape) was therefore done against **disposable scratch databases** built fresh with a real `alembic upgrade head` under each gate's own scratchpad path — never against `server/yuno.db` or `server/.e2e.db`, per the hard rule against writing to either file. Content-table row counts remain `0` across the board: `sources`, `rubrics`, `rubric_dimensions`, `hands_on_work`, `canonical_graph_versions`, `topics`, `topic_relations`, `editorial_approvals`, `content_revisions`, `source_snapshots`. **No production content has ever been published, and none was published this round.**

## What changed since round 3

Six commits landed between `93103cd` and `0f3219f`, touching 15 files and no migration:

1. **`4493208`** — "give rubric manifest loading a production entry point." Adds `load_rubric_manifest` to `evidence_evaluation/service.py`, the offline CLI `server/scripts/load_rubric_manifest.py`, one import-linter `ignore_imports` entry, and 11 tests. **Closes the mechanism half of B11.**
2. **`90e23c3`** — "give source registration a production entry point." Adds `register_source` to `provenance/service.py`, the offline CLI `server/scripts/register_source.py`, and 10 tests. **Closes the mechanism half of B4** (IDK-003 §12 item 7).
3. **`2b5ebc2`** — "ship the 20-per-source snapshot janitor." Adds `prune_excess_snapshot_bodies` to `provenance/adapters.py`, wired into `api/app.py`'s hourly retention lane, and 7 tests. **Ships IDK-003 §12 item 9's janitor half**, with the qualification recorded as B24 below.
4. **`825a01f`** — "ship the 180-day source staleness re-check." Adds `sources_due_for_recheck` to `provenance/service.py`, a disclosure-gated sweep closure in `api/app.py`, and 12 tests. **Ships §12 item 9's cadence half**, with the qualification recorded as B25 below.
5. **`636bf26`** — corrects five stale line citations this round's own commits invalidated. See below.
6. **`0f3219f`** — restores `test_pyproject_declares_the_required_contracts` to green. See below.

Each gate re-confirmed independently, rather than assuming from commit messages, that none of these publishes a canonical graph, writes a production `editorial_approvals` row, populates the `sources`/`rubrics`/`hands_on_work` registries with real content, ships any learner-facing copy, or resolves B15's per-row Appendix C copy question.

**On the licensing position, stated because it is asymmetric.** The product owner has stated that the product does not pursue licence rights. On that basis IDK-003 §7 field 5 (the resolved licence identifier) and §12 item 3 (Tier A/B retrieve branching) were deliberately **not** built this round. This is recorded by gate 3 as reported context, not as verified fact, and it **does not close B5**: IDK-003 §7 and §4 remain approved, unamended text requiring a named licence basis. Closing that finding requires a content-owner decision-document change under §14, which no engineering session may make. The same stance does **not** remove IDK-003 §12 item 5's 400-character excerpt cap either, whose own approved rationale calls it "a product-policy ceiling, not a fair-use determination" grounded in PRD §9 (`PRD.md:235`, `PRD.md:407`) — see B29.

### Findings this round raised and closed within it

Three of this round's own checks found defects that were fixed and re-judged before the record closed. Recorded explicitly so the sequence is not mistaken for a clean first pass:

- **Five stale line citations, caused by this round's own commits.** `90e23c3`/`825a01f` inserted 74 lines ahead of `withdraw_source`, and `4493208` inserted five import lines, silently invalidating pointers in four files that cite them by line: `evidence_evaluation/service.py:939,950` (→ `provenance/service.py:270-271` and `:253-266`), `docs/assessment/IDK-009-critical-dimension-exposure.md:13` (→ `service.py:389`), `tests/integration/test_runner.py:351` (→ `api/app.py:1045`), and `docs/runner/IDK-406-execution-deferral.md:21` (→ `api/app.py:966`). Gate 2 and gate 5 each found one independently; a repo-wide sweep for citations of the three shifted files found the rest. Fixed in `636bf26`, citation text only, no line-count change. Gates 2, 5 and 7 re-derived every corrected number and confirmed all of them. Gate 7 additionally judged the `IDK-406-execution-deferral.md` edit legitimate: that document is `Status: recorded`, carries no attestation line, states it "amends no approved decision", and the edit touches one evidentiary clause in §2 and none of §1/§3/§4/§5 — the same class of repair `7b805bd` made last round.
- **A declaration-parity test that had been red since round 3.** `test_pyproject_declares_the_required_contracts` (`server/tests/architecture/test_import_boundaries.py`) asserts set equality between the `independence` contract's declared `ignore_imports` in `server/pyproject.toml` and a literal in the test. `796fa30` — **round 3's own contract repair** — added `provenance.service -> identity.**` to pyproject without declaring it here, so the test failed from round-3 HEAD onward; `4493208` repeated the omission this round with `evidence_evaluation.service -> identity.**`. `lint-imports` reported `4 kept, 0 broken` throughout, which is exactly why neither surfaced: the contract itself was never broken, only its declaration parity, and only a full-suite run reveals it. Verified rather than inferred — gate 2 reproduced `1 failed` in a detached worktree at `93103cd`. Fixed in `0f3219f`; `pytest tests/architecture/ -q` → 822 passed, re-run independently by gates 2, 3 and 7.
- **A batch-atomicity defect in `register_source`'s first draft**, caught before commit. `add_source` (`provenance/repository.py:44-54`) flushes the `SourceRow` but not the paired `SourceBodyRow`, and `get_source` treats a bodyless row as absent, so under the session's `autoflush=False` a same-batch duplicate id was reported as free and reached a raw SQLite trigger abort instead of a typed `ConflictError`. Fixed with batch-local id tracking (`provenance/service.py:311-319`) and covered by a test.

**What that second item implies is itself recorded, not smoothed over.** Gate 2 named the process gap rather than only crediting the fix: its own evidence, and round 3's, cited `lint-imports`'s summary line as proof the import-linter contract was intact, without ever running `pytest tests/architecture/` as a whole. That is why a red test could sit through an entire round unnoticed. Gate 2 files it as found-and-closed-within-this-round rather than a new blocking finding — the architectural decision was never wrong, only its declaration — and records "run the full architecture suite alongside `lint-imports`, not instead of it" as what prevents recurrence.

## Findings register

### Still open (or newly found)

| # | Gate | Finding | Owning ticket | Status |
| --- | --- | --- | --- | --- |
| B1 | 1 | No production `canonical_graph_versions` row exists; CUR-01 boundary and CUR-02 graph-absence have no shipped artifact to review against | IDK-102 (production seed run) | still open |
| B3 | 2 | No production `editorial_approvals` row exists to inspect against §4's mechanically-enforced criteria | IDK-102 (production seed run) | still open |
| B4 | 3 | No production source registry **content**; `sources` is still 0 rows and no manifest has been run | unassigned — IDK-003 §12 names IDK-201/207/404/408 or a dedicated provenance follow-up | still open — **mechanism half closed this round** |
| B5 | 3 | Resolved licence identifier still unbuildable under the current approved text; the null-`canonical_url` fallback gap remains | IDK-201 / IDK-207 | still open — see the licensing note above |
| B6 | 3 | `unavailable` and `withdrawn` render through one shared, undifferentiated copy template; `SourceResponse` still doesn't expose `withdrawal_reason` | IDK-201 / IDK-207 | still open |
| B10 (content) | 4, 5 | Twelve approved IDK-009 scenario records not authored; every synthesized `HandsOnWork` row still hardcodes `scenario_status="fixture"` | IDK-405 | still open |
| B11 | 5 | No approved rubric manifests shipped (`hands-on-rubric-v1`, `practice-rubric-v1`, `mock-rubric-v1`); `rubrics`/`rubric_dimensions` are 0/0 | IDK-204 | still open — **mechanism half closed this round** |
| B12 (content) | 5 | None of the twelve approved scenario records shipped as content | IDK-405 / IDK-302 / IDK-303 | still open |
| B15 | 7 | PRD Appendix C rows 3, 4 and 6 have no row-specific residual copy in-product; one generic disclaimer covers all six | IDK-406 — blocked on an owner decision | still open |
| B18 | 5 | `'approved'`, the `hands_on_work.scenario_status` literal, has no IDK-009 text behind it | IDK-009 — needs the editorial approver's decision | still open |
| B19 | 5 | Persisted classification literal remains `likely-known` (hyphen) where IDK-009 §2 specifies `likely_known` (underscore) | IDK-009 — needs the editorial approver's decision | still open |
| B20 | 6 | `018ecd8`'s Java-only migration bulk-deletes every `language='relational'` runner confirmation/record outside any IDK-010 §6/§14.2 expiry schedule | none identified — needs the product/privacy owner's decision | still open |
| B21 | 2, 5 | The `designated_editorial_approver` grant now gates three acts across three decisions | IDK-002 / IDK-003 / **IDK-009** — needs a decision-document action, not engineering work | still open — **widened this round** |
| B24 | 3 | The §6 "20 retained snapshots per source" janitor prunes snapshot **bodies**, not snapshot rows | IDK-003 — needs the approver's reading, or a decision-document clarification | **newly found** |
| B25 | 3 | §9's "immediately on crossing the §8 `unavailable` threshold" detection trigger is an argued reading of shipped behaviour, not a built or independently tested mechanism | IDK-003 / provenance follow-up | **newly found** |
| B26 | 3 | No committed test boots the real app and asserts on the two new `api/app.py` closures | provenance follow-up | **newly found** |
| B27 | 6 | One acceptance of a disclosure titled "Explicit authoritative source retrieval" now authorizes indefinitely recurring, unattended retrieval | IDK-010 / product-privacy owner decision | **newly found** |
| B28 | 7 | `docs/runner/IDK-406-execution-deferral.md:21` cites `runner/adapters.py:86` for `LocalRunnerProcessPort`, which is at `:124` — **pre-existing**, not caused by this round | IDK-406 (document owner) | **newly found** |
| B29 | 3 | IDK-003 §12 item 5's 400-character excerpt cap is unshipped **and unbuildable as written** — no verbatim-excerpt field exists on `CitationPayload`/`ClaimPayload` for a cap to apply to | IDK-201 / IDK-207 — needs a contract decision, not a validator | **newly found** |

### Closed since the previous round

| Finding | Commit that closed it | Gate record that verified it |
| --- | --- | --- |
| B4, mechanism half | `90e23c3` | `gate-3-sources-licensing.md` |
| B11, mechanism half | `4493208` | `gate-5-rubrics-scenarios.md` |
| IDK-003 §12 item 9, janitor half (subject to B24) | `2b5ebc2` | `gate-3-sources-licensing.md`, `gate-6-privacy-lifecycle.md` |
| IDK-003 §12 item 9, cadence half (subject to B25) | `825a01f` | `gate-3-sources-licensing.md`, `gate-6-privacy-lifecycle.md`, `gate-7-runner-posture.md` |
| Declaration-parity test red since round 3 (raised and closed within this round) | `0f3219f` | `gate-2-editorial-approvals.md` |
| Five stale line citations (raised and closed within this round) | `636bf26` | `gate-2`, `gate-5`, `gate-7` |

**On B21 specifically — it widened, and the widening is the point.** Round 3 raised B21 for `withdraw_source`'s reuse of `designated_editorial_approver`. Two more reuses landed this round. Gates 2 and 5 judged them separately rather than accepting the code's own "consolidates under B21" framing, and reached the same split:

- `register_source` **does** consolidate. It gates an IDK-003 §12 item 7 act, and IDK-003 §13 itself explicitly records that no distinct content-owner grant exists — the same decision, the same textual admission, the same remedy.
- `load_rubric_manifest` **does not fully consolidate.** It gates an IDK-009 content act, and IDK-009 names a third role label ("content/assessment owner", `IDK-009:9`) while never mentioning `owner_role_grants`, "grant", or D1 anywhere in its text — unlike IDK-003 §13. Gate 5 put the asymmetry precisely: `withdraw_source`/`register_source` gate actions their *own* governing decision requires an editorial actor for; `load_rubric_manifest` gates an action under a decision that never engaged with the operational-grant question at all, and its docstring's appeal to "IDK-003 §14's change control" reaches outside the decision that clause governs.

The remedy is therefore two-part: an IDK-002/IDK-003 successor for the source acts, plus an IDK-009 successor or a second IDK-002 widening for the rubric-content act. Neither is engineering work. The alternative paths were both worse and were rejected deliberately: inventing a role value would be an unapproved vocabulary change under IDK-003 §14, and shipping ungated write paths would reopen the very finding the grant checks close.

**On B24 and B25 — where the shipped mechanism meets the decision text.** Both are qualifications on work that genuinely shipped, recorded so a future round is not misled by "§12 item 9 is done":

- **B24.** §6's row reads "Retained snapshots per source: 20, oldest-first pruning among snapshots with no live `citations.source_snapshot_id` reference." `source_snapshots` rows cannot be deleted at all — gate 3 verified this empirically on a scratch database, where `DELETE FROM source_snapshots` raises `source_snapshots header is immutable` (from the trigger `e10d1a0c0100` recreated, not `6ee79a009c2a`'s original) while `DELETE FROM source_snapshot_bodies` succeeds. The janitor therefore prunes each excess uncited snapshot's persisted body and its content-addressed file, retaining the metadata row — the identical trade §6's own "License-revocation purge" row already makes. Gate 3's judgement: this satisfies §6's stated disk-growth rationale but not its literal 20-row wording. Recorded as the approver's reading to make, not resolved in code.
- **B25.** §9 names three detection triggers. The explicit-re-retrieval trigger ships (`POST /sources/{source_id}/retrieve`). The 180-day cadence now ships and is tested at the 179/180/181-day boundary. The "immediately on crossing the §8 `unavailable` threshold" trigger was argued — the crossing is itself the detection event — rather than built: no hash comparison occurs at that transition. Gate 3 declined to treat the argument as a shipped mechanism. The countervailing consideration is recorded too: scheduling a fresh retrieval immediately after three failures spanning ≥72h is either a no-op or an unbounded retry against a URL just proven dead, so building it is a policy call rather than plain engineering.

## PRD Appendix C — every row dispositioned

All six rows remain dispositioned against a **disabled** runner, re-verified empirically this round: `runner_enabled` is `False`, `policy_ready()` is `False`, `GET /runner/capabilities` reports `enabled: false`, and `runner_confirmations`/`runner_records` are empty. `docs/runner/IDK-406-execution-deferral.md`'s accepted-risk record (POSIX `rlimit`s instead of the IDK-007 cgroup/namespace/syscall-filter boundary) is unchanged in substance by this round's commits and is not reopened here.

| PRD Appendix C row | MVP control — shipped? | Residual statement — labelled in-product? | Disposition |
| --- | --- | --- | --- |
| Shell injection | Yes. `subprocess.Popen(list(spec.argv), shell=False, ...)` (`adapters.py:137-139`); the version probe is likewise `shell=False` (`adapters.py:85-92`) | Yes (`HandsOnLab.tsx:102,116`) | Clear |
| Excess CPU/time/output | Yes, at the accepted-risk-adjusted level. `apply_limits()` sets `RLIMIT_CPU`/`RLIMIT_AS`(non-Darwin)/`RLIMIT_NPROC`/`RLIMIT_FSIZE` (`adapters.py:128-134`); the run loop enforces wall/output/temp budgets (`adapters.py:184-254`) | Yes, same generic string | Clear — already dispositioned by `IDK-406-execution-deferral.md` |
| File pollution | Yes. `LocalTempWorkspace.create`/`cleanup` (`adapters.py:111-121`) refuses to `rmtree` anything outside `gettempdir()` or lacking the `yuno-runner-` prefix | No row-specific copy anywhere in `src/` — only the generic string | Open (B15) |
| Environment/secrets leakage | Yes. `minimal_environment()` allowlists only `PATH`/`LANG`/`LC_ALL`/`TZ`, then strips any key matching the `_FORBIDDEN_ENV` markers (`service.py:264-273`, markers at `service.py:48-56`) | No row-specific copy — only the generic string | Open (B15) |
| Misleading validation | Yes. `RunnerOperation.COMPILE`/`TEST` are distinct (`domain.py:32-34`); static hands-on review never invokes the runner; `RUNNER_LIMITATION` surfaced at `service.py:105,129,696,740` | Yes, generic string plus `HandsOnLab.tsx:102`'s explicit runtime-separation clause | Clear |
| Orphaned process | Yes. `request_termination()` (`adapters.py:165-174`) sends `SIGTERM` via `os.killpg`, escalating to `SIGKILL` after 0.5s (`adapters.py:207-216`) | No standing row-specific copy — the one adjacent string (`HandsOnLab.tsx:105`) is a conditional cleanup-failure notice, not an unconditional disclosure | Open (B15) |

Relational absence (IDK-008) was re-verified empirically: `RunnerLanguage` admits only `java`; the retired `"language":"relational"` confirmation returns the standard `422` envelope with zero persisted rows across four scratch-DB attempts; no connector credential/endpoint field exists anywhere in settings, contracts, persisted records, or generated client types. IDK-008 §4's requirement that RDB static reviews carry no-connection/no-runtime-proof clauses remains **vacuously unmet** — no RDB content exists yet to carry them. B23, the flaky zero-SQL assertion round 3 raised and closed, was re-measured at **30/30 isolated passes across two HEADs**.

## Correction to round 3's record

Round 3's gate 6 stated that `docs/privacy/IDK-010-policy-1.0-review-evidence.md` "does not exist in this tree." That is factually wrong: the file has existed since 2026-08-13, predating IDK-503's review entirely, and rounds 1 and 2 both acknowledged it correctly. Round 4's gate 6 read it in full and reached round 1's conclusion with accurate knowledge of the file — it does not satisfy this gate's attestation requirement, being self-recorded by the same engineering commit series, retaining no inspectable artifact, and scoped narrowly to the export-activation flag. The disposition is unaffected; only round 3's citation was wrong. **Round 3's record is not edited** — prior rounds stand untouched, so the correction lives here.

## Blocking-question coverage (spec §12.3)

| Question | Gate | Status after inspection |
| --- | --- | --- |
| 1 Curriculum spine | 1 | Decision approved; implementation still unverifiable — nothing published (B1) |
| 2 Editorial policy | 2 | Decision approved; enforcement code shipped and re-verified; no production approval row exists (B3); the grant's scope now spans three decisions (B21, widened) |
| 3 Source policy | 3 | Decision approved; registration, withdrawal, the licence-revocation purge, the snapshot janitor and the 180-day staleness cadence all now have production entry points; no registry content exists (B4), the licence identifier remains unbuildable under approved text (B5), and two mechanism qualifications are recorded (B24, B25) |
| 4 Role taxonomy | 4 | Decision approved; approved copy ships verbatim and no learner-facing copy entered the tree this round; hands-on scenario content still unshipped (B10) |
| 7 Runner posture | 7 | Decision approved; execution deferred per the accepted IDK-406 risk record; per-row Appendix C residual copy still missing (B15) |
| 8 Database exercises | 7 | Decision approved; absence verified and holding, re-confirmed empirically this round |

## What a future round should not re-derive from scratch

- **The scenario-loader premise is settled and negative.** There is no scenario registry table anywhere — no `__tablename__` declares one and no migration creates one — and the hands-on write primitive `add_work` already has a production caller (`hands_on/service.py:120`, via `prepare_submission`, reached from `api/routes/hands_on.py:159`). Gate 5 verified all three claims independently. A scenario loader is therefore not a missing-caller problem; it needs a new table whose `topic_binding_key → canonical topic stable ID` mapping IDK-009 §4 forbids inferring from prose and which IDK-405's Scope makes dependent on IDK-204 consuming IDK-102's published graph — i.e. blocked on B1.
- **The three registries' content halves are owner work, not engineering work.** The manifests, source rows and scenario records were deliberately not authored this round. Each loader ships with an offline CLI that consumes a manifest supplied by a content owner; none ships content.
