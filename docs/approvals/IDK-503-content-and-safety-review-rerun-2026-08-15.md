# IDK-503 — Consolidated content-and-safety approval review (RE-RUN)

- Review date: 2026-08-15
- Scope: the same seven content-and-safety gates IDK-503 names, checked against PRD Appendix C's six threat/limitation rows, re-inspected fresh against the tree as it stands today.
- Per-gate evidence: `docs/approvals/IDK-503-rerun-2026-08-15/gate-1-curriculum-boundary.md` … `gate-7-runner-posture.md`.
- Mechanical field scan: `node scripts/check-review-records.mjs`.

## What this record is, and what it is not

This is a **re-run of IDK-503, not an amendment.** The 2026-08-14 consolidated record (`docs/approvals/IDK-503-content-and-safety-review.md`) and its seven gate files under `docs/approvals/IDK-503/` stand untouched and are superseded by nothing here. This document stands beside that round as an independent, later inspection of a tree that has since moved.

Each of the seven gates below was walked again from scratch on 2026-08-15 against the artifact actually shipped at that time — database rows (read-only queries, never a write to `server/yuno.db` or `server/.e2e.db`), source lines, migrations replayed on disposable scratch databases, and named tests actually executed. The prior round's gate files were consulted only to recover scope, never as a source of citations. Where a decision's requirement is not shipped, or is shipped only in part, that is recorded as a finding against the owning ticket rather than softened.

It grants **no approval**. IDK-503's approvals belong to the designated editorial approver (gates 1–5), the product/privacy owner (gate 6), and the security/engineering owner (gate 7). Every gate below is `pending` on that signature. No checkbox in this document is checked, and no gate's disposition reads `approved`.

**How the seven gates were brought to one commit, stated rather than smoothed over:** gates 1, 2 and 3 were first inspected at `HEAD = 92f2a85`, while gates 4–7 were inspected at `HEAD = 2621d29` (one commit later — "resolve the local owner without opening a UnitOfWork," IDK-503 B14). Rather than publish a record spanning two commits, gates 1, 2 and 3 were each re-checked against `2621d29` explicitly, and each carries a "delta check" section recording what was examined and re-run rather than a silent restamp. All seven gates therefore state `HEAD = 2621d298f8f268d42ec6be94d454fa61d986f054`. The delta itself is one commit touching only `server/src/yuno/api/app.py`, `server/src/yuno/api/dependencies.py` and two test files; each of the three gates confirmed by diff that none of the files its findings rest on changed, and re-ran the tests those findings cite.

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

One gate reached inspection-passed. Six did not — the same split as the 2026-08-14 round, though the findings underneath five of the six blocking gates have moved.

## Database state — stated plainly so it is not mistaken for current

Both inspectable databases are **inspection artifacts, not production, and neither reflects the shipped schema**:

- `server/yuno.db`: `alembic_version` = `4747447ccaa3`. It was migrated during this work — but only as far as `c3409df`'s basis_ref-validation migration. It was **not** migrated to the code's actual head. The chain from its position to head is `4747447ccaa3 → 4cb74877e4ba → be4d11f03666`: it is missing `4cb74877e4ba` (`bf664e2`'s source-license/withdrawal migration) and `be4d11f03666` (`92f2a85`'s hands-on scenario-status/scenario-id migration), **two full migrations behind**, both already on `main`. This was confirmed structurally in multiple gates (not merely by reading `alembic_version`): `.schema sources` on this file shows no `withdrawal_reason`/`superseded_by_source_id` columns and the pre-widening `license_status` CHECK; `.schema hands_on_work` shows the pre-widening `scenario_status IN ('fixture')` CHECK with no `scenario_id` column.
- `server/.e2e.db`: `alembic_version` = `a9d4e6f1b208`, seven-to-eight revisions behind head depending on the counting gate (gate 5 counts eight edges to head; gate 7 and gate 1 describe it only as "further behind, untouched"). It predates `e10d1a0c0100` and was not written to by any commit in this window or by any gate's inspection.

Every gate's own DB-level verification (CHECK constraints, triggers, schema shape) was therefore done against **disposable scratch databases** built fresh with a real `alembic upgrade head` run under each gate's own scratchpad path — never against `server/yuno.db` or `server/.e2e.db` — per the hard rule against writing to either file. Content-table row counts are `0` across the board in both real databases: `topics`, `topic_relations`, `canonical_graph_versions`, `editorial_approvals`, `content_revisions`, `sources`, `source_snapshots`, `rubrics`, `rubric_dimensions`, `hands_on_work` (all zero rows). No production content has ever been published.

