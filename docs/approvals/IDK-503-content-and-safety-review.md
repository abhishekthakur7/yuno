# IDK-503 — Consolidated content-and-safety approval review

- Review date: 2026-08-14
- Scope: the seven content-and-safety gates IDK-503 names, checked against PRD Appendix C's six threat/limitation rows.
- Per-gate evidence: `docs/approvals/IDK-503/gate-1-curriculum-boundary.md` … `gate-7-runner-posture.md`.
- Mechanical field scan: `node scripts/check-review-records.mjs`.

## What this record is, and what it is not

This record holds the **engineering inspection** half of IDK-503: each gate was walked against the artifact actually shipped in this tree — database rows, source lines, migrations, named tests, exact UI strings — and the result written down with its citation. Where a decision's requirement is not shipped, that is recorded as a blocking finding against the owning ticket rather than softened.

It grants **no approval**. IDK-503's approvals belong to the designated editorial approver (gates 1–5), the product/privacy owner (gate 6), and the security/engineering owner (gate 7). Every gate below is `pending` on that signature, and six of the seven carry blocking findings that must close before a signature is even meaningful. Nothing here should be read as "gate approved"; the acceptance criterion "no gate is approved from a description of intended behavior rather than inspection of the shipped artifact" is satisfied by refusing to approve at all, not by inspecting well.

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

One gate reached inspection-passed. Six did not.

## The single fact that dominates gates 1–5

**No production content has ever been published.** `topics`, `canonical_graph_versions`, `editorial_approvals`, `sources`, `source_snapshots`, `rubrics` and `rubric_dimensions` are each at zero rows in both inspectable databases (`server/yuno.db`, local dev; `server/.e2e.db`, e2e — neither is production). Every learner-facing content surface today renders an empty or unavailable state.

That is not a defect in the mechanisms: the canonical validator, the approval-gated read joins, the role-grant enforcement, the claim/citation immutability triggers and the DEP-03 layer-reversal guard are all shipped, tested, and were confirmed working. It means the five content gates have **nothing shipped to inspect**, which under this ticket's own acceptance criteria is a blocking finding, not a pass. Gates 3, 4 and 5 additionally found requirements that are unimplemented *in code*, and those would block even after content ships.

## Blocking findings register

| # | Gate | Finding | Owning ticket |
| --- | --- | --- | --- |
| B1 | 1 | No production canonical graph published; CUR-01 boundary and CUR-02 graph-absence have no shipped artifact to review | IDK-102 |
| B2 | 2 | `basis_ref` schema validation (json_valid constraint, §4 field contract, `reviewed_manifest_hash` cross-check, `review_kind` consistency) entirely unimplemented | IDK-102 |
| B3 | 2 | No production `editorial_approvals` row exists to check against the approved criteria | IDK-102 |
| B4 | 3 | No production source registry; every shipped claim traces to a test fixture | unassigned (IDK-003 §12 names IDK-201/207/404/408 or a provenance follow-up) |
| B5 | 3 | Learner-facing attribution omits 4 of 6 required §7 fields (canonical URL link, retrieval timestamp, resolved license, version label) | IDK-201 / IDK-207 |
| B6 | 3 | `unavailable` and `withdrawn` render through one shared copy template instead of distinguishable facts | IDK-201 / IDK-207 |
| B7 | 3 | No automatic `unavailable` transition (3 failures / ≥72h) and no license-revocation purge; no code path can write `availability_status` at all | unassigned (candidate provenance follow-up / IDK-404) |
| B8 | 4 | Approved title-variation, non-prediction and per-level competency copy ships nowhere | IDK-104 / IDK-105 / IDK-301 |
| B9 | 4 | Interview Prep heading is a hardcoded `"Interview prep · Senior backend"` literal that ignores the goal's level | IDK-301 |
| B10 | 4 | Hands-on scenarios are generically synthesized, permanently labelled `fixture-pending-idk-009`; schema admits only `scenario_status IN ('fixture')` | IDK-405 |
| B11 | 5 | No approved rubric manifests shipped (`hands-on-rubric-v1`, `practice-rubric-v1`, `mock-rubric-v1` and their six stable dimensions absent everywhere) | IDK-204 |
| B12 | 5 | None of IDK-009's twelve approved scenario records shipped; no `scenario_id` field exists | IDK-405 / IDK-302 / IDK-303 |
| B13 | 5 | `not-demonstrated`, the fifth member of the approved closed outcome vocabulary, is entirely unimplemented | IDK-204 |
| B14 | 7 | A read-only UnitOfWork is opened while handling a request that then fails closed-schema validation, so IDK-008's literal "before the route/UoW" wording does not hold (zero side effects still confirmed) | IDK-406 |
| B15 | 7 | Appendix C rows 3, 4 and 6 have no row-specific residual copy in-product; one generic disclaimer covers all six | IDK-406 |
| B16 | 7 | IDK-005's platform matrix is unenforced: `detect_command` reports `supported` on this macOS host, which IDK-005 §1 forbids; no `/etc/os-release`, WSL or container check exists | IDK-406 |

Two lower-severity mismatches are recorded in gate 5 rather than here, because they are entangled with B11/B13 and should be fixed with them: the critical-dimension precedence rule of IDK-009 §9.2 has no shipped notion of a critical dimension, and the persisted classification is `likely-known` where the decision writes `likely_known`.

## PRD Appendix C — every row dispositioned

