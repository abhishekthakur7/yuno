# IDK-503 (re-run, round 3) gate 2 — Editorial approval evidence and criteria

- Gate: Editorial approval evidence and criteria (CORE-02/INT-02, D1)
- Reviewer role required: designated editorial approver
- Inspection date: 2026-08-15
- Disposition: blocking-finding
- Attestation: pending -- designated editorial approver has not signed this gate. No attestation was sought or recorded during this inspection.

This is round 3 of the IDK-503 re-run (HEAD `7b805bd`), a fresh, independent
inspection, not an amendment of either `docs/approvals/IDK-503/gate-2-editorial-approvals.md`
(2026-08-14) or `docs/approvals/IDK-503-rerun-2026-08-15/gate-2-editorial-approvals.md`
(round 2, HEAD `2621d29`). The round-2 file was read only to recover scope, per
instruction; none of its citations are carried forward unverified. Every claim
below was re-derived in this session: by reading the current source at the
cited lines, by diffing round 2's HEAD against this round's HEAD to confirm
which files actually changed, by migrating a fresh scratch database and
inspecting its real schema/triggers, by running the actual test suites, and
by querying both `server/yuno.db` and `server/.e2e.db` read-only.

## HEAD delta check (`796fa30` → `7b805bd`)

The body of this inspection was performed at `796fa30`. One further commit,
`7b805bdd72d5740eb8180f3e6fde9c33af2a672f` ("fix: three defects the round-3
gate inspections found," fixing issues gates 4/5/7 raised), has since landed
and was checked before finalizing this record — not assumed clean.

`git diff 796fa30 7b805bd --stat` touches exactly four files:
`docs/assessment/IDK-009-critical-dimension-exposure.md` (4 lines),
`server/tests/integration/test_runner.py` (20 lines),
`src/selected/core/CorePages.tsx` (11 lines), and
`src/selected/core/InterviewHub.test.tsx` (11 lines). None is
`editorial_approvals`, `basis_ref`, `publish_canonical_graph`,
`withdraw_source`, or the `designated_editorial_approver` grant check this
gate's findings rest on — `IDK-009-critical-dimension-exposure.md` is gate
5's evidence-evaluation territory (already assessed as not touching this gate
under `0a6e7c9` above, and this commit only edits that same document
further); `test_runner.py` is gate 7's runner-posture territory;
`CorePages.tsx`/`InterviewHub.test.tsx` is frontend, the same surface as
`bd05da6`/`cbd4c16` above, already assessed as not touching this gate.

`git diff 796fa30 7b805bd -- server/src/ server/scripts/ server/pyproject.toml`
returns empty — confirmed directly, not inferred from the stat summary.
Nothing under `server/src/yuno/modules/canonical/`,
`server/src/yuno/modules/identity/`, `server/src/yuno/modules/provenance/`,
or `server/scripts/` moved. This means both this gate's re-verified
mechanism (finding 1-8, blocking finding 1) and its new authority-boundary
concern (blocking finding 2, the `withdraw_source` grant reuse) are
unaffected: the commit message says it addresses gates 4, 5, and 7's
findings, not gate 2's, and the file-level diff confirms that claim rather
than merely repeating it.

**Conclusion: nothing in `7b805bd` bears on gate 2's subject matter. No
finding below changes; disposition is unchanged.** The HEAD this record is
stamped against has been advanced to `7b805bd` only after this check
confirmed the delta is inert for this gate's purposes — not as a silent
restamp. Blocking finding 2 in particular is deliberately not addressed by
this commit: it names a decision-document gap (which role/grant authorizes
source withdrawal), and nothing in `7b805bd`'s four touched files is a
decision document or the code path this finding is about, so it necessarily
stands as recorded.

## What changed since round 2, assessed against this gate

`git log 2621d29..HEAD` (five commits). Each assessed individually, not assumed clean:

