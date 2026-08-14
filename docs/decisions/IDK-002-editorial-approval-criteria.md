# IDK-002 — Editorial approval evidence and review criteria

Status: approved

Decision version: `1.0`

Policy identifier: `editorial-approval-criteria-v1`

Approval date: 2026-08-14

Approver role: designated editorial approver — MVP local owner acting explicitly in that role, per PRD §13

This decision settles what an `EditorialApproval` record must demonstrate before the canonical graph version it attaches to is trustworthy for production learner use: the checklist an approver completes, the structured content `editorial_approvals.basis_ref` must carry, the minimum sample sizes that make a review sufficient rather than performative, and what this policy forbids regardless of who performs the review. It does not decide who the approver is (PRD §13 and Appendix H D1 fix that as the MVP local owner acting under the `designated_editorial_approver` grant), does not approve any curriculum content (IDK-001) or source/license (IDK-003), and is not itself evidence that any production graph version has been reviewed — that evidence is produced when IDK-102 seeds a production version under this policy and checked by IDK-503. Recording an approval asserts that a named reviewer inspected specific, hash-identified evidence against the criteria below and found it satisfactory. It is not a claim that the content is factually complete, permanently current, defect-free, or a guarantee of learner outcome, hiring readiness, or interview performance — PRD §7/§8 and IDK-009 §2 already foreclose those claims and this decision does not reopen them.

## 1. Decision and boundary

An editorial approval means the designated editorial approver personally inspected the exact hash-identified manifest and content bodies about to be published, applied every checklist item in section 3, recorded the outcome in a validated `basis_ref` payload (section 4), and is willing to be named as accountable reviewer for that version. Nothing more is asserted.

It does not mean the content is correct in any absolute sense, that it will remain current, that every claim was independently fact-checked beyond section 5's sampling rule, or that a learner who completes reviewed material is prepared for a real interview or job. Approval is binary at the version level (CUR-03) but the review underneath is itemized: a version either has a complete, passing checklist recorded in `basis_ref`, or it has no valid approval and D1's mechanism keeps it permanently unreadable. There is no partial-approval state; section 6 forbids constructing one.

## 2. What is already resolved and not reopened

Appendix H D1, PRD §13, and PRD's dependency table already fix, and this decision does not reopen:

- **Who approves.** The MVP local owner acting under a `designated_editorial_approver` grant, distinct from `learner` (SAAS-01). Implemented: `owner_role_grants` (spec §4.2) carries `role CHECK(learner,designated_editorial_approver)`; `RolePolicy.require` (`server/src/yuno/modules/identity/domain.py`) raises `RoleNotGrantedError` when the grant is missing; `publish_canonical_graph` (`server/src/yuno/modules/canonical/publisher.py`) checks it before any write.
- **Publication mechanics.** No in-app authoring/publication UI or API. Publication happens only through the offline tool (`server/scripts/publish_canonical.py`), which inserts version, topics, relations, content revisions, and `EditorialApproval` last inside one SQLite transaction; any exception before `uow.commit()` rolls everything back.
- **Immutability.** An approved version can never be updated or deleted. `87af9746aec1_canonical_graph.py`'s migration installs triggers rejecting UPDATE/DELETE on any row belonging to a published version, and `CanonicalGraphRepository` exposes no update/delete method at all. A correction is always a new version.
- **Approval-gated reads.** Every read path is gated on `editorial_approvals` existing, not a `status` filter, so a half-seeded version is never readable.
- **v2+ mechanics.** Subsequent versions flow through CUR-04 diff/merge (D9, IDK-407); this decision does not redesign that mechanism, it only adds the diff-review checklist item in section 3.7.

What is genuinely open, and what this decision resolves, is the content and sufficiency of the review behind an approval. Before this decision, `editorial_approvals.basis_ref` is `TEXT NOT NULL` with no format or content requirement beyond not being SQL `NULL`. Every fixture in the repository uses an arbitrary string such as `"fixture-approval-basis-v1"` or `"fixture-basis-should-never-be-used"` (`server/tests/fixtures/canonical/data/*.json`), and nothing distinguishes that string from a genuine review record. Sections 3–5 change that.

