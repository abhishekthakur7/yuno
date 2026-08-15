# IDK-503 (re-run, round 4) gate 2 — Editorial approval evidence and criteria

- Gate: Editorial approval evidence and criteria (CORE-02/INT-02, D1)
- Reviewer role required: designated editorial approver
- Inspection date: 2026-08-15
- Disposition: blocking-finding
- Attestation: pending -- designated editorial approver has not signed this gate. No attestation was sought or recorded during this inspection.

This is round 4 of the IDK-503 re-run (HEAD `0f3219f6a8b2a2436fce6d36c918307655a53c84`), a
fresh, independent inspection, not an amendment of round 1
(`docs/approvals/IDK-503/gate-2-editorial-approvals.md`), round 2
(`docs/approvals/IDK-503-rerun-2026-08-15/gate-2-editorial-approvals.md`), or round 3
(`docs/approvals/IDK-503-rerun-2026-08-15-b/gate-2-editorial-approvals.md`, HEAD `7b805bd`).
Round 3's file was read only to recover scope and the open-findings list, per instruction;
no citation below is carried forward unverified. Every claim here was independently
re-derived this session: by reading the current source at the cited lines, by diffing round
3's HEAD (`93103cd`) against this round's HEAD to confirm exactly which files changed, by
migrating a fresh scratch database with a real `alembic upgrade head` and exercising its
live constraints, by running the actual test suites and reporting real pass counts, and by
querying both `server/yuno.db` and `server/.e2e.db` read-only. Two prior rounds already
share the date 2026-08-15 (`-b`); this is a fourth tree, hence `-c`.

## HEAD delta check (`825a01f` → `0f3219f`)

The body of this inspection was performed at `825a01f`. Two further commits have since
landed and were each checked before finalizing this record — not assumed clean, per the same
discipline round 3 used when `7b805bd` landed mid-inspection.

### `636bf26` — "fix: correct five line citations this round's own commits invalidated"

`git show --stat 636bf26` touches exactly four files: `docs/assessment/IDK-009-critical-dimension-exposure.md`
(1 line), `docs/runner/IDK-406-execution-deferral.md` (1 line),
`server/src/yuno/modules/evidence_evaluation/service.py` (2 lines), and
`server/tests/integration/test_runner.py` (1 line) — "4 files changed, 5 insertions(+), 5
deletions(-)", a 1-for-1 line swap in each hunk. `git diff 825a01f 636bf26` (full, not just
stat) was read in full this session: every changed line is a citation string inside
docstring/comment prose (a line number in a cross-file pointer); no code statement, no test
assertion, no schema, and no decision-document prose changed. `git diff 825a01f 636bf26 --
server/src/yuno/modules/provenance/service.py` returns empty — the file the two citations
inside *this gate's* territory point at was not itself touched by this commit, confirming
the fix is pointer-only, not a substantive change to `withdraw_source`.

**The two citations inside this gate's own territory, independently re-derived, not
trusted:** `evidence_evaluation/service.py:939` now reads `provenance/service.py:270-271`
(was `:190-191`) and `:950` now reads `provenance/service.py:253-266` (was `:174-186`) —
exactly the drift this inspection's own body recorded under "Notes and residual risk" below.
Read directly against the current tree: `provenance/service.py:270-271` is
`grants = uow.owners.grants(owner_id)` / `RolePolicy.require(grants,
Role.DESIGNATED_EDITORIAL_APPROVER)` — `withdraw_source`'s grant check, exactly as claimed.
`provenance/service.py:253-266` is the paragraph beginning "IDK-003 §8 reserves `withdrawn`
for entry 'only by explicit editorial action' — the grant check below
(`Role.DESIGNATED_EDITORIAL_APPROVER`) is what makes an action 'editorial'..." running
through "...a distinct `actor_owner_id` would be a parameter nothing could ever supply a
different value for," immediately before the closing `"""` at `:267` — `withdraw_source`'s
editorial-action rationale block, exactly as claimed. **Both corrected citations are
correct.**

The other three corrections in this commit (`IDK-009-critical-dimension-exposure.md:13`,
`api/app.py:863`→`:1045` in `test_runner.py:351`, `api/app.py:784`→`:966` in
`IDK-406-execution-deferral.md:21`) are gate 5 and gate 7 territory — read in the diff above
to confirm they too are citation-text-only, but not independently re-derived line-by-line
here, since none names `editorial_approvals`, `basis_ref`, `publish_canonical_graph`,
`withdraw_source`, `register_source`, `load_rubric_manifest`, or the
`designated_editorial_approver` grant check this gate's findings rest on.

`git diff 825a01f 636bf26 --stat -- server/src/yuno/modules/canonical/
server/src/yuno/modules/identity/ docs/decisions/` returns empty — confirmed directly. The
commit touches no code in `canonical/` or `identity/`, no `owner_role_grants` reference of
any kind (`git diff 825a01f 636bf26 | grep -c owner_role_grants` → `0`), and no file under
`docs/decisions/`. B3 (no production `editorial_approvals` row) and blocking finding 2 (B21,
including this round's widening judgement re IDK-009) rest on none of the four files this
commit touched, so neither is affected.

**Conclusion: `636bf26` corrects, rather than changes, this gate's own evidence.** The
citation drift this inspection found and recorded under "Notes and residual risk" is now
fixed in the shipped code; no finding, no disposition, and no judgement in this record
changes from this commit.

### `0f3219f` — "fix: restore the import-boundary contract-declaration test to green"

**Scope, verified rather than trusted.** `git show 0f3219f` touches exactly one file,
`server/tests/architecture/test_import_boundaries.py`, "1 file changed, 7 insertions(+)": two
new literal-set entries (`"yuno.modules.provenance.service -> yuno.modules.identity.**"` and
`"yuno.modules.evidence_evaluation.service -> yuno.modules.identity.**"`) inside
`test_pyproject_declares_the_required_contracts`'s expected set, plus a five-line explanatory
comment above them. `git diff 636bf26 0f3219f -- server/pyproject.toml` returns empty — no
exemption is added to `pyproject.toml` by this commit; both edges it declares already existed
there (one from round 3's `796fa30`, one from this round's `4493208`). This is a test-file
change only, adding no new production behavior and removing none.

**Full suite, run fresh rather than quoted from the commit message:**
`uv run --directory server pytest tests/architecture/ -q` → **822 passed**, matching the
commit message's own claim exactly.

**`lint-imports`, re-run rather than assumed unaffected:**
`./server/.venv/bin/lint-imports --config server/pyproject.toml` →

```
Composition-root layering: api > modules > shared (spec §3.2) KEPT
Per-module layering (spec §3.3) KEPT
Domain and application are framework-free (spec §3.2, SYS-01/NFR-07) KEPT
Module independence (spec §3.3, IDK-102 scope) KEPT