- **`0a6e7c9`** (is_critical exposure decision + `IMPLEMENTATION_TICKETS.md` status reconciliation): `git show 0a6e7c9 --stat` touches `IMPLEMENTATION_TICKETS.md`, a new `docs/assessment/IDK-009-critical-dimension-exposure.md`, and a comment-only change in `server/src/yuno/modules/evidence_evaluation/models.py`. The `IMPLEMENTATION_TICKETS.md` diff reconciles four ticket statuses — IDK-204, IDK-302, IDK-303, IDK-405 — from `Complete` to a new `Content incomplete` status; none of the four is IDK-102 (the production-seed ticket this gate's blocking finding is owned by) or IDK-002. The `is_critical` decision concerns `RubricDimension`/`AssessmentDimensionResult` (gate 5's evidence-evaluation territory), not `editorial_approvals`/`basis_ref`. **Checked; does not touch this gate.**
- **`bd05da6`** (render IDK-003 §7 attribution on the Topic Studio resources tab): `git show bd05da6 --stat` touches only `src/selected/core/CorePages.tsx` and its test file — a frontend rendering change that resolves `useArtifactProvenance` for the Sources layer's own artifact and displays it. No change to `editorial_approvals`, `basis_ref`, `publish_canonical_graph`, or the `designated_editorial_approver` grant check. **Checked; does not touch this gate.**
- **`cbd4c16`** (require an explicit target level at onboarding/bundle-creation): touches only `src/selected/core/CorePages.tsx`, `InterviewHub.test.tsx`, `ProfileGoalsPages.test.tsx`, and e2e harness files (IDK-004 fail-closed-selection territory). No relation to editorial approval. **Checked; does not touch this gate.**
- **`796fa30`** (import-linter `ignore_imports` entry + `TopicTools` prop collapse): `git diff 2621d29..HEAD --stat -- server/src/yuno/modules/canonical/` returns nothing — the canonical module, `validation.py`, `publisher.py`, `models.py`, and their tests are byte-identical to round 2's inspection point. The `server/pyproject.toml` change (lines 178–186, 213) only adds `"yuno.modules.provenance.service -> yuno.modules.identity.**"` to `ignore_imports`, a consequence of `5596654` below, and the `CorePages.tsx`/`TopicTools` prop change is the same frontend surface as `bd05da6`, unrelated to the approval mechanism. **The import-linter entry is assessed as part of `5596654` below; the rest does not touch this gate.**
- **`5596654`** (`server/scripts/withdraw_source.py`, a new offline editorial CLI, with a `designated_editorial_approver` grant check inside `provenance.service.withdraw_source`): **assessed in detail below — this is the one change with a genuine, if narrow, bearing on this gate.**

### The `withdraw_source` grant reuse, assessed against IDK-002/D1's model of editorial authority

`5596654` gives `withdraw_source` (`server/src/yuno/modules/provenance/service.py:142-216`) a role-grant check identical in shape to `publish_canonical_graph`'s:

```
server/src/yuno/modules/provenance/service.py:190-191
        grants = uow.owners.grants(owner_id)
        RolePolicy.require(grants, Role.DESIGNATED_EDITORIAL_APPROVER)
```

against

```
server/src/yuno/modules/canonical/publisher.py:139-140
        grants = uow.owners.grants(actor_owner_id)
        RolePolicy.require(grants, Role.DESIGNATED_EDITORIAL_APPROVER)
```

The script's own docstring (`server/scripts/withdraw_source.py:46-54`) and the
service function's docstring (`provenance/service.py:173-186`) argue this is
correct by analogy: IDK-003 §8 reserves `withdrawn` for "explicit editorial
action," and holding `designated_editorial_approver` is "what makes an action
editorial." `server/pyproject.toml:178-186` records the identical reasoning
for the new import-linter `ignore_imports` entry. This is a real, tested
enforcement path, not a documentation claim only: `pytest
tests/integration/test_withdraw_source_script.py
tests/integration/test_provenance_withdrawal.py` → 15 passed in this session,
including `test_withdrawal_refused_when_actor_lacks_the_grant_exits_1`
(`test_withdraw_source_script.py:265`), and `lint-imports` reports 4
contracts kept, 0 broken with the new entry in place.