## 3. The approval checklist

Every item is required for every version before its `EditorialApproval` may be recorded, except item 7 (v2+ only) and item 3's identity-continuity clause (only for stable IDs carried forward). Each item states what is inspected, pass/fail conditions, and what is recorded — mapped to a `basis_ref` field in section 4.

**3.1 Curriculum-boundary review (CUR-01).** Inspected: every topic's `subject`/`scope_tags` against CUR-01's boundary and CUR-02's DSA carve-out. `validation.py`'s `_validate_curriculum_boundary`/`_validate_no_go_nodes` already reject an out-of-boundary `subject` or a Go token mechanically — that is a floor check, not this item. This item is the judgment layer the validator cannot perform: does each topic's actual content, not just its tag, stay inside the boundary, and does the aggregate avoid implying comprehensive coverage. Pass: every topic's content is defensibly inside its declared subject; framing states a bounded scope. Fail: any topic whose content strays outside its subject, or coverage framed as comprehensive. Recorded: pass/fail plus topics reviewed vs. total (must be equal, section 5).

**3.2 DSA-topic-to-scenario relation review (CUR-02).** Inspected: every `subject == "dsa"` topic. `_validate_dsa_scenario_relations` already rejects a DSA topic with zero `SCENARIO`-typed relation — a floor check, not this item. This item confirms the linked scenario is topically sound: the DSA concept is genuinely load-bearing for solving it, not a relation inserted only to satisfy the validator. Pass: every DSA topic's scenario materially depends on the concept. Fail: a scenario link present but topically vacuous. Recorded: pass/fail plus DSA topics reviewed vs. total (small set by CUR-02's own design; section 5).

**3.3 Prerequisite-graph DAG and stable-identity review.** Two parts. DAG shape: `_validate_relation_cycles` already rejects a cycle in every relation type except `related` — the approver re-confirms that output against the manifest and judges whether `prerequisite` edges form a defensible teaching order (acyclic but backwards still fails). Stable identity: any `stable_id` reused from a prior version (`topic_identity_exists` true) must still denote the same concept — the database guarantees the string persists, not that its meaning did. Pass: sound ordering, and every reused `stable_id` still names the same concept. Fail: pedagogically backwards ordering, or a reused ID whose content now differs materially. Recorded: DAG pass/fail, plus continuity confirmed vs. total reused IDs (never sampled — identity breaks silently corrupt evidence transfer and review history).

**3.4 Source/citation spot-check.** Inspected: `claims` rows on this manifest's content and their `citations`/`sources`/`source_snapshots` (spec §4.3). Two depths: structural completeness — every claim CNT-04 requires citation for (sensitive, disputed, comparative, time/version-dependent) has ≥1 citation with a non-blank locator, pointing at a non-withdrawn source; live-content accuracy — for a sample, the approver opens the cited snapshot and confirms it actually supports the claim. This item does not re-litigate source licensing (IDK-003's separate, unreopened gate). Pass: 100% structural completeness, and the sample finds no unsupported or misrepresented claim. Fail: any missing required citation, or any sampled citation whose source does not support the claim. Recorded: structural result (exhaustive) plus live-check sample/population size (section 5).

**3.5 Layer-reversal regression review (DEP-03).** Inspected: every adjacent pair of the eight approved layers (Essential → Implementation → Internals → Production → Alternatives → Failures → Interview → Sources, IDK-201) per topic. DEP-03 requires a later layer refine, never reverse, an earlier one; its named acceptance evidence is a content-fixture regression set that does not exist in the codebase yet (searched; none found — section 9), so this is currently a fully manual read. Pass: no adjacent pair contradicts an earlier unqualified claim. Fail: any later layer states something incompatible with an earlier layer's unqualified claim. Recorded: pass/fail plus topics reviewed vs. total — exhaustive, never sampled (mis-teaching content is the harm this item exists to catch).

