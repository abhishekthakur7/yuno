# IDK-503 gate 2 — Editorial approval evidence and criteria

- Gate: Editorial approval evidence and criteria (CORE-02/INT-02, Appendix H D1)
- Reviewer role required: designated editorial approver
- Inspection date: 2026-08-14
- Decision under review: docs/decisions/IDK-002-editorial-approval-criteria.md — Status: approved, Decision version `1.0`, Policy identifier `editorial-approval-criteria-v1`, Approval date 2026-08-14 (per document body and §11 approval record)
- Implementing tickets: IDK-102 (offline publisher / D1 mechanics), IDK-201 (layer set, referenced by §3.5)
- Disposition: blocking-finding
- Attestation: pending — designated editorial approver has not signed this gate.

## Inspected artifacts

| Artifact | What it is | How inspected |
| --- | --- | --- |
| `server/yuno.db` | Local dev SQLite DB | `sqlite3 server/yuno.db "SELECT * FROM editorial_approvals;"` — 0 rows returned |
| `server/.e2e.db` | E2E-run SQLite DB | `sqlite3 server/.e2e.db "SELECT * FROM editorial_approvals;"` — 0 rows returned |
| `server/yuno.db` schema | DDL for `editorial_approvals` | `sqlite3 server/yuno.db ".schema editorial_approvals"` |
| `server/src/yuno/modules/canonical/models.py:418-442` | `EditorialApprovalRow` ORM model | Read; grepped for `CheckConstraint`/`basis_ref` |
| `server/src/yuno/modules/canonical/domain.py:169-178` | `EditorialApproval` frozen dataclass | Read; no `__post_init__` present |
| `server/src/yuno/modules/canonical/publisher.py:84-219` | `publish_canonical_graph` | Read; traced `basis_ref` from parameter to `record_approval` call (line 195) and to `reason=basis_ref` (line 219) |
| `server/scripts/publish_canonical.py:118-150` | `load_manifest` | Read; confirmed `basis_ref` returned as opaque `approval["basis_ref"]` string, line 150 |
| `server/src/yuno/modules/identity/domain.py:42-53` | `RolePolicy.require` | Read; raises `RoleNotGrantedError` when role missing from grants |
| `server/src/yuno/modules/canonical/publisher.py:135` | Role-grant enforcement call site | `RolePolicy.require(grants, Role.DESIGNATED_EDITORIAL_APPROVER)` before any write |
| `server/tests/integration/test_canonical_publish.py:217-231` | `test_learner_only_grant_rejected_before_any_write` | Read test body; asserts `RoleNotGrantedError` raised for a learner-only owner |
| `server/src/yuno/modules/canonical/repository.py:167-233` | `get_published_version`/`list_published_versions`/`get_published_topics`/`get_published_relations` | Read; all four `select` statements `.join(EditorialApprovalRow, ...)` |
| `server/tests/integration/test_canonical_repository.py:123-278` | Half-seed/unapproved-visibility tests | Read test names and assertions |
| `server/tests/integration/test_canonical_acceptance.py:180` | `test_half_seeded_version_unreadable_through_every_read_path` | Read test name/body |
| `server/tests/integration/test_canonical_api.py:178,209` | `test_half_seeded_version_404s_on_list_and_detail`, `test_half_seeded_and_nonexistent_versions_produce_the_same_error_shape` | Read test names/bodies |
| `server/tests/fixtures/canonical/data/v1_approved.json:92`, `v2_approved.json:92` | Fixture `basis_ref` values | Read; literal strings `"fixture-approval-basis-v1"` / `"fixture-approval-basis-v2"` |
| `IMPLEMENTATION_TICKETS.md:557-561` | IDK-102 ticket status | Read; `Status: Complete` |

## Findings