Whether reusing the *same* grant for a *second*, structurally different act
is consistent with IDK-002/D1's model of editorial authority is the actual
question, and the decision documents answer it, not favorably for this reuse:

- **IDK-002 itself scopes the grant to D1's act specifically.** IDK-002:25 ("Who approves," in "What is already resolved and not reopened") describes the grant purely in terms of canonical-graph publication: *"`publish_canonical_graph` (`server/src/yuno/modules/canonical/publisher.py`) checks it before any write."* No other write path is named or contemplated.
- **PRD Appendix H D1 (`PRD.md:352`) ties the grant to the same one act**: *"a real `EditorialApproval` record attributed to the designated editorial approver... The tooling runs only against a stopped server or writes each version in a single transaction with the approval record last."* D1 never mentions source withdrawal.
- **PRD's own dependency table (`PRD.md:395-396`) treats "editorial approver" and "content owner" as two distinct, separately-tracked roles**, and only one of them is resolved: line 395, source-license review → *"Content owner TBD / editorial approver TBD"*; line 396, canonical publication gate → *"Resolved for MVP: the local owner acts as the designated editorial approver."* Source-license/withdrawal governance is explicitly the *unresolved* row, not the resolved one.
- **IDK-003 — the decision that actually governs source withdrawal — names a different approver role than IDK-002's.** IDK-003:11: *"Approver role: content owner, per PRD §13."* IDK-003:187 (§12 item 7) frames the still-unbuilt registry-population path as inserting `sources` rows "attributed to the content-owner role," not the editorial-approver role.
- **IDK-003 §13 names the exact gap `5596654` steps into, as an open item, not a settled one.** IDK-003:200: *"`owner_role_grants.role` (`learner`, `designated_editorial_approver`) has no distinct content-owner value, so no role attribution records who approved a given `sources` row, **unlike D1's explicit grant for canonical publication**."* That sentence draws precisely the boundary this commit crosses: D1's grant is explicit and scoped to canonical publication; the content-owner grant IDK-003 actually calls for does not exist.
- **The schema itself enforces that D1's grant vocabulary is closed to one act.** Verified independently against a scratch DB migrated to head (`be4d11f03666`): `.schema editorial_approvals` shows `CONSTRAINT ck_editorial_approvals_approver_role_valid CHECK (approver_role IN ('designated_editorial_approver'))` (also present in the original migration, `server/src/yuno/migrations/versions/87af9746aec1_canonical_graph.py:196`). This CHECK constrains *`editorial_approvals.approver_role`* — the D1 attestation record — not the `owner_role_grants` table `withdraw_source` actually checks, so it does not itself block the reuse; but it confirms the `editorial_approvals` mechanism gate 2 audits was built assuming this grant has exactly one authorized act.

Net assessment: this is not a mechanism bug — the grant check works, is tested,
and the import-linter contract is intact. It is an **unresolved authority-
boundary question presented as settled**. IDK-002 defines `designated_editorial_approver`
in terms of one act (D1 canonical publication) and states plainly that "who
approves" is fixed by Appendix H D1/PRD §13 and not reopened by IDK-002. PRD
§13 and IDK-003 both treat "who governs source policy" as a *separate,
unresolved* question — IDK-003 approved under a "content owner" role that
IDK-003's own §13 admits has no operational grant. `5596654` resolves that
open question in code (by reusing the editorial-approver grant) rather than
through either decision document's change control (IDK-002 §10, IDK-003 §14),
and does so for an act — source withdrawal, which can trigger an immediate,
irreversible purge of stored snapshot bodies (IDK-003 §8) — with real
consequence if the grant's authorized scope turns out not to have been meant
to cover it.

## Re-verification of round 2's two open items

