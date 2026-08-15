# IDK-503 — Consolidated content-and-safety approval review (RE-RUN, round 3)

- Review date: 2026-08-15
- Scope: the same seven content-and-safety gates IDK-503 names, checked against PRD Appendix C's six threat/limitation rows, re-inspected fresh against the tree as it stands today.
- Per-gate evidence: `docs/approvals/IDK-503-rerun-2026-08-15-b/gate-1-curriculum-boundary.md` … `gate-7-runner-posture.md`.
- Mechanical field scan: `node scripts/check-review-records.mjs`.

## What this record is, and what it is not

This is a **re-run of IDK-503, not an amendment.** The 2026-08-14 round (`docs/approvals/IDK-503-content-and-safety-review.md`, gates under `docs/approvals/IDK-503/`) and the earlier 2026-08-15 round (`docs/approvals/IDK-503-content-and-safety-review-rerun-2026-08-15.md`, gates under `docs/approvals/IDK-503-rerun-2026-08-15/`) stand untouched and are superseded by nothing here. This document stands beside both as an independent, later inspection of a tree that has since moved again.

**Two rounds now share the date 2026-08-15.** A round is identified by the tree it inspected, not by the calendar day; the previous round is bound to `2621d29` and this one to `7b805bd`. The `-b` suffix on this record and its gate directory exists solely to keep two same-day rounds addressable as separate artifacts, and the `ROUNDS` array in `scripts/check-review-records.mjs` carries both.

Each of the seven gates below was walked again from scratch against the artifact actually shipped today — database rows (read-only queries, never a write to `server/yuno.db` or `server/.e2e.db`), source lines, migrations replayed on disposable scratch databases, and named tests actually executed. The prior rounds' gate files were consulted only to recover scope, never as a source of citations; every line number, row count and test result below was re-derived. Where a decision's requirement is not shipped, or is shipped only in part, that is recorded as a finding against the owning ticket rather than softened.

It grants **no approval**. IDK-503's approvals belong to the designated editorial approver (gates 1–5), the product/privacy owner (gate 6), and the security/engineering owner (gate 7). Every gate below is `pending` on that signature. No checkbox in this document is checked, and no gate's disposition reads `approved`.

**How the seven gates were brought to one commit, stated rather than smoothed over:** all seven were first inspected at `HEAD = 796fa30`. `7b805bd` then landed, fixing three defects these very inspections found (see "Findings this round raised and closed within it"). Rather than publish a record spanning two commits, or restamp the gates silently, **every one of the seven re-checked itself against `7b805bd` explicitly** and carries a "HEAD delta check (`796fa30` → `7b805bd`)" section recording what it examined, what it re-derived, and what it re-ran. That pass was not cosmetic: it corrected two stale line-number citations that the delta had shifted (gate 1's `CorePages.tsx:1004` → `:1009`, gate 3's `CorePages.tsx:1089` → `:1094`), re-ran the behavioural evidence in gates 3, 4, 5 and 7, and produced two closures (gates 4 and 7) that the gates reached by judging the fixes on their merits rather than accepting them. All seven therefore state `HEAD = 7b805bdd72d5740eb8180f3e6fde9c33af2a672f`.

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

One gate reached inspection-passed. Six did not — the same split as both prior rounds, though gate 3 drops from four blocking findings to three, gate 4 and gate 7 each closed a finding, and gate 2 gained one.

## Database state — stated plainly so it is not mistaken for current

Both inspectable databases are **inspection artifacts, not production, and neither reflects the shipped schema**. Neither moved this round, because this round adds no migration:

- `server/yuno.db`: `alembic_version` = `4747447ccaa3`, still two revisions behind the code's head `be4d11f03666` (`4747447ccaa3 → 4cb74877e4ba → be4d11f03666`).
- `server/.e2e.db`: `alembic_version` = `a9d4e6f1b208`, further behind still.

Every gate's DB-level verification (CHECK constraints, triggers, schema shape) was therefore done against **disposable scratch databases** built fresh with a real `alembic upgrade head` run under each gate's own scratchpad path — never against `server/yuno.db` or `server/.e2e.db`, per the hard rule against writing to either file. Content-table row counts are `0` across the board in both real databases: `topics`, `topic_relations`, `canonical_graph_versions`, `editorial_approvals`, `content_revisions`, `sources`, `source_snapshots`, `rubrics`, `rubric_dimensions`, `hands_on_work` (all zero rows). No production content has ever been published.