Contracts: 4 kept, 0 broken.
```

Unchanged from every prior check this round and in round 3 — confirming the commit message's
claim that the import contract itself was never broken, only its declaration-parity test.

**The pre-existing-failure claim, reproduced independently, not taken on trust.** Created a
detached worktree at round-3 HEAD (`git worktree add --detach <scratch-path> 93103cd`) and
ran `uv run pytest tests/architecture/test_import_boundaries.py::test_pyproject_declares_the_required_contracts -q`
inside it: **1 failed**, with the actual assertion diff read directly —

```
AssertionError: assert {...} == {...}
Extra items in the left set:
'yuno.modules.provenance.service -> yuno.modules.identity.**'
```

— i.e. `pyproject.toml`'s declared `ignore_imports` (the "left set," read at test-collection
time) contained an entry the test's own literal ("right set") did not, at round-3's own final
HEAD, before this round's four commits touched anything. **Reproduced, not merely repeated
from the commit message.** The worktree was removed afterward (`git worktree remove --force`)
and `git worktree list` confirmed only the main worktree remains — no residue left in the
tree under review.

**Judgement: this is a real, gate-2-relevant gap, but it is closed within this round and
does not add a new blocking finding.** Two things are true at once. First, the underlying
architectural fact was never in doubt: `lint-imports` reported `4 kept, 0 broken` at every
point checked, this round and last, so no unauthorized import ever crossed the
`provenance`/`evidence_evaluation` → `identity` boundary, and B21's own supporting citation
of "the import-linter contract is intact" (round 3, and this round's "Confirming none of the
four commits..." section above) was never false — the *contract* held throughout. Second,
the *evidence* this gate (and round 3's gate 2) offered for that claim was incomplete: citing
`lint-imports`'s summary line is not the same claim as "every test in the architecture suite
passes," and the one test that would have caught a declared-but-undeclared exemption mismatch
was red for an entire round — from `796fa30` (round 3) through `4493208` (this round) —
without any gate noticing, because no gate ran `pytest tests/architecture/` as a whole. **This
inspection did not either**, in the body performed at `825a01f`: the targeted test files run
above (`test_withdraw_source_script.py`, `test_register_source_script.py`,
`test_load_rubric_manifest_script.py`, the canonical basis_ref suite, `lint-imports`) do not
include `tests/architecture/`, so this gate's own original evidence base would not have
surfaced this gap either, and did not until the coordinator's message prompted the full-suite
run recorded here. That is worth stating plainly rather than only crediting the fix: "the
import-linter contract is intact" is a claim about `lint-imports`'s CLI output, and this round
learned that claim is necessary but not sufficient evidence that the architecture test suite
itself is green.

This is not elevated to a new blocking finding, for the same reason B22/B23 in round 3's
consolidated review were recorded as "raised and closed within this round" rather than
carried into blocking findings: the gap is real, was independently verified (not assumed),
and is now fixed and re-verified (822 passed, 4 kept/0 broken) inside the same round it was
found in — there is no outstanding defect for the approver to act on, and no decision
document is implicated (this is a test-suite hygiene question, not an authority-boundary
question like B21, and not a missing-content question like B3). It does not change B21's
substance either: both declared-then-undeclared exemptions are the identical, deliberate
`-> identity` edge for the identical grant-check idiom (`publish_canonical_graph`,
`withdraw_source`/`register_source`, `load_rubric_manifest` respectively) — the omission was
in the test's literal, not in the architectural decision to allow the import, so it neither
strengthens nor weakens this round's B21 judgement above.

**What would prevent recurrence** (recorded per the brief's format, since this was a genuine
gap even though already cleared): future gate-2 (and gate-3/gate-5, which co-own the services
this touches) inspections verifying an import-linter exemption should run
`uv run --directory server pytest tests/architecture/ -q` in addition to `lint-imports`, not
instead of it — the two check different things (the contract vs. its own self-declaration),
and only the full suite catches drift between them. Already cleared this round by `0f3219f`;
re-verified above, not merely cited.

## What changed since round 3

`git log 93103cd..825a01f` — four commits, oldest first:

1. **`4493208`** ("give rubric manifest loading a production entry point") — adds
   `load_rubric_manifest` to `server/src/yuno/modules/evidence_evaluation/service.py`
   (172 lines) and the offline CLI `server/scripts/load_rubric_manifest.py` (247 lines).
   **Bears on this gate**: the function's grant check is
   `RolePolicy.require(grants, Role.DESIGNATED_EDITORIAL_APPROVER)`
   (`evidence_evaluation/service.py:990`), and its docstring explicitly claims this
   "consolidates under existing finding B21" (`evidence_evaluation/service.py:930-950`).
   Assessed in depth below.
2. **`90e23c3`** ("give source registration a production entry point") — adds
   `register_source` to `server/src/yuno/modules/provenance/service.py` (120 lines) and the
   offline CLI `server/scripts/register_source.py` (261 lines). **Bears on this gate**:
   identical grant check, `RolePolicy.require(grants, Role.DESIGNATED_EDITORIAL_APPROVER)`
   (`provenance/service.py:387`), with the identical "consolidates under B21" claim
   (`provenance/service.py:375-382`). Assessed in depth below.
3. **`2b5ebc2`** ("ship the 20-per-source snapshot janitor") — adds
   `prune_excess_snapshot_bodies` to `provenance/adapters.py` (152 lines touched) and wires
   `apply_snapshot_janitor()` into `api/app.py`'s hourly retention lane. **Does not bear on
   this gate**: `grep -n "DESIGNATED_EDITORIAL_APPROVER\|RolePolicy\|from yuno.modules.identity"
   server/src/yuno/modules/provenance/adapters.py` returns nothing — no grant check, no
   `identity` import anywhere in this file. `apply_snapshot_janitor`'s own docstring
   (`api/app.py`, this commit) states the reasoning directly: "This is automated local
   maintenance triggered by elapsed time and accumulated snapshot count, not an editorial
   act, so it needs no `designated_editorial_approver` grant check." No write to
   `editorial_approvals`, no call to `publish_canonical_graph` or `record_approval`
   anywhere in the commit (`git show 2b5ebc2 | grep -n "editorial_approvals\|publish_canonical_graph\|record_approval"` → no hits).
4. **`825a01f`** ("ship the 180-day source staleness re-check") — adds
   `sources_due_for_recheck` and `_latest_successful_snapshot` to `provenance/service.py`
   (78 lines touched) and wires `apply_staleness_recheck()` into `api/app.py`'s hourly
   lane. **Does not bear on this gate's substance**: `grep -n
   "DESIGNATED_EDITORIAL_APPROVER\|RolePolicy" server/src/yuno/modules/provenance/service.py`
   shows the only two `RolePolicy.require(..., DESIGNATED_EDITORIAL_APPROVER)` call sites in
   the entire file are `withdraw_source` (`:271`) and `register_source` (`:387`) —
   `sources_due_for_recheck`/`reserve_source_retrieval` carry no grant check, consistent
   with them being an automated cadence sweep, not an editorial act. **This commit does have
   an incidental effect on this gate's citation accuracy**, recorded under "Notes and
   residual risk" below: by inserting 74 new lines before `withdraw_source` in the same
   file, it silently invalidated two line-number citations inside `load_rubric_manifest`'s
   own docstring (`4493208`, which landed earlier and could not have known about it).

`git diff 93103cd..825a01f --stat -- server/src/yuno/modules/canonical/
server/src/yuno/modules/identity/` returns nothing — both modules, and therefore the D1
mechanism this gate audits and the `Role`/`RolePolicy` vocabulary all four commits reuse,
are byte-identical to round 3's inspection point. `uv run alembic heads` → `be4d11f03666
(head)`, unchanged from round 3 — none of the four commits carries a migration.

## B21: is it still one finding?

Round 3 raised B21 for `withdraw_source`'s reuse of `designated_editorial_approver` — D1's
canonical-publication grant — to gate an IDK-003 §8 act that IDK-003 itself attributes to a
"content owner" role IDK-003 §13 records as not existing in `owner_role_grants`. This round's
two mechanism commits both reuse the identical grant and both explicitly claim consolidation
under B21 rather than opening new findings. That claim is only partly right.

**The schema fact both docstrings rest on is verified, not assumed.** `owner_role_grants`'s
current DDL (dumped from a fresh scratch DB migrated to head,
`/private/tmp/.../scratchpad/gate2_round4_scratch.db`):

```
CONSTRAINT ck_owner_role_grants_role_valid CHECK (role IN ('learner','designated_editorial_approver'))
```

Live-tested, not just read: `INSERT INTO owner_role_grants (owner_id, role, assigned_at,
assigned_by_owner_id) VALUES ('owner1','content_owner', ...)` against that scratch DB failed
with `CHECK constraint failed: ck_owner_role_grants_role_valid`; the identical statement with
`role='designated_editorial_approver'` succeeded. `server/yuno.db`'s actual
`owner_role_grants` table (`sqlite3 -readonly server/yuno.db "SELECT owner_id, role FROM
owner_role_grants;"`) holds exactly two rows, both for the single local owner
(`01KZXCXSMEPP7XW5WNKH9RPTM0`): `designated_editorial_approver` and `learner`. No third value
has ever existed anywhere in this product's data. `identity/domain.py:28-30` confirms the
same two-member closed enum in code. So the premise both new functions' docstrings state —
"no distinct content-owner role exists" — checks out at every layer: enum, migration CHECK,
and the one production database.