**3.6 Half-seed invisibility and immutability sanity check.** Inspected: after `scripts/publish_canonical.py` reports success, the approver independently re-queries `GET /canonical/versions[/{id}]` and confirms exactly one new version is visible with the expected `version_label`/`manifest_hash` and no orphaned material from any failed attempt. This does not re-run IDK-102's own automated atomicity/trigger tests (`test_canonical_publish.py`, `test_canonical_immutability.py`) — those are mechanism concerns; this is the one check a human can perform on an atomic transaction with no observable interior. Pass: exactly one new version visible, matching expectations. Fail: more than one, a mismatched hash/label, or orphan evidence. Recorded: pass/fail, one fact per publish attempt.

**3.7 Diff review against the previously approved version (v2+, IDK-407).** Inspected: when a prior published version exists, every added, modified, and deleted topic/relation/content item between it and the candidate, computed the same base-to-latest way IDK-407's diff will compute it. Deletions matter most: a deleted topic can carry a learner's evidence into D9's "archived local topic" path, and that consequence must be judged sound before it ships. Pass: every diff item, including every deletion, reviewed and defensible. Fail: any diff item — especially a deletion — left unreviewed. Recorded: base `version_label` diffed against, plus items reviewed vs. total diff items (exhaustive, never sampled).

## 4. The `basis_ref` contract