## What changed since the previous round

Six commits landed between `2621d29` and `7b805bd` (oldest first; `570b6e2`, a Serena config check-in, touches no reviewed surface):

1. **`0a6e7c9`** — "record the `is_critical` exposure decision and reconcile four ticket statuses." Recorded, in `docs/assessment/IDK-009-critical-dimension-exposure.md`, an engineering decision **not** to expose `is_critical` in any API contract or client type, answering a question the previous round's gate 5 left with the approver. Corrected a comment in `evidence_evaluation/models.py` that cited a `rubric_dimensions.is_critical` column which deliberately does not exist. Reconciled `IMPLEMENTATION_TICKETS.md`: IDK-204, IDK-302, IDK-303 and IDK-405 moved from `Complete` to a newly-defined `Content incomplete`, each naming the specific records it is missing.
2. **`bd05da6`** — "render IDK-003 §7 attribution on the resources tab." **Closed the third-surface half of B5**: `TopicTools`' resources tab now renders `ArtifactProvenanceDetails` against the Sources layer's own artifact, reusing the already-approved rendering rather than introducing copy.
3. **`cbd4c16`** — "require an explicit target level at first-use setup." **Closed B17**: onboarding's level state starts genuinely unselected and submission is gated on an explicit choice; `BundleEditor`'s recommended-bundle creation no longer hardcodes `Senior`.
4. **`5596654`** — "give source withdrawal a production entry point." **Closed B7**: `server/scripts/withdraw_source.py`, an offline editorial CLI in the same D1 lane as `publish_canonical.py`, plus a `designated_editorial_approver` grant check inside `withdraw_source` itself so no future caller can bypass it.
5. **`796fa30`** — "restore the module-independence contract and drop the `TopicTools` prop defaults." Repaired an import-linter contract that `5596654` broke, and removed six optional-with-defaults props that had been added so test call sites would compile.
6. **`7b805bd`** — "fix three defects the round-3 gate inspections found." See below.

Each gate re-confirmed independently, rather than assuming from commit messages, that none of these publishes a canonical graph, writes a production `editorial_approvals` row, populates the `sources`/`rubrics`/`hands_on_work` registries with real content, or resolves B15's per-row Appendix C copy question.

### Findings this round raised and closed within it

This round is unusual in that three of its own inspections found defects that were then fixed and re-judged by the same inspections before the record closed. Recorded explicitly so the sequence is not mistaken for a clean first pass:

- **B22 — `BundleEditor.createBundle` shipped unreviewed learner-facing copy.** Gate 4 found that `cbd4c16`'s own fix had introduced it: the bundle name interpolated the chosen level, so `'Mid-level backend interview'` and `'Staff backend interview'` were sentences no decision document had reviewed, and the `Staff` case used the bare stored enum rather than the approved `Staff-level` label wording. Gate 4's two suggested remedies both ended at "obtain editorial sign-off." `7b805bd` took neither: the product now generates no name at all, the empty state asks the learner for one, and creation is gated on it. Gate 4 re-judged and closed it — while explicitly declining to credit the fix with "extending IDK-004 compliance," since requiring a name is orthogonal to §4's level rule.
- **B23 — the B14 regression test's zero-SQL assertion was flaky.** Gate 7 found `test_retired_relational_language_rejected_before_route_or_uow`'s `assert statements == []` failing 3 of 6 runs, and independently reproduced the mechanism outside pytest: the listeners attach to the app-wide engine, which `DurableJobDispatcher`'s `jobs-<lane>` threads also use, so their queue polling was attributed to the request under test. B14's functional claim was never in doubt — `uow_calls == 0` held in all 38 of gate 7's attempts. `7b805bd` excludes those threads by name. Gate 7 re-judged the fix on its merits (confirming the excluded population is disjoint from any path the route could run on, so a real defect cannot be masked) and measured 20/20 isolated runs plus 3/3 full-file runs at 45/45 against its own ~40% pre-fix failure rate.
- **Two citation errors in `0a6e7c9`'s own decision record.** Gate 5 found `models.py:401` should read `:406` — the same commit had lengthened the comment above the line it cited — and that "read by exactly one consumer" undercounted three plumbing read-sites. `7b805bd` corrected both; gate 5 re-derived the corrections independently and confirmed them.