**`register_source`'s reuse is genuinely the same finding as `withdraw_source`'s.** Both acts
are named by the same decision document, in the same section: IDK-003 §12 item 7
(`docs/decisions/IDK-003-source-licensing-and-snapshot-policy.md:187`) calls for source
registration "attributed to the content-owner role," and IDK-003 §13
(`:200`) is the same sentence `withdraw_source`'s B21 already rests on: "`owner_role_grants.role`
(`learner`, `designated_editorial_approver`) has no distinct content-owner value... unlike
D1's explicit grant for canonical publication." IDK-003 §13 draws its own comparison to D1
explicitly; the code is not inventing that analogy, it is following one the governing
decision itself states. Consolidating `register_source` under B21 is correct: same decision,
same named-but-missing role, same textual admission, same remedy (an IDK-002 or IDK-003
successor version).

**`load_rubric_manifest`'s reuse reaches further, and the docstring's consolidation claim
undersells that.** `load_rubric_manifest` gates `rubrics`/`rubric_dimensions` rows — IDK-204's
mechanism for IDK-009 content, not IDK-003 content. IDK-009 is a different governing decision
with its own, differently-worded approver role: `docs/decisions/IDK-009-assessment-and-derived-state.md:9`
— "Owner and approver: content/assessment owner, per PRD §13" — and its own change-control
table (`:361-363`) names "Content/assessment owner" as the role for approving future IDK-009
versions. That is a third label ("content/assessment owner"), not IDK-003's "content owner,"
and PRD §13's actual dependency table (`PRD.md:391-396`) has no row for assessment or rubric
content at all — its nearest row is "Initial canonical source set and source-license
review... Content owner TBD / editorial approver TBD" (`PRD.md:395`), which is IDK-003's
territory, not IDK-009's. IDK-009 is analogizing to a PRD row that was never about it.