All six rows are dispositioned **against a disabled runner**. `runner_enabled` is `False`, all nine `runner_*` policy fields are `None`, `policy_ready()` is false, `GET /runner/capabilities` reports `enabled: false`, and `runner_confirmations`/`runner_records` are empty in both databases. `docs/runner/IDK-406-execution-deferral.md` records that the IDK-007 isolation layer (root broker, cgroup v2 subtree, namespaces, syscall filter) will not be built and that execution therefore stays off; this review confirms that document's factual claims and does not re-litigate the accepted risk.

| Appendix C row | MVP control — shipped? | Residual statement — labelled in-product? | Disposition |
| --- | --- | --- | --- |
| Shell injection | Yes. `subprocess.Popen(list(spec.argv), shell=False)` (`runner/adapters.py:99-109`); `detect_command` likewise; tests pin exact argv (`test_runner.py:432`) | Yes. "Controlled subprocess execution only." (`HandsOnLab.tsx:102`) | Reviewed — control implemented, residual labelled |
| Excess CPU/time/output | Partly. Wall/output/temp limits enforced in the poll loop (`adapters.py:146-216`); the isolation the approved policy requires is `setrlimit`, which IDK-007 §5 explicitly refuses as a substitute for cgroup accounting | Yes. "not a sandbox or hostile-code isolation" (`HandsOnLab.tsx:102/116`, `OperationalPages.tsx:401`) | Reviewed — bounded by IDK-406 deferral; acceptable only while execution stays disabled |
| File pollution | Yes. Per-run temp workspace with prefix-guarded cleanup (`adapters.py:73-83`) and tracked `cleanup_state` (`service.py:436-451`) | No row-specific copy ("process permissions define remaining host access risk") — see B15 | Reviewed — control implemented, residual copy missing |
| Environment/secrets leakage | Yes. `minimal_environment()` allowlists PATH/LANG/LC_ALL/TZ and strips `AWS_`/`SECRET`/`TOKEN`/`PASSWORD`/`CREDENTIAL`/`CONNECTION_STRING`/`DATABASE_URL` (`service.py:48-56,264-273`); test at `test_runner.py:254-263` | No row-specific copy ("local machine policy remains outside product control") — see B15 | Reviewed — control implemented, residual copy missing |
| Misleading validation | Yes. Compile/test operations distinct; static hands-on review never invokes the runner; `RUNNER_LIMITATION` surfaced on capabilities and the jobs page | Yes. "not proof of production or AWS behavior" (`HandsOnLab.tsx:102`) | Reviewed — control implemented, residual labelled |
| Orphaned process | Yes. `SIGTERM` to the process group, `SIGKILL` escalation after 0.5s, spawn identity recorded (`adapters.py:110-178`) | No row-specific copy ("OS failures may require manual recovery") — see B15 | Reviewed — control implemented, residual copy missing |

Relational absence (IDK-008) was verified separately and holds: `RunnerLanguage` admits only `java`; the retired `"language":"relational"` confirmation returns the standard `422` envelope with zero persisted rows (reproduced empirically); the Java-only migration deletes the prior placeholder subgraph and narrows the CHECK; no connector credential/endpoint field exists in settings, contracts, persisted records, process environment or generated client types; no runner path opens a database socket or process. The one caveat is B14's ordering nuance. IDK-008 §4's requirement that RDB static reviews carry no-connection/no-runtime-proof clauses is **vacuously unmet** — no RDB content exists yet to carry them — and must be re-checked when that content ships.

## Blocking-question coverage (spec §12.3)

| Question | Gate | Status after inspection |
| --- | --- | --- |
| 1 Curriculum spine | 1 | Decision approved; implementation unverifiable — nothing published |
| 2 Editorial policy | 2 | Decision approved; enforcement code absent |
| 3 Source policy | 3 | Decision approved; implementation absent |
| 4 Role taxonomy | 4 | Decision approved; approved copy not shipped |
| 7 Runner posture | 7 | Decision approved; execution deferred, platform gate unenforced |
| 8 Database exercises | 7 | Decision approved; absence verified and holding |
| 9 Assessment design | 5 | Decision approved; rubrics/scenarios not shipped |

Gate 6 additionally supplies inspection evidence toward questions 10 and 11, which IDK-010 policy 1.0 already settled.

## Attestation

No signature has been given. Each line below is signed only by the named role, and only against the gate's own evidence file.

- [ ] **Designated editorial approver** — gates 1, 2, 3, 4, 5. Blocked: B1–B13 must close first.
- [ ] **Product/privacy owner** — gate 6. Not blocked by a finding. Requires the reviewer's own hands-on pass over a downloaded export package, a delete preflight/completion record and a live rotated log file, per IDK-010 §10, plus a decision on the one drift note (the IDK-406 Java-only migration's bulk deletion of `language='relational'` rows is a data-lifecycle event policy 1.0 does not name a category for).
- [ ] **Security/engineering owner** — gate 7. Blocked: B14–B16 must close, or B15 must be replaced by a recorded decision that one consolidated disclosure is intended to subsume all six Appendix C rows.

## Re-review trigger

This review must be re-run, not amended, once the owning tickets close — in particular after IDK-102's production publish, IDK-204's rubric registry, IDK-405's scenario load, and IDK-406's platform gate. A gate's disposition here is bound to the tree inspected on 2026-08-14 and carries forward to no later state.
