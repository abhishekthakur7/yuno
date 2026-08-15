# Implementation tickets — Backend Engineer Learning & Interview Prep

**Status:** Planning only. No application code, test, screenshot, dependency, migration, deployment, or other repository file has been changed by this document, and nothing has been installed, migrated, published, deployed, or executed through a runner.

**Source of authority**, highest first:

1. The fixed product, route, and scope instructions governing this plan.
2. PRD Appendix H decisions D1–D11.
3. The 60 PRD `Must` requirements and NFR-01 through NFR-11.
4. `IMPLEMENTATION_SPEC.md`.
5. Remaining PRD material.
6. The surviving selected application as the approved UX reference, where it does not conflict with the above.

Unresolved questions are never silently answered here. Where the PRD or specification leaves something open, this plan carries a decision ticket, a `Blocked by` status, and an explicit stop point until an attributed decision artifact is approved. No threshold, provider command or version, source license, OS/toolchain matrix, retention guarantee, security or sandbox property, readiness claim, or operational guarantee is introduced without that recorded authority.

## Ledgers

| Ledger | Sections | Count |
|---|---|---|
| Blocking decisions | 0 | 11 decision tickets |
| MVP | 1–4 | 29 implementation tickets |
| MVP-hardening | 5 | 5 tickets |
| Later / Post-MVP | 6 | 4 tickets |

Later, Post-MVP, and unresolved-TBD work never appears as an MVP acceptance criterion, and no MVP schema, port, or inactive UI control anticipates one.

## Product name

The product is **Yuno**. This was decided by the product owner and is a settled fact, not an open question — it is deliberately absent from Appendix 7.

The prototype currently ships an inherited, never-decided wordmark "Lattice" in seven places: `index.html`'s `<title>`, the header wordmark and its `aria-label` (`src/selected/LearningApp.tsx`), `package.json`'s `name`, the `data-app="lattice-learning"` DOM hook every Playwright test selects on, all four localStorage key prefixes, and the export filename. Neither `PRD.md` nor `IMPLEMENTATION_SPEC.md` ever names the product, so nothing in the governing documents conflicts with this decision.

Renaming is scoped to two tickets, because most "lattice" occurrences disappear on their own:

- **IDK-103** renames the user-visible and structural identifiers: `<title>`, the header wordmark and `aria-label`, `package.json`'s `name`, and the `data-app` hook (with the matching Playwright selector). Changing a wordmark string is copy, not a redesign, so this does not breach the no-redesign rule.
- **IDK-409** names the export package from the product name; its exact format and version remain IDK-010's to settle.
- **No rename is needed** for the four localStorage key prefixes or the export filename: IDK-107, IDK-303 and IDK-409 delete those code paths outright. Renaming keys that are being removed would be wasted work.

IDK-505's residue scan therefore treats any surviving `lattice` / `Lattice` string as a defect.

## Product invariants held constant

- Exactly two learning paths: **Learn** and **Interview Prep**.
- **My learning** (`/`) is the workspace home, not a learning path.
- Operational tools — Evidence, Imports, Canonical updates, Search, Jobs, Settings, Reports — are supporting destinations, not a learning path.
- Exactly these 14 routes, with `/app/$pageId` validating the 13 `/app/*` page IDs and every other value rendering the existing not-found view linking to `/`:
  `/` · `/app/onboarding` · `/app/learn-roadmap` · `/app/topic-studio` · `/app/interview-hub` · `/app/practice` · `/app/mock` · `/app/reports` · `/app/evidence` · `/app/imports` · `/app/canonical-updates` · `/app/search` · `/app/jobs` · `/app/settings`
- Refresher and Questions remain independently reachable Interview Prep submodes as `?mode=refresher` and `?mode=questions` states of `/app/interview-hub` — no new canonical route.
- Active Mock remains outside the ordinary global shell.
- The selected application is not redesigned.
- No compatibility is preserved for localStorage persistence, legacy-key hydration, fixture evaluation, bundled search, simulated jobs, or retired routes. Each is removed by a named ticket once its API-backed replacement works.

## First production slice

The dependency chain delivers this end to end before anything else:

**My learning → Onboarding → persisted diagnostic/setup → full roadmap preview → explicit goal confirmation → persisted My learning and roadmap**

IDK-107 owns that end-to-end proof and owns removing the prototype localStorage and legacy-hydration behavior once the API-backed replacement works.

## Phase exit semantics

IMPLEMENTATION_SPEC §11 states that gates G1/G2/G4 "cannot remain unresolved for exit" from Phase 1. All three are now resolved as decisions: IDK-001 settles G1's curriculum spine, IDK-002 G2's editorial-approval criteria, IDK-004 G4's role-copy policy. Every gate still requires proof that its decision was applied to shipped artifacts — approving a policy is never the same as demonstrating it, and no production graph version has been published. "Exit" is used in two senses, distinguished here so mechanism work and content approval remain explicit:

- **Engineering exit** — every ticket in the phase is implemented and its required tests pass against approved fixtures. This is what gates *starting the next phase*. It does not require any IDK-0xx decision to be resolved, because every ticket's mechanism is specified to be testable against fixture data, and each decision ticket states the preliminary work permitted while it is open.
- **Content / pilot exit** — the phase's approval gates are resolved and demonstrably applied to shipped artifacts. This is what gates *release, pilot, and any learner-facing content claim*. It is the sense §11's gate list uses.

So Phase 1 reaches engineering exit once IDK-101–IDK-108 pass against a fixture graph explicitly labelled non-production, and reaches content exit only once G1/G2/G4 are each approved and applied. All three policies are approved; all three still owe consuming evidence — IDK-004's shipped copy review, IDK-002's publish-time `basis_ref` validation, and IDK-001's spine actually authored by IDK-201 and published by IDK-102 into a real approved graph version. Decision approval moved the blocker from "unresolved question" to "unbuilt implementation"; it did not move the exit. IDK-503 performs the content-exit review for every gate; IDK-505 is the final release gate and fails while any content exit is outstanding. No fixture-backed engineering exit may be presented as pilot readiness.

This is a terminology reconciliation, not a decision: it selects no answer to any open question, and an approver may relabel either sense without changing a single ticket's scope or tests.

## Reading a ticket

Every ticket uses the same field order. `Status` is `Not started`, `Complete`, `Blocked by <decision ID>`, or `Later` for an implementation ticket, and `Approved` or `Ready` for a Section 0 decision ticket; Appendix 1 defines each value. A `Blocked by` status means an unresolved decision is required for *that ticket's own* acceptance criteria, not that no work can start — each decision ticket states the preliminary work that may proceed. `Estimate` is deliberately unset everywhere: the implementation team estimates after approval.

---

## 0. Blocking decisions and approval gates

These eleven tickets frame the unresolved PRD §14 / IMPLEMENTATION_SPEC §12.3 questions that gate MVP scope. None selects an outcome; each defines the question, the evidence an approver needs, and the exact point downstream work must stop.

### IDK-001 — MVP curriculum spine decision

- Phase: 0 — Blocking decisions
- Status: Approved — decision version 1.0 recorded 2026-08-14
- Objective: Propose, and put to the editorial approver, which Java/Spring Boot/AWS topics and connected System Design/RDB topics constitute the reviewed MVP canonical spine, and which DSA relations are scenario-relevant.
- User-visible outcome: None directly; the eventual answer determines every topic a learner ever sees in Learn.
- PRD traceability: CUR-01 (contributing), CUR-02 (contributing), CNT-01 (contributing)
- Appendix H decisions: None (D1 governs publication mechanics, not curriculum content).
- Owning module: canonical
- Dependencies: None
- Scope:
  - Question (PRD §14 Q1; IMPLEMENTATION_SPEC §12.3 Q1): "Which Java/Spring Boot/AWS topics and which connected System Design/RDB topics form the minimum reviewed MVP spine? Which DSA relations are scenario-relevant?"
  - Evidence required: a candidate topic list with stable IDs, prerequisite/relationship graph draft, curriculum scope tags demonstrating the Java/Spring Boot+AWS boundary (CUR-01), an explicit DSA-topic-to-scenario relation for every DSA node proposed (CUR-02), and written confirmation Go+AWS is entirely absent from the MVP spine.
  - Affected tickets and phases: gates the real (non-fixture) content used by IDK-102's production publish run, IDK-201's authored topic layers, and Phase 1/2 exit; does not block IDK-102's own fixture-based mechanism tests.
  - Allowed preliminary work: build and test the D1 offline publish tool, graph validation (DAG/cycle rejection, stable IDs, curriculum tags), and topic/roadmap read-gates against a synthetic fixture graph explicitly labeled non-production.
  - Stop point: no `canonical_graph_versions` row seeded from this decision may receive an `EditorialApproval` for production learner use, and IDK-102's "publish the real v1" acceptance criterion cannot be reached, until this spine is approved.
- Out of scope:
  - Authoring the actual lesson content/layers for approved topics (IDK-201).
  - The publish tooling's transactional/validation mechanics (IDK-102).
- Data and invariants:
  - Eventual answer must be expressible as `topic_identities`/`topics`/`topic_relations` rows meeting spec §4.3 constraints (stable ID, DAG, curriculum tags, DSA-requires-scenario-relation).
- API/domain/event contracts: None (framing only; no endpoint accepts curriculum content in MVP).
- UX routes and states: `/app/learn-roadmap` and `/app/topic-studio` remain `unavailable` for any goal until a production graph version carries a valid approval record built from this decision.
- Implementation notes:
  - Decision version 1.0 proposes concrete topic IDs, counts, and titles. This supersedes the earlier constraint that no topic be named here: a spine that names no topic cannot satisfy its own "candidate topic list with stable IDs" evidence requirement, and IDK-102's production publish run has nothing to consume. Proposing candidates is not accepting them — no topic is accepted until the editorial review records approval.
- Acceptance criteria:
  - A complete candidate spine exists — every `topic_identities`/`topics`/`topic_relations` field for all 53 topics and 74 relations, the DSA-to-scenario bindings with per-binding justification, the stable-ID naming and retirement rule, the checkpoint scheme, and the exclusion list — and no candidate topic is marked accepted.
- Minimum required tests:
  - Automated: None required by this ticket. As mechanical evidence for the approver, the spine was parsed from the decision document and run through the real `validate_manifest`, returning valid: 53 topics within `ALLOWED_SUBJECTS`, 74 relations (67 `prerequisite`, 7 `scenario`) forming a DAG with no dangling reference or duplicate tuple, every `dsa` topic carrying a `scenario` relation, and no `go`/`golang`/`go_aws` token. Every `level_tag`, `target_capability`, and `recommended_layer` is within IDK-004's and spec §7.1's vocabularies, and the checkpoint ranges tile 0–56 contiguously. This proves the spine is publishable, not that it is the right curriculum.
  - Manual: The content owner, acting as designated editorial approver, approved `mvp-curriculum-spine-v1` on 2026-08-14. IDK-102 retains the publish-time obligation to run `validate_manifest` against the real constructed manifest and record a compliant `basis_ref`; IDK-503 reviews the shipped result.
  - Existing coverage reused: `validate_manifest`'s CUR-01/CUR-02/DAG rules; they check structure, never curriculum judgment.
- Failure and recovery:
  - Unresolved: IDK-102's production seed run and all Phase 1/2 content-facing tickets continue operating against fixture graphs only; no fixture graph is ever presented to a learner as approved.
- Removal/replacement: None.
- Approval gate:
  - Approved by the content owner, acting as designated editorial approver per PRD §13, on 2026-08-14. Artifact: `docs/decisions/IDK-001-mvp-curriculum-spine.md`, decision version 1.0, referenced by the D1 publish run that creates production canonical v1. Approval settles the curriculum question; it publishes nothing, and the decision artifact's section 14 implementation conditions still gate IDK-102.
- Estimate:
  - Completed by decision approval.

### IDK-002 — Frame the editorial approval evidence/criteria decision

- Phase: 0 — Blocking decisions
- Status: Approved — decision version 1.0 recorded 2026-08-14
- Objective: Record `editorial-approval-criteria-v1`: the checklist an approval must complete, the structured `basis_ref` payload it must produce, the sampling minimums that make a review sufficient, and what the policy forbids regardless of who reviews.
- User-visible outcome: None directly; determines what a real `EditorialApproval.basis_ref` must contain before any graph version is trustworthy.
- PRD traceability: CUR-03 (contributing), NFR-03 (contributing)
- Appendix H decisions: D1 (partially resolves the approver role; this ticket scopes only the remaining criteria question).
- Owning module: canonical
- Dependencies: None
- Scope:
  - Resolved question (PRD §14 Q2, partially resolved by D1; IMPLEMENTATION_SPEC §12.3 Q2): decision version 1.0 records the seven-item checklist, the `editorial-approval-basis-v1` payload schema, sampling minimums, and prohibitions in `docs/decisions/IDK-002-editorial-approval-criteria.md`.
  - Approved checklist: curriculum-boundary judgment (CUR-01), DSA-topic-to-scenario soundness (CUR-02), DAG ordering plus stable-identity continuity, source/citation structural completeness and live-content spot-check, layer-reversal regression (DEP-03), half-seed/immutability confirmation, and a v2+ diff review covering every deletion (IDK-407).
  - Approved sufficiency: exhaustive review everywhere except live citation verification, which is sampled at `max(5, ceil(0.20 × distinct sources))` capped at the population. Stable-identity continuity and diff review are never sampled.
  - Approved `basis_ref` contract: one canonical JSON object with a fixed field set, validated at publish time — `json_valid`, required fields, a `reviewed_manifest_hash` cross-check against the row's own `manifest_hash`, and `review_kind` consistency. An empty string, a free-text sentence, a bare date, or a `basis_ref` reused from another version is invalid.
  - Affected tickets and phases: gates the content of real production approval records written by IDK-102's publish tool and IDK-407's v2 publish; does not block their mechanism tests, which use fixture `basis_ref` values under the decision's section 7 separation. IDK-503 reviews the shipped `basis_ref`.
  - Stop point after approval: no production graph version is "reviewed" for pilot readiness until the decision artifact's section 8 validation ships and its section 3 checklist is completed against the exact manifest published.
- Out of scope:
  - Who the approver is (resolved: local owner acting explicitly in that role).
  - The transactional mechanics of publication (IDK-102).
- Data and invariants:
  - `editorial_approvals.basis_ref` stays a `TEXT` column; decision version 1.0 fixes its required content. `editorial-approval-criteria-v1` and the `editorial-approval-basis-v1` payload literal are immutable — a criteria change requires a new decision version so an existing `basis_ref` is never silently reinterpreted under a later bar.
- API/domain/event contracts: None new. The publish path gains framework-free validation of the parsed `basis_ref` object before `record_approval`.
- UX routes and states: None directly; no in-app approval UI exists in MVP (D1).
- Implementation notes:
  - Approval is policy, not enforcement. `basis_ref` carries zero mechanical validation today — `server/src/yuno/modules/canonical/models.py:442` declares it `Text, nullable=False` with no `json_valid` CheckConstraint, so `""` currently satisfies the column, and `publisher.py` forwards the string unexamined.
- Acceptance criteria:
  - Decision version 1.0 records the checklist with per-item pass/fail conditions, the `basis_ref` field schema and its publish-time validation, sampling minimums with per-item rationale, the prohibition list, fixture/production separation, required implementation evidence, enforcement gaps, and immutable change control.
- Minimum required tests:
  - Automated: None — decision framing carries no automated test. The validation the decision requires is implementation work owned by IDK-102.
  - Manual: Designated editorial approver approved `editorial-approval-criteria-v1` on 2026-08-14; IDK-102 retains the publish-path validation obligation and IDK-503 the shipped `basis_ref` review.
  - Existing coverage reused: The existing `payload_json_valid` CheckConstraint pattern and the single `record_approval` write path; neither substitutes for the validation this decision requires.
- Failure and recovery:
  - A `basis_ref` failing any section 4 check is rejected before any write, and the publish transaction rolls back whole. Fixture publishes remain legitimate only against a database no running Yuno server reads from.
- Removal/replacement: The any-string acceptance behavior for `basis_ref` is removed outright, with no fallback preserved for it.
- Approval gate:
  - Approved by the designated editorial approver on 2026-08-14. Artifact: `docs/decisions/IDK-002-editorial-approval-criteria.md`, decision version 1.0.
- Estimate:
  - Completed by decision approval.

### IDK-003 — Frame the source licensing/snapshot/withdrawal policy decision

- Phase: 0 — Blocking decisions
- Status: Approved — decision version 1.0 recorded 2026-08-14
- Objective: Record `source-policy-v1`: the approved source registry by license basis and tier, the forbidden-source denial list, snapshot/cache/excerpt limits, the attribution contract, and the withdrawal/unavailability/replacement state machine.
- User-visible outcome: None directly; determines what may legally appear in the Sources layer and in claim-level citations.
- PRD traceability: CNT-04 (contributing), PRV-02 (contributing)
- Appendix H decisions: None.
- Owning module: provenance
- Dependencies: None
- Scope:
  - Resolved question (PRD §14 Q3; IMPLEMENTATION_SPEC §12.3 Q3): decision version 1.0 records the registry, tier model, limits, attribution contract, and state machine in `docs/decisions/IDK-003-source-licensing-and-snapshot-policy.md`.
  - Approved registry: six source classes on a two-tier model. Tier A (full local snapshot plus quotation) covers the IETF RFC series under the IETF Trust Legal Provisions, PostgreSQL documentation under the PostgreSQL License, and the Spring Framework/Boot reference documentation under Apache-2.0. Tier B (link and citation metadata only, no persisted body) covers Oracle Java SE documentation and the JLS, OpenJDK JEP pages, and AWS documentation — none of which has an identified open license.
  - Approved limits: 10 MiB per Tier A snapshot, no body persisted for Tier B, 20 retained snapshots per source with cited snapshots never pruned, and a 400-character inline verbatim excerpt ceiling per citation.
  - Approved state machine: `unavailable` is transient and entered automatically only after 3 consecutive failed retrievals spanning at least 72 hours; `withdrawn` is terminal-for-new-use and only ever entered by explicit editorial action carrying a `withdrawal_reason`. Whether a stored snapshot may still be served after withdrawal turns on that reason — a `license-revoked`/`license-changed-incompatible` withdrawal purges the body immediately, because re-serving a stored copy after its permitting license ends is a fresh distribution on every serve.
  - Forbidden outright: paywalled content, scraped aggregators, Stack Overflow/Stack Exchange, content with no identifiable license, competitor course material, and model-generated output as a source for another claim.
  - Affected tickets and phases: gates real citation content used by IDK-207 and IDK-201; does not block the schema or fake-adapter provenance mechanism tests, which use synthetic sources. IDK-503 reviews the shipped result.
  - Stop point after approval: all six registry rows are approved at their stated tier. No real external source may be cited in production content until the decision artifact's section 12 implementation evidence exists — the `license_status` CHECK, the tier-branched retrieval path, the status-transition repository method, the excerpt cap, and the registry-population path. That is engineering work, not a review gate.
- Out of scope:
  - Live source retrieval mechanics (Section 4, IDK-404).
  - Cache-key/staleness mechanics for generated content (IDK-207).
- Data and invariants:
  - Decision version 1.0 closes `sources.license_status` to `approved-open-license`/`approved-link-only` and fixes the meaning of each `availability_status` value, plus a five-value `withdrawal_reason` vocabulary. `source-policy-v1` is immutable — adding or removing a registry row, changing a tier, the excerpt cap, or the automatic-`unavailable` threshold requires a new decision version. A citation retains the license basis that applied at its snapshot's `retrieved_at`; no version change retroactively relicenses an existing citation.
- API/domain/event contracts: None new. The attribution contract fixes what a rendered citation must carry; `SourceResponse`/`SourceSnapshotResponse` already return every required field.
- UX routes and states: `/app/topic-studio` Sources sub-view and `/app/search` remain fixture-only until section 12's implementation evidence exists. `unavailable` and `withdrawn` must render as distinguishable facts, which they do not today.
- Implementation notes:
  - Approval is policy, not enforcement, and this policy is further gated than its peers: it was approved in the content-owner capacity only. `HttpSourceRetrievalAdapter` persists the full response body regardless of `license_status`, so no Tier B link-only path exists — retrieving a real Tier B source today would over-retain content its terms do not permit storing. `SqlAlchemySourceRepository` exposes no `update_source`, so no code path can transition a source's status at all.
- Acceptance criteria:
  - Decision version 1.0 records the registry with a named license basis and tier per class, the unapproved and forbidden buckets, numeric snapshot/cache/excerpt limits with enforcement points, the attribution contract, the withdrawal/replacement state machine including the serve-after-withdrawal rule, the staleness rule, the prohibition list, the closed status vocabularies, required implementation evidence, enforcement gaps, and immutable change control.
- Minimum required tests:
  - Automated: None — decision framing carries no automated test. Sections 12's enforcement is implementation work owned by IDK-201/207/404/408.
  - Manual: Content owner approved `source-policy-v1` on 2026-08-14, approving all six registry rows at their stated tier. IDK-503 reviews the shipped result.
  - Existing coverage reused: The adapter's existing 10 MiB bound, content-type/redirect/private-IP rejection, and the immutability triggers on `sources`/`source_snapshots`/`claims`/`citations`; none substitutes for the tier, purge, excerpt, or status-transition enforcement this policy requires.
- Failure and recovery:
  - Until section 12 ships, generation and citation pipelines continue against synthetic fixture sources only. Every `sources` row in the repository today carries `license_status = "fixture-approved"`, which the policy forbids on a production row.
- Removal/replacement: The free-text `license_status` column is closed to the two-value production vocabulary, and the unconditional full-body persistence path is replaced by a tier-branched one. No fallback is preserved for either.
- Approval gate:
  - Approved by the content owner on 2026-08-14. Artifact: `docs/decisions/IDK-003-source-licensing-and-snapshot-policy.md`, decision version 1.0.
- Estimate:
  - Policy completed by decision approval; section 12's enforcement remains to be estimated by the implementing tickets.

### IDK-004 — Approve the user-facing role-taxonomy decision

- Phase: 0 — Blocking decisions
- Status: Approved — decision version 1.0 recorded 2026-08-13
- Objective: Record the exact learner-facing mid/senior/staff competency descriptions, company-title-variation helper, no-beginner audience note, and level/capability interpretation used across onboarding and Interview Prep.
- User-visible outcome: None directly; determines the exact competency-description copy shown during onboarding target-level selection.
- PRD traceability: CORE-02 (contributing), ONB-01 (contributing)
- Appendix H decisions: None.
- Owning module: profiles_goals
- Dependencies: None
- Scope:
  - Resolved question (PRD §14 Q9; IMPLEMENTATION_SPEC §12.3 Q4): `role-competency-copy-v1` records exact copy and behavior in `docs/decisions/IDK-004-role-level-competencies.md`.
  - Approved labels: Mid-level backend engineer, Senior backend engineer, and Staff-level backend engineer, each mapped to the unchanged `Mid-level`/`Senior`/`Staff` persisted value.
  - Approved boundary: titles vary across companies; learners choose desired practice scope, not a validated current title. The selection predicts no hiring, promotion, or job performance and introduces no beginner track.
  - Affected tickets and phases: IDK-104/105 apply the copy to setup, IDK-301 applies it to Interview Prep, IDK-405 consumes it alongside IDK-009's evaluator calibration, and IDK-503 reviews the shipped result.
  - Stop point after approval: unapproved competency prose may not ship, and the approved copy is not production-active until the decision artifact's section 6 evidence passes.
- Out of scope:
  - Changing the base three-tier enum (already given in PRD §3).
  - Goal workspace CRUD mechanics (IDK-104).
- Data and invariants:
  - `goal_workspaces.target_level` remains exactly `Mid-level`/`Senior`/`Staff`; capability remains independently selected from `know`/`understand`/`choose`/`implement`/`diagnose`/`defend`.
  - Level is learner-confirmed, never inferred from title, employer, years, imports, diagnostics, assessment, or model output; changing it never relabels historical evidence or assessments.
- API/domain/event contracts: None.
- UX routes and states: `/app/onboarding`, goal Settings, Interview Prep level controls, and hands-on role-context help consume one versioned copy registry; compact controls retain the stable labels and expose the selected description accessibly.
- Implementation notes: Approval is display-copy/data policy, not a schema migration or compatibility layer.
- Acceptance criteria:
  - Decision version 1.0 records exact labels, descriptions, audience/title-variation/capability helpers, ambiguity/history behavior, IDK-009 alignment, activation evidence, and change control.
- Minimum required tests:
  - Automated: None — decision framing carries no automated test.
  - Manual: Product owner approved `role-competency-copy-v1` on 2026-08-13; consuming tickets retain component and shipped-copy review obligations.
  - Existing coverage reused: PRD §3 fixes the three labels and audience baseline; IDK-009 fixes matching evaluator calibration. Neither substitutes for consuming UI evidence.
- Failure and recovery:
  - Missing/mismatched copy with a valid stored enum shows the stable label and an unavailable helper without forcing reselection. A missing/invalid target value requires explicit selection and never silently defaults; neither case invents a description.
- Removal/replacement: None.
- Approval gate:
  - Approved by the product owner on 2026-08-13. Artifact: `docs/decisions/IDK-004-role-level-competencies.md`, decision version 1.0.
- Estimate:
  - Completed by decision approval.

### IDK-005 — Approve the local runner support matrix

- Phase: 0 — Blocking decisions
- Status: Approved — decision version 1.0 recorded 2026-08-13
- Objective: Record the exact MVP operating-system, Java, learner-language, build-mode, detection, and unsupported-configuration policy for local execution.
- User-visible outcome: None directly; determines what "supported/missing/incompatible" toolchain detection reports to a learner.
- PRD traceability: NFR-10 (contributing)
- Appendix H decisions: None.
- Owning module: runner
- Dependencies: None
- Scope:
  - Resolved question (PRD §14 Q4; IMPLEMENTATION_SPEC §12.3 Q5): `runner-toolchain-v1` supports attested Ubuntu 24.04 LTS host/conventional-VM rows on `x86_64` or `arm64`, a complete stable JDK `21.x`, and direct application-constructed `javac`/`java` compile/test only, exactly as recorded in `docs/decisions/IDK-005-local-runner-support-matrix.md`.
  - Learner Python execution, Maven, Gradle, Ant, wrappers, dependency downloads, macOS, Windows, WSL, containers, other Linux distributions/releases, and every unlisted configuration are unsupported in MVP. Go remains absent/Later. IDK-008 decision v1.0 separately approves database execution as absent.
  - Detection is configuration-led from one absolute JDK home, validates the exact platform/architecture and paired `java`/`javac` identity, runs a fixed sentinel, and revalidates before execution. Exact state precedence, safe diagnostic codes, learner messages, records, evidence, and change control are part of decision version 1.0.
  - Affected tickets and phases: the support-policy part of IDK-406's NFR-10 gate is satisfied. IDK-007 and IDK-008 are also approved; IDK-406 is Ready, but implementation/exact-tuple evidence still prohibits activation.
- Out of scope:
  - Runner process mechanics and enforcement implementation (IDK-406).
  - Enablement, numeric resource limits, termination grace, and cleanup posture (IDK-007).
  - Database-exercise posture (IDK-008).
- Data and invariants: Decision version `runner-toolchain-v1` is immutable. Matrix/invocation changes require a newly approved version. Stable JDK 21 patch/implementor changes remain probe-compatible but require new exact-tuple activation evidence; they never enable execution automatically.
- API/domain/event contracts: `runner-toolchain-v1` fixes Java capability states, diagnostics/messages, safe response metadata, top-level enablement separation, server-owned test-driver resolution, and immutable snapshot/evidence references; IDK-406 owns their schema/API implementation and generated-contract replacement.
- UX routes and states: None in my sections.
- Implementation notes: Approval is policy, not activation. A probe-compatible Java item may be `supported`; top-level runner enablement remains false without the exact platform/JDK/executable evidence and IDK-007's complete posture.
- Acceptance criteria:
  - Decision version 1.0 records the exact matrix, direct-JDK compile/test contract, paired-tool discovery, state precedence, safe diagnostic/message set, unsupported configurations, activation ownership, and immutable change control.
- Minimum required tests:
  - Automated: None — decision framing carries no automated test.
  - Manual: Engineering owner approved `runner-toolchain-v1` on 2026-08-13; IDK-406 retains every implementation, state/message, race, and exact-tuple smoke-test obligation.
  - Existing coverage reused: Official Java, Ubuntu, Python subprocess/OS, Maven, and Gradle documentation plus read-only local inspection are recorded in the decision artifact; none substitutes for activation evidence.
- Failure and recovery:
  - Missing/unverifiable/mismatched platform or tools fail closed with a fixed safe diagnostic and no learner process. Unsupported configurations retain full static review.
- Removal/replacement: None.
- Approval gate:
  - Approved by the engineering owner on 2026-08-13. Artifact: `docs/decisions/IDK-005-local-runner-support-matrix.md`, decision version 1.0.
- Estimate:
  - Completed by decision approval.

### IDK-006 — Frame the provider CLI version/authentication-discovery decision

- Phase: 0 — Blocking decisions
- Status: Approved — decision version 1.1 recorded 2026-08-13
- Objective: Record the approved version-agnostic Codex/Claude CLI capability policy and the safe installation/authentication discovery policy, completing Appendix H D7's provider transport decision.
- User-visible outcome: None directly; determines what "provider unavailable/misconfigured" detection can safely report.
- PRD traceability: AI-02 (contributing)
- Appendix H decisions: D7 (transport, timeout, environment, cancellation, version policy, and authentication discovery resolved by decision version 1.1).
- Owning module: provider
- Dependencies: None
- Scope:
  - Resolved question (PRD §14 Q7; IMPLEMENTATION_SPEC §12.3 Q6): any identified installed CLI version is eligible; exact commands, fixed models, capability probes, environment policy, timers, and safe discovery are recorded in `docs/decisions/IDK-006-provider-cli-support.md`.
  - Evidence required: version-agnostic capability discovery for Codex 5.6 Terra/high and Claude, and a safe (non-secret-leaking) authentication-discovery procedure consistent with D7's env-allowlist and redaction rules (spec §8.5).
  - Affected tickets and phases: gate G6 is satisfied for IDK-403 by decision version 1.1; implementation and security/privacy evidence remain required before configured capability may ship.
- Out of scope:
  - CLI subprocess transport mechanics (resolved by D7, implemented in Section 4).
  - Generated-content cache/provenance contract (IDK-207).
- Data and invariants: None owned by Sections 0–2.
- API/domain/event contracts: None.
- UX routes and states: None in my sections.
- Implementation notes: None.
- Acceptance criteria:
  - Decision version 1.1 records every required provider/version-policy/command/model/discovery/environment/timer/cancellation/schema/recovery/evidence row and is mechanically enforced by IDK-403.
- Minimum required tests:
  - Automated: IDK-403 provider discovery, adapter, security, capability-cache, and wiring tests demonstrate the adopted matrix.
  - Manual: Engineering owner approved decision version 1.1 on 2026-08-13.
  - Existing coverage reused: official primary CLI references and read-only local CLI help/version/status probes recorded in the decision artifact.
- Failure and recovery:
  - Missing executable, unidentified or incompatible command surface, and unavailable authentication remain distinct fail-closed capability states with fixed recovery guidance; numeric version values are never rejected.
- Removal/replacement: None.
- Approval gate:
  - Approved by the engineering owner on 2026-08-13. Artifact: `docs/decisions/IDK-006-provider-cli-support.md`, decision version 1.1.
- Estimate:
  - Completed with the IDK-403/404 implementation.

### IDK-007 — Approve the runner enablement and resource posture

- Phase: 0 — Blocking decisions
- Status: Approved — decision version 1.0 recorded 2026-08-13
- Objective: Record the disabled-by-default Settings opt-in, per-run confirmation, exact whole-tree resource limits, network controls, termination, cleanup, reconciliation, and safety-suspension posture for local Java execution.
- User-visible outcome: None directly; determines whether/how the runner feature is ever exposed to a learner.
- PRD traceability: RUN-01 (contributing), RUN-02 (contributing), RUN-03 (contributing)
- Appendix H decisions: None (Appendix C is a threat-model reference, not a D-decision).
- Owning module: runner
- Dependencies: None
- Scope:
  - Resolved question (PRD §14 Q5; IMPLEMENTATION_SPEC §12.3 Q7): `runner-environment-v1`, `runner-limits-v1`, `runner-risk-ack-v1`, and `runner-run-confirmation-v1` are recorded in `docs/decisions/IDK-007-runner-enablement-and-resource-posture.md`.
  - Runner is off until the owner explicitly enables it in Settings under the exact tuple/evidence/current-policy gates; every run still needs a single-use five-minute confirmation. Policy/evidence changes and cleanup failures revoke/suspend enablement; there is no automatic enablement.
  - Aggregate compile+test limits are exact thresholds/denials: 10-second preparation; wall termination threshold 30 seconds; aggregate-CPU termination threshold 20 CPU-seconds with 10-ms target observation cadence and two-CPU bandwidth (actual observation/final usage recorded, no false scheduler-overshoot guarantee); 1 GiB/no-swap memory; 128 tasks; 100/10 MiB learner input; 256 KiB driver; 1 MiB each/2 MiB aggregate output; 16 MiB file; 256 FDs; no core; authoritative 256 MiB/10,000-entry workspace denial/classification; one live and three queued runs; and two-second graceful TERM/tree-empty windows. Limits/control failure freeze and kill immediately; file/FD OS denials are not fabricated terminal classifications.
  - Enforcement uses one delegated parent cgroup-v2 subtree with workspace-server/payload children, an administrator-installed root-owned broker under immutable `runner-broker-service-v1` service-manager death/watchdog coupling, immutable runtime-view/workspace-filesystem/filter manifests, a complete privilege drop to a dedicated runner identity, private user/PID/mount/network namespaces with only broker-owned `runner-workspace-fs-v1` writable, `no_new_privs`, fixed RLIMIT defense-in-depth, and an architecture-verified deny-by-default syscall allowlist. The workspace server records a monotonic denial event before returning `ENOSPC`; cleanup failure or broker/control/filesystem loss creates immediate persistent safety suspension; startup and shutdown reconcile before runner enablement.
  - Affected tickets and phases: IDK-406's enablement/resource-policy gate is satisfied. IDK-008 is also approved, so IDK-406 is Ready; implementation/native exact-tuple evidence still prohibits activation.
- Out of scope:
  - Runner mechanisms and native evidence (IDK-406).
  - OS/JDK/build-mode policy (IDK-005), database exercises (IDK-008), and retained-output/cleanup-intent lifecycle (IDK-010).
- Data and invariants: All nine policy IDs (`runner-environment-v1`, `runner-limits-v1`, `runner-risk-ack-v1`, `runner-run-confirmation-v1`, `yuno-runner-broker-v1`, `runner-broker-service-v1`, `runner-runtime-view-v1`, `runner-workspace-fs-v1`, `runner-syscall-filter-v1`) and all numeric/state/message semantics are immutable version 1.0; a change revokes acknowledgement/enablement and requires a new approved version and activation evidence.
- API/domain/event contracts: Version 1.0 fixes desired/effective enablement, Settings acknowledgement, per-run confirmation/expiry, limit codes/messages, concurrency, safety suspension/reset, immutable limit snapshots, and cleanup/reconciliation records. IDK-406 owns implementation/generated contracts.
- UX routes and states: Settings owns explicit enable/disable/re-acknowledgement; Topic Studio owns per-run confirmation and fixed disabled/limit/cancel/cleanup states; Submit/static review remains independent.
- Implementation notes: Approval is not activation. Compatible toolchain state can remain visible while `effective_enabled=false`; no learner process starts without exact-tuple evidence and every control.
- Acceptance criteria:
  - Decision version 1.0 records every enablement gate, acknowledgement, numeric limit/measurement, cgroup/workspace/network boundary, message, termination/cleanup/reconciliation transition, record, version rule, activation test, and implementation removal.
- Minimum required tests:
  - Automated: None — decision framing carries no automated test.
  - Manual: Engineering/security owner approved decision version 1.0 on 2026-08-13; IDK-406 retains all mechanism, boundary, race, native, security, and accessible-UX evidence.
  - Existing coverage reused: PRD Appendix C, the IDK-005 toolchain boundary, current-code audit, and official Linux/Python documentation are recorded in the artifact; none substitutes for activation evidence. IDK-007 independently owns its execution/admission/escalation values and does not treat pending lifecycle policy as prior approval.
- Failure and recovery:
  - Incomplete/unverifiable controls keep effective enablement false. Unverified process/workspace cleanup immediately suspends the runner and requires recorded manual recovery; the rest of Yuno/static review remains available.
- Removal/replacement: None.
- Approval gate:
  - Approved by the engineering/security owner on 2026-08-13. Artifact: `docs/decisions/IDK-007-runner-enablement-and-resource-posture.md`, decision version 1.0.
- Estimate:
  - Completed by decision approval.

### IDK-008 — Approve the MVP database-exercise posture

- Phase: 0 — Blocking decisions
- Status: Approved — decision version 1.0 recorded 2026-08-14
- Objective: Record `database-exercise-posture-v1`: MVP exposes no executable database connector, while mechanisms remain eligible for IDK-001/002-approved RDB content and explicitly labelled static SQL/design review.
- User-visible outcome: None directly; IDK-406 must remove false relational-capability advertising while static artifact review remains possible without opening a database connection.
- PRD traceability: RUN-01 (contributing)
- Appendix H decisions: None.
- Owning module: runner
- Dependencies: None
- Scope:
  - Resolved question (PRD §14 Q6; IMPLEMENTATION_SPEC §12.3 Q8): version 1.0 adopts neither learner-supplied nor product-managed database execution in MVP. Artifact: `docs/decisions/IDK-008-database-exercise-posture.md`.
  - Relational/database execution is absent from capabilities, Settings, confirmation/run contracts, persisted enums/checks, generated clients, and UI. Configuration or an installed/listening database never creates a capability.
  - The Java-only runner schema has no relational discriminator or compatibility path. The exact retired regression signature is `POST /runner/confirmations` with an otherwise-valid body containing `"language":"relational"`; it receives the standard `422` closed-schema response before route/UoW. Other unknown fields/invalid values use ordinary schema validation, while SQL artifact text remains eligible for static review.
  - Subject to IDK-001/002 content approval, RDB SQL/design artifacts and static rubric review remain eligible. Each review-specific limitation must say it made no database connection, executed no statement/plan/migration/concurrency behavior, and proves no runtime/persistence/performance/locking/production behavior; no global exact sentence is mandated.
  - Affected tickets and phases: this resolves IDK-406's final decision blocker and IDK-503 reviews the shipped absence/rejection. It does not activate Java execution.
- Out of scope:
  - Implementing any learner-supplied or managed database connector, accepting credentials/endpoints, provisioning lifecycle, or weakening the approved Java socket-denial boundary.
- Data and invariants: `database-exercise-posture-v1` is immutable; no structured database-execution configuration/credential/endpoint, confirmation, job, runner record, or output is created by invalid runner input. Learner-authored static content is governed separately by privacy/export policy.
- API/domain/event contracts: Relational/database values are absent from capability/confirmation/run schemas; the exact retired `POST /runner/confirmations` `"language":"relational"` signature receives ordinary standard `422` schema validation before route/UoW. IDK-406 owns the removal and generated-contract/zero-side-effect evidence.
- UX routes and states: No relational connector control or disabled placeholder ships. RDB static review remains usable and explicitly says no database connection or runtime validation occurred.
- Implementation notes: Approval requires IDK-406 to remove a false placeholder capability rather than adding a second privileged execution system; it does not claim the removal is already live. Any future connector requires a new approved engine/credential/network/operation/lifecycle policy and its own activation evidence.
- Acceptance criteria:
  - Decision version 1.0 records absence, closed-schema validation, static-review semantics/ownership, obsolete-path removal, change control, and implementation/review evidence ownership without claiming execution activation.
- Minimum required tests:
  - Automated: None — decision framing carries no automated test.
  - Manual: Engineering owner approved `database-exercise-posture-v1` on 2026-08-14; IDK-406 owns negative implementation evidence and IDK-503 the shipped review.
  - Existing coverage reused: PRD RUN-01's optionality, IMPLEMENTATION_SPEC §12.2/§12.3, the current false configured-string capability audit, and approved IDK-005/007 boundaries are recorded in the artifact.
- Failure and recovery:
  - Until IDK-406 removes the placeholder paths and proves closed-schema zero-side-effect rejection, no relational/database capability is exposed. Static review remains the recovery/fallback in every state.
- Removal/replacement: IDK-406 removes `runner_relational_connector`, `RunnerLanguage.RELATIONAL`, relational SQLite checks/migrations, the configured-string detector, relational OpenAPI/client/UI variants, fixtures, and compatibility paths. Its Java-only migration transactionally deletes any non-authoritative `language='relational'` placeholder rows, exclusively owned bodies/inputs/outputs, and linked `kind='runner'` jobs/results/attempts/events whose logical request/run/result references target those placeholders. Unrelated jobs and all goals/artifacts/evidence survive, and no dangling logical reference remains; IDK-501 verifies this approved obsolete-row removal and governed-data preservation.
- Approval gate:
  - Approved by the engineering owner on 2026-08-14. Artifact: `docs/decisions/IDK-008-database-exercise-posture.md`, decision version 1.0.
- Estimate:
  - Completed by decision approval.

### IDK-009 — Frame the representative assessment scenarios and derived-state rule set decision

- Phase: 0 — Blocking decisions
- Status: Approved — decision version 1.0 recorded 2026-08-13
- Objective: Record the approved representative initial/delayed hands-on and Practice/Mock scenarios, rubric dimensions and qualitative outcomes, role-level breadth, ambiguity policy, deterministic derived-state rules, and review-scheduling parameters.
- User-visible outcome: None directly; determines the real rubric dimensions, scenario content, and readiness/coverage/proficiency/retention rules a learner eventually sees, while the deterministic function shape itself is already fixed by Appendix H D6.
- PRD traceability: EVAL-01 (contributing), EVAL-02 (contributing), PRG-01 (contributing), PRG-02 (contributing), HND-03 (contributing), RET-01 (contributing), RET-03 (contributing)
- Appendix H decisions: D6 fixes the function shape; this ticket separately approves its production policy as `derived-state-v1`.
- Owning module: evidence_evaluation
- Dependencies: None
- Scope:
  - Resolved question (PRD §14 Q8; IMPLEMENTATION_SPEC §12.3 Q9): the twelve-scenario mid/senior/staff matrix, three rubric versions, qualitative outcome representation, valid-alternative/ambiguity policy, `derived-state-v1`, and `review-schedule-v1` are recorded in `docs/decisions/IDK-009-assessment-and-derived-state.md`.
  - Approved breadth: initial and delayed changed-context hands-on, Practice, and Mock at each exposed level; delayed evidence is eligible no earlier than seven UTC calendar dates after its exact paired initial submission.
  - Affected tickets and phases: the decision gate is satisfied for IDK-204–206 and IDK-302–304, and the scenario/rubric portion is satisfied for IDK-405/IDK-503. Together with approved IDK-004, this removes IDK-405's decision blockers. IDK-204 owns rubric manifests and exact canonical-topic mappings, IDK-302 owns Practice records, IDK-303 owns Mock records, and IDK-405 owns hands-on records. Consuming code, the IDK-001/102 approved graph mapping, the IDK-003 source posture for factual corrections, and manual scenario-realism evidence remain required before production activation or release.
  - Stop point after approval: no fixture/unapproved scenario or rubric may be presented as reviewed content, and progress remains non-authoritative until the decision artifact's section 11 implementation evidence passes.
- Out of scope:
  - The deterministic function's shape and invariants (already resolved by D6; implemented in IDK-205).
  - Runtime content loading, persisted scenario/revision/phase and normalized ambiguity/carry-forward fields, derived-rule activation, and review-scheduler activation, which remain implementation work in their owning tickets.
- Data and invariants:
  - Scenario, rubric, ambiguity, derived-rule, and schedule versions are immutable references. Existing fixture records retain their fixture identity and never become approved by relabelling.
- API/domain/event contracts: None.
- UX routes and states: `/app/evidence`, `/app/reports`, `/app/practice`, `/app/mock`, and `/app/topic-studio` consume the approved versions only after their implementation gates pass.
- Implementation notes:
  - Version 1 deliberately uses five qualitative dimension outcomes (`pass`, `trade-off`, `factual-correction`, `not-demonstrated`, `ambiguity-unresolved`) and conservative classifications with no hidden numeric score or topic/rubric weights.
- Acceptance criteria:
  - Decision version 1.0 records every required role/scenario cell and content revision, scenario/capability/rubric/pair mapping, rubric dimension/outcome, curated valid-alternative/near-miss case, ambiguity persistence/neutrality rule, deterministic derived-state classification/timing/aggregation rule, scheduling parameter, disclosure, and version-change rule.
- Minimum required tests:
  - Automated: None — decision framing carries no automated test.
  - Manual: Content/assessment owner approved decision version 1.0 on 2026-08-13; consuming tickets retain their implementation and shipped-artifact reviews.
  - Existing coverage reused: PRD Appendix H D6 and the implemented fixture mechanisms establish the fixed function shape; they do not substitute for production activation evidence.
- Failure and recovery:
  - Missing or mismatched approved content/rule data fails closed to non-authoritative/unavailable; fixture content remains explicitly non-production.
- Removal/replacement: None.
- Approval gate:
  - Approved by the content/assessment owner on 2026-08-13. Artifact: `docs/decisions/IDK-009-assessment-and-derived-state.md`, decision version 1.0.
- Estimate:
  - Completed by decision approval.

### IDK-010 — Frame the combined size/retention and export/delete/logging lifecycle decision

- Phase: 0 — Blocking decisions
- Status: Approved — policy version 1.0 recorded 2026-08-13
- Objective: Frame, as one combined decision, the size/retention limits for imports/artifacts/transcripts/generated content/job history/runner output/temp files/diagnostic expiry, and the precise export package/versioning, delete-recovery, backup, and log-retention/redaction posture.
- User-visible outcome: None directly; determines what limits and lifecycle guarantees Settings can honestly display.
- PRD traceability: SET-01 (contributing), NFR-04 (contributing), NFR-06 (contributing), DAT-02 (contributing)
- Appendix H decisions: D5 (evidence tombstone mechanics resolved; retention timing left open), D4 (job/event retention referenced but timing open).
- Owning module: settings_data
- Dependencies: None
- Scope:
  - Resolved question (PRD §14 Q10+Q11; IMPLEMENTATION_SPEC §12.3 Q10+Q11, combined): policy version 1.0 records every size/count limit, retention duration, export contract item, delete/recovery/backup posture, and logging/support-access rule in `docs/decisions/IDK-010-data-lifecycle-policy.md`.
  - Approved export contract: one canonical UTF-8 JSON document, format identifier `yuno-portable-export` version `1.0`, filename `yuno-export-v1-YYYYMMDDTHHMMSSZ.json`, sorted keys and no insignificant whitespace, SHA-256 integrity digest over the canonical `data` object, and stable `availability: unavailable` reasons (`tombstoned`, `source-missing`, `raw-original-excluded`, `policy-excluded`). Interview transcripts, raw import originals, quarantined provider output, and runner output bodies are excluded from v1 and marked, never fabricated or silently omitted.
  - Approved delete/backup posture: goal deletion is irreversible with no recovery window and no undelete; Yuno creates no backups and supports no in-app restore; only non-content IDs, hashes, versions, impact snapshot, status, and timestamps survive.
  - Approved logging posture: an ordinary-log field allowlist, additional denial of query strings, bodies, user agents, IP addresses, email/display names, arbitrary exception messages, and unknown fields; five 10 MiB owner-only rotated files capped at 14 days or 50 MiB; no remote support access, upload, or telemetry forwarding.
  - Affected tickets and phases: the decision gate is satisfied for IDK-409 (export/delete/redaction/logging orchestration) and for the production expiry/cap values referenced by IDK-105 (diagnostic expiry, 30 days) and IDK-202 (overlay-proposal pending cap, 25 per goal). IDK-503's G10/G11 review and section 10's review evidence remain required.
  - Stop point after approval: production export stays disabled and Settings may claim no retention, recovery, or redaction guarantee until the decision artifact's section 14.6 enforcement gaps are implemented and section 10's privacy-review evidence passes. Approval closed the decision question; it waived no implementation evidence.
- Out of scope:
  - The tombstone/downgrade transaction mechanics themselves (IDK-108, already fully specified by D5).
  - Full export/delete job orchestration UI (Section 4, IDK-409).
- Data and invariants:
  - `export_operations`, `delete_operations`, `evidence_tombstones` remain schema-complete; policy version 1.0 fixes their retention/recovery/format VALUES. The policy version is an immutable reference — changing an approved value requires a newly approved version, not an edit.
- API/domain/event contracts: None owned by this ticket; the approved export envelope, `availability`/reason vocabulary, and log allowlist are implemented by IDK-409.
- UX routes and states: `/app/settings` export/delete regions may display only the guarantees section 14 approves, and only once the matching enforcement ships; an approved-but-unenforced limit is not displayable.
- Implementation notes:
  - Approval is policy, not enforcement. The decision artifact's section 14.6 names the enforcement gaps that exist today, and section 11 requires every current `server/src/yuno/config.py` placeholder to be reconciled against the approved tables — no existing default became policy merely by being in code.
- Acceptance criteria:
  - Policy version 1.0 records every size/count limit, retention duration and clock, export contract item, delete/recovery/backup posture, logging/support-access rule, required review evidence, enforcement-gap list, and change-control rule.
- Minimum required tests:
  - Automated: None — decision framing carries no automated test.
  - Manual: Product/privacy owner approved policy version 1.0 on 2026-08-13 through the decision artifact's section 14.7 approval statement; IDK-409 retains the implementation evidence and IDK-503 the G10/G11 privacy review over section 10's representative dataset.
  - Existing coverage reused: The NIST Privacy Framework, ICO storage-limitation, OWASP logging, and NIST SP 800-88 Rev. 2 references recorded in section 14; none substitutes for enforcement evidence.
- Failure and recovery:
  - Until an approved value has a matching enforcement mechanism, it stays configurable and undisplayed; Settings never presents an approved-but-unenforced limit as an active guarantee.
- Removal/replacement: The approved 1-hour terminal runner-workspace janitor retention replaces the 24-hour engineering placeholder; the unset export policy is replaced by the `yuno-portable-export` 1.0 contract; stderr structured logging is replaced by the approved owner-only rotated local files.
- Approval gate:
  - Approved by the product/privacy owner on 2026-08-13. Artifact: `docs/decisions/IDK-010-data-lifecycle-policy.md`, policy version 1.0.
- Estimate:
  - Completed by decision approval.

### IDK-011 — Frame the external telemetry decision

- Phase: 0 — Blocking decisions
- Status: Ready
- Objective: Frame whether any external telemetry is permitted after MVP, and if so, under what consent, disclosure, minimization, and deletion rules.
- User-visible outcome: None directly; MVP ships with local-only guardrail events regardless of this decision's outcome (PRD §13, spec §12.2 default #3).
- PRD traceability: None of the 60 Musts require telemetry; PRV-01 (contributing), PRV-02 (contributing) as the disclosure boundary any future telemetry would have to respect.
- Appendix H decisions: None.
- Owning module: audit_observability
- Dependencies: None
- Scope:
  - Question (PRD §14 Q12; IMPLEMENTATION_SPEC §12.3 Q12): "Is any external telemetry included after MVP, and if so, with what explicit consent and disclosure?"
  - Evidence required: a proposal for consent flow, disclosure copy, data-minimization scope, and deletion rules for any future external telemetry, explicitly separate from the local-only guardrail events already described in PRD §13.
  - Affected tickets and phases: gates only IDK-604 (Post-MVP, separately approved scope per §6); does not affect any MVP ticket, since PRD explicitly locks MVP to local-only events.
  - Allowed preliminary work: implement local-only guardrail event recording (fabricated citations, unsupported runtime claims, silent mutations, overconfident transfer, invalid schema output, unapproved publication attempts, level-inappropriate scenarios) within `audit_events`, with no external transmission path.
  - Stop point: no external telemetry code path may exist or be enabled in MVP under any configuration; this decision only unlocks Post-MVP scope (IDK-604), never an MVP ticket.
- Out of scope:
  - Local structured logging/redaction (IDK-010).
  - Any MVP audit-event mechanism (owned by IDK-101).
- Data and invariants:
  - `audit_events` remains local-only regardless of this decision's outcome.
- API/domain/event contracts: None.
- UX routes and states: None.
- Implementation notes: None.
- Acceptance criteria:
  - A documented open telemetry question exists; no external telemetry consent/disclosure model is declared adopted.
- Minimum required tests:
  - Automated: None — decision framing carries no automated test.
  - Manual: Product/privacy owner reviews and either declines external telemetry for the foreseeable roadmap or approves a consent/disclosure model for Post-MVP.
  - Existing coverage reused: None.
- Failure and recovery:
  - Unresolved (default state): external telemetry stays disabled indefinitely; no MVP behavior changes.
- Removal/replacement: None.
- Approval gate:
  - Approver: TBD (product/privacy owner per PRD §13, G12 per spec §12.1). Required artifact: either a declination or an approved external-telemetry consent/disclosure model, scoped to Post-MVP only.
- Estimate:
  - TBD; implementation team to estimate after approval.

## 1. MVP foundation

These eight tickets deliver the modular-monolith skeleton, the approval-gated canonical publication mechanism, the exact route contract, goal-workspace multiplicity, persisted diagnostics, deterministic roadmap projection, the atomic first end-to-end slice, and conservative evidence transfer/delete — replacing the prototype's client-only localStorage model with server-persisted, owner-scoped state.

### IDK-101 — Modular-monolith foundation: persistence, UoW, OpenAPI boundary, audit

- Phase: 1 — MVP foundation
- Status: Complete
- Objective: Stand up the FastAPI/SQLAlchemy/SQLite modular monolith per spec §3.2/§3.3: the `owner_id` seam with a server-resolved local owner, foreign-key-enforced SQLite, a single Alembic head check, one UnitOfWork per HTTP command, an OpenAPI-generated TypeScript client with CI drift check, append-only `audit_events`, and enforced module import boundaries.
- User-visible outcome: None directly observable by a learner; every later ticket's persistence, ownership isolation, and auditability depend on this skeleton existing correctly.
- PRD traceability: SYS-01 (primary), DAT-01 (primary), NFR-03 (primary), NFR-07 (primary)
- Appendix H decisions: None.
- Owning module: identity, audit_observability (cross-cutting: applies to every module via shared UoW/Alembic/dependency-direction conventions)
- Dependencies: None
- Scope:
  - Domain/application layers with zero imports of FastAPI, SQLAlchemy ORM types, subprocess APIs, FTS syntax, or provider-specific payloads (spec §3.2).
  - One built-in `owners` row (`kind='local_builtin'`), server-resolved on every request; client-supplied owner IDs ignored/rejected (spec §5.1).
  - Every owner-owned table carries `owner_id`; every goal-owned table also carries `goal_id`; composite `UNIQUE(id, owner_id[, goal_id])` and composite FKs.
  - One application UoW per HTTP command; external model/source/runner calls never execute inside a SQLite write transaction (spec §3.4).
  - Alembic single-head check on server startup and any offline tooling; forward-only expand/backfill/contract migrations; failed migration stops startup with a recoverable diagnostic (spec §4.8).
  - OpenAPI as source of truth; generated TypeScript client checked for drift in CI (spec §5.1).
  - `audit_events` append-only, rejecting UPDATE/DELETE via repository and SQLite trigger.
  - **Async-operation seam.** Define the `JobRef` response contract, the `202` enqueue shape, and a minimal `JobDispatcher` port with a synchronous in-process executor, so Phase 2–3 tickets can specify `202 JobRef` endpoints, enqueue-time dedupe and single-flight against a real abstraction. IDK-401 later replaces the executor and backing tables with the durable two-lane worker **without changing this contract**. The `jobs_events` module and its tables remain IDK-401's; Phase 2–3 modules use this port and never write job rows directly (spec §3.2 cross-module ORM rule).
- Out of scope:
  - Any specific module's business schema beyond the shared conventions (owned by IDK-102 through IDK-208 respectively).
  - OS/toolchain detection (IDK-005, Section 4).
- Data and invariants:
  - `owners`, `owner_role_grants` tables per spec §4.2.
  - Booleans as `INTEGER CHECK(value IN (0,1))`; timestamps UTC `TEXT`; IDs opaque `TEXT` UUID/ULID.
  - Foreign keys enabled on every connection (`PRAGMA foreign_keys=ON`).
  - Mutable aggregates carry `row_version`; PATCH/commands use `If-Match`/expected version.
- API/domain/event contracts:
  - Common API rules per spec §5.1: base path `/api/v1`, `Idempotency-Key` on mutating creates, `If-Match` on PATCH, standard error shape (`code`, `message`, `request_id`, `correlation_id`, `retryable`, ...), principal HTTP statuses (400/404/409/410/412/422/423/429/503/504).
- UX routes and states: None directly; this ticket has no route of its own but underlies every route's owner resolution.
- Implementation notes:
  - Enforce the dependency direction diagram in spec §3.2 with an automated architecture test (e.g., import-linting) rather than code review alone.
- Acceptance criteria:
  - A record written under owner A is unreachable through any repository call scoped to owner B.
  - Domain/application code contains no forbidden imports; CI fails if one is introduced.
  - Server and offline tooling both refuse to start against a non-head Alembic database.
  - Generated TypeScript client drift fails CI when the OpenAPI schema changes without regeneration.
  - `audit_events` rejects UPDATE/DELETE at the database layer.
  - A Phase 2–3 caller can enqueue through the `JobDispatcher` port, receive a `JobRef`, and observe single-flight/dedupe behavior without importing `jobs_events` ORM types; swapping the synchronous executor for IDK-401's durable worker requires no caller change.
- Minimum required tests:
  - Automated: (1) Domain/unit architecture test asserting no domain/application module imports FastAPI, SQLAlchemy ORM, subprocess, or FTS syntax (proves SYS-01/NFR-07); (2) a schema sweep asserting every table in the SQLAlchemy metadata outside an explicit allow-list carries `owner_id` (and `goal_id` where goal-owned) with the composite FK — re-run against the final schema at IDK-505; (3) SQLite repository/integration test proving owner-scoped isolation (a row owned by owner A cannot be read/written via owner B's UoW) and that `audit_events` rejects UPDATE/DELETE (proves DAT-01/NFR-03).
  - Manual: None beyond code review; the architecture test is self-verifying.
  - Existing coverage reused: None — the prototype has no server, persistence, or owner concept.
- Failure and recovery:
  - A migration failure stops server/tooling startup with a recoverable diagnostic; it never exposes a partially upgraded schema.
- Removal/replacement: None — this is net-new backend infrastructure; the prototype's `installNetworkTripwire` (`src/shared/network.ts`) is untouched by this ticket; its removal is owned by IDK-409, which replaces it with the PRV-01 disclosure gate.
- Approval gate:
  - None for this ticket's own acceptance.
- Estimate:
  - TBD; implementation team to estimate after approval.

### IDK-102 — Approval-gated offline canonical v1 publication

- Phase: 1 — MVP foundation
- Status: Complete
- Objective: Build the D1 offline seed/publish tool: no in-app authoring/publication UI or API; graph material plus `EditorialApproval` inserted last in one transaction; refusal of in-place mutation of any approved version; every read path gated on approval-record existence.
- User-visible outcome: A learner never sees a half-seeded or unapproved canonical graph; roadmap/topic/search reads are always backed by a fully approved version.
- PRD traceability: CUR-03 (primary), CNT-01 (primary), CUR-01 (primary), CUR-02 (primary)
- Appendix H decisions: D1
- Owning module: canonical
- Dependencies: IDK-101
- Scope:
  - Offline publisher checks Alembic head, validates manifest version/hash, stable IDs, curriculum tags, layer/checkpoint data, relationship references, prerequisite DAG, claim/citation shapes, and source statuses (spec §6.1 steps 1–2).
  - Verifies an explicit `designated_editorial_approver` grant before writing (spec §6.1 step 3).
  - Runs only against a stopped server or within one SQLite transaction; inserts version + all dependent material, then `EditorialApproval` last, then commits (spec §6.1 steps 4–5).
  - Failure rolls back everything; a version without approval is invisible to every catalog, topic, search, generation, roadmap, and diff read (spec §6.1 step 6).
  - Refuses in-place mutation/deletion of an already-approved version — corrections require a new version (spec §6.1 step 7).
  - Ships MVP fixtures: approved v1/v2, a half-seeded version, an invalid relation/cycle, an overlay conflict, and an upstream-deleted-topic-with-local-state fixture (spec §6.1 step 8).
  - **Module-boundary enforcement.** `canonical` is the first bounded context beyond IDK-101's cross-cutting `identity`/`audit_observability` foundation, so this ticket establishes the mechanism that enforces spec §3.3 module ownership and spec §3.2's "cross-module ORM mutation is forbidden" — an automated contract per module, alongside IDK-101's existing layer and framework-freeness contracts, asserting no module imports another module's ORM types or repositories. IDK-101 enforces the layer axis only; nothing yet enforces the module axis, and with 2 of 17 modules built there is no coupling to unwind. Every later module ticket adds its own contract rather than retrofitting the set.
  - **Write-transaction I/O boundary.** The publisher is the first component to run a long multi-step validation and a multi-table insert inside one atomic transaction, so this ticket establishes how spec §3.4's "external model, source and runner operations never execute inside a SQLite write transaction" is enforced rather than merely documented. IDK-101 leaves this as convention: a write held open across slow work locks out every other SQLite writer for the duration.
- Out of scope:
  - Any in-app authoring or publication UI/API (explicitly excluded by D1).
  - The actual MVP curriculum content (IDK-001).
  - Canonical v2 diff/merge acceptance flow (Section 4, IDK-407).
- Data and invariants:
  - `canonical_graph_versions`, `topic_identities`, `topics`, `topic_relations`, `content_revisions`, `editorial_approvals` per spec §4.3.
  - SQLite triggers reject UPDATE/DELETE on any graph/topic/relation/content/approval row belonging to an approved version.
  - `editorial_approvals.graph_version_id` is `UNIQUE`.
- API/domain/event contracts:
  - No canonical publication write endpoint exists in MVP (spec §5.1); reads only: `GET /canonical/versions`, `GET /canonical/versions/{id}` return approved versions only.
- UX routes and states: `/app/learn-roadmap`, `/app/topic-studio`, `/app/canonical-updates` show `unavailable` for any goal without an approved graph pin; canonical draft states `authored/curated/AI-draft → validation-failed/pending-approval → published (terminal, immutable) → superseded`.
- Implementation notes:
  - Reuse spec §9.1's state table rows for `Canonical draft`/`Canonical published` as the acceptance reference for state transitions.
  - Enforce module ownership with an automated contract, as IDK-101 does for layers, rather than by code review.
  - `migrations/env.py` resolves the database URL from the Alembic `Config` before falling back to process settings; the offline publisher must set it explicitly rather than relying on ambient configuration.
  - Any `batch_alter_table` on a table carrying append-only triggers drops them silently — recreate them in the same migration (see IDK-101's trigger-existence test).
- Acceptance criteria:
  - A half-seeded version (no approval row) is unreadable through every read path exercised by the fixtures.
  - Any UPDATE/DELETE attempt against an approved version's rows is rejected.
  - A validation failure (bad DAG, missing stable ID, out-of-boundary curriculum tag, DSA node without scenario relation, or a Go node) rolls back the entire publish transaction.
  - The two-version fixture (v1 → v2) is independently publishable and each remains immutable.
  - CI fails if any module imports another module's ORM types or repositories.
  - The publisher performs no external call while holding a write transaction.
- Minimum required tests:
  - Automated: (1) SQLite repository/integration test asserting a version without an `EditorialApproval` row is invisible through catalog/topic/roadmap/search read joins, and that a committed approval-last transaction is atomic (kill mid-transaction → nothing partial persists); (2) domain/property test for graph validation rejecting cycles, missing stable IDs, out-of-boundary curriculum tags, DSA-without-scenario-relation, and any Go node; (3) negative test asserting a publish attempt by an owner holding only the `learner` grant — with no `designated_editorial_approver` row in `owner_role_grants` — is rejected before any write, preserving the D1 role distinction that SAAS-01 depends on; (4) architecture test asserting the module-ownership contract catches a deliberate cross-module ORM import, proving the contract is not vacuous — the same self-test discipline IDK-101 applies to its layer contracts; (5) test asserting no write transaction stays open across an external call, exercised against the publisher's validation-then-insert sequence.
  - Manual: Editorial approver reviews the half-seed and immutability-trigger fixtures as part of the Phase 1 exit review.
  - Existing coverage reused: IDK-101's layer/framework-freeness import contracts and schema-convention sweep, both of which bind the new `canonical` tables automatically.
- Failure and recovery:
  - Publish failure rolls back completely; the prior published version (if any) remains the only visible one; no partial state is ever readable.
- Removal/replacement: None — net-new capability.
- Approval gate:
  - Production seeding of the real MVP spine additionally requires IDK-001 (curriculum content) and IDK-002 (approval criteria); this ticket's own mechanism acceptance does not require them.
- Estimate:
  - TBD; implementation team to estimate after approval.

### IDK-103 — Exact 14-route shell and not-found contract, backend-resolved

- Phase: 1 — MVP foundation
- Status: Complete
- Objective: Preserve the existing exact 14-route contract (`/`, `/app/onboarding`, `/app/learn-roadmap`, `/app/topic-studio`, `/app/interview-hub`, `/app/practice`, `/app/mock`, `/app/reports`, `/app/evidence`, `/app/imports`, `/app/canonical-updates`, `/app/search`, `/app/jobs`, `/app/settings`), `/app/$pageId` validation of the exact 13 page IDs, the shared shell, the not-found experience, and focused Mock outside the shell — now backed by the server-resolved local owner from IDK-101 instead of anonymous client-only state.
- User-visible outcome: Navigation, page structure, and the not-found experience remain exactly as approved; nothing about IA, terminology, or control placement changes.
- PRD traceability: CORE-01 (primary)
- Appendix H decisions: None.
- Owning module: frontend
- Dependencies: IDK-101
- Scope:
  - Keep `src/selected/app-model.ts`'s `APP_PAGE_IDS` (exactly 13 IDs) and `src/app/router.tsx`'s route tree unchanged.
  - Keep Refresher/Questions reachable only as `?mode=refresher`/`?mode=questions` query states of `/app/interview-hub`; no new canonical route.
  - Keep focused Mock (`/app/mock`) outside the ordinary global shell (no `GlobalHeader`/`CourseBand`).
  - Swap the shell's data source from `LearningStateProvider`'s localStorage reducer to TanStack Query hooks against the generated OpenAPI client, with `loading`/`empty`/`ready`/`stale`/`locked`/`unavailable`/`failure` view states per route per spec §2.1.
  - Apply the approved product name **Yuno**: `index.html`'s `<title>`, the header wordmark text and its `aria-label` (`src/selected/LearningApp.tsx`), `package.json`'s `name`, and the `data-app` hook (`lattice-learning` → `yuno-learning`), updating the `[data-app=...]` selector in `tests/e2e/selected-app.spec.ts` in the same change so the suite keeps passing. Layout, hierarchy, terminology and control placement are untouched — this is a copy and identifier change only.
- Out of scope:
  - Per-route business logic and data (owned by the module-specific tickets below).
  - Any new route, page ID, or navigation entry.
- Data and invariants:
  - `AppPageId` remains exactly the 13-member union in `src/selected/app-model.ts`.
- API/domain/event contracts: None new; this ticket wires existing routes to the OpenAPI client generated in IDK-101.
- UX routes and states: All 14 canonical routes; `/app/$pageId` not-found for any other value, linking to `/`.
- Implementation notes:
  - No redesign of navigation hierarchy, responsive model, terminology, or control placement (AGENTS.md / packet hard rule: selected app is the approved UX reference).
- Acceptance criteria:
  - All 14 routes render; `/app/$pageId` for any value outside the 13 IDs (including retired concept routes) renders the not-found view linking to `/`.
  - Focused Mock never renders `GlobalHeader`/`CourseBand`.
  - Refresher/Questions are reachable only via `?mode=` on `/app/interview-hub`.
  - No `lattice` or `Lattice` string survives in shipped source, markup, package metadata, or test selectors.
- Minimum required tests:
  - Automated: Playwright/component test covering the three acceptance criteria the existing suite does NOT reach — `/app/interview-hub?mode=refresher` and `?mode=questions` resolve as states of that one route (no new route registered, `APP_PAGE_IDS` unchanged), and `/app/mock` renders without `GlobalHeader`/`CourseBand` at all four viewports. The 14-route render and not-found behavior are already covered and are not duplicated.
  - Manual: None beyond the existing Playwright suite.
  - Existing coverage reused: `src/selected/app-model.test.ts` (13 page IDs, `appHref`/`isAppPageId` contract); `tests/e2e/selected-app.spec.ts` ("all 14 canonical routes render...", "unsupported and retired routes render the not-found view").
- Failure and recovery:
  - A failed data read on any route shows the route's `failure` state with retry, never a route-level crash; not-found is unaffected by backend errors.
- Removal/replacement: Replaces `navigateApp`'s hand-rolled `history.pushState` + synthetic `PopStateEvent` shim (`src/selected/app-model.ts`) with TanStack Router navigation (`router.navigate`/`<Link>`), since the locked stack names TanStack Router as the routing library. Also replaces the inherited `Lattice` wordmark, `<title>`, `package.json` name and `data-app` hook with the approved product name **Yuno**. `APP_PAGE_IDS`, the route tree and the not-found view are otherwise preserved unchanged; only the data source and the product name change (see IDK-107 for the localStorage scoping).
- Approval gate:
  - None for this ticket's own acceptance.
- Estimate:
  - TBD; implementation team to estimate after approval.

### IDK-104 — Global profile and multiple isolated goal workspaces

- Phase: 1 — MVP foundation
- Status: Complete
- Objective: Implement one global `learner_profiles` row per owner and N isolated `goal_workspaces`, with goal switch/resume/archive, `/` My learning states (empty/ready/stale/locked/unavailable), historical Resume kept separate from dismissible Recommended next, and audience/level labelling that excludes any beginner track.
- User-visible outcome: A learner can create more than one goal, switch between them without mixing progress, and see `/` reflect the currently selected goal's real state.
- PRD traceability: CORE-03 (primary), CORE-02 (primary)
- Appendix H decisions: None.
- Owning module: profiles_goals
- Dependencies: IDK-004, IDK-101, IDK-103
- Scope:
  - `learner_profiles` (global, not goal-scoped) and `goal_workspaces` (owner, name, path `learn/interview_prep`, subject/role, target level/capability, one graph pin, status, `row_version`).
  - Goal create, switch (set current goal), resume (historical Resume, distinct record/surface from Recommended next per spec §2.1), archive.
  - `/` states: empty (no goals → setup), ready/stale (goal cards + explanation), locked/unavailable (goal deleted/migration issue).
  - Target-level enum restricted to the PRD §3 tiers (Mid-level/Senior/Staff); no beginner-track option ever rendered (CORE-02 structural check).
  - Shared `role-competency-copy-v1` metadata from IDK-004 for onboarding and goal Settings: exact display labels/descriptions, audience/title-variation helper, independent capability helper, and explicit-confirmation/history behavior.
- Out of scope:
  - Goal delete mechanics, impact preview, and cross-goal evidence tombstoning (IDK-108).
  - Full export orchestration (Section 4, IDK-409).
- Data and invariants:
  - `goal_workspaces` per spec §4.4; index owner/status/recent; no goal mixes evidence or progress across goals (verified via repository-level isolation test).
- API/domain/event contracts:
  - `GET/PATCH /profile`; `GET/POST /goals`; `GET/PATCH /goals/{goalId}`; `POST /goals/{goalId}/archive` per spec §5.2.
- UX routes and states: `/` — `empty`/`ready`/`stale`/`locked`/`unavailable` per spec §2.2; `/app/settings` profile region reads/writes the global profile.
- Implementation notes:
  - Resume surfaces the learner's last saved position per goal; Recommended next is a separate, independently dismissible record — neither overwrites nor impersonates the other (spec §2.1).
- Acceptance criteria:
  - Two goals created by the same owner never leak each other's evidence/progress/overlay state when queried independently.
  - Switching the current goal changes what `/` and downstream routes render without losing the other goal's state.
  - No beginner-track option is ever rendered in onboarding, and the audience statement appears in onboarding's target-level step. CORE-02's "catalog labels" resolve to the canonical graph's curriculum scope-boundary tags surfaced on the roadmap and topic surfaces, which are owned and validated by IDK-102 under CUR-01 — this ticket does not introduce a separate catalog surface, and none exists among the 14 routes.
  - The exact `role-competency-copy-v1` label/description and title-variation helper for the selected level are programmatically associated with the control; goal Settings preserves the stable stored value while exposing the same copy.
- Minimum required tests:
  - Automated: Repository/integration plus component test proving two-goal isolation and asserting the exact approved heading, three stable values/labels, selected description and helpers, no beginner option, no first-use preselection, accessible association, invalid-value fail-closed behavior, no setup/goal persistence before explicit confirmation, and unchanged `Mid-level`/`Senior`/`Staff` request payloads.
  - Manual: None beyond the isolation test; audience/level labelling is verified structurally by the automated test plus IDK-004's manual approval of copy.
  - Existing coverage reused: None — the prototype models exactly one hardcoded course/goal with no isolation concept to reuse.
- Failure and recovery:
  - A migration or read failure for the currently selected goal surfaces `/` as `unavailable` with retry, never silently falls back to a different goal.
- Removal/replacement: Removes the prototype's single hardcoded `COURSE` fixture (`src/shared/model.ts`) as the only goal a learner can ever have, and deletes `src/shared/model.test.ts`, whose eleven-lesson/four-module assertions exist solely to pin that fixture and become meaningless once goals are server-persisted; replaced by server-persisted `GoalWorkspace` records with real multiplicity.
- Approval gate:
  - Copy policy is satisfied by `docs/decisions/IDK-004-role-level-competencies.md`, decision version 1.0; production activation requires the component and shipped-copy evidence listed there.
- Estimate:
  - TBD; implementation team to estimate after approval.

### IDK-105 — Persisted optional diagnostic/setup lifecycle

- Phase: 1 — MVP foundation
- Status: Complete
- Objective: Persist diagnostic sessions and answers as first-class entities (explicitly not `LearningState`), owner-scoped, surviving pause/refresh/restart; every optional step skippable; adaptive next-question selection from responses/confidence; optional Markdown/plain-text notes (Learn) or questions (Interview Prep) captured as untrusted seed.
- User-visible outcome: A learner can take, pause, resume, or skip a diagnostic without losing answered questions, and optionally paste notes/questions that are visibly untrusted until reviewed later in Imports.
- PRD traceability: ONB-01 (primary), ONB-02 (primary), D11 (primary, shared with IDK-107)
- Appendix H decisions: D11
- Owning module: diagnostics
- Dependencies: IDK-004, IDK-101, IDK-102, IDK-103
- Scope:
  - `diagnostic_sessions` (owner, captured approved graph, setup inputs, state, started/paused/expiry/failure, confirmed goal) and `diagnostic_answers` (owner/session, sequence, question ref, answer, confidence, adaptive-context version, timestamp, unique session/sequence, append-only).
  - States per spec Appendix D / §9.1: `not-started → in-progress/paused/skipped → roadmap-preview` (confirm is IDK-107), `failed` retryable preserving prior answers.
  - Adaptive next-question selection driven by prior responses/confidence against a versioned question set.
  - Persisted setup inputs include the explicit target level and independently selected target capability; the onboarding control renders `role-competency-copy-v1`, permits edits before preview/confirmation, and restores the exact saved choice after pause/reload.
  - Optional Markdown/plain-text notes/questions captured verbatim as untrusted seed, later handed to Imports (IDK-203) for review — never parsed or treated as truth here.
  - Every optional step (diagnostic itself, notes/questions) skippable without forcing retake.
- Out of scope:
  - The atomic goal-confirmation transaction (IDK-107).
  - Import parsing/mapping of the captured notes (IDK-203).
  - Concrete expiry duration for abandoned sessions (deferred to IDK-010; mechanism supports a configurable expiry, no value invented).
- Data and invariants:
  - `diagnostic_sessions`/`diagnostic_answers` per spec §4.4; sessions are explicitly not `LearningState` (Appendix A invariant).
  - No lost answers across pause/resume/restart; unique `(session_id, sequence)`.
- API/domain/event contracts:
  - `POST /diagnostics`; `GET/PATCH /diagnostics/{id}`; `POST /diagnostics/{id}/answers`; `GET /diagnostics/{id}/roadmap-preview` per spec §5.2 (preview itself is IDK-106's projector, invoked here).
- UX routes and states: `/app/onboarding` — `not-started → in-progress/skipped/paused → roadmap-preview`; failure preserves answers; cancel leaves a resumable draft.
- Implementation notes:
  - Diagnostic captures the approved graph version at session start (D11); this pin is what IDK-107's atomic confirmation later uses.
- Acceptance criteria:
  - Pausing mid-diagnostic and reloading resumes with all prior answers intact.
  - Skipping the diagnostic or the notes/questions step never blocks reaching roadmap-preview.
  - Adaptive next-question selection changes based on a prior answer's content/confidence in a reproducible way.
  - Target level and capability changes survive pause/reload and optional diagnostic skip; neither diagnostics nor imported text silently changes the learner-confirmed selection.
- Minimum required tests:
  - Automated: Domain/integration test asserting a paused/refreshed/restarted diagnostic session preserves every answer plus the explicit target-level/capability selections; editing both before confirmation persists the final explicit choice; and skipping any optional step reaches `roadmap-preview` without requiring retake. IDK-104 owns rendering the approved copy.
  - Manual: None beyond the automated test.
  - Existing coverage reused: None — the prototype's `onboarding.sourceMaterial` (`src/shared/state.tsx`) is a single localStorage string with no session/answer persistence to reuse.
- Failure and recovery:
  - A service failure during the diagnostic preserves all recorded answers and reports `failed` retryable rather than discarding progress.
- Removal/replacement: Removes the prototype's single `onboarding.sourceMaterial` string field with no diagnostic-session concept at all; replaced by persisted `diagnostic_sessions`/`diagnostic_answers`.
- Approval gate:
  - IDK-004 decision version 1.0 satisfies the role-copy policy; its UI evidence remains required. Concrete expiry/cleanup duration for abandoned sessions requires IDK-010; this ticket's own persistence/skip/resume acceptance does not require it.
- Estimate:
  - TBD; implementation team to estimate after approval.

### IDK-106 — Deterministic learner-controlled roadmap preview

- Phase: 1 — MVP foundation
- Status: Complete
- Objective: Implement the D2 deterministic roadmap projection — pinned approved graph + accepted overlay + explicit corrections — with pending proposals/conflicts as non-mutating annotations, topological sort with stable-ID lexicographic tie-break, goal scoping that never hides a transferred-evidence topic, and rejection with a visible reason for any order constraint that creates a cycle or violates an unmodified prerequisite. Full preview is available before goal creation with jump/skip/reorder/depth-override/correction, and recommendation is always shown separately from override.
- User-visible outcome: The learner sees the entire roadmap, can jump/skip/reorder/override depth/correct inferred state at any time (before or after goal creation), and rebuilds never silently reorder or hide anything.
- PRD traceability: ONB-03 (primary), CORE-05 (primary), LRN-01 (primary), DEP-01 (primary), D2 (primary)
- Appendix H decisions: D2
- Owning module: roadmap
- Dependencies: IDK-101, IDK-102
- Scope:
  - `RoadmapProjector` algorithm per spec §6.2: load all graph topics (never remove a transferred-evidence topic), apply accepted skip/depth/bridge/archive annotations without changing canonical rows, add approved learner order constraints to canonical prerequisite edges, reject any constraint creating a cycle or violating an unmodified prerequisite with a visible reason, topologically sort with stable-ID lexicographic tie-break, attach evidence/state/explanation/pending-proposal/conflict annotations, hash projection inputs into a projection version.
  - Usable both pre-goal (diagnostic roadmap-preview, IDK-105) and post-goal (`/app/learn-roadmap`).
  - `personal_overlays`/`overlay_entries` (order constraint, skip, depth types) per spec §4.4.
  - Recommendation (depth by goal/evidence) always rendered distinct from learner override; override persists across refresh (DEP-01).
- Out of scope:
  - Bridges and AI-generated overlay proposals (IDK-202).
  - Diagnostic session persistence (IDK-105) and atomic goal confirmation (IDK-107).
- Data and invariants:
  - `personal_overlays`, `overlay_entries` per spec §4.4; approved overlay order entries are additional precedence constraints layered atop canonical prerequisites.
  - Opening, refreshing, recommendation generation, and provider output cannot write the overlay (spec §6.2 closing invariant).
- API/domain/event contracts:
  - `GET /goals/{goalId}/roadmap`; `GET /goals/{goalId}/learning-states`; `POST /goals/{goalId}/corrections`; `POST /goals/{goalId}/order-constraints`; `POST /goals/{goalId}/skip-decisions`; `POST /goals/{goalId}/depth-overrides` per spec §5.2.
- UX routes and states: `/app/learn-roadmap` — `loading` (approved graph + goal read succeeds) → `ready`; `checkpoint-saved` on overlay write; `stale-canonical-version` when a newer graph exists (goal pin unchanged); topological-invalid order returns a visible rejection (spec §9.1).
- Implementation notes:
  - The projector must be a pure function of `(graph_version, overlay_entries, corrections)` — same inputs always yield the same order and annotations, proving determinism directly rather than by UI inspection.
- Acceptance criteria:
  - Reloading the roadmap with unchanged inputs always produces the same topic order.
  - A skip/depth/order/correction action never silently reverses a prior learner decision; every mutation requires explicit confirmation and is recorded as an append-only overlay entry.
  - An order constraint creating a cycle or violating an unmodified prerequisite is rejected with a visible reason and no partial write.
  - A topic carrying transferred evidence is never hidden by goal scoping.
- Minimum required tests:
  - Automated: Domain/property test proving the projector is a deterministic pure function of its inputs (same graph+overlay+corrections → identical order every run, including under randomized valid-topic-set permutations) and that ties in topological rank are broken by stable-ID lexicographic order specifically — a fixture with tied-rank topics whose insertion order differs from their stable-ID order must still emit stable-ID order, so a merely-deterministic-but-non-lexicographic tie-break fails and that any overlay mutation only occurs via an explicit append-only `overlay_entries` write — never as a side effect of read, refresh, or recommendation generation (this ticket is the primary owner of "deterministic roadmap / no silent mutation").
  - Manual: None beyond the automated property test.
  - Existing coverage reused: None — the prototype's `roadmapOrder`/`roadmap` reducer state (`src/shared/state.tsx`) is client-only with no topological validation or projection-version concept to reuse; the interaction pattern (Customize, Skip/Restore, depth/knowledge selects, reorder buttons) in `src/selected/core/CorePages.tsx` remains the approved UX reference.
- Failure and recovery:
  - A read failure preserves and displays the last accepted projection rather than an empty or default roadmap.
- Removal/replacement: Removes the prototype's client-only `roadmapOrder`/`roadmap` state computed and persisted purely in localStorage with no server-side topological validation; replaced by the server-side deterministic `RoadmapProjector`.
- Approval gate:
  - None for this ticket's own acceptance (uses fixture graphs); real curriculum content awaits IDK-001.
- Estimate:
  - TBD; implementation team to estimate after approval.

### IDK-107 — Atomic goal confirmation and first working production slice

- Phase: 1 — MVP foundation
- Status: Complete
- Objective: Implement the D11 atomic goal-confirmation transaction — one UoW creates the goal, its `LearningState`s, any preview-made overlay edits, and the diagnostic confirmation link, pinned to the graph version captured at diagnostic start — delivering the first end-to-end production slice (My learning → Onboarding → persisted diagnostic/setup → full roadmap preview → explicit goal confirmation → persisted My learning and roadmap), and remove the prototype's localStorage/legacy-hydration persistence now that the API-backed replacement works.
- User-visible outcome: Confirming a goal after onboarding reliably creates a real, persisted goal with its roadmap and diagnostic history — surviving reload, restart, and browser storage clearing — with no partial goal ever visible.
- PRD traceability: ONB-03 (contributing), D11 (primary)
- Appendix H decisions: D11
- Owning module: diagnostics (cross-module: profiles_goals, roadmap)
- Dependencies: IDK-101, IDK-102, IDK-103, IDK-104, IDK-105, IDK-106
- Scope:
  - `POST /diagnostics/{id}/confirm-goal`: one transaction creates `goal_workspaces` row, initial `learning_states` rows, preview-made `overlay_entries`, and the diagnostic-session-to-goal confirmation link, all pinned to the graph version captured at diagnostic start (spec §5.2, §6 D11).
  - `409` if already confirmed; `410` if the diagnostic session expired.
  - A newer graph version published meanwhile arrives later as an ordinary CUR-04 diff proposal (Section 4, IDK-407) — never silently applied here.
  - UoW rollback guarantees partial goal creation is impossible.
  - Remove `LEARNING_STORAGE_KEY`/`LEGACY_LEARNING_STORAGE_KEY` localStorage persistence, `hydrateLearningState`, legacy-key migration, and the client-side `APPROVE_ROADMAP` reducer action as the source of truth — replace with TanStack Query reads/writes against the real API.
- Out of scope:
  - The roadmap projection algorithm itself (IDK-106).
  - The diagnostic session/answer lifecycle itself (IDK-105).
  - Evidence transfer into a second goal (IDK-108).
- Data and invariants:
  - Confirmation is atomic per spec §3.4's mandatory-UoW list ("D11 goal confirmation: goal, initial LearningStates, preview overlay and diagnostic confirmation").
  - `diagnostic_sessions.confirmed_goal` set exactly once.
- API/domain/event contracts:
  - `POST /diagnostics/{id}/confirm-goal` per spec §5.2.
- UX routes and states: `/app/onboarding` `roadmap-preview → confirmed` (terminal); confirmed Learn exits to `/app/learn-roadmap`, confirmed Interview Prep exits to `/app/interview-hub`.
- Implementation notes:
  - This is the critical end-to-end proof gating Phase 1 exit; no other ticket may claim ownership of the atomic-confirmation invariant.
- Acceptance criteria:
  - Confirming a goal always results in either a fully created goal (goal + all LearningStates + overlay + confirmation link) or no created rows at all — never a partial set.
  - A simulated mid-transaction failure (e.g., overlay-edit write failure) leaves zero new rows.
  - The full slice — My learning → Onboarding → diagnostic → roadmap preview → confirm → persisted My learning/roadmap — works end to end against the real API with no localStorage involved.
  - The onboarding/diagnostic/roadmap slices (`onboarding`, `roadmap`, `roadmapOrder`, `currentLessonId`, `recommendationDismissed`) are no longer read from or written to `lattice.learning.state.v1`; they resolve exclusively through the API.
  - The legacy key `lattice.concept-b.learner-state.v1` and all of `hydrateLearningState`/`loadState`'s legacy-migration logic are deleted outright.
  - **Known, bounded persistence window:** `src/shared/state.tsx` persists roadmap, practice, mock, evidence and code drafts under one key, so the remaining `practice`, `mock`, `evidence`, `codeDraft` and `codeNotes` slices keep using `lattice.learning.state.v1` until IDK-204, IDK-302 and IDK-303 replace them. This ticket must not delete that key while those slices still read it; doing so would silently stop Practice/Mock/Evidence persisting for the rest of Phase 2. IDK-303 performs the final key deletion once the last slice is API-backed.
- Minimum required tests:
  - Automated: Integration test (UoW rollback) injecting a failure partway through the confirm-goal transaction and asserting the goal, its LearningStates, its overlay edits, and the diagnostic confirmation link are all absent afterward — no partial goal exists (this ticket is the primary owner of "atomic diagnostic confirmation").
  - Manual: None beyond the automated rollback test; the end-to-end slice is additionally covered by the replacement Playwright flow below.
  - Existing coverage reused: None — REPLACED. The prototype Playwright tests `selected application storage migrates once to neutral keys without losing learner state`, `partial legacy storage is deeply hydrated and copied forward without concept identity`, `valid neutral storage wins and does not consume legacy storage`, and `wrong legacy concept identity is ignored without deleting its payload` (`tests/e2e/selected-app.spec.ts`) assert legacy-hydration/localStorage-migration behavior this ticket removes; they are replaced by a new Playwright flow asserting the atomic API-backed confirm-goal slice survives reload with no localStorage dependency. `onboarding previews the full roadmap and requires explicit approval` is replaced by the same API-backed flow asserting `POST /diagnostics/{id}/confirm-goal` succeeds exactly once and is idempotent on retry (`409` on re-confirm).
- Failure and recovery:
  - Any failure during confirmation reports `failed` retryable and preserves the diagnostic session in `roadmap-preview` so the learner can retry without re-entering prior answers.
- Removal/replacement: Removes `LEGACY_LEARNING_STORAGE_KEY` and all legacy-key hydration/migration logic in `src/shared/state.tsx` (the `lattice.concept-b.learner-state.v1` path inside `loadState`/`hydrateLearningState`), the onboarding/roadmap slices of `LEARNING_STORAGE_KEY` persistence, and the client-side `APPROVE_ROADMAP` reducer as the source of truth for approval. `LEARNING_STORAGE_KEY` itself survives this ticket carrying only the practice/mock/evidence/code slices, and is deleted by IDK-303 once IDK-204/IDK-302/IDK-303 have replaced them; replaced by the server-persisted D11 atomic transaction and TanStack Query-backed reads.
- Approval gate:
  - None for this ticket's own acceptance.
- Estimate:
  - TBD; implementation team to estimate after approval.

### IDK-108 — Conservative evidence transfer and delete/tombstone effects

- Phase: 1 — MVP foundation
- Status: Complete
- Objective: Implement D5 — evidence is immutable and goal-scoped; cross-goal transfer creates fresh `LearningState` rows in the target goal referencing source evidence read-only with a classification, copying nothing and transferring no completion; deleting a source goal tombstones evidence referenced elsewhere (classification metadata retained, content dropped) and downgrades dependent states to `unverified` with an audit entry, shown as an impact preview before confirmation.
- User-visible outcome: Creating a second goal shows likely-known/partial/unverified/new classifications for relevant prior evidence (correctable, never hidden); deleting a goal shows exactly what will be tombstoned/downgraded before the learner confirms.
- PRD traceability: CORE-04 (primary), D5 (primary)
- Appendix H decisions: D5
- Owning module: evidence_evaluation, profiles_goals
- Dependencies: IDK-101, IDK-104
- Scope:
  - `evidence`, `evidence_payloads`, `evidence_tombstones`, `transferred_evidence_refs` schema per spec §4.5 (base tables; full assessment/rubric layer is IDK-204).
  - Transfer: creates a target `learning_states` row + `transferred_evidence_refs` row referencing source evidence read-only with a classification (`likely_known`/`partial`/`unverified`/`new`); nothing copied or mutated across goals; no completion transferred.
  - Delete: `POST /goals/{goalId}/delete-preflight` produces an immutable impact snapshot (which evidence tombstones, which dependent states downgrade); `POST /goals/{goalId}/delete` requires the unchanged snapshot, then atomically tombstones referenced evidence, downgrades dependent `learning_states` to `unverified`, and writes an audit event — all in one transaction.
- Out of scope:
  - The full evidence-submission/assessment pipeline (IDK-204).
  - Goal create/switch/archive mechanics (IDK-104).
  - Full export orchestration (Section 4, IDK-409).
- Data and invariants:
  - Evidence is immutable and append-only; the only "mutation" is the governed tombstone (record + payload removal) per spec §4.1.
  - Deleting a source goal never partially downgrades cross-goal state — all-or-nothing per the transaction (spec §3.4).
- API/domain/event contracts:
  - `POST /goals/{goalId}/delete-preflight`, `POST /goals/{goalId}/delete` per spec §5.2.
- UX routes and states: goal delete flow (reached from `/app/settings` in the full product; the tombstone/downgrade transaction is owned here, while the Settings-side preflight/confirm flow and the stale-snapshot rejection rule are owned and tested by IDK-409) — `Delete idle → delete-confirmation (preflight impact snapshot) → running → complete/failed`; changed impact after preflight requires a new preflight (spec §9.3).
- Implementation notes:
  - The impact preview must reflect exactly what the delete transaction will do — verified by asserting preview output equals post-delete effect in the same test.
- Acceptance criteria:
  - Transferring evidence into a new goal never copies evidence content or marks a topic complete; the source evidence remains unchanged.
  - Deleting a goal whose evidence is referenced elsewhere tombstones that evidence (metadata retained, content dropped) and downgrades every dependent `learning_states` row to `unverified`, atomically, with an audit event.
  - The delete-preflight impact snapshot exactly matches the post-delete effect.
- Minimum required tests:
  - Automated: Property/integration test asserting (1) transfer creates a read-only reference with a classification and copies zero evidence content/completion, and (2) deleting a goal whose evidence is cross-referenced atomically tombstones that evidence, downgrades every dependent state to `unverified`, and writes exactly one audit event — with the delete-preflight snapshot equal to the realized effect (this ticket is the primary owner of "conservative transfer/delete/tombstones").
  - Manual: None beyond the automated test.
  - Existing coverage reused: None — the prototype has no multi-goal or transfer concept to reuse.
- Failure and recovery:
  - A failure during delete rolls back entirely — no partial cross-goal downgrade is ever left behind (spec §9.3 "No partial cross-goal downgrade").
- Removal/replacement: None — the prototype models a single implicit goal with no transfer/delete concept; this is net-new capability.
- Approval gate:
  - None for this ticket's own acceptance; full export/delete UI orchestration and retention guarantees additionally require IDK-010.
- Estimate:
  - TBD; implementation team to estimate after approval.

## 2. MVP learning and evidence

These eight tickets deliver self-contained topic layers, learner-approved overlay/bridge proposals, untrusted import mapping, immutable evidence and evaluation, deterministic derived progress, the goal notebook and optional review queue, the generated-content cache contract, and learner-readable Evidence/Reports surfaces — replacing the prototype's regex-based fixture scoring and static hardcoded lesson copy.

### IDK-201 — Self-contained approved topic layers and roadmap return

- Phase: 2 — MVP learning and evidence
- Status: Complete
- Objective: Deliver the self-contained topic workspace with the eight approved layers (Essential, Implementation, Internals, Production, Alternatives, Failures, Interview, Sources), a topic-attached conversation, always-reachable roadmap return without losing context, and problem-first checkpoints naming scenario, target capability, expected artifact, a 30–60 minute session range, rubric and assumptions, an evidence criterion, and a material static/runtime limitation, with every revealed layer accurate on its own (a later layer refines, never reverses).
- User-visible outcome: Opening any topic shows everything needed to work it without hidden prerequisite navigation, and the roadmap is always one action away.
- PRD traceability: LRN-02 (primary), LRN-03 (primary), DEP-02 (primary), DEP-03 (primary)
- Appendix H decisions: None.
- Owning module: learning_content
- Dependencies: IDK-101, IDK-102, IDK-103, IDK-106, IDK-107
- Scope:
  - `GET /topics/{topicId}?graph_version=`, `GET /goals/{goalId}/topics/{topicId}/layers`, `GET /goals/{goalId}/topics/{topicId}/layers/{layer}` reading approved graph/content only.
  - Checkpoint contract fields: scenario + role-appropriate constraints, target capability, expected artifact/code/design/decision, estimated 30–60 minute session range, rubric and assumptions, evidence criterion, material static/runtime limitation (spec §7.1).
  - Topic-attached conversation (thread scoped to the topic).
  - `/app/topic-studio` always offers a return-to-roadmap control that preserves context (LRN-01 contributing).
- Out of scope:
  - Live AI content generation (Section 4, IDK-404) and the generated-content cache/staleness contract (IDK-207) — this ticket consumes whatever `generated_artifacts`/authored `content_revisions` exist, it does not produce them.
  - The Java runner (Section 4, IDK-406).
  - Overlay/bridge proposals (IDK-202).
- Data and invariants:
  - `content_revisions` per spec §4.3 (immutable, unique graph/topic/layer/hash).
  - `topics.target_capability` and every checkpoint's target capability are constrained by a `CHECK` to exactly the six capability-ladder values `know`, `understand`, `choose`, `implement`, `diagnose`, `defend` (spec §7.1) — an arbitrary capability string cannot be persisted (LRN-03).
  - DEP-03: a later layer must refine, never reverse, an earlier layer's mental model — enforced by a curated content regression fixture set.
- API/domain/event contracts:
  - `POST /goals/{goalId}/topics/{topicId}/generate`, `POST /artifacts/{id}/regenerate` return `202 JobRef` (invocation only; the job pipeline itself is IDK-207/Section 4).
- UX routes and states: `/app/topic-studio` — layer `loading`/`empty`/`stale`/`unavailable`; generated-before-correction staleness offers explicit regenerate (consumed from IDK-207); static and runtime results are visually distinct.
- Implementation notes:
  - Preserve the selected app's topic-studio interaction pattern (`src/selected/core/CorePages.tsx` `Topic`/`TopicTools`/`Classroom`) — persistent rail on desktop, focus-trapped drawer on mobile, tabs for notes/resources/help — as the approved UX reference; only the data source and content authority change.
- Acceptance criteria:
  - A topic can be understood and worked without navigating away for hidden prerequisites.
  - Every checkpoint response includes all seven required fields (scenario, capability, artifact, session range, rubric/assumptions, evidence criterion, limitation).
  - A curated fixture set with a deliberately reversing later layer fails the DEP-03 regression check.
- Minimum required tests:
  - Automated: Domain/content regression + schema-validation test asserting (1) every checkpoint response carries all seven required fields with `target_capability` drawn from the six-value capability ladder and a non-empty evidence criterion and 30–60 minute session range (proves LRN-03 and DEP-02), and (2) a curated set of layer-pair fixtures never has a later layer contradict an earlier one's mental model (only refine) — the exact evidence named for DEP-03 in spec §10.2 ("Content fixtures reject explanations whose later layer reverses rather than refines").
  - Manual: Editorial content reviewer performs the DEP-03 reversal-regression review referenced in spec §10.2 (gate G2/G3) for real authored content.
  - Existing coverage reused: Component-level interaction pattern from `tests/e2e/selected-app.spec.ts` ("Topic Studio Run is exploratory and Submit alone appends evidence", keyboard flow assertions for Notes/Resources/Help tabs) is reused for the shell interaction; the underlying `LESSON_CONTEXT` static copy is not reused (see Removal/replacement).
- Failure and recovery:
  - A layer read failure shows `unavailable` with retry while the rest of the topic workspace (other layers, conversation, notebook) remains usable.
- Removal/replacement: Removes the prototype's hardcoded `LESSON_CONTEXT` per-lesson copy object and the static reading section in `Topic` (`src/selected/core/CorePages.tsx`, `src/shared/model.ts`); superseded as the source of truth by server-served `content_revisions`/`generated_artifacts` content (IDK-207), though curated static content may remain a legitimate authored `content_revisions` source once IDK-001/IDK-002 approve real curriculum.
- Approval gate:
  - Real authored/curated content for the approved MVP spine additionally requires IDK-001 and IDK-002; this ticket's workspace-contract acceptance uses fixture content and does not require them.
- Estimate:
  - TBD; implementation team to estimate after approval.

### IDK-202 — Explicit recommendations and bridges through overlay proposals

- Phase: 2 — MVP learning and evidence
- Status: Complete
- Objective: Restrict AI/adaptation to writing `OverlayProposal` records pinned to the graph version they were generated against, revalidated at acceptance and rejected with a visible reason if stale, applied in a single transaction, deduplicated by content hash while pending, and capped per goal; bridges carry why/relationship/proposed placement and are add/postpone/dismiss with append-only decision history — nothing is added silently.
- User-visible outcome: A learner sees every gap/bridge/recommendation as an explicit, explainable proposal they can accept, postpone, or dismiss; nothing changes their plan without that action.
- PRD traceability: LRN-04 (primary), GAP-01 (primary), GAP-02 (primary), CNT-02 (primary), D2 (contributing)
- Appendix H decisions: D2, D3
- Owning module: roadmap
- Dependencies: IDK-106
- Scope:
  - `overlay_proposals` (owner/goal, generated-against graph, topic, type, payload/hash, state/reason/timestamps); partial unique pending `(goal_id, content_hash)`; configurable pending cap (value TBD, see Data and invariants).
  - `POST /goals/{goalId}/overlay-proposals`; `POST /overlay-proposals/{id}/decision`; `POST /bridges/{id}/decision` per spec §5.2.
  - Acceptance revalidates the proposal's pinned graph version against the goal's current pin; `409 proposal_stale` with a visible reason if mismatched; otherwise applies atomically as one or more `overlay_entries`.
  - Bridge proposals carry why, relationship, and proposed placement (GAP-01); decisions (add/postpone/dismiss) are append-only with reason if supplied (GAP-02).
  - Adaptive emphasis/examples/exercises flow only through this proposal/recommendation channel and the review channel (IDK-206) — never by rewriting cached lesson bodies (LRN-04/D3 boundary, enforced jointly with IDK-207).
- Out of scope:
  - The roadmap projection algorithm itself (IDK-106, already the primary owner of no-silent-mutation).
  - Live AI generation of the proposal content (Section 4, IDK-404) — this ticket accepts proposals from any source (fake adapter in tests) and governs their lifecycle.
  - Generated-content cache/staleness (IDK-207).
- Data and invariants:
  - `overlay_proposals` per spec §4.4; pending-cap value is TBD and configurable, not invented here (folds under IDK-010's size/retention scope); the cap-rejection mechanism itself is fully testable at any placeholder cap.
- API/domain/event contracts:
  - `GET /goals/{goalId}/overlay-proposals`; `POST /goals/{goalId}/overlay-proposals`; `POST /overlay-proposals/{id}/decision`; `POST /bridges/{id}/decision` per spec §5.2.
- UX routes and states: `/app/learn-roadmap` — bridge `proposed → accepted/postponed/dismissed`; overlay `awaiting → accepted` (stale → `rejected-stale`) per spec §9.1.
- Implementation notes:
  - Two proposals with identical `(goal_id, content_hash)` while pending must collapse to one (dedupe), verified by the acceptance test below.
- Acceptance criteria:
  - No proposal is ever applied without an explicit learner decision.
  - A proposal pinned to a graph version older than the goal's current pin is rejected at acceptance with `409 proposal_stale` and a visible reason, never silently applied against the new graph.
  - A duplicate pending proposal (same goal, same content hash) is deduplicated rather than creating a second pending row.
  - A bridge decision (add/postpone/dismiss) is recorded append-only, never overwriting a prior decision.
- Minimum required tests:
  - Automated: Domain/integration test for the overlay-proposal accept transaction — proposal pinned to graph version N, goal moved to version N+1, acceptance attempt returns `409 proposal_stale` with a visible reason and applies nothing; a second proposal with an identical content hash while the first is pending is rejected/deduplicated rather than duplicated; and, at a configured placeholder cap of N, the N+1th pending proposal for a goal is rejected with visible feedback rather than accepted (the cap's production value is IDK-010's, the rejection path is proven now).
  - Manual: None beyond the automated test.
  - Existing coverage reused: None — the prototype has no bridge/proposal concept; "Recommended next" in `src/selected/core/CorePages.tsx` `Home` is a client-computed suggestion with a dismiss action, which remains the approved UX reference for the "explainable, dismissible" interaction pattern only, not for its data source.
- Failure and recovery:
  - A failed acceptance transaction leaves the proposal `awaiting-learner-decision` and the roadmap unchanged.
- Removal/replacement: None — bridges/overlay proposals are net-new; nothing in the prototype implemented this mechanism.
- Approval gate:
  - The pending-cap numeric value requires IDK-010; this ticket's cap-rejection mechanism is testable at any placeholder value without it.
- Estimate:
  - TBD; implementation team to estimate after approval.

### IDK-203 — Untrusted import review and existing-topic-only mapping

- Phase: 2 — MVP learning and evidence
- Status: Complete
- Objective: Implement D10 — original preserved exactly with hash; parsed asynchronously into ordered untrusted statements with parser provenance; normalized dedupe; unmapped statements never auto-create topics or expand curriculum scope; mapping targets only an existing canonical topic in the goal's approved graph; learner may correct, map, verify as their own assertion, or dismiss; mapping changes the per-topic imports hash and surfaces D3 staleness; graph adoption reprocesses unmapped statements; imports never become canonical truth, evidence, or completion.
- User-visible outcome: Pasted notes/questions remain visibly untrusted, are never silently absorbed into the curriculum, and the learner explicitly decides what — if anything — each statement means for their goal.
- PRD traceability: IMP-01 (primary), IMP-02 (primary), D10 (primary)
- Appendix H decisions: D10
- Owning module: imports
- Dependencies: IDK-101, IDK-102, IDK-105
- Scope:
  - `import_records` (owner, optional goal, type, original content ref/hash, parser version, status, timestamps/failure) — original immutable and inspectable.
  - `import_statements` (owner/import, sequence, original/normalized hash, parsing confidence as metadata only, trust and mapping states, corrected text, timestamps); identical unmapped hashes deduplicated per owner/version.
  - `import_statement_mappings` (owner/goal/statement, existing topic, graph version, decision type, accepted/revoked timestamps).
  - `POST /imports`; `GET /imports/{id}`; `POST /imports/{id}/parse`; `GET /imports/{id}/statements`; `PATCH /import-statements/{id}`; `POST .../map`; `POST .../verify`; `POST .../dismiss`; `POST /imports/{id}/reprocess` per spec §5.2.
  - Mapping succeeds only against an existing topic in the goal's currently pinned approved graph; attempting to map to a nonexistent/out-of-scope topic is rejected.
  - Approved mapping changes the per-topic imports hash and surfaces the D3 staleness indicator on affected generated artifacts (consumed by IDK-207).
  - Graph adoption (accepting a canonical merge, Section 4 IDK-407) reprocesses previously unmapped statements.
- Out of scope:
  - Import origination from onboarding notes/questions capture (IDK-105, which hands the raw text to this ticket for parsing).
  - Canonical merge/diff acceptance itself (Section 4, IDK-407) — this ticket only reacts to a new graph version by reprocessing.
  - The generated-content cache/staleness mechanism itself (IDK-207) — this ticket only emits the hash change that triggers it.
- Data and invariants:
  - Imports never create topics, expand curriculum scope, become canonical truth, become evidence, or establish completion (spec §6.6 step 8, Appendix A).
  - **Atomic UoW (spec §3.4):** an approved mapping decision and the resulting per-topic imports-hash invalidation commit in ONE transaction, so no state exists where a mapping is approved but the D3 staleness signal IDK-207 consumes has not been written (or the reverse).
  - Original content is immutable once created (spec §4.7).
- API/domain/event contracts:
  - As listed in Scope, per spec §5.2 "Imports" group; parse/reprocess return `202 JobRef`.
- UX routes and states: `/app/imports` — `selected → parsing → parsed-untrusted → learner-review → applied/failed/cancelled`; unmapped and duplicates remain inspectable; mapping to a nonexistent topic is rejected (spec §9.1).
- Implementation notes:
  - Preserve the selected app's `ImportsPage` interaction pattern (`src/selected/operations/OperationalPages.tsx`) — original preserved verbatim, per-statement decision chips, correction textarea, topic-mapping select — as the approved UX reference; only the parser, mapping-target set, and persistence layer change.
- Acceptance criteria:
  - The original import text is always retrievable byte-for-byte via its hash.
  - No unmapped statement ever creates a topic or appears as canonical content anywhere.
  - Mapping to a topic outside the goal's approved graph is rejected.
  - Approving a mapping updates the per-topic imports hash and the affected artifact shows a staleness indicator.
  - Identical unmapped statements (by normalized hash) are deduplicated rather than listed twice.
- Minimum required tests:
  - Automated: Domain/property test asserting (1) mapping a statement to a nonexistent or out-of-graph topic is rejected and creates no topic, (2) two statements with identical normalized hashes are deduplicated per owner, and (3) approving a mapping changes the per-topic imports hash in a way IDK-207's cache-key computation observes as a staleness trigger (this ticket is the primary owner of "import mapping").
  - Manual: None beyond the automated test.
  - Existing coverage reused: None — REPLACED. `parseImport` (`src/selected/operations/OperationalPages.tsx`) is a client-only regex line-splitter with a hardcoded 3-option topic `<select>` and pure-localStorage decisions; it is replaced by server-side async parse jobs and mapping against the real approved graph. The Playwright test `parsed imports remain personal untrusted material and cannot create evidence or completion` is replaced by an equivalent flow against the real `/imports` API asserting the same untrusted/no-evidence/no-completion invariant.
- Failure and recovery:
  - A parse failure leaves the original import intact and reports `failed` retryable; statements already reviewed before a later reprocess are not silently discarded.
- Removal/replacement: Removes the prototype's client-only `parseImport` regex splitter and the `OperationsState.importStatements` localStorage array with a hardcoded 3-topic mapping target; replaced by server-side async parse jobs and `import_statements`/`import_statement_mappings` mapping against the real approved graph.
- Approval gate:
  - None for this ticket's own acceptance.
- Estimate:
  - TBD; implementation team to estimate after approval.

### IDK-204 — Immutable evidence, evaluations, disputes, and re-evaluation

- Phase: 2 — MVP learning and evidence
- Status: Content incomplete — the schema, the version gate and the evaluation domain ship and are tested, but the three immutable IDK-009 v1 rubric manifests this ticket's Scope requires loading (`hands-on-rubric-v1`, `practice-rubric-v1`, `mock-rubric-v1`) exist nowhere outside `docs/`, and `rubrics`/`rubric_dimensions` hold zero rows. IDK-503 re-run finding B11, `docs/approvals/IDK-503-content-and-safety-review-rerun-2026-08-15.md`.
- Objective: Deliver immutable, append-only evidence and assessments; visible rubric dimensions and assumptions; acceptance of multiple valid solutions; append-only disputes; re-evaluation that creates a successor and marks the predecessor excluded-from-derivation while preserving history; unresolved ambiguity that carries no readiness penalty.
- User-visible outcome: Submitting an artifact/answer produces a real, permanent evidence record with rubric-based feedback; disputing it never erases the original, and re-evaluation adds a new result rather than overwriting.
- PRD traceability: EVAL-01 (primary), EVAL-02 (primary)
- Appendix H decisions: D6 (contributing — "AI output becomes an input only after schema validation records it as evidence").
- Owning module: evidence_evaluation
- Dependencies: IDK-101, IDK-102, IDK-108
- Scope:
  - `rubrics`, `rubric_dimensions`, `assessments`, `assessment_dimension_results`, `assessment_disputes`, `reevaluation_requests` per spec §4.5, layered on IDK-108's `evidence`/`evidence_payloads` base.
  - Load and version-gate the three immutable IDK-009 v1 rubric manifests and persist the exact approved `topic_binding_key → canonical topic stable ID` mapping after IDK-102 publishes the IDK-001-approved graph.
  - Approved assessment metadata from IDK-009 v1: immutable scenario ID/content revision, assessment phase, conditionally required paired-initial reference, ambiguity-policy version, five-outcome dimension vocabulary, and normalized per-dimension ambiguity records with same-scope carried-result references.
  - `POST /goals/{goalId}/evidence` (immutable create); `GET .../evidence`; `GET /evidence/{id}`; `POST .../assess`; `GET /assessments/{id}`; `POST .../disputes`; `POST .../reevaluate` per spec §5.2.
  - Evaluation accepts multiple valid solutions when assumptions/consequences are defensible; feedback separates factual corrections from trade-offs (EVAL-01).
  - Dispute appends a reason; re-evaluation creates a successor `assessments` row and marks the predecessor `derivation_excluded=true` in one UoW, preserving both (EVAL-02).
  - Evidence submission itself (`POST /goals/{goalId}/evidence`) creates the immutable metadata + payload row that IDK-108's transfer/tombstone mechanics reference read-only from other goals.
- Out of scope:
  - Evidence transfer/delete/tombstone mechanics (owned by IDK-108).
  - The deterministic derived-state computation that consumes assessments (IDK-205).
  - Live provider-backed evaluation invocation (Section 4, IDK-404) — this ticket's evaluation pipeline is exercised against a fake/schema-validated adapter in tests; real invocation ships later without changing this contract.
  - Rubric/scenario content itself (IDK-009).
- Data and invariants:
  - Evidence and assessments are immutable; the only lifecycle event is append (new evidence, new assessment, new dispute, new re-evaluation successor) — never UPDATE/DELETE, enforced by repository and SQLite trigger.
  - `assessments.derivation_excluded` is the only field a re-evaluation ever sets on a predecessor; its text/result never changes.
  - Unresolved ambiguity (`ambiguity-unresolved` state) carries zero readiness penalty by construction — verified jointly with IDK-205.
  - Every authoritative assessment uses an approved scenario/rubric pairing whose role, phase, capability and content revision match; fixture/unapproved rows are rejected rather than treated as production content.
  - Capability matching is exact-only. A delayed assessment requires a paired initial assessment; every other phase forbids one. The pair must be earlier, eligible, and match owner, goal, mapped topic, capability, and the registry-declared initial scenario.
  - Each ambiguous dimension records cause, competing interpretations, resolution needed, and the immutable pre-attempt effective clear dimension-result reference (or explicit null); an ambiguity never makes prior evidence newer.
- API/domain/event contracts:
  - `EvaluationRequest`/`EvaluationResult` per spec §5.3 plus IDK-009 v1 scenario/revision/phase/pair and normalized ambiguity fields: dimension outcomes (`pass`, `trade-off`, `factual-correction`, `not-demonstrated`, `ambiguity-unresolved`), rationales, facts, trade-offs, citations, ambiguities, feedback, cross-question candidate, revision invitation, warnings/limitation labels.
  - Evaluation/re-evaluation return `202 JobRef`; assess/reevaluate endpoints per spec §5.2.
- UX routes and states: `/app/practice` `evaluating → feedback-ready/failed-recoverable`; `/app/evidence` assessment `feedback-ready → disputed → re-evaluating → feedback-ready/ambiguity-unresolved/failed` per spec §9.2.
- Implementation notes:
  - A fake adapter satisfying the `EvaluationResult` schema is sufficient for this ticket's tests; no live provider call is required or permitted here (NFR-09).
- Acceptance criteria:
  - Every assessment is retrievable forever once created; no endpoint can modify or delete one.
  - Two structurally different but defensible answers to the same prompt both receive passing dimension outcomes when their assumptions are stated and consistent.
  - Disputing an assessment never alters the original; re-evaluating creates a new assessment row, marks the old one `derivation_excluded=true`, and both remain queryable.
  - An `ambiguity-unresolved` assessment produces no readiness deduction (verified against IDK-205's function).
  - A mixed assessment preserves its clear dimensions while every ambiguous dimension resolves to its recorded pre-attempt carry; an all-ambiguous assessment leaves assessed, correction-only, and transfer-only baselines exactly unchanged.
- Minimum required tests:
  - Automated: Domain/property test asserting re-evaluation always creates a successor assessment and marks exactly the immediate predecessor `derivation_excluded=true` in one transaction, with both rows still readable afterward and no evidence or assessment ever mutated in place; the same suite rejects scenario/rubric/mapping/capability mismatches and every invalid delayed-pair relation, validates all five outcomes including omitted-but-not-false `not-demonstrated`, accepts the curated alternatives while correcting each near miss, and proves mixed/all-ambiguous carried-result scope and neutrality over assessed/correction/transfer baselines (with IDK-205 owning aggregate outputs).
  - Manual: Content/assessment reviewer validates the "multiple valid solutions accepted" behavior against the curated valid-alternative cases approved by IDK-009 decision version 1.0.
  - Existing coverage reused: None — REPLACED. The prototype's `evaluateCode` regex-based static-check function and `practiceFeedback` regex-based feedback generator (`src/shared/state.tsx`) are deterministic fixture logic standing in for real evaluation; they are replaced by the schema-validated `EvaluationResult` contract, testable here against a fake adapter. The Run-versus-Submit invariant asserted by `src/shared/state.test.ts`'s `keeps exploratory Run separate from evidence-producing Submit` is re-homed to IDK-405, which owns evidence creation on Submit; this ticket does not duplicate it.
- Failure and recovery:
  - A failed evaluation job leaves the evidence record intact and reports `failed` on the assessment path; retry is cache-checked per D4/D8 (Section 4) and never double-charges or duplicates an assessment.
- Removal/replacement: None directly. This ticket supplies the schema-validated `EvaluationResult`/`assessments` domain contract that replaces the prototype's regex-based fixture scoring, but the deletions themselves are owned elsewhere — `practiceFeedback` by IDK-302, and `evaluateCode`/`SIMULATION_LIMITATION` by IDK-405.
- Approval gate:
  - The production rubric dimensions, scenario matrix, and ambiguity policy are approved by IDK-009 decision version 1.0; activation still requires the approved-content and ambiguity carry-forward evidence named there. Authoritative learner-facing factual corrections additionally remain blocked until IDK-003's approved source/citation posture is implemented; synthetic-source mechanism tests may proceed.
- Estimate:
  - TBD; implementation team to estimate after approval.

### IDK-205 — Deterministic derived progress with explicit now

- Phase: 2 — MVP learning and evidence
- Status: Complete
- Objective: Implement D6 — a server-side deterministic function `f(eligible evidence, learner corrections/confirmations, explicit now, rule version)` computing coverage, proficiency, retention, and readiness; corrections are first-class inputs recomputation never silently reverses; `now` is explicit because retention decays; per-goal memoization is invalidated in the same transaction as evidence appends; responses carry definitions, supporting evidence, uncertainty, and rule version; exactly four inferred states (likely known, partial, unverified, new), never inferred completion; detailed/simple is presentation-only and deletes nothing; dismissed/disabled reviews carry no penalty; the production policy is `derived-state-v1` from IDK-009 decision version 1.0.
- User-visible outcome: Progress always reflects real evidence and the learner's own corrections, never silently reverts a correction, and is explicit about what "now" means when retention is involved.
- PRD traceability: PRG-01 (primary), PRG-02 (primary), D6 (primary)
- Appendix H decisions: D6
- Owning module: evidence_evaluation
- Dependencies: IDK-101, IDK-108, IDK-204
- Scope:
  - `learner_corrections` (owner/goal/topic, correction/confirmation/gap/transfer-confirmation, value, reason, timestamp, supersession — append-only first-class D6 input) and `goal_progress_memos` (goal PK, coverage/proficiency/retention/readiness, explanation JSON, input hash, derivation version, explicit computed-at) per spec §4.4/§4.5.
  - `DerivedStateService.f(evidence, corrections, now, rule_version)` — pure, deterministic, recomputed on read with per-goal memoization invalidated in the same transaction as any evidence append or correction write.
  - `GET /goals/{goalId}/progress?now=`; `GET /goals/{goalId}/learning-state-explanations` per spec §5.2 — server chooses authoritative clock unless a test-only clock port is injected; response records effective `now` and rule version.
  - Exactly four classification states (`likely_known`/`partial`/`unverified`/`new`) on `learning_states`; never a completion flag.
  - Detailed/simple display is presentation-only — simple mode never deletes underlying data (consumed by IDK-208's UI).
- Out of scope:
  - Authoring or approving derived-state policy — `derived-state-v1` is owned by IDK-009. This ticket implements and activates it after the section 11 evidence in the decision artifact passes.
  - Evidence/assessment creation itself (IDK-204).
  - Review dismiss/disable UI (IDK-206) — this ticket only guarantees the zero-penalty invariant the review module must respect.
- Data and invariants:
  - Corrections override inference until explicitly superseded by a later correction — recomputation never silently discards a standing correction (D6).
  - `goal_progress_memos` is a cache only, always recomputable from source rows; never a source of truth.
  - Detailed/simple never deletes data (PRG-01).
  - Cell outcome selection, correction/transfer semantics, coverage/proficiency/retention/readiness aggregation, and UTC-date timing follow `derived-state-v1` exactly; no implementation-local score or threshold exists.
- API/domain/event contracts:
  - `GET /goals/{goalId}/progress?now=`, `GET /goals/{goalId}/learning-state-explanations` per spec §5.2; response fields include definitions, supporting evidence references, uncertainty, and `rule_version`.
- UX routes and states: `/app/evidence`, `/app/reports`, `/app/settings` (progress-display setting) consume this; states are presentation-only, not lifecycle states of this service itself.
- Implementation notes:
  - `ClockPort` is injectable in tests to make "explicit now" deterministic without wall-clock flakiness.
- Acceptance criteria:
  - Calling `f` twice with identical evidence/corrections/now/rule_version always returns identical output.
  - A learner correction is never silently reversed by a later recomputation unless a newer correction explicitly supersedes it.
  - Advancing `now` alone (no new evidence) can change retention-derived values but never fabricates new evidence.
  - A dismissed or disabled review item produces zero change to readiness/coverage/proficiency/retention.
  - No classification other than the four allowed states is ever returned; no field represents "completion."
- Minimum required tests:
  - Automated: Domain/property test proving `f` is a pure deterministic function of `(evidence, corrections, now, rule_version)` — randomized input order with fixed replay reproduces identical output; newest-clear-per-dimension ordering resolves contradictions; mixed/all ambiguity has the approved carried/zero delta; corrections and transfers follow their distinct rules; retention aggregates per required cell at the 7th, 90th and 91st UTC-date boundaries; memo hashes roll at those date boundaries; a correction is never reversed unless explicitly superseded; and detailed/simple toggling leaves stored evidence/assessments/memos byte-identical. IDK-206 owns dismissed/disabled-review zero delta.
  - Manual: None beyond the automated test; policy approval is recorded under IDK-009 and shipped-artifact review remains IDK-503 work.
  - Existing coverage reused: None — the prototype never computes derived progress at all; its roadmap `learnerState` dropdown (`src/shared/state.tsx`) is a directly user-set field with no derivation, which this ticket supersedes by treating that same value as one correction input among several, not the entire state.
- Failure and recovery:
  - A memo-invalidation failure falls back to recomputing directly from source rows on the next read rather than serving a stale cached value.
- Removal/replacement: Supersedes the prototype's roadmap `learnerState` dropdown as the sole source of all progress dimensions. The persisted learner correction remains the exact displayed-state override until explicitly superseded, while coverage/proficiency/retention/readiness are deterministically derived under its approved correction semantics.
- Approval gate:
  - Satisfied by `docs/decisions/IDK-009-assessment-and-derived-state.md`, decision version 1.0; output must remain explicitly non-authoritative until its section 11 activation evidence passes.
- Estimate:
  - TBD; implementation team to estimate after approval.

### IDK-206 — Goal notebook and optional review/retrieval

- Phase: 2 — MVP learning and evidence
- Status: Complete
- Objective: Deliver one notebook per goal with entries labelled auto or user and optional topic/evidence/source links, plus an optional non-blocking review queue with retrieval, spacing, interleaving, and context variation; per-goal enable/disable and duration/cadence/type tuning; recall/explanation/application required before reveal; attempts record response, optional confidence, feedback/correction, next interval, and later varied-context result; production scheduling uses `review-schedule-v1` approved by IDK-009.
- User-visible outcome: Every goal has a real notebook of labelled entries, and an optional review queue that never blocks navigation and never penalizes dismissal or disabling.
- PRD traceability: NBK-01 (primary), RET-01 (primary), RET-02 (primary), RET-03 (primary)
- Appendix H decisions: D6 (contributing — "dismissed reviews carry no penalty" is part of the D6 rule set).
- Owning module: notebook_review
- Dependencies: IDK-204, IDK-201
- Scope:
  - `notebook_entries` (owner/goal, optional topic/evidence/source, `entry_kind CHECK(auto,user)`, Markdown, timestamps, optional tombstone) per spec §4.5.
  - `goal_review_preferences` (owner/goal PK, enabled, duration/cadence/type settings, row version); `review_items` (owner/goal/topic, unique immutable source-assessment ref, prompt ref/type, ready/due/dismissed/disabled/generation-failed/completed, current rung, due/interval); `review_attempts` (owner/goal/item, response, optional confidence, feedback/correction, next interval, non-reused context ref/hash and result, timestamp, immutable).
  - `GET/POST /goals/{goalId}/notebook`; `PATCH/DELETE /notebook/{id}`; `GET/PATCH .../review-preferences`; `GET .../reviews`; `POST /reviews/{id}/attempts`; `POST .../dismiss` per spec §5.2.
  - Retrieval prompts require recall/explanation/application before the answer is revealed (RET-03).
  - Per-goal enable/disable and duration/cadence/type tuning affects only future suggestions, never blocks roadmap access, and creates zero readiness penalty (RET-02, verified jointly with IDK-205).
  - `review-schedule-v1` interval transitions, UTC cadence anchors/slots, deterministic subject interleaving, five-minute item budget, and changed-context requirement.
- Out of scope:
  - Authoring or approving scheduling policy — `review-schedule-v1` is owned by IDK-009. This ticket implements and activates it.
  - Derived-state computation itself (IDK-205) — this ticket only guarantees it never feeds a penalty in.
- Data and invariants:
  - Review is optional and non-blocking by construction — a disabled or empty review queue never gates any roadmap or topic action.
  - `review_attempts` are immutable; the answer stays hidden until a response is recorded (reveal-before-response is forbidden per spec §9.2).
  - Review items and attempts retain `review-schedule-v1`; each item has a current ladder rung before attempt, and a scheduling decision consumes the assessed review classification plus optional confidence rather than inferring quality from response text.
  - Initial `due_at` is anchored to the immutable source assessment timestamp; subsequent due times are anchored to the attempt. Cadence compares UTC dates, missing approved topic/subject mappings fail closed, and varied-context hashes may not repeat for an item.
- API/domain/event contracts: As listed in Scope, per spec §5.2 "Notebook/review" group.
- UX routes and states: notebook/review states — `empty/ready → saved`; review `ready/due → completed/ready`; `dismissed/disabled` per spec §9.2; empty or disabled review never blocks navigation.
- Implementation notes:
  - Preserve the selected app's Settings review-tuning interaction pattern (`src/selected/operations/OperationalPages.tsx` `SettingsPage` review controls: enabled toggle, session length, cadence, retrieval/varied-context checkboxes) as the approved UX reference; only the persistence layer and actual scheduling change.
- Acceptance criteria:
  - Every notebook entry is labelled `auto` or `user`; entries link optionally to a topic/evidence/source.
  - Disabling review, or dismissing every due item, never blocks any roadmap or topic navigation action and produces zero readiness change.
  - A review item's answer is never retrievable before a response is recorded for it.
  - Attempts are append-only and immutable once recorded.
  - Every initial interval, result/confidence transition, cadence slot, subject ordering, session budget and varied-context decision is reproducible from persisted inputs under `review-schedule-v1`.
- Minimum required tests:
  - Automated: Domain test asserting (1) recall/explanation/application response is required before reveal, (2) every `review-schedule-v1` initial/result/confidence transition including material-correction/not-demonstrated precedence, source-anchored initial due time, UTC-date cadence slot, deterministic subject interleave, five-minute session budget, unique changed-context hash, idempotent source-item creation, and missing-topic/subject fail-closed rule, and (3) dismissing or disabling review produces exactly zero progress delta.
  - Manual: None beyond the automated test; policy approval is recorded under IDK-009 and shipped-artifact review remains IDK-503 work.
  - Existing coverage reused: None — the prototype's `codeNotes` (`src/shared/state.tsx`) is a single free-text field standing in for the entire notebook, and its `review` settings (`src/selected/operations/OperationalPages.tsx`) are inert toggles with no actual queue; both are replaced by real `notebook_entries`/`review_items`/`review_attempts`.
- Failure and recovery:
  - A review-item generation failure reports `generation-failed` retryable while the roadmap and topic workspace remain fully available (spec §9.2).
- Removal/replacement: Removes the prototype's single-string `codeNotes` field as the entire notebook, and the inert `review` settings toggles with no backing queue; replaced by goal-scoped `notebook_entries` and a real `review_items`/`review_attempts` queue.
- Approval gate:
  - Satisfied by `docs/decisions/IDK-009-assessment-and-derived-state.md`, decision version 1.0; fixture scheduling remains non-production until replaced by `review-schedule-v1`.
- Estimate:
  - TBD; implementation team to estimate after approval.

### IDK-207 — Generated-content cache, provenance, and staleness contract

- Phase: 2 — MVP learning and evidence
- Status: Complete
- Objective: Implement the D3 cache/provenance/staleness contract for generated learner-facing content: exact key `(canonical_graph_version, topic_id, goal_id, layer, topic_mapped_approved_imports_hash, prompt_template_version)`; provider/model, profile, and live evidence excluded from the key but recorded in an immutable personalization snapshot; staleness surfaced never silent; regeneration only on explicit learner action or a key-changing event; generation single-flighted per key at enqueue; adaptive emphasis/examples/exercises flow through recommendation/review channels and never rewrite cached lesson bodies; claim-level citations for sensitive/disputed/comparative/time-or-version-dependent claims, routine content self-contained and expandable; withdrawn/unavailable sources retained with status.
- User-visible outcome: Generated lesson content is consistent and cacheable per exact context, and the learner is always told — never left silently guessing — when a correction or update has made the shown content stale.
- PRD traceability: CNT-03 (primary), CNT-04 (primary), D3 (primary)
- Appendix H decisions: D3
- Owning module: learning_content, provenance
- Dependencies: IDK-101, IDK-102, IDK-201, IDK-203
- Scope:
  - `generated_artifacts` (owner/goal/graph/topic/layer/type, imports hash, template version, exact cache key/hash, state, body ref/hash, provider/model, timestamp, job; unique D3 cache key), `artifact_provenance_snapshots` (immutable personalization snapshot: evidence/state hash, profile hash, provider/model, generation time, schema/contract versions), `artifact_provenance_refs` per spec §4.7.
  - `claims`/`citations` claim-level support for sensitive, disputed, comparative, and time/version-dependent claim types; routine content remains self-contained with expandable provenance (spec §6.5).
  - Enqueue semantics: cache hit returns the artifact; an active in-flight generation for the same key returns the same `JobRef`; otherwise exactly one job is created (single-flight).
  - Staleness: compare current personalization-snapshot hash to the baked one; on mismatch, show a staleness indicator with an explicit "generated before your correction — regenerate?" affordance; never silently swap content.
  - Regeneration fires only on explicit learner action or a key-changing event (accepted canonical merge, newly approved topic-mapped imports from IDK-203); the cached lesson body itself is never rewritten by adaptive emphasis/examples/exercises (those flow through IDK-202/IDK-206 channels only).
- Out of scope:
  - Live provider invocation itself (Section 4, IDK-404) — this ticket's tests use a fake adapter satisfying `GenerateResult`.
  - Source retrieval mechanics (Section 4).
  - The actual source registry/license content (IDK-003).
- Data and invariants:
  - Cache key uniqueness enforced at the database level (`generated_artifacts` unique D3 cache key).
  - Schema-invalid output is quarantined (`schema_quarantines`) and can never become content/evidence/state (NFR-05, verified jointly with Section 4).
  - Artifact, provenance snapshot, and terminal job result commit atomically.
- API/domain/event contracts:
  - `POST /goals/{goalId}/topics/{topicId}/generate`, `POST /artifacts/{id}/regenerate` per spec §5.2, returning `202 JobRef` (cache hit) or `202 JobRef` (new/joined job).
  - `GET /artifacts/{id}/provenance`, `GET /sources`, `GET /sources/{id}`, `GET /claims/{id}` per spec §5.2.
- UX routes and states: `/app/topic-studio` artifact `absent/stale → generating → ready`; snapshot mismatch → `stale` recoverable with the existing body still visible plus a warning (spec §9.1).
- Implementation notes:
  - Live provider invocation is explicitly out of scope (owned by IDK-404); this ticket's acceptance is fully satisfiable with a fake adapter per NFR-09.
- Acceptance criteria:
  - Two requests for an identical cache key, issued concurrently, result in exactly one generation job and both callers observe the same `JobRef`/eventual artifact.
  - A profile/evidence/provider change that is excluded from the cache key never changes which cached artifact is returned, but does update the staleness comparison.
  - A key-changing event (accepted merge, newly approved import mapping) is the only automatic trigger for staleness; everything else requires an explicit learner regenerate action.
  - A claim classified as sensitive/disputed/comparative/time-or-version-dependent always carries a claim-level citation; routine claims remain self-contained with expandable detail.
- Minimum required tests:
  - Automated: Domain/repository test asserting (1) the cache key is computed exactly from the six specified components with provider/model/profile/evidence excluded, (2) two concurrent generate calls for an identical key single-flight to one job, and (3) a personalization-snapshot mismatch surfaces a staleness flag without altering the visible cached body until an explicit regenerate action (the exact "key/staleness/single-flight" evidence named for CNT-03 in spec §10.2); and (4) a claim persisted with type `fact`(sensitive)/`disputed`/`comparative`/`time-or-version-dependent` and no `citations` row is rejected, while a routine claim is accepted without one — proving CNT-04's claim-level support rule and supplying NFR-09's named "citations" contract evidence.
  - Manual: None beyond the automated test; source/citation policy correctness is a manual review activity under IDK-003.
  - Existing coverage reused: None — the prototype's `LESSON_CONTEXT` static copy (`src/shared/model.ts`) has no cache-key, provenance, or staleness concept at all.
- Failure and recovery:
  - A generation failure leaves the prior cached artifact (if any) visible and marks the new attempt `failed` retryable; nothing partial is ever cached under the key.
- Removal/replacement: Supersedes the prototype's static `LESSON_CONTEXT` copy as the sole content source; curated static content may still populate `content_revisions` as an authored fallback once IDK-001/IDK-002 resolve, but `generated_artifacts` becomes the governing cache/provenance layer.
- Approval gate:
  - The real source registry/license terms cited in claim-level citations additionally require IDK-003; this ticket's cache/provenance/staleness mechanism acceptance uses synthetic sources and does not require it.
- Estimate:
  - TBD; implementation team to estimate after approval.

### IDK-208 — Learner-readable Evidence and Reports surfaces

- Phase: 2 — MVP learning and evidence
- Status: Complete
- Objective: Present Evidence and Reports so a conclusion and next action lead, with details disclosing rubric dimensions, assumptions, sources, provenance, lineage, history, and disputes; a tombstoned-source warning where relevant; detailed/simple presentation; and no evaluative report before explicit terminal completion (Mock-specific terminal gating itself is owned by Section 3/IDK-304 — this ticket covers the learner-readable presentation layer shared by Evidence and the learning portions of Reports).
- User-visible outcome: Opening Evidence or Reports always shows what the learner's work supports and what to do next before anything else, with full rubric/provenance detail available on request.
- PRD traceability: PRG-01 (contributing), CORE-04 (contributing), EVAL-01 (contributing), EVAL-02 (contributing), HND-02 (contributing)
- Appendix H decisions: D5 (contributing — tombstoned-source warning), D6 (contributing — presentation of derived state).
- Owning module: frontend
- Dependencies: IDK-108, IDK-204, IDK-205
- Scope:
  - `/app/evidence`: conclusion + limitation + next action lead; details disclose rubric dimensions, assumptions, sources, provenance, transfer lineage, disputes, and re-evaluation history (reading IDK-204/IDK-205/IDK-108 data, writing only dispute/correction/re-evaluation requests — never an evidence overwrite).
  - Learning-relevant portions of `/app/reports` presentation conventions (conclusion-first, disclosure-detail pattern) shared with the interview-specific report (Section 3 owns the Mock-terminal-gating logic itself).
  - Detailed/simple presentation toggle (reads IDK-104's `owner_settings.progress_display`) changes only what's shown, never deletes underlying data.
  - Tombstoned-source warning rendered when a cited source's status is withdrawn/unavailable (from IDK-207's provenance).
- Out of scope:
  - Any new domain invariant already tested at a lower level in IDK-204 (assessment/dispute append-only), IDK-205 (derived-state determinism), or IDK-108 (transfer/tombstone mechanics) — this ticket adds no redundant test for those.
  - Mock-terminal completion gating for the interview-specific report (Section 3, IDK-304).
- Data and invariants:
  - Presentation-only: switching detailed/simple never deletes or mutates underlying `evidence`, `assessments`, or `goal_progress_memos` rows (verified against IDK-205's existing invariant).
- API/domain/event contracts:
  - Reads `GET /goals/{goalId}/evidence`, `GET /evidence/{id}`, `GET /assessments/{id}`, `GET /goals/{goalId}/progress`; writes `POST .../disputes`, `POST .../reevaluate` per spec §5.2 (already defined by IDK-204).
- UX routes and states: `/app/evidence` — `empty` (before Submit), `ready`, `disputed`, `re-evaluating`, `ambiguity-unresolved`, `tombstoned-source warning`, `failure`/retry; mobile conclusion precedes details (spec §2.2).
- Implementation notes:
  - Preserve the selected app's `EvidencePage` disclosure pattern (`src/selected/operations/OperationalPages.tsx`: hero conclusion card, "Inspect provenance"/"Evidence history" `<details>` regions, dispute action) as the approved UX reference; only the data source changes.
- Acceptance criteria:
  - Evidence and Reports always render conclusion + next action before any detail region, at every viewport.
  - A withdrawn/unavailable cited source renders a visible tombstoned-source warning rather than silently disappearing.
  - Toggling detailed/simple never changes the underlying stored evidence/assessment/progress data (verified by re-reading the API after a toggle).
- Minimum required tests:
  - Automated: Component test asserting the Evidence page always renders the conclusion/next-action region before any `<details>` disclosure region, and that a source with `availability_status='withdrawn'` renders the tombstoned-source warning — the one presentation-layer invariant not already covered at the domain level by IDK-204/IDK-205/IDK-108.
  - Manual: None beyond the automated test.
  - Existing coverage reused: `src/selected/operations/OperationalPages.tsx` `EvidencePage`'s hero-card-then-details layout pattern and the Playwright test `Evidence is unavailable before submission and derives its conclusion from submitted learner state` (`tests/e2e/selected-app.spec.ts`) are reused as the interaction-pattern reference; the underlying prototype `state.evidence`/`disputedEvidenceId` localStorage fields they assert against are REPLACED by the real IDK-204/IDK-108-backed API, so the test's data setup is rewritten against the API while its structural assertions (conclusion visible before submission, dispute-request recorded without overwrite) are preserved.
- Failure and recovery:
  - A read failure on any Evidence/Reports region shows that region's `failure` state with retry while the rest of the page remains usable.
- Removal/replacement: Removes the prototype's client-only `state.evidence` array and `disputedEvidenceId` boolean flag (`src/shared/state.tsx`, `src/selected/operations/OperationalPages.tsx`) standing in for evidence/dispute history; replaced by the IDK-204/IDK-205/IDK-108-backed reads.
- Approval gate:
  - None for this ticket's own acceptance.
- Estimate:
  - TBD; implementation team to estimate after approval.

## 3. MVP interview

Interview Prep ships as two remaining independently-reachable submodes of `/app/interview-hub` (Refresher, Questions) plus the two assessment modes that make preparation defensible: Practice (hints on request, feedback per attempt) and focused Mock (adaptive but feedback-withheld until terminal completion). These four tickets replace the local-reducer prototype for interview flows with owner/goal-scoped persisted runs while preserving the approved UX exactly.

### IDK-301 — Interview Prep hub, editable bundles, and linked Refresher

- Phase: 3 — MVP interview
- Status: Complete
- Objective: Deliver `/app/interview-hub` as the Interview Prep home with independently reachable Refresher and Questions submodes, editable/copyable generic role-level bundles, optional behavioral/leadership items, and Refresher artifacts linked to subject, layer, source, and evidence gap.
- User-visible outcome: A learner opens Interview Prep with no Learn-path prerequisite, sees separate Refresher, Questions, Practice, and Mock cards, deep-links directly into `?mode=refresher` or `?mode=questions`, copies or edits a recommended bundle for a generic role/level with no company field, and can add or remove behavioral/leadership independently of technical subjects.
- PRD traceability: INT-01 (primary), INT-02 (primary), INT-03 (primary), REF-01 (primary), CORE-01 (contributing).
- Appendix H decisions: D3 (contributing — Refresher artifacts are read through the D3 generated-content cache owned by IDK-207/IDK-404).
- Owning module: interview, frontend.
- Dependencies: IDK-004, IDK-103, IDK-104, IDK-201, IDK-205.
- Scope:
  - `/app/interview-hub` route rendering separate Refresher, Questions, Practice, Mock cards per the existing approved layout (`InterviewHub` in `src/selected/core/CorePages.tsx`), re-pointed to API-backed reads.
  - `?mode=refresher` and `?mode=questions` as query states of the same canonical route (no new route); direct deep-link entry with no Learn-goal or Learn-completion check.
  - `interview_bundles`/`interview_bundle_items` CRUD and copy: `GET/POST /interview-bundles`, `GET/PATCH/DELETE /interview-bundles/{id}`, `POST /interview-bundles/{id}/copy`.
  - Generic role/level context fields only; no company field or company-identifying text accepted anywhere in bundle create/edit/copy.
  - The role/level selector and level-derived heading consume `role-competency-copy-v1`; compact labels retain the three stable values while the selected description and company-title-variation helper remain adjacent and accessible.
  - Behavioral and leadership as `interview_bundle_items` with an `optional`/`included` flag independently toggleable without touching technical-subject items.
  - Refresher listing: `GET /goals/{goalId}/refreshers` returning artifacts each carrying subject, layer, source reference, and the evidence gap that motivated the refresher.
  - Questions listing: `GET /goals/{goalId}/questions` surfacing bundle-scoped question selection controls that hand off into Practice/Mock without producing feedback themselves (Questions mode never shows evaluative feedback — that only appears after entering Practice per spec §7.4).
- Out of scope:
  - Practice/Mock run mechanics (IDK-302, IDK-303).
  - Consolidated reports (IDK-304).
  - Live provider-backed refresher generation and source retrieval wiring (IDK-404); this ticket consumes whatever artifact the D3 cache already holds and shows a stale/unavailable state otherwise.
- Data and invariants:
  - `interview_bundles`: owner, optional goal, name, generic role/level, origin, copy source, status, `row_version`; no company column exists, so no company claim can be persisted.
  - `interview_bundle_items`: bundle, subject, optional topic/question, position, optional/included flag; behavioral and leadership rows are ordinary optional items, removable without altering technical-subject rows.
  - Refresher reads join `generated_artifacts` + `artifact_provenance_refs` (source kind) + the topic-linked evidence/learning-state row that identified the gap; no refresher route may fabricate a source or evidence-gap link that does not exist in these tables.
- API/domain/event contracts:
  - `GET/POST /interview-bundles`; `GET/PATCH/DELETE /interview-bundles/{id}`; `POST /interview-bundles/{id}/copy` — `201` on create/copy, `200` on read/update, `204` on delete; `Idempotency-Key` on create/copy; `If-Match` on PATCH.
  - `GET /goals/{goalId}/refreshers`; `GET /goals/{goalId}/questions` — `200`; `404` when goal out of owner scope.
  - No endpoint accepts or returns a company field; server-side validation rejects one if a client sends it (`422`).
- UX routes and states:
  - `/app/interview-hub` — `loading` (bundle/refresher fetch), `empty` (no bundle yet → copy/edit offered), `ready`, `unavailable` (content/provider unavailable retains authored bundle material per spec §2.2), `stale` (refresher artifact older than current evidence snapshot, per D3 staleness).
  - `/app/interview-hub?mode=refresher`, `/app/interview-hub?mode=questions` — same states, scoped to the submode's content.
- Implementation notes:
  - Preserve the existing card layout, icons, and copy exactly (approved UX); only the data source changes from `useLearningState()` reducer fields to generated OpenAPI query hooks.
  - Independent reachability is enforced by never gating the route `beforeLoad`/query on any Learn goal or Learn-roadmap completion signal.
  - Bundle role/level selector uses the exact three labels and descriptions approved by IDK-004; the page heading derives from the selected bundle/goal level rather than assuming Senior.
- Acceptance criteria:
  - Opening `/app/interview-hub`, `?mode=refresher`, and `?mode=questions` in a fresh owner session with zero Learn evidence renders successfully with no Learn-completion check performed.
  - Copying a bundle produces a new `interview_bundles` row editable independently of the source; no request/response path carries a company field.
  - Toggling a behavioral or leadership `interview_bundle_item` never mutates a technical-subject item's `optional`/`included` state.
  - A Refresher artifact's detail view shows its subject, layer, source, and the evidence gap that triggered it, or an explicit `unavailable`/`stale` state — never a fabricated link.
  - The selector renders the approved title-variation helper and selected competency description, and changing any level still persists only the stable `Mid-level`/`Senior`/`Staff` value.
- Minimum required tests:
  - Automated: Domain/API plus component test — creating/copying a bundle enforces generic role/level fields and rejects a company field; the exact three approved labels/descriptions and helper render, the heading follows each selection, PATCH retains the stable enum, and independently toggling behavioral/leadership items leaves technical-subject rows unchanged.
  - Manual: Content review confirms each shipped Refresher artifact's subject/layer/source/evidence-gap linkage reads correctly and names no company (REF-01; contributes to G3/G4 review at hardening).
  - Existing coverage reused: `tests/e2e/selected-app.spec.ts`'s 14-route render test already opens `/app/interview-hub` from a fresh browser session, demonstrating no Learn-completion prerequisite; extend it with `?mode=refresher`/`?mode=questions` deep-link assertions rather than duplicating full navigation coverage.
- Failure and recovery:
  - Refresher/bundle fetch failure renders `unavailable` and retains any previously loaded authored material; no synthesized bundle or refresher content is shown.
  - A bundle copy that fails mid-request leaves the source bundle untouched (single synchronous create, no partial write).
- Removal/replacement: None owned by this ticket. The hub's Mock card status text currently reads the local reducer's `state.mock.status`; IDK-303 owns replacing that read with the API-backed run status.
- Approval gate: G4 role-copy policy is satisfied by IDK-004 decision version 1.0; its component/shipped-copy evidence remains required. G1 (IDK-001) still gates final subject coverage before hardening exit.
- Estimate: TBD; implementation team to estimate after approval.

### IDK-302 — Practice: hints, per-attempt feedback, append-only retry

- Phase: 3 — MVP interview
- Status: Content incomplete — the Practice state machine ships and is tested, but the three approved Practice scenario records from IDK-009 content revision `idk009-v1-r1` that this ticket's Scope requires loading exist nowhere outside `docs/`, and IDK-204's rubric registry it consumes is itself unshipped. IDK-503 re-run finding B12, `docs/approvals/IDK-503-content-and-safety-review-rerun-2026-08-15.md`.
- Objective: Implement the Practice lifecycle `ready → answering → follow-up → submitted → evaluating → feedback-ready → failed-recoverable` with hints only after explicit request, feedback only after Submit, facts/trade-offs separation, adaptive follow-ups, and append-only attempts that retry/repair never overwrite.
- User-visible outcome: A learner answers a Practice question, optionally requests a hint before answering, submits to receive per-attempt feedback that separately labels factual corrections and trade-offs, and can repair or continue without losing any earlier attempt; cancelling an in-flight evaluation preserves the submitted attempt.
- PRD traceability: QPR-01 (primary), QPR-02 (primary), EVAL-01 (contributing), EVAL-02 (contributing), HND-01 (contributing — Practice's response/evidence pattern reuses the same evaluated-artifact shape whose primary owner is IDK-405), NFR-09 (contributing).
- Appendix H decisions: D6 (contributing — accepted practice attempts become evidence input to derived learner state).
- Owning module: interview, evidence_evaluation, frontend.
- Dependencies: IDK-008, IDK-009, IDK-204, IDK-205, IDK-301.
- Scope:
  - Load exactly the three approved Practice scenario records from IDK-009 content revision `idk009-v1-r1`; consume IDK-204's approved rubric registry and exact canonical-topic mappings rather than accepting caller-authored or fixture content as authoritative.
  - `/app/practice` route: selected question/scenario, draft answer, on-request hint, Submit, dimension feedback, facts/trade-offs, retry/repair, adaptive follow-up.
  - `interview_runs` (mode `Practice`) and `interview_turns` (question/answer/hint/follow-up kinds) persistence; `interview_turn_results` visible only after Submit.
  - `POST /interview-runs`; `GET /interview-runs/{id}`; `POST /interview-runs/{id}/answers`; `POST /interview-runs/{id}/hints` — hint turn appended only on explicit request, never auto-shown.
  - Submit is the approval boundary: it creates an immutable attempt/evidence candidate and enqueues an interactive-lane evaluation job; feedback is not shown before that job's terminal result commits.
  - Cancel-in-flight-evaluation control that preserves the just-submitted attempt turn (attempt row is never deleted or replaced by a cancel).
  - Adaptive follow-up turns that target named assumptions or evidence gaps from the evaluation result, not generic re-asks.
  - The approved `senior-zero-downtime-schema-practice-v1` static feedback limitation communicates IDK-008's semantic clauses: no database connection; no statement/query-plan/migration/concurrency execution; and no proof of runtime, persistence, performance, locking, or production behavior.
- Out of scope:
  - The evaluator's internal rubric computation and dispute/re-evaluation mechanics (owned by IDK-204's evidence_evaluation domain; this ticket only consumes its contract).
  - Live CLI-provider execution (IDK-403) and the durable two-lane worker's crash/restart guarantees (IDK-401); Practice is built and tested against the interview/evaluation domain contract and a fake evaluator per NFR-09, then connected to the real job/provider pipeline by IDK-404.
  - Mock's distinct no-feedback-while-active behavior (IDK-303).
- Data and invariants:
  - `interview_turns`: unique `(run_id, turn_number)`; DB/service rejects a feedback-kind turn appearing before its answer turn's Submit.
  - `interview_turn_results`: `visibility timestamp` set only at Submit-derived evaluation commit for Practice (immediate visibility rule differs from Mock's completion-only visibility, enforced by the same table's mode-aware visibility rule).
  - Attempts are append-only: retry/repair creates a new `interview_turns` answer row; no update/delete path exists on a prior attempt row.
  - `EvaluationResult` (spec §5.3) carries separate `facts` and `trade-offs` arrays plus named rubric dimension outcomes; the UI renders them as visually distinct groups, never merged into one undifferentiated feedback blob.
- API/domain/event contracts:
  - `POST /interview-runs` (mode=Practice) → `201`.
  - `POST /interview-runs/{id}/answers` → `202` with `JobRef` (interactive-lane evaluation job) once nonblank.
  - `POST /interview-runs/{id}/hints` → `200`, appends a hint turn; repeat calls are idempotent per turn (no duplicate hint spam beyond one requested-hint turn per question unless the domain explicitly allows more).
  - Evaluation job terminal event (`job_events`) carries `state=succeeded`/`failed`, `retryable`, and a typed result ref; cancel uses `POST /jobs/{id}/cancel` semantics defined by IDK-401 but this ticket only asserts that its own attempt row survives cancellation — it does not re-test job-cancellation atomicity itself.
- UX routes and states:
  - `/app/practice` — `ready`, `answering`, `follow-up`, `submitted`, `evaluating`, `feedback-ready`, `failed-recoverable` (Appendix D interview/evaluation states).
  - `aria-live` region announces status/feedback only after Submit, matching the approved shared interaction contract.
- Implementation notes:
  - Reuse the existing Classroom/Practice layout and copy from `src/selected/core/CorePages.tsx`'s `Practice` component; swap the local reducer for OpenAPI query/mutation hooks against the endpoints above.
  - "Repair" prefills the draft from the latest attempt but on re-submit always appends a new attempt; it never mutates the prior one, matching the current reducer's `START_REPAIR`/`SUBMIT_PRACTICE` intent but backed by durable append-only rows.
- Acceptance criteria:
  - No hint turn exists in `interview_turns` until an explicit hint request is recorded.
  - No `interview_turn_results` row is visible to the client before its Submit-triggered evaluation job reaches a terminal state.
  - Two consecutive submissions on the same question produce two distinct, individually retrievable attempt rows; the first attempt's stored answer text is unchanged after the second submission.
  - Cancelling an `evaluating` run leaves the submitted attempt row intact and queryable.
  - Feedback UI renders facts and trade-offs as separately labeled groups sourced from distinct `EvaluationResult` fields.
- Minimum required tests:
  - Automated: Domain/state-machine test (interview module, lowest useful level) loading the exact three approved Practice records and driving `ready → answering → (hint) → submitted → evaluating → feedback-ready`, asserting exact role/topic/capability/rubric mapping, hint-before-request is impossible, feedback-before-Submit is impossible, a second submit appends rather than overwrites, cancelling `evaluating` preserves the attempt row, and the approved RDB Practice record carries every IDK-008 static-limitation clause. This is the primary Practice-timing test for the codebase; no other ticket duplicates it.
  - Manual: Reviewer confirms adaptive follow-up wording names a specific assumption or evidence gap rather than a generic prompt (QPR-01 follow-up quality, part of G9 content review).
  - Existing coverage reused: `tests/e2e/selected-app.spec.ts`'s "Practice reveals a requested hint, then feedback, repair, and append-only history" test is REPLACED — its localStorage-state assertions (`learningState(page)` reads of `lattice.learning.state.v1`) are superseded by assertions against `GET /interview-runs/{id}` once Practice is API-backed; the interaction ordering it exercises (hint → submit → feedback → repair → second attempt) remains the intended E2E shape for the successor test.
- Failure and recovery:
  - Evaluation job failure surfaces `failed-recoverable` with a retry action that resumes from the existing attempt (no re-submission required); the attempt itself is never lost.
  - A dropped connection during `evaluating` reconciles via `GET /interview-runs/{id}` on reload; no client-only state is authoritative.
- Removal/replacement: The localStorage-persisted `practice` slice (`questionIndex`, `draft`, `hintRequested`, `mode`, `attempts`) and its dispatch actions (`SET_PRACTICE_DRAFT`, `REQUEST_HINT`, `SUBMIT_PRACTICE`, `START_REPAIR`, `CONTINUE_PRACTICE`) in `src/shared/state.tsx`, the deterministic `practiceFeedback()` fixture scorer, and the bundled `PRACTICE_QUESTIONS` fixture bank in `src/shared/model.ts` are removed and replaced by the `interview_runs`/`interview_turns`/`interview_turn_results` contract above.
- Approval gate: Satisfied by `docs/decisions/IDK-009-assessment-and-derived-state.md`, decision version 1.0. Production Practice content must use the approved scenario/rubric versions and pass the decision artifact's section 11 activation evidence.
- Estimate: TBD; implementation team to estimate after approval.

### IDK-303 — Focused Mock: adaptive turns, exact safe-exit draft, terminal Complete

- Phase: 3 — MVP interview
- Status: Content incomplete — the Mock state machine, exact-draft preservation and terminal Complete ship and are tested, but the three approved Mock scenario records from IDK-009 content revision `idk009-v1-r1` that this ticket's Scope requires loading exist nowhere outside `docs/`, and IDK-204's rubric registry it consumes is itself unshipped. IDK-503 re-run finding B12, `docs/approvals/IDK-503-content-and-safety-review-rerun-2026-08-15.md`.
- Objective: Implement `/app/mock` outside the ordinary global shell with one adaptive interviewer question at a time, no hints or evaluative feedback while nonterminal, byte-for-byte Save & exit draft preservation, resume that changes only status, and an explicit, idempotent, terminal Complete that fixes the transcript and enqueues final evaluation.
- User-visible outcome: A learner answers a focused Mock interview seeing only status, the current question, the answer field, Save & exit, and terminal completion — no hints, rubric, score, praise, recommendation, evaluation, or Reports link while active; exiting and resuming returns the exact draft unchanged; completing is a deliberate, irreversible action after which the transcript can no longer accept answers.
- PRD traceability: QMK-01 (primary), EVAL-01 (contributing), EVAL-02 (contributing).
- Appendix H decisions: D4.
- Owning module: interview, jobs_events, frontend.
- Dependencies: IDK-009, IDK-301, IDK-302, IDK-104.
- Scope:
  - Load exactly the three approved Mock scenario records from IDK-009 content revision `idk009-v1-r1`; consume IDK-204's approved rubric registry and exact canonical-topic mappings rather than generating authoritative questions from arbitrary bundle text.
  - `/app/mock` route rendered without `GlobalHeader`/`CourseBand` at every viewport (focused shell, matching the existing `focusedMock` behavior in `src/selected/LearningApp.tsx`).
  - `interview_runs` (mode `Mock`) and `interview_turns` state machine: `ready → answering/follow-up → paused (Save & exit) → answering (resume) → answering → follow-up (submit turn, generate next turn) → completing (explicit Complete, transcript fixed, final evaluation enqueued) → completed | failed-recoverable`.
  - `POST /interview-runs` (mode=Mock); `POST /interview-runs/{id}/answers`; `POST /interview-runs/{id}/pause`; `POST /interview-runs/{id}/resume`; `POST /interview-runs/{id}/complete`.
  - DB/service-level rejection of any hint or interim-report request while nonterminal, returning `409 mock_feedback_withheld`.
  - Save & exit persists the in-progress draft exactly as typed (no trim, no normalization) and does not complete the run.
  - Complete rejects a blank or incomplete transcript; once valid, Complete is idempotent — repeated calls after the first successful completion return the same terminal state without creating a second transcript-fix or a second evaluation enqueue.
  - Cancelling next-turn generation preserves the transcript exactly as it stood before the cancelled generation attempt.
- Out of scope:
  - The consolidated report content and the removal of fixture-evaluation gating (IDK-304).
  - The durable two-lane worker's crash/restart/retry guarantees for the next-turn and final-evaluation jobs (IDK-401) and the live CLI provider (IDK-403); this ticket defines and tests the Mock domain/state machine against the job/provider port using a fake next-turn generator, and IDK-404 wires it to the real pipeline.
- Data and invariants:
  - `interview_turns` unique `(run_id, turn_number)`; DB trigger/service rejects inserting a hint or feedback-kind turn while the parent run's state is nonterminal.
  - The draft field persisted at `paused` is stored as an exact byte-for-byte copy (including leading/trailing whitespace and internal line breaks) of the client-submitted string; no server-side trim, collapse, or normalization step may run on it.
  - `Complete` on a nonterminal run with a blank or unchanged-since-last-turn answer is rejected (`409`); Complete on an already-`completed` run returns `200` with the existing terminal result rather than mutating anything (idempotent terminal action per spec §5.2).
  - Complete's transaction fixes the transcript (`interview_runs.final_assessment` linkage prepared) and enqueues the final-evaluation interactive-lane job in the same atomic step described by D4 — this ticket asserts the domain-level invariant; IDK-401 owns the job-engine atomicity mechanism itself.
- API/domain/event contracts:
  - `POST /interview-runs/{id}/hints` and any interim `GET .../report` while nonterminal → `409 mock_feedback_withheld` (exact code from spec §5.2).
  - `POST /interview-runs/{id}/pause` → `200`, run state `paused`, draft stored exactly; `POST .../resume` → `200`, run state returns to `answering`, draft unchanged — resume "changes status only."
  - `POST /interview-runs/{id}/complete` on blank/incomplete transcript → `409`; on valid nonterminal run → `202` with `JobRef` for the final evaluation, run state `completing`; on already-`completed` run → `200` idempotent no-op.
  - Next-turn generation job cancellation leaves `interview_turns` unchanged from its pre-cancellation content (asserted here; job-cancellation race resolution mechanics per spec §8.2 are IDK-401's).
- UX routes and states:
  - `/app/mock` — `active/paused/resumed/follow-up/completing/completed/failed-recoverable` (route table) mapped onto Appendix D's `ready, answering, follow-up, submitted, evaluating, feedback-ready, disputed, re-evaluating, ambiguity-unresolved, failed-recoverable` vocabulary as applicable to Mock's subset (no `evaluating`/`feedback-ready` exposure while nonterminal).
  - No ordinary global shell, hints, rubric, score, praise, recommendation, evaluation, or Reports link appears at any nonterminal state or viewport.
- Implementation notes:
  - Preserve the existing Save & exit / Complete confirmation-dialog UX in `src/selected/core/CorePages.tsx`'s `Mock` component (focus-restoring `AlertDialog`s) exactly; only the persistence and gating move server-side.
  - The "final question" framing and turn numbering become dynamic (driven by the adaptive interviewer's next-turn decision) rather than the hardcoded `Question 3 · final question` string.
- Acceptance criteria:
  - A draft saved via Save & exit and then resumed round-trips through the API with zero character difference, including leading/trailing whitespace.
  - Any hint or interim-report request while the run is nonterminal returns `409 mock_feedback_withheld` and changes no state.
  - Complete on a blank draft is rejected; Complete on a valid draft transitions to `completing` exactly once even if the client double-submits the request (idempotency key deduping and terminal-state check both prevent a second transcript fix).
  - Cancelling a next-turn generation leaves the transcript's turn count and content identical to before the cancel.
- Minimum required tests:
  - Automated: Domain/property test (interview module) loading the exact three approved Mock records and asserting role/topic/capability/rubric mapping, byte-for-byte draft preservation across pause→resume (including a string with leading/trailing whitespace and embedded newlines), Complete's rejection of a blank/incomplete transcript, Complete's idempotency under a repeated call, next-turn-generation cancellation leaving the transcript unchanged, and a hint or interim-report request while the run is nonterminal returning `409 mock_feedback_withheld` with no state change. It also asserts, at the component level, that `/app/mock` renders no `GlobalHeader`/`CourseBand` while nonterminal. This is the primary Mock-timing/exact-draft test for the codebase; no other ticket duplicates it.
  - Manual: Reviewer confirms the active Mock screen at all four required viewports shows only status, current question, answer field, Save & exit, and Complete — nothing else (focused-shell UX review).
  - Existing coverage reused: `tests/e2e/selected-app.spec.ts`'s "Mock pause/resume preserves the exact draft and evaluation appears only after terminal completion" test is REPLACED for its state-machine portion (pause/resume exact-draft, Complete gating dialogs) — that interaction shape is retained as the E2E successor against the API-backed run, while its `reportKind`/fixture-evaluation assertions move to IDK-304's regression test.
- Failure and recovery:
  - A next-turn generation failure surfaces `failed-recoverable` on the run with the transcript unchanged and a retry action; the learner is never shown a synthesized next question.
  - Final-evaluation enqueue failure after a valid Complete leaves the run in `completing` with `failed-recoverable` recovery per D4, not silently reverting to `answering` (the transcript is already fixed).
- Removal/replacement: The localStorage-persisted `mock` slice (`status`, `draft`, `priorTurns`, `completedTurns`) and its dispatch actions (`SET_MOCK_DRAFT`, `SAFE_EXIT_MOCK`, `RESUME_MOCK`, `COMPLETE_MOCK`) in `src/shared/state.tsx`, and the bundled `MOCK_PRIOR_TURNS`/`MOCK_CURRENT_QUESTION` fixtures in `src/shared/model.ts`, are removed and replaced by the `interview_runs`/`interview_turns` contract above. The `reportKind` fixture-vs-transcript-only classification and `MOCK_FIXTURE_DRAFT` string-match gate are IDK-304's removal, not this ticket's.
- Approval gate: The Mock scenario/rubric decision is satisfied by IDK-009 decision version 1.0. The state-machine mechanics remain independently buildable, but authoritative Mock content requires IDK-204's exact approved topic mapping and the decision artifact's section 11 evidence; G4/G9 shipped-content review remains required before release.
- Estimate: TBD; implementation team to estimate after approval.

### IDK-304 — Terminal-only consolidated Reports and fixture-evaluation removal

- Phase: 3 — MVP interview
- Status: Complete
- Objective: Deliver `/app/reports` as the learner-readable, conclusion-first consolidated view for terminal Mock (and Practice-linked) results, with rubric history and dispute/re-evaluation entry, and remove the prototype's exact-string-match fixture scoring so it survives only as a controlled regression test.
- User-visible outcome: A learner sees a report only after explicitly completing Mock; the report leads with a plain-language conclusion and next action, then discloses assumptions, facts vs. trade-offs, rubric dimensions, ambiguity, transcript, and provenance; edited, blank, incomplete, or arbitrary transcripts never receive the exact-fixture evaluation and are instead shown as transcript-only or a real evaluator result.
- PRD traceability: QMK-02 (primary), EVAL-01 (contributing), EVAL-02 (contributing), PRG-01 (contributing), CNT-04 (contributing).
- Appendix H decisions: None.
- Owning module: interview, evidence_evaluation, provenance, frontend.
- Dependencies: IDK-009, IDK-204, IDK-301, IDK-302, IDK-303.
- Scope:
  - `/app/reports` route: conclusion and next action first, then assumptions, facts vs. trade-offs, rubric dimensions, ambiguity, transcript, and provenance, exactly matching the approved disclosure ordering in spec §2.2.
  - `GET /interview-runs/{id}/report` gated so no evaluative content is returned before the run's explicit terminal `completed` state.
  - Rubric history surface across superseded/successor assessments (append-only, per D6/EVAL-02).
  - Dispute and re-evaluation entry points: `POST /goals/{goalId}/evidence/disputes`-equivalent (`.../disputes`) and `.../reevaluate` wired from the report view for the evaluated attempt.
  - **Removal of exact-string-match fixture scoring.** `MOCK_FIXTURE_DRAFT` and `reportKind: 'fixture-evaluation'` in `src/shared/state.tsx` and `src/shared/model.ts` are deleted from production code paths. Fixture evaluation survives only as a controlled regression test asserting the exact unedited complete fixture transcript still produces the expected assessment through the real evaluator/domain contract.
  - Blank, incomplete, edited, or arbitrary transcripts render `transcript-only` or route through the validated production evaluator (owned by IDK-204/IDK-403/IDK-404) — never the deleted fixture shortcut.
- Out of scope:
  - The evaluator implementation itself (evidence_evaluation domain, IDK-204) and the live provider call it may make (IDK-403/IDK-404); this ticket consumes the evaluation result contract and controls when it is shown.
  - Mock's turn-taking/safe-exit mechanics (IDK-303) and Practice's attempt mechanics (IDK-302).
- Data and invariants:
  - `assessments`/`assessment_dimension_results`/`assessment_disputes`/`reevaluation_requests` are read-only from this ticket's perspective; report never writes an assessment, only reads and requests dispute/re-evaluation.
  - `interview_runs.final_assessment` and `state=completed` are the sole gate for any evaluative content; a report request against a `paused`/`answering`/`follow-up`/`completing` run returns `empty`/`unavailable`, never a partial or estimated result.
  - The controlled regression test's fixture transcript is the only input permitted to produce a pre-approved "known-good" assessment outcome in test code; no non-test code path may special-case that string.
- API/domain/event contracts:
  - `GET /interview-runs/{id}/report` → `200` only when `state=completed`; otherwise `409`/`404` per the run's current state (no evaluative payload leaks early).
  - `POST /goals/{goalId}/evidence/{evidenceId}/disputes`; `POST /goals/{goalId}/evidence/{evidenceId}/reevaluate` → `202` with `JobRef`; original assessment is preserved, successor assessment appended (EVAL-02).
- UX routes and states:
  - `/app/reports` — `empty/unavailable` (before terminal completion), `evaluating`, `feedback-ready`, `ambiguity-unresolved`, `stale` (after a superseding re-evaluation).
  - Mobile sections stack in the same conclusion-first order; disclosure details use semantic headings/`<details>` per the approved layout.
- Implementation notes:
  - Reuse the existing `Reports` component's section ordering and copy in `src/selected/core/CorePages.tsx` (conclusion → next action → report gate → facts/trade-offs → transcript/provenance → evidence history); replace the `fixture`/`transcriptOnly` branch entirely with a real `state=completed` + assessment-presence check.
  - The "report gate" copy ("Exact-fixture evaluation" / "Transcript only" / "Unavailable") is replaced by real states: evaluated (real assessment present), transcript-only (evaluation not yet available or not requested), unavailable (run not completed).
- Acceptance criteria:
  - No request to `/app/reports` or `GET /interview-runs/{id}/report` returns evaluative content for a run whose state is not `completed`.
  - The regression test's exact unedited fixture transcript, submitted through the real evaluator, produces the previously-expected assessment shape; any single-character edit to that transcript does not.
  - A blank or incomplete transcript (which IDK-303 already rejects at Complete) can never reach this ticket's evaluative path at all.
  - `reportKind`/`MOCK_FIXTURE_DRAFT` no longer exist anywhere in non-test source.
- Minimum required tests:
  - Automated: Domain/contract regression test (evidence_evaluation + interview modules, per NFR-09) — the exact unedited complete fixture transcript passed through the real evaluation contract yields the expected assessment, while a one-character-edited copy of the same transcript does not receive fixture-equivalent scoring and instead resolves as a transcript-only or genuinely-evaluated (non-special-cased) result. This is the controlled regression test spec §7.4 requires and the only place fixture evaluation survives.
  - Manual: Reviewer walks the report disclosure ordering (conclusion → next action → assumptions → facts/trade-offs → rubric → ambiguity → transcript → provenance) against the approved layout for at least one real (non-fixture) completed Mock run (contributes to G9 content/rubric review).
  - Existing coverage reused: `tests/e2e/selected-app.spec.ts`'s Mock-to-Reports flow assertions on `mock.reportKind === 'fixture-evaluation'` are REPLACED by an assertion against the real `GET /interview-runs/{id}/report` gated on `state=completed`; the "no report before terminal completion" ordering the existing test exercises is retained as the E2E shape.
- Failure and recovery:
  - Evaluator failure on a completed run's final evaluation surfaces `failed-recoverable` on the report with a retry action; the fixed transcript is never altered by a failed or retried evaluation.
  - Ambiguity in the evaluation result is shown as `ambiguity-unresolved` and explicitly does not reduce any readiness/progress figure (EVAL-02, D6).
- Removal/replacement: Removes the prototype's exact-string-match fixture scoring (`MOCK_FIXTURE_DRAFT` and `reportKind: 'fixture-evaluation'` in `src/shared/state.tsx` and `src/shared/model.ts`) and the `FIXTURE_REPORT` constant in `src/shared/model.ts` with its consumption in `Reports` (`src/selected/core/CorePages.tsx`); fixture evaluation survives only as the controlled regression test described above.
- Approval gate: Satisfied by `docs/decisions/IDK-009-assessment-and-derived-state.md`, decision version 1.0. A real report must retain the approved rubric, ambiguity, version, and non-prediction disclosures and pass the decision artifact's section 11 activation evidence.
- Estimate: TBD; implementation team to estimate after approval.

## 4. MVP AI and hands-on

These nine tickets deliver the durable two-lane job engine, SSE, the CLI provider port with disclosure and schema quarantine, live generation/evaluation/source-retrieval wiring, the hands-on static-review lifecycle, the Java runner, canonical v2 publication and atomic merge, FTS5 search, and settings/export/delete — replacing every remaining prototype simulation (jobs, network tripwire, canonical-update localStorage, bundled search, export/reset) with the real API-backed system.

### IDK-401 — Durable two-lane job engine: crash, restart, retry, cancel, atomicity

- Phase: 4 — MVP AI and hands-on
- Status: Complete
- Objective: Deliver the one durable worker process with reserved interactive and background lanes, FIFO within each lane, queue-level dedupe/single-flight at enqueue, startup reconciliation, and one-transaction terminal result/state/event commit, replacing the prototype "no live job system" Jobs page with the real operational view.
- User-visible outcome: `/app/jobs` shows real queued/running/succeeded/failed/cancel-requested/cancelled jobs across both lanes with retry/cancel controls that reflect actual server state; background bulk work never blocks an interactive conversational turn; a server restart never leaves a job in an ambiguous terminal state.
- PRD traceability: DAT-02 (primary), NFR-02 (primary), NFR-05 (contributing — fail-closed reconciliation), NFR-06 (contributing — job diagnostics).
- Appendix H decisions: D4, D8.
- Owning module: jobs_events.
- Dependencies: IDK-101.
- Scope:
  - `jobs`, `job_attempts`, `job_events`, `job_results` tables per spec §4.7 with partial-unique active dedupe key, lane/state indexing, and immutable `job_attempts` retry history.
  - One worker process with two reserved dispatch loops (interactive: tutor/Practice/Mock turns and explicit regenerations; background: bulk generation, import parsing, indexing, review scheduling); FIFO within each lane; background work can never occupy the interactive slot.
  - Queue-level dedupe/single-flight enforced at enqueue via the active dedupe-key constraint.
  - A configured, visible pending-job cap and background age-promotion after a configured interval, both implemented as server configuration values with the numeric value left TBD pending IDK-010 — the mechanism (cap enforcement returning `429`, promotion changing scheduling priority) ships now; the specific numbers are supplied later without a code change beyond configuration.
  - Startup reconciliation: `queued` stays `queued`; an ordinary provider/background `running` attempt has its recorded process group and temp path reconciled then becomes `failed`+`retryable`; `cancel-requested` becomes `cancelled` with no retry offer. Runner jobs first invoke IDK-406's registered cgroup/cleanup-intent lifecycle hook and are never reconciled through this generic process-group path.
  - Result artifact, terminal job state, and terminal event committed in one transaction (`job_results` unique per job, inserted atomically with the terminal `jobs.state` write and the `job_events` row).
  - Retry: short-circuits to `succeeded` when a committed result already exists under the job's dedupe key; typed per job kind — idempotent rerun (indexing/import), cache-checked rerun (generation), resume-with-substitution (interview turns), user-confirmed fresh run (runner).
  - Cancellation races resolved per spec §8.2: terminal result committed first wins; cancellation committed first discards/quarantines a late result; repeated cancel returns the authoritative state idempotently.
  - Janitor sweep of terminal-state temp directories with retention timing left TBD pending IDK-010; PID/PGID/temp-path persisted at spawn (`job_attempts`) with spawn identity verified before signalling, so a reused PID is never killed.
  - `GET /jobs`; `GET /jobs/{id}`; `POST /jobs/{id}/retry`; `POST /jobs/{id}/cancel`; `POST /jobs/{id}/reconcile`.
- Out of scope:
  - SSE delivery of job events (IDK-402).
  - The CLI provider adapter and its own timers (IDK-403).
  - The Java runner's process/limit specifics (IDK-406) beyond the generic job-kind retry typing this ticket defines.
- Data and invariants:
  - `jobs`: partial unique constraint on active dedupe key prevents two concurrently-active jobs for the same dedupe target.
  - `job_results`: unique per `job_id`; insertion is atomic with the terminal `jobs.state` transition and its `job_events` row — no code path can write a result without also committing the terminal state and event in the same transaction.
  - `job_attempts`: immutable once written; each attempt records PID, PGID, temp path, start/end timestamps, and outcome/diagnostic.
- API/domain/event contracts:
  - `JobPayload`/`JobResult` per spec §5.3 (kind/schema version, owner/goal, lane, dedupe key, typed request/result ref, correlation IDs).
  - `POST /jobs/{id}/retry` → retry-type-specific behavior per job kind, short-circuiting to `succeeded` when a committed result exists.
  - `POST /jobs/{id}/cancel` → `202`/`200` per current state; repeated cancel is idempotent.
- UX routes and states:
  - `/app/jobs` — `queued/running/succeeded/failed/cancel-requested/cancelled`; mobile job cards replace tables; status communicated as text plus icon, never color alone.
- Implementation notes:
  - Lane dispatch is two independent claim loops within the single worker process, not two processes — satisfies DAT-02's "one worker process" while D8 refines it into two reserved lanes.
  - The pending-job cap and age-promotion interval are read from server configuration at dispatch time, not hardcoded, so IDK-010's eventual values require no code change.
- Acceptance criteria:
  - Killing the worker mid-`running` and restarting it reconciles that job to `failed`+`retryable` with its temp path swept, and a fresh `queued` job submitted before the crash is unaffected.
  - Two enqueue requests sharing a dedupe key while one is active produce exactly one active job; the second returns the first's `JobRef`.
  - A background job never delays an interactive-lane job's claim when both are queued simultaneously.
  - Retrying a job whose dedupe key already has a committed result returns `succeeded` without a new execution.
  - A cancel racing a just-committed terminal result leaves the terminal result as authoritative; a cancel that commits first discards a late-arriving result.
- Minimum required tests:
  - Automated: Integration test — job crash/restart/retry/cancel/dedupe/lane-starvation and terminal-result atomicity, exercising: worker restart with a `running` job (reconciles to `failed`+`retryable`), a `cancel-requested` job at restart (becomes `cancelled`, no retry offer), duplicate enqueue under one dedupe key (single active job), the cancellation-race ordering from spec §8.2, and one case per D4 retry type proving they are behaviourally distinct — idempotent rerun (indexing/import), cache-checked rerun (generation), resume-with-substitution recording an explicit substitution for an interview turn, and runner retry rejected without a fresh user confirmation. This is the primary durable-job test for the codebase; no other ticket in these two sections duplicates it.
  - Manual: Operator inspects `/app/jobs` during a background bulk-generation run and confirms an interactively-enqueued Practice evaluation still claims and completes without waiting on the background job.
  - Existing coverage reused: None — no prior test exercises a live job system.
- Failure and recovery:
  - Startup reconciliation runs before the server accepts new work; a reconciliation failure stops startup with a recoverable diagnostic rather than serving a partially-reconciled job list (mirrors the Alembic-head-check failure posture in spec §4.8).
  - A janitor sweep failure is recorded as a cleanup failure on the affected job, not silently ignored.
- Removal/replacement: Replaces the simulated `/app/jobs` "no live job system is connected" prototype page (`JobsPage` in `src/selected/operations/OperationalPages.tsx`) with the real jobs/lanes operational view described above.
- Approval gate: G10 (size/retention, IDK-010) must settle the pending-job cap value, age-promotion interval, and janitor retention timing before release; the mechanism ships now against configurable placeholders.
- Estimate: TBD; implementation team to estimate after approval.

### IDK-402 — SSE reconnect with authoritative GET reconciliation

- Phase: 4 — MVP AI and hands-on
- Status: Complete
- Objective: Deliver owner-scoped `GET /events` SSE with `Last-Event-ID` reconnect, in-order replay of retained events, client-side dedupe, and mandatory post-reconnect reconciliation against `GET /jobs/{id}` as the authoritative source.
- User-visible outcome: A learner watching an in-flight job sees connected/reconnecting/unavailable status with a Refresh action; after any connection loss, the UI always confirms the true job state via GET rather than trusting replayed events alone, and duplicate event delivery never double-applies a state change.
- PRD traceability: SYS-03 (primary), NFR-02 (contributing).
- Appendix H decisions: None.
- Owning module: jobs_events, frontend.
- Dependencies: IDK-101, IDK-401.
- Scope:
  - `GET /events` SSE endpoint scoped to the resolved local owner; supports `Last-Event-ID` request header.
  - Server returns later retained owner-scoped `job_events` rows in event-ID order on reconnect.
  - Client dedupes by `event_id` and tolerates duplicate delivery without re-applying an already-applied state change.
  - After any connection loss, the client always calls `GET /jobs/{id}` for every watched job; GET state and committed `job_results` are authoritative over anything replay implied.
  - Connected/reconnecting/unavailable status indicator with an explicit Refresh action wired to the same GET reconciliation path.
  - Keepalive events are transport-only and are never treated as a job-state change by the client.
- Out of scope:
  - The job engine's own state machine and atomicity (IDK-401) — this ticket only delivers and reconciles events about it.
  - Exact replay retention/expiry/maximum-replay-window values (TBD, IDK-010); this ticket implements the mechanism against whatever retention window the server configuration provides and never promises replay beyond it.
- Data and invariants:
  - `job_events`: `event_id` opaque monotonically ordered; indexed `(owner_id, event_id)` and `(job_id, event_id)` for both scoped streaming and reconciliation lookups.
  - The SSE contract's seven fields (`event_id`, `job_id`, `owner_id`, optional `goal_id`, `state`, `event_type`, `timestamp`, optional `progress`/`result_ref`, `retryable`, `request_id`, `correlation_id`, optional `run_id`) are delivered exactly as specified in spec §5.4 — no field is invented or omitted.
- API/domain/event contracts:
  - `GET /events` (SSE) — owner-scoped; `Last-Event-ID` request header triggers replay of later retained events in ID order before live streaming resumes.
  - Reconnect/unavailable client states always trigger `GET /jobs/{id}` for each job the UI is currently watching; a missed-replay window is never silently assumed complete.
- UX routes and states:
  - Applies to every async route with a job in flight (`/app/topic-studio`, `/app/practice`, `/app/mock`, `/app/imports`, `/app/canonical-updates`, `/app/search`, `/app/jobs`) — `connected`, `reconnecting`, `unavailable` per Appendix D's SSE states, each with an observable Refresh/GET fallback.
- Implementation notes:
  - The client SSE consumer is a single shared hook/service so every route's async state indicator behaves identically rather than each page reimplementing reconnect logic.
  - Deduping by `event_id` is a client-side Set/LRU keyed on the opaque ID; no ordering assumption is made beyond "server returns retained events in ID order."
- Acceptance criteria:
  - Disconnecting and reconnecting the SSE stream mid-job replays only events newer than the last received `event_id`, in order, with no duplicate application of an already-seen event.
  - Simulating a missed-replay window (event expired before reconnect) still results in the correct final UI state because the client's post-reconnect `GET /jobs/{id}` call is authoritative.
  - A keepalive-only reconnect never toggles any job's displayed state.
- Minimum required tests:
  - Automated: Integration test — SSE reconnect, duplicate-event tolerance, and missed-replay GET reconciliation: (1) client reconnects with `Last-Event-ID` and receives only newer retained events in order; (2) a duplicate event delivered twice is applied once; (3) a job whose events were not retained through a gap still resolves to its true state via `GET /jobs/{id}`; (4) a keepalive frame injected between two real events leaves every watched job's displayed state unchanged. This is the primary SSE-reconnect test for the codebase; no other ticket duplicates it.
  - Manual: Reviewer disconnects network mid-background-index-rebuild and confirms `/app/search` shows `reconnecting` then `connected` with a working Refresh action throughout.
  - Existing coverage reused: None — no prior test exercises a live event stream.
- Failure and recovery:
  - An unavailable/replay-missed stream shows `unavailable` with a Refresh action; the UI never implies a job stopped simply because the stream dropped.
  - A malformed or unexpected event is dropped client-side and does not crash the stream consumer; the next `GET /jobs/{id}` reconciliation still recovers correct state.
- Removal/replacement: None. SSE and reconnect/GET-reconciliation states are new; the prototype Jobs page removed by IDK-401 had no connected feed to replace.
- Approval gate: G10 (size/retention, IDK-010) must settle exact replay retention/expiry/maximum-replay-window values before release; this ticket's acceptance is scoped to "replay never promises beyond what is retained" regardless of the eventual number.
- Estimate: TBD; implementation team to estimate after approval.

### IDK-403 — CLI provider port: disclosure gate and schema quarantine

- Phase: 4 — MVP AI and hands-on
- Status: Complete — activated under approved IDK-006 decision version 1.1
- Objective: Deliver the D7 CLI-subprocess provider port for Codex 5.6 Terra/high (default) and Claude (alternative) with no-shell argv construction, stdin/temp-file context delivery, per-provider environment allowlist, three configurable timers, process-group cancellation/timeout, pinned per-adapter output contracts, and mandatory PRV-01 disclosure-before-enqueue with schema quarantine for invalid output.
- User-visible outcome: Before any provider-backed action first runs, the learner sees and accepts a network/provider disclosure; a misconfigured or unauthenticated provider is reported as a recoverable configuration error rather than a generic timeout; invalid model output never becomes a lesson, evaluation, or governed mutation — it is quarantined and surfaced as a retryable failure.
- PRD traceability: AI-01 (primary), AI-02 (primary), PRV-01 (primary), PRV-02 (primary), NFR-05 (primary), NFR-09 (primary).
- Appendix H decisions: D7.
- Owning module: provider.
- Dependencies: IDK-006, IDK-101, IDK-401.
- Scope:
  - `ProviderPort` and Codex/Claude adapters constructing argv directly (no shell invocation).
  - Prompt/context delivered via stdin or a restricted temporary file only — never argv (which leaks into process listings and logs).
  - Unused stdin closed to `/dev/null`; mandatory provider-specific non-interactive configuration.
  - Per-provider environment variable allowlist, distinct from the runner's separate minimal allowlist (RUN-02's environment policy is IDK-406's, not duplicated here).
  - Three fixed, typed timers approved by IDK-006 — 20 seconds to first valid JSON event, 180 seconds of event inactivity, and a 1,200 second absolute cap.
  - No-first-output, inactivity timeout, and absolute timeout have distinct fixed classifications.
  - Cancel and timeout kill the process group and descendants; failed and timeout-truncated streams are discarded after reduction to a safe classification and are never schema-quarantined.
  - Each adapter pins an explicit versioned event-stream output contract; only schema-validated output crosses the port.
  - Invalid output is written to `schema_quarantines` and can never become a `generated_artifacts`, `assessments`, evidence, or any governed mutation.
  - PID/PGID/temp path persisted at spawn (`provider_requests`); startup verifies recorded process-start identity before signalling, reporting cleanup failure rather than killing a reused PID.
  - PRV-01 disclosure check before enqueue: `GET /disclosures`; `POST /disclosures/{category}/accept`; `POST .../revoke`; missing/unaccepted disclosure returns `412` at enqueue, before any job is created.
  - `GET /provider-capabilities` reports `executable-missing`, `unsupported-version`, `authentication-unavailable`, or `configured` per provider — never assumes availability.
  - PRV-02 data minimization: only the categories listed in spec §8.5 (required learner context, selected evidence/answers, approved import excerpts, canonical/source context, requested output schema, operation metadata) are sent; redaction categories (credentials/tokens/cookies/auth headers, provider auth env values, AWS keys/connection secrets, unrelated env vars, avoidable absolute paths/usernames, raw prompt/transcript/artifact bodies in ordinary logs, quarantined raw output) never appear in ordinary logs.
- Out of scope:
  - Which specific generation/evaluation call sites use this port (IDK-404 wires callers).
  - The runner's separate subprocess policy (IDK-406) — the low-level subprocess utility is shared per D7, but the runner's own environment/limits are IDK-406's.
  - Exact commands, version-agnostic capability policy, model behavior, environment policy, and authentication discovery are approved in `docs/decisions/IDK-006-provider-cli-support.md`.
- Data and invariants:
  - `provider_requests`: owner/goal/job, purpose, adapter/contract versions, context-ref hash, disclosure ref, PID/PGID/temp path, lifecycle/diagnostic; raw prompt is never a normal log field (only a redacted or securely-referenced form is retained per PRV-02).
  - `schema_quarantines`: request, raw-output secure ref/hash, expected schema version, validation errors, timestamp; a `schema_quarantines` row can never be joined into a result, evidence, or any governed-state write path — enforced at the repository boundary, not just by convention.
  - `network_disclosures`: unique `(owner, category, disclosure_version)`; `accepted_at` must be non-null and the acceptance must precede the enqueue timestamp of any gated job.
- API/domain/event contracts:
  - `GenerateRequest`/`GenerateResult` and `EvaluationRequest`/`EvaluationResult` per spec §5.3 — result is `succeeded`/`failed`/`quarantined`, never a bare raw string.
  - Enqueue without a prior disclosure acceptance for the relevant category → `412`.
  - `GET /provider-capabilities` → one of the four fixed capability states per provider, never inferred from a successful past call alone.
- UX routes and states:
  - Applies to `/app/topic-studio`, `/app/practice`, `/app/mock`, `/app/interview-hub` wherever a provider-backed action is offered — `idle, preparing, waiting-for-disclosure, queued, running, succeeded, failed, cancelled` (Appendix D model/source request states).
  - `/app/settings` provider/network disclosure panel reads the same `network_disclosures`/`provider-capabilities` this ticket exposes (IDK-409 owns the Settings page itself).
- Implementation notes:
  - The heartbeat/inactivity/absolute-cap timers are validated as the exact approved policy values by typed configuration.
  - Adapter and runner share the same low-level "spawn, capture, kill process group" subprocess utility per D7, but each owns its own environment allowlist and policy object — no cross-import of policy between `provider` and `runner` modules.
- Acceptance criteria:
  - A fake adapter test proves no shell is invoked (argv array only) and prompt/context never appears in the constructed argv.
  - An enqueue attempt without a prior disclosure acceptance for the operation's category returns `412` and creates no job.
  - Output that fails schema validation is written to `schema_quarantines` and is unreachable from any `generated_artifacts`/`assessments`/evidence query.
  - A simulated no-first-output condition is classified as `no-first-output`, distinct from `inactivity-timeout` and `absolute-timeout`.
  - Cancel/timeout kills the full process group including a spawned child, verified via the fake `ProcessPort`.
- Minimum required tests:
  - Automated: Provider fake-adapter test — argv/stdin/env construction (no shell, no prompt-in-argv), the `412` disclosure gate before enqueue, the three timer classifications (heartbeat/inactivity/absolute) resolving to distinct outcomes, process-group cancellation, and invalid output landing in `schema_quarantines` and never becoming a result/evidence/governed mutation. This is the primary disclosure/schema-quarantine test for the codebase; no other ticket duplicates it.
  - Manual: Privacy reviewer inspects a captured `provider_requests` diagnostic record and confirms every PRV-02 redaction category is absent (part of G6/G11 review).
  - Existing coverage reused: None — no prior test exercises a real provider adapter.
- Failure and recovery:
  - A missing executable, unsupported CLI, or unavailable authentication reports its exact fixed capability state and any dependent action shows a recoverable error, never a generic crash.
  - Timeout-truncated output is discarded after the fixed retryable classification is recorded; retry re-attempts the same request under the job's dedupe key per IDK-401's cache-checked-rerun typing for generation.
- Removal/replacement: None. No existing provider integration prototype exists to remove; the Settings page's current "Providers and network... Not connected" static text is replaced by IDK-409's disclosure UI, not by this ticket.
- Approval gate: Satisfied by `docs/decisions/IDK-006-provider-cli-support.md`, decision version 1.1; implementation evidence is mapped in `docs/provider/IDK-403-404-acceptance-map.md`.
- Estimate: Completed with the IDK-006/403/404 implementation.

### IDK-404 — Wire live generation, evaluation, tutor conversation, and source retrieval

- Phase: 4 — MVP AI and hands-on
- Status: Complete — live local CLI composition and deterministic wiring coverage recorded
- Objective: Connect Practice, Mock, topic-tutor conversation, and disclosed source retrieval to the real two-lane job engine (IDK-401) and the validated CLI provider port (IDK-403), honoring the D3 cache contract owned by IDK-207, so interview and learning flows stop depending on fakes/local reducers and run against live generation and evaluation.
- User-visible outcome: A learner's Practice submission, Mock turn, topic-tutor question, and any explicit "regenerate" or source-retrieval action now actually enqueue and complete through the real job/provider pipeline; nothing changes in the approved UX itself — only the data path underneath becomes live.
- PRD traceability: CNT-03 (contributing), CNT-04 (contributing), AI-01 (contributing), LRN-02 (contributing — topic tutor conversation wiring).
- Appendix H decisions: D3 (contributing — this ticket is the consumer that must honor the cache-key/staleness contract owned by IDK-207, not redefine it), D7 (contributing), D8 (contributing).
- Owning module: learning_content, evidence_evaluation, interview, provenance, provider, jobs_events.
- Dependencies: IDK-207, IDK-301, IDK-302, IDK-303, IDK-401, IDK-402, IDK-403.
- Scope:
  - Replace the fake evaluator/generator test doubles used by IDK-302's and IDK-303's interview-turn flows with real interactive-lane job enqueues that call through IDK-403's provider port, for: Practice answer evaluation, Mock next-turn generation, Mock final evaluation, and topic-tutor conversation turns.
  - Wire `POST /topics/{topicId}/generate` and `POST /artifacts/{id}/regenerate` (background-lane generation jobs) to the D3 cache key `(canonical_graph_version, topic_id, goal_id, layer, topic_mapped_approved_imports_hash, prompt_template_version)` exactly as IDK-207 defines it — this ticket enqueues against that key and single-flights per key; it does not alter the key's shape, its staleness-comparison rule, or the "regeneration only via explicit action or a key-changing event" invariant.
  - Wire disclosed source retrieval as an explicit `POST /sources/{sourceId}/retrieve` background-lane operation — never silently triggered by a page view, generation job, or cache-key change.
  - Withdrawn/unavailable sources retain their stored status and last known provenance through this wiring; a retrieval attempt against a withdrawn source does not attempt to re-fetch it silently.
  - Route Practice/Mock/tutor/generation results through IDK-403's schema-validated contract only — no direct consumption of unvalidated provider output anywhere in this ticket's call sites.
- Out of scope:
  - The D3 cache key definition, staleness-comparison rule, and single-flight-at-enqueue mechanism themselves (owned by IDK-207).
  - The schema-quarantine invariant and provider timers themselves (owned by IDK-403).
  - The job engine's atomicity/retry/cancel mechanics themselves (owned by IDK-401) and SSE delivery (IDK-402).
  - Any new UI surface — this ticket is integration-only; no route, state, or copy changes beyond swapping a fake for a real call.
- Data and invariants:
  - Every call site this ticket touches enqueues through `jobs`/`job_results` (IDK-401) and reads results through IDK-403's `GenerateResult`/`EvaluationResult` contracts; no call site bypasses either.
  - Generation calls at a given cache key remain single-flighted: two near-simultaneous Practice/tutor/refresher requests against the same key produce one job, not two.
  - Source retrieval writes `source_snapshots` only through the separately disclosed, explicit source-retrieval POST; no provider generation/regeneration or key-changing event fetches a source as a side effect.
- API/domain/event contracts:
  - Reuses IDK-401's job contracts, IDK-402's `GET /events`, IDK-403's provider contracts, and IDK-207's cache-key contract; source retrieval remains its own explicit POST contract and disclosure category.
  - Topic-tutor conversation turns are persisted as `learning_content` conversation entries linked to the topic, following the same schema-validated-output-only rule as generation/evaluation.
- UX routes and states:
  - `/app/topic-studio` (tutor conversation, generation/regeneration), `/app/practice`, `/app/mock`, `/app/interview-hub` (refresher generation) — states are unchanged from IDK-301/302/303/IDK-201's definitions; this ticket only makes `queued/running/succeeded/failed` reflect real work instead of a fake.
- Implementation notes:
  - This ticket should be implemented as a sequence of call-site swaps (fake → real) each covered by the integration test below, not as a rewrite of any consuming ticket's domain logic.
  - Where a consuming ticket's test (IDK-302, IDK-303) already asserts domain behavior against a fake, those tests are not duplicated here — this ticket only proves the wiring itself is correct end to end.
- Acceptance criteria:
  - A Practice submission actually produces a `provider_requests` row and a schema-validated `EvaluationResult` reaching `interview_turn_results`, with no fake/local evaluator remaining in the production call path.
  - A Mock next-turn request and final-evaluation request both traverse the real job/provider pipeline identically to Practice's evaluation path.
  - Two concurrent regenerate requests for the same topic/goal/layer/graph-version/imports-hash/template-version produce exactly one `generated_artifacts` row and one job.
  - A source retrieval never occurs as a side effect of opening a topic page, provider regeneration, or a key-changing event; it occurs only from the explicit source-retrieval POST.
- Minimum required tests:
  - Automated: Integration test — a Practice submission (or topic-tutor turn) enqueued through the real two-lane job system resolves via the schema-validated provider port and produces a cache-keyed result matching the shapes IDK-207 and IDK-403 already define; the test asserts the wiring path only (enqueue → real job claim → real provider call → validated result → visible to the caller), not the cache-key invariant or the schema-quarantine invariant themselves, which remain owned by IDK-207 and IDK-403 respectively.
  - Manual: Reviewer confirms, via the real (non-fake) provider adapter in a local configured environment, that opening a topic page performs no network call and that only an explicit regenerate action does.
  - Existing coverage reused: IDK-302's and IDK-303's domain/state-machine tests continue to cover Practice/Mock behavior against a fake evaluator/generator; they are not rerun against the live provider here to avoid non-deterministic CI dependence on a real CLI.
- Failure and recovery:
  - A provider or job failure surfaces through the same `failed-recoverable` states IDK-302/303/401/403 already define; this ticket introduces no new failure classification.
  - If source retrieval fails, the source's prior status/provenance is retained unchanged (per spec §6.5), not marked withdrawn or unavailable solely because one fetch attempt failed.
- Removal/replacement: None new — this ticket removes whatever fake/local evaluator or generator stand-ins IDK-302/303 introduced for their own testing, replacing them with the real call sites; it does not itself own deletion of any prototype UI or localStorage artifact already assigned elsewhere.
- Approval gate: Satisfied through the approved IDK-006 policy and completed IDK-403 port; deterministic fake-provider integration tests remain authoritative and no paid live invocation is required.
- Estimate: Completed with the IDK-006/403/404 implementation.

### IDK-405 — Hands-on lifecycle and static/runtime separation

- Phase: 4 — MVP AI and hands-on
- Status: Content incomplete — the hands-on lifecycle, immutable artifact revisions and static/runtime separation ship and are tested, but the three approved initial and three paired delayed hands-on scenario records from IDK-009 content revision `idk009-v1-r1` that this ticket's Scope requires loading exist nowhere outside `docs/`; every synthesized `HandsOnWork` row still hardcodes `scenario_status="fixture"`, `scenario_id=None`, and `hands_on_work` holds zero rows. IDK-503 re-run findings B10 and B12, `docs/approvals/IDK-503-content-and-safety-review-rerun-2026-08-15.md`.
- Objective: Implement the hands-on lifecycle `scenario → artifact/code/design/decision → visible rubric review → adaptive cross-question → revision → submitted evidence` with every stage and revision linked, static review always labelled static with a required non-empty limitation, and the UI visually distinguishing static analysis, compilation, and test execution, where only Submit appends evidence.
- User-visible outcome: A learner works a scenario in Topic Studio, submits an artifact for review, sees a rubric-based static review that is unmistakably labelled as static (never claiming runtime behavior), receives an adaptive cross-question, revises, and only an explicit Submit creates evidence; Run remains exploratory and never appends evidence on its own.
- PRD traceability: HND-01 (primary), HND-02 (primary), HND-03 (co-primary with IDK-503, which owns the scenario-realism review that HND-03's PRD acceptance actually names), EVAL-01 (contributing).
- Appendix H decisions: D6 (contributing — submitted hands-on evidence feeds derived learner state).
- Owning module: learning_content, evidence_evaluation, frontend.
- Dependencies: IDK-004, IDK-005, IDK-008, IDK-009, IDK-201, IDK-204, IDK-403, IDK-404.
- Scope:
  - `hands_on_work`, `hands_on_artifacts` (immutable revisions), `hands_on_reviews` (review mode, required limitation label) per spec §4.6.
  - Load exactly the three approved initial and three paired delayed hands-on scenario records from IDK-009 content revision `idk009-v1-r1`; consume IDK-204's approved rubric registry and exact canonical-topic mappings.
  - For each scenario revision that permits runner `test`, approve one versioned server-owned Java driver source/hash/reserved path/FQCN binding under IDK-005's `runner-test-driver-manifest-v1`, plus curated passing and failing artifacts proving the intended assertions; scenarios without that reviewed binding permit compile/static review only and never infer a test entry point.
  - Scenario presentation carrying role/level metadata and credible production constraints (the approved scenario set itself is IDK-009's; this ticket consumes it).
  - Scenario role-context help consumes IDK-004 `role-competency-copy-v1`; the six approved IDK-009 records map exactly to `Mid-level`/`Senior`/`Staff` without changing IDK-009 evaluator calibration.
  - Artifact submission (`Submit`) creates an immutable `hands_on_artifacts` revision and, only at Submit, an evidence candidate — `Run`/preview actions never do.
  - Static review path: a schema-validated static review result (via IDK-403/IDK-404's provider wiring) that always carries a non-empty, review-specific limitation string — never a single hardcoded global disclaimer reused verbatim across every review.
  - For an IDK-001/002-approved RDB artifact, that review-specific limitation must communicate all IDK-008 clauses: no database connection; no statement/query-plan/migration/concurrency execution; and no proof of runtime, persistence, performance, locking, or production behavior.
  - Adaptive cross-question generated from the specific submitted artifact and its review result, targeting a named gap or assumption (mirrors QPR-01's follow-up pattern but for hands-on work).
  - Revision: a new `hands_on_artifacts` row linked to the same `hands_on_work` aggregate; every stage (scenario, each artifact revision, each review, the cross-question, and the final evidence) is queryable as one linked chain.
  - UI treatment that visually distinguishes "static analysis" results from "compilation" and "test execution" results wherever a runner-produced result (IDK-406) appears alongside this ticket's static review, so a learner can never mistake one for the other.
- Out of scope:
  - The runner subprocess itself, its confirmation flow, limits, and cleanup (IDK-406) — this ticket only defines how its output is visually and semantically separated from static review, not how it runs.
  - The rubric/assessment domain mechanics themselves (owned by IDK-204); this ticket is a consumer.
  - Scenario content authoring (IDK-009's approved scenario set) and role-taxonomy wording (IDK-004); both are approved inputs rather than authored here.
- Data and invariants:
  - `hands_on_artifacts`: immutable revisions, unique `(work_id, revision_number)`; no UPDATE/DELETE path exists on a prior revision.
  - `hands_on_reviews`: `review_mode` enumerated (at minimum `static`); a static-mode row's `required_limitation_label` column is `NOT NULL` and non-empty at the database constraint level, not just at the UI layer — a static review can never be persisted without one.
  - Evidence creation is exclusively triggered by an explicit Submit action; no scheduled job, page view, or Run action may create an evidence row.
- API/domain/event contracts:
  - Hands-on Submit → creates `hands_on_artifacts` revision + evidence candidate + enqueues the static-review evaluation job (interactive lane, per D8) → `202` with `JobRef`.
  - Review result surfaces via the same `EvaluationResult` contract IDK-403 defines, with an added mandatory `limitation` field enforced non-empty for `review_mode=static`.
  - Cross-question is delivered as a follow-up `interview`-shaped turn or an equivalent `learning_content` conversation turn — reusing the existing adaptive-follow-up pattern rather than inventing a second one.
- UX routes and states:
  - `/app/topic-studio` — layer loading/empty/stale/unavailable for the scenario/context; Run has its own confirmation/running/cancel/recovery states (IDK-406's), rendered visually distinct from this ticket's static-review ready/evaluating/feedback-ready states.
  - Static and runtime results appear in visually separated regions/sections of the same page, never merged into one undifferentiated "results" block.
- Implementation notes:
  - Reuse the existing Topic Studio artifact editor (CodeMirror region) and Run/Submit button placement from `src/selected/core/CorePages.tsx`'s `Topic` component; the visual split between "Static check output" and any future runner output panel is a layout concern this ticket owns, while the runner panel's content is IDK-406's.
  - The cross-question step reuses the adaptive-follow-up delivery mechanism already built for Practice (IDK-302) rather than a parallel implementation.
- Acceptance criteria:
  - Every `hands_on_reviews` row with `review_mode=static` has a non-empty `required_limitation_label` at the database level; an attempt to write one without it is rejected.
  - Clicking Run at no point creates a `hands_on_artifacts`-linked evidence row; only Submit does.
  - A full lifecycle (scenario → artifact → static review → cross-question → revision → submitted evidence) is reconstructable as one linked chain from a single `hands_on_work` ID.
  - The rendered page never places a static-review result and a runner-produced (compile/test) result in the same visual container without a clear label distinguishing them.
  - Each test-enabled scenario revision has exactly one approved driver binding with complete curated pass/fail sources and expected result/reason; non-test-enabled revisions have none, and a caller cannot supply or override one. IDK-406 executes these pairs before activation.
- Minimum required tests:
  - Automated: Domain/component test — the exact six approved hands-on records load with their role/topic/capability/rubric/pair mappings, exact IDK-004 learner-facing metadata, and an exact zero-or-one reviewed driver binding per revision with complete pass/fail sources and expected reason; static review requires a limitation, and any approved RDB artifact limitation contains every IDK-008 semantic clause; exploratory Run appends neither artifact nor evidence while Submit does; and static/runtime regions are distinct. IDK-406 owns compilation/execution, manifest enforcement, injection, argv, and Java-only runner schema—not review wording.
  - Manual: Reviewer approves each test driver's assertions and curated pass/fail expectations, then confirms across the IDK-009 samples that no static-review limitation label is a generic string reused across unrelated scenarios (part of G4/G9 review).
  - Existing coverage reused: `tests/e2e/selected-app.spec.ts`'s "Topic Studio Run is exploratory and Submit alone appends evidence" test is REPLACED — its `learningState(page)`/localStorage evidence-length assertions are superseded by assertions against `GET /goals/{goalId}/evidence` once Submit is API-backed; the Run-vs-Submit ordering it exercises remains the intended E2E shape for the successor test.
- Failure and recovery:
  - A failed static-review evaluation job surfaces `failed-recoverable` on the submitted artifact without discarding the artifact revision itself; retry re-runs review against the same immutable revision.
  - If the runner is disabled or unapproved (IDK-406's posture), the static-review workflow described here remains fully usable — HND-02/RUN-03's "static workflow remains usable" guarantee is honored by this ticket having no runtime dependency on the runner.
- Removal/replacement: Removes the deterministic regex-based `evaluateCode()` "static checks" scorer, the hardcoded `SIMULATION_LIMITATION` string, and the `RUN_CHECKS`/`SUBMIT_CODE` reducer actions' evidence-writing behavior in `src/shared/state.tsx` and `src/shared/model.ts`, replacing them with the schema-validated static-review pipeline and per-review limitation labels described above. (The `Run` button's own execution semantics, if backed by the real runner, are IDK-406's replacement, not this ticket's.)
- Approval gate: Decision inputs are satisfied by IDK-004 decision version 1.0 and IDK-009 decision version 1.0. Implementation plus shipped scenario-realism, shared-role-copy, and limitation-label review evidence remain required before production activation or release.
- Estimate: TBD; implementation team to estimate after approval.

### IDK-406 — Controlled Java runner: confirmation, no-shell execution, limits, and cleanup

- Phase: 4 — MVP AI and hands-on
- Status: Partially implemented; execution deferred by owner decision 2026-08-14 and remains fail-closed. This status was corrected the same day after an audit found the previous wording wrong in both directions — it claimed the execution machinery was "untouched", which understated what exists, while the specific isolation primitives it named are genuinely absent.
  - Landed: the Java-only schema/contract narrowing (Alembic revision `c5b1e70a94d2`, verified by IDK-501) — `language IN ('java')` checks on `runner_confirmations`/`runner_records` with the approved transactional relational-placeholder disposal, `RunnerLanguage` reduced to `JAVA`, `Settings.runner_relational_connector` and `Settings.runner_python_command` removed, the configured-string relational detector and the Python capability branch removed, and the relational/Python OpenAPI, generated-client, and UI surfaces removed.
  - Also landed, contrary to the previous status text: a substantially complete execution service (`server/src/yuno/modules/runner/service.py`, 786 lines — `capabilities`, `validate_input`, `resolve_inputs_within_limits`, `create_confirmation`, `minimal_environment`, bounded output capture, workspace-usage limit classification, `execute_runner_job`), a real `LocalRunnerProcessPort` (`runner/adapters.py:86`) wired at `api/app.py:784`, and 24 integration tests in `server/tests/integration/test_runner.py`.
  - Genuinely absent: the root broker, cgroups, namespaces, and syscall filter. `runner/adapters.py` isolates using POSIX `resource.setrlimit` through `preexec_fn` only (`adapters.py:92-108`) — RLIMIT_CPU/AS/NPROC/FSIZE. No capability snapshot, test-driver manifest, or native exact-tuple activation evidence exists in this repository, and no CI job produces one.
  - Fail-closed is intact: `runner_enabled` defaults `False` and every `runner_*` policy value defaults `None` (`server/src/yuno/config.py:93-104`), so no learner process can start. Effective Java execution remains prohibited.
  - Deferred by owner decision 2026-08-14, recorded in `docs/runner/IDK-406-execution-deferral.md`: the broker, cgroup v2 subtree, namespaces, workspace filesystem service, and syscall filter IDK-007 requires will not be built, so execution stays disabled indefinitely. The gap is not "unbuilt" but "built to a standard IDK-007 §5 explicitly refuses" — it names `RLIMIT_NPROC`/`RLIMIT_AS`/`RLIMIT_CPU` as not accepted, and those are precisely what `runner/adapters.py:92-108` uses. The owner has accepted the resulting risk for this local single-owner deployment; that acceptance does not transfer to any hosted or multi-user context. IDK-007 and IDK-005 are unweakened — this declines to build to their bar rather than lowering it.
- Objective: Implement the confirmed, no-shell, limited, cancellable Java 21 direct compile/test runner on the exact approved IDK-005/007 policies, with deterministic platform/paired-JDK detection; Python, build-tool, and database execution absent/unsupported under approved IDK-005/008; Go Later; and effective enablement fail-closed until exact-tuple evidence passes.
- User-visible outcome: A learner explicitly confirms a Run, sees declared inputs and their hashes, watches structured ordered output stream in, can cancel the complete cgroup-owned process tree with a recorded cleanup outcome, and sees clear language that this is controlled subprocess execution — not a sandbox, hostile-code isolation, production, or AWS proof; if the runner isn't enabled, Run stays absent/disabled while Submit's static review (IDK-405) keeps working.
- PRD traceability: RUN-01 (primary), RUN-02 (primary), RUN-03 (primary), NFR-10 (primary), HND-02 (contributing — static/runtime visual separation the runner's output must support).
- Appendix H decisions: D8 (contributing — runner jobs are user-confirmed-fresh-run typed retries within the two-lane job system).
- Owning module: runner.
- Dependencies: IDK-005, IDK-007, IDK-008, IDK-401, IDK-405.
- Scope:
  - `RunnerPort`/`ProcessPort`/`TempWorkspacePort` implementations for `runner-toolchain-v1` Java compile/test as the MVP runtime capability: Ubuntu 24.04 LTS host/conventional-VM rows on `x86_64`/`arm64`, complete stable JDK `21.x`, and direct `javac`/`java` only.
  - Replace the ad-hoc schema with immutable `runner_capability_snapshots`, `runner_activation_evidence`, and `runner_test_driver_manifests`, plus exact snapshot/evidence/driver FKs from confirmations/records and the existing declared-input/output storage.
  - `GET /runner/capabilities`; `POST /runner/confirmations`; `POST /runner-runs`; `GET /runner-runs/{id}`; `POST /runner-runs/{id}/cancel`.
  - Explicit confirmation and declared input hashes required per run (`runner_inputs`: logical path, content ref/hash, declared type; no undeclared input may execute).
  - No shell; direct argv only (shared low-level subprocess utility with the provider per D7, but a separate environment/limits policy object).
  - Per-run temporary workspace; exact path/materialization grammar; empty classes/source-path directories; a fresh fixed environment excluding PATH, CLASSPATH, every Java option-injection variable, AWS credentials, and all other parent state.
  - Configuration-led runtime/toolchain detection reporting `supported / missing / incompatible` from the exact OS/architecture/host-or-VM-attestation row, one absolute JDK home and `release` file, exact full-version/implementor/architecture agreement, both executable identities, and the fixed sentinel — never PATH presence or a compiler-only prefix probe.
  - Direct compile uses the exact IDK-005 classpath/sourcepath/`--release 21 -proc:none -encoding UTF-8 -d` contract. Test uses an immutable server-owned `runner-test-driver-manifest-v1`, injects its reserved/hash-declared source, and launches its validated FQCN. IDK-405 owns approved scenario-to-driver content bindings; the caller never supplies or selects a driver.
  - `runner-limits-v1` aggregate compile+test thresholds/denials: 10-second preparation; 30-second wall and 20-CPU-second observed termination thresholds with actual observation/final values recorded; two-CPU bandwidth; 1 GiB/no-swap tree memory; 128 tasks; 100/10 MiB learner input; 256 KiB driver; 1 MiB each/2 MiB aggregate output; 16 MiB file; 256 FDs; no core; authoritative 256 MiB/10,000-entry workspace denial/classification; one active/three queued; and two-second graceful TERM/empty-tree windows.
  - One delegated parent cgroup-v2 subtree per run, with workspace-server and payload child cgroups for attribution but parent aggregate CPU/memory/pids/freeze/kill/empty proof; plus the root-owned `yuno-runner-broker-v1` service, immutable `runner-broker-service-v1` service unit (`KillMode=control-group`, one-second independent watchdog, bounded stop then hierarchy kill, `Restart=no`, nested run subtrees), and length-bounded sealed-FD request protocol; immutable `runner-runtime-view-v1` and broker-owned `runner-workspace-fs-v1` with monotonic pre-`ENOSPC` denial events; verified drop of groups/UID/GID/capabilities; private user/PID/mount/network namespaces exposing only the exact read-only JDK/runtime closure and workspace filesystem; `pivot_root`/old-root detachment; `no_new_privs`; only `/dev/null` stdin and stdout/stderr surviving exec; fixed RLIMIT defense-in-depth; and the architecture-specific immutable `runner-syscall-filter-v1` deny-by-default table. Missing/unverifiable control keeps effective enablement false.
  - Structured, totally ordered, truncated output (`runner_output_chunks`: one runner-global sequence, stream, content ref, truncation flag).
  - Cancellation/limit/disable/shutdown repeatedly enumerates the verified cgroup and sends pidfd SIGTERM to every member, including `setsid` descendants; after the two-second grace it uses `cgroup.kill` plus pidfd SIGKILL fallback, proves `populated=0`, then performs symlink-safe workspace/cgroup removal with recorded cleanup outcome.
  - UI/domain distinguishes compile vs. test vs. static phases explicitly (`RunnerResult` carries separate compile/test/static phases).
  - An explicit "not a sandbox / not hostile-code isolation / not production or AWS proof" statement surfaced wherever a run result appears.
  - Learner Python, Maven, Gradle, Ant, wrappers, external dependencies, and every other unapproved build mode are absent/rejected with the exact IDK-005 diagnostics; ambient installation never creates a capability.
  - Relational/database execution is absent under `database-exercise-posture-v1`. Capability/confirmation/run contracts contain no relational value or compatibility path; the exact retired `POST /runner/confirmations` `"language":"relational"` signature receives the standard `422` Java-only schema response before route/UoW and creates no persistence, probe, job, broker, process, socket, artifact mutation, or evidence action. Subject to content approval, RDB static review remains available under IDK-405/302's review-specific no-connection/no-runtime-proof clauses.
  - Go absent entirely from the capability set and code path (RUN-04 is Later; no inactive UI control anticipates it).
  - If runner posture is not approved/enabled, `/app/topic-studio`'s Run affordance is absent or disabled while Submit (IDK-405's static review) remains fully usable.
  - Settings desired/effective enablement and `runner-risk-ack-v1`; every run separately uses single-use five-minute `runner-run-confirmation-v1`. Policy/evidence change, disable, or safety suspension revokes enablement with no automatic recovery.
  - Retry of a failed/cancelled runner job requires a fresh user confirmation and fresh declared-input hashes (D4's user-confirmed-fresh-run typing) — never a silent re-run of stale inputs.
- Out of scope:
  - Static review content/rubric and the Submit/evidence pipeline (IDK-405).
  - The CLI provider's own environment allowlist and timers (IDK-403) — the runner keeps a separate, distinct minimal allowlist per D7.
  - Every learner-supplied or product-managed database connector, database endpoint/credential, driver/parser, server/instance lifecycle, database process/socket, and Java network exception. IDK-008 v1 approves absence, not a connector seam.
- Data and invariants:
  - `runner_capability_snapshots`: immutable policy/build-mode, state/diagnostic, safe platform/tool identity, probe/expiry, environment/limits versions. `runner_activation_evidence`: immutable unique exact tuple plus compile/test/limit/cancel/cleanup evidence and approval. `runner_test_driver_manifests`: immutable approved scenario revision, reserved source/hash, FQCN, and review basis.
  - `runner_enablements`: desired/effective state, current risk acknowledgement plus bound policy/evidence revisions, optimistic revision, transition timestamps/reason. `runner_limit_snapshots`: immutable exact v1 values. `runner_safety_suspensions`: cleanup trigger/classification and reviewed reset basis. API-private `runner_cleanup_intents`: safe cgroup/workspace identities, retry/escalation schedule, separate empty-tree/workspace/cgroup outcomes, safe diagnostic, suspension and reset references. Immutable `runner_runtime_view_manifests`, `runner_workspace_fs_manifests`, and `runner_syscall_filter_manifests` record mounted-object identity, filesystem implementation/event contract, and architecture-specific syscall action table/hash referenced by activation evidence.
  - `runner_records`: job, owner/goal/artifact revision, confirmation, capability-snapshot/activation-evidence/test-driver references, fixed Java/build-mode identity, argv JSON, environment/limits versions, PID/PGID/temp path, state/outcome/cleanup. Java is the only language; Python, relational/database, and Go are removed from enums/checks/OpenAPI.
  - `runner_inputs`: unique per runner/logical-path; no run executes against an input that isn't a declared, hashed row here.
  - `runner_output_chunks`: unique `(runner, sequence)` with `stream` as payload, giving one total capture order. The truncation flag is set only for stdout/stderr capture truncation; filesystem/file/FD denial does not invent output truncation.
  - No AWS credential, secret, connection string, broker/control descriptor, host mount, or setup privilege is ever present in the learner process environment/view, verified by explicit negative/native tests rather than documentation alone.
  - `cleanup-complete` requires an empty/removed cgroup and absent workspace. Unverifiable identity/tree/reference or failed removal persists cleanup intent plus safety suspension, cancels runner work, and blocks execution until reviewed reset.
- API/domain/event contracts:
  - `GET /runner/capabilities` → Java `direct-jdk-v1` `supported/missing/incompatible` plus separate top-level `enabled`, fixed disabled diagnostic/message, policy/environment/limits versions, and safe normalized platform/JDK fields. Free-form `detail`, raw paths/output/hashes/evidence references, and Python are absent.
  - `GET /runner/enablement`; version-checked `POST /runner/enablement` with `accepted=true`/`runner-risk-ack-v1`; idempotent `DELETE /runner/enablement` durably disables/cancels without waiting for cleanup. Safety recovery/reset has no HTTP endpoint: the offline `yuno.runner_admin` command accepts an existing intent ID but no paths/PIDs, holds the runner-admin lease, exposes fixed safe classifications, and resets only after verified reconciliation plus recorded local-operator review.
  - `POST /runner/confirmations` → accepts goal/work/scenario revision, optional submitted artifact revision, operation, declared learner inputs/hashes, and acknowledgement only. An exploratory draft is snapshotted in confirmation inputs without creating an artifact/evidence; a supplied immutable artifact must match. Server resolves Java/build mode/driver and records snapshot/evidence/driver before a run.
  - `POST /runner-runs` → `202 JobRef` (runner-lane job, D8's "user-confirmed fresh run" retry typing); `GET /runner-runs/{id}` for status; `POST .../cancel` targets the complete verified cgroup tree, transitioning toward the cleanup states.
  - `RunnerSpec`/`RunnerResult` per spec §5.3 exactly: confirmation; language/capability; declared inputs and hashes; direct argv; working-directory policy; environment-policy and limits versions; compile/test/static phases; exit/signal/limit state; structured stdout/stderr refs and truncation; duration; cleanup state; explicit limitation.
- UX routes and states:
  - `/app/topic-studio` Run region — `pending-confirmation, queued, preparing, running, cancel-requested, completed, failed, timed-out-or-limited, cancelled, cleanup-pending, cleanup-complete/cleanup-failed` (Appendix D runner states).
  - `/app/jobs` surfaces runner jobs identically to other job kinds (read-only from this ticket's perspective; IDK-401 owns the jobs view itself).
  - When runner is disabled/unapproved: the Run control is absent or explicitly disabled with a stated reason; no inactive placeholder control ships ahead of enablement.
  - `/app/settings` renders IDK-007's exact enablement dialog; every Topic Studio Run renders exact files/driver/argv/limits plus an unchecked confirmation. Re-acknowledgement, capacity, limit, cancel, cleanup, reconciliation, and safety-suspension states use fixed copy.
- Implementation notes:
  - Runner and provider share only the low-level direct-argv spawn/stream-capture primitives per D7. The runner's cgroup/pidfd/namespaces/mount/syscall-filter/termination policy is a separate implementation and never falls back to the provider's process-group kill boundary.
  - IDK-406 supplies a runner lifecycle hook registered with the durable dispatcher/composition root: startup runner reconciliation completes before runner-job admission, and shutdown first stops runner admission, cancels queued work, drains/kills the active cgroup, and persists cleanup before generic worker/database shutdown proceeds. Hook failure keeps the runner suspended while static application startup remains available; shutdown does not release runner ownership until cleanup state is durable.
  - Capability GET may use IDK-005's bounded 60-second cache keyed by policy, platform/attestation, configuration revision/home fingerprint, and nullable two-tool identities with absent sentinels; settings changes invalidate atomically. Confirmation probes afresh; enqueue verifies the snapshot; the worker verifies executable identity and the sentinel immediately before learner execution. Every probe uses the fresh stripped environment; replacement/removal fails without learner execution.
  - Replace threaded `subprocess` `preexec_fn` with the administrator-installed, root-owned broker and dedicated Linux launcher boundary: resolve immutable policy by run ID, validate sealed descriptors/manifests, create cgroup/namespaces/mount view, drop every setup privilege/control FD, then use descriptor-bound execution without path re-resolution. Do not keep the obsolete threaded-spawn path as a fallback.
  - Remove `RLIMIT_NPROC`/`RLIMIT_AS`/`RLIMIT_CPU`, direct-child `wait4` accounting, process-group-only cleanup, polling-only storage enforcement, inherited PATH, and one-shot `rmtree`; replace them with IDK-007's broker/cgroup/pidfd/namespaces/quota/syscall-filter/reconciliation policy. RLIMIT file/FD/core remains defense-in-depth only and handled file/FD denial is not misreported as a terminal limit.
- Acceptance criteria:
  - A run cannot start without a prior `POST /runner/confirmations` referencing the exact declared input hashes later used at `POST /runner-runs`.
  - No run's constructed environment contains an AWS credential variable, verified by an explicit fake-`ProcessPort` assertion.
  - Cancelling a running job terminates every verified cgroup member, including children that fork and call `setsid`, proves `populated=0`, and always reaches `cleanup-complete` or durable `cleanup-failed`/safety suspension — cleanup is never left unrecorded.
  - A simulated limit breach ends the run and returns a structured `timed-out-or-limited` result rather than hanging or silently truncating without the truncation flag.
  - With the runner disabled, `/app/topic-studio`'s Submit/static-review workflow (IDK-405) completes successfully with no Run-dependent code path invoked.
  - Retrying a failed/cancelled runner job is rejected without a fresh confirmation and fresh input hashes.
  - Java compatibility reports `supported` only after the exact probes pass; top-level `enabled` stays false unless the exact platform/JDK/executable tuple has approved compile/test, limit, cancel/process-tree, and cleanup evidence and IDK-007's complete posture passes.
  - Maven/Gradle/wrapper/Python requests and a scenario without an approved test-driver identity are rejected before confirmation; no learner process starts. The exact retired `POST /runner/confirmations` `"language":"relational"` signature fails ordinary Java-only schema validation before route/UoW and creates zero socket/process/record/artifact-mutation/evidence effects.
  - Running an unsubmitted editor draft creates only confirmation/run/input/output records and zero `hands_on_artifacts` or evidence rows.
  - Manual disable durably stops admission and cancels/drains queued/live work. Startup reconciliation completes before enablement; shutdown drains before worker/database stop. Cleanup failure suspends immediately and remains visible/retried.
- Minimum required tests:
  - Automated: **PRIMARY** runner matrix/threat-model suite (domain/integration, per spec §10.1) — every platform/JDK/enablement/acknowledgement/disabled/limit/message fixture; probe-only versus in-run sentinel classification; cache/state-nullability rules; immutable snapshots/evidence/drivers/broker/runtime/workspace/filter/cleanup manifests; curated drivers; path/environment/final-exec races; exact argv and unsupported modes; relational absence plus the exact retired `POST /runner/confirmations` `"language":"relational"` `422` validation precedence and no settings/schema/OpenAPI/UI/socket/process/record mutation; static-review independence (content wording stays IDK-405/302-owned); Settings enable/disable/revoke and five-minute confirmation; hard-controller/input/capture/workspace boundary/+1 cases; recorded wall/CPU observation/watchdog behavior; handled `ENOSPC` still triggers exact workspace classification while filesystem/event failure suspends; file/FD denial has no false classification; real cgroup CPU/memory/task events; root-broker protocol, privilege drop/control-FD absence, private namespace/sole-writable-workspace/runtime-view identity and syscall-filter bypass tests; descendants ignoring TERM/`setsid`; broker crash/SIGKILL/deadlock/control-loss independent hierarchy kill; cancellation/disable/shutdown/crash/lifecycle-hook races; empty-tree cleanup/retry/suspension/offline reset; and static fallback. No other ticket duplicates it.
  - Manual: Security/engineering reviewer inspects the root-owned broker/service/delegation, descriptor-bound launcher, runtime/filter manifests, privilege drop, cgroup/pidfd/namespaces/mount/quota/syscall-filter/environment path, offline recovery reset, and exact disclosures; per-exact-tuple Ubuntu evidence covers every enforceable limit/denial, cgroup-tree cancellation, host-write/socket denial, crash reconciliation, and cleanup (contributes to G7 review).
  - Existing coverage reused: None — no prior test exercises a real Java subprocess runner; the prototype's `evaluateCode()` regex scorer (removed by IDK-405) never executed a process at all.
- Failure and recovery:
  - A missing/incompatible toolchain surfaces as a capability-report state before enqueue. If identity changes after enqueue, the worker records a safe recoverable capability failure and executes no learner code.
  - A cleanup failure (e.g., orphaned process, unremovable temp directory) is recorded as `cleanup-failed` and surfaced as a residual-risk notice, per Appendix C's "OS failures may require manual recovery" residual statement — never silently hidden.
  - If runner posture is disabled after being enabled, in-flight runs are cancelled through the same cgroup-empty-then-cleanup path; no run is abandoned mid-flight.
- Removal/replacement: Remove settings `runner_javac_command`, `runner_java_command`, `runner_java_version_prefix`, `runner_python_command`, and `runner_relational_connector`, replacing the Java settings with one absolute `runner_jdk_home` plus the approved host/VM attestation. Remove `RunnerLanguage.PYTHON` and `RunnerLanguage.RELATIONAL`, both DB-check/migration members and generated OpenAPI/types, raw-path `runner_records.toolchain`, the PATH/compiler-prefix detector and fixtures, threaded `preexec_fn`, first-source entry inference, the configured-string relational detector, and all relational UI/configuration compatibility paths. The Java-only schema revision transactionally deletes non-authoritative relational placeholder confirmation/runner rows, exclusively owned bodies/inputs/outputs, and linked `kind='runner'` job/result/attempt/event subgraphs whose logical references target the placeholders. It preserves unrelated jobs and all goals, artifacts, and evidence, proves that no surviving logical reference dangles, and never relabels or archives removed rows. IDK-405 separately removes `evaluateCode()`/`RUN_CHECKS`. No obsolete path remains as a fallback.
- Approval gate: The ordered decision inputs are satisfied by IDK-005 decision version 1.0 (OS/toolchain/build mode), IDK-007 decision version 1.0 (enablement/limits/network/termination/cleanup), and IDK-008 decision version 1.0 (database execution absent). Implementation, exact-tuple native Java evidence, verified database absence/rejection, and shipped threat-model review remain mandatory before effective enablement or learner execution.
- Estimate: TBD; implementation team to estimate after approval.

### IDK-407 — Atomic canonical v2 publication and opt-in merge

- Phase: 4 — MVP AI and hands-on
- Status: Complete
- Objective: Publish a second approved canonical graph version through the same offline tooling as IDK-102, and deliver the opt-in, always-recomputed base→latest canonical-update diff/merge flow at `/app/canonical-updates` with atomic acceptance moving the goal's version pin.
- User-visible outcome: A learner sees a published curriculum update as an inspectable diff naming impacts, selects changes, resolves each conflict (overlay-wins pre-selected and explained, never silently applied), sees archived-local-topic entries for any topic upstream removed while carrying their evidence/overlay state, and only after explicit confirmation does the goal's version pin move — with postpone/dismiss leaving the goal completely unchanged.
- PRD traceability: CUR-04 (primary), CNT-01 (contributing), CNT-02 (contributing).
- Appendix H decisions: D1 (v2 publication), D9.
- Owning module: canonical, roadmap, audit_observability, frontend.
- Dependencies: IDK-102, IDK-106, IDK-201, IDK-101.
- Scope:
  - Run the offline publish tooling built by IDK-102 a second time to produce an approved v2 `canonical_graph_versions` row with its own `EditorialApproval`, immutable once approved, exactly like v1.
  - `canonical_merge_proposals` and `merge_items` per spec §4.4: the diff is always current-goal base → latest approved version, never chained through an intermediate version even when more than two versions exist.
  - `GET /goals/{goalId}/canonical-update` — computes/returns the current base→latest diff, impacts, and per-item conflict/resolution state.
  - `POST /canonical-update-proposals/{id}/decision` — postpone/dismiss; the goal's version pin and overlay remain byte-for-byte unchanged.
  - `POST /canonical-update-proposals/{id}/accept` — one transaction: moves the goal's single graph-version pin, writes every per-conflict resolution AND every unselected-change retention as target-version `overlay_entries`, closes the proposal, invalidates roadmap/generated-content/import/search projections, and writes an audit event.
  - Overlay-wins is the pre-selected, explained default resolution for every conflict; nothing is applied without the learner reaching the explicit confirmation step.
  - Upstream-deleted topics carrying learner evidence or overlay state become an explicit "archived local topic" overlay entry rather than disappearing.
  - Any stale target version, any unresolved conflict, or any write failure during acceptance rolls back the entire transaction — the goal remains pinned to its prior version with zero partial writes.
  - Adoption of the new pin triggers IDK-203's reprocessing of previously unmapped import statements for the goal (per D10); this ticket triggers that job at the correct moment and does not reimplement the mapping logic itself.
- Out of scope:
  - The curriculum content of v2 itself (governed by IDK-001/IDK-002's editorial process feeding the same IDK-102 tooling).
  - Import statement re-mapping logic (IDK-203) — this ticket only triggers reprocessing at graph adoption.
  - Generated-content regeneration mechanics (IDK-207/IDK-404) — this ticket only flips the relevant cached artifacts' D3 staleness flag as part of projection invalidation.
- Data and invariants:
  - `canonical_merge_proposals`: unique active target proposal per goal; base/target versions always resolve to two approved, immutable `canonical_graph_versions` rows.
  - `merge_items`: acceptance requires every item to carry a complete resolution (selected flag plus chosen resolution) before the transaction may commit — a proposal with any item lacking a resolution cannot be accepted.
  - `overlay_entries` written at acceptance are typed `merge resolution` or `archived local topic` and reference the target graph version, never the base version.
  - `goal_workspaces`' single graph pin moves exactly once per successful acceptance transaction; a concurrent acceptance attempt against a stale base returns `409` and the transaction never partially commits.
- API/domain/event contracts:
  - `GET /goals/{goalId}/canonical-update` → `200` with the current diff, or `empty` if the goal is already pinned to the latest approved version.
  - `POST /canonical-update-proposals/{id}/accept` → `200` on success (pin moved; background invalidation jobs enqueued for roadmap/content/import/search projections) or `409 proposal_stale` / `409` naming the unresolved conflicts on failure — no partial pin move under any failure path.
  - `POST /canonical-update-proposals/{id}/decision` (postpone/dismiss) → `200`; goal state, pin, and overlay are unchanged; the decision itself is the only new persisted fact.
- UX routes and states:
  - `/app/canonical-updates` — `proposed/awaiting/conflict-needs-resolution/accepted/postponed/dismissed/stale` (Appendix D overlay/diff states); sticky desktop action region becomes a normal in-flow mobile action region; fieldsets/radios explain the consequence of each conflict resolution choice.
  - On acceptance, `/app/learn-roadmap` reflects the new pin's projection on next load (`stale-canonical-version` clears); any in-flight generated-content view shows the D3 staleness indicator until regenerated.
- Implementation notes:
  - Reuse the existing `CanonicalUpdatesPage` layout, copy, and interaction order from `src/selected/operations/OperationalPages.tsx` (diff rows, per-conflict radio resolution, approval checkbox, sticky accept/postpone/dismiss/select-all actions) exactly; only the persistence and the transaction boundary move server-side.
  - "Select all" and per-row selection remain client-side draft state until the explicit Accept action submits the final selection — no partial selection is persisted mid-review.
- Acceptance criteria:
  - With two approved versions (v1, v2) and a goal pinned to v1, `GET /goals/{goalId}/canonical-update` returns a diff computed directly v1→v2, never through an intermediate hypothetical version.
  - Accepting a proposal with an unresolved conflict is rejected before any write occurs; the goal's pin, overlay, and proposal state are all unchanged after the rejected attempt.
  - A successful acceptance is one transaction: the pin, every conflict-resolution overlay entry, every unselected-change retention overlay entry, the proposal's closure, and the audit event either all commit or none do (a simulated mid-transaction failure proves full rollback).
  - An upstream-deleted topic carrying evidence appears as an "archived local topic" overlay entry after acceptance, not as a silently vanished roadmap row.
  - Postpone and dismiss leave the goal's pin, overlay, and roadmap projection byte-identical to before the decision.
- Minimum required tests:
  - Automated: Domain/integration test — the two-version merge fixture (approved v1/v2, an overlay conflict, and an upstream-deleted topic carrying local state, per spec §6.1's MVP fixture list) exercising: base→latest (never chained) diff computation, overlay-wins pre-selection, rejection of acceptance with any item unresolved, the archived-local-topic entry for the deleted topic, one-transaction pin-move-plus-resolutions-plus-invalidation-plus-audit on success, full rollback (pin unchanged) on a simulated write failure, and that a successful acceptance enqueues IDK-203's unmapped-statement reprocessing job for the goal (proving the D10 re-mapping-on-adoption trigger actually fires). This is the primary atomic-canonical-merge test for the codebase; no other ticket duplicates it.
  - Manual: Reviewer walks the full accept flow end to end against the two-version fixture and confirms the impact/conflict copy matches the approved wording and that overlay-wins is visibly pre-selected with its consequence explained before the approval checkbox can be checked.
  - Existing coverage reused: `tests/e2e/selected-app.spec.ts`'s "canonical curriculum updates stay pending until an explicit acceptance action" test is REPLACED — its `operationsState(page)`/localStorage assertions (`goalVersion`, `acceptedUpdates`, `acceptedConflictResolution`) are superseded by assertions against `GET /goals/{goalId}/canonical-update` and the goal's real graph pin once this ticket ships; the interaction ordering it exercises (pending → per-row selection → conflict resolution → explicit approval checkbox → Accept → pin moves → reload preserves the decision) remains the intended E2E shape for the successor test.
- Failure and recovery:
  - A stale-version race (the pin already advanced) returns `409 proposal_stale`; the client is guided to re-fetch the recomputed diff rather than retry the same stale proposal.
  - Any failure during the atomic acceptance transaction leaves the goal pinned to its prior version with no partial overlay entries — verified by the rollback test above.
- Removal/replacement: Removes the prototype localStorage `goalVersion` / `acceptedUpdates` / `acceptedConflictResolution` canonical-update simulation and the static `UPDATE_ROWS` diff-content fixture in `src/selected/operations/OperationalPages.tsx`, replacing it with the atomic, server-persisted D9 merge flow described above.
- Approval gate: None blocking this ticket's own mechanics (CUR-04 carries no G-gate in spec §10.2, and the two-version fixture required by D1/CUR-04 is explicitly permitted as MVP-fixture content rather than requiring the full approved curriculum spine). G1/G2 (curriculum spine, editorial policy) govern the real content of any production v2, not the merge mechanism this ticket delivers.
- Estimate: TBD; implementation team to estimate after approval.

### IDK-408 — FTS5 search with owner/goal isolation and stale fallback

- Phase: 4 — MVP AI and hands-on
- Status: Complete
- Objective: Deliver SQLite FTS5 search over approved canonical topic/content, owned generated content, notebook, and eligible evidence metadata, with every result joined to `search_documents` for owner/goal filtering, idempotent background projection writes, an explicit stale-index state with deterministic owned-row fallback, and rebuild-then-switch semantics that never activate a partial projection.
- User-visible outcome: A learner searches their own goal's content and never sees another owner's or another goal's material; when the index is stale or unavailable, results still return from a deterministic, clearly labelled "degraded" fallback rather than silently going empty or leaking unfiltered rows; a rebuild in progress never surfaces a half-built result set.
- PRD traceability: SYS-02 (primary), NFR-08 (contributing).
- Appendix H decisions: None.
- Owning module: search, frontend.
- Dependencies: IDK-201, IDK-204, IDK-206, IDK-101.
- Scope:
  - `search_documents` (ACL/ownership source table: entity type/ID, owner/goal/version/topic, title/body/tags, projection version, updated time), `search_index_state` (projection name PK, version, status, source watermark, job/failure refs, timestamps), `search_fts` (FTS5 virtual table over `search_documents` as external content).
  - Indexing scope: approved canonical topic/content, owned `generated_artifacts`, `notebook_entries`, and eligible `evidence` metadata only.
  - Explicit exclusion from indexing by default: tombstoned evidence payloads, `schema_quarantines` output, raw provider context, `runner_output_chunks`, and unreviewed `import_statements`/originals.
  - `GET /search?q=&goal_id=&types=` — every returned row is produced by joining `search_fts` results back to `search_documents` and filtering on the resolved owner and the requested `goal_id`; no query path returns an FTS hit that has not passed this join/filter.
  - `POST /search-index/rebuild`; `GET /search-index/status` — rebuild is an idempotent background job (safe to run repeatedly with the same net effect), writing a new projection generation and switching the active generation only after the rebuild fully succeeds; a failed or partial rebuild never becomes the active projection.
  - `stale-index` state surfaces the source watermark it was built from and current rebuild status.
  - Deterministic fallback: while stale/unavailable, search queries owned projection *source* rows (not the FTS index) directly, in a stable order, and every result is labelled degraded.
- Out of scope:
  - The content of what gets indexed (owned by the modules producing canonical content, generated artifacts, notebook entries, and evidence themselves) — this ticket only builds and maintains the projection over already-existing rows.
  - Ranking/relevance tuning beyond SQLite FTS5's built-in matching; no vector or semantic search is introduced.
- Data and invariants:
  - `search_documents`: every row carries `owner_id` and, where applicable, `goal_id`; this table — not `search_fts` — is the authoritative ACL source, so every read path joins through it.
  - `search_fts`: FTS5 with `search_documents` as external content; a raw FTS match on title/body/tags without the accompanying `search_documents` join can never be returned to a client.
  - `search_index_state`: single row per projection name; `status` transitions `ready → stale → rebuilding → ready|failed`; the active generation pointer flips only on a fully successful rebuild — a rebuild that fails partway leaves the previously-active generation serving traffic unchanged.
  - Projection writes (indexing a new/changed source row) are themselves idempotent background jobs: re-running the same projection job for the same source row produces the same net index state, not a duplicate.
- API/domain/event contracts:
  - `GET /search?q=&goal_id=&types=` → `200` with `results`/`empty`, or a degraded result set explicitly flagged when serving from the stale-index fallback.
  - `POST /search-index/rebuild` → `202 JobRef` (background lane); `GET /search-index/status` → `200` with `ready|stale|rebuilding|failed` plus source watermark.
- UX routes and states:
  - `/app/search` — `empty/results/stale-index/rebuilding/unavailable/failure`; when stale, the UI labels degradation explicitly and still returns useful (owned, correctly filtered) results rather than an empty state; the search form and status announcement remain keyboard-accessible.
- Implementation notes:
  - Reuse the existing `SearchPage` layout and interaction (`src/selected/operations/OperationalPages.tsx`) — query box, submit, result list — but replace `SEARCH_ITEMS`/local `learning.evidence` filtering with the `GET /search` contract above; the unconditional "Bundled index may be stale" notice becomes the real `search_index_state`-driven stale banner.
  - The owner/goal join is enforced at the repository layer via a single shared query helper, not re-implemented ad hoc per result type, so a future indexed entity type cannot accidentally skip the ACL join.
- Acceptance criteria:
  - A search executed as one owner/goal never returns a `search_documents` row belonging to a different owner or a different goal, even when the underlying FTS5 match itself would have matched the text.
  - A tombstoned evidence payload, a `schema_quarantines` row, raw provider context, runner output, or an unreviewed import original never appears in any search result by default.
  - While `search_index_state.status = stale` or `unavailable`, `GET /search` still returns correctly filtered, stably ordered results sourced directly from `search_documents`, each labelled degraded.
  - A rebuild that fails partway through leaves the previously active FTS generation serving unchanged, correct results; only a fully successful rebuild switches the active generation.
  - Running the same projection job twice for an unchanged source row leaves `search_documents`/`search_fts` in the same state as running it once.
- Minimum required tests:
  - Automated: Repository/integration test — FTS query results are reachable only via the `search_documents` join and filtered by owner_id/goal_id (a planted second-owner and second-goal matching row never appears in a scoped query's results), and the stale-index fallback returns deterministic, degraded-labelled, owner/goal-filtered results directly from `search_documents` when `search_index_state.status != ready`. This is the primary owner/goal search-isolation test for the codebase; no other ticket duplicates it.
  - Manual: Reviewer confirms the `/app/search` stale banner shows the real source watermark and rebuild status rather than an unconditional static notice, across a rebuilding and a healthy state.
  - Existing coverage reused: The existing Playwright suite exercises only `/app/search`'s heading render as part of the generic 14-route test; that render assertion is reused as-is. The bundled-fixture search behavior itself has no prior dedicated test to replace.
- Failure and recovery:
  - A rebuild job failure marks `search_index_state.status = failed` with a diagnostic reference and retries per IDK-401's idempotent-rerun retry typing for indexing jobs; the prior active generation continues serving search traffic throughout.
  - An entirely unavailable search backend (e.g., during a migration) surfaces `unavailable` with a retry/rebuild action, never a fabricated empty-but-successful result.
- Removal/replacement: Removes the bundled `SEARCH_ITEMS` fixture search and its always-on "Bundled index may be stale" notice in `src/selected/operations/OperationalPages.tsx`, replacing both with the real `search_documents`/`search_fts`/`search_index_state`-backed query and status described above.
- Approval gate: None. SYS-02 carries no approval-gate marker in spec §10.2; the projection, ownership-join, and stale/degraded-fallback mechanics are fully specified and self-contained.
- Estimate: TBD; implementation team to estimate after approval.

### IDK-409 — Settings, disclosure-gated network, durable export/delete, and redacted logging

- Phase: 4 — MVP AI and hands-on
- Status: Complete — implemented by `d57d7e7`, enforced against IDK-010 policy version 1.0 by `20f0ea4`, export activated by `dc5267f`
- Objective: Deliver `/app/settings` covering global profile, goal settings, imports, provider/network disclosure, review, accessibility, progress display, versioned export, and destructive delete as durable jobs, with disclosure acceptance gating the first network enqueue, an immutable unchanged-at-confirmation delete impact snapshot, truthful (never fabricated) export representation of unavailable/tombstoned content, and structured, redaction-compliant local logs.
- User-visible outcome: A learner edits profile/goal/accessibility/progress-display/review settings with changes persisting and their effect visible; before any provider or source network call happens, they have explicitly accepted a disclosure; requesting export or delete shows real job progress and an accurate impact preview naming what will be affected before they confirm; a changed impact since the last preview forces a fresh preflight rather than silently proceeding.
- PRD traceability: SET-01 (primary), NFR-04 (primary), NFR-06 (primary), PRV-01 (contributing), PRV-02 (contributing).
- Appendix H decisions: D5, D7 (contributing).
- Owning module: settings_data, audit_observability, provider, frontend.
- Dependencies: IDK-010, IDK-101, IDK-104, IDK-403.
- Scope:
  - `owner_settings` (accessibility JSON, `progress_display`, `provider_selection`, `row_version`), `network_disclosures`, `export_operations`, `delete_operations` per spec §4.2.
  - `GET/PATCH /settings` — versioned writes using `row_version`/`If-Match`; a stale write is rejected (`412`) rather than silently overwriting a concurrent change.
  - Profile, goal settings, imports summary/link, provider/network disclosure status, review preferences, accessibility (reduced motion, etc.), progress display (detailed/simple — presentation-only, per D6, never deleting underlying data), export, and delete, matching the existing `SettingsPage` sectioned layout.
  - `POST /disclosures/{category}/accept` / `.../revoke` surfaced here as the Settings-side entry point to the disclosure gate IDK-403 enforces at enqueue; acceptance is recorded before this ticket allows any Settings action that would trigger a first network-affecting job.
  - `POST /exports`; `GET /exports/{id}` — export is a durable background-lane job producing a documented, versioned package named from the approved product name **Yuno** (the package's exact format, version scheme and filename convention remain IDK-010's to settle; only the product name is decided); unavailable or tombstoned content is explicitly represented as unavailable in the export, never fabricated or silently omitted without a marker.
  - `POST /goals/{goalId}/delete-preflight`; `POST /goals/{goalId}/delete` — preflight produces an immutable impact snapshot naming cross-goal evidence tombstones and dependent LearningState downgrades (the tombstone/downgrade mechanics themselves are IDK-108's; this ticket owns the settings-side preflight/confirm/execute flow and the snapshot's unchanged-at-confirmation guarantee); a snapshot that no longer matches current state at confirmation time is rejected and a new preflight is required.
  - Structured local logs correlating request/correlation/owner/goal/job/provider-request/runner IDs, applying the spec §8.5 redaction categories (credentials/tokens/cookies/authorization headers; provider auth environment values; AWS keys/connection secrets; unrelated environment variables; avoidable absolute user paths/usernames; raw prompt/transcript/artifact bodies in ordinary logs; quarantined raw output).
  - Learner-visible failure records link to a safe diagnostic classification rather than a raw stack trace or internal detail.
- Out of scope:
  - The provider disclosure gate's own enforcement at enqueue and the CLI adapter itself (IDK-403) — this ticket surfaces and records acceptance/revocation; IDK-403 enforces it.
  - The tombstone/downgrade domain mechanics and their atomicity (IDK-108) — this ticket owns the Settings-facing preflight/confirm/execute flow and snapshot-freshness check, not the tombstone algorithm.
  - Choosing the export package format/version, transcript-inclusion rules, delete recovery window, backup posture, log retention duration, or support-access model — all fixed by IDK-010 policy version 1.0; this ticket implements those approved values and invents none of its own.
- Data and invariants:
  - `owner_settings.row_version` increments on every successful `PATCH /settings`; a PATCH carrying a stale `If-Match` is rejected, never silently merged.
  - `network_disclosures`: unique `(owner, category, disclosure_version)`; an accepted disclosure's `accepted_at` timestamp must precede the timestamp of the first job enqueue it gates — verified, not merely documented.
  - `delete_operations.impact` snapshot is written once at preflight and is immutable; the confirm step re-derives the current impact and compares it against the stored snapshot — any difference forces a new preflight rather than proceeding with a stale snapshot.
  - `export_operations` records a format-version field on every export; nothing in the exported package is ever synthesized to fill a gap where source data is unavailable or tombstoned — the package instead marks that field as unavailable.
  - Structured logs never contain a raw prompt, transcript, artifact body, or quarantined raw output — those remain referenced by secure ref/hash only, matching IDK-403's `provider_requests`/`schema_quarantines` handling.
- API/domain/event contracts:
  - `GET/PATCH /settings` → `200`; `412` on stale `If-Match`; `422` on an invalid setting value → `invalid-setting` UI state.
  - `POST /exports` → `202 JobRef`; `GET /exports/{id}` → `running/complete/failed` with a version field always present.
  - `POST /goals/{goalId}/delete-preflight` → `200` with the immutable impact snapshot; `POST /goals/{goalId}/delete` → `202 JobRef` only when the submitted snapshot reference matches the current one, else `409` requiring a new preflight.
  - `POST /disclosures/{category}/accept` / `.../revoke` → `200`; a subsequent enqueue attempt for a revoked category returns `412` per IDK-403's gate.
- UX routes and states:
  - `/app/settings` — `invalid/saved; provider unavailable; export running/failed/complete; delete preflight/confirmation/running/failed/complete`; impact preview names cross-goal evidence tombstones explicitly; dialogs restore focus on close; OS and in-app reduced-motion preferences are both respected.
- Implementation notes:
  - Reuse the existing `SettingsPage` section layout, headings, and copy structure from `src/selected/operations/OperationalPages.tsx` (owner profile, progress display, optional review, accessibility, imports link, providers/network, local data) exactly; replace each section's read/write with the corresponding OpenAPI hook and remove the two destructive local-only actions named below.
  - The delete confirmation dialog reuses the existing focus-restoring `AlertDialog` pattern already present for "Delete imports," extended to require an unchanged impact-snapshot reference rather than a bare confirm click.
- Acceptance criteria:
  - A `PATCH /settings` sent with a stale `row_version`/`If-Match` is rejected and the stored settings are unchanged.
  - No provider- or source-network-affecting job can be enqueued for a category whose disclosure has not been accepted (verified as an integration path through this ticket's Settings UI into IDK-403's gate, not a re-test of the gate's own unit behavior).
  - A delete confirmed with an impact snapshot that no longer matches current state (because something changed between preflight and confirm) is rejected and requires a fresh preflight before it can proceed.
  - A completed delete produces the evidence tombstones and dependent-state downgrades named by its impact snapshot, plus an audit event, atomically (mechanics verified by IDK-108's own test; this ticket verifies the Settings-side flow only reaches that atomic operation with a fresh snapshot).
  - An export of a goal containing a tombstoned evidence item represents that item as explicitly unavailable in the package, never omitted without a marker and never filled with fabricated content.
  - A sampled structured log entry from a provider-backed action contains no credential, token, AWS key, unrelated environment variable, raw prompt/transcript body, or quarantined raw output.
- Minimum required tests:
  - Automated: Integration test — (0) a successful `PATCH /settings` persists each setting category and the new value is returned by a subsequent `GET /settings` with an incremented `row_version`, proving SET-01's "changes persist locally and expose their effect"; (1) a delete confirmation submitted against a changed impact snapshot is rejected and requires a new preflight; (2) a completed delete produces evidence tombstones, dependent LearningState downgrades, and an audit event atomically; (3) a captured structured log record from a provider-backed action is asserted to omit at least one representative redaction category (e.g., a provider auth environment value) end to end. This is the primary export/delete/redaction test for the codebase; no other ticket duplicates it.
  - Manual: Privacy reviewer inspects one full export package against a goal with a tombstoned evidence item and confirms the item is marked unavailable rather than fabricated or silently dropped (contributes to G11 review).
  - Existing coverage reused: None for export/delete specifically — the prototype's `Export JSON`/`Reset local pages` actions and the network tripwire have no meaningful behavior worth reusing, since they operate entirely client-side against localStorage and a synthetic network allowlist rather than any real disclosure, job, or redaction mechanism.
- Failure and recovery:
  - An export or delete job failure surfaces `failed` with a retry action; delete failure never leaves a partial cross-goal downgrade — the underlying atomic operation (IDK-108) either fully applies or fully rolls back.
  - A revoked disclosure blocks only future enqueues for that category; it does not retroactively alter already-committed provider requests or results.
- Removal/replacement: Removes the prototype `Export JSON` blob-download action and the `Reset local pages` localStorage reset in `src/selected/operations/OperationalPages.tsx`, replacing them with the durable `POST /exports`/`GET /exports/{id}` job and the real destructive-delete preflight/confirm flow. Also removes the entire operations-side localStorage store in `src/selected/operations/OperationalPages.tsx` — `STORAGE_KEY` (`lattice.operations.state.v1`), `LEGACY_STORAGE_KEY` (`lattice.selected.operations.v1`), `hydrateOperationsState`, `loadState` and the `useOperationsState` hook that binds Evidence, Imports, Canonical updates, Search, Jobs and Settings together — once IDK-203/IDK-206/IDK-208/IDK-407 have migrated the last of its fields; and removes `installNetworkTripwire` in `src/shared/network.ts` together with `src/shared/network.test.ts` — the tripwire's blanket block of non-local-origin requests contradicts PRV-01's disclosed-provider/source-network posture (network access for configured model providers and source retrieval is explicitly permitted with disclosure; strict offline is explicitly not claimed) and is replaced by the disclosure-acceptance gate this ticket surfaces and IDK-403 enforces at enqueue.
- Approval gate: Satisfied. IDK-010 policy version 1.0 (2026-08-13) supplied the export package/version, transcript-inclusion, delete-recovery, backup, and log retention/support-access values, and this ticket implements them. The decision artifact's section 10 review evidence is recorded in `docs/privacy/IDK-010-policy-1.0-review-evidence.md` — the product/privacy owner's manual review passed on 2026-08-13, which is what permits `export_privacy_review_approved` to default true and production export to activate. IDK-503 still owns the consolidated G10/G11 review across every gate; this ticket's own privacy acceptance is closed.
- Estimate: TBD; implementation team to estimate after approval.

## 5. MVP-hardening

Phase 5 closes the MVP without adding features: it proves migrations survive representative real data, proves the essential flows are actually usable by keyboard and assistive technology, runs the manual approval reviews that content/runner tickets deferred, records honest performance distributions, and performs the final scope/fabrication audit before release. None of these five tickets invents a threshold, license, guarantee, or answer to an open PRD question.

### IDK-501 — Alembic representative upgrades and recoverable migration failure

- Phase: 5 — MVP-hardening
- Status: Complete
- Objective: Prove the versioned persistence layer — Alembic schema plus the independently versioned artifacts named in spec §4.8 — upgrades forward across representative existing local databases without data loss, and that a failed migration stops startup with a recoverable diagnostic rather than exposing a partially upgraded service.
- User-visible outcome: After any product upgrade, a learner's existing goals, evidence, diagnostics, jobs, and search remain intact and usable; if an upgrade cannot complete, the app refuses to start with a clear, recoverable message instead of behaving unpredictably.
- PRD traceability: NFR-11 (primary); CUR-03 (contributing — approval-last immutability is exercised across upgrades).
- Appendix H decisions: D1 (approved canonical versions are never data-migrated in place — corrections publish a new version and use D9).
- Owning module: audit_observability (migration diagnostics/startup gating); every module owns its own Alembic revisions per §3.3 and is exercised, not rewritten, by this ticket.
- Dependencies: IDK-101, IDK-102, IDK-104, IDK-105, IDK-108, IDK-203, IDK-303, IDK-401, IDK-406, IDK-407, IDK-408.
- Scope:
  - Build representative fixture databases reflecting spec §4.8's exact list: two goals with cross-goal transferred evidence; a paused diagnostic session; approved canonical graph v1 and v2 with a goal pinned mid-transition; an overlay conflict plus an upstream-deleted topic carrying local state; imports; a generated artifact with provenance snapshot; an active job and a job requiring startup recovery reconciliation; a completed Mock transcript; a deliberately stale FTS5 projection.
  - Run the ordered Alembic upgrade path against each fixture and assert exact preservation of governed invariants (immutability, owner/goal scoping, append-only histories, cache keys, job dedupe keys) after upgrade.
  - Verify forward-only expand/backfill/contract discipline for every migration accumulated across Phases 1–4: no destructive drop before backfill; no in-place rewrite of an approved canonical version's rows.
  - Exercise IDK-406's explicitly approved Java-only constraint revision: any obsolete non-authoritative `language='relational'` confirmation/runner placeholder rows, exclusively owned bodies/inputs/outputs, and linked `kind='runner'` job/result/attempt/event subgraphs whose logical request/run/result references target them are deleted transactionally before check rebuild. Unrelated jobs and all goals, artifacts, and evidence survive, and no surviving logical reference points to a removed ID. This is the sole approved obsolete-placeholder disposal, not a general data-loss exception or compatibility archive.
  - Implement/verify the single-expected-head startup gate for both the FastAPI server and the offline publish tool, in both below-head and above-head (newer DB than code) directions.
  - Implement/verify a deliberately failing migration stops startup, leaves no partially upgraded readable service, and surfaces a recoverable diagnostic naming the failed revision.
  - Confirm the thirteen artifacts in §4.8 (Alembic schema, canonical manifest, graph, content revision, overlay format, import parser, prompt template, provider contract, derived-state rules, generated artifacts, job payload/result, FTS projection, export format) each carry a distinct version identifier that does not conflate with the Alembic schema version.
- Out of scope:
  - Defining retention/backup policy for old databases (Appendix F, TBD).
  - New product features; this ticket hardens existing migration machinery only.
  - Post-MVP schema changes for Go/AWS or SaaS seams (Section 6).
- Data and invariants:
  - Single-row `alembic_version` head; server and publisher both refuse to operate off it.
  - Forward-only expand → backfill → contract as separate revisions where destructive.
  - A failed migration commits no ambiguous partial state; non-transactional operations document their recovery path.
  - Approved `canonical_graph_versions` rows stay immutable across migrations; new columns may be added, content may never be rewritten.
- API/domain/event contracts:
  - No new endpoints. Startup failure surfaces as a `503 unavailable — migration` shape per §5.1 (`code`, `message`, `retryable: false`, `recovery_action`).
- UX routes and states:
  - None directly; indirectly defines every route's `unavailable` state (§2.1) when schema is off-head.
- Implementation notes:
  - Build fixtures by scripting the same commands/APIs used by Phase 1–4 test suites, snapshotting at pre-upgrade revisions, rather than hand-authoring SQL.
  - Parametrize pytest over "each prior revision → head" plus one genuinely broken revision.
- Acceptance criteria:
  - Every §4.8 fixture upgrades to head with zero governed learner/domain data loss and intact invariants; a dedicated obsolete-relational-placeholder fixture proves only the exact IDK-008/406 placeholder-owned runner/job/result/attempt/event subgraph is removed, all governed/unrelated data remains, and no typed request/run/result reference dangles.
  - Server and publisher both refuse a non-head database, below and above head.
  - The injected-failure fixture stops startup cleanly with an actionable diagnostic.
  - All thirteen independently versioned artifacts expose distinct, mechanically verifiable version identifiers.
  - A negative test confirms an approved canonical version cannot be data-migrated in place; only new-version-plus-D9 succeeds.
- Minimum required tests:
  - Automated: pytest integration suite running every §4.8 representative fixture through Alembic upgrade, including the bounded obsolete-relational-placeholder disposal assertion, plus one negative test for recoverable failure with no partial state.
  - Manual: None beyond the automated suite; the recoverable-diagnostic wording is reviewed as part of IDK-503, not duplicated here.
  - Existing coverage reused: None — the prototype has no server or database, so no prior migration coverage exists to reuse.
- Failure and recovery:
  - On failure the server exits without binding, writes a diagnostic naming the failed revision, and leaves the database at its last committed revision (or a clearly quarantined marker) so a fixed re-run resumes rather than duplicates.
  - Above-head is treated identically to below-head: refuse to start, log the mismatch, no partial operation.
- Removal/replacement: None — the prototype has no server or database, so there is no prior migration mechanism to remove.
- Approval gate: Feeds spec §11 Phase 5 exit ("recoverable failures demonstrated") and is evidence toward §12.3 blocking question 11 (data lifecycle) without resolving it.
- Estimate:
  - TBD; implementation team to estimate after approval.

### IDK-502 — Essential accessibility verification across SET-02 flows

- Phase: 5 — MVP-hardening
- Status: Automated coverage complete; manual screen-reader pass deferred by owner decision 2026-08-14. Every automated acceptance criterion is met (axe WCAG 2 A/AA across all 14 routes × 4 viewports and every reachable async state, keyboard-only walkthroughs of all six SET-02 flows, focus restoration on every production dialog/drawer, reduced-motion via both the OS media query and the app's own `so-reduced-motion` setting). The VoiceOver/NVDA review required by "Minimum required tests" and acceptance criterion 4 is not done and is not currently scheduled. It is deferred, not satisfied: no automated check substitutes for it, so IDK-502 stays incomplete and IDK-505 must still account for the gap at release.
- Objective: Verify essential keyboard, assistive-technology, responsive, focus, and reduced-motion behavior across the exact SET-02-named flows — onboarding, roadmap, questions, feedback, notebook, settings — at the four required viewports, extending rather than rewriting the existing Playwright axe/keyboard/focus/reduced-motion/overflow coverage to the routes and async states that did not exist in the prototype.
- User-visible outcome: A learner using only a keyboard or assistive technology can complete onboarding, edit the roadmap, use Interview Prep Questions, receive and act on feedback, use the notebook, and change Settings — including job/SSE, evaluating/feedback-ready, delete-confirmation, and merge-conflict states — without losing keyboard operability, focus context, or reduced-motion compliance.
- PRD traceability: SET-02 (primary); NFR-01 (primary); contributing: ONB-01/02/03, CORE-05, LRN-01, QPR-01/02, NBK-01, SET-01.
- Appendix H decisions: None (accessibility verification is not itself a D-decision, though it must cover the async states D1–D11 mechanics produce).
- Owning module: frontend.
- Dependencies: IDK-103, IDK-105, IDK-106, IDK-107, IDK-201, IDK-202, IDK-206, IDK-301, IDK-302, IDK-303, IDK-401, IDK-402, IDK-407, IDK-409.
- Scope:
  - Reuse the existing axe/keyboard/focus-restoration/reduced-motion/no-overflow patterns in tests/e2e/selected-app.spec.ts as the baseline; extend, do not replace, wherever the underlying route survives into production.
  - Extend coverage to production-only async states absent from the prototype: job/SSE `connected`/`reconnecting`/`unavailable` (`/app/jobs` and any route with an in-flight job banner); `evaluating`/`feedback-ready` in Practice and Mock; delete-confirmation dialogs (Settings); merge-conflict resolution controls (`/app/canonical-updates`).
  - Verify keyboard operability, semantic roles/labels, and visible focus for: onboarding progressive fields and diagnostic flow; roadmap Customize/Jump/Skip/Restore/depth/order; Interview Prep Questions selection and Practice hint/Submit/retry; feedback disclosure (facts vs. trade-offs, rubric dimensions); notebook entry creation/labeling; Settings profile/import/provider/accessibility/progress-display/export/delete.
  - Verify focus restoration on every new production dialog/drawer (job retry/cancel confirmation, merge-conflict accept dialog, delete-confirmation alertdialog), following the pattern already proven for the prototype's navigation drawer and destructive dialog.
  - Verify `prefers-reduced-motion` suppression on new production animation (job progress, SSE reconnect indicator, staleness banners) using the existing zero-duration assertion pattern.
  - Run axe WCAG 2 A/AA scans against every one of the 14 routes in every reachable async state, at 1440×1000, 1366×768, 768×1024, 390×844.
  - Commission a manual screen-reader pass (at minimum one of VoiceOver/NVDA) over the six named SET-02 flows — the part no automated check replaces.
- Out of scope:
  - Non-essential flows not named by SET-02 (Search, Jobs browsing, Imports beyond the named flows) get axe coverage as a byproduct of the 14-route sweep but no separate manual review.
  - Redesigning the accessibility-oriented Radix/shadcn-style primitives; this ticket verifies them.
  - WCAG AAA conformance — only A/AA, matching the existing axe tag configuration.
- Data and invariants:
  - No async route transition may drop keyboard focus into an unreachable or ambiguous location.
  - Every destructive/state-changing dialog restores focus to its trigger on cancel/close.
  - Reduced-motion suppresses non-essential animation/transition duration to effectively zero across every production route.
- API/domain/event contracts: None new; verifies UI behavior against contracts owned by IDK-401/402 (jobs/SSE), IDK-303 (Mock), IDK-409 (delete-confirmation).
- UX routes and states: All 14 canonical routes, emphasizing `/app/onboarding`, `/app/learn-roadmap`, `/app/interview-hub` (Questions mode), `/app/practice`, `/app/topic-studio` (notebook), `/app/settings`, plus job/SSE, evaluating/feedback-ready, delete-confirmation, merge-conflict states.
- Implementation notes:
  - Add new Playwright specs alongside tests/e2e/selected-app.spec.ts; remove only assertions tied to a prototype mechanism a Section 4 removal ticket has actually deleted.
  - Use the same `AxeBuilder` `['wcag2a','wcag2aa']` configuration already in place.
  - Drive async states via a fake job/provider adapter (per NFR-09) rather than live providers.
- Acceptance criteria:
  - Zero WCAG 2 A/AA axe violations on every canonical route in every reachable async state, at all four viewports.
  - Automated keyboard-only walkthroughs complete all six named SET-02 flows without a mouse.
  - Focus-restoration and reduced-motion assertions pass for every new production dialog/drawer/animation.
  - Manual screen-reader review is completed and its findings recorded before Phase 5 exit.
- Minimum required tests:
  - Automated: Playwright specs extending the existing suite with axe/keyboard/focus/reduced-motion coverage for job/SSE, evaluating/feedback-ready, delete-confirmation, and merge-conflict states.
  - Manual: Screen-reader pass (VoiceOver or NVDA, minimum one) over onboarding, roadmap, Questions, feedback, notebook, and Settings.
  - Existing coverage reused: tests/e2e/selected-app.spec.ts's 14-route render/no-overflow sweep, WCAG A/AA axe sweep, keyboard-operable-flows test, drawer/destructive-dialog focus-restoration test, and reduced-motion suppression test are extended in place.
- Failure and recovery:
  - Any newly discovered accessibility regression blocks Phase 5 exit per spec §12.1 until fixed or explicitly waived by the accessibility owner.
  - A route/state that cannot be made keyboard-operable is documented as a known gap with an owner, never silently shipped.
- Removal/replacement: None — this ticket extends coverage; prototype mechanisms it touches are removed by their owning tickets (IDK-107, IDK-304), not this one.
- Approval gate: Phase 5 accessibility exit per spec §11 row 5 and the §12.1 "accessibility regresses in async states" risk row; frontend/accessibility owner sign-off required before release.
- Estimate:
  - TBD; implementation team to estimate after approval.

### IDK-503 — Consolidated content-and-safety approval review

- Phase: 5 — MVP-hardening
- Status: Convened 2026-08-14; blocked on findings and on approver attestation. All seven gates were inspected against shipped artifacts and recorded in `docs/approvals/IDK-503/gate-1..7-*.md`, consolidated in `docs/approvals/IDK-503-content-and-safety-review.md`, with `node scripts/check-review-records.mjs` (`pnpm review:check`) as the mechanical field scan. Every PRD Appendix C row carries an explicit disposition. Result: gate 6 (size/retention and export/delete/logging lifecycle) reached inspection-passed-pending-attestation; the other six carry 16 blocking findings, dominated by the fact that no production content has ever been published — `topics`, `canonical_graph_versions`, `editorial_approvals`, `sources`, `source_snapshots`, `rubrics` and `rubric_dimensions` are all empty — plus code-level gaps that would block even after content ships (absent `basis_ref` validation, absent source-registry implementation, unshipped IDK-004 role copy, unshipped rubric/scenario registry and `not-demonstrated` outcome, and an unenforced IDK-005 platform matrix). No gate is approved: attestation belongs to the designated editorial approver, the product/privacy owner and the security/engineering owner, and none has signed.
- Objective: Convene and record the manual approval review that closes MVP's content-and-safety gates — curriculum boundary, editorial approval criteria, source/license policy, role taxonomy, rubric and scenario review, privacy/export/delete/logging inspection, and runner threat-model posture — checked against PRD Appendix C's six threat/limitation rows.
- User-visible outcome: None directly; the outcome is a set of recorded, attributed approvals (or explicit blocks) gating whether affected features may ship.
- PRD traceability: No new primary. Contributing: DEP-03 (editorial reversal-regression sign-off, implemented by IDK-201), HND-03 (role-appropriate scenario sign-off, implemented by IDK-405), CNT-04 (source/claim sign-off, implemented by IDK-207), RUN-03 (not-a-sandbox wording sign-off, implemented by IDK-406).
- Appendix H decisions: D1 (editorial approval posture/attribution).
- Owning module: canonical (approval-basis record of record); review also inspects provenance, evidence_evaluation, runner, settings_data outputs without owning those tables.
- Dependencies: IDK-001, IDK-002, IDK-003, IDK-004, IDK-005, IDK-007, IDK-008, IDK-009, IDK-010, IDK-102, IDK-201, IDK-207, IDK-405, IDK-406, IDK-409.
- Scope:
  - Review the curriculum boundary decided in IDK-001 against the shipped canonical graph's scope tags (CUR-01).
  - Review the editorial approval evidence/criteria decided in IDK-002 against actual `editorial_approvals.basis` records produced by IDK-102's offline publisher.
  - Review the source licensing/snapshot/withdrawal policy decided in IDK-003 against shipped `sources`/`source_snapshots` rows and their license/availability status.
  - Review the learner-facing role copy decided in IDK-004 against onboarding, Settings, Interview Prep, and hands-on scenario metadata, including title-variation, no-beginner, non-prediction, and IDK-009 calibration alignment.
  - Review the representative assessment scenarios and rubric versions decided in IDK-009 against shipped approved rubric manifests and role/level scenario records (HND-03 scenario review; DEP-03 layer-reversal regression review).
  - Inspect the combined size/retention and export/delete/logging lifecycle decided in IDK-010 against shipped export contents, delete-confirmation impact snapshots, log redaction rules, and job/artifact retention behavior.
  - Review the runner enablement/resource posture (IDK-005 OS/toolchain matrix, IDK-007 runner posture, IDK-008 database-execution absence) row-by-row against PRD Appendix C's six threat/limitation rows, confirming each MVP control and residual statement is actually implemented and correctly labeled in-product (RUN-03). Verify relational capability/config/schema/UI is absent, retired runner signatures fail closed-schema validation before route/UoW, RDB static reviews carry all no-connection/no-runtime-proof clauses in review-specific wording, and no structured connector credential/endpoint field or database socket/process is introduced.
  - Produce one recorded approval artifact (or explicit blocking findings) per gate, attributed and dated, referencing the specific shipped fixture/record inspected.
- Out of scope:
  - Making the underlying decisions (IDK-001/002/003/004/005/007/008/009/010) — this ticket reviews their implementation, not their authorship.
  - Any code change; findings requiring a fix are filed against the owning implementation ticket.
  - Performance measurement (IDK-504) and final scope audit (IDK-505) — separate tickets.
- Data and invariants:
  - Every recorded approval or block cites the specific shipped artifact inspected, not an abstract feature description.
  - A recorded block is binding: the referenced feature may not release until re-reviewed and cleared.
- API/domain/event contracts: None new. Reads `editorial_approvals`, `sources`/`source_snapshots`, `rubrics`/`rubric_dimensions`, `export_operations`/`delete_operations`, `runner_records`, and structured log samples.
- UX routes and states: Inspects `/app/canonical-updates`, `/app/topic-studio` (runner/limitation labels), `/app/settings` (export/delete/disclosure), `/app/evidence`/`/app/reports` (rubric/citation presentation) as implemented.
- Implementation notes:
  - Schedule only after dependent decisions resolve and their implementation tickets ship into a reviewable build.
  - Use Appendix C's six-row table verbatim as the runner-review checklist so no row is skipped.
- Acceptance criteria:
  - Each of the seven named gates has a recorded, attributed, dated approval or an open blocking finding with an owner.
  - Every Appendix C row has an explicit reviewed disposition.
  - No gate is approved from a description of intended behavior rather than inspection of the shipped artifact.
- Minimum required tests:
  - Automated: None — this is a manual approval review; an optional mechanical scan may confirm the presence of required review-record fields (gate, reviewer role, date, referenced artifact) but does not substitute for the review.
  - Manual: Full review session(s) by the designated editorial approver, plus a security/engineering owner for the runner threat-model row, walking each gate against shipped artifacts and Appendix C's six rows.
  - Existing coverage reused: None — this governance review has no automated precedent.
- Failure and recovery:
  - A blocking finding halts release of the affected feature only, provided it is tracked with an owner and is not itself an unresolved safety defect.
  - A mismatch between a reviewed artifact and its decision record blocks release until the mismatch is resolved.
- Removal/replacement: None.
- Approval gate: This ticket is itself the approval gate for CUR-01/CUR-03, CORE-02/INT-02, DEP-03, HND-03, CNT-04, and RUN-03 sign-off, feeding spec §11 Phase 5 exit and §12.3 blocking questions 1–4 and 7–9.
- Estimate:
  - TBD; implementation team to estimate after approval.

### IDK-504 — Representative performance measurement, no invented threshold

- Phase: 5 — MVP-hardening
- Status: Harness committed and run; 13 of the 15 spec §8.6 measurements recorded, 2 recorded as explicit gaps. `pnpm perf` (`scripts/perf/run.mjs`) recreates `perf-results/`, seeds one fixed representative dataset (`server/scripts/seed_performance_dataset.py`: 60 canonical topics, 68 relations, 2 goals, 5 evidence, 4 notebook entries, 2 imports, 3 generated artifacts, 3 jobs, 134 search documents — identical counts across two fresh databases), records the §8.6 context, runs the four producers (`tests/perf/*.perf.spec.ts` and `server/scripts/measure_performance.py`), then builds and checks `docs/performance/IDK-504-representative-measurements.md`. `scripts/perf/check-report.mjs` asserts every §8.6 measurement is present as a distribution or a recorded gap, that the context is complete, and that no threshold language appears; it passes. Measured: cold and warm navigation across all 14 routes, FTS query and stale-fallback latency, SSE-to-visible-state, interactive job start under background-lane load, import-parse and index-rebuild effects on concurrent reads, CPU/memory/SQLite size, and viewport overflow plus input latency at all four viewports. Not measured: `roadmap-render` and `roadmap-interaction`, recorded as gaps with their reason — `/app/learn-roadmap` renders its 60 rows on a quiet server but not during the run, because the backend's SQLAlchemy pool (5 + 10 overflow) is exhausted by then. A separate observation the run surfaced and the report notes: each `/api/v1/events` SSE stream outlives the browser context that opened it, so a sweep of fresh contexts accumulates server-side streams until the pool is exhausted; cold navigation therefore does not open one, and that limitation is stated in the sample's own notes. No threshold, baseline or target is set anywhere; an approver sets acceptance thresholds later.
- Objective: Record representative local performance measurements across the exact measurement set in spec §8.6 — device/OS/runtime/toolchain and dataset shape; cold/warm navigation; full-roadmap render/interaction; FTS query and stale fallback; SSE-to-visible-state latency; interactive job start while background work runs; import/index-rebuild effects; CPU/memory/SQLite size; 390/768/1366/1440 viewport overflow and input latency — reporting distributions and outliers with no invented pass/fail number.
- User-visible outcome: None directly; the outcome is a reproducible performance report an approver later uses to set thresholds. No performance guarantee is shown to a learner.
- PRD traceability: NFR-08 (primary); contributing: SYS-02, SYS-03, DAT-02.
- Appendix H decisions: D8 (worker lanes — this ticket measures, but does not assert a guarantee for, the interactive-job-start-while-background-runs behavior).
- Owning module: audit_observability (measurement collection/reporting); measurements span frontend, search, jobs_events.
- Dependencies: IDK-101, IDK-103, IDK-201, IDK-202, IDK-203, IDK-401, IDK-402, IDK-408.
- Scope:
  - Record device/OS/runtime/toolchain and dataset shape (goal count, topic count, evidence count, import volume) for every measurement run.
  - Measure cold and warm navigation across the 14 canonical routes.
  - Measure full-roadmap render and interaction (Customize/Jump/Skip/Restore/depth/order) at representative dataset sizes.
  - Measure FTS query latency and the deterministic stale-fallback path's latency (spec §8.4).
  - Measure SSE-to-visible-state latency: server-emitted job event to corresponding UI state change.
  - Measure interactive job start latency while background-lane work runs, observing (not certifying) the D8 non-blocking behavior.
  - Measure import parsing and search-index rebuild effects on concurrent navigation/search responsiveness.
  - Record CPU, memory, and SQLite database file size under the representative dataset.
  - Measure 390/768/1366/1440 viewport overflow behavior and input latency at each viewport.
  - Report results as distributions (percentiles, min/max, sample count) plus outliers — never a single pass/fail number.
- Out of scope:
  - Setting or publishing any pass/fail threshold, baseline, or numeric target.
  - Load/scale testing beyond representative single-local-owner usage (no concurrent-user testing applies to MVP).
  - Optimizing performance to hit a threshold; resulting optimization work is filed separately.
- Data and invariants:
  - Every measurement is tied to its device/OS/runtime/toolchain/dataset-shape context; an untethered number is not a valid report entry.
  - The report contains no language implying an approved threshold, SLA, or guarantee.
- API/domain/event contracts: None new; instruments existing routes/APIs/SSE/job contracts.
- UX routes and states: All 14 canonical routes at all four required viewports, including `loading`/`stale`/`rebuilding` search states and job `queued`/`running`/`succeeded` states.
- Implementation notes:
  - Reuse the existing Playwright viewport/no-overflow harness (`expectNoHorizontalOverflow` in tests/e2e/selected-app.spec.ts) as scaffolding, extended to capture timing, not just layout.
  - Reuse dataset fixtures built for IDK-501 where dataset shape overlaps rather than maintaining two synthetic datasets.
  - Instrument with standard browser/Node performance APIs and existing `audit_events`/`job_events` correlation IDs; no new external telemetry pipeline (IDK-011 still gates any external telemetry).
- Acceptance criteria:
  - A recorded report covers every §8.6 measurement, each with full context and a distribution-plus-outliers presentation.
  - The report contains zero invented thresholds/baselines/targets and states explicitly that an approver sets acceptance thresholds later.
  - The harness/script producing the report is committed and reproducible.
- Minimum required tests:
  - Automated: A committed measurement harness (Playwright for client-side navigation/render/viewport/input-latency; a server-side script for CPU/memory/SQLite-size/SSE-latency) producing the report deterministically from a fixed dataset; asserts the report covers every §8.6 item and contains no threshold language.
  - Manual: Human review confirms the report's distributions are representative (no stuck timer or broken measurement) and dataset-shape documentation is complete.
  - Existing coverage reused: tests/e2e/selected-app.spec.ts's viewport/no-overflow harness is extended for viewport-overflow-plus-input-latency measurements.
- Failure and recovery:
  - If a measurement cannot be taken reproducibly, the report states the gap explicitly rather than fabricating a number.
  - No runtime failure/recovery behavior of its own; it observes systems whose failure/recovery paths are owned elsewhere.
- Removal/replacement: None.
- Approval gate: Supplies the evidence base for a later approver to set NFR-08 thresholds (spec §12.3 item 10 indirectly, via dataset-shape observations); does not itself close that gate.
- Estimate:
  - TBD; implementation team to estimate after approval.

### IDK-505 — Final MVP readiness, scope, recovery, and unsupported-claim audit

- Phase: 5 — MVP-hardening
- Status: Not started
- Objective: Perform the final MVP readiness, scope, recovery, and unsupported-claim audit against PRD §14's final audit checklist and spec §13's final completeness audit, and confirm every prototype mechanism scheduled for removal is actually gone.
- User-visible outcome: None directly; the outcome is a pass/fail readiness determination and, where failing, a concrete defect list that must close before release.
- PRD traceability: No new primary; contributing to all 60 Musts and NFR-01–NFR-11 collectively as the final cross-cutting audit.
- Appendix H decisions: D1–D11 (the audit confirms each is still honored in the shipped product; none newly owned here).
- Owning module: audit_observability.
- Dependencies: IDK-101 through IDK-409 (all Section 1–4 tickets), IDK-501, IDK-502, IDK-503, IDK-504.
- Scope:
  - Walk PRD §14's final audit checklist line by line against the shipped product, recording a disposition for each item: exactly two learning paths with Refresher/Questions independently reachable; curriculum claims bounded; whole roadmap/corrections/depth/order visible and explicit; inferences never become completion and ambiguity/valid alternatives carry no automatic readiness penalty; Practice and Mock have distinct hint/follow-up/feedback behavior; Mock retains adaptive cross-questioning while withholding only hints/feedback until completion; imports/canonical drafts/overlays/updates/sources/provenance observe approval and opt-in boundaries; network use disclosed, strict offline not promised, no real AWS; runner labels controlled-subprocess limitations with confirmation/limits/cancellation/output/cleanup; locked stack and future seams preserved without premature prohibited infrastructure; nothing fabricated.
  - Walk spec §13's final completeness audit line by line: all 60 Musts + NFR-01–11 traced; D1–D11 preserved; all 14 routes covered including `/app/$pageId` validation and not-found; exactly two learning paths (My learning/Tools are not additional paths); Resume and Recommended next remain separate; evidence (not viewing/Run) establishes progress; MVP/hardening/Later/TBD/unsupported ledgers remain distinct.
  - Confirm each of the thirteen named prototype-removal targets is actually gone from the shipped product: localStorage persistence and legacy hydration (IDK-107, final key deletion IDK-303); static-review fixture scoring `evaluateCode`/`SIMULATION_LIMITATION` (IDK-405); Practice fixture feedback `practiceFeedback`/`PRACTICE_QUESTIONS` (IDK-302); Mock fixture transcript state (IDK-303); fixture evaluation gating `MOCK_FIXTURE_DRAFT`/`reportKind`/`FIXTURE_REPORT` (IDK-304); client-only evidence/dispute state (IDK-208); the import regex parser (IDK-203); the single hardcoded course fixture and `src/shared/model.test.ts` (IDK-104); static lesson copy `LESSON_CONTEXT` (IDK-201); the simulated jobs page (IDK-401); the canonical-update localStorage simulation and `UPDATE_ROWS` (IDK-407); the bundled search fixture `SEARCH_ITEMS` (IDK-408); and the prototype export/reset, the operations localStorage store and the network tripwire (IDK-409).
  - Run a mechanical scan for fabrication smells — hardcoded scores presented as thresholds, invented OS/version strings, invented CLI version numbers, "guaranteed"/"sandbox"/"production-tested"/"AWS-verified" wording — across shipped UI copy and API responses, supplementing (not replacing) manual review.
- Out of scope:
  - Fixing any defect found — findings are filed against the owning ticket/module for remediation.
  - Re-deriving decisions already closed by IDK-503; this ticket confirms scope/removal/fabrication discipline, not content/safety approval.
  - Performance threshold-setting (IDK-504's boundary, not this ticket's).
- Data and invariants:
  - Every checklist line gets an explicit recorded disposition (pass, fail-with-defect, or not-applicable-with-reason); none is silently skipped.
  - A "removed" claim for a prototype mechanism is verified by absence in the shipped source tree/runtime behavior, not by a comment claiming replacement.
- API/domain/event contracts: None new; inspects existing shipped API responses/UI copy for fabricated claims.
- UX routes and states: All 14 canonical routes plus `/app/$pageId` invalid-ID and not-found behavior, reviewed for scope/claim discipline in rendered copy.
- Implementation notes:
  - Sequence last within Phase 5, after IDK-501/502/503/504 each produce recorded results, since this audit's checklist references their outputs.
  - Transcribe PRD §14 and spec §13 as literal checklists rather than paraphrasing, to avoid silently dropping an item.
- Acceptance criteria:
  - Every line of PRD §14 and spec §13's final audits has a recorded disposition against the shipped product.
  - All thirteen named prototype-removal targets are confirmed absent by direct inspection.
  - The mechanical fabrication-smell scan returns zero unresolved hits, or every hit is triaged with a filed defect.
  - No open "fail" disposition remains for a Must/NFR item at completion; any accepted residual risk is explicitly recorded with an owner.
- Minimum required tests:
  - Automated: A mechanical scan (grep/lint script) for fabrication-smell strings and for any surviving `lattice`/`Lattice` string (the product is **Yuno**) and for residual references to the thirteen removed prototype mechanisms (e.g., `localStorage`, `lattice.`, fixture-evaluation identifiers, bundled search index files), run in CI to catch future regression.
  - Manual: Line-by-line walkthrough of PRD §14 and spec §13 by a product/engineering reviewer against the running shipped application, recording a disposition per line.
  - Existing coverage reused: All Playwright/unit/integration suites produced by Section 1–4 tickets and IDK-501/502/504 are read as evidence inputs, not re-run standalone.
- Failure and recovery:
  - Any unresolved "fail" disposition blocks MVP release; the audit routes the defect to the owning ticket for remediation before re-audit.
  - If a prototype-removal target is found still present, this ticket blocks release until the owning removal ticket completes.
- Removal/replacement: Confirms (does not itself perform) removal of all thirteen targets: localStorage persistence and legacy hydration (IDK-107, final key deletion IDK-303); static-review fixture scoring `evaluateCode`/`SIMULATION_LIMITATION` (IDK-405); Practice fixture feedback `practiceFeedback`/`PRACTICE_QUESTIONS` (IDK-302); Mock fixture transcript state (IDK-303); fixture evaluation gating `MOCK_FIXTURE_DRAFT`/`reportKind`/`FIXTURE_REPORT` (IDK-304); client-only evidence/dispute state (IDK-208); the import regex parser (IDK-203); the single hardcoded course fixture and `src/shared/model.test.ts` (IDK-104); static lesson copy `LESSON_CONTEXT` (IDK-201); the simulated jobs page (IDK-401); the canonical-update localStorage simulation and `UPDATE_ROWS` (IDK-407); the bundled search fixture `SEARCH_ITEMS` (IDK-408); and the prototype export/reset, the operations localStorage store and the network tripwire (IDK-409).
- Approval gate: The final Phase 5 exit gate per spec §11 row 5 and PRD §13's product/engineering/governance acceptance criteria; the last checkpoint before MVP release.
- Estimate:
  - TBD; implementation team to estimate after approval.

## 6. Post-MVP

All four tickets carry no MVP dependency, are not reachable through MVP acceptance, and require their own separate approval before any implementation begins.

### IDK-601 — Go runner support and Go+AWS curriculum (Later)

- Phase: 6 — Post-MVP
- Status: Later
- Objective: Add Go execution to the runner port and a Go+AWS curriculum track, each gated by its own separate approval — a runtime/toolchain/threat-model approval for Go execution, and an independent curriculum decision for Go+AWS content.
- User-visible outcome: (Later) A learner could eventually select a Go+AWS goal and run Go compile/test locally, once both approvals exist; no MVP learner sees any Go-related affordance.
- PRD traceability: RUN-04 (primary, Later); CUR-02 (contributing — the MVP Go-absence rule this ticket must not relax).
- Appendix H decisions: None (a Go extension would need new equivalents of D1/D7-class decisions; none exist yet).
- Owning module: runner (plus canonical for the curriculum-side addition).
- Dependencies: IDK-406, IDK-102, IDK-005, IDK-007.
- Scope:
  - (Later) Extend `RunnerPort`/`RunnerSpec`/`RunnerResult` to accept Go alongside Java, following the same argv-only, declared-input, temporary-workspace, controlled-environment, limit, cancellation, and cleanup discipline already established for Java.
  - (Later) Author and offline-publish a new canonical graph version containing Go+AWS topics via the existing D1 pipeline, as a wholly new version.
  - (Later) Extend the OS/toolchain support matrix and detection logic to report Go as supported/missing/incompatible, following the NFR-10 pattern built for Java.
- Out of scope:
  - Any Go-related UI, capability flag, or database row reachable in MVP; `runner_records.language` accepting `go` stays rejected until this ticket's approval lands.
  - Relaxing IDK-102's canonical-graph validation that actively rejects a Go node in the MVP graph (CUR-02) — enabling Go requires a new approved graph version, not a relaxation of that validation.
- Data and invariants:
  - CUR-02's Go-absence rule is untouched by this ticket; enabling Go requires a new approved graph version through D1 plus a separate runner-side capability approval.
  - A Go-capable runner must satisfy the same Appendix C threat-model rows the Java runner satisfies, re-reviewed for Go-specific toolchain risk.
- API/domain/event contracts: (Later) `RunnerSpec.language` gains a `go` variant only after approval; no MVP contract changes.
- UX routes and states: (Later) `/app/topic-studio` runner controls would report Go capability once approved; no MVP route exposes it.
- Implementation notes: Placeholder scope only; no implementation begins until both the runner and curriculum approvals are separately granted.
- Acceptance criteria: (Later — set at the time of separate approval, not now.)
- Minimum required tests:
  - Automated: Not defined now; testing scope is set by the separate future approval, per Section 6's no-MVP-test-obligation rule.
  - Manual: Not defined now.
  - Existing coverage reused: None.
- Failure and recovery: (Later — defined alongside the future approval.)
- Removal/replacement: None.
- Approval gate: Requires two independent future approvals — a runtime/toolchain/threat-model approval for Go execution, and a separate curriculum decision for Go+AWS content — neither of which exists yet.
- Estimate:
  - TBD; implementation team to estimate after approval.

### IDK-602 — OpenRouter and DeepSeek provider adapters (Later)

- Phase: 6 — Post-MVP
- Status: Later
- Objective: Implement OpenRouter and DeepSeek adapters against the existing `ProviderPort` without changing any domain contract, so no MVP flow depends on them.
- User-visible outcome: (Later) A learner could eventually select OpenRouter or DeepSeek as an alternative generation/evaluation provider in Settings; no MVP learner sees these options.
- PRD traceability: AI-03 (primary, Later).
- Appendix H decisions: D7 governs the shape any new adapter must follow (argv-only, stdin/temp-file context delivery, non-interactive flags, env allowlist, inactivity/absolute timeouts, first-output heartbeat, process-group cancellation, pinned output contract) — applied to two new adapters, not amended.
- Owning module: provider.
- Dependencies: IDK-403, IDK-404.
- Scope:
  - (Later) Implement `ProviderPort` adapters for OpenRouter and DeepSeek, each pinning its own explicit output contract per D7, reusing the shared subprocess utility already built for Codex/Claude.
  - (Later) Extend `GET /provider-capabilities` to report OpenRouter/DeepSeek as configured/unavailable alongside Codex/Claude, without altering `GenerateRequest`/`GenerateResult`/`EvaluationRequest`/`EvaluationResult` shapes.
  - (Later) Extend Settings provider selection UI to list the new options once available.
- Out of scope:
  - Any change to `ProviderPort` or the schema-validation/quarantine domain contracts established by IDK-403/IDK-404.
  - Making OpenRouter or DeepSeek the MVP default or alternative; Codex 5.6 Terra/high remains default and Claude the sole MVP alternative (AI-02).
  - Any MVP flow depending on these adapters' presence or configuration.
- Data and invariants:
  - `provider_requests`/`schema_quarantines` invariants (raw prompt not a normal log field; quarantine cannot become result/evidence) apply identically with no schema change.
  - No MVP acceptance test may reference OpenRouter or DeepSeek; their absence must not break any MVP flow.
- API/domain/event contracts: (Later) No domain-contract change; new adapter implementations and new capability-report values only.
- UX routes and states: (Later) `/app/settings` provider selection gains new options once implemented; no MVP route references them.
- Implementation notes: Reuse the D7-compliant shared subprocess utility and adapter-contract-pinning pattern built for Codex/Claude rather than inventing a new transport approach.
- Acceptance criteria: (Later — set at the time of separate approval, not now.)
- Minimum required tests:
  - Automated: Not defined now; would follow IDK-403's fake-adapter/contract-regression pattern once scheduled by the separate future approval.
  - Manual: Not defined now.
  - Existing coverage reused: None.
- Failure and recovery: (Later — expected to follow the same recoverable no-first-output/timeout/quarantine classification already established for Codex/Claude, defined alongside the future approval.)
- Removal/replacement: None.
- Approval gate: Requires provider access/licensing and engineering approval for OpenRouter and DeepSeek before implementation begins; no MVP dependency.
- Estimate:
  - TBD; implementation team to estimate after approval.

### IDK-603 — Hosted authorization and SaaS seam replacements (Later)

- Phase: 6 — Post-MVP
- Status: Later
- Objective: Implement hosted authorization separating an ordinary learner's personal suggestions from designated editorial publication (SAAS-01), and replace MVP seams — SQLite→Postgres, local files→object storage, worker→managed queue, local CLI→API model access, local subprocess→remote isolated runner, local owner→Google/email identity (SAAS-02) — without changing domain contracts.
- User-visible outcome: (Later) A hosted multi-user deployment where an ordinary learner can propose but never directly publish canonical content, running on hosted infrastructure; no MVP learner is hosted or multi-tenant.
- PRD traceability: SAAS-01 (primary, Later); SAAS-02 (primary, Later).
- Appendix H decisions: D1 — the `owner_role_grants` distinction between `learner` and `designated_editorial_approver`, already shipped in MVP, is exactly the seam SAAS-01 authorization builds on.
- Owning module: identity (SAAS-01); SAAS-02 seam replacements sit behind existing settings_data/jobs_events/provider/runner-adjacent ports without new ownership.
- Dependencies: IDK-101, IDK-102, IDK-403, IDK-406, IDK-401.
- Scope:
  - (Later) Design hosted authorization so an ordinary SaaS learner's role grant never includes `designated_editorial_approver`, extending the existing role-grant mechanism rather than redesigning it.
  - (Later) Replace SQLite with Postgres behind existing repository interfaces, with no change to domain entities/invariants.
  - (Later) Replace local file storage (evidence payloads, artifacts, exports) with object storage behind the existing storage port.
  - (Later) Replace the single durable worker with a managed queue behind existing `JobRepository`/dispatch interfaces, preserving two-lane semantics.
  - (Later) Replace local CLI provider invocation with API-based model access behind the existing `ProviderPort`, preserving equivalent safety controls in whatever form a hosted transport requires (a new decision, not D7 itself, since D7 is CLI-subprocess-specific).
  - (Later) Replace local subprocess runner execution with a remote isolated runner behind the existing `RunnerPort`, preserving the same declared-input/confirmation/limit/cleanup contract shape.
  - (Later) Replace the built-in local owner with Google/email hosted identity behind the existing `IdentityPort`.
- Out of scope:
  - Any of these replacements shipping into or being reachable from the MVP local-owner single-tenant product.
  - Payments, teams, social features, gamification, mobile — PRD §13 excludes these from assumed future commitments; not part of this ticket.
  - Redefining domain contracts (`GenerateRequest`/`RunnerSpec`/`JobPayload`/etc.) — every replacement sits behind an existing port unchanged.
- Data and invariants:
  - The `owner_id` seam and the learner/`designated_editorial_approver` role-grant distinction already shipped in IDK-101/IDK-102 are what make SAAS-01 possible without a data-model rewrite; this ticket alters authorization policy, not table shape.
  - No MVP domain entity, invariant, or contract changes as a side effect of any SAAS-02 seam replacement.
- API/domain/event contracts: (Later) No MVP contract changes; hosted-specific contracts (auth tokens, tenant scoping) are additive and outside MVP's OpenAPI surface.
- UX routes and states: (Later) Hosted deployment would need new auth-entry UX (sign-in, tenant/role display); no MVP route changes.
- Implementation notes: Placeholder scope description; SAAS-01 authorization design and each SAAS-02 seam replacement are independent workstreams sequenced once hosted-SaaS scope is approved.
- Acceptance criteria: (Later — set at the time of separate approval, not now.)
- Minimum required tests:
  - Automated: Not defined now; testing scope is set by the separate future approval that authorizes hosted SaaS scope.
  - Manual: Not defined now.
  - Existing coverage reused: None.
- Failure and recovery: (Later — defined alongside the future approval.)
- Removal/replacement: None — this ticket adds hosted seams alongside, not instead of, MVP local ports; MVP local operation is not removed.
- Approval gate: Requires a separate hosted-SaaS product/architecture approval before any implementation begins; no MVP dependency and not reachable through MVP acceptance.
- Estimate:
  - TBD; implementation team to estimate after approval.

### IDK-604 — Separately approved scope: scheduling, voice, company-specific prep, telemetry (Later)

- Phase: 6 — Post-MVP
- Status: Later
- Objective: Track scheduling/study-time planning, voice, company-specific interview preparation, and any external telemetry (gated by IDK-011) as scope items each requiring its own separate approval before implementation, and explicitly record payments, teams, social features, gamification, and mobile as further items PRD §13 excludes from assumed future commitments.
- User-visible outcome: (Later) None in MVP; any of these capabilities becomes visible only after its own separate scope approval and implementation.
- PRD traceability: None (scheduling, voice, and company-specific preparation are named only in PRD §2 non-goals and §13's delivery sequence/dependencies, not as separate Must/NFR IDs; telemetry is gated by the IDK-011 decision, not a Must/NFR ID).
- Appendix H decisions: None (no D-ID governs these items).
- Owning module: frontend (placeholder for any eventual scheduling/voice UI); no MVP module ownership since nothing ships.
- Dependencies: IDK-011.
- Scope:
  - (Later) Scheduling/study-time planning: a future capability to plan or remind learners of study sessions, requiring its own separately approved scope — not derivable from any MVP roadmap/checkpoint mechanism.
  - (Later) Voice: PRD's voice-extensible interfaces (Appendix B) may accept modality metadata later, but MVP exposes text only; voice input/output requires separate scope approval.
  - (Later) Company-specific interview preparation: PRD explicitly excludes company-specific claims/content from MVP (INT-02); any company-specific track requires its own separate curriculum/scope approval, distinct from the generic role/level bundles shipped in MVP.
  - (Later) External telemetry: any telemetry leaving the local device requires the separately disclosed decision gated by IDK-011; MVP guardrail events (PRD §13 metrics section) remain local-only by default.
  - Explicitly record that payments, teams, social features, gamification, and mobile applications are non-goals not assumed as future commitments, so they are not silently reintroduced as scope creep.
- Out of scope:
  - Any implementation of the above; this ticket is a scope-boundary marker until each item receives its own separate approval.
  - Treating any of these as an MVP dependency or a feature reachable through MVP acceptance criteria.
- Data and invariants:
  - None of these items may introduce a schema, port, or UI affordance reachable from the MVP build; their data models are undefined until separately approved.
  - IDK-011's telemetry decision, even once resolved, gates telemetry only — it does not implicitly approve scheduling, voice, or company-specific prep.
- API/domain/event contracts: None in MVP.
- UX routes and states: None in MVP; no new route is added by this ticket.
- Implementation notes: Exists to make the Post-MVP scope boundary explicit and auditable (feeding IDK-505's scope-fabrication check), not to specify implementation detail with no approved decision yet.
- Acceptance criteria: (Later — set independently per item at the time of its own separate approval.)
- Minimum required tests:
  - Automated: Not defined now; testing scope is set by each item's separate future approval, independently.
  - Manual: Not defined now.
  - Existing coverage reused: None.
- Failure and recovery: (Later — defined independently per item alongside its own future approval.)
- Removal/replacement: None.
- Approval gate: Each of scheduling, voice, and company-specific preparation requires its own independent, separately approved scope decision; external telemetry additionally requires the IDK-011 disclosure/consent decision. None of the four is an MVP dependency or reachable through MVP acceptance.
- Estimate:
  - TBD; implementation team to estimate after approval.

---

# Appendices

## Appendix 1 — Ticket dependency table

Every dependency points backward to a decision ticket or a lower-numbered implementation ticket. No ticket depends on a later one.

Status vocabulary, fixed here because it was previously ambiguous: `Not started` means no implementation exists. `Complete` means the ticket's own acceptance criteria are implemented and its Appendix 8 required automated tests exist and pass; it does not mean the manual reviews Appendix 8 lists for that ticket have been performed — IDK-503 owns those, and IDK-505 is the final release gate. `Content incomplete` means the ticket's code paths are implemented and its Appendix 8 automated tests pass, but at least one acceptance criterion in the ticket's own `Scope` requires loading approved content that does not exist anywhere in the tree; the ticket names the missing content. `Approved` applies only to Section 0 decision tickets and means the decision artifact exists and carries a recorded approval. `Blocked by <ID>` means an unresolved decision is required for that ticket's own acceptance. Until 2026-08-14 this table used `Ready` for both "not started" and "implemented and tested", which made it unusable as a readiness signal; `Ready` no longer appears for an implementation ticket.

`Content incomplete` was added on 2026-08-15 for the same reason `Ready` was retired: IDK-204, IDK-302, IDK-303 and IDK-405 each read `Complete` while the approved rubric manifests and the twelve approved IDK-009 §4 scenario records they are scoped to load existed nowhere — a gap the IDK-503 re-run recorded against all four (`docs/approvals/IDK-503-content-and-safety-review-rerun-2026-08-15.md`, findings B11 and B12). `Complete` cannot carry that state without meaning two different things again.

| Ticket | Phase | Status | Depends on |
|---|---|---|---|
| IDK-001 | 0 | Approved | — |
| IDK-002 | 0 | Approved | — |
| IDK-003 | 0 | Approved | — |
| IDK-004 | 0 | Approved | — |
| IDK-005 | 0 | Approved | — |
| IDK-006 | 0 | Approved | — |
| IDK-007 | 0 | Approved | — |
| IDK-008 | 0 | Approved | — |
| IDK-009 | 0 | Approved | — |
| IDK-010 | 0 | Approved | — |
| IDK-011 | 0 | Ready | — |
| IDK-101 | 1 | Complete | — |
| IDK-102 | 1 | Complete | IDK-101 |
| IDK-103 | 1 | Complete | IDK-101 |
| IDK-104 | 1 | Complete | IDK-004, IDK-101, IDK-103 |
| IDK-105 | 1 | Complete | IDK-004, IDK-101, IDK-102, IDK-103 |
| IDK-106 | 1 | Complete | IDK-101, IDK-102 |
| IDK-107 | 1 | Complete | IDK-101, IDK-102, IDK-103, IDK-104, IDK-105, IDK-106 |
| IDK-108 | 1 | Complete | IDK-101, IDK-104 |
| IDK-201 | 2 | Complete | IDK-101, IDK-102, IDK-103, IDK-106, IDK-107 |
| IDK-202 | 2 | Complete | IDK-106 |
| IDK-203 | 2 | Complete | IDK-101, IDK-102, IDK-105 |
| IDK-204 | 2 | Content incomplete | IDK-101, IDK-102, IDK-108 |
| IDK-205 | 2 | Complete | IDK-101, IDK-108, IDK-204 |
| IDK-206 | 2 | Complete | IDK-201, IDK-204 |
| IDK-207 | 2 | Complete | IDK-101, IDK-102, IDK-201, IDK-203 |
| IDK-208 | 2 | Complete | IDK-108, IDK-204, IDK-205 |
| IDK-301 | 3 | Complete | IDK-004, IDK-103, IDK-104, IDK-201, IDK-205 |
| IDK-302 | 3 | Content incomplete | IDK-008, IDK-009, IDK-204, IDK-205, IDK-301 |
| IDK-303 | 3 | Content incomplete | IDK-009, IDK-104, IDK-301, IDK-302 |
| IDK-304 | 3 | Complete | IDK-009, IDK-204, IDK-301, IDK-302, IDK-303 |
| IDK-401 | 4 | Complete | IDK-101 |
| IDK-402 | 4 | Complete | IDK-101, IDK-401 |
| IDK-403 | 4 | Complete | IDK-006, IDK-101, IDK-401 |
| IDK-404 | 4 | Complete | IDK-207, IDK-301, IDK-302, IDK-303, IDK-401, IDK-402, IDK-403 |
| IDK-405 | 4 | Content incomplete | IDK-004, IDK-005, IDK-008, IDK-009, IDK-201, IDK-204, IDK-403, IDK-404 |
| IDK-406 | 4 | Partially implemented; execution deferred by owner decision — isolation layer will not be built, runner stays disabled | IDK-005, IDK-007, IDK-008, IDK-401, IDK-405 |
| IDK-407 | 4 | Complete | IDK-101, IDK-102, IDK-106, IDK-201 |
| IDK-408 | 4 | Complete | IDK-101, IDK-201, IDK-204, IDK-206 |
| IDK-409 | 4 | Complete | IDK-010, IDK-101, IDK-104, IDK-403 |
| IDK-501 | 5 | Complete | IDK-101, IDK-102, IDK-104, IDK-105, IDK-108, IDK-203, IDK-303, IDK-401, IDK-406, IDK-407, IDK-408 |
| IDK-502 | 5 | Automated complete; manual screen-reader pass deferred by owner decision | IDK-103, IDK-105, IDK-106, IDK-107, IDK-201, IDK-202, IDK-206, IDK-301, IDK-302, IDK-303, IDK-401, IDK-402, IDK-407, IDK-409 |
| IDK-503 | 5 | Ready — not convened | IDK-001, IDK-002, IDK-003, IDK-004, IDK-005, IDK-007, IDK-008, IDK-009, IDK-010, IDK-102, IDK-201, IDK-207, IDK-405, IDK-406, IDK-409 |
| IDK-504 | 5 | Not started | IDK-101, IDK-103, IDK-201, IDK-202, IDK-203, IDK-401, IDK-402, IDK-408 |
| IDK-505 | 5 | Not started | IDK-101 – IDK-409 (all), IDK-501, IDK-502, IDK-503, IDK-504 |
| IDK-601 | 6 | Later | IDK-005, IDK-007, IDK-102, IDK-406 — builds on MVP work; no MVP acceptance depends on it |
| IDK-602 | 6 | Later | IDK-403, IDK-404 — builds on MVP work; no MVP acceptance depends on it |
| IDK-603 | 6 | Later | IDK-101, IDK-102, IDK-401, IDK-403, IDK-406 — builds on MVP work; no MVP acceptance depends on it |
| IDK-604 | 6 | Later | IDK-011 (telemetry portion only); no MVP acceptance depends on it |

## Appendix 2 — Route-to-ticket matrix (all 14 canonical routes)

`/app/$pageId` validates exactly the 13 `/app/*` page IDs; every other value renders the existing not-found view linking to `/`. Refresher and Questions are `?mode=` query states of `/app/interview-hub`, not additional routes.

| Route | Owning tickets | Notes |
|---|---|---|
| `/` | IDK-103, IDK-104 | My learning home — workspace home, not a learning path. Historical Resume stays separate from dismissible Recommended next. |
| `/app/onboarding` | IDK-103, IDK-105, IDK-106, IDK-107 | Setup, persisted diagnostic, full roadmap preview, atomic D11 confirmation. |
| `/app/learn-roadmap` | IDK-103, IDK-106, IDK-202, IDK-407 | Learn path entry. Deterministic projection; bridges/proposals as annotations; stale-canonical-version annotation. |
| `/app/topic-studio` | IDK-103, IDK-201, IDK-207, IDK-404, IDK-405, IDK-406 | Self-contained topic workspace, generated-content staleness, hands-on lifecycle, gated runner. |
| `/app/interview-hub` | IDK-103, IDK-301 | Interview Prep path entry. `?mode=refresher` and `?mode=questions` are states of this route. |
| `/app/practice` | IDK-103, IDK-302, IDK-404 | Hint-on-request, feedback-after-Submit, append-only attempts. |
| `/app/mock` | IDK-103, IDK-303, IDK-404 | Focused shell outside the ordinary global shell; no hints or evaluation while nonterminal. |
| `/app/reports` | IDK-103, IDK-208, IDK-304 | Terminal-only consolidated reports; conclusion and next action first. |
| `/app/evidence` | IDK-103, IDK-108, IDK-204, IDK-205, IDK-208 | Immutable evidence, disputes, transfer lineage, derived progress, tombstoned-source warning. |
| `/app/imports` | IDK-103, IDK-203 | Untrusted originals, statement review, existing-topic-only mapping. |
| `/app/canonical-updates` | IDK-103, IDK-407 | Base→latest opt-in diff/merge with atomic acceptance. |
| `/app/search` | IDK-103, IDK-408 | FTS5 with owner/goal join, stale-index state, degraded fallback. |
| `/app/jobs` | IDK-103, IDK-401, IDK-402 | Real two-lane jobs, SSE status, GET reconciliation. |
| `/app/settings` | IDK-103, IDK-104, IDK-206, IDK-403, IDK-409 | Profile, review, disclosure, accessibility, progress display, export/delete. |
| `/app/$pageId` validation + not-found | IDK-103 | Exact 13 page IDs; retired concept routes and unknown IDs render not-found. |

## Appendix 3 — Appendix H D1–D11 to enforcing ticket and test

| Decision | Enforcing tickets | Primary enforcing test |
|---|---|---|
| D1 — Canonical publication posture | IDK-102 (v1, primary), IDK-407 (v2) | IDK-102: approval-record read-gate + approval-last atomicity; half-seeded version invisible; immutability triggers reject in-place mutation. |
| D2 — Roadmap semantics | IDK-106 (primary), IDK-202 | IDK-106: projector purity/determinism property test with stable-ID lexicographic tie-break and no-silent-mutation assertion. |
| D3 — Generated-content cache | IDK-207 (primary), IDK-203, IDK-404 | IDK-207: exact six-component cache key, single-flight at enqueue, snapshot-mismatch staleness without silent body change. |
| D4 — Job recovery | IDK-401 (primary), IDK-303, IDK-406 | IDK-401: crash/restart reconciliation, dedupe short-circuit, terminal result/state/event single-transaction atomicity, cancellation races. |
| D5 — Evidence scope and transfer | IDK-108 (primary), IDK-409 | IDK-108: read-only transfer reference with classification and zero content/completion copy; atomic tombstone + `unverified` downgrade + audit; preflight equals realized effect. |
| D6 — Derived learner state | IDK-205 (primary), IDK-204, IDK-206 | IDK-205: `f(evidence, corrections, now, rule_version)` determinism property; corrections never silently reversed; dismissed/disabled review contributes zero delta. |
| D7 — Provider transport | IDK-403 (primary), IDK-406 (shared subprocess utility, separate policy) | IDK-403: fake-adapter argv/stdin/env construction, no shell, no prompt in argv, three distinct timer classifications, process-group cancellation. |
| D8 — Worker model | IDK-401 (primary), IDK-404 | IDK-401: two reserved lanes, FIFO within lane, background never occupies the interactive slot, enqueue-level dedupe/single-flight. |
| D9 — Canonical merge | IDK-407 (primary) | IDK-407: two-version fixture; base→latest never chained; acceptance rejected while any item is unresolved; one-transaction pin move plus resolutions plus invalidation plus audit; full rollback on failure. |
| D10 — Import mapping | IDK-203 (primary) | IDK-203: mapping to a nonexistent or out-of-graph topic rejected and creates no topic; normalized-hash dedupe; approved mapping changes the imports hash observed by D3. |
| D11 — Diagnostic persistence | IDK-107 (primary), IDK-105 | IDK-107: injected mid-transaction failure leaves no goal, no LearningStates, no preview overlay and no confirmation link — no partial goal. IDK-105 covers session/answer persistence across pause/refresh/restart. |

## Appendix 4 — Every PRD Must requirement, mapped individually

All 60 `Must` requirements. Delivery is MVP except SET-02 (MVP-hardening). "Primary" is the single verification owner; "Supporting" tickets contribute without duplicating the primary's test.

| # | ID | Delivery | Primary ticket | Supporting tickets |
|---|---|---|---|---|
| 1 | CORE-01 | MVP | IDK-103 | IDK-104, IDK-301 |
| 2 | CORE-02 | MVP | IDK-104 | IDK-004, IDK-105 |
| 3 | CORE-03 | MVP | IDK-104 | IDK-101, IDK-108, IDK-409 |
| 4 | CORE-04 | MVP | IDK-108 | IDK-205, IDK-208 |
| 5 | CORE-05 | MVP | IDK-106 | IDK-202, IDK-107 |
| 6 | ONB-01 | MVP | IDK-105 | IDK-104, IDK-107 |
| 7 | ONB-02 | MVP | IDK-105 | IDK-203 |
| 8 | ONB-03 | MVP | IDK-106 | IDK-105, IDK-107 |
| 9 | LRN-01 | MVP | IDK-106 | IDK-201 |
| 10 | LRN-02 | MVP | IDK-201 | IDK-207, IDK-404 |
| 11 | LRN-03 | MVP | IDK-201 | IDK-202, IDK-405 |
| 12 | LRN-04 | MVP | IDK-202 | IDK-106, IDK-207 |
| 13 | DEP-01 | MVP | IDK-106 | IDK-201 |
| 14 | DEP-02 | MVP | IDK-201 | IDK-205 |
| 15 | DEP-03 | MVP | IDK-201 | IDK-503 |
| 16 | GAP-01 | MVP | IDK-202 | IDK-106 |
| 17 | GAP-02 | MVP | IDK-202 | IDK-106 |
| 18 | INT-01 | MVP | IDK-301 | IDK-103 |
| 19 | INT-02 | MVP | IDK-301 | IDK-004 |
| 20 | INT-03 | MVP | IDK-301 | — |
| 21 | REF-01 | MVP | IDK-301 | IDK-207, IDK-404 |
| 22 | QPR-01 | MVP | IDK-302 | IDK-204, IDK-404 |
| 23 | QPR-02 | MVP | IDK-302 | IDK-204 |
| 24 | QMK-01 | MVP | IDK-303 | IDK-401, IDK-404 |
| 25 | QMK-02 | MVP | IDK-304 | IDK-204, IDK-208 |
| 26 | IMP-01 | MVP | IDK-203 | IDK-105 |
| 27 | IMP-02 | MVP | IDK-203 | IDK-407 |
| 28 | NBK-01 | MVP | IDK-206 | IDK-201, IDK-408 |
| 29 | RET-01 | MVP | IDK-206 | IDK-009, IDK-409 |
| 30 | RET-02 | MVP | IDK-206 | IDK-205, IDK-409 |
| 31 | RET-03 | MVP | IDK-206 | IDK-009 |
| 32 | PRG-01 | MVP | IDK-205 | IDK-208, IDK-304, IDK-409 |
| 33 | PRG-02 | MVP | IDK-205 | IDK-106, IDK-108 |
| 34 | EVAL-01 | MVP | IDK-204 | IDK-302, IDK-303, IDK-304, IDK-405 |
| 35 | EVAL-02 | MVP | IDK-204 | IDK-205, IDK-208, IDK-304 |
| 36 | HND-01 | MVP | IDK-405 | IDK-204, IDK-302 |
| 37 | HND-02 | MVP | IDK-405 | IDK-406, IDK-208 |
| 38 | HND-03 | MVP | IDK-405 (mechanism) + IDK-503 (scenario-realism review) | IDK-009 |
| 39 | RUN-01 | MVP | IDK-406 | IDK-005, IDK-008 |
| 40 | RUN-02 | MVP | IDK-406 | IDK-401 |
| 41 | RUN-03 | MVP | IDK-406 | IDK-007, IDK-503 |
| 42 | CNT-01 | MVP | IDK-102 | IDK-106, IDK-407 |
| 43 | CNT-02 | MVP | IDK-202 | IDK-106, IDK-407 |
| 44 | CNT-03 | MVP | IDK-207 | IDK-404, IDK-201 |
| 45 | CNT-04 | MVP | IDK-207 | IDK-003, IDK-404, IDK-304 |
| 46 | CUR-01 | MVP | IDK-102 | IDK-001, IDK-203 |
| 47 | CUR-02 | MVP | IDK-102 | IDK-001, IDK-601 |
| 48 | CUR-03 | MVP | IDK-102 | IDK-002, IDK-407 |
| 49 | CUR-04 | MVP | IDK-407 | IDK-106, IDK-203 |
| 50 | SET-01 | MVP | IDK-409 | IDK-104, IDK-206, IDK-403 |
| 51 | SET-02 | MVP-hardening | IDK-502 | IDK-103 |
| 52 | AI-01 | MVP | IDK-403 | IDK-207, IDK-404 |
| 53 | AI-02 | MVP | IDK-403 | IDK-006 |
| 54 | DAT-01 | MVP | IDK-101 | IDK-408, IDK-409 |
| 55 | DAT-02 | MVP | IDK-401 | IDK-402, IDK-406 |
| 56 | PRV-01 | MVP | IDK-403 | IDK-409, IDK-404 |
| 57 | PRV-02 | MVP | IDK-403 | IDK-409, IDK-503 |
| 58 | SYS-01 | MVP | IDK-101 | every module ticket |
| 59 | SYS-02 | MVP | IDK-408 | IDK-101, IDK-407 |
| 60 | SYS-03 | MVP | IDK-402 | IDK-401 |

## Appendix 5 — NFR-01 through NFR-11, mapped individually

| ID | Category | Primary ticket | Supporting tickets | Evidence |
|---|---|---|---|---|
| NFR-01 | Accessibility | IDK-502 | IDK-103, all routed tickets | Automated axe plus keyboard/focus checks, and a manual screen-reader pass no automated check replaces. |
| NFR-02 | Reliability | IDK-401 | IDK-402, IDK-501 | Restart/reconciliation integration test; no ambiguous terminal result. |
| NFR-03 | Integrity | IDK-101 | IDK-102, IDK-108, IDK-204, IDK-407 | Append-only `audit_events` rejecting UPDATE/DELETE; immutability triggers; unauthorized/missing transition tests. |
| NFR-04 | Privacy | IDK-409 | IDK-403, IDK-010, IDK-503 | Disclosure gate, export/delete status, impact snapshot; privacy review. |
| NFR-05 | Safety | IDK-403 | IDK-406, IDK-401 | Fail-closed schema quarantine and no-execution/no-mutation negative tests. |
| NFR-06 | Observability | IDK-409 | IDK-401, IDK-403 | Structured correlated logs with the §8.5 redaction categories; failure record links to a safe diagnostic classification. |
| NFR-07 | Maintainability | IDK-101 | IDK-403, IDK-406 | Architecture import-boundary test plus contract tests against fake adapters. |
| NFR-08 | Performance | IDK-504 | IDK-408, IDK-401, IDK-402 | Representative recordings only; thresholds are set later by an approver and none is published here. |
| NFR-09 | Testability | IDK-403 | IDK-205, IDK-204, IDK-207, IDK-304, IDK-505 | Deterministic domain tests without live models; curated contract and regression fixtures. The PRD's five named evidence categories map to: transfer → IDK-108; mutation protection → IDK-106; citations → IDK-207; rubrics → IDK-204; provider-schema failures → IDK-403. |
| NFR-10 | Portability | IDK-406 | IDK-005, IDK-403 | Capability detection reporting supported / missing / incompatible without assuming availability. |
| NFR-11 | Compatibility | IDK-501 | IDK-101, IDK-102, IDK-407 | Representative Alembic upgrade fixtures, or a stop with a recoverable migration error. |

## Appendix 6 — Later / Post-MVP ticket list

No MVP acceptance criterion depends on any item below, and no MVP schema, port, or inactive UI control anticipates one.

| Ticket | Covers | Later requirements |
|---|---|---|
| IDK-601 | Go + AWS curriculum and Go runner support | RUN-04; CUR-02's deferral of Go+AWS |
| IDK-602 | OpenRouter and DeepSeek provider adapters on the existing `ProviderPort` | AI-03 |
| IDK-603 | Hosted authorization plus Postgres, object storage, managed queue, API model access, remote isolated runner, Google/email identity | SAAS-01, SAAS-02 |
| IDK-604 | Scheduling/study-time planning, voice, company-specific preparation, external telemetry | PRD §13 Post-MVP; telemetry gated by IDK-011. Payments, teams, social features, gamification and mobile require separate scope and are not assumed future commitments. |

## Appendix 7 — Deferred / TBD list

Nothing below has been answered, and no ticket's acceptance criteria assume an answer. Each names the decision ticket that must resolve it.

| Unresolved item | Decision ticket | Blocks |
|---|---|---|
| MVP curriculum spine; scenario-relevant DSA relations | IDK-001 | Production canonical v1 content (IDK-102); Phase 1/2 content exit |
| Editorial approval evidence and review criteria | IDK-002 | Production approval records (IDK-102); pilot-readiness (IDK-505) |
| Approved sources, licenses, snapshot/cache/withdrawal/replacement rules | IDK-003 | Real citations in IDK-207/IDK-201; content release |
| Size/retention limits (imports, artifacts, transcripts, generated content, retained runner output, job/event history, resolved cleanup records), diagnostic session expiry, overlay-proposal pending cap, generic pending-job cap, background age-promotion interval, janitor retention, SSE replay retention/expiry/maximum replay window; export package format and version, transcript inclusion, delete recovery, backups, log retention and support-access posture | IDK-010 | IDK-409; configurable placeholders in IDK-105, IDK-202, IDK-401, IDK-402 |
| External telemetry — whether permitted at all, and under what consent, disclosure, minimization and deletion rules | IDK-011 | IDK-604 only. MVP is local-only regardless of the outcome. |
| Performance acceptance thresholds | Approver, after IDK-504 records measurements | Release sign-off only; IDK-504 publishes no pass/fail number |

## Appendix 8 — Minimal-test inventory

One required automated test per implementation ticket by default; `None` where existing coverage or a required manual approval genuinely suffices. Each invariant is tested once, at the lowest useful level. Non-negotiable areas are marked **PRIMARY**.

| Ticket | Required automated test | Required manual review |
|---|---|---|
| IDK-001 – IDK-011 | None — decision framing carries no automated test (11 tickets) | Named approver review per ticket (11 reviews) |
| IDK-101 | Architecture import-boundary test; schema sweep for `owner_id`/`goal_id` on every table; owner-isolation + `audit_events` immutability repository test | — |
| IDK-102 | **PRIMARY** publication approval gate: approval-record read-gate, approval-last atomicity, half-seed invisibility; graph-validation property test; publish rejected without a `designated_editorial_approver` grant | Editorial review of half-seed and immutability fixtures |
| IDK-103 | `?mode=` submodes resolve without a new route, and `/app/mock` renders without the global shell — the two acceptance criteria existing coverage does not reach | — |
| IDK-104 | Two-goal isolation plus exact heading/role copy, stable values, no beginner/default, explicit-confirm-before-persist, accessibility and invalid-value fail-closed contract | — |
| IDK-105 | Diagnostic pause/refresh/restart preserves answers and explicit role/capability edits through confirmation; optional-step skip | — |
| IDK-106 | **PRIMARY** deterministic roadmap / no silent mutation: projector purity property test including stable-ID lexicographic tie-break | — |
| IDK-107 | **PRIMARY** atomic diagnostic confirmation: UoW rollback integration test | — |
| IDK-108 | **PRIMARY** conservative transfer / delete / tombstones: transfer + atomic tombstone/downgrade/audit property test | — |
| IDK-201 | Checkpoint seven-field + capability-ladder enum validation (LRN-03, DEP-02) and DEP-03 layer-reversal content regression | Editorial reversal-regression review |
| IDK-202 | Overlay-proposal stale rejection, pending content-hash dedupe, and placeholder-cap rejection | — |
| IDK-203 | **PRIMARY** import mapping: out-of-graph mapping rejection, normalized dedupe, imports-hash staleness trigger | — |
| IDK-204 | Re-evaluation append/exclusion; exact scenario/rubric/topic/capability/pair gates; five outcomes; ambiguity carry neutrality over assessed/correction/transfer baselines | Valid-alternative review under IDK-009 decision version 1.0 |
| IDK-205 | **PRIMARY** deterministic derived state with explicit now: order-independent replay, conflict/correction/transfer/ambiguity branches, 7/90/91 UTC boundaries and memo rollover, plus detailed/simple data preservation | — |
| IDK-206 | Recall-before-reveal; all schedule transitions; source-anchored due time; UTC cadence/interleave/budget; unique changed context; mapping fail-closed; zero review penalty | — |
| IDK-207 | Exact cache key, single-flight at enqueue, snapshot-mismatch staleness, and claim-level citation enforcement (CNT-04, NFR-09) | — |
| IDK-208 | Component: conclusion before details; tombstoned-source warning | — |
| IDK-301 | Bundle generic stable role/level with approved shared copy/dynamic heading/no company field; independently removable optional items | Refresher subject/layer/source/gap linkage review |
| IDK-302 | **PRIMARY** Practice timing: state-machine test (no hint before request, no feedback before Submit, append-only retry, cancel preserves attempt) plus IDK-008 static-limitation clauses on the approved RDB record | Adaptive follow-up specificity review |
| IDK-303 | **PRIMARY** Mock timing and exact safe-exit draft: byte-for-byte draft round-trip, blank-completion rejection, idempotent Complete, cancel preserves transcript, `409 mock_feedback_withheld` while nonterminal | Focused-shell review at all four viewports |
| IDK-304 | Controlled fixture-transcript regression (the only surviving use of fixture evaluation) | Report disclosure-ordering review |
| IDK-401 | **PRIMARY** durable job crash/restart/retry/cancel/dedupe/lane and terminal-result atomicity, plus one case per D4 retry type | Lane non-blocking observation |
| IDK-402 | **PRIMARY** SSE reconnect, duplicate tolerance, missed-replay GET reconciliation, keepalive is not a state change | Reconnect UX review |
| IDK-403 | **PRIMARY** disclosure and provider schema quarantine: fake-adapter argv/stdin/env, `412` pre-enqueue gate, three timer classifications, process-group cancel, quarantine isolation | Privacy redaction inspection of a `provider_requests` record |
| IDK-404 | Wiring integration: enqueue → real job claim → validated result → visible to caller | No-network-on-page-open confirmation |
| IDK-405 | **PRIMARY** six approved scenario/role/driver mappings plus curated driver pass/fail semantics and static/runtime separation: Run appends neither artifact nor evidence, Submit does, distinct result regions; approved RDB artifacts carry every IDK-008 limitation clause | Driver assertions, shared role calibration and review-specific limitation labels reviewed across levels |
| IDK-406 | **PRIMARY** runner matrix and threat model: all platform/JDK/state/message fixtures, paired-tool/sentinel/race checks, immutable snapshots/evidence/drivers/broker/runtime/workspace/filter/cleanup manifests, exact driver argv, relational absence/retired-signature closed-schema zero-side-effect rejection and static-review independence, unsupported modes, no-shell, resource boundaries, cancellation and cleanup | Root-broker/service/delegation, privilege-drop, runtime/filter/workspace/environment inspection plus per-tuple Ubuntu smoke |
| IDK-407 | **PRIMARY** atomic canonical merge: two-version fixture, base→latest, unresolved-conflict rejection, one-transaction acceptance, full rollback, unmapped-import reprocessing triggered | Accept-flow copy and overlay-wins pre-selection review |
| IDK-408 | **PRIMARY** owner/goal search isolation plus deterministic degraded fallback | Stale banner reflects real watermark |
| IDK-409 | **PRIMARY** export/delete/redaction: settings persist-and-expose positive path, stale-snapshot rejection, atomic delete effects, log redaction | Export package privacy review |
| IDK-501 | **PRIMARY** Alembic representative upgrades and recoverable migration failure | — |
| IDK-502 | **PRIMARY** essential accessibility flows (extends existing axe/keyboard/focus/reduced-motion coverage to new async states) | Screen-reader pass — the part no automated check replaces |
| IDK-503 | None — this ticket is approval review | Consolidated curriculum, source/licence, editorial, rubric/scenario, privacy and runner/database-absence threat-model review |
| IDK-504 | **PRIMARY** representative performance measurement harness — records distributions and outliers, publishes no threshold | Approver sets acceptance thresholds afterwards |
| IDK-505 | Mechanical scan that all thirteen scheduled prototype mechanisms are absent from shipped source, plus the final `owner_id` schema sweep | Final MVP readiness, scope, recovery and unsupported-claim audit — must explicitly disposition local Java execution as present in code but disabled and not shipped (`docs/runner/IDK-406-execution-deferral.md`), and the deferred IDK-502 screen-reader pass |
| IDK-601 – IDK-604 | None — test obligations are defined by the separate future approval, not assumed now | — (each item's scope approval is a future decision, not a review scheduled now) |

**Totals.** 37 required automated tests across 33 tickets (IDK-101 and IDK-102 each require three; IDK-503, the 11 decision tickets and the 4 Post-MVP tickets require none). 31 required manual reviews: 11 decision approvals, 3 in Phases 1–2 (IDK-102, IDK-201, IDK-204), 4 in Phase 3, 9 in Phase 4, and 4 in Phase 5.

## Appendix 9 — Completeness audit

- **60 Must requirements** appear individually in Appendix 4, each with exactly one primary verification owner. Counted against PRD §6: 64 rows minus 4 `Later` rows (RUN-04, AI-03, SAAS-01, SAAS-02) = 60. 59 are MVP; SET-02 alone is MVP-hardening.
- **NFR-01 through NFR-11** appear individually in Appendix 5, each with one primary owner.
- **D1 through D11** each map to at least one enforcing ticket and a named enforcing test in Appendix 3.
- **All 14 canonical routes** are mapped in Appendix 2, plus `/app/$pageId` validation and the not-found view. No route is added or removed.
- **Exactly two learning paths remain**: Learn (`/app/learn-roadmap`, `/app/topic-studio`) and Interview Prep (`/app/interview-hub` with its `?mode=refresher` and `?mode=questions` states, `/app/practice`, `/app/mock`). `/` is the workspace home; Evidence, Imports, Canonical updates, Search, Jobs, Settings and Reports are supporting destinations. Refresher and Questions remain independently reachable without a new canonical route.
- **All dependencies point backward** (Appendix 1). No ticket depends on a higher-numbered ticket. Phase 2–3 tickets that expose `202 JobRef` endpoints depend on IDK-101's `JobDispatcher` seam — the contract plus a synchronous in-process executor — which IDK-401 later replaces with the durable two-lane worker without changing the contract. No Phase 2–3 module writes `jobs_events` tables directly.
- **No Later or TBD work appears as MVP acceptance.** Section 6 tickets are `Later` with no MVP dependency. Every unresolved decision is carried as a `Blocked by` status and an explicit stop point, never as an assumed answer; configurable placeholders are marked non-final.
- **Non-negotiable verification areas have exactly one primary owner** (Appendix 8, marked **PRIMARY**): publication approval gate IDK-102; deterministic roadmap IDK-106; atomic diagnostic confirmation IDK-107; transfer/delete/tombstones IDK-108; import mapping IDK-203; derived state with explicit now IDK-205; Practice timing IDK-302; Mock timing and exact draft IDK-303; durable jobs IDK-401; SSE plus authoritative GET IDK-402; disclosure and quarantine IDK-403; static/runtime separation IDK-405; runner lifecycle IDK-406; atomic canonical merge IDK-407; search isolation IDK-408; export/delete/redaction IDK-409; Alembic upgrades IDK-501; accessibility flows IDK-502; performance measurement IDK-504. E2E coverage is not duplicated; where an existing Playwright test asserts prototype behavior, the ticket marks it REPLACED and names the API-backed successor. Two assertion overlaps found in adversarial review were resolved by assigning a single owner: the dismissed/disabled-review zero-delta assertion belongs to IDK-206 (IDK-205 references it), and the delete-preflight stale-snapshot rejection belongs to IDK-409 (IDK-108 owns only the tombstone/downgrade transaction).
- **Product name settled.** The product is **Yuno**. The prototype's inherited `Lattice` wordmark is renamed by IDK-103 (UI, markup, package metadata, test selector) and informs the export package name in IDK-409; the four localStorage prefixes and the export filename need no rename because IDK-107, IDK-303 and IDK-409 delete those paths. IDK-505 fails on any surviving `lattice` string. This is a resolved decision and correctly absent from Appendix 7.
- **Adversarially reviewed.** Six independent refutation passes (requirement fidelity, Appendix H fidelity, sequencing/buildability, invented-claim discipline, verification adequacy, internal contradictions) were run against this document; the invented-claim pass returned no defects, and every defect the other five raised and that was verified against the file has been corrected here.
- **Nothing is silently invented.** Approved policy values cite their attributed decision artifacts; unresolved performance, source, retention/delete, runner, privacy, and operational questions remain routed to the decision tickets still listed in Appendix 7. Implementation evidence never substitutes for a required approval, and approval never substitutes for activation evidence.
- **Prototype removals are each owned exactly once.** localStorage persistence: IDK-107 removes the legacy key and the onboarding/roadmap slices, and IDK-303 deletes `LEARNING_STORAGE_KEY` once the last practice/mock/evidence slice is API-backed — the interim window is stated explicitly in IDK-107 rather than left implicit. Static-review fixture scoring (`evaluateCode`, `SIMULATION_LIMITATION`) → IDK-405. Practice fixture feedback (`practiceFeedback`, `PRACTICE_QUESTIONS`) → IDK-302. Mock fixture transcript state → IDK-303. Fixture evaluation gating (`MOCK_FIXTURE_DRAFT`, `reportKind`, `FIXTURE_REPORT`) → IDK-304. Client-only evidence/dispute state → IDK-208. Import regex parser → IDK-203. Single hardcoded course fixture and `src/shared/model.test.ts` → IDK-104. Static lesson copy (`LESSON_CONTEXT`) → IDK-201. `navigateApp` pushState/popstate shim → IDK-103. Simulated jobs page → IDK-401. Canonical-update localStorage simulation and `UPDATE_ROWS` → IDK-407. Bundled search fixture (`SEARCH_ITEMS`) → IDK-408. Prototype export/reset, the operations-side localStorage store (`lattice.operations.state.v1`, its legacy key, `hydrateOperationsState`, `useOperationsState`) and the network tripwire → IDK-409. IDK-505 verifies all thirteen targets are absent, and its own scope enumerates the same thirteen.
- **Planning only.** This file is the sole artifact created. No application code, test, screenshot, dependency, migration, deployment, or other repository file was changed, and nothing was installed, migrated, published, deployed, or executed through a runner.