`basis_ref` stays `TEXT NOT NULL` (spec §4.1's "versioned JSON only for non-relational metadata" convention, already used by `merge_item_bodies.payload_json`/`canonical_merge_followup_bodies.payload_json` under `CheckConstraint("json_valid(payload_json)")`). This decision requires one canonical JSON object with these fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `basis_ref_version` | string, literal `"editorial-approval-basis-v1"` | Schema this payload follows; an incompatible shape change requires a new literal and decision version (section 10). |
| `policy_identifier` | string, literal `"editorial-approval-criteria-v1"` | Ties the approval to the exact criteria version reviewed against (cf. `assessments.scenario_content_revision`, IDK-009 §8.1). |
| `reviewed_manifest_hash` | string, SHA-256 hex | Must equal this row's own `canonical_graph_versions.manifest_hash`. Binds the review to the exact byte-identical published material. |
| `checklist_completed_at` | string, UTC timestamp | When section 3 completed; distinct from `editorial_approvals.approved_at`, stamped at publish time. |
| `review_kind` | `"initial"` \| `"diff"` | Must match whether `list_published_versions()` returns a prior row at review time. |
| `diff_against_version_label` | string \| `null` | Required non-null, equal to the actual latest published `version_label`, exactly when `review_kind` is `"diff"`; `null` otherwise. |
| `curriculum_boundary_review` | `{result, topics_reviewed, topics_total}` | §3.1; reviewed must equal total. |
| `dsa_scenario_review` | `{result, dsa_topics_reviewed, dsa_topics_total}` | §3.2; reviewed must equal total. |
| `dag_identity_review` | `{result, reused_stable_ids_confirmed, reused_stable_ids_total}` | §3.3; confirmed must equal total. |
| `source_citation_review` | `{structural_result, structural_claims_reviewed, structural_claims_total, live_check_sample_size, live_check_population_size, live_check_result}` | §3.4; structural exhaustive, live-check meets §5's minimum. |
| `layer_reversal_review` | `{result, topics_reviewed, topics_total}` | §3.5; reviewed must equal total. |
| `half_seed_immutability_check` | `{result}` | §3.6. |
| `diff_review` | `{result, items_reviewed, items_total}` \| `null` | §3.7; required non-null (equal counts) exactly when `review_kind` is `"diff"`, else `null`. |
| `approver_is_sole_content_author` | boolean | Whether `approver_owner_id` is also the sole `creator_owner_id` across this version's rows — both columns already exist and are already comparable without schema change; this field makes that comparison an explicit recorded fact (section 6). |
| `notes` | string, optional | Elaboration only; never a substitute for a structured field — a `basis_ref` with every structured field blank and substance only in `notes` fails validation (section 6). |

Minimum mechanical validation required at publish time: (1) `json_valid(basis_ref)` — a `CheckConstraint` matching the existing `payload_json_valid` pattern, absent from `EditorialApprovalRow` today (unlike its neighbor `content_revisions.kind_non_blank`); (2) every required field present and correctly typed; (3) `reviewed_manifest_hash` recomputed and compared against this row's actual `manifest_hash`, closing reuse across versions; (4) `review_kind`/`diff_against_version_label`/`diff_review` cross-checked against `list_published_versions()`; (5) every `*_reviewed`/`*_total` pair equal where section 5 requires exhaustiveness, and the live-content sample meeting section 5's minimum. None of this exists in the codebase today (sections 8–9).

`basis_ref` may **not** be: an empty string (fails `json_valid` and every required-field check); a free-text sentence with no structured fields; a bare date; a URL to nothing (fails structurally as a citation locator, or fails `json_valid` if it is the entire value); or a `basis_ref` reused from a different graph version (fails the `reviewed_manifest_hash` cross-check).

## 5. Sampling and sufficiency rules

Default posture is exhaustive; only the live-content citation check is sampled, with a stated floor and rate rather than an arbitrary number.

- **Curriculum boundary (3.1):** 100% of topics. The mechanical half already runs over every topic; CUR-01 is a hard scope boundary the PRD treats categorically, not a quality gradient a sample can stand in for.
- **DSA-scenario relations (3.2):** 100% of DSA-subject topics. CUR-02 keeps this category small by design (the v1 fixture has exactly one); exhaustive review of a small category is cheap and a false pass violates a Must requirement.
- **DAG soundness (3.3):** 100% of the validator's reported relation set (re-confirmation). **Stable-identity continuity (3.3):** 100% of reused `stable_id` values, never sampled — an unreviewed identity break silently corrupts evidence transfer and review scheduling, with no other detection mechanism.
- **Source/citation (3.4):** structural completeness 100% (CNT-04 already bounds the population). Live-content verification sampled at `max(5, ceil(0.20 × distinct_sources_in_version))`, capped at the total when fewer than 5 sources exist. Proposed value: live verification is the one genuinely expensive, non-automatable step, so unlike every other item it does not scale for free; 20% keeps cost sublinear as the catalog grows, and the floor of 5 protects an early small version from a near-zero sample.
- **Layer reversal (3.5):** 100% of topics, every adjacent layer pair — a Must-adjacent safety property, reviewed by reading, which scales the same way authoring did.
- **Half-seed/immutability (3.6):** not a sampling question — one confirmation per publish attempt.
- **Diff review (3.7):** 100% of diff items every time a prior version exists. A partial review covering only additions is explicitly insufficient (section 6): deletions carry the most severe unreviewed downside.

## 6. What this decision forbids

- No approval recorded from a description of intended behavior rather than direct inspection of the shipped artifact — concretely, the exact hash-identified manifest and content bodies passed to `scripts/publish_canonical.py`. Because D1 inserts content and approval atomically in one transaction, "the shipped artifact" for a first-time review is necessarily the pre-publish, hash-identified manifest; `reviewed_manifest_hash` (section 4) makes this checkable rather than asserted.
- No placeholder or engineering `basis_ref` — including every literal string this repository's tests currently use (`"fixture-approval-basis-v1"`, `"fixture-basis-should-never-be-used"`, `"test"`, `"diagnostic-test"`) — on an `editorial_approvals` row attached to a production graph version. These remain legitimate for engineering/mechanism tests under section 7; forbidden only when pointed at a version presented to a learner.
- No self-approval of authored content without disclosing that fact. MVP's single-owner design means `creator_owner_id` and `approver_owner_id` will usually be identical — not forbidden, since D1 already resolved it — but the checklist may not be treated as satisfied by that coincidence without recording `approver_is_sole_content_author: true` and completing it as a deliberate, distinct act.
- No partial approval leaving any topic unreviewed. Every `*_reviewed`/`*_total` pair in `basis_ref` must be equal wherever section 5 requires exhaustiveness.
- No approval carried forward across a graph version without a fresh diff review (section 3.7). A prior version's findings may not substitute for reviewing what actually changed.
- No retroactive approval of an already-published version. D1 makes this structurally impossible today (no update path; triggers reject any attempt), but this decision states the prohibition explicitly so a future workaround — publishing a "correction" version whose `basis_ref` claims to review history it never inspected — is also forbidden, not merely blocked by the current schema.

## 7. Fixture versus production separation

Today the only separation between an engineering fixture publish and a production publish is operational: which manifest file and `--database-url` a human supplies to `scripts/publish_canonical.py`, plus tests running against isolated per-test databases rather than the server's configured `yuno.db`. No column on `canonical_graph_versions`, `topics`, or `editorial_approvals` marks a row non-production. The one existing marker, `NON_PRODUCTION_LABEL` (`server/tests/fixtures/canonical/__init__.py`), is a Python constant living entirely in test code — it is never persisted and cannot travel with a version pointed at a real database.

This is a real gap: nothing prevents a fixture-shaped manifest carrying `basis_ref: "fixture-basis-should-never-be-used"` from being published to whatever database `YUNO_DATABASE_URL` resolves to. This decision closes the gap at the policy layer:

- Section 4's schema cannot be honestly completed against synthetic content — a `curriculum_boundary_review` claiming a `fixture-`/`[SYNTHETIC]`-marked topic satisfies CUR-01 is not a defensible entry.
- `reviewed_manifest_hash` means a fixture's `basis_ref` shape reused against a real manifest fails the hash cross-check outright, since the two will never share a `manifest_hash`.
- Section 6's placeholder prohibition applies specifically at the point a version is presented to a learner; engineering fixtures remain legitimate for IDK-102's own mechanism tests, which never reach a learner-facing read path against a real deployment.

A version is fixture/non-production if and only if it is never published against the database a running Yuno server actually reads from. The moment a manifest is published against that database, this policy's full checklist applies regardless of what its `stable_id`/`title` strings claim about themselves.

## 8. Required removal and implementation evidence

Unlike IDK-008, which found and removed genuine dead code, this review found no obsolete compatibility shim to remove: `editorial_approvals.basis_ref`'s current free-form column is exactly the "allowed preliminary work" IDK-002's own ticket scope sanctioned. What changes is the validation contract governing it, not the column — and there is no fallback preserved for the old any-string acceptance behavior:

1. A `CheckConstraint("json_valid(basis_ref)", name="basis_ref_valid")` on `EditorialApprovalRow` (`server/src/yuno/modules/canonical/models.py`) and its migration, mirroring the existing `payload_json_valid` pattern. Absent today.
2. Framework-free schema validation of the parsed object against section 4, invoked by `publish_canonical_graph` before `uow.canonical.record_approval(approval)` — analogous to `validate_manifest` running before the transaction opens. Absent today: `EditorialApproval` (`domain.py`) has no `__post_init__`, and `publisher.py` forwards `basis_ref: str` unexamined.
3. `scripts/publish_canonical.py`'s `load_manifest` (~line 150) currently reads `approval["basis_ref"]` and forwards it as an opaque string; it must construct and validate the section 4 object from the manifest's `approval` block, rejecting a mismatched shape with the same exit-code-2 behavior it already uses for other malformed manifests.
4. A residue scan confirming no code path can write an `editorial_approvals` row bypassing 1–3. There is exactly one write path today (`CanonicalGraphRepository.record_approval`, called only from `publish_canonical_graph`), so this is a single-call-site check, not a sweep.

No existing row needs migration: no production canonical graph version has ever been published (IMPLEMENTATION_TICKETS.md lists IDK-001/IDK-002 unresolved, and IDK-102's own approval gate requires both before production seeding), so every `editorial_approvals` row in the codebase today is test fixture data.

Before IDK-102's production seed run, or IDK-407's v2 publish, can pass under this policy:

1. Items 1–4 above are implemented and tested: a `basis_ref` failing `json_valid`, a required-field check, the `reviewed_manifest_hash` cross-check, or `review_kind` consistency is rejected before any write.
2. Every section 3 checklist item is completed against the actual manifest and content about to publish, with section 5's sample sizes satisfied and recorded.
3. Section 6's prohibitions are checked and none apply.
4. IDK-503 has inspected the actual persisted `basis_ref` produced by this run against this decision, per its own scope.

A mismatch between a reviewed artifact and its decision record blocks release under IDK-503's own acceptance criteria; at best a non-compliant version remains mechanically approved (readable) but not policy-compliant.

## 9. Known enforcement gaps

- `basis_ref` carries zero mechanical validation today. `TEXT NOT NULL` blocks `NULL`, not an empty string, so `""` currently satisfies the column.
- No cross-check ties a stored `basis_ref`'s claimed content to the `manifest_hash` of its own row; a stale or reused `basis_ref` is not detectable by any query today.
- No schema-level flag distinguishes a fixture publish from a production publish (section 7); separation is entirely operational.
- `topics.level_tag` and `topics.target_capability` carry no `CHECK`-enforced vocabulary at the database layer as of `87af9746aec1_canonical_graph.py` — only `subject` and DSA-scenario relations are mechanically validated. IDK-201's ticket text anticipates a `target_capability` CHECK to the six-value capability ladder, not yet shipped.
- DEP-03's layer-reversal regression fixture set does not exist in the codebase; section 3.5 is a fully manual read with no automated backstop.
- `sources`/`source_snapshots`/`claims`/`citations` exist in `provenance`, structurally ready for section 3.4, but IDK-003 (source licensing/snapshot/withdrawal policy) is itself unresolved — this decision specifies what a citation review must check, not that any source is legally approved for use.
- No production canonical graph version has ever been published under any policy; this decision has no precedent instance of its own application, and its first is whatever version IDK-102 seeds once IDK-001's content exists and this decision is approved.
- IDK-407 (v2 publish/merge) has not shipped; an approver performing section 3.7 today must compute the diff by direct manifest comparison, not a built diff tool.
- IDK-503 has not run and is blocked on IDK-001/IDK-002/IDK-003. Until it runs, this document defines criteria; it is not evidence any version complies with them.

## 10. Change control

`editorial-approval-criteria-v1` is immutable. No criterion in sections 3–6 may be edited, loosened, tightened, added, or removed in place. Any change requires a newly approved decision version with its own `policy_identifier` suffix (`editorial-approval-criteria-v2`, …) and its own `basis_ref_version` literal, so an existing `basis_ref` remains legible as reviewed under v1's rules rather than silently reinterpreted under a later bar — mirroring IDK-009 §12's rule that a version change never rewrites an existing record's meaning.

A new version must fix, at minimum: the exact sample-size formula changed and its scope-specific rationale (an unjustified round number is not acceptable under this decision's own section 5 standard); which `basis_ref` fields are added, removed, or retyped, and whether the change is backward-read-compatible (an incompatible change bumps `basis_ref_version`, never in-place mutation); and whether section 6's prohibitions narrow or widen, stated explicitly. A new version never retroactively invalidates an already-recorded approval; it remains valid evidence under the policy version its `basis_ref.policy_identifier` names.

## 11. Approval record

| Approver | Role | Date | Decision | Version | Basis |
| --- | --- | --- | --- | --- | --- |
| MVP local owner | Designated editorial approver | 2026-08-14 | Approved without changes | 1.0 | Sections 1–10 and the project implementation request |

The approval resolves IDK-002's decision question. It does not create evidence that any graph version complies with these criteria: section 8's validation work is unimplemented, no production canonical graph version has ever been published, and IDK-503 owns the shipped review.

## 12. Approval statement

The designated editorial approver approved this policy by recording:

`Approved IDK-002 recommended editorial-approval-criteria-v1 policy version 1.0 in sections 1–10 without changes.`

No exception may be recorded through this single-sentence form: a partial approval or an approval with modifications requires stating exactly which section changed and re-issuing this document as a new decision version under section 10, not appending a caveat to this statement.