**Round 2 finding 1 (basis_ref mechanical validation) — re-confirmed closed, independently.**
`git diff 2621d29..HEAD --stat -- server/src/yuno/modules/canonical/ ...` (tests included) returns no output: the canonical module and its three basis_ref test files are byte-identical to round 2's inspection point, so this is a genuine re-verification, not a restamp:

- `server/src/yuno/modules/canonical/models.py:432` — `CheckConstraint("json_valid(basis_ref)", name="basis_ref_valid")`, confirmed present by reading the file directly in this session.
- Fresh scratch DB (`/private/tmp/.../scratchpad/gate2_scratch.db`, unique to this gate) migrated with `YUNO_DATABASE_URL=sqlite+pysqlite:////.../gate2_scratch.db uv run --directory server alembic upgrade head` → ran all 30 migrations cleanly to `be4d11f03666`. `.schema editorial_approvals` on that DB shows both `ck_editorial_approvals_basis_ref_valid CHECK (json_valid(basis_ref))` and `ck_editorial_approvals_approver_role_valid CHECK (approver_role IN ('designated_editorial_approver'))`, plus all three immutability triggers (`trg_editorial_approvals_no_update`, `_no_delete`, `_no_insert_replace`) with bodies unchanged.
- A live `INSERT INTO editorial_approvals (...) VALUES (..., 'not-json', ...)` against that scratch DB failed with `CHECK constraint failed: ck_editorial_approvals_basis_ref_valid` — the constraint is enforced at the database layer, not merely declared in the ORM.
- `server/src/yuno/modules/canonical/publisher.py` ordering re-confirmed by reading the file directly: `require_single_head(engine)` at `:117`, `validate_manifest(manifest)` at `:119` (both outside the UoW), then inside the UoW: grant check at `:139-140`, `validate_basis_ref(...)` at `:143`, first write `uow.canonical.create_version(version)` at `:181`, `uow.canonical.record_approval(approval)` last at `:221`.
- `pytest tests/integration/test_canonical_basis_ref_constraint.py tests/integration/test_canonical_publish.py tests/unit/test_canonical_basis_ref_validation.py` → 60 passed, run fresh in this session.

**Round 2 finding 2 / blocking finding 1 (no production `editorial_approvals` row) — re-confirmed still open, unchanged:**

- `sqlite3 -readonly server/yuno.db "SELECT COUNT(*) FROM editorial_approvals;"` → `0`.
- `sqlite3 -readonly server/.e2e.db "SELECT COUNT(*) FROM editorial_approvals;"` → `0`.
- `server/yuno.db`'s `alembic_version` = `4747447ccaa3` — still two revisions behind this tree's actual head (`be4d11f03666`); the two missing migrations (`4cb74877e4ba` sources license fields, `be4d11f03666` scenario-status/id widening) do not touch `editorial_approvals` or `basis_ref`, confirmed by reading both migration files, so this does not change the gate's disposition but the local dev DB remains behind head.
- `server/.e2e.db`'s `alembic_version` = `a9d4e6f1b208`, further behind, no `basis_ref_valid` constraint present — consistent with round 2's note that it is untouched by this work.
- `sqlite3 -readonly server/yuno.db "SELECT COUNT(*) FROM owner_role_grants WHERE role='designated_editorial_approver';"` → `1` (the single local owner already holds the grant) and `sqlite3 -readonly server/yuno.db "SELECT COUNT(*) FROM sources;"` → `0` — neither a production canonical version nor a production source has ever been published, consistent with IDK-002:119/IDK-003:193's own statements.

## Inspected artifacts