## Findings register

### Still open (or newly found)

| # | Gate | Finding | Owning ticket | Status |
| --- | --- | --- | --- | --- |
| B1 | 1 | No production `canonical_graph_versions` row exists; CUR-01 boundary and CUR-02 graph-absence have no shipped artifact to review against | IDK-102 (production seed run) | still open |
| B3 | 2 | No production `editorial_approvals` row exists to inspect against §4's mechanically-enforced criteria | IDK-102 (production seed run) | still open |
| B4 | 3 | No production source registry; every shipped claim traces to a test fixture or the IDK-504 perf-dataset seed script (itself fixture-shaped) | unassigned — IDK-003 §12 names IDK-201/207/404/408 or a dedicated provenance follow-up | still open |
| B5 | 3 | Resolved license identifier still unbuildable (no named-basis mapping exists below the UI); the null-`canonical_url` fallback gap remains | IDK-201 / IDK-207 (the license-basis data path itself has no owner) | still open — **third-surface half closed this round** |
| B6 | 3 | `unavailable` and `withdrawn` render through one shared, undifferentiated copy template; `SourceResponse` still doesn't expose `withdrawal_reason` for a fix to key on | IDK-201 / IDK-207 | still open |
| B10 (content) | 4, 5 | Twelve approved IDK-009 hands-on/practice/mock scenario records not authored; every synthesized `HandsOnWork` row still hardcodes `scenario_status="fixture"` | IDK-405 | still open (schema half closed in the prior round) |
| B11 | 5 | No approved rubric manifests shipped (`hands-on-rubric-v1`, `practice-rubric-v1`, `mock-rubric-v1`) | IDK-204 (now `Content incomplete` in `IMPLEMENTATION_TICKETS.md` — the inconsistency the prior round flagged is resolved) | still open |
| B12 (content) | 5 | None of the twelve approved scenario records shipped as content (`scenario_id` exists structurally but holds nothing) | IDK-405 / IDK-302 / IDK-303 (all now `Content incomplete`) | still open |
| B15 | 7 | PRD Appendix C rows 3, 4 and 6 have no row-specific residual copy in-product; one generic disclaimer covers all six rows | IDK-406 — blocked on an owner decision (write per-row copy, or record that one consolidated disclosure is intended to subsume all six) | still open |
| B18 | 5 | `'approved'`, the `hands_on_work.scenario_status` literal, is an implementation naming choice with no decision text behind it | IDK-009 — needs the editorial approver's decision, not code | still open |
| B19 | 5 | Persisted classification literal remains `likely-known` (hyphen) across every layer where IDK-009 §2 specifies `likely_known` (underscore) | IDK-009 — needs the editorial approver's decision (accept the shipped spelling, or commission a coordinated multi-table rename) | still open |
| B20 | 6 | `018ecd8`'s Java-only migration bulk-deletes every `language='relational'` runner confirmation/record and its owned inputs/bodies/output chunks, outside any IDK-010 §6/§14.2 expiry schedule | none identified — needs the product/privacy owner's decision on whether to accept this as a named category | still open |
| B21 | 2 | `withdraw_source`'s grant check reuses `designated_editorial_approver` — D1/IDK-002's canonical-publication authority — to gate source withdrawal, an act IDK-003 attributes to a distinct content-owner role that IDK-003 §13 records as not existing. A cross-decision authority question is thereby settled in code rather than through either decision's change control | IDK-002 / IDK-003 — needs a decision-document action, not engineering work | **newly found** |

### Closed since the previous round