More importantly: **IDK-009 never engages with the operational grant question at all.**
`grep -n -i "owner_role_grants\|grant\b\|designated_editorial_approver"
docs/decisions/IDK-009-assessment-and-derived-state.md` returns zero matches. IDK-003 §13
explicitly admits the schema gap and explicitly invites the D1 comparison
("unlike D1's explicit grant for canonical publication"); IDK-009 says nothing of the kind —
it never mentions `owner_role_grants`, never compares itself to D1, and its one on-point
sentence (`:40`, "these are evaluator calibration boundaries, not learner-facing role
descriptions") is about assessment-level labels, not database grants. `load_rubric_manifest`'s
docstring (`evidence_evaluation/service.py:930-950`) borrows IDK-003 §13's specific
admission and applies it to IDK-009's silence — an analogy the code constructs itself,
one level further removed from either governing text than `withdraw_source`'s or
`register_source`'s reuse, both of which point at a decision document that made the
admission in its own words.

**Net judgement**: B21 should not be read as one flat finding covering all three reuses.
`withdraw_source` and `register_source` are the same finding — same decision, same textual
basis, same remedy — and consolidating them is correct engineering judgement, not scope
creep. `load_rubric_manifest` is the same *mechanism* (identical code idiom, identical
schema fact, identical two-option trade-off) applied to a *different* cross-decision
question: it settles, in code, not just "who governs IDK-003 source acts" but "who governs
IDK-009 content acts" — a decision document B21's original remedy language (an IDK-002 or
IDK-003 successor version) does not cover, since neither of those two documents can resolve
an IDK-009-scoped role question. Folding it silently under B21's existing text would leave
the approver believing one decision-document action clears all three reuses, when clearing
`load_rubric_manifest`'s specifically would also require IDK-009 (or a role-defining
successor to IDK-002) to say something it currently does not.

**The trade-off reasoning itself holds, independent of the above.** Inventing a
`content_owner`/`content_assessment_owner` value in `owner_role_grants.role` would itself be
an unapproved vocabulary change: IDK-003 §14 (`docs/decisions/IDK-003-source-licensing-and-snapshot-policy.md`,
"## 14. Change control") requires a new decision version for changes to closed vocabularies
it names by example (registry tiers, the `withdrawal_reason` vocabulary); `owner_role_grants.role`'s
CHECK constraint is the identical kind of closed vocabulary, so the same principle extends to
it by direct analogy, even though §14 does not enumerate role values verbatim. And shipping
either write path ungated would have reopened, for two more production write paths, the exact
gap B7 closed for withdrawal: both functions are structured so the grant check lives inside
the service function itself rather than only in the CLI ("so no future caller can bypass it,"
`provenance/service.py:373-375`, `evidence_evaluation/service.py:947-948`), which is verified
correct, not merely asserted — see the grant-refusal tests below. Between "invent unapproved
vocabulary," "ship ungated," and "reuse the one grant that exists, and record the question,"
the third is the only one that does not itself create a new violation — but for
`load_rubric_manifest` specifically, "record the question" needs to name IDK-009, not just
IDK-002/IDK-003, as a document that may need to move.

**Live verification that the check is real, not documentation-only:**

```
server/src/yuno/modules/provenance/service.py:387
        RolePolicy.require(grants, Role.DESIGNATED_EDITORIAL_APPROVER)
server/src/yuno/modules/evidence_evaluation/service.py:990
        RolePolicy.require(grants, Role.DESIGNATED_EDITORIAL_APPROVER)
```

