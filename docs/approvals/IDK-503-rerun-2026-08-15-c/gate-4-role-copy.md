# IDK-503 rerun (2026-08-15, round 4) gate 4 — Learner-facing role copy and taxonomy

- Gate: Learner-facing role copy and taxonomy
- Reviewer role required: designated editorial approver
- Inspection date: 2026-08-15
- Disposition: blocking-finding
- Attestation: pending -- designated editorial approver has not signed this gate. No attestation was sought or recorded during this inspection.

This is round 4, a fresh independent re-inspection originally conducted against HEAD `825a01f0e954e89640eb517f4e41faf2ea964af2` (`825a01f`), not a diff against round 3. The coordinator then advanced the tree by two commits while this file was in progress: current HEAD is `0f3219f6a8b2a2436fce6d36c918307655a53c84` (`0f3219f`) -- see "HEAD delta check" below for that re-derivation, done by reading the actual diffs, not by trusting the commit messages. Round 3's `docs/approvals/IDK-503-rerun-2026-08-15-b/gate-4-role-copy.md` (HEAD `7b805bd`) was read only to recover scope and the open-findings list, per instruction; every citation below was independently re-derived against the relevant HEAD by direct file reads, greps, and test runs, not copied forward. Round 1 (`docs/approvals/IDK-503/`), round 2 (`docs/approvals/IDK-503-rerun-2026-08-15/`), and round 3 were not edited. Two prior rounds already used the calendar date 2026-08-15, so this round -- identified by the tree it inspects, not the date -- takes the `-c` suffix.

## HEAD delta check (`825a01f` → `0f3219f`)

`git log --oneline 825a01f..0f3219f` shows two commits landed after this gate's original inspection: `636bf26` ("fix: correct five line citations this round's own commits invalidated") and `0f3219f` ("fix: restore the import-boundary contract-declaration test to green").

`git diff 825a01f 0f3219f --stat`:

```
 docs/assessment/IDK-009-critical-dimension-exposure.md | 2 +-
 docs/runner/IDK-406-execution-deferral.md              | 2 +-
 server/src/yuno/modules/evidence_evaluation/service.py | 4 ++--
 server/tests/architecture/test_import_boundaries.py    | 7 +++++++
 server/tests/integration/test_runner.py                | 2 +-
 5 files changed, 12 insertions(+), 5 deletions(-)
```

`git diff 825a01f 0f3219f -- src/selected/ server/src/yuno/api/routes/ server/src/yuno/modules/hands_on/` returns no output -- confirmed empty: this delta touches none of the surfaces this gate cares about.

Both commits read in full, not just the stat:

- **`636bf26`**: five line-number corrections inside docstrings/comments, all in files this round's own commits (`90e23c3`, `2b5ebc2`, `825a01f`, `4493208`) shifted underneath: `evidence_evaluation/service.py:939,950` (two citations of `provenance/service.py`'s `withdraw_source` grant check, now `:270-271` and `:253-266`), `docs/assessment/IDK-009-critical-dimension-exposure.md:13` (a citation of `service.py:384`, now `:389`), `server/tests/integration/test_runner.py:351` (a comment citing `api/app.py:863`, now `:1045`), `docs/runner/IDK-406-execution-deferral.md:21` (citing `api/app.py:784`, now `:966`). No line count changes in any of the four; only the cited numbers change. None of these four files is a frontend file, a route file, or part of the hands_on module.
- **`0f3219f`**: adds exactly two string literals to `server/tests/architecture/test_import_boundaries.py`'s `test_pyproject_declares_the_required_contracts` expected-set list -- `"yuno.modules.provenance.service -> yuno.modules.identity.**"` and `"yuno.modules.evidence_evaluation.service -> yuno.modules.identity.**"` -- restoring parity between that test's literal and `server/pyproject.toml`'s already-existing import-linter contract (the `pyproject.toml` entries themselves were added by `796fa30` last round and `4493208` this round; this commit only catches the test up). These are Python import-path strings compared inside a test assertion, never rendered to any UI surface.