| Finding | Commit that closed it | Gate record that verified it |
| --- | --- | --- |
| B5 (third-surface half) | `bd05da6` | `gate-3-sources-licensing.md` |
| B7 | `5596654` (+ `796fa30`'s contract repair) | `gate-3-sources-licensing.md` |
| B17 | `cbd4c16` (+ `7b805bd`'s copy removal) | `gate-4-role-copy.md` |
| B22 (raised and closed within this round) | `7b805bd` | `gate-4-role-copy.md` |
| B23 (raised and closed within this round) | `7b805bd` | `gate-7-runner-posture.md` |

**On B21 specifically.** It is the direct consequence of closing B7, and the two cannot both be satisfied by engineering alone. IDK-003 §8 admits `withdrawn` "only by explicit editorial action"; the only editorial grant that exists in `owner_role_grants.role` is `designated_editorial_approver`; and IDK-003 §13 itself records that no distinct content-owner value exists. Adding one would be an unapproved vocabulary change under IDK-003 §14's change control, and removing the grant check would reopen B7 in a worse form. The implementation therefore used the only editorial authority available and this record names the consequence rather than absorbing it silently. Naming the correct authority is the approver's decision.

## PRD Appendix C — every row dispositioned

All six rows remain dispositioned against a **disabled** runner: `runner_enabled` is `False`, `policy_ready()` is `False`, `GET /runner/capabilities` reports `enabled: false`, and `runner_confirmations`/`runner_records` are empty in both databases. `docs/runner/IDK-406-execution-deferral.md`'s accepted-risk record (POSIX `rlimit`s instead of the IDK-007 cgroup/namespace/syscall-filter boundary) is unchanged by this round's commits and is not reopened here.

| PRD Appendix C row | MVP control — shipped? | Residual statement — labelled in-product? | Disposition |
| --- | --- | --- | --- |
| Shell injection | Yes. `subprocess.Popen(list(spec.argv), shell=False, ...)` (`adapters.py:137-139`); the version probe is likewise `shell=False` (`adapters.py:85-92`) | Yes (`HandsOnLab.tsx:102,116`) | Clear |
| Excess CPU/time/output | Yes, at the accepted-risk-adjusted level. `apply_limits()` sets `RLIMIT_CPU`/`RLIMIT_AS`(non-Darwin)/`RLIMIT_NPROC`/`RLIMIT_FSIZE` (`adapters.py:128-134`); the run loop enforces wall/output/temp budgets (`adapters.py:184-254`) | Yes, same generic string | Clear — already dispositioned by `IDK-406-execution-deferral.md` |
| File pollution | Yes. `LocalTempWorkspace.create`/`cleanup` (`adapters.py:111-121`) refuses to `rmtree` anything outside `gettempdir()` or lacking the `yuno-runner-` prefix | No row-specific copy anywhere in `src/` — only the generic string | Open (B15) |
| Environment/secrets leakage | Yes. `minimal_environment()` allowlists only `PATH`/`LANG`/`LC_ALL`/`TZ`, then strips any key matching the `_FORBIDDEN_ENV` markers (`service.py:264-273`, markers at `service.py:48-56`) | No row-specific copy — only the generic string | Open (B15) |
| Misleading validation | Yes. `RunnerOperation.COMPILE`/`TEST` are distinct (`domain.py:32-34`); static hands-on review never invokes the runner; `RUNNER_LIMITATION` surfaced at `service.py:105,129,696,740` | Yes, generic string plus `HandsOnLab.tsx:102`'s explicit runtime-separation clause | Clear |
| Orphaned process | Yes. `request_termination()` (`adapters.py:165-174`) sends `SIGTERM` via `os.killpg`, escalating to `SIGKILL` after 0.5s (`adapters.py:207-216`) | No standing row-specific copy — the one adjacent string (`HandsOnLab.tsx:105`) is a conditional cleanup-failure notice, not an unconditional disclosure | Open (B15) |

Relational absence (IDK-008) was re-verified empirically this round: `RunnerLanguage` admits only `java`; the retired `"language":"relational"` confirmation returns the standard `422` envelope with zero persisted rows; no connector credential/endpoint field exists anywhere in settings, contracts, persisted records, or generated client types. IDK-008 §4's requirement that RDB static reviews carry no-connection/no-runtime-proof clauses remains **vacuously unmet** — no RDB content exists yet to carry them.

## Blocking-question coverage (spec §12.3)

| Question | Gate | Status after inspection |
| --- | --- | --- |
| 1 Curriculum spine | 1 | Decision approved; implementation still unverifiable — nothing published |
| 2 Editorial policy | 2 | Decision approved; enforcement code shipped and re-verified; no production approval row exists to inspect it against (B3); the grant's scope is now itself in question (B21) |
| 3 Source policy | 3 | Decision approved; explicit withdrawal now has a production entry point and the license-revocation purge fires through it (B7 closed); attribution now ships on all three surfaces, but the resolved license identifier remains unbuildable (B5); no production source registry (B4) |
| 4 Role taxonomy | 4 | Decision approved; approved copy ships and first-use setup now fails closed to an explicit level (B17 closed); hands-on scenario content still unshipped (B10 content half) |
| 7 Runner posture | 7 | Decision approved; execution deferred per the accepted IDK-406 risk record (unchanged); per-row Appendix C residual copy still missing (B15) |
| 8 Database exercises | 7 | Decision approved; absence verified and holding, re-confirmed empirically this round |
| 9 Assessment design | 5 | Decision approved; rubrics still not shipped (B11); scenario content still not shipped (B12 content half); the `is_critical` exposure question is now settled by a recorded engineering decision |

Gate 6 additionally supplies inspection evidence toward questions 10 and 11, which IDK-010 policy 1.0 already settled.

## Observations that are not findings

- **IDK-003 §6 still reads "Not implemented — no purge-by-license-event path exists"** for the license-revocation purge, which now both ships and has a production caller. IDK-003 is an approved decision document and was **not** edited. Gates 3 and 6 both recorded this as a documentation-freshness observation for the approver.
- **A citation in the previous round does not check out.** Gate 5 found that round 2's gate-5 file cites "17 passed" for `test_evidence_evaluation.py`, but the file has had exactly 10 tests since a commit predating that round. Prior rounds stand untouched, so this is recorded here rather than corrected there — which is the point of re-running rather than amending.
- **Two open copy questions from gate 4, neither blocking.** The onboarding level `<select>`'s placeholder option carries an *empty label*, because no approved placeholder string exists and inventing one would itself breach the rule against fabricating learner-facing copy; the approver should decide whether to supply one or accept blank. Separately, IDK-004 §4's "Not sure" helper text ships nowhere, and the decision text is genuinely ambiguous about whether it was meant to render as on-screen copy at all.
- **A soft coupling introduced by B23's fix.** The `"jobs-"` thread-name prefix now appears in both `jobs_events/service.py` and `test_runner.py` with nothing enforcing they stay in sync. Gate 7 recorded it as minor and not a correctness problem today.

## Attestation

No signature has been given. Each line below is signed only by the named role, and only against the gate's own evidence file.

- [ ] **Designated editorial approver** — gates 1, 2, 3, 4, 5. Blocked: B1, B3, B4, B5, B6, B10 (content half), B11, B12 (content half) must close first. Additionally needs this approver's own decision — not engineering work — on B18 (the `'approved'` literal's missing decision backing), B19 (the `likely-known`/`likely_known` spelling mismatch and its cross-table blast radius), and B21 (which role may withdraw a source, given that IDK-003 §13 records the content-owner grant as non-existent). B17, which blocked the previous round, is now closed.
- [ ] **Product/privacy owner** — gate 6. Not blocked by a finding — this gate re-reached `inspection-passed-pending-attestation` fresh. Still requires the reviewer's own hands-on pass over a downloaded export package, a delete preflight/completion record, and a live rotated log file, per IDK-010 §10 (none of that evidence exists yet in this tree). Also needs a decision on B20, and awareness that the license-revocation purge — a named category under IDK-003 §6, not IDK-010 — is now reachable by an operator running an offline CLI while no API server is live, which gate 6 records as residual risk rather than a policy violation.
- [ ] **Security/engineering owner** — gate 7. Blocked: B15 must close, or be replaced by a recorded decision that one consolidated disclosure is intended to subsume all six Appendix C rows. B23 is closed.

## Re-review trigger

This review must be re-run, not amended, once the owning tickets close — in particular after IDK-102's production publish (clears B1/B3), IDK-204's rubric registry (clears B11), IDK-405's/IDK-302's/IDK-303's scenario-content load (clears B10/B12 content halves), a provenance follow-up covering the source registry (clears B4), and after B15, B18, B19, B20 and B21 each receive an owner decision. A gate's disposition here is bound to the tree inspected on 2026-08-15 at `7b805bdd72d5740eb8180f3e6fde9c33af2a672f`, for all seven gates, and carries forward to no later state.
