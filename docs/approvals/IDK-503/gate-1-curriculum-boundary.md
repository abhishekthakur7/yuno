# IDK-503 gate 1 — Curriculum boundary (CUR-01/CUR-02/CUR-03)

- Gate: Curriculum boundary (CUR-01/CUR-02/CUR-03)
- Reviewer role required: designated editorial approver
- Inspection date: 2026-08-14
- Decision under review: `docs/decisions/IDK-001-mvp-curriculum-spine.md` — Status: approved, Decision version `1.0`, Policy identifier `mvp-curriculum-spine-v1`, Approval date 2026-08-14 (per the document's own §19/§20 approval record).
- Implementing tickets: IDK-102 (offline canonical publisher, `server/scripts/publish_canonical.py`, `server/src/yuno/modules/canonical/`), IDK-201 (topic layer authoring, marked Complete in `IMPLEMENTATION_TICKETS.md:878-883`)
- Disposition: blocking-finding
- Attestation: pending — designated editorial approver has not signed this gate.

## Inspected artifacts

| Artifact | What it is | How inspected |
| --- | --- | --- |
| `server/yuno.db` | Local dev SQLite database | `sqlite3 server/yuno.db "SELECT count(*) FROM topics/canonical_graph_versions/editorial_approvals;"` |
| `server/.e2e.db` | E2E-run SQLite database | Same `SELECT count(*)` queries |
| `server/src/yuno/modules/canonical/validation.py` | Canonical manifest validator (CUR-01/CUR-02 rules) | Read source, lines 1-70, 295-360 |
| `server/tests/unit/test_canonical_validation.py` | Unit tests for validation rules | `rg`, then targeted `pytest` run |
| `server/tests/fixtures/canonical/data/invalid_go_node.json` | Synthetic fixture proving Go rejection | Read file contents |
| `docs/decisions/IDK-001-mvp-curriculum-spine.md` | The approved curriculum-boundary decision (§7-§12, §17) | Full read |
| `src/selected/core/CorePages.tsx` | Curriculum-facing UI copy (Roadmap, Topic Studio, Interview Hub, Practice) | `grep` for coverage/completeness claims |
| `IMPLEMENTATION_TICKETS.md:557-621` (IDK-102), `IMPLEMENTATION_TICKETS.md:878-883` (IDK-201) | Ticket status fields | Read |

Targeted test run (not full suite): `uv run --directory server pytest tests/unit/test_canonical_validation.py -k "go_node" -q` → `1 passed, 23 deselected`.

## Findings

| # | Decision requirement | Shipped reality (with citation) | Verdict |
| --- | --- | --- | --- |
| 1 | A production `canonical_graph_versions` row seeded from `mvp-curriculum-spine-v1` exists, carrying the 53 topics/74 relations of §7-§8, so its `scope_tags` can be compared row-by-row to the approved boundary. | `sqlite3 server/yuno.db "SELECT count(*) FROM topics"` → `0`; `... FROM canonical_graph_versions` → `0`; `... FROM editorial_approvals` → `0`. Same zero counts in `server/.e2e.db`. No `topics`/`topic_relations`/`topic_identities` rows exist in either inspectable database. | not shipped |
| 2 | CUR-02: validation actively rejects any Go node. | `_validate_no_go_nodes` (`server/src/yuno/modules/canonical/validation.py:315-328`) checks `topic.subject`/`scope_tags` against `_GO_TOKENS = {"go","golang","go_aws"}` (line 48) and appends `ViolationCode.GO_NODE_PRESENT`. Exercised by `server/tests/unit/test_canonical_validation.py:327,333,336,362` against fixture `server/tests/fixtures/canonical/data/invalid_go_node.json` (topic `subject: "go"`). Targeted run confirms: `pytest tests/unit/test_canonical_validation.py -k "go_node" -q` → 1 passed. | matches (validation logic proven at unit level) |
| 3 | CUR-02: the shipped MVP graph itself contains no Go node. | No shipped MVP graph exists to check (see finding 1) — the only Go-labeled data anywhere is the synthetic `invalid_go_node.json` fixture, explicitly documented as non-production (fixture's own `description` field: "a topic with subject='go' ... this overlap is the expected/correct behaviour, not a fixture bug"). | not shipped (nothing to verify absence against; not a pass) |
| 4 | CUR-03 / bounded claims: shipped curriculum-facing copy does not overstate coverage. | `grep -i "comprehensive\|full coverage\|entire curriculum\|complete curriculum\|all topics\|every topic"` over `src/` returns no matches. `src/selected/core/CorePages.tsx` renders `unavailable`/`empty` states for roadmap and topic-studio (e.g. line 409: `<h1>Your roadmap is unavailable</h1>`; line 936: `"Approved practice content is not available yet"`) rather than any coverage claim. | matches — no overstatement found in shipped copy, but copy currently shows only empty/unavailable states since no content is loaded (see finding 1) |
| 5 | The shipped graph version is the one IDK-001 approves (version id, publish provenance). | No `canonical_graph_versions` row exists (finding 1), so there is no version id or `editorial_approvals.basis_ref` to check provenance against. `docs/decisions/IDK-001-mvp-curriculum-spine.md:389,415` states this directly: "No such version exists — approving a spine is not publishing one" (§17) and "no `canonical_graph_versions` row exists, no content is authored... until IDK-201 authors content and IDK-102's publisher runs" (§20). | not shipped |

## Blocking findings

### 1. No production canonical graph has been published — CUR-01 boundary and CUR-02 graph-absence cannot be inspected against shipped content

- **What is missing:** A `canonical_graph_versions` row (with its `topics`/`topic_relations`/`topic_identities`/`content_revisions`/`editorial_approvals` per spec §4.3) seeded from `mvp-curriculum-spine-v1`. This is the artifact IDK-503's own scope line requires: "Review the curriculum boundary decided in IDK-001 against the shipped canonical graph's scope tags (CUR-01)."
- **Owning ticket:** IDK-102 (offline canonical publisher) — specifically its "production seed run" obligation, which `IMPLEMENTATION_TICKETS.md:621-622` and the decision doc's own §14/§17 both describe as still open ("IDK-102 retains the publish-time obligation to run `validate_manifest`..." and "No such version exists — approving a spine is not publishing one").
- **Evidence of absence:** `sqlite3 server/yuno.db "SELECT count(*) FROM topics"` = 0, `... FROM canonical_graph_versions"` = 0, `... FROM editorial_approvals"` = 0; identical zero counts in `server/.e2e.db`. The only topic/relation data anywhere in the repo lives in `server/tests/fixtures/canonical/data/*.json`, which the decision document itself (§3) labels "synthetic, non-production, independent of this document."
- **What would clear it:** IDK-102's production publish run completing against a real manifest built from IDK-001 §7-§9 plus IDK-201-authored `content_revisions`, producing a `canonical_graph_versions` row with a matching `editorial_approvals` row and `basis_ref`, per decision §14's six conditions. This gate must then be re-run against that shipped version, row-by-row against §7's 53 topics and §12's exclusions.

## Notes and residual risk

- The validation *mechanism* (CUR-01 boundary check, CUR-02 Go rejection, CUR-02 DSA-scenario requirement) is real, shipped, and unit-tested — this is a positive finding but is not a substitute for inspecting shipped curriculum content, since IDK-503's scope explicitly requires reviewing the decision "against the shipped canonical graph's scope tags," not against the validator alone.
- The decision document (`docs/decisions/IDK-001-mvp-curriculum-spine.md`) transparently states this gap itself (§14 "Known gaps," §17 "Stop point," §20 "Approval statement") — this is not a surprise discovered by this review, but it is nonetheless a blocking condition for gate 1 as scoped by IDK-503.
- No overstated-coverage copy was found in shipped UI source, but this is a weak signal: with no graph published, curriculum-facing surfaces currently render only `empty`/`unavailable` states, not actual topic listings, so CUR-03's bounded-claims check has not yet been exercised against real rendered content either.
- This finding blocks gate 1 sign-off; it does not by itself block unrelated MVP surfaces that don't depend on a published graph.
