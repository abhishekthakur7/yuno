# IDK-503 rerun (2026-08-15) — gate 1: Curriculum boundary (CUR-01/CUR-02/CUR-03)

- Gate: Curriculum boundary (CUR-01/CUR-02/CUR-03)
- Reviewer role required: designated editorial approver
- Inspection date: 2026-08-15
- Decision under review: `docs/decisions/IDK-001-mvp-curriculum-spine.md` — Status: approved, Decision version `1.0`, Policy identifier `mvp-curriculum-spine-v1`, Approval date 2026-08-14 (per the document's own §19/§20).
- Tree inspected: `HEAD` = `2621d298f8f268d42ec6be94d454fa61d986f054` (`git rev-parse HEAD`, committed 2026-08-15T06:14:49+05:30). Originally inspected at `92f2a85`; re-inspected at `2621d29` per a follow-up request — see "Delta check: `92f2a85` → `2621d29`" below the field block. No uncommitted changes remain (`git status --porcelain` clean of tracked files; `2621d29` is exactly the commit of the working-tree diff this document previously described as uncommitted).
- Implementing tickets: IDK-102 (offline canonical publisher, `server/scripts/publish_canonical.py`, `server/src/yuno/modules/canonical/`) — Status: Complete (`IMPLEMENTATION_TICKETS.md:560`); IDK-201 (topic layer authoring) — Status: Complete (`IMPLEMENTATION_TICKETS.md:881`). Both "Complete" statuses are mechanism-complete (the publisher tool and the read/serve pathway exist and are tested against fixtures); neither claims production content has been authored or published — see Findings below.
- Disposition: blocking-finding
- Attestation: pending — designated editorial approver has not signed this gate. No approval is recorded by this document.

## Delta check: `92f2a85` → `2621d29` (re-inspection, same day)

This gate was first inspected at `HEAD` = `92f2a85`. One further commit landed afterward: `2621d29` — "fix: resolve the local owner without opening a UnitOfWork (IDK-503 B14)". Checked via `git show --stat 2621d29` and a full `git show 2621d29` read before restamping the HEAD above:

- Files touched: `server/src/yuno/api/app.py` (+4), `server/src/yuno/api/dependencies.py` (+12/-8), `server/tests/integration/test_api_contract.py` (+16/-8), `server/tests/integration/test_runner.py` (+113, two new tests) — the same four files, same 144/-17 shape, this document already listed as an uncommitted working-tree diff during the first pass. `2621d29` is that diff, now committed; it is not new code beyond what was already reviewed then.
- Substance: `get_owner_id` now reads a singleton `app.state.owner_id` cached at lifespan startup instead of opening an `IdentityUnitOfWork`/running a `SELECT` per request (IDK-008-driven: the retired `"language":"relational"` runner-confirmation body must 422 before any UoW/SQL/pool-checkout). Two new regression tests (`test_retired_relational_language_rejected_before_route_or_uow`, `test_job_retry_extra_field_422_opens_no_uow`) pin zero-UoW behavior on the runner and job-retry routes.
- Bearing on gate 1: **none.** `2621d29` touches no file under `server/src/yuno/modules/canonical/**`, no migration, `docs/decisions/IDK-001-mvp-curriculum-spine.md`, or any curriculum-facing route/copy in `src/`. It is entirely about how the acting owner id is resolved for *all* authenticated routes (a cross-cutting perf/correctness fix), not about topics, canonical graph versions, editorial approvals, or DSA-scenario relations.
- Database re-check at this HEAD: `sqlite3 server/yuno.db "SELECT count(*) FROM topics/canonical_graph_versions/editorial_approvals/content_revisions"` all still `0`; `alembic_version` still `4747447ccaa3` (unchanged — `2621d29` carries no migration). Re-ran `pytest tests/unit/test_canonical_validation.py -q` at this HEAD → still 24 passed (untouched by this commit, re-run for completeness rather than assumed).
- **Conclusion: no finding below changes.** Every citation, verdict, and the Blocking finding are unchanged from the `92f2a85` pass and are re-stated below at the new HEAD rather than silently restamped.

## What changed since the previous round (2026-08-14) — verified against this tree

Commits `6bebd2f`, `c3409df`, `f4a204f`, `bf664e2`, `a9ee2a4`, `92f2a85` landed since the prior gate-1 inspection (`git log --oneline`, `git show --stat <sha>` run against each). None of the six touches `server/src/yuno/modules/canonical/**`, a curriculum migration, `docs/decisions/IDK-001-mvp-curriculum-spine.md`, or a curriculum-facing route in `src/`:

- `6bebd2f` — runner platform gate (B16), assessment vocabulary `not-demonstrated`/critical-dimension (B13, IDK-009 §9.2), and IDK-004 §2 learner-facing copy (B8/B9). None is a CUR-01/02/03 artifact.
- `c3409df` — `basis_ref` validation for `editorial_approvals` (IDK-503 B2). This is gate 2 (editorial approvals) territory, not gate 1: it constrains the shape of an approval record once one is written, but zero `editorial_approvals` rows exist in either database (see below), so it has not changed what gate 1 can inspect.
- `f4a204f` — `boolean_column` CHECK-constraint surfacing fix in `server/src/yuno/shared/infrastructure/base.py`. Infrastructure-only; no migration; does not touch canonical tables.
- `bf664e2` — `sources` availability write path (IDK-503 B7, gate 3 territory).
- `a9ee2a4` — citation attribution rendering (IDK-503 B5, gate 3 territory).
- `92f2a85` — widens `hands_on_work.scenario_status` and adds `hands_on_work.scenario_id` (IDK-503 B10/B12). This is the practice-run/hands-on table, not `topics`/`topic_relations`/`canonical_graph_versions`; it does not create, seed, or approve a canonical graph version, and does not touch the DSA→scenario `topic_relations` CUR-02 checks in `validation.py`.

Net effect on gate 1: **no commit in this window authored or published curriculum content, ran the offline publisher against a real manifest, or wrote an `editorial_approvals` row.** The blocking condition the previous round recorded is unchanged in kind. This is re-verified below against today's tree rather than carried forward.

## Database state — verified myself, both files

`YUNO_DATABASE_URL` (not `DATABASE_URL`) is the app's env var; read-only `sqlite3` queries only, nothing written.

| File | `alembic_version` (`SELECT * FROM alembic_version`) | Position vs. migration chain |
| --- | --- | --- |
| `server/yuno.db` | `4747447ccaa3` | **Not at head.** Chain (walked via each migration's `revision`/`down_revision`, `server/src/yuno/migrations/versions/*.py`): `... a9d4e6f1b208 -> e10d1a0c0100 -> f06c40340400 -> c5b1e70a94d2 -> fb1c910aedc7 -> 4747447ccaa3 -> 4cb74877e4ba -> be4d11f03666 (head)`. `yuno.db` sits at `4747447ccaa3`, which is the revision `c3409df`'s migration lands on — it is missing `4cb74877e4ba` (`bf664e2`'s sources-license migration) and `be4d11f03666` (`92f2a85`'s hands_on-scenario migration), both **already committed to `main`**. Confirmed structurally: `sqlite3 yuno.db ".schema sources"` shows no `withdrawal_reason`/`superseded_by_source_id` column, and `.schema hands_on_work` shows `scenario_status TEXT NOT NULL, CONSTRAINT ... CHECK (scenario_status IN ('fixture'))` — the pre-widening constraint. `alembic heads` against this database's URL reports `be4d11f03666 (head)`, i.e., the code's migration head is two revisions ahead of what's actually applied to this file. |
| `server/.e2e.db` | `a9d4e6f1b208` | Predates `e10d1a0c0100` (the revision immediately after it in the chain above) — confirmed untouched, consistent with the task framing. |

This contradicts the framing that `yuno.db` was "migrated ... to the current head" — it was migrated partway (through `c3409df`'s migration) and not further. Recorded here as a fact I verified myself, not assumed; it does not change the gate-1 disposition below since none of the missing migrations touch a canonical/topic table.

Content-table row counts, both databases, both `0`:

```
sqlite3 server/yuno.db  "SELECT count(*) FROM topics"                    -> 0
sqlite3 server/yuno.db  "SELECT count(*) FROM topic_identities"          -> 0
sqlite3 server/yuno.db  "SELECT count(*) FROM topic_relations"           -> 0
sqlite3 server/yuno.db  "SELECT count(*) FROM canonical_graph_versions"  -> 0
sqlite3 server/yuno.db  "SELECT count(*) FROM editorial_approvals"       -> 0
sqlite3 server/yuno.db  "SELECT count(*) FROM content_revisions"         -> 0
sqlite3 server/.e2e.db  "SELECT count(*) FROM topics"                    -> 0
sqlite3 server/.e2e.db  "SELECT count(*) FROM topic_identities"          -> 0
sqlite3 server/.e2e.db  "SELECT count(*) FROM topic_relations"           -> 0
sqlite3 server/.e2e.db  "SELECT count(*) FROM canonical_graph_versions"  -> 0
sqlite3 server/.e2e.db  "SELECT count(*) FROM editorial_approvals"       -> 0
sqlite3 server/.e2e.db  "SELECT count(*) FROM content_revisions"         -> 0
```

## Inspected artifacts

| Artifact | What it is | How inspected |
| --- | --- | --- |
| `server/yuno.db`, `server/.e2e.db` | Local dev / e2e SQLite databases | Read-only `sqlite3 ... "SELECT count(*) FROM ..."` against `topics`, `topic_identities`, `topic_relations`, `canonical_graph_versions`, `editorial_approvals`, `content_revisions`; `SELECT * FROM alembic_version`; `.schema sources`, `.schema hands_on_work` |
| `server/src/yuno/migrations/versions/*.py` (32 files) | Alembic migration chain | Read each file's `revision`/`down_revision` to reconstruct chain order and locate both databases' position in it |
| `server/src/yuno/modules/canonical/validation.py` | Canonical manifest validator (CUR-01/CUR-02 rules) | Read in full; specifically `ALLOWED_SUBJECTS` (lines 39-48), `_validate_no_go_nodes` (338-350), `_validate_curriculum_boundary` (322-335), `_validate_dsa_scenario_relations` (353-374), `compute_manifest_hash` (113), `validate_manifest` (161) |
| `server/tests/unit/test_canonical_validation.py` | Unit tests for validation rules | `rg` for `GO_NODE_PRESENT`/`invalid_go_node`; ran `uv run pytest tests/unit/test_canonical_validation.py -k "go_node" -q` (1 passed) and the full file `uv run pytest tests/unit/test_canonical_validation.py -q` (24 passed) |
| `server/tests/fixtures/canonical/data/invalid_go_node.json` | Synthetic fixture proving Go rejection | Read file contents in full |
| `docs/decisions/IDK-001-mvp-curriculum-spine.md` | The approved curriculum-boundary decision | Full read, all 20 sections, this round |
| `src/selected/core/CorePages.tsx` | Curriculum-facing UI copy (Roadmap, Topic Studio, Practice) | `grep -rniE "comprehensive\|full coverage\|entire curriculum\|complete curriculum\|all topics\|every topic"` over `src/` (no matches); read the specific `unavailable`/`empty` render branches (lines 436, 448, 637, 981) |
| `IMPLEMENTATION_TICKETS.md:557-609` (IDK-102), `IMPLEMENTATION_TICKETS.md:878-917` (IDK-201) | Ticket status/scope fields | Read in full |
| `git log --oneline`, `git show --stat <sha>` for `6bebd2f`, `c3409df`, `f4a204f`, `bf664e2`, `a9ee2a4`, `92f2a85`, `2621d29` | Commit history across both inspection passes | Read commit messages and changed-file lists; `2621d29` additionally read via full `git show 2621d29` |
| `git status`, `git diff --stat` | Working-tree state at the first pass (`92f2a85`) | Read in full — the diff then present was `server/src/yuno/api/{app,dependencies}.py` plus two integration test files; confirmed identical to, and fully absorbed by, `2621d29` once committed (same 144/-17 shape) |

## Findings

| # | Decision requirement | Shipped reality (with citation) | Verdict |
| --- | --- | --- | --- |
| 1 | A production `canonical_graph_versions` row seeded from `mvp-curriculum-spine-v1` exists, carrying the 53 topics/74 relations of §7-§8, so `scope_tags` can be compared row-by-row against the approved boundary. | `sqlite3 server/yuno.db "SELECT count(*) FROM canonical_graph_versions"` = `0`; `... FROM topics"` = `0`; `... FROM topic_relations"` = `0`; `... FROM editorial_approvals"` = `0`. Identical zero counts in `server/.e2e.db`. Verified today, not carried forward. | not shipped |
| 2 | CUR-02: validation actively rejects any Go node. | `_validate_no_go_nodes` (`server/src/yuno/modules/canonical/validation.py:338-350`) checks `topic.subject`/`scope_tags` against `_GO_TOKENS = {"go","golang","go_aws"}` (line 50), appends `ViolationCode.GO_NODE_PRESENT`. Exercised by `server/tests/unit/test_canonical_validation.py:322,327,330,333,336,339,362` against fixture `server/tests/fixtures/canonical/data/invalid_go_node.json` (topic `subject: "go"`). Re-run today: `pytest tests/unit/test_canonical_validation.py -k "go_node" -q` → 1 passed; full file → 24 passed. | matches (validation logic proven at unit level, re-confirmed this round) |
| 3 | CUR-02: the shipped MVP graph itself contains no Go node. | No shipped MVP graph exists to check (finding 1). The only Go-labeled data anywhere is the synthetic `invalid_go_node.json` fixture, whose own `description` field states the overlap with `OUT_OF_BOUNDARY_CURRICULUM_TAG` is "expected/correct behaviour, not a fixture bug" — i.e., explicitly non-production. | not shipped (nothing to verify absence against; not a pass) |
| 4 | CUR-01: `ALLOWED_SUBJECTS` matches the decision's six subjects exactly. | `server/src/yuno/modules/canonical/validation.py:39-48`: `{"java", "spring_boot", "aws", "system_design", "rdb", "dsa"}` — identical to `docs/decisions/IDK-001-mvp-curriculum-spine.md:17`'s six subjects. `_validate_curriculum_boundary` (lines 322-335) rejects any topic whose `subject` is outside this set. | matches |
| 5 | CUR-03 / bounded claims: shipped curriculum-facing copy does not overstate coverage. | `grep -rniE "comprehensive\|full coverage\|entire curriculum\|complete curriculum\|all topics\|every topic"` over `src/` today returns no matches (exit code 1). `src/selected/core/CorePages.tsx:436,448` render `"Your roadmap is unavailable"` / `"No roadmap topics are available"`; `:981` renders `"Approved practice content is not available yet"`. Same three states as the prior round, re-read and re-confirmed this round rather than assumed unchanged. | matches — no overstatement found, but this is a weak signal since only empty/unavailable states exist to check (finding 1) |
| 6 | The shipped graph version is the one IDK-001 approves (version id, publish provenance, `basis_ref`). | No `canonical_graph_versions` row exists (finding 1), so there is no version id or `editorial_approvals.basis_ref` to check provenance against, and no basis to exercise `c3409df`'s new `validate_basis_ref` against a real approval row for this gate's purposes. `docs/decisions/IDK-001-mvp-curriculum-spine.md:389,415` (§17, §20) states this directly. | not shipped |
| 7 | IDK-102 (publisher) / IDK-201 (topic layers) ticket status accurately reflects what's shipped. | `IMPLEMENTATION_TICKETS.md:560`: IDK-102 `Status: Complete` — scoped to the *mechanism* (validator, atomic insert-then-approve, immutability triggers, module-boundary contract); its own text (`:606-609`, "Approval gate") states production seeding "additionally requires IDK-001 ... and IDK-002" and carries no estimate. `IMPLEMENTATION_TICKETS.md:881`: IDK-201 `Status: Complete` — scoped to the *read/serve pathway and checkpoint contract*, consuming `content_revisions` (currently 0 rows) rather than authoring it (`:894`, "Out of scope"). Neither "Complete" is a claim that production curriculum content exists; both are consistent with finding 1. | matches (tickets do not overstate; the gap is real, not a ticket-status error) |

## Blocking findings

### 1. No production canonical graph has been published — CUR-01 boundary and CUR-02 graph-absence cannot be inspected against shipped content

- **What is missing:** A `canonical_graph_versions` row (with its `topics`/`topic_relations`/`topic_identities`/`content_revisions`/`editorial_approvals`, per IMPLEMENTATION_SPEC §4.3) seeded from `mvp-curriculum-spine-v1`. This is the artifact gate 1's scope requires: the shipped canonical graph's `scope_tags`, checked row-by-row against IDK-001 §7's 53 topics and §12's exclusions.
- **Owning ticket:** IDK-102's production seed run, distinct from its (Complete) mechanism build. `IMPLEMENTATION_TICKETS.md:606-609` names IDK-001 and IDK-002 as additional prerequisites for that run; the decision document's own §14 lists six unmet conditions (content authored by IDK-201, sources registered per IDK-003 §12, a real manifest passing `validate_manifest` with a computed `manifest_hash`, IDK-002's checklist completed against that manifest and recorded in a valid `basis_ref`, the D1 publisher run, and a resulting `editorial_approvals` row).
- **Evidence of absence, verified today:** `sqlite3 server/yuno.db "SELECT count(*) FROM topics"` = `0`; `... FROM canonical_graph_versions"` = `0`; `... FROM editorial_approvals"` = `0`; `... FROM content_revisions"` = `0`. Identical zero counts in `server/.e2e.db`. The only topic/relation data anywhere in the repo lives in `server/tests/fixtures/canonical/data/*.json`, explicitly labelled synthetic/non-production by the fixtures themselves and by the decision document's §3 ("Does not gate: IDK-102's own fixture-based mechanism tests ... synthetic, non-production, independent of this document"). None of the six commits landed since the prior round (`6bebd2f`, `c3409df`, `f4a204f`, `bf664e2`, `a9ee2a4`, `92f2a85`) writes to `canonical_graph_versions`, `topics`, `topic_relations`, or `editorial_approvals`, or runs `server/scripts/publish_canonical.py` against a real manifest — confirmed by `git show --stat` on each.
- **What would clear it:** IDK-201-authored `content_revisions` for the 53 topics, IDK-003 §12's source registration, a manifest built from IDK-001 §7-§9 passing `validate_manifest` with zero violations, IDK-002's checklist completed by the designated editorial approver against that exact manifest and recorded in a valid `basis_ref`, and IDK-102's D1 publisher run producing a matching `canonical_graph_versions` + `editorial_approvals` pair. Gate 1 must then be re-run against that shipped version, row-by-row against §7's 53 topics and §12's exclusions — the validator mechanism alone (finding 2/4 above) is not a substitute.
- **Nature of this finding:** partly content (IDK-201's authoring — an editorial/content-owner obligation, not closable by engineering alone) and partly implementation (the publish run itself, which is engineering work gated on that content existing). Neither half can be closed by this review.

## Notes and residual risk

- The validation *mechanism* (CUR-01 boundary check, CUR-02 Go rejection, CUR-02 DSA-scenario requirement, manifest hashing) is real, shipped, and unit-tested (24/24 passing today) — a positive finding, but explicitly not a substitute for inspecting shipped curriculum content, since gate 1 requires reviewing the decision against the shipped canonical graph's `scope_tags`, not against the validator alone. This is unchanged from the prior round and re-verified rather than assumed.
- `server/yuno.db`'s `alembic_version` (`4747447ccaa3`) is two migrations behind the code's actual head (`be4d11f03666`, per `alembic heads`) — verified structurally via `.schema sources` and `.schema hands_on_work` lacking the columns/constraints those two migrations add. This does not affect gate 1's disposition (no canonical/topic migration is among the missing ones), but it means claims that this database is "current" should not be taken at face value elsewhere in this rerun without the same structural check.
- No overstated-coverage copy was found in shipped UI source (finding 5), but this remains a weak signal: with no graph published, curriculum-facing surfaces render only `empty`/`unavailable` states, not actual topic listings, so CUR-03's bounded-claims check has still not been exercised against real rendered content.
- The decision document transparently states this gap itself (§14 "Known gaps," §17 "Stop point," §20 "Approval statement") — not a new discovery, but still a blocking condition for gate 1 as scoped.
- This finding blocks gate 1 sign-off only; it does not by itself block unrelated MVP surfaces that don't depend on a published graph.
- `2621d29` (`server/src/yuno/api/app.py`, `server/src/yuno/api/dependencies.py`, and two integration test files — first seen mid-review as an uncommitted diff, now committed) caches `owner_id` on `app.state` rather than resolving it per-request through a `UnitOfWork`. Reviewed twice (as a diff, then as a commit) and confirmed both times unrelated to curriculum boundary — no canonical-module, migration, or curriculum-copy file is touched. See "Delta check" above.