`pytest tests/integration/test_register_source_script.py` → 10 passed, including
`test_actor_without_the_grant_is_refused_and_writes_nothing` (`:158`).
`pytest tests/integration/test_load_rubric_manifest_script.py` → 11 passed, including
`test_load_refused_when_actor_lacks_the_grant_exits_1_and_writes_nothing` (`:221`). Both
counts match `grep -c "^    def test_" <file>` exactly (10 and 11 respectively) — not a
partial run. `uv run lint-imports` → "Contracts: 4 kept, 0 broken" with the new
`yuno.modules.evidence_evaluation.service -> yuno.modules.identity.**` entry
(`server/pyproject.toml:221`, added by `4493208` alongside a rationale comment naming B21)
in place alongside the pre-existing `provenance.service -> identity` entry `5596654`
added in round 3.

## Re-verification: B3, no production `editorial_approvals` row

- `sqlite3 -readonly server/yuno.db "SELECT COUNT(*) FROM editorial_approvals;"` → `0`.
- `sqlite3 -readonly server/.e2e.db "SELECT COUNT(*) FROM editorial_approvals;"` → `0`.
- `server/yuno.db`'s `alembic_version` = `4747447ccaa3`, still two revisions behind this
  tree's actual head `be4d11f03666` — unchanged from round 3; none of this round's four
  commits carries a migration, so this gap did not move.
- `server/.e2e.db`'s `alembic_version` = `a9d4e6f1b208`, further behind, unchanged.
- `sqlite3 -readonly server/yuno.db "SELECT COUNT(*) FROM canonical_graph_versions;"` → `0`;
  `... FROM sources;` → `0`; `... FROM rubrics;` → `0` — neither a canonical version, a
  source, nor a rubric has ever been registered in the local production database, and
  `register_source`/`load_rubric_manifest` (both offline CLIs with exactly one caller today
  — themselves) have not been run against it this round.
- IDK-002 §8 (`docs/decisions/IDK-002-editorial-approval-criteria.md:119`): "No existing row
  needs migration: no production canonical graph version has ever been published." Still
  true; re-confirmed directly against the current database, not assumed from the decision
  text.

**Still open, unchanged from rounds 1-3.**

## Re-verification: the D1 mechanism (basis_ref validation, publish_canonical_graph)

`git diff 93103cd..825a01f -- server/src/yuno/modules/canonical/` returns empty — the
canonical module is byte-identical to round 3's inspection point, confirmed directly rather
than inferred from the commit messages (none of the four names canonical work).

- `server/src/yuno/modules/canonical/models.py:432` — `CheckConstraint("json_valid(basis_ref)",
  name="basis_ref_valid")`, read directly this session.
- Scratch DB (`/private/tmp/.../scratchpad/gate2_round4_scratch.db`, fresh this session)
  migrated with `YUNO_DATABASE_URL=sqlite+pysqlite:////.../gate2_round4_scratch.db uv run
  --directory server alembic upgrade head` → all 30 migrations ran cleanly to
  `be4d11f03666`, exit 0. `.schema editorial_approvals` on that DB shows
  `ck_editorial_approvals_basis_ref_valid CHECK (json_valid(basis_ref))` and
  `ck_editorial_approvals_approver_role_valid CHECK (approver_role IN
  ('designated_editorial_approver'))`, plus all three immutability triggers
  (`trg_editorial_approvals_no_update`/`_no_delete`/`_no_insert_replace`), bodies read and
  unchanged from round 3's dump.
- `server/src/yuno/modules/canonical/publisher.py` ordering, re-confirmed by reading the
  file directly: grant check `RolePolicy.require(grants, Role.DESIGNATED_EDITORIAL_APPROVER)`
  at `:140` (preceded by `grants = uow.owners.grants(actor_owner_id)` at `:139`),
  `validate_basis_ref(...)` at `:143`, first write `uow.canonical.create_version(version)`
  at `:181`, `uow.canonical.record_approval(approval)` last at `:221` — identical ordering
  and identical line numbers to round 3, because the file has not changed.
- `pytest tests/integration/test_canonical_basis_ref_constraint.py
  tests/integration/test_canonical_publish.py
  tests/unit/test_canonical_basis_ref_validation.py` → 60 passed, run fresh this session,
  matching round 3's count exactly.
- `pytest tests/integration/test_withdraw_source_script.py
  tests/integration/test_provenance_withdrawal.py` → 15 passed, run fresh this session,
  matching round 3's count exactly. `withdraw_source`'s own grant check
  (`RolePolicy.require(grants, Role.DESIGNATED_EDITORIAL_APPROVER)`) now sits at
  `provenance/service.py:271` rather than round 3's `:190-191` — the function's *logic* is
  untouched (`git diff 93103cd..825a01f` for this hunk shows only line-number movement from
  code inserted earlier in the file, not a change to `withdraw_source` itself). That shift
  broke two self-referential citations elsewhere in the tree; see "HEAD delta check" above
  and "Notes and residual risk" below — `636bf26` corrects both.

**The new grant checks follow the same idiom, not a looser one.** `register_source`
(`provenance/service.py:385-387`) and `load_rubric_manifest`
(`evidence_evaluation/service.py:987-990`) both open a `with uow_factory() as uow:` block,
call `uow.owners.grants(owner_id)`, and call `RolePolicy.require(grants,
Role.DESIGNATED_EDITORIAL_APPROVER)` before any read or write inside that block — the
identical shape as `publisher.py:139-140` and `provenance/service.py:270-271`. Neither new
function accepts a caller-supplied role, weakens the check to `RolePolicy.has` (a boolean
check that would let a caller silently no-op instead of failing), or moves the check after
any write. This was verified by reading both functions in full, not sampled.

## Confirming none of the four commits touches production approval/publication state

- `git diff 93103cd..825a01f | grep -n "editorial_approvals\|publish_canonical_graph\|record_approval"`
  → five hits, all inside new docstring prose comparing the new grant checks to
  `publish_canonical_graph`'s; zero in executable code.