| Artifact | What it is | How inspected |
| --- | --- | --- |
| `docs/decisions/IDK-002-editorial-approval-criteria.md` | Governing decision | Read in full this session; §2 ("Who approves," `:25`), §4 (`:53-75`), §8 (`:110-128`), §10 (`:142-146`) re-walked |
| `docs/decisions/IDK-003-source-licensing-and-snapshot-policy.md` | Decision governing source withdrawal, read to assess the grant-reuse question | Read in full this session; §1/§8/§11-§14 (approver role, withdrawal state machine, known gaps, change control) |
| `PRD.md` | Product requirements, Appendix H D1 and §13 dependency/open-question tables | Read Appendix H D1 (`:352`), the dependency table (`:391-399`), and open question 2 (`:425`) |
| `docs/approvals/IDK-503-rerun-2026-08-15/gate-2-editorial-approvals.md` | Round-2 gate record | Read for scope only, per instruction; citations treated as stale and re-derived |
| `git log 2621d29..HEAD` / `git show --stat <each>` | The five commits since round 2 | Each read individually; four assessed as not touching this gate, one (`5596654`) assessed in depth |
| `git diff 2621d29..HEAD --stat -- server/src/yuno/modules/canonical/ <tests>` | Confirms the canonical module/tests are unchanged since round 2 | Run; empty output confirms byte-identical |
| `server/src/yuno/modules/canonical/models.py:432` | `EditorialApprovalRow.basis_ref` CHECK | Read directly |
| `server/src/yuno/modules/canonical/publisher.py:117-221` | `publish_canonical_graph` ordering | Read in full; call-site line numbers re-confirmed by grep |
| `server/src/yuno/modules/provenance/service.py:142-216` | `withdraw_source`, incl. its grant check | Read in full |
| `server/scripts/withdraw_source.py` | New offline CLI (174 lines) | Read in full |
| `server/pyproject.toml:160-220` | Import-linter contract, `ignore_imports` | Read; the new `provenance.service -> identity` entry and its rationale comment |
| `server/src/yuno/migrations/versions/87af9746aec1_canonical_graph.py:196` | `editorial_approvals.approver_role` CHECK | Read directly (`approver_role IN ('designated_editorial_approver')`) |
| Scratch DB `gate2_scratch.db` | Fresh SQLite DB migrated to head, unique to this gate | Created under this session's scratchpad; `alembic upgrade head` (exit 0, 30 migrations incl. `4747447ccaa3`) via `YUNO_DATABASE_URL`; never touched `server/yuno.db`/`server/.e2e.db` |
| Scratch DB schema/trigger dump | Real migrated `editorial_approvals` DDL | `sqlite3 <scratch>.db ".schema editorial_approvals"` and a `sqlite_master` trigger query |
| Scratch DB live INSERT test | CHECK constraint enforced at the DB layer | `INSERT ... VALUES (..., 'not-json', ...)` → rejected |
| `server/tests/integration/test_canonical_basis_ref_constraint.py`, `test_canonical_publish.py`, `server/tests/unit/test_canonical_basis_ref_validation.py` | basis_ref mechanism tests | Run: 60 passed |
| `server/tests/integration/test_withdraw_source_script.py`, `test_provenance_withdrawal.py` | Grant-check + withdrawal-mechanism tests | Run: 15 passed |
| `uv run lint-imports` | Import-linter contracts | Run: 4 kept, 0 broken |
| `uv run alembic heads` | Current migration head | Run: `be4d11f03666 (head)` |
| `server/yuno.db`, `server/.e2e.db` | Local/e2e SQLite DBs | `sqlite3 -readonly` queries only: `editorial_approvals` row counts, `alembic_version`, `owner_role_grants`, `sources` counts |

## Findings