**Verdict: neither commit ships learner-facing copy.** `636bf26` changes only line-number citations inside docstrings, a comment, and a `docs/` maintenance note -- prose that already existed, repointed to its new location, no new sentence and no substantive claim. `0f3219f` changes only a Python test's expected-set literal -- an assertion input, not a string any learner-facing code path could reach. Both are consistent with this round's finding that the four new production commits (`4493208`, `90e23c3`, `2b5ebc2`, `825a01f`) shifted line numbers underneath pre-existing citations without adding any new user-visible surface.

**This gate's findings are unaffected by the delta**, re-confirmed directly rather than assumed: `git diff 825a01f 0f3219f -- server/src/yuno/modules/hands_on/` is empty (B10 content half's evidence, `hands_on/service.py:105-119`, is untouched); `git diff 825a01f 0f3219f -- src/selected/core/CorePages.tsx` is empty (B17's `:204/245/390/392/399` and `:815/828-829/861`, B22's `:815-819/828-832/859-861`, and both carried-forward copy items -- the blank `<option value="">` placeholder at `:390`/`:860` and IDK-004 §4's "Not sure" helper text, still absent from `src/selected` -- are all unaffected, since the file that carries every one of those citations did not change in this delta). No test file this gate executed (`ProfileGoalsPages.test.tsx`, `InterviewHub.test.tsx`) appears in `636bf26`'s or `0f3219f`'s changed-file list, so the 26-passed/0-failed result recorded below still holds without a re-run.

## The four new commits: none ship learner-facing copy

`git log --oneline 93103cd..825a01f` names four commits landed since round 3: `4493208` (rubric manifest loader), `90e23c3` (source registration CLI), `2b5ebc2` (snapshot janitor), `825a01f` (staleness re-check). Determined independently, not assumed from the commit messages:

- **File surface.** `git diff --stat 93103cd..825a01f -- src/selected/` returns no output: zero frontend files touched by any of the four commits. `git diff --stat 93103cd..825a01f -- server/src/yuno/api/routes/` also returns no output: zero route files touched, and `git diff 93103cd..825a01f -- server/src/yuno/api/app.py | grep -nE '@app\.|@router\.|APIRouter'` returns no matches -- no new HTTP endpoint is added anywhere in this delta. The full file list (`git diff --stat 93103cd..825a01f`) touches only `server/pyproject.toml`, two new `server/scripts/*.py` CLIs, `server/src/yuno/api/app.py`, `server/src/yuno/modules/evidence_evaluation/service.py`, `server/src/yuno/modules/provenance/{adapters,service}.py`, and three new integration test files.
- **`4493208`** (`git show --stat`): adds `server/scripts/load_rubric_manifest.py` (offline CLI, argparse + `print(..., file=sys.stderr)` only, no FastAPI/ASGI import), `evidence_evaluation/service.py`'s `load_rubric_manifest`/`_validate_rubric_dimension_structure` functions, and a `server/pyproject.toml` import-linter rule. `grep -rn "load_rubric_manifest" server/src/yuno/api/` returns no output -- the new service function is not wired into any route, so no learner request path can reach it.
- **`90e23c3`** (`git show --stat`): adds `server/scripts/register_source.py` (same offline-CLI shape: `argparse`, `print(..., file=sys.stderr)`, no ASGI import, docstring at `register_source.py:18-24` states this explicitly -- "An HTTP route would additionally require learner-facing copy this project is forbidden to invent, and this script, like its two siblings, carries none") and `provenance/service.py`'s `register_source` function. `grep -rn "register_source" server/src/yuno/api/` returns no output -- not wired into any route.
- **`2b5ebc2`** (`git show --stat`): adds `apply_snapshot_janitor` to `app.py`'s periodic-task closure and `prune_excess_snapshot_bodies` to `provenance/adapters.py`. Read in full: the only new strings are `log_event` event names (`"snapshot_janitor.cycle.failed"`, `"snapshot_janitor.cycle.completed"`) and docstring prose -- structured server logs, never returned in an HTTP response body or rendered anywhere in `src/selected`.
- **`825a01f`** (`git show --stat`): adds `apply_staleness_recheck` to the same periodic-task closure and `sources_due_for_recheck`/`reserve_source_retrieval` (re-export) to `provenance/service.py`. Read in full: same pattern -- `log_event` event names (`"staleness_recheck.cycle.skipped"`, etc.) and docstring prose only. `reserve_source_retrieval` is also imported by the pre-existing `routes/provenance.py:31` (unchanged by this delta, confirmed by `git diff 93103cd..825a01f -- server/src/yuno/api/routes/provenance.py` returning no output) -- that route path is out of this delta's scope and was not re-inspected here since nothing in it changed.

**Verdict: none of the four commits introduces learner-facing copy.** All four are, as expected, server-side offline CLIs, service functions, and background-job wiring with operator-facing stdout/stderr (the two new scripts) or structured-log-only (the two `app.py` periodic-task additions) surfaces. This gate exists to catch exactly the case round 3 found (B22: `BundleEditor.createBundle` interpolating a level into a bundle name) -- no equivalent defect exists in this delta because none of the four commits touches any file capable of rendering to a learner: no `src/selected/**` file changed, and no new HTTP route was added.

## Re-inspection of the gate's standing findings, from scratch

### B10 (content half) — still open, re-derived fresh

`git log --oneline 7b805bd..825a01f -- server/src/yuno/modules/hands_on/` returns no output: the hands-on module is untouched since round 3. Direct read of `server/src/yuno/modules/hands_on/service.py:105-119`:

```
105:        work = HandsOnWork(
106:            new_id(),
107:            owner_id,
108:            goal_id,
109:            topic_id,
110:            f"{topic.title} hands-on scenario",
111:            f"Create and defend a solution for the approved {topic.title} topic boundary.",
112:            role,
113:            level,
114:            constraints,
115:            "fixture",
116:            None,
117:            "fixture-pending-idk-009",
118:            timestamp,
119:        )
```

Field order confirmed against `server/src/yuno/modules/hands_on/domain.py:12-25`'s `HandsOnWork` dataclass: positions 10-12 are `scenario_status`, `scenario_id`, `scenario_source`. Every synthesized row still hardcodes `scenario_status="fixture"`, `scenario_id=None`, `scenario_source="fixture-pending-idk-009"`. `grep -rn "idk009-v1-r1\|scenario_id" server/src/yuno/modules/hands_on/*.py` matches only the `domain.py`/`models.py`/`repository.py` field declarations -- no scenario-ID literal anywhere.

`docs/decisions/IDK-009-assessment-and-derived-state.md:323` ("The twelve records in this decision are the representative approved seed") and `:350` ("IDK-503: manually review all twelve shipped records") confirm the "twelve approved scenario records" framing. `IMPLEMENTATION_TICKETS.md:1686` (re-read this round): IDK-405's status is still "Content incomplete ... every synthesized `HandsOnWork` row still hardcodes `scenario_status="fixture"`, `scenario_id=None`, and `hands_on_work` holds zero rows. IDK-503 re-run findings B10 and B12."

Database confirmation, this round: `sqlite3 -readonly server/yuno.db "SELECT COUNT(*) FROM hands_on_work;"` → `0`; `sqlite3 -readonly server/.e2e.db "SELECT COUNT(*) FROM hands_on_work;"` → `0`. Alembic head confirmed via `uv run --directory server alembic heads` → `be4d11f03666 (head)`, unchanged; `sqlite3 -readonly server/yuno.db "SELECT version_num FROM alembic_version;"` → `4747447ccaa3` (behind head); `.e2e.db` → `a9d4e6f1b208` (behind head). Neither database is evidence for or against the schema half (B10 schema half remains closed per round 3, re-confirmed by direct source read of `server/src/yuno/modules/hands_on/models.py:31-40`, which still shows `ck_hands_on_work_hands_on_scenario_status_valid CHECK (scenario_status IN ('fixture','approved'))` and a nullable `scenario_id`; both immutability triggers are still present in `server/src/yuno/migrations/versions/be4d11f03666_hands_on_scenario_status_and_id.py`).

**Still open, unchanged since round 2 and round 3.**

### IDK-004 `role-competency-copy-v1` — verified verbatim, re-derived fresh

`git log --oneline 7b805bd..825a01f -- src/selected/` returns no output: the entire frontend is untouched since round 3. A fresh Python byte-comparison script (regex-extracting the blockquoted heading/audience-note/title-variation-helper/target-capability-helper from `docs/decisions/IDK-004-role-level-competencies.md` §2, and the corresponding exported constants and per-level `label`/`description` pairs from `src/selected/core/CorePages.tsx:48-68`, then comparing with Python string equality, not eyeballing) confirms all four standalone strings and all three per-level `{label, description}` pairs match byte-for-byte, including the U+2014 em dash in the title-variation helper (`'—'` in the source string, confirmed via `in` check). `aria-describedby` wiring re-confirmed intact by direct read: onboarding (`CorePages.tsx:390-392`), bundle create (`:860`), bundle edit (`:867`).

Every line number cited (`CorePages.tsx:48-68`, `:204`, `:245`, `:389-392`, `:399`, `:798-876`, `:860-862`, `:949-950`) was independently re-read this round and is identical to round 3's citations for the same lines, consistent with the file being byte-identical since round 3.

### Two items carried forward, explicitly not resolved

Per instruction, these are re-verified as still-open and not resolved with invented copy:

1. **The level `<select>`'s empty placeholder label.** `CorePages.tsx:390` (onboarding) and `:860` (bundle create) both still render `<option value="" />` -- no text content. `grep -c 'option value=""' src/selected/core/CorePages.tsx` confirms both instances still present. IDK-004 §2's "Exact learner-facing copy" section (the only section using verbatim blockquotes, confirmed by re-reading `docs/decisions/IDK-004-role-level-competencies.md:19-43`) contains no placeholder string for this control. **What the approver must supply:** either an approved placeholder string for the blank `<option>` (e.g., something naming the unselected state for a screen-reader user), or an explicit decision that a blank label is acceptable. No copy is proposed here.
2. **Whether IDK-004 §4's "Not sure" helper text was meant to ship.** `docs/decisions/IDK-004-role-level-competencies.md:63`: "'Not sure' is helper text, not a fourth stored level: choose Mid-level for bounded component work, Senior for end-to-end flows, or Staff for cross-system and multi-team decisions." `grep -rn "Not sure" docs/decisions/IDK-004-role-level-competencies.md src/selected server/src/yuno` matches only the decision document -- no "Not sure" affordance, option, or paraphrase exists anywhere in `src/selected`, unchanged since round 3. **What the approver must supply:** a determination of whether this sentence was meant to render as on-screen helper copy next to the level selector (and if so, in what exact wording -- none is proposed here), or whether it is meta-guidance that only constrains a future "not sure" affordance to never become a stored fourth level. Either reading is defensible from the decision text alone; this inspection does not resolve it.

### B17 — re-verified, still closed

`CorePages.tsx:204`: `const [targetLevel, setTargetLevel] = useState<GoalCreate['target_level'] | ''>('')` -- comment at `:202-203` cites IDK-004 §4 directly. `:245`: `if (!graphVersion || !targetLevel) return` gates `beginDiagnostic` itself. `:390`: `<option value="" />` is the first, initially-selected option in the target-level `<select>`. `:392`: the per-level description renders only `{targetLevel && ...}`. `:399`: the visible submit button's `disabled` expression includes `!targetLevel`. All five citations re-read directly this round; all five line numbers match round 3's exactly.

`BundleEditor`'s secondary instance, re-read: `:815` `const [createLevel, setCreateLevel] = useState<InterviewLevel | ''>('')`; `:828-829` `if (!createLevel || !createName.trim()) return` inside `createBundle`; `:861` the create button's `disabled` expression includes `!createLevel`.

**Closed** -- a learner cannot reach a stored level (in either onboarding or bundle creation) without an explicit choice.

### B22 — re-verified, still closed

`grep -n "backend interview" src/selected/core/*.tsx`: the only matches are in `InterviewHub.test.tsx` (test-fixture data, lines 12/57/162), not in any app source file. The `` `${createLevel} backend interview` `` template string that round 3's blocking finding 2 caught does not exist anywhere in `CorePages.tsx`. Direct read of `BundleEditor` (`:806-820`, `:828-842`, `:858-862`):

- `:815-816`: `createLevel` starts unselected (`''`).
- `:819-820`: a `createName` state (`useState('')`) with a comment: "The bundle's name is the learner's, not the product's. A generated default (e.g. a level interpolated into a sentence) would be learner-facing copy no decision document has reviewed -- see IDK-503 round 3, gate 4."
- `:828-829`: `createBundle`'s guard is `if (!createLevel || !createName.trim()) return`.
- `:832` (inside the mutation call at `:828-842`): `name: createName.trim()` -- the only value that ever reaches the API is learner-typed text; no template, no default, no fallback.
- `:859`: `<label>Bundle name<input value={createName} onChange={event => setCreateName(event.target.value)} /></label>` -- no `placeholder`, no `defaultValue`.
- `:861`: create-button `disabled` expression includes `!createName.trim()`.

**Closed** -- the generated-name code path round 3 flagged no longer exists in the source at all, re-confirmed by direct read rather than trusting round 3's report.

### Frontend tests re-run at this HEAD

`source ~/.nvm/nvm.sh && nvm use 24.19.0 && rtk proxy npx vitest run src/selected/core/ProfileGoalsPages.test.tsx src/selected/core/InterviewHub.test.tsx` (raw, unfiltered vitest output via `rtk proxy` to get real per-file numbers):

```
 Test Files  2 passed (2)
      Tests  26 passed (26)
```

**26 passed, 0 failed**, at HEAD `825a01f`. Matches round 3's count exactly, consistent with `git log 7b805bd..825a01f -- src/selected/` returning no output (the test files themselves are unchanged since round 3).

### No-beginner and non-prediction rules — re-verified

`sqlite3 -readonly server/yuno.db ".schema goal_workspaces"` → `CONSTRAINT ck_goal_workspaces_target_level_valid CHECK (target_level IN ('Mid-level','Senior','Staff'))`, unchanged. `grep -rni "beginner|entry.level|entry-level" src/selected server/src/yuno` matches only the approved audience-note negation (`CorePages.tsx:52`). `grep -rni "predict|hiring|promotion" src/selected` matches only the approved title-variation-helper negation (`:53`), the Interview Prep hub's negation (`:951`), and the unrelated job-engine config string `background_age_promotion_seconds` (`operations/OperationalPages.tsx:311`, an operator-facing durable-worker status panel, not a role-level claim) plus its test fixture (`operations/JobsPage.test.tsx:29`). Same three non-blocking matches as round 3.

## Inspected artifacts

| Artifact | What it is | How inspected |
| --- | --- | --- |
| `git diff --stat 93103cd..825a01f` (full, and per-commit `git show --stat`) | Confirms the file surface of all four new commits | Executed |
| `git diff --stat 93103cd..825a01f -- src/selected/`, `-- server/src/yuno/api/routes/` | Confirms zero frontend files and zero route files touched by the four new commits | Executed, both empty |
| `server/scripts/register_source.py`, `server/scripts/load_rubric_manifest.py` | The two new offline CLIs | Read in full; confirmed argparse + `print(..., file=sys.stderr)` only, no ASGI/FastAPI import, not wired into any route via grep |
| `server/src/yuno/api/app.py` (`apply_snapshot_janitor`, `apply_staleness_recheck`) | The two new periodic-task closures | Read in full; confirmed `log_event` structured-log strings only, no new `@app.*`/`@router.*`/`APIRouter` route |
| `server/src/yuno/modules/hands_on/service.py:105-119`, `domain.py:12-25` | Confirms the hands-on module is untouched since round 3 (`git log 7b805bd..825a01f -- server/src/yuno/modules/hands_on/` empty) and still synthesizes fixture rows positionally | Read source |
| `server/src/yuno/modules/hands_on/models.py:31-40` | Confirms `ck_hands_on_work_hands_on_scenario_status_valid` and nullable `scenario_id` still present in source | Read source |
| `server/yuno.db`, `server/.e2e.db` (read-only) | Confirms both remain behind alembic head and both have 0 `hands_on_work` rows | `sqlite3 -readonly server/yuno.db "SELECT version_num FROM alembic_version"` / `"SELECT COUNT(*) FROM hands_on_work"`; same for `.e2e.db` |
| `uv run --directory server alembic heads` | Confirms alembic head unchanged (`be4d11f03666`) | Executed |
| `docs/decisions/IDK-004-role-level-competencies.md` §2 | Approved `role-competency-copy-v1` copy | Read source; byte-compared to `CorePages.tsx` by a fresh Python script |
| `docs/decisions/IDK-009-assessment-and-derived-state.md:323,350` | Confirms "twelve approved scenario records" framing | Read source |
| `src/selected/core/CorePages.tsx:48-68` | `ROLE_LEVEL_COPY` registry | Read source; byte-compared to IDK-004 §2 by script |
| `src/selected/core/CorePages.tsx:197-416` (`Onboarding`) | First-use goal setup: level state, submit gate, select/helper, submit-button disable expression | Read source |
| `src/selected/core/CorePages.tsx:798-876` (`BundleEditor`) | Interview Prep bundle role/level/name controls, empty-state creation gating | Read source |
| `src/selected/core/CorePages.tsx:917-967` (`InterviewHub`) | Interview Prep hub eyebrow derivation | Read source |
| `IMPLEMENTATION_TICKETS.md:1686` (IDK-405) | Confirms IDK-405's status and owning-ticket claim for the still-open B10 content half | Read source |
| `grep -rni "beginner\|entry.level\|predict\|hiring\|promotion" src/selected server/src/yuno` | Re-confirms the no-beginner and non-prediction rules still hold | Executed |
| `grep -rn "Not sure" docs/decisions/IDK-004-role-level-competencies.md src/selected server/src/yuno` | Checks whether IDK-004 §4's "Not sure" helper text ships anywhere | Executed — only the decision doc matches |
| `grep -n "backend interview" src/selected/core/*.tsx` | Confirms B22's generated-name template string does not exist anywhere in app source | Executed — only test-fixture data matches |

Tests executed:
- `source ~/.nvm/nvm.sh && nvm use 24.19.0 && rtk proxy npx vitest run src/selected/core/ProfileGoalsPages.test.tsx src/selected/core/InterviewHub.test.tsx` at HEAD `825a01f` → **26 passed, 0 failed** (2 test files, 26 tests).

## Blocking findings

### 1. Hands-on scenario content authorship remains unimplemented (B10, content half)
- What is missing: The twelve approved IDK-009 `idk009-v1-r1` scenario records are not loaded or bound to topics. Every synthesized `HandsOnWork` row is still hardcoded `scenario_status="fixture"`, `scenario_id=None`, `scenario_source="fixture-pending-idk-009"`.
- Owning ticket: IDK-405, status "Content incomplete" per `IMPLEMENTATION_TICKETS.md:1686` (re-read this round).
- Evidence of absence: `server/src/yuno/modules/hands_on/service.py:105-119`; `git log 7b805bd..825a01f -- server/src/yuno/modules/hands_on/` returns no output, confirming this module is untouched by any of the four new commits; zero matches for any IDK-009 scenario ID under `server/src/yuno/modules/hands_on/`; `server/yuno.db` and `server/.e2e.db` both hold 0 rows in `hands_on_work` (`sqlite3 -readonly ... "SELECT COUNT(*) FROM hands_on_work"`, this round).
- What would clear it: Load the IDK-009 registry content, bind topics to approved scenario IDs/role/level/constraints text, set `scenario_status="approved"` and a real `scenario_id` for approved content, and re-inspect against a live `hands_on_work` row.

## Notes and residual risk

- **Copy question (a) — the empty-label placeholder option.** Unchanged from round 3's judgment: not blocking on its own, since IDK-004 §4's operative requirement is behavioral (no preselection, explicit confirmation, fail-closed) and is independently satisfied regardless of placeholder text. Still a genuine open item for the approver: `CorePages.tsx:390` and `:860` render `<option value="" />` with no text at all, and no approved placeholder string exists in IDK-004 §2. Carried forward unresolved, per instruction; no copy is proposed here.
- **Copy question (b) — the "Not sure" helper text (IDK-004 §4).** Unchanged from round 3: no on-screen equivalent exists anywhere in `src/selected`. Whether this sentence was meant to ship as copy next to the level selector, or is meta-guidance constraining a future affordance, cannot be resolved from the decision text alone. Carried forward unresolved, per instruction; no copy is proposed here.
- The four commits landed since round 3 (`4493208`, `90e23c3`, `2b5ebc2`, `825a01f`) touch only `server/` (offline CLIs, service functions, and periodic-task wiring behind existing hourly background lanes) and introduce zero new HTTP routes and zero frontend files. None ships or could ship learner-facing copy — see "The four new commits" section above for the full re-derivation.
- Settings (`OperationalPages.tsx`'s goal-editor target-level/capability control) was verified in round 2 (B8) and was not touched by any commit since round 2 (confirmed: `git log 7b805bd..825a01f -- src/selected/operations/OperationalPages.tsx` returns no output for the level/capability control itself, though the file does contain the unrelated `background_age_promotion_seconds` string noted above). It was not re-read line-by-line this round since it fell outside this round's changed-file scope. Treat it as **not re-verified this round**, not as confirmed still-correct.
- `server/yuno.db` (alembic `4747447ccaa3`) and `server/.e2e.db` (alembic `a9d4e6f1b208`) both remain behind head (`be4d11f03666`) and both have 0 rows in `hands_on_work`, unchanged from round 3 — neither database is evidence for or against B10's schema-shape closure, which was re-confirmed by direct source read instead this round (see "Inspected artifacts" above).
- B13, B14, B15, B16, B21, and any IDK-504 measurement gaps are outside this gate's scope and were not re-inspected here. B21 (the `designated_editorial_approver` grant reuse for editorial-adjacent actions) is specifically implicated by this round's `register_source` and `load_rubric_manifest` functions reusing the identical grant for the identical reason round 3 already flagged for `withdraw_source` — both new functions' own docstrings name this consolidation explicitly (`provenance/service.py`'s `register_source` docstring; `evidence_evaluation/service.py`'s `load_rubric_manifest` docstring) — but re-inspecting B21 itself is out of this gate's scope.
- The e2e suite (`tests/e2e/*`) was not run this round; the task scoped tests to the two vitest files above, and no `tests/e2e/*` file changed in `git diff --stat 93103cd..825a01f` nor in `git diff --stat 825a01f 0f3219f`.
- The two commits landed after this gate's original inspection (`636bf26`, `0f3219f`, current HEAD) are covered by the "HEAD delta check" section above: five line-citation corrections in docstrings/comments/`docs/` and two Python test-literal additions, neither touching `src/selected/`, any route file, or the hands_on module. This gate's disposition and findings are unaffected by that delta.