- `grep -rln "editorial_approvals\|canonical_graph_versions\|publish_canonical_graph"
  server/tests/integration/test_register_source_script.py
  server/tests/integration/test_load_rubric_manifest_script.py
  server/tests/integration/test_provenance_snapshot_janitor.py
  server/tests/integration/test_provenance_staleness_recheck.py` → no matches in any of the
  four new test files.
- `grep -rn "publish_canonical_graph(" --include='*.py' server/` → exactly three hits:
  its own `def`, and its two pre-existing callers (`scripts/publish_canonical.py`,
  `scripts/seed_performance_dataset.py`) — no new caller.
- `grep -rn "record_approval(" --include='*.py' server/` → exactly three hits: the port
  definition, the repository implementation, and `publisher.py:221`'s single call site —
  unchanged from round 3.
- Confirmed independently: **no**, none of the four commits publishes a canonical graph or
  writes a production `editorial_approvals` row.

## Inspected artifacts

| Artifact | What it is | How inspected |
| --- | --- | --- |
| `docs/decisions/IDK-002-editorial-approval-criteria.md` | Governing decision | Read directly this session; §2 "Who approves" (`:25`), §8 (`:119`), §10 (`:142-146`) |
| `docs/decisions/IDK-003-source-licensing-and-snapshot-policy.md` | Governs source withdrawal/registration | Read directly; approver-role line (`:11`), §12 item 7 (`:187`), §13 (`:200`), §14 change control |
| `docs/decisions/IDK-009-assessment-and-derived-state.md` | Governs rubric/assessment content, newly relevant this round | Read in full this session; §1 approver line (`:9`), §3 (`:40`), §11 (`:346`), §12 change-control table (`:361-363`); repo-wide grep for `owner_role_grants`/`grant`/`designated_editorial_approver` → zero hits |
| `PRD.md` | Appendix H D1 and the §13 dependency table | Re-read `:352` (D1), `:391-399` (dependency table, confirmed no assessment/rubric row exists) |
| `docs/approvals/IDK-503-rerun-2026-08-15-b/gate-2-editorial-approvals.md` | Round-3 gate record | Read for scope only, per instruction; citations treated as stale and re-derived |
| `docs/approvals/IDK-503-content-and-safety-review-rerun-2026-08-15-b.md` | Round-3 consolidated record, source of B21/B3's numbering | Read for the B21 finding text (`:82`, `:94`) and B3 (`:71`); both re-cited by the new commits' own docstrings and checked here |
| `git log 93103cd..825a01f` / `git show --stat <each>` | The four commits since round 3 | Each read individually; two assessed as not bearing on this gate, two assessed in depth |
| `server/src/yuno/modules/provenance/service.py:297-412` | `register_source`, incl. grant check and docstring | Read in full |
| `server/src/yuno/modules/evidence_evaluation/service.py:882-1044` | `load_rubric_manifest`, incl. grant check and docstring | Read in full |
| `server/src/yuno/modules/provenance/adapters.py` | Snapshot janitor (`2b5ebc2`) | Read in full; confirmed no `identity` import or grant check |
| `server/src/yuno/modules/provenance/service.py:1-90` (staleness functions) | Staleness re-check (`825a01f`) | Read in full; confirmed no grant check; confirmed it is what shifted `withdraw_source`'s line numbers |
| `server/src/yuno/modules/identity/domain.py:28-30` | `Role` enum, closed to two members | Read directly |
| Scratch DB `gate2_round4_scratch.db` | Fresh SQLite DB migrated to head, unique to this round | Created under this session's scratchpad; `alembic upgrade head` exit 0, 30 migrations incl. `be4d11f03666`; never touched `server/yuno.db`/`server/.e2e.db` |
| Scratch DB live INSERT tests | `owner_role_grants.role` CHECK enforced at the DB layer | `INSERT ... role='content_owner'` → rejected; `INSERT ... role='designated_editorial_approver'` → succeeded |
| `server/tests/integration/test_canonical_basis_ref_constraint.py`, `test_canonical_publish.py`, `server/tests/unit/test_canonical_basis_ref_validation.py` | basis_ref mechanism tests | Run: 60 passed |
| `server/tests/integration/test_withdraw_source_script.py`, `test_provenance_withdrawal.py` | Grant-check + withdrawal-mechanism tests | Run: 15 passed |
| `server/tests/integration/test_register_source_script.py` | Registration mechanism + grant-refusal test | Run: 10 passed, matches `def test_` count |
| `server/tests/integration/test_load_rubric_manifest_script.py` | Rubric-load mechanism + grant-refusal test | Run: 11 passed, matches `def test_` count |
| `server/tests/integration/test_provenance_snapshot_janitor.py`, `test_provenance_staleness_recheck.py` | The two commits not bearing on this gate | Run: 19 passed combined — confirms they function; confirms (by absence of any identity/grant reference) they do not touch this gate |
| `uv run lint-imports` | Import-linter contracts | Run: 4 kept, 0 broken, including the new `evidence_evaluation.service -> identity` entry |
| `uv run alembic heads` | Current migration head | Run: `be4d11f03666 (head)`, unchanged from round 3 |
| `server/yuno.db`, `server/.e2e.db` | Local/e2e SQLite DBs | `sqlite3 -readonly` queries only: `editorial_approvals`/`canonical_graph_versions`/`sources`/`rubrics` row counts, `alembic_version`, `owner_role_grants` |
| `server/tests/architecture/test_import_boundaries.py` | Full architecture suite, incl. the declaration-parity test `636bf26`/`0f3219f` touch | Run at current HEAD: 822 passed. Separately run at a detached worktree pinned to round-3 HEAD `93103cd`: `test_pyproject_declares_the_required_contracts` alone → 1 failed, actual assertion diff read; worktree removed after |
| `./server/.venv/bin/lint-imports --config server/pyproject.toml` | Import-linter, run directly (not via `uv run`) to confirm the fixed test's own environment | Run: 4 kept, 0 broken, unchanged |