| # | Decision requirement | Shipped reality (with citation) | Verdict |
| --- | --- | --- | --- |
| 1 | §4 requires `basis_ref` to be one canonical JSON object with 15 named fields (`basis_ref_version`, `policy_identifier`, `reviewed_manifest_hash`, checklist sub-objects, etc.) attached to production graph versions | `editorial_approvals` table is empty in both `server/yuno.db` and `server/.e2e.db` (0 rows, direct `SELECT *` query) — no production row exists to evaluate against §4's schema | not shipped |
| 2 | §8 item 1: `CheckConstraint("json_valid(basis_ref)", name="basis_ref_valid")` on `EditorialApprovalRow`, mirroring `payload_json_valid` | `sqlite3 server/yuno.db ".schema editorial_approvals"` shows no such constraint; only `pk`, `approver_role` CHECK, two FKs, one UNIQUE. `models.py:442` column is plain `Mapped[str] = mapped_column(Text, nullable=False)` with no `CheckConstraint` on `basis_ref` (confirmed by full-file grep for `CheckConstraint`, only hits at lines 193/262 for unrelated `payload_json` columns) | not shipped |
| 3 | §8 item 2: framework-free schema validation of the parsed `basis_ref` object invoked before `record_approval` | `domain.py:169-178` `EditorialApproval` dataclass has no `__post_init__`; `publisher.py:84-219` forwards `basis_ref: str` straight into `EditorialApproval(...)` (line 192) and `uow.canonical.record_approval(approval)` (line 195) with no validation call in between | not shipped |
| 4 | §8 item 3: `scripts/publish_canonical.py`'s `load_manifest` must construct/validate the §4 object from the manifest's `approval` block, rejecting a mismatched shape | `publish_canonical.py:150` `return manifest, topic_identity_slugs, approval["approver_role"], approval["basis_ref"]` — returns the raw string unexamined, exactly as the decision doc's §8 describes as "absent today" | not shipped |
| 5 | §6: no placeholder `basis_ref` (e.g. `"fixture-approval-basis-v1"`) on a version presented to a learner | No production `editorial_approvals` row exists (finding 1), so no placeholder has reached a learner-facing version; but placeholder strings are the only `basis_ref` content that exists anywhere in the repo (`server/tests/fixtures/canonical/data/v1_approved.json:92` = `"fixture-approval-basis-v1"`, `v2_approved.json:92` = `"fixture-approval-basis-v2"`) — consistent with fixture-only use, no violation observed | matches (nothing to violate yet) |
| 6 | Who approves: `designated_editorial_approver` grant distinct from `learner`, enforced before any write | `identity/domain.py:42-53` `RolePolicy.require` raises `RoleNotGrantedError`; `publisher.py:135` calls it before any DB write; test `test_canonical_publish.py:217-231` (`test_learner_only_grant_rejected_before_any_write`) asserts a learner-only owner publishing `v1_approved` fixture raises `RoleNotGrantedError` | matches |
| 7 | Approval-gated reads: every read path gated on `editorial_approvals` existing, not a status filter | `repository.py:167-233`: `get_published_version` (168-177), `list_published_versions` (179-192), `get_published_topics` (194-204), `get_published_relations` (206-217) each `.join(EditorialApprovalRow, ...)`. Covered by `test_canonical_repository.py:123,151,168,194` (half-seeded-version exclusion per method), `test_canonical_acceptance.py:180` (`test_half_seeded_version_unreadable_through_every_read_path`), `test_canonical_api.py:178,209` (404 behavior at the API boundary) | matches |
| 8 | §9 known-gaps list itself (self-reported by the decision doc) | Independently reproduced every gap the decision doc claims in §9: no `json_valid` constraint (finding 2), no `reviewed_manifest_hash` cross-check (no such code found anywhere in `publisher.py`/`domain.py`), no fixture/production schema flag (no column found on `canonical_graph_versions`/`editorial_approvals` beyond what's in the `.schema` dump above) | matches (gaps confirmed, not closed) |

## Blocking findings

### 1. `basis_ref` mechanical/schema validation required by §4/§8 is entirely unimplemented

- What is missing: (a) `CheckConstraint("json_valid(basis_ref)")` on `editorial_approvals`; (b) parsed-object validation against §4's 15-field contract; (c) `reviewed_manifest_hash` cross-check against the row's own `manifest_hash`; (d) `review_kind`/`diff_against_version_label` consistency check against `list_published_versions()`. None of these exist.
- Owning ticket: IDK-102 (per decision doc §8, these items belong to the offline publisher this ticket built) — no separate ticket implements §8's items 1-4; IDK-102 is marked `Status: Complete` in IMPLEMENTATION_TICKETS.md:560 without them.
- Evidence of absence: `server/src/yuno/modules/canonical/models.py:442` (plain `Text` column, no `CheckConstraint`); `server/src/yuno/modules/canonical/domain.py:169-178` (no `__post_init__`); `server/src/yuno/modules/canonical/publisher.py:84-219` (basis_ref forwarded unexamined); `server/scripts/publish_canonical.py:150` (same).
- What would clear it: implement §8 items 1-4 in a migration + `models.py` + `domain.py`/`publisher.py`/`publish_canonical.py`, with a test asserting a `basis_ref` failing `json_valid`, a required-field check, or the `reviewed_manifest_hash` cross-check is rejected before any write (decision §8 acceptance item 1). Then re-run this gate against an actual publish attempt.

### 2. No production `editorial_approvals` row exists to inspect against §4's criteria

- What is missing: any row in `editorial_approvals` on the databases available for inspection. The gate's task is to compare shipped `basis_ref` values against the approved criteria; there is nothing shipped to compare.
- Owning ticket: IDK-102 (production seed run) — decision doc §8 itself states "no production canonical graph version has ever been published" and IDK-503 (this ticket) is named as the check that must run once one is.
- Evidence of absence: `sqlite3 server/yuno.db "SELECT * FROM editorial_approvals;"` and the same query against `server/.e2e.db` both return zero rows.
- What would clear it: run IDK-102's production seed against a real manifest under this policy, producing a `basis_ref` conforming to §4, then re-inspect the row's actual field content (not merely that a row exists) against §4/§5's exhaustiveness and sampling rules.

## Notes and residual risk

- D1's attribution/role-grant mechanism (finding 6) and approval-gated reads (finding 7) are both shipped and tested; these portions of the decision are not blocked.
- The decision document's own §9 "Known enforcement gaps" section independently states the same two blocking findings recorded here — this inspection corroborates rather than discovers them, confirming the gaps were not silently closed since the decision was recorded.
- Because no production version has ever published, `server/yuno.pre-idk010-partial.db` (a third local db file observed in `server/`) was not queried — it predates IDK-010 work and is unrelated to this gate's scope; not inspected.
- This gate cannot reach "inspection-passed" status until (a) §8's validation code ships and (b) at least one production `basis_ref` row exists and conforms to §4. Both are currently absent.