## What changed since the 2026-08-14 round

Seven commits landed between the two rounds (`git log --oneline`, oldest first as merged):

1. **`6bebd2f`** — "close the actionable IDK-503 findings and the two IDK-504 gaps." Closed the runner platform-detection gate (B16), the assessment outcome vocabulary and critical-dimension precedence rule (B13), and IDK-004 §2's learner-facing role copy plus the Interview Prep heading derivation (B8, B9). Left B15 (Appendix C per-row residual copy) explicitly open pending an owner decision.
2. **`c3409df`** — "implement basis_ref validation for editorial approvals." Closed B2: the `json_valid` CHECK constraint, the full §4 15-field schema validation, the `reviewed_manifest_hash` cross-check, and the `review_kind`/published-state consistency check, all independently re-verified against a database actually migrated to head plus a live rejected `INSERT` and two real `scripts/publish_canonical.py` executions against malformed manifests.
3. **`f4a204f`** — "surface `boolean_column` CHECK constraints at table level." Infrastructure-only fix in `server/src/yuno/shared/infrastructure/base.py`; touches no curriculum, editorial-approval, source, role-copy, rubric, privacy, or runner surface. No gate attributes any finding to it.
4. **`bf664e2`** — "give sources a real availability write path." **Partially closed B7** (see Partial closures below): the withdrawal/license migration, the `update_source` write primitive, the automatic 3-failure/≥72h `unavailable` transition (now production-reachable via `POST /sources/{id}/retrieve`'s real job lane), and the license-revocation purge primitive (verified correct at the DB level in both gate 3 and gate 6). Did not ship a production entry point for explicit withdrawal.
5. **`a9ee2a4`** — "render IDK-003 section 7 citation attribution inline." **Partially closed B5** (see Partial closures below): three of four previously-missing §7 fields now ship at the generated-content/provenance surface (canonical URL as a link, retrieval timestamp via a genuine snapshot join, version label) and two of those three also ship at the Reports/Evidence surface. The resolved license identifier does not ship, because it cannot yet be built.
6. **`92f2a85`** — "widen `scenario_status` and add `scenario_id` (schema only)." **Partially closed B10 and B12** (see Partial closures below): the `hands_on_work` CHECK now admits `'approved'` alongside `'fixture'`, and a nullable `scenario_id` column now exists, confirmed on a database actually migrated to head. No content was authored or loaded; the commit's own message states the scope is schema-shape only, and every gate that re-inspected it independently confirmed that framing checks out.
7. **`2621d29`** — "resolve the local owner without opening a UnitOfWork." **Closed B14** for the specific route IDK-008 names (`POST /runner/confirmations`): independently re-measured on a scratch database — zero UnitOfWork opens, zero SQL statements, zero pool checkouts — for the retired `"language":"relational"` request, which now fails closed with the standard `422` envelope before any database interaction. Confirmed systemic (115 call sites across 18 route files use the same `get_owner_id` dependency) and confirmed safe (no code path anywhere updates or deletes an `OwnerRow` within a process lifetime, so the cached id cannot go stale).

None of these seven commits touches a curriculum/canonical table, writes a production `editorial_approvals` row, populates the `sources`/`rubrics`/`hands_on_work` registries with real content, or resolves B15's per-row Appendix C copy question — each gate re-confirmed this independently rather than assuming it from the commit messages.

### Partial closures — precise, not softened

- **B5 (learner-facing attribution).** Shipped: canonical URL as a real link (with correct null-omission, not a broken `href`), the snapshot retrieval timestamp via a genuine per-citation `source_snapshot_id` join (not a "most recent snapshot" substitution), and the version label at the generated-content surface. **Not shipped: the resolved license identifier (§7 field 5).** IDK-003 §7 forbids showing the raw `license_status` string alone and requires "the named basis (e.g. 'PostgreSQL License' or 'link-only, no reproduction')." That named basis exists in **no schema, contract, or API** anywhere in the tree (`SourceResponse` exposes only the raw `license_status: str`; a repo-wide grep for any license-basis mapping returns zero hits). This is not a rendering gap — there is nothing to render. Gate 3 additionally found, newly this round, a **third citation-adjacent surface** (`TopicTools`'s "resources" tab, fed by raw generated `sourcesMarkdown` text) that carries **none** of the six §7 fields and was not in scope of the commit that shipped the other three, and confirmed the **null-`canonical_url` fallback gap** (no wording exists for when the required field is absent) remains open, exactly as the shipping commit's own message flagged.
- **B7 (source availability write path).** Shipped and production-reachable: the migration, the `update_source` primitive, and the automatic `unavailable` transition. Shipped and correct but **not** production-reachable: the license-revocation purge, because **`withdraw_source` has no production caller** — no route, script, or CLI entry point invokes it anywhere in the tree; every reference outside its own definition is a test. A source cannot actually be withdrawn in the running product today, so the purge it gates cannot actually fire outside a test.
- **B10 / B12 (hands-on and assessment scenario content).** Shipped: the schema shape only — `scenario_status` admits `'approved'`, `scenario_id` exists, both confirmed on a database migrated to head, both threaded through `openapi.json` and the generated TypeScript client. **Not shipped: the twelve approved IDK-009 §4–§5 scenario records.** They are content, not code, and were not authored anywhere — a per-ID repo-wide grep for all twelve exact scenario IDs finds them only inside `docs/decisions/IDK-009-assessment-and-derived-state.md` and prior/current approval-review prose, never in `server/`, `src/`, `tests/`, or any migration or seed. Every synthesized `HandsOnWork` row is still hardcoded `scenario_status="fixture"`, `scenario_id=None`, `scenario_source="fixture-pending-idk-009"`.
- **B14 (UoW-before-422 ordering).** Closed for the one route IDK-008's text names. This is not a partial closure in the same sense as the three above — IDK-008 §3/§6 names specifically the retired relational-confirmation signature on `POST /runner/confirmations`, and that route now satisfies it exactly as literally written. Any other route that itself declares its own `Depends(get_unit_of_work)` still opens one for its own work, which the decision text never asked to change.

## Findings register

### Still open (or newly found)

| # | Gate | Finding | Owning ticket | Status |
| --- | --- | --- | --- | --- |
| B1 | 1 | No production `canonical_graph_versions` row exists; CUR-01 boundary and CUR-02 graph-absence have no shipped artifact to review against | IDK-102 (production seed run) | still open |
| B3 | 2 | No production `editorial_approvals` row exists to inspect against §4's now-mechanically-enforced criteria | IDK-102 (production seed run) | still open |
| B4 | 3 | No production source registry; every shipped claim traces to a test fixture or the IDK-504 perf-dataset seed script (itself fixture-shaped) | unassigned — IDK-003 §12 names IDK-201/207/404/408 or a dedicated provenance follow-up | still open |
| B5 | 3 | Resolved license identifier unbuildable (no named-basis mapping exists below the UI); a third surface (`TopicTools` resources tab) carries none of the six §7 fields; the null-`canonical_url` fallback gap remains | IDK-201 / IDK-207 (license-basis data path itself has no owner) | still open (partial closure — see above) |
| B6 | 3 | `unavailable` and `withdrawn` render through one shared, undifferentiated copy template; `SourceResponse` doesn't even expose `withdrawal_reason` for a future fix to key on | IDK-201 / IDK-207 | still open |
| B7 | 3 | Explicit source withdrawal — and the license-revocation purge it gates — has no production entry point anywhere in the product | unassigned — candidate is the same provenance follow-up named for B4 | still open (partial closure — see above) |
| B10 (content) | 4, 5 | Twelve approved IDK-009 hands-on/practice/mock scenario records not authored; every synthesized `HandsOnWork` row still hardcodes `scenario_status="fixture"` | IDK-405 | still open (schema half closed — see above) |
| B11 | 5 | No approved rubric manifests shipped (`hands-on-rubric-v1`, `practice-rubric-v1`, `mock-rubric-v1`); four of six approved stable dimensions appear nowhere in shipped code | IDK-204 (marked "Complete" in `IMPLEMENTATION_TICKETS.md` — inconsistent with this finding) | still open |
| B12 (content) | 5 | None of the twelve approved scenario records shipped as content (the `scenario_id` field now exists structurally but holds nothing) | IDK-405 / IDK-302 / IDK-303 (all marked "Complete" — inconsistent with this finding) | still open (schema half closed — see above) |
| B15 | 7 | PRD Appendix C rows 3, 4 and 6 have no row-specific residual copy in-product; one generic disclaimer covers all six rows | IDK-406 — blocked on an owner decision (write per-row copy, or record a decision that one consolidated disclosure is intended to subsume all six rows) | still open |
| B17 | 4 | Onboarding's level selector initializes to and can silently submit `'Senior'` with no explicit learner choice required, contradicting IDK-004 §4's fail-closed requirement; `BundleEditor.createBundle` hardcodes the same default for its recommended bundle | none identified | newly found |
| B18 | 4 | `'approved'`, the new `hands_on_work.scenario_status` literal, is an implementation naming choice with no decision text behind it: IDK-009 never names a `scenario_status` field and supplies no non-fixture literal for one. A persisted enum value was introduced without decision authority | IDK-009 — needs the editorial approver's decision, not code | newly found |
| B19 | 5 | Persisted classification literal remains `likely-known` (hyphen) across every layer — 2 domain enums, at least 3 migration `CHECK` constraints across `roadmap`/`evidence_evaluation`, 3 generated TypeScript union types, and 2 learner-facing `<select>` controls — where IDK-009 §2 specifies `likely_known` (underscore), quoted directly: "The only persisted classification values are `likely_known`, `partial`, `unverified`, and `new`" | IDK-009 — needs the editorial approver's decision (accept the shipped spelling, or commission a coordinated multi-table rename); not engineering work this gate can assign | still open — carried forward from the 2026-08-14 round's unnumbered note, now given an identifier |
| B20 | 6 | `018ecd8`'s Java-only migration bulk-deletes every `language='relational'` runner confirmation/record and its owned inputs/bodies/output chunks, outside any IDK-010 §6/§14.2 expiry schedule; IDK-010 policy 1.0 names no category for this data-lifecycle event | none identified — needs the product/privacy owner's decision on whether to accept this as a named category | still open — carried forward from the 2026-08-14 round's attestation note, now given an identifier |

### Closed since the previous round

| Finding | Commit that closed it | Gate record that verified it |
| --- | --- | --- |
| B2 | `c3409df` | `gate-2-editorial-approvals.md` |
| B8 | `6bebd2f` | `gate-4-role-copy.md` |
| B9 | `6bebd2f` | `gate-4-role-copy.md` |
| B13 | `6bebd2f` | `gate-5-rubrics-scenarios.md` |
| B14 | `2621d29` | `gate-7-runner-posture.md` |
| B16 | `6bebd2f` | `gate-7-runner-posture.md` |

## PRD Appendix C — every row dispositioned

All six rows remain dispositioned against a **disabled** runner: `runner_enabled` is `False`, `policy_ready()` is `False` (18 values required, all absent — gate 7 corrects the prior round's count of 9 nullable `runner_*` fields to 11, plus 7 further fixed-default fields also required), `GET /runner/capabilities` reports `enabled: false`, and `runner_confirmations`/`runner_records` are empty in both databases. `docs/runner/IDK-406-execution-deferral.md`'s accepted-risk record (POSIX `rlimit`s instead of the IDK-007 cgroup/namespace/syscall-filter boundary) is unchanged by this round's commits and is not reopened here.

| PRD Appendix C row | MVP control — shipped? | Residual statement — labelled in-product? | Disposition |
| --- | --- | --- | --- |
| Shell injection | Yes. `subprocess.Popen(list(spec.argv), shell=False, ...)` (`adapters.py:137-139`); `detect_command`'s version probe likewise `shell=False` | Yes. "Controlled subprocess execution only..." (`HandsOnLab.tsx:102,116`) | Clear |
| Excess CPU/time/output | Yes, at the level actually built. `apply_limits()` sets `RLIMIT_CPU`/`RLIMIT_AS`(non-Darwin)/`RLIMIT_NPROC`/`RLIMIT_FSIZE`; poll loop enforces wall/output/temp budgets. The full cgroup-based guarantee IDK-007 §5 requires remains the subject of the accepted-risk deferral, not a fresh finding | Yes. Same generic string | Clear — accepted-risk-adjusted, already dispositioned by `IDK-406-execution-deferral.md` |
| File pollution | Yes. `LocalTempWorkspace.create`/`cleanup` refuses to `rmtree` anything outside `gettempdir()` or lacking the `yuno-runner-` prefix | No row-specific copy anywhere in `src/` — only the generic string | Open (B15) |
| Environment/secrets leakage | Yes. `minimal_environment()` allowlists `PATH`/`LANG`/`LC_ALL`/`TZ` and strips any key matching `AWS_`/`SECRET`/`TOKEN`/`PASSWORD`/`CREDENTIAL`/`CONNECTION_STRING`/`DATABASE_URL` | No row-specific copy — only the generic string | Open (B15) |
| Misleading validation | Yes. Compile/test operations distinct; static hands-on review never invokes the runner; `RUNNER_LIMITATION` surfaced on capabilities and job pages | Yes. Generic string plus an explicit "Runtime execution is separate and cannot create hands-on evidence" clause | Clear |
| Orphaned process | Yes. `request_termination()` sends `SIGTERM` via `os.killpg`, escalates to `SIGKILL` if still alive | No standing row-specific copy — the one adjacent string (`HandsOnLab.tsx:105`) is a conditional cleanup-failure notice, not an unconditional disclosure | Open (B15) |

Relational absence (IDK-008) was re-verified empirically this round, not merely re-read: `RunnerLanguage` admits only `java`; the retired `"language":"relational"` confirmation returns the standard `422` envelope with zero persisted rows (`runner_confirmations`=0, `jobs`=0), reproduced against a scratch database; no connector credential/endpoint field exists anywhere in settings, contracts, persisted records, or generated client types; no runner path opens a database socket or process; the narrowing migration's CHECK constraint is confirmed live even on the stale `server/yuno.db`. IDK-008 §4's requirement that RDB static reviews carry no-connection/no-runtime-proof clauses remains **vacuously unmet** — no RDB content exists yet to carry them.

## Blocking-question coverage (spec §12.3)

| Question | Gate | Status after inspection |
| --- | --- | --- |
| 1 Curriculum spine | 1 | Decision approved; implementation still unverifiable — nothing published |
| 2 Editorial policy | 2 | Decision approved; enforcement code now shipped and independently verified (B2 closed); no production approval row exists to inspect it against (B3 open) |
| 3 Source policy | 3 | Decision approved; availability write path and the automatic `unavailable` transition now shipped and production-reachable; explicit withdrawal has no production entry point; attribution partially shipped; no production source registry |
| 4 Role taxonomy | 4 | Decision approved; approved copy now shipped and wired end to end (B8/B9 closed); hands-on scenario content still unshipped (B10 content half); newly found onboarding-default gap (B17) |
| 7 Runner posture | 7 | Decision approved; execution deferred per the accepted IDK-406 risk record (unchanged); platform gate now enforced (B16 closed); per-row Appendix C residual copy still missing (B15 open) |
| 8 Database exercises | 7 | Decision approved; absence verified and holding, re-confirmed empirically this round |
| 9 Assessment design | 5 | Decision approved; outcome vocabulary and critical-dimension precedence now shipped (B13 closed); rubrics still not shipped (B11); scenario content still not shipped (B12 content half) |

Gate 6 additionally supplies inspection evidence toward questions 10 and 11, which IDK-010 policy 1.0 already settled.

## Attestation

No signature has been given. Each line below is signed only by the named role, and only against the gate's own evidence file.

- [ ] **Designated editorial approver** — gates 1, 2, 3, 4, 5. Blocked: B1, B3, B4, B5, B6, B7, B10 (content half), B11, B12 (content half) must close first. Additionally needs this approver's own decision — not engineering work — on B17 (onboarding default-level behavior), B18 (the `'approved'` literal's missing decision backing), and B19 (the `likely-known`/`likely_known` spelling mismatch and its cross-table blast radius).
- [ ] **Product/privacy owner** — gate 6. Not blocked by a finding — this gate re-reached `inspection-passed-pending-attestation` fresh. Still requires the reviewer's own hands-on pass over a downloaded export package, a delete preflight/completion record, and a live rotated log file, per IDK-010 §10 (none of that evidence exists yet in this tree). Also needs a decision on B20 (the `018ecd8` Java-only migration's bulk deletion, a data-lifecycle event policy 1.0 does not name a category for) and awareness that the new license-revocation purge (`bf664e2`) is a named category under IDK-003 §6, not IDK-010 — correctly implemented and not a second drift note, but absent from IDK-010's own text.
- [ ] **Security/engineering owner** — gate 7. Blocked: B15 must close, or be replaced by a recorded decision that one consolidated disclosure is intended to subsume all six Appendix C rows. B14 and B16, which blocked the prior round, are now closed.

## Re-review trigger

This review must be re-run, not amended, once the owning tickets close — in particular after IDK-102's production publish (clears B1/B3), IDK-204's rubric registry (clears B11), IDK-405's/IDK-302's/IDK-303's scenario-content load (clears B10/B12 content halves), a provenance follow-up covering the source registry and withdrawal entry point (clears B4/B7), and after B15/B17/B18/B19/B20 each receive an owner decision. A gate's disposition here is bound to the tree inspected on 2026-08-15 at `2621d298f8f268d42ec6be94d454fa61d986f054`, for all seven gates, and carries forward to no later state.