## Findings

| # | Item | Verdict |
| --- | --- | --- |
| 1 | §8 item 1 `json_valid(basis_ref)` CHECK constraint | **closed** — re-confirmed at the database layer this session |
| 2 | Immutability triggers survive the batch-rebuild migration | **closed** — all three present, bodies unchanged |
| 3 | Framework-free §4 schema validation invoked before any write | **closed** — `publisher.py:143` before `:181`'s first insert; file unchanged since round 2 |
| 4 | §4's 15-field contract | **closed for presence** — file byte-identical since round 2, not re-walked field-by-field this round for the same reason round 3 gave |
| 5 | `reviewed_manifest_hash` cross-check | **closed** — file unchanged |
| 6 | `review_kind`/published-state consistency check | **closed** — file unchanged, re-confirmed via passing tests |
| 7 | `scripts/publish_canonical.py` rejects a malformed `basis_ref` | **closed** — unchanged since round 2; not re-executed this round, no code in this path changed |
| 8 | Single write path to `editorial_approvals` (`record_approval`) | **closed** — `publisher.py:221` still the only call site; `register_source`/`load_rubric_manifest` (new this round) write only to `sources`/`rubrics`, confirmed by reading both functions and grepping their test files |
| 9 | No placeholder `basis_ref` on a production version | **matches (nothing to violate yet)** — unchanged |
| 10 (B3) | No production `editorial_approvals` row exists | **still open** — re-confirmed this session, see blocking finding 1 |
| 11 (B21) | `designated_editorial_approver` grant reuse for an act D1/IDK-002 never scoped it to | **still open, and its scope has widened this round** — see blocking finding 2 |
| 12 | Import-boundary contract-declaration test (`test_pyproject_declares_the_required_contracts`) red since round 3's `796fa30`, undetected by any gate | **found and closed within this round** — reproduced independently at round-3 HEAD (`1 failed`), fixed by `0f3219f`, re-verified (822 passed, `lint-imports` 4 kept/0 broken); not a blocking finding, see "HEAD delta check" above |

## Blocking findings

### 1. No production `editorial_approvals` row exists to inspect against §4's mechanically-enforced criteria (B3)

- What is missing: any row in `editorial_approvals` on either database available for
  inspection.
- Owning ticket: IDK-102 (production seed run) — IDK-002 §8 (`:119`) states no production
  canonical graph version has ever been published, and names IDK-503 as the check that must
  run once one is.
- Evidence of absence: `sqlite3 -readonly server/yuno.db "SELECT COUNT(*) FROM
  editorial_approvals"` → `0`; same query against `server/.e2e.db` → `0`. Re-verified
  directly this session, read-only, against the current tree; unchanged since rounds 1-3,
  and none of this round's four commits could have changed it (no migration, no new caller
  of `record_approval`, confirmed above).
- Status vs. previous rounds: still open, unchanged.
- What would clear it: run IDK-102's production seed against a real manifest under
  `editorial-approval-criteria-v1`, producing a `basis_ref` conforming to §4, then re-inspect
  the row's actual field content against §4/§5's exhaustiveness and sampling rules — not
  merely that a row exists.

### 2. `designated_editorial_approver`'s reuse for non-D1 write paths now spans three write paths and two governing decisions outside IDK-002; the newest of the three reaches further than the finding's current remedy language covers (B21)

- What is missing: a decision-document basis for treating (a) source withdrawal and
  registration (IDK-003 §8, §12 item 7) and (b) approved rubric-manifest loading (IDK-204's
  mechanism for IDK-009 content) as acts the `designated_editorial_approver` grant (IDK-002/D1)
  authorizes. No such basis exists today for either.
- Owning ticket: none named for either gap. (a) sits at the IDK-002/IDK-003 boundary, exactly
  as round 3 recorded for `withdraw_source` — an IDK-002 successor version (widening "who
  approves") or an IDK-003 successor version (adding the missing grant IDK-003:200 already
  names as absent) would resolve it, and `register_source` is the identical question,
  correctly consolidated under it. (b) is a **new boundary this round**: it sits at the
  IDK-002/IDK-009 boundary instead, and neither an IDK-002 nor an IDK-003 successor version
  resolves it on its own — IDK-009 itself would need to define an operational grant for its
  own "content/assessment owner" role (`IDK-009:9`), or IDK-002 would need to widen "who
  approves" a second time to name a role IDK-009 controls. Both are decision-document
  changes this inspection is expressly forbidden from making.