| # | Item | Verdict |
| --- | --- | --- |
| 1 | §8 item 1 `json_valid(basis_ref)` CHECK constraint | **closed** — re-confirmed at the database layer this session (see above) |
| 2 | Immutability triggers survive the batch-rebuild migration | **closed** — all three present, bodies unchanged |
| 3 | Framework-free §4 schema validation invoked before any write | **closed** — `publisher.py:143` before `:181`'s first insert; unchanged file, re-confirmed by reading |
| 4 | §4's 15-field contract | **closed for presence** (unchanged since round 2; not re-walked field-by-field this round since the file is byte-identical and was already exhaustively walked and independently re-verified as unchanged — see "What changed" above) |
| 5 | `reviewed_manifest_hash` cross-check | **closed** — file unchanged; `publisher.py:143-162` ordering re-confirmed |
| 6 | `review_kind`/published-state consistency check | **closed** — file unchanged, re-confirmed via passing tests |
| 7 | `scripts/publish_canonical.py` rejects a malformed `basis_ref` | **closed** — unchanged since round 2; not re-executed this round (no code in this path changed; re-running the same script against the same fixtures would not produce new information over round 2's actual execution) |
| 8 | Single write path to `editorial_approvals` (`record_approval`) | **closed** — `publisher.py:221` still the only call site; `withdraw_source` (new this round) writes to `sources`, not `editorial_approvals` — confirmed by reading `provenance/service.py:192-213`, which touches only `uow.provenance.update_source`/`purge_license_revoked_snapshot_bodies` |
| 9 | No placeholder `basis_ref` on a production version | **matches (nothing to violate yet)** — unchanged |
| 10 | No production `editorial_approvals` row exists | **still open** — re-confirmed this session, see blocking finding 1 |
| 11 (new this round) | `designated_editorial_approver` grant reuse for source withdrawal, consistency with IDK-002/D1's model of editorial authority | **open — see blocking finding 2** |

## Blocking findings

### 1. No production `editorial_approvals` row exists to inspect against §4's criteria

- What is missing: any row in `editorial_approvals` on either database available for inspection.
- Owning ticket: IDK-102 (production seed run) — IDK-002 §8 (`:119`) states no production canonical graph version has ever been published, and names IDK-503 as the check that must run once one is.
- Evidence of absence: `sqlite3 -readonly server/yuno.db "SELECT COUNT(*) FROM editorial_approvals"` → `0`; same query against `server/.e2e.db` → `0`. Re-verified directly in this session, read-only, against the current tree.
- Status vs. previous rounds: still open, unchanged from both round 1 and round 2. Nothing in this round's five commits writes a production `editorial_approvals` row or changes this fact.
- What would clear it: run IDK-102's production seed against a real manifest under `editorial-approval-criteria-v1`, producing a `basis_ref` conforming to §4 (mechanically enforced per findings 1-8 above), then re-inspect the row's actual field content against §4/§5's exhaustiveness and sampling rules — not merely that a row exists.

### 2. `withdraw_source`'s grant check reuses `designated_editorial_approver` for an act D1/IDK-002 never scoped it to, resolving an open cross-decision authority question in code rather than through either decision's change control

- What is missing: a decision-document basis for treating source withdrawal (IDK-003 §8) as an act the `designated_editorial_approver` grant (IDK-002/D1) authorizes. No such basis exists today.
- Owning ticket: none named for this specific gap; it sits at the boundary between IDK-002 (this gate) and IDK-003 (gate 3) and most naturally requires either an IDK-002 successor version (widening §2's "who approves"/scope) or an IDK-003 successor version (adding the missing distinct grant/role IDK-003:200 already names as absent) — both are decision-document changes, which this inspection is expressly forbidden from making (`AGENTS.md`; task instructions: "Never edit an approved decision document").
- Evidence of absence / of the conflict:
  - IDK-002:25 scopes the grant's "who approves" description to `publish_canonical_graph` only.
  - `PRD.md:352` (Appendix H D1) ties the grant to the same one act ("a real `EditorialApproval` record").
  - `PRD.md:395-396` treats "editorial approver" (resolved, publication-only) and "content owner" (unresolved) as two separate rows.
  - `docs/decisions/IDK-003-source-licensing-and-snapshot-policy.md:11` names the approver role for source policy as "content owner," not "designated editorial approver."
  - `docs/decisions/IDK-003-source-licensing-and-snapshot-policy.md:200` (§13) states explicitly that no distinct content-owner grant value exists, "unlike D1's explicit grant for canonical publication" — naming the exact gap `5596654` steps into rather than closes.
  - `server/src/yuno/modules/provenance/service.py:190-191` now checks `Role.DESIGNATED_EDITORIAL_APPROVER` before `withdraw_source` runs, verified live: `pytest tests/integration/test_withdraw_source_script.py tests/integration/test_provenance_withdrawal.py` → 15 passed, including a test that a missing grant is refused with exit 1.
- What would clear it: a decision-document action — either (a) a new IDK-002 decision version explicitly extending `designated_editorial_approver`'s authorized-acts list to cover IDK-003 §8 withdrawal and reconciling `PRD.md:395`'s "content owner TBD" row, or (b) a new IDK-003 decision version that introduces the distinct content-owner grant value IDK-003:200 already flags as missing and re-points `withdraw_source`'s check at it. Either requires the product/content owner's decision, not further engineering on this ticket — this inspection implements neither, per the hard rule against editing approved decision documents.

## Notes and residual risk

- **The D1 mechanism gate 2 exists to audit is unaffected by this round's changes and remains sound.** `server/src/yuno/modules/canonical/` and its three basis_ref test files are byte-identical to round 2's HEAD (`git diff 2621d29..HEAD --stat` on that path returns nothing); this round independently re-derived the same conclusion by reading the files, migrating a fresh scratch DB, and running 60 tests, rather than trusting round 2's word for it.
- **Blocking finding 2 is a boundary question, not a defect in the audited mechanism.** `withdraw_source` never writes to `editorial_approvals`; the `editorial_approvals.approver_role` CHECK constraint (`approver_role IN ('designated_editorial_approver')`, confirmed on the scratch DB and in `87af9746aec1_canonical_graph.py:196`) still only ever admits the one value tied to D1's own act. The concern is that the *grant itself* — held by the one local owner — is now also treated as sufficient authorization for a second, unrelated act (source withdrawal, which can trigger an immediate, irreversible snapshot-body purge under IDK-003 §8) without any decision document actually saying that is what the grant is for. In this MVP's single-owner design the practical blast radius is limited (the one owner already holds the grant, so no unintended party gains access today), but the architectural question — what does `designated_editorial_approver` authorize, and who decides that — is exactly this gate's subject matter, and it is being answered by an engineering docstring's analogy rather than by either governing decision.
- **The engineering reasoning is not unconsidered.** `server/scripts/withdraw_source.py:46-54` and `server/pyproject.toml:178-186` both explicitly weigh and reject inventing a new role value (correctly identifying that as its own unapproved change under IDK-003 §14), and instead choose the existing grant by analogy to D1. That is a defensible engineering judgment call under time pressure, but it settles a question the decision documents leave open, and AGENTS.md's instruction to "make architectural decisions for the long term" cuts toward resolving this explicitly rather than leaving an analogy as the only basis for who may trigger an irreversible purge.
- **`server/yuno.db` remains behind the tree's actual migration head** (`4747447ccaa3` vs. current head `be4d11f03666`); re-confirmed this session. Neither of the two missing migrations touches `editorial_approvals`/`basis_ref`, so this does not change this gate's disposition, but the DB should be re-migrated before any production seed run is attempted against it.
- **Two narrow, previously-flagged gaps in `validate_basis_ref` remain unchanged and unre-litigated this round** (checklist_completed_at's timestamp format is not parsed; the nested review sub-fields' result values are not constrained to an enum) — the underlying file is byte-identical to round 2, and round 2's assessment (neither is required by §4's explicit five-item minimum-validation list) was not re-derived from scratch this round beyond confirming the file itself is unchanged; carried forward as unchanged fact, not re-verified reasoning.
- **This gate still cannot reach "inspection-passed" status.** Blocking finding 1 (no production row) is unchanged from both prior rounds and requires an actual IDK-102 seed run. Blocking finding 2 is new this round and requires a decision-document action this inspection is not permitted to make.