- Evidence of absence / of the conflict:
  - `owner_role_grants.role` admits only `learner` and `designated_editorial_approver`,
    confirmed live on a scratch DB this session (CHECK constraint rejects any third value)
    and in `server/yuno.db`'s actual two rows.
  - `docs/decisions/IDK-003-source-licensing-and-snapshot-policy.md:187` (§12 item 7)
    attributes source registration to "the content-owner role"; `:200` (§13) states plainly
    that no such grant exists, "unlike D1's explicit grant for canonical publication" — the
    same sentence B21 already rested on for withdrawal, and `register_source`
    (`provenance/service.py:363-382`) cites it identically.
  - `docs/decisions/IDK-009-assessment-and-derived-state.md:9` names a *third* role label,
    "content/assessment owner, per PRD §13" — distinct from IDK-003's "content owner" — and
    `PRD.md:391-396`'s dependency table has no row for assessment/rubric content at all;
    its nearest row (`:395`, source-license review) is IDK-003's territory, not IDK-009's.
  - `docs/decisions/IDK-009-assessment-and-derived-state.md` contains zero references to
    `owner_role_grants`, "grant," D1, or `designated_editorial_approver` anywhere (confirmed
    by repo grep this session) — unlike IDK-003 §13, IDK-009 never itself raises or admits
    the operational-grant question `load_rubric_manifest`'s docstream answers on its behalf.
  - `server/src/yuno/modules/evidence_evaluation/service.py:990` now checks
    `Role.DESIGNATED_EDITORIAL_APPROVER` before `load_rubric_manifest` runs; verified live:
    `pytest tests/integration/test_load_rubric_manifest_script.py` → 11 passed, including a
    test that a missing grant is refused with exit 1
    (`test_load_refused_when_actor_lacks_the_grant_exits_1_and_writes_nothing`).
  - `server/src/yuno/modules/provenance/service.py:387` checks the same role before
    `register_source` runs; `pytest tests/integration/test_register_source_script.py` → 10
    passed, including the equivalent grant-refusal test (`:158`).
- What would clear it: two decision-document actions, not one. (a) For source
  withdrawal/registration: an IDK-002 successor version explicitly extending
  `designated_editorial_approver`'s authorized-acts list to cover IDK-003 §8/§12, or an
  IDK-003 successor version introducing the distinct content-owner grant IDK-003:200 already
  flags as missing. (b) For rubric-manifest loading: an IDK-009 successor version defining an
  operational grant for its own "content/assessment owner" role (and reconciling that label
  against IDK-003's separately-named "content owner," since a single approver acting under
  two near-synonymous, textually distinct role names is itself worth resolving in the same
  pass), or a second IDK-002 widening naming IDK-009 content specifically. Either requires
  the product/content owner's decision, not further engineering — this inspection implements
  neither.

## Notes and residual risk

- **The D1 mechanism this gate exists to audit is unaffected by this round's changes and
  remains sound.** `server/src/yuno/modules/canonical/` is byte-identical to round 3's HEAD;
  this round independently re-derived that by diffing the path directly, migrating a fresh
  scratch DB, and running 60 tests, rather than trusting round 3's word for it.
- **A citation inside the shipped code itself had gone stale within this very set of
  commits — now corrected in `636bf26`, verified rather than trusted.** `load_rubric_manifest`'s
  docstring (`evidence_evaluation/service.py:939,950`) cited `withdraw_source`'s grant check
  at `provenance/service.py:190-191` and its rationale paragraph at `:174-186` — both
  accurate when `4493208` (the oldest of this round's four commits) was written, matching
  round 3's own citations exactly. `825a01f` (the newest of the four, landed roughly 30
  minutes later per commit timestamps) then inserted 74 lines before `withdraw_source` in the
  same file for the staleness-recheck feature, shifting the real grant check to `:271` and
  the rationale paragraph to roughly `:253-266`, without either citation being updated. This
  inspection recorded that drift; `636bf26` ("fix: correct five line citations this round's
  own commits invalidated"), which landed after the body of this inspection but before this
  record was finalized, corrects exactly those two citations to `:270-271` and `:253-266` —
  independently re-derived against the current tree under "HEAD delta check" above and
  confirmed correct: `:270-271` is the grant check, `:253-266` is the rationale paragraph.
  The same commit also swept up three more citations this round's other commits broke
  (in `docs/assessment/IDK-009-critical-dimension-exposure.md`, `test_runner.py`, and
  `docs/runner/IDK-406-execution-deferral.md` — gate 5/7 territory, read but not
  independently re-derived here) and explicitly declined to fix a fourth, pre-existing,
  unrelated stale citation (`IDK-406-execution-deferral.md`'s `runner/adapters.py:86`
  pointer, stale since before round 3 and not caused by this round), reporting it to the
  owner instead of silently widening its own scope. This was never elevated to a blocking
  finding, and remains not one now that it is fixed — `withdraw_source`'s logic was never in
  question, only a documentation pointer to it.
- **B21's practical blast radius stays limited today, for the same reason round 3 gave.**
  The single local owner already holds `designated_editorial_approver`, so this round's two
  new reuses grant no new party any new access; the concern remains architectural (what does
  the grant authorize, and who decides that) rather than an active security exposure.
- **The two commits not bearing on this gate (`2b5ebc2`, `825a01f`) were checked, not
  assumed.** Both are automated maintenance triggered by elapsed time/count, both explicitly
  document why they need no editorial grant, and both pass their own test suites (19 passed
  combined) — confirming they function without confirming, by itself, that they are correctly
  unscoped; that check was done separately by reading `adapters.py` and the staleness
  functions directly for the absence of any `identity` import or grant call.
- **This gate still cannot reach "inspection-passed" status.** Blocking finding 1 (B3, no
  production row) is unchanged from all three prior rounds and requires an actual IDK-102
  seed run. Blocking finding 2 (B21) is now wider than round 3 recorded it and requires
  decision-document action from the approver across two decisions (IDK-002/IDK-003 for
  source acts, IDK-002/IDK-009 for rubric-content acts), not one.
