# Production implementation specification

## 1. Authority, scope, and delivery ledgers

### 1.1 Authority order

When two statements conflict, apply this order:

1. The fixed product, route, and scope instructions in the implementation-specification request.
2. PRD Appendix H decisions D1–D11.
3. PRD `Must` requirements and NFR-01–NFR-11.
4. PRD Appendices A–G: invariants, contracts, operational states, acceptance, and traceability.
5. Remaining PRD prose, principles, journeys, and delivery sequence.
6. The surviving selected application as the approved UX/interaction reference where it does not conflict with items 1–5.
7. Existing fixture data, localStorage reducers, deterministic feedback, bundled search, simulated jobs, and network tripwires as prototype evidence only.

A `Later`, Post-MVP, or unresolved TBD item cannot become MVP through schema anticipation, an inactive UI control, or a future-facing port. Appendix H overrides earlier wording without exception.

### 1.2 Delivery ledgers

| Ledger | Included |
|---|---|
| MVP | Single built-in local owner; exactly Learn and Interview Prep; global profile and multiple goal workspaces; onboarding, persisted diagnostics, roadmap preview and approval; bounded Java/Spring Boot microservices plus AWS curriculum; representative connected System Design/RDB; scenario-relevant DSA; roadmap/overlays/bridges; topic layers; generation, sources and imports; evidence/evaluation/progress; notebook and optional review; independently reachable Refresher and Questions; Practice and focused Mock; offline canonical publication; opt-in canonical updates; Codex 5.6 Terra/high default and Claude alternative through CLI ports; Java compile/test runner; owner-scoped SQLite persistence; FTS5; durable two-lane worker; SSE; settings/export/delete. |
| MVP-hardening | SET-02 keyboard and assistive-technology acceptance; migration/recovery fixtures; accessibility checks; AI schema regression; privacy review; runner threat-model decision; content, source and rubric review; representative performance recordings; end-to-end pilot-readiness review. Hardening does not waive NFRs needed for safe earlier implementation. |
| Later/Post-MVP | RUN-04 Go execution and Go+AWS; AI-03 OpenRouter/DeepSeek; SAAS-01 hosted authorization; SAAS-02 Postgres, object storage, managed queues, API-hosted models, remote isolated runners and Google/email identity; scheduling/study-time planning; voice; separately approved company-specific preparation. |
| Unresolved | Curriculum topic spine; editorial review criteria; source approval/licensing/snapshot/withdrawal policy; role taxonomy descriptions; OS/toolchain matrix; provider CLI versions/install/auth discovery; runner enablement and resource limits; database exercise posture; assessment scenarios; size/retention limits; export/delete/logging lifecycle; external telemetry; diagnostic expiry; SSE replay retention. |
| Unsupported/non-goal in MVP | Authentication, cloud sync, tenancy, billing, teams, payments, social features, voice, company-specific preparation, real AWS, remote execution, mobile apps, gamification, strict offline guarantees, comprehensive or beginner curricula, hiring/interview/job outcome guarantees, hostile-code isolation, production/AWS proof. Redis, Kafka, Kubernetes, vector search, Electron, microservices, managed queues, Postgres, object storage and hosted identity are not MVP dependencies. |

The PRD contains no `Should` rows. There are 60 individually traceable `Must` requirements: 59 MVP and SET-02 in MVP-hardening.

## 2. Approved UX-to-system mapping

### 2.1 Shared interaction contract

- Desktop primary navigation remains **My learning / Learn / Interview prep**, with Search and Tools secondary.
- Mobile/tablet collapse navigation and course content into accessible drawers; ordinary pages become a single-column layout. Mock remains focused at every viewport.
- Historical **Resume** and explainable, dismissible **Recommended next** are separate records and surfaces. Neither overwrites or impersonates the other.
- The full roadmap remains visible. Learner Skip, Restore, order, depth and knowledge controls are persisted overlay decisions; recommendations never mutate them.
- All topic, depth, order, state, bridge, proposal and canonical changes show their effects and require explicit learner action.
- A skipped topic remains visible. Opening it must ask to restore it or open it read-only; it must not silently restore itself.
- `Run` is exploratory. Only `Submit` can append evidence.
- Practice hints appear only after request; feedback appears only after Submit and separates facts from trade-offs.
- Mock exposes only status, current question, answer field, safe exit and terminal completion. No ordinary global shell, hints, rubric, score, praise, recommendation, evaluation or Reports link appears while active.
- Reports and Evidence lead with a learner-readable conclusion and next action. Details disclose rubric dimensions, assumptions, sources, provenance, lineage, history and disputes.
- Imports remain visibly untrusted. Mapping means personal association, not factual verification.
- Destructive actions require a scope/impact preview, confirmation, observable progress and recovery status.
- All async routes use an explicit view state: `loading`, `empty`, `ready`, `stale`, `locked`, `unavailable`, `failure`. Retry/cancel controls appear only when the underlying operation allows them; recovery reconciles the authoritative GET resource.

### 2.2 Canonical routes

`P` means persisted server state; `D` means deterministic derived state.

| Route | Purpose, regions and commands | Modules; reads and writes; approvals/jobs | States, navigation, responsive/a11y | Requirements |
|---|---|---|---|---|
| `/` | My learning/home. Goal switcher, historical Resume, Recommended next with reason/dismiss, active goals, setup entry. | `profiles_goals`, `roadmap`, `evidence_progress`, `recommendations`. Reads P goals, last position, dismissal history; D next action and progress. Writes current goal, dismissal, navigation history. No silent roadmap write. | Empty: no goals → setup. Ready/stale: goal cards and explanation. Locked/unavailable: goal deleted/migration issue. Retry derived-progress read. Desktop cards stack on mobile; headings/regions, visible focus and labelled dismiss. Exits roadmap, topic, Interview Prep, setup and tools. | CORE-01/03/04/05, LRN-03/04, PRG-01/02 |
| `/app/onboarding` | Progressive setup, optional import, optional adaptive diagnostic, full roadmap preview, corrections and final approval. | `profiles_goals`, `diagnostics`, `imports`, `canonical`, `roadmap`. Reads P profile and approved graph; writes P diagnostic session/answers and preview edits. Confirm is one D11 transaction creating goal, LearningStates and overlay. Import parsing/generation may be background jobs. | `not-started → in-progress/skipped/paused → roadmap-preview → confirmed`; stale graph remains captured and later becomes a diff. Failure preserves answers; cancel leaves resumable draft. Native fields/fieldsets, error summaries, keyboard controls. Confirmed Learn exits to roadmap; Interview Prep exits to hub. | CORE-02/03/04/05, ONB-01/02/03, PRG-02, IMP-01, D11 |
| `/app/learn-roadmap` | Complete learner-controlled roadmap: sections, topic rows, evidence markers, Customize, Jump, Skip/Restore, depth, knowledge, order, bridges, proposals and canonical-stale annotations. | `roadmap`, `overlays`, `canonical`, `evidence_progress`. Reads P goal pin/overlay/corrections/proposals; D stable projection. Writes append-only overlay entries or proposal decisions. Every mutation requires explicit confirmation where it changes approved state. Bridge/proposal jobs may run in background. | Loading skeleton keeps hierarchy; empty only for invalid/unavailable approved graph; stale/conflict annotations do not mutate. Locked during atomic merge only. Failure retains last accepted projection. Desktop full rows; mobile collapsible controls. Topological-invalid order returns visible rejection. | CORE-04/05, LRN-01/04, DEP-01/02, GAP-01/02, CNT-01/02, CUR-04, D2/D9 |
| `/app/topic-studio` | Self-contained topic workspace: context, selected layer, Markdown, CodeMirror artifact, tutor conversation, evidence target, Run/Submit, rubric result, notebook/review/progress, Sources, course rail/drawer. | `learning_content`, `canonical`, `provider`, `runner`, `evidence`, `notebook_review`, `provenance`, `jobs`. Reads approved topic/content/cache/provenance and P drafts. Writes drafts, conversation turns, notebook entries, runner confirmation, evidence Submit. Generation, evaluation, source and runner jobs. | Layer loading/empty/stale/unavailable; generated-before-correction staleness offers explicit regenerate. Runner has confirmation/running/cancel/recovery. Static and runtime results are visually distinct. Desktop persistent rail; mobile focus-trapped drawer with focus restoration. CodeMirror labelled and keyboard reachable. | LRN-01/02/03/04, DEP-01/03, GAP-01/02, CNT-03/04, HND-01/02/03, RUN-01/02/03, NBK-01 |
| `/app/interview-hub` | Interview Prep home. Preserve separate cards for Refresher, Questions, Practice and Mock; bundle/subject editor; generic role/level; optional behavioral/leadership. | `interview`, `learning_content`, `evidence_progress`. Reads/writes P bundle, subjects and current run. No Learn prerequisite. | Refresher and Questions are independently deep-linkable as `/app/interview-hub?mode=refresher` and `?mode=questions`; these are states of the same canonical route, not new routes. Empty bundle offers copy/edit. Unavailable content/provider retains authored material. Cards remain keyboard buttons and stack on mobile. | INT-01/02/03, REF-01, CORE-01 |
| `/app/practice` | Selected question/scenario, answer, on-request hint, Submit, dimension feedback, facts/trade-offs, retry/repair, adaptive follow-up and append-only attempts. | `interview`, `evaluation`, `provider`, `evidence`, `jobs`. Reads bundle/run/turns/rubric; writes P drafts, requested hint, immutable attempt and follow-up. Interactive evaluation jobs. Submit is approval boundary for feedback/evidence. | Ready/answering/follow-up/submitted/evaluating/feedback-ready/failed-recoverable. Cancel evaluation preserves attempt. Retry never overwrites prior answer. Classroom rail becomes drawer. `aria-live` only announces status/feedback after Submit. | QPR-01/02, EVAL-01/02, HND-01, INT-01/02 |
| `/app/mock` | Focused text interview, one adaptive question at a time, exact draft persistence, Save & exit and terminal Complete confirmations. | `interview`, `provider`, `jobs`. Reads/writes P Mock run, turns and draft. Interactive next-turn jobs; final evaluation only after terminal completion. | Active/paused/resumed/follow-up/completing/completed/failed-recoverable. Safe exit preserves the exact draft and does not complete. Cancellation of next-turn generation preserves transcript. No hint/rubric/evaluation controls while nonterminal. Focused responsive shell and focus-restoring dialogs. | QMK-01/02, EVAL-01/02, D4 |
| `/app/reports` | Learner-readable Mock/practice conclusions and next action, then assumptions, facts/trade-offs, rubric dimensions, ambiguity, transcript and provenance. | `interview`, `evaluation`, `evidence_progress`, `provenance`. Reads P terminal runs/assessments; D current conclusions. No evaluative report before explicit Mock completion. Re-evaluation/dispute job entry. | Empty/unavailable before terminal completion; evaluating; feedback-ready; ambiguity-unresolved; stale after superseding evaluation. Never use fixture evaluation for blank, edited, incomplete or arbitrary transcripts. Mobile sections stack; disclosure details use semantic headings/details. | QMK-02, EVAL-01/02, PRG-01, CNT-04 |
| `/app/evidence` | “What your work supports”: conclusion, limitation, next action, evidence history, rubric, provenance, transfer lineage, disputes and re-evaluations. | `evidence`, `evaluation`, `progress`, `provenance`. Reads immutable P evidence/assessments/transfers; D LearningState/progress. Writes disputes, corrections and re-evaluation requests, never evidence overwrite. Interactive re-evaluation jobs. | Empty before Submit; ready; disputed; re-evaluating; ambiguity-unresolved; tombstoned-source warning; failure/retry. Detailed/simple display changes presentation only. Mobile conclusion precedes details. | CORE-04, PRG-01/02, EVAL-01/02, HND-01/02, D5/D6 |
| `/app/imports` | Original-preserving import, parsing, statement review, flags, mapping/correction/verification/dismissal and provenance. | `imports`, `canonical`, `jobs`, `learning_content`. Reads P originals/statements/current graph; writes learner decisions and approved personal mappings. Parse/reprocess jobs are background. No operation creates canonical content, evidence or completion. | Selected/parsing/parsed-untrusted/review/applied/failed/cancelled; unmapped and duplicates remain inspectable. Mapping to nonexistent topics rejected. New graph adoption reprocesses unmapped statements. Mobile source/review/actions stack. | IMP-01/02, CNT-03, CUR-01, D3/D10 |
| `/app/canonical-updates` | Base→latest published diff, impacts, selected changes, conflicts, overlay-wins recommendation, archived local topics, confirmation, accept/postpone/dismiss. | `canonical`, `roadmap`, `overlays`, `audit`. Reads approved versions and P goal state; writes one atomic merge. Diff generation may be background. Acceptance is the approval boundary. | Proposed/awaiting/conflict/accepted/postponed/dismissed/stale. Failure rolls back pin and all resolutions. Stale diff is recomputed base→latest. Sticky desktop action region becomes normal mobile flow. Fieldsets/radios explain consequences. | CNT-01/02, CUR-03/04, D1/D9 |
| `/app/search` | Search approved topic/content, generated artifacts, notebook and owned evidence; result routes to the owning view. | `search`, `jobs`. Reads FTS projection joined to owner/goal visibility. Writes only ephemeral query/history preference if approved. Rebuild/indexing is background. | Empty/results/stale-index/rebuilding/unavailable/failure. When stale, label degradation and use deterministic owned SQL fallback; retry rebuild. Results remain useful during background work. Search form and status announcement keyboard accessible. | SYS-02, NFR-08 |
| `/app/jobs` | Operational view of worker lanes, jobs, progress, results, diagnostics, retry, cancel and reconciliation. | `jobs_events`, `provider`, `runner`, `audit`. Reads P jobs/events/results; writes cancel/retry. No fabricated records. | Connected/reconnecting/unavailable SSE plus queued/running/succeeded/failed/cancel-requested/cancelled jobs. GET reconciliation is always available. Mobile job cards replace tables. Status is text plus icon, not color only. | DAT-02, SYS-03, NFR-02/05/06 |
| `/app/settings` | Global profile, goal settings, imports, provider/network disclosures, review, accessibility, progress display, export and destructive delete. | `identity_profile`, `profiles_goals`, `review`, `provider`, `settings_data`, `audit`. Writes versioned settings. Export/delete are durable jobs. Disclosure acceptance precedes first network enqueue. | Invalid/saved; provider unavailable; export running/failed/complete; delete preflight/confirmation/running/failed/complete. Impact preview names cross-goal evidence tombstones. Dialogs restore focus; OS and in-app reduced-motion respected. | SET-01/02, RET-01/02, PRG-01, PRV-01/02, CORE-03, NFR-01/04 |

`/app/$pageId` continues to validate the exact 13 page IDs. `/app/home`, retired concept routes and unknown IDs render the existing not-found experience linking to `/`.

## 3. Production architecture and module boundaries

### 3.1 Locked stack

- Client: React, TypeScript, Vite, TanStack Router, TanStack Query, Tailwind, accessible Radix/shadcn-style primitives, Markdown and CodeMirror.
- Server: FastAPI, Pydantic, SQLAlchemy, Alembic and SQLite with FTS5.
- Processing: one durable worker process with reserved interactive and background lanes; SSE.
- Contract: OpenAPI-generated TypeScript client is the only web API client.
- Tooling/testing: uv, pnpm, pytest, Vitest, React Testing Library and Playwright.

### 3.2 Dependency direction

```text
React routes/components
  → generated OpenAPI client and query hooks
    → FastAPI route adapters
      → application commands/queries + UnitOfWork
        → domain entities/services/policies
          → ports
            ← SQLAlchemy, SQLite/FTS5, CLI provider, source, runner adapters
```

Domain/application modules cannot import FastAPI, SQLAlchemy ORM types, subprocess APIs, FTS syntax or provider-specific payloads. Modules read one another through query interfaces and write through application commands or UoW-collected domain events. Cross-module ORM mutation is forbidden.

### 3.3 Module ownership

| Module | Owns | Principal services/ports |
|---|---|---|
| `identity` | Built-in local owner, role grants, future identity seam | `IdentityPort.local_owner`; `RolePolicy` |
| `profiles_goals` | Profile, goals, goal selection/archive | `ProfileRepository`, `GoalRepository` |
| `diagnostics` | Sessions, answers, preview and D11 confirmation | `DiagnosticService`, `DiagnosticRepository` |
| `canonical` | Versions, topics, relations, content revisions, editorial approval, publication | `CanonicalGraphRepository`, `PublicationService` |
| `roadmap` | Projection, overlay entries/proposals, bridges, canonical merge | `RoadmapProjector`, `OverlayAcceptanceService`, `GoalMergeService` |
| `learning_content` | Layers, generated artifacts/cache, topic conversation | `GenerationService`, `ArtifactRepository` |
| `imports` | Originals, statements, mappings and review decisions | `ImportMappingService`, `ImportRepository` |
| `provenance` | Sources, snapshots, claims and citations | `SourcePort`, `SourceRepository` |
| `evidence_evaluation` | Evidence, rubrics, assessments, disputes, corrections, derived progress | `DerivedStateService`, `EvidenceTransferService`, `ClockPort` |
| `notebook_review` | Notebook, review preferences/items/attempts/scheduling | `ReviewScheduler`, repositories |
| `interview` | Bundles, Refresher, Questions, Practice and Mock | `InterviewOrchestrator`, `InterviewRepository` |
| `provider` | Schema-validated generation/evaluation transport | `ProviderPort`, provider adapters |
| `jobs_events` | Durable jobs, two-lane dispatch, recovery, events and SSE | `JobRepository`, `JobRecoveryService` |
| `runner` | Confirmation, declared inputs, controlled execution and cleanup | `RunnerPort`, `ProcessPort`, `TempWorkspacePort` |
| `search` | Search documents, FTS5 projection and rebuild | `SearchPort`, `SearchProjectionRepository` |
| `settings_data` | Settings, disclosures, export/delete orchestration | `ExportPort`, `DeleteService` |
| `audit_observability` | Audit events, structured diagnostics and correlations | `AuditRepository`, diagnostic sink |

### 3.4 Unit-of-work and transaction rules

One HTTP command uses one application UoW. External model, source and runner operations never execute inside a SQLite write transaction.

Atomic UoWs are mandatory for:

- D1 publication: graph material plus approval last.
- D11 goal confirmation: goal, initial LearningStates, preview overlay and diagnostic confirmation.
- Overlay/bridge acceptance.
- D9 graph-pin move plus every conflict/unselected-change overlay entry.
- Evidence append plus progress-memo invalidation.
- Re-evaluation successor plus predecessor exclusion.
- Import mapping decision plus affected import-hash invalidation.
- Job enqueue/dedupe; job claim; terminal result plus state and event.
- Delete confirmation, evidence tombstones, dependent state downgrade and audit.

## 4. Relational model, invariants and migrations

### 4.1 Database conventions

- IDs: opaque `TEXT` UUID/ULID values.
- Timestamps: UTC `TEXT`, required unless the lifecycle has not reached that point.
- Booleans: `INTEGER CHECK(value IN (0,1))`.
- Extensible payloads: versioned JSON only for non-relational metadata; ownership, status, version and references remain columns.
- Every owner-owned table has `owner_id`; every goal-owned table also has `goal_id`.
- Composite `UNIQUE(id, owner_id[, goal_id])` and composite foreign keys prevent cross-owner/goal references.
- Mutable aggregates have `row_version INTEGER NOT NULL DEFAULT 1`; PATCH and commands use `If-Match`/expected version.
- Immutable histories reject UPDATE/DELETE through repositories and SQLite triggers. The only evidence “mutation” is a governed tombstone record plus removal of its separate payload.
- All enumerations have SQLite `CHECK` constraints.
- Foreign keys are enabled on every connection.
- Each module owns its tables and Alembic revisions; other modules may not write them directly.

### 4.2 Identity, profile, settings and lifecycle

| Table | Columns and constraints | Index/lifecycle |
|---|---|---|
| `owners` | `id PK`, `kind CHECK(local_builtin) UNIQUE`, `display_name`, `status CHECK(active,tombstoned)`, `created_at` | Singleton MVP owner; never authenticated. |
| `owner_role_grants` | `owner_id FK`, `role CHECK(learner,designated_editorial_approver)`, `assigned_at`, `assigned_by_owner_id`; PK `(owner_id,role)` | D1 keeps learner/editor roles distinct. |
| `learner_profiles` | `owner_id PK/FK`, experience/strength/weakness Markdown or versioned JSON, `profile_revision`, `updated_at` | Global, not goal-scoped. |
| `owner_settings` | `owner_id PK`, accessibility JSON, `progress_display CHECK(detailed,simple)`, `provider_selection`, `row_version`, `updated_at` | Simple display never removes detailed data. |
| `network_disclosures` | `id PK`, owner, operation/destination/data categories, `disclosure_version`, `accepted_at`, `revoked_at` | Unique owner/category/version; acceptance required before enqueue. |
| `export_operations` | owner, optional goal, `status`, format-version field, job/result/failure refs, timestamps | Async; exact package/version and retention remain TBD. |
| `delete_operations` | owner, optional goal, `scope`, impact snapshot, confirmation, status/job/failure refs | Scope and consequences fixed before confirmation; recovery/retention TBD. |

### 4.3 Canonical curriculum, content and provenance

| Table | Columns and constraints | Index/invariant/delete |
|---|---|---|
| `canonical_graph_versions` | `id PK`, `version_label UNIQUE`, `manifest_version`, `manifest_hash UNIQUE`, `status`, creator, timestamps, optional superseding version | Approved versions immutable; visible only through approval join. |
| `topic_identities` | `stable_id PK`, `stable_slug UNIQUE`, created/retired timestamps | Stable across graph versions. |
| `topics` | graph version + stable ID composite PK/FKs; title, subject, scope/level tags, target capability, recommended layer, checkpoint range, content revision | Index graph/subject; DSA requires scenario relation; curriculum tags enforce boundary. |
| `topic_relations` | graph, from/to stable IDs, relation type, rationale; unique tuple | Composite graph FKs; prerequisite cycles rejected; only explicitly configured non-prerequisite relation types may cycle. |
| `content_revisions` | graph/topic/layer, kind, status, Markdown ref/hash, prompt-template version, creator, supersedes ref, timestamp | Immutable. Unique graph/topic/layer/hash. |
| `editorial_approvals` | `id PK`, `graph_version_id UNIQUE`, approver owner/role, basis ref, timestamp | Inserted last; immutable. Approval criteria TBD. |
| `sources` | owner/editor origin, type, title, publisher, canonical URL, license status, availability status, timestamps | URL uniqueness subject to source policy; licensing policy TBD. |
| `source_snapshots` | source, retrieved timestamp, content ref/hash, status, version label, redacted failure | Immutable; unavailable/withdrawn preserved explicitly. |
| `claims` | parent content revision or generated artifact—exactly one—claim text/type/status | Claim types include fact, trade-off, comparative and time/version-dependent. |
| `citations` | claim, source, optional snapshot, locator, support kind, note | Unique claim/source/snapshot/locator. Citation is traceability, not truth. |

SQLite triggers reject UPDATE/DELETE on any graph, topic, relation, content or approval row belonging to an approved version.

### 4.4 Goals, diagnostics, overlays and roadmap

| Table | Columns and constraints | Index/invariant/delete |
|---|---|---|
| `goal_workspaces` | owner, name, path `learn/interview_prep`, subject/role, target level/capability, one graph pin, status, timestamps, row version | Index owner/status/recent. No goal mixes evidence or progress. |
| `diagnostic_sessions` | owner, captured approved graph, setup inputs, state, started/paused/expiry/failure, confirmed goal | D11; not LearningState. Expiry duration TBD. |
| `diagnostic_answers` | owner/session, sequence, question ref, answer, confidence, adaptive-context version, timestamp | Unique session/sequence; append-only. |
| `personal_overlays` | owner/goal unique, base graph, state, row version | Aggregate for accepted learner changes. |
| `overlay_entries` | owner/goal/overlay, target graph/topic, entry type, value, reason, source, approval timestamp, supersedes ref, content hash | Immutable history. Types: order constraint, skip, depth, bridge, archived local topic, merge resolution. |
| `overlay_proposals` | owner/goal, generated-against graph, topic, type, payload/hash, state/reason/timestamps | Partial unique pending `(goal_id,content_hash)`; configurable pending cap, value TBD. |
| `canonical_merge_proposals` | owner/goal, base/target versions, diff hash/ref, status/timestamps | Always base→latest; unique active target proposal. |
| `merge_items` | proposal, topic/relation/content change, selected flag, impact, conflict type, recommended and chosen resolution | Acceptance requires complete resolution. |
| `learning_states` | owner/goal/topic, graph, classification, origin, recommended depth, derivation version/input hash/timestamp | Unique goal/topic. Classification only likely-known/partial/unverified/new. |
| `learner_corrections` | owner/goal/topic, correction/confirmation/gap/transfer-confirmation, value, reason, timestamp, supersession | Append-only first-class D6 input. |
| `transferred_evidence_refs` | target LearningState, source goal/evidence, classification and rationale, created timestamp | Read-only reference; never copies evidence/completion. |
| `goal_progress_memos` | goal PK, coverage/proficiency/retention/readiness, explanation JSON, input hash, derivation version, explicit computed-at | Cache only; recomputed deterministically on stale read. |

Approved overlay order entries are additional precedence constraints. A write that would conflict with canonical prerequisites or create a cycle is rejected with a visible reason. Projection then uses topological ordering with stable-ID lexical tie-breaking.

### 4.5 Evidence, evaluation, notebook and review

| Table | Columns and constraints | Index/invariant/delete |
|---|---|---|
| `evidence` | owner/goal/topic, type, capability, payload hash, summary, origin, timestamp | Immutable metadata; index goal/topic/time. |
| `evidence_payloads` | `evidence_id PK`, content ref/body, content version | Removed only by governed delete. |
| `evidence_tombstones` | `evidence_id PK`, delete operation, reason, timestamp | Presence means content unavailable while classification lineage remains. |
| `rubrics` | `id PK`, task/capability/role context, version, status, provenance | Approved fixture/version required. |
| `rubric_dimensions` | rubric, stable dimension ID/name, description, ordinal, evaluation guidance | Unique rubric/dimension. |
| `assessments` | owner/goal/evidence/run, rubric version, state, assumptions, facts/trade-offs/ambiguities, feedback, successor/predecessor refs, derivation-excluded flag | Immutable result; append-only re-evaluation. |
| `assessment_dimension_results` | assessment/dimension, qualitative outcome or score representation, rationale, evidence refs | Unique assessment/dimension; scoring policy TBD. |
| `assessment_disputes` | owner/goal/assessment, reason, status, requested/resolved timestamps and resolution note | Immutable request/history. |
| `reevaluation_requests` | dispute, prior assessment, job, status and resulting assessment | New result supersedes; does not overwrite. |
| `notebook_entries` | owner/goal, optional topic/evidence/source, `entry_kind CHECK(auto,user)`, Markdown, timestamps, optional tombstone | Per-goal notebook is a query, not one mutable blob. |
| `goal_review_preferences` | owner/goal PK, enabled, duration/cadence/type settings, row version | Disabled reviews impose no penalty. |
| `review_items` | owner/goal/topic, prompt ref/type, ready/due/dismissed/disabled/generation-failed/completed, due/interval/context | Index goal/status/due. |
| `review_attempts` | owner/goal/item, response, optional confidence, feedback/correction, next interval, context variation/result, timestamp | Immutable; answer remains hidden until response. |

The precise derived-state rules, dimension representation and review scheduling parameters must be versioned and approved before Phase 2 exit; no numeric weights are invented here.

### 4.6 Interview and hands-on

| Table | Columns and constraints | Index/invariant |
|---|---|---|
| `interview_bundles` | owner, optional goal, name, generic role/level, origin, copy source, status, row version | No company field/claim. |
| `interview_bundle_items` | bundle, subject, optional topic/question, position, optional/included | Behavioral and leadership independently removable. |
| `interview_runs` | owner, optional goal/bundle, mode Practice/Mock, role/level, state, timestamps, final assessment | Terminal Mock immutable. |
| `interview_turns` | run, turn number, speaker, question/answer/hint/feedback/follow-up kind, body, timestamp | Unique run/turn. DB/service rejects Mock hint or feedback while nonterminal. |
| `interview_turn_results` | answer turn, assessment, visibility timestamp | Practice visible after Submit; Mock visible only after completion. |
| `hands_on_work` | owner/goal/topic/scenario, state, timestamps | Aggregate for complete workflow. |
| `hands_on_artifacts` | work, revision number, kind, content ref/hash, timestamp | Immutable revisions. |
| `hands_on_reviews` | work/artifact/assessment, review mode, required limitation label | Static mode requires a nonempty limitation. |

### 4.7 Imports, generation, provider, jobs, runner and search

| Table | Columns and constraints | Index/invariant |
|---|---|---|
| `import_records` | owner, optional goal, type, original content ref/hash, parser version, status, timestamps/failure | Original immutable and inspectable. |
| `import_statements` | owner/import, sequence, original/normalized hash, parsing confidence, trust and mapping states, corrected text, timestamps | Unique import/sequence; identical unmapped hashes deduplicated per owner/version. |
| `import_statement_mappings` | owner/goal/statement, existing topic, graph version, decision type, accepted/revoked timestamps | Defines approved personal import hash; never creates topic/evidence. |
| `generated_artifacts` | owner/goal/graph/topic/layer/type, imports hash, template version, exact cache key/hash, state, body ref/hash, provider/model, timestamp, job | Unique D3 cache key. |
| `artifact_provenance_snapshots` | artifact, evidence/state hash, profile hash, provider/model, generation time, schema/contract versions | Immutable personalization snapshot. |
| `artifact_provenance_refs` | artifact, kind and referenced entity | Unique artifact/kind/ref. |
| `provider_requests` | owner/goal/job, purpose, adapter/contract versions, context-ref hash, disclosure ref, PID/PGID/temp path, lifecycle/diagnostic | Raw prompt is not a normal log field. |
| `schema_quarantines` | provider request, raw-output secure ref/hash, schema version, validation errors, timestamp | Cannot be result/evidence/governed mutation. |
| `jobs` | owner, optional goal, kind, lane, state, retryable, dedupe key, attempt, payload/result refs, diagnostics, lease/worker, timestamps | Partial unique active dedupe; indexes lane/state/queue time. |
| `job_attempts` | job/attempt, process identity, PID/PGID/temp path, start/end/outcome/diagnostic | Immutable retry history. |
| `job_events` | event ID, owner/job, state/type, timestamp, progress/result ref, retryable, correlation IDs | SSE source; indexed owner/event and job/event. |
| `job_results` | job unique, typed result kind/ref/hash, committed timestamp | Inserted atomically with terminal state. |
| `runner_records` | job, owner/goal/artifact, confirmation, language/toolchain, argv JSON, environment-policy version, limits config version, PID/PGID/temp path, state/outcome/cleanup | Java MVP; Python/DB only configured; Go rejected as Later. |
| `runner_inputs` | runner, logical path, content ref/hash, declared type | No undeclared inputs. |
| `runner_output_chunks` | runner, stream, sequence, content ref, truncation flag, timestamp | Unique runner/stream/sequence. |
| `search_documents` | entity type/ID, owner/goal/version/topic, title/body/tags, projection version, updated time | ACL/ownership source table. |
| `search_index_state` | projection name PK, version, status, source watermark, job/failure refs, timestamps | Ready/stale/rebuilding/failed. |
| `search_fts` | FTS5 title/body/tags with external `search_documents` content | Owner/goal filtering occurs by joining results to `search_documents`. |
| `audit_events` | owner/goal/actor role, entity/action, before/after hashes, reason, correlation IDs, timestamp | Append-only; excludes avoidable sensitive payloads. |

Unapproved retention, backup and recovery guarantees remain TBD. Physical deletion is not scheduled until the lifecycle policy is approved.

### 4.8 Alembic and versioning

- Server and offline publisher refuse to operate unless the database is at the single expected Alembic head.
- Use forward-only expand/backfill/contract migrations. A failed migration stops startup with a recoverable diagnostic; it cannot expose a partially upgraded service.
- Representative upgrade fixtures include: two goals and transferred evidence; paused diagnostics; approved graph v1/v2; overlay conflict/deleted topic; imports; generated artifact; active/recovered jobs; Mock transcript; stale FTS projection.
- FTS rebuild is an idempotent background job reconstructed from source tables. Until atomic completion, the prior projection is marked stale and deterministic fallback remains available.
- Independently version: Alembic schema, canonical manifest, graph, content revision, overlay format, import parser, prompt template, provider contract, derived-state rules, generated artifacts, job payload/result, FTS projection and export format.
- Approved canonical versions are never data-migrated in place; publish a new version and use D9.
- Exact export format, backup posture, retention and delete recovery remain approval gates.

## 5. OpenAPI, domain, job and SSE contracts

### 5.1 Common API rules

- Base path: `/api/v1`.
- OpenAPI is the source of truth; generated TypeScript types are checked for drift in CI.
- The local owner is resolved server-side. Client-supplied owner IDs are ignored or rejected.
- Goal resources are checked against both owner and goal.
- Mutating creates/actions use `Idempotency-Key`; PATCH uses `If-Match`. A reused key with a different request hash returns `409`.
- Successful synchronous create: `201`; async enqueue: `202` with `JobRef`; read/update: `200`; completed deletion without body: `204`.
- Error shape: `code`, `message`, `request_id`, `correlation_id`, `retryable`, optional `field_errors`, `current_state`, `job_id`, `recovery_action`.
- Principal statuses: `400` malformed, `404` absent/out of scope, `409` invalid transition/stale/dedupe, `410` expired/tombstoned, `412` missing disclosure or stale `If-Match`, `422` domain/schema violation, `423` operation locked, `429` configured pending cap, `503` unavailable/migration/provider/runner, `504` only for synchronous gateway timeout.
- Every accepted mutation emits an audit event. Enqueue and terminal result have separate audit effects.
- No canonical publication write endpoint exists in MVP.

### 5.2 Endpoint inventory

| Group | Methods and paths | Transaction/result behavior |
|---|---|---|
| Profile | `GET/PATCH /profile` | Profile revision and audit. |
| Goals | `GET/POST /goals`; `GET/PATCH /goals/{goalId}`; `POST .../archive`; `POST .../delete-preflight`; `POST .../delete` | Goal create synchronous unless through D11. Delete returns job after confirmed impact. |
| Onboarding/diagnostics | `POST /diagnostics`; `GET/PATCH /diagnostics/{id}`; `POST .../answers`; `GET .../roadmap-preview`; `POST .../confirm-goal` | Confirm is atomic D11; `409` already confirmed, `410` expired. |
| Roadmap/corrections | `GET /goals/{goalId}/roadmap`; `GET .../learning-states`; `POST .../corrections`; `POST .../order-constraints`; `POST .../skip-decisions`; `POST .../depth-overrides` | Writes immutable overlay/correction records; returns new projection version. |
| Overlays/bridges | `GET /goals/{goalId}/overlay-proposals`; `POST .../overlay-proposals`; `POST /overlay-proposals/{id}/decision`; `POST /bridges/{id}/decision` | Accept revalidates graph and applies atomically; stale returns `409 proposal_stale`. |
| Topics/layers | `GET /topics/{topicId}?graph_version=`; `GET /goals/{goalId}/topics/{topicId}/layers`; `GET .../layers/{layer}`; `POST .../generate`; `POST /artifacts/{id}/regenerate` | Approved graph only. Generation/regeneration returns `202 JobRef`. |
| Imports | `POST /imports`; `GET /imports/{id}`; `POST .../parse`; `GET .../statements`; `PATCH /import-statements/{id}`; `POST .../map`; `POST .../verify`; `POST .../dismiss`; `POST /imports/{id}/reprocess` | Original create `201`; parsing/reprocess `202`; decisions cannot affect canonical/evidence. |
| Sources/provenance | `GET /sources`; `GET /sources/{id}`; `GET /claims/{id}`; `GET /artifacts/{id}/provenance` | Withdrawn/unavailable status retained. Source retrieval is disclosure-gated async. |
| Evidence/evaluation | `POST /goals/{goalId}/evidence`; `GET .../evidence`; `GET /evidence/{id}`; `POST .../assess`; `GET /assessments/{id}`; `POST .../disputes`; `POST .../reevaluate` | Submit creates immutable evidence. Evaluation/re-evaluation returns JobRef. |
| Notebook/review | `GET/POST /goals/{goalId}/notebook`; `PATCH/DELETE /notebook/{id}`; `GET/PATCH .../review-preferences`; `GET .../reviews`; `POST /reviews/{id}/attempts`; `POST .../dismiss` | Review dismissal/disable has no progress penalty. |
| Progress/readiness | `GET /goals/{goalId}/progress?now=`; `GET .../learning-state-explanations` | Server chooses authoritative clock unless a test-only clock port is injected; response records effective `now` and rule version. |
| Bundles/Refresher/Questions | `GET/POST /interview-bundles`; `GET/PATCH/DELETE /interview-bundles/{id}`; `POST .../copy`; `GET /goals/{goalId}/refreshers`; `GET .../questions` | Generic role/level only. |
| Practice/Mock | `POST /interview-runs`; `GET /interview-runs/{id}`; `POST .../answers`; `POST .../hints`; `POST .../pause`; `POST .../resume`; `POST .../complete`; `GET .../report` | Mock hint/interim report returns `409 mock_feedback_withheld`. Complete is idempotent terminal action. |
| Canonical reads/diffs | `GET /canonical/versions`; `GET /canonical/versions/{id}`; `GET /goals/{goalId}/canonical-update`; `POST /canonical-update-proposals/{id}/accept`; `POST .../decision` | Only approved versions returned. Merge acceptance is atomic D9. |
| Provider disclosures | `GET /disclosures`; `POST /disclosures/{category}/accept`; `POST .../revoke`; `GET /provider-capabilities` | Capability reports configured/unavailable, not assumed. |
| Runner | `GET /runner/capabilities`; `POST /runner/confirmations`; `POST /runner-runs`; `GET /runner-runs/{id}`; `POST .../cancel` | Confirmation and declared inputs required; returns JobRef. |
| Jobs | `GET /jobs`; `GET /jobs/{id}`; `POST .../retry`; `POST .../cancel`; `POST .../reconcile` | Retry type is determined by job kind; runner retry requires fresh confirmation. |
| Events | `GET /events` SSE | Owner-scoped events; supports `Last-Event-ID`. |
| Search | `GET /search?q=&goal_id=&types=`; `POST /search-index/rebuild`; `GET /search-index/status` | Rebuild background; stale status explicit. |
| Settings/export/delete | `GET/PATCH /settings`; `POST /exports`; `GET /exports/{id}`; `POST /delete-operations`; `GET /delete-operations/{id}` | Destructive request must reference an unchanged impact snapshot. |

### 5.3 Domain contracts

| Contract | Required fields |
|---|---|
| `GenerateRequest` | Purpose; owner/goal/topic/layer; graph version; structured context references; capability target; output-schema version; safety mode; provider choice; prompt-template version; disclosure reference. |
| `GenerateResult` | Succeeded/failed/quarantined; validated payload or none; provider/model/contract version; timestamp; provenance references; warnings; failure classification; result hash. |
| `EvaluationRequest` | Evidence/answer and task refs; rubric/version; assumptions; requested capability; source/provenance refs; role/level; static/runtime method. |
| `EvaluationResult` | Dimension outcomes and rationales; facts; trade-offs; citations; ambiguities; feedback; cross-question candidate; revision invitation; warnings and limitation labels. |
| `ImportParseResult` | Parser version; original hash; ordered statements; normalized hashes; confidence as parsing metadata only; warnings; duplicate candidates. |
| `CanonicalDiff` | Base/target approved versions; topic/relation/content changes; local overlay/evidence impacts; conflicts; selected state; target-version resolutions; diff hash. |
| `RunnerSpec` | Confirmation; language/capability; declared inputs and hashes; direct argv; working-directory policy; environment-policy and limits versions. |
| `RunnerResult` | Compile/test/static phases; exit/signal/limit state; structured stdout/stderr refs and truncation; duration; cleanup state; explicit limitation. |
| `JobPayload` | Kind/schema version; owner/goal; lane; dedupe key; typed request ref; disclosure/confirmation refs; correlation IDs. |
| `JobResult` | Kind/schema version; authoritative result reference/hash; warnings; diagnostic reference; terminal timestamp. |
| `ProvenanceSnapshot` | Graph/content/import/evidence/profile hashes; source/claim/citation refs; provider/model; contract/template versions; generation time. |
| `QuarantineRecord` | Request/job, output hash/secure ref, expected schema, validation failures, timestamp; never a result reference. |
| `Warning` | Stable code; severity; learner-safe message; affected field/ref; retry/recovery action. |
| `ResultRef` | Type, entity ID, schema version, content hash and route/API locator. |

### 5.4 SSE contract

Each event contains:

- `event_id`: opaque monotonically ordered ID for the persisted event stream.
- `job_id`, `owner_id`, optional `goal_id`.
- `state` and `event_type`.
- `timestamp`.
- optional typed `progress` or `result_ref`.
- `retryable`.
- `request_id`, `correlation_id` and optional `run_id`.

Rules:

1. Clients send `Last-Event-ID` when reconnecting.
2. The server returns later retained owner-scoped events in event-ID order.
3. Clients deduplicate by event ID and tolerate duplicate delivery.
4. After connection loss, the client always reconciles watched jobs with `GET /jobs/{id}`; GET state and committed result are authoritative.
5. An unavailable/replay-missed stream shows reconnecting/unavailable status and a Refresh action.
6. Exact replay retention, event expiry and maximum replay window remain TBD; the API must not promise replay beyond retained events.
7. A keepalive may maintain transport but is not a job-state event.

## 6. Canonical graph, overlays, generation, sources and imports

### 6.1 D1 offline publication

1. Publisher checks the database is at Alembic head.
2. It validates manifest version/hash, stable IDs, curriculum tags, layer/checkpoint data, relationship references, prerequisite DAG, claim/citation shapes and source statuses.
3. It verifies an explicit `designated_editorial_approver` grant. The MVP local owner may act in that role, but the audit actor remains editorial rather than learner.
4. Against a stopped server, or within one SQLite transaction, it inserts a new version and all dependent material.
5. It inserts `EditorialApproval` last and commits.
6. Failure rolls back everything. A version without an approval is invisible to all catalog, topic, search, generation, roadmap and diff reads.
7. An already approved version cannot be changed or deleted. Corrections require another version.
8. MVP fixtures include approved v1/v2, a half-seeded version, invalid relation/cycle, an overlay conflict and an upstream-deleted topic carrying local state.

There is no in-app authoring/publication UI or publication API.

### 6.2 D2 roadmap projection

Inputs are the goal’s single approved graph pin, accepted overlay entries and explicit learner corrections. Pending proposals/conflicts are annotations only.

Algorithm:

1. Load all graph topics; never remove a transferred-evidence topic.
2. Apply accepted skip/depth/bridge/archive annotations without changing canonical rows.
3. Add approved learner order constraints to canonical prerequisite edges.
4. Reject any order constraint that creates a cycle or violates an unmodified prerequisite.
5. Topologically sort; when multiple nodes are available, select stable IDs lexically.
6. Attach evidence, state, explanation, pending proposals and conflicts.
7. Hash the projection inputs and return a projection version.

Opening, refreshing, recommendation generation and provider output cannot write the overlay.

### 6.3 D9 canonical merge

- Diff is always current goal base → latest approved version, never chained.
- “Accept selected” still moves the goal to one complete target graph. Unselected upstream changes are preserved as target-version overlay entries representing the learner’s retained local choice.
- Every conflict must have a resolution. Overlay-wins is preselected and explained, not silently applied.
- An upstream-deleted topic with evidence or overlay state becomes an archived-local-topic entry.
- One transaction updates the graph pin, writes all target-version overlay entries/resolutions, closes the proposal, invalidates roadmap/generated-content/import/search projections and audits the merge.
- Any stale version, unresolved conflict or write failure rolls back the entire transaction.

### 6.4 D3 generated-content cache

Exact key:

`(canonical_graph_version, topic_id, goal_id, layer, topic_mapped_approved_imports_hash, prompt_template_version)`

Provider/model, profile and live evidence are excluded from the key. They are recorded in the personalization snapshot.

- Enqueue uses a unique active cache-key constraint: cache hit returns the artifact; active hit returns the same JobRef; otherwise one job is created.
- Current profile/evidence/provider/model snapshot is compared with the baked snapshot. A mismatch displays staleness and offers regeneration.
- Regeneration occurs only after explicit learner action or a key-changing accepted canonical merge/import mapping.
- Recommendation/review channels carry adaptive emphasis/examples/exercises; cached lesson bodies are never silently rewritten.
- Schema-invalid output is quarantined and cannot become content/evidence/state.
- Artifact, provenance and terminal job result commit atomically.

### 6.5 Sources and citations

- Claims classify the kind of authority needed; official documentation, standards/specifications and primary sources are preferred where appropriate.
- Sensitive, disputed, comparative and time/version-dependent claims expose claim-level citations.
- Routine content remains self-contained with expandable provenance.
- Citation presence never establishes truth or canonical status.
- Withdrawn/unavailable sources remain visible with status and last known provenance. Their handling, snapshot rights and replacement policy require source-policy approval.
- Source retrieval is a disclosed network operation and cannot be silently triggered.

### 6.6 D10 imports

1. Preserve the exact original and hash.
2. Parse asynchronously into ordered untrusted statements with parser provenance.
3. Deduplicate normalized statements; no match remains `unmapped`.
4. Mapping targets an existing topic in the goal’s approved graph only.
5. Learner may correct, map, accept for personal context, verify as their own assertion, or dismiss. Learner acceptance is not editorial or factual authority.
6. Approved personal mapping changes the per-topic imports hash and surfaces D3 staleness.
7. Graph adoption reprocesses previously unmapped statements.
8. Imports never create topics, expand scope, become canonical truth, become evidence or establish completion.

## 7. Learning, evidence, notebook, review, Practice and Mock

### 7.1 Learning contract

Capability ladder: `know → understand → choose → implement → diagnose → defend`.

Topic layers remain:

`Essential`, `Implementation`, `Internals`, `Production`, `Alternatives`, `Failures`, `Interview`, `Sources`.

A problem-first checkpoint names:

- the scenario and role-appropriate constraints;
- target capability;
- expected artifact, code, design or decision;
- estimated 30–60 minute session range;
- rubric and assumptions;
- evidence criterion;
- material static/runtime limitation.

Hands-on lifecycle:

`scenario → artifact/code/design/decision → rubric review → adaptive cross-question → revision → submitted evidence`

Multiple valid solutions are accepted when their assumptions and consequences are defensible. Feedback separates factual corrections from trade-offs.

### 7.2 Evidence and derived state

- Evidence is immutable, goal-scoped and append-only.
- Viewing, reading, running, elapsed time and fixture completion never create evidence.
- Cross-goal transfer creates a target LearningState plus read-only transfer reference; no content or completion is copied.
- Deleting a source goal removes referenced evidence payloads, records tombstones and downgrades dependent states to `unverified` in one audited transaction.
- Assessment disputes append. Re-evaluation creates a successor and excludes the predecessor from derivation without deleting history.
- Unresolved ambiguity alone cannot reduce readiness.
- Derived state is server-side deterministic: `f(eligible evidence, corrections/confirmations, explicit now, rule version)`.
- Corrections override inference until explicitly superseded.
- Dismissed/disabled reviews carry no penalty.
- Coverage, proficiency, retention and readiness responses include definitions, supporting evidence, uncertainty and rule version. They are not interview or job predictions.
- Detailed/simple is presentation-only.

### 7.3 Notebook and review

- Notebook entries are goal-scoped and labelled `auto` or `user`.
- Entries can reference a topic, evidence item or source.
- Review is optional and non-blocking.
- Retrieval prompts require recall/explanation/application before reveal.
- Attempts record optional confidence, correction/feedback, next interval and later varied-context result.
- Scheduling parameters are versioned and configurable; exact algorithm/limits require approval.
- Disabling or dismissing review changes future suggestions only.

### 7.4 Refresher, Practice and Mock

| Mode | Hints | Feedback | State/evidence |
|---|---|---|---|
| Refresher | Not assessment hints | Source-linked concise explanation | Independent of Learn completion; linked to subject/layer/source/evidence gap. |
| Questions | Question selection/bundle controls | None until entering Practice | Independently reachable Interview Prep submode. |
| Practice | Only after explicit request | Only after Submit; per attempt; facts vs trade-offs; rubric dimensions | Attempts append; retry/repair preserves history; adaptive follow-ups. |
| Mock | Never while active | Consolidated only after explicit terminal completion | Exact draft safe exit/resume; one adaptive turn at a time; terminal transcript fixed. |

Fixture evaluation is permitted only for the exact unedited complete fixture transcript used by a controlled regression test. Blank, incomplete, edited or arbitrary transcripts must be transcript-only or use a validated production evaluator; they never inherit fixture scoring.

## 8. Provider, jobs, runner, search, privacy and observability

### 8.1 D7 CLI provider transport

- Adapter constructs an argv array and never invokes a shell.
- Prompt/context uses stdin or a restricted temporary file, never argv.
- Unused stdin is closed to `/dev/null`.
- Mandatory provider-specific noninteractive configuration is required.
- Environment variables come from a provider-specific allowlist. The runner has a different minimal allowlist.
- Network disclosure is checked before enqueue.
- Three configurable timers exist: first-output heartbeat, inactivity timeout and absolute timeout. Values remain TBD.
- No-first-output failure is classified as recoverable provider configuration/authentication, not generic timeout.
- Cancel/timeout terminates the process group and descendants.
- Persist PID, PGID, temp path and process-start identity. Startup must verify recorded process identity before signalling; if identity cannot be verified, report cleanup failure rather than killing an unrelated reused PID.
- Timeout-truncated output is retryable diagnostic material, not schema quarantine.
- Each adapter pins a contract version such as JSONL events plus final JSON.
- Validated output alone crosses the provider port.
- Exact CLI commands, versions, installation and authentication discovery remain TBD.

### 8.2 D4/D8 durable jobs

Lifecycle:

`queued → running → succeeded | failed | cancel-requested → cancelled`

`failed + retryable=true` is the sole failed-recoverable representation.

- One worker process owns two reserved dispatch loops: interactive and background. FIFO holds within each lane.
- Background work cannot occupy the interactive slot.
- Background age promotion changes scheduling priority after a configured interval; the interval is TBD.
- Pending-job cap is configured and visible; value TBD.
- Dedupe/single-flight is enforced at enqueue.
- Startup reconciliation:
  - queued remains queued;
  - running has recorded process groups/temp paths reconciled, then becomes failed/retryable;
  - cancel-requested becomes cancelled without retry.
- Result artifact/reference, terminal job state and terminal event commit in one transaction.
- Cancellation races:
  - if terminal result committed first, terminal state wins;
  - if cancellation commits before result, late result is discarded/quarantined;
  - repeated cancel returns the authoritative state.
- Retry:
  - indexing/import: idempotent rerun;
  - generation: cache-checked rerun;
  - interview: resume with explicit substitution record;
  - runner: new user confirmation and fresh run.
- Retry short-circuits to succeeded if a committed result already exists under the dedupe key.
- Janitor removes terminal temp directories and records cleanup failures. Retention timing is TBD.

### 8.3 Controlled runner

- Java compile/test is the MVP runtime capability.
- Python and relational database controls appear only after capability detection/configuration.
- Go is rejected as Later.
- Each run requires explicit confirmation and declared input hashes.
- No shell; direct argv only.
- Per-run temporary workspace and separate minimal environment; no AWS credentials injected.
- Runtime/toolchain detection reports supported, missing or incompatible without assuming availability.
- Configurable wall-time, process, memory/CPU where enforceable, file/output and temporary-storage limits; exact values are TBD.
- Output is structured, ordered and truncated according to approved limits.
- Cancellation targets the process group and proceeds to cleanup.
- UI distinguishes static analysis, compilation and test execution.
- Passing local execution is not a sandbox, hostile-code isolation, production, AWS or security proof.
- If runner posture is not approved, the feature remains disabled while static workflow remains usable.

### 8.4 FTS5 search

- Index approved canonical topic/content, owned generated content, notebook and eligible evidence metadata.
- Do not index tombstoned evidence payloads, quarantined output, raw provider context, runner output or unreviewed import originals by default.
- Every FTS result joins to `search_documents` for owner/goal filtering.
- Projection writes are idempotent background jobs.
- `stale-index` shows source watermark and rebuild status.
- While stale/unavailable, deterministic fallback searches owned projection source rows using stable ordering and labels degraded results.
- Rebuild writes a new projection generation and switches only after success.
- Navigation/search responsiveness is measured while background jobs and SSE are active.

### 8.5 Privacy and observability

Data minimization categories:

- required learner context;
- selected evidence/answers;
- approved import excerpts;
- canonical/source context;
- requested output schema;
- operation metadata.

Redaction categories:

- credentials, tokens, cookies and authorization headers;
- provider auth environment values;
- AWS keys and connection secrets;
- unrelated environment variables;
- avoidable absolute user paths/usernames;
- raw prompt/transcript/artifact bodies in ordinary logs;
- quarantined raw output.

Structured local logs carry request, correlation, owner, goal, job, provider-request and runner IDs. Learner-visible failure records link to a safe diagnostic classification. External telemetry is absent unless separately approved and disclosed; consent and lifecycle remain TBD.

Export must cover profile, goals, graph pins, overlays, evidence metadata and available payloads, notebook, review, diagnostics, interviews/transcripts according to the approved package policy, imports and provenance. Unavailable or tombstoned content is represented as unavailable, never fabricated.

### 8.6 Performance methodology

No pass threshold is invented. Record:

- device/OS/runtime/toolchain and dataset shape;
- cold/warm navigation;
- full-roadmap render and interaction;
- FTS query and stale fallback;
- SSE-to-visible-state latency;
- interactive job start while background work runs;
- import/index rebuild effects;
- CPU, memory and SQLite size;
- 390/768/1366/1440 viewport overflow and input latency.

Report distributions and outliers; an approver sets acceptance thresholds later.

## 9. State machines

`Audit` means an append-only audit event. `DB` names the enforcing constraint/test.

### 9.1 Product and content states

| Area; current state | Trigger and guard | Persisted fields / atomic side effects | Next; terminal/recovery | Forbidden; UX/evidence; enforcement |
|---|---|---|---|---|
| Diagnostic `not-started` | Start with approved captured graph | Session/setup inputs; Audit | `in-progress` recoverable | No LearningState yet; integration test |
| Diagnostic `in-progress` | Answer, pause or skip; optional steps never required | Append answer or state timestamp | `in-progress/paused/skipped` | No lost answers; unique sequence |
| Diagnostic `paused/skipped` | Resume or preview | Preserve answers | `resumed/roadmap-preview` | No forced retake; restart test |
| Diagnostic `roadmap-preview` | Explicit Confirm; graph still approved | D11 atomic goal + states + preview overlay + session link | `confirmed` terminal | No partial goal; UoW rollback test |
| Diagnostic any | Service failure | Failure code/refs | `failed` retryable | Resume preserves work |
| Roadmap `loading` | Approved graph and goal read succeeds | None | `ready` | Unapproved graph forbidden by approval join |
| Roadmap `ready` | Save checkpoint/learner overlay | Append entry/correction; projection invalidation; Audit | `checkpoint-saved/ready` | No silent mutation; property test |
| Roadmap `ready` | Graph newer | Create/recompute diff annotation only | `stale-canonical-version` | Goal pin unchanged |
| Bridge `proposed` | Add/postpone/dismiss | Atomic overlay entry or decision; Audit | `accepted/postponed/dismissed` | No automatic add |
| Overlay `awaiting` | Accept with matching graph and cap/dedupe valid | Append overlay entry; close proposal | `accepted` | Stale → `rejected-stale`; transaction test |
| Canonical draft `authored/curated/AI-draft` | Validate | Validation result | `validation-failed/pending-approval` | No read visibility |
| Canonical `pending-approval` | Offline explicit editor approval | Whole version + approval last | `published` terminal immutable | No in-app publish; DB triggers and half-seed test |
| Canonical `published` | New version approved | Supersession reference only | `superseded` | In-place update/delete forbidden |
| Diff `proposed/awaiting` | Postpone/dismiss | Decision/audit | terminal decision; goal unchanged | No pin move |
| Diff `conflict-needs-resolution` | Resolve every item then explicit Accept | D9 pin + target overlays + invalidations | `accepted` terminal | Partial commit forbidden |
| Artifact absent/stale | Explicit Generate/Regenerate or key change | Single-flight job | `queued/generating` | No implicit evidence/profile rewrite |
| Artifact `generating` | Valid terminal output | Artifact + provenance + job result atomically | `ready` | Schema invalid → quarantine |
| Artifact `ready` | Snapshot mismatch | Derived stale flag | `stale` recoverable | Existing body remains visible with warning |
| Model/source `idle` | Prepare operation | Context refs/hash | `preparing` | No network yet |
| Model/source `preparing` | Disclosure absent/present | Disclosure ref | `waiting-for-disclosure/queued` | Enqueue without disclosure forbidden |
| Model/source `running` | Success/fail/cancel | Typed result or diagnostic | terminal/retryable as classified | No governed mutation from raw output |
| Import `selected` | Parse enqueue | Original/hash/job | `parsing` | Original immutable |
| Import `parsing` | Valid parse/fail/cancel | Statements atomically | `parsed-untrusted/failed/cancelled` | No truth/evidence |
| Import `learner-review` | Map/correct/verify/dismiss | Decision/history and hash invalidation | `applied/review` | Existing canonical topic only |
| Import `unmapped` | New graph adopted | Deduped reprocess job | review/unmapped | Never creates topic |

### 9.2 Learning/interview states

| Area; current state | Trigger/guard | Atomic effects | Next/recovery | Forbidden/enforcement |
|---|---|---|---|---|
| Practice `ready` | Open question | Run/draft | `answering` | No feedback |
| Practice `answering` | Request hint | Append requested hint turn | `answering` | Unrequested hint hidden |
| Practice `answering` | Submit nonblank | Append attempt/evidence candidate and evaluation job | `submitted/evaluating` | Submit cannot overwrite attempt |
| Practice `evaluating` | Valid result/failure | Assessment + dimensions + job result | `feedback-ready/failed` | Feedback only now |
| Practice `feedback-ready` | Repair/continue | New draft or adaptive turn | `answering/follow-up` | Earlier attempts immutable |
| Mock `ready` | Start | Run and first interactive job | `answering` | No Learn prerequisite |
| Mock `answering/follow-up` | Save & exit confirmation | Exact draft/status | `paused` recoverable | No terminal completion/evaluation |
| Mock `paused` | Resume | Status only | `answering` | Draft byte-for-byte unchanged |
| Mock `answering` | Submit turn | Append answer; generate next turn | `follow-up` | No hints/evaluative output |
| Mock nonterminal | Explicit Complete, run valid | Fix transcript; enqueue final evaluation | `completing` | Blank/incomplete completion rejected |
| Mock `completing` | Valid evaluation/failure | Consolidated assessment/job result | `completed/failed-recoverable` | Report unavailable before completed |
| Assessment `feedback-ready` | Dispute reason | Append dispute/re-eval job | `disputed/re-evaluating` | Original preserved |
| Assessment `re-evaluating` | Success/ambiguity/failure | Successor + prior excluded in one UoW | `feedback-ready/ambiguity-unresolved/failed` | Ambiguity no penalty |
| Notebook `empty/ready` | Save entry | Entry/audit | `saved/ready` | Auto/user label required |
| Review `ready/due` | Attempt | Attempt, feedback, next schedule | `completed/ready` | Reveal before response forbidden |
| Review `ready/due` | Dismiss/disable | Preference/item state | `dismissed/disabled` | No navigation/readiness penalty |
| Review generation | Failure | Failure code/job | `generation-failed` retryable | Roadmap remains available |

### 9.3 Operational states

| Area; current state | Trigger/guard | Atomic effects | Next/recovery | Forbidden/enforcement |
|---|---|---|---|---|
| Job `queued` | Lane claims with lease | Attempt/start state | `running` | Duplicate active dedupe key forbidden |
| Job `running` | Result commit | JobResult + terminal state/event | `succeeded` terminal | Result without terminal state forbidden |
| Job `running` | Failure | Error/retryable/diagnostic | `failed` | Retry depends on kind |
| Job `queued/running` | Cancel | Mark request or cancel immediately | `cancel-requested/cancelled` | Terminal state immutable |
| Job startup | Reconcile persisted state | Process cleanup/temp sweep/audit | queued stays; running→failed retryable; cancel-requested→cancelled | Crash/restart integration tests |
| Runner `pending-confirmation` | Valid explicit confirmation/toolchain | Runner/job/input refs | `queued` | Unconfirmed run rejected |
| Runner `queued` | Worker claim | Temp workspace/process record | `preparing/running` | No shell/undeclared input |
| Runner `running` | Complete/fail/limit/cancel | Output/result; then cleanup state | `completed/failed/timed-out-or-limited/cancelled` | Static/runtime labels enforced |
| Runner terminal | Cleanup | Cleanup outcome/audit | `cleanup-complete/cleanup-failed` | Janitor and threat-model tests |
| Search `empty/ready` | Query | Result set | `results/empty` | Owner filtering mandatory |
| Search any | Source watermark advances | Mark state/enqueue | `stale-index/rebuilding` | Cannot label stale as current |
| Search `rebuilding` | Success/failure | Switch projection or preserve old | `ready/failed` | Partial projection not activated |
| Settings valid | Save with current row version | New settings/audit | `saved` | Invalid → `invalid-setting` |
| SSE `connected` | Transport loss | Client state | `reconnecting` | UI must not imply jobs stopped |
| SSE `reconnecting` | Reconnect/replay | Deduped events then GET reconciliation | `connected` | Replay alone not authoritative |
| SSE any | Reconnect unavailable | Error/status | `unavailable` | Refresh/GET fallback required |
| Export requested | Confirm scope | Export job | `running` | No fabricated missing data |
| Export `running` | Result/failure | Result ref/diagnostic | `complete/failed` | Version field required |
| Delete idle | Preflight | Immutable impact snapshot | `delete-confirmation` | No deletion yet |
| Delete confirmation | Confirm unchanged snapshot | Delete job | `running` | Changed impact requires new preflight |
| Delete running | Success/failure | Tombstones/downgrades/audit atomically | `complete/failed` | No partial cross-goal downgrade |

## 10. Verification and complete traceability

### 10.1 Test layers

- Domain unit/property tests: graph ordering, overlay mutation protection, transfer, derived state with explicit time, review penalty exclusions, cache keys, merge selection and import hashes.
- SQLite repository/integration tests: ownership, composite FKs, immutable triggers, atomic UoWs, FTS projections.
- OpenAPI compatibility: generated client committed/checked against server schema.
- Alembic upgrade fixtures and recoverable failure.
- Provider fake adapters: argv/stdin/env, heartbeat/timeouts, cancellation, schema quarantine and contract regression.
- Job crash/restart/retry/cancel/dedupe/lane/starvation and terminal-result atomicity.
- SSE reconnect, duplicate events, missed replay and GET reconciliation.
- Runner threat model: no shell, declared inputs, environment, missing toolchain, timeout/limit/cancel/process cleanup, static/runtime wording.
- Playwright: all routes and viewports, interaction timing, focused Mock, approval boundaries, accessibility, focus restoration and reduced motion.
- Manual: curriculum/source/editorial/rubric review, screen reader, threat-model review, privacy/export/delete inspection and representative performance record.

### 10.2 Must requirement traceability

Status codes: `S` = specified; `G#` = approval gate listed in §12.3.

| ID | Phase / owner | Data/invariant | Contract; lifecycle; route | Acceptance and test | Status |
|---|---|---|---|---|---|
| CORE-01 | P1 App shell | Goal path enum; no third path | Route nav; independent hub/roadmap entry | Playwright nav/IA manual | S |
| CORE-02 | P1 Goals/content | Audience/level tags; no beginner graph | Onboarding/catalog; setup→preview | Label/catalog fixture review | S; G1/G4 |
| CORE-03 | P1 Goals | Profile 1:N goals; goal-scoped FKs | Goals CRUD/export/delete; `/` | Two-goal isolation journey/repository tests | S |
| CORE-04 | P1–2 Evidence | transfer refs, no completion, D5 | Goal preview/corrections; onboarding/evidence | Transfer/delete/tombstone property + PW | S |
| CORE-05 | P1 Roadmap | full projection; overlay history | Roadmap mutation commands; preview/ready | No-silent-mutation/reload PW | S |
| ONB-01 | P1 Diagnostics | persisted setup fields | Diagnostic create/PATCH/confirm; onboarding | Editable choices and atomic-confirm test | S; G4 |
| ONB-02 | P1 Diagnostics/imports | answers; original untrusted import | Answers/import endpoints; optional transitions | Adaptive fixture/skip/restart/import test | S; G9 |
| ONB-03 | P1 Roadmap | captured graph + preview overlay | Preview/confirm; roadmap-preview | Full preview/correction/rollback PW | S |
| LRN-01 | P1–2 Roadmap | projection always addressable | Roadmap GET; topic→roadmap | Context-preserving journey | S |
| LRN-02 | P2 Content | layers/conversation/notebook refs | Topic layer/content APIs; topic route | Self-contained topic PW/content review | S; G1/G3 |
| LRN-03 | P2 Learning | capability/evidence target required | Recommendation/checkpoint contract | Fixture/schema validation | S; G9 |
| LRN-04 | P2 Roadmap | proposals only; D2/D3 | Proposal decisions; stale annotations | Mutation-protection/property/PW | S |
| DEP-01 | P1–2 Roadmap | recommendation separate from override | Depth command/projection | Refresh and visual distinction PW | S |
| DEP-02 | P2 Content | checkpoint range + evidence criterion | Topic/checkpoint response | Content fixture validation | S |
| DEP-03 | P2 Content QA | independently accurate layer versions | Content publication validation | Editorial reversal-regression review | S; G2/G3 |
| GAP-01 | P2 Roadmap | bridge proposal/reason/relation/place | Bridge proposal; ready→proposed | Gap fixture/PW | S |
| GAP-02 | P2 Roadmap | append-only decision | Bridge decision; accept/postpone/dismiss | No-auto-add/audit tests | S |
| INT-01 | P3 Interview | independent submode state | Hub query submodes; `/app/interview-hub` | Direct-entry PW without Learn | S |
| INT-02 | P3 Interview | editable/copy bundle | Bundle CRUD/copy; hub | Copy/edit/no-company fixture | S; G4 |
| INT-03 | P3 Interview | optional bundle items | Bundle PATCH; hub | Add/remove behavioral/leadership PW | S |
| REF-01 | P3 Content/interview | refresher artifact/source/gap refs | Refreshers API; hub refresher | Source-linked refresher test | S; G3 |
| QPR-01 | P3 Interview | immutable attempts/turns | Answer/hint/complete; Practice states | Timing/retry/adaptive PW + fake provider | S; G9 |
| QPR-02 | P3 Evaluation | facts/trade-offs fields | Evaluation result; feedback-ready | UI/schema separation test | S |
| QMK-01 | P3 Interview | Mock turn constraints | Answers/pause/resume; focused Mock | No-hint/interim-feedback/adaptive PW | S |
| QMK-02 | P3 Evaluation | final assessment visible after terminal | Complete/report; completing→completed | Mock feedback-timing/fixture-gate tests | S; G9 |
| IMP-01 | P2 Imports | original immutable/untrusted | Import/parse; Imports | No truth/evidence/completion integration | S |
| IMP-02 | P2 Imports | decisions, dedupe, mapping | Statement map/verify/dismiss | Flag/dedupe/correction/reprocess tests | S |
| NBK-01 | P2 Notebook | goal scope; auto/user label | Notebook CRUD; Topic tools | Link/label/isolation tests | S |
| RET-01 | P2 Review | queue/settings/items | Reviews APIs; ready/due/dismissed | Nonblocking queue PW/domain | S; scheduling rule gate |
| RET-02 | P2 Review | per-goal preferences; no penalty | Preferences PATCH; Settings | Disable/dismiss derived-state test | S |
| RET-03 | P2 Review | immutable attempt/schedule | Attempt endpoint; due→completed | Recall-before-reveal/confidence test | S; scheduling rule gate |
| PRG-01 | P2 Progress | four dimensions + explanations | Progress GET; Evidence/Reports/Settings | Detailed/simple no-data-loss test | S; derived-rule approval |
| PRG-02 | P1–2 Progress | four allowed states; correction | Correction and state APIs | No inferred-completion/property/PW | S |
| EVAL-01 | P2 Evaluation | rubric dimensions/assumptions | Assessment contract; feedback/report | Valid-alternative curated fixtures | S; G9 |
| EVAL-02 | P2 Evaluation | disputes/successors/exclusion | Dispute/re-evaluate; ambiguity states | Append-only/no-penalty tests | S |
| HND-01 | P4 Hands-on | linked work/artifact/review/revision/evidence | Work/review/run/submit workflow | End-to-end linked-stage integration | S; G9 |
| HND-02 | P4 Runner/eval | static mode requires limitation | Runner/review result; Topic/Evidence | Static/runtime claim separation tests | S |
| HND-03 | P4 Content QA | role/scenario metadata | Scenario contract | Mid/senior/staff manual fixture review | S; G4/G9 |
| RUN-01 | P4 Runner | Java capability; gated Python/DB | Capabilities/run API | Java plus missing/configured tool tests | S; G5/G8 |
| RUN-02 | P4 Runner | confirmation/input/argv/process/cleanup | Runner lifecycle; Topic/Jobs | Threat-model/cancel/cleanup tests | S; G5/G7/G10 |
| RUN-03 | P4 Runner | limits-policy version; not-sandbox label | Limited terminal result | Limit/wording/manual security review | S; G7/G10 |
| CNT-01 | P1 Canonical | stable versioned graph/DAG | Approved graph reads/publication | Graph validation/property tests | S; G1 |
| CNT-02 | P1–2 Roadmap | overlay separate canonical | Overlay APIs; roadmap/update | Canonical immutability/audit tests | S |
| CNT-03 | P2/P4 Content | D3 artifact/provenance | Generate/regenerate; Topic | Exact key/staleness/single-flight tests | S; G3/G6 |
| CNT-04 | P2/P4 Provenance | claim-level citations/status | Claims/provenance APIs; Sources layer | Source/claim editorial fixtures | S; G3 |
| CUR-01 | P1 Canonical | scope tags/boundary | Catalog/graph reads | Graph-scope validation/manual review | S; G1 |
| CUR-02 | P1 Canonical | DSA scenario relation; Go absent | Graph validation | DSA relation/Go absence tests | S |
| CUR-03 | P4 Canonical | approval-last/immutable D1 | Offline publisher only | Half-seed/approval/trigger/two-role tests | S; G2 |
| CUR-04 | P4 Roadmap | base→latest diff, atomic D9 | Diff/accept; canonical-updates | Two-version merge/rollback/PW | S |
| SET-01 | P1–4 Settings | profile/settings/disclosures/export/delete | Settings/data APIs; Settings | Persistence/effect/export/delete journeys | S; G10/G11 |
| SET-02 | P5 Frontend | semantic components/preferences | All essential routes | Axe, keyboard, screen reader, focus/reduced-motion | S; hardening |
| AI-01 | P4 Provider/domain | contract versions/quarantine | Generation/evaluation jobs | Invalid schema/no-mutation regression | S |
| AI-02 | P4 Provider | provider choice/config status | Capabilities/generate | Codex/Claude fake adapters/unavailable state | S; G6 |
| DAT-01 | P1 Persistence | owner on all local records | Server-resolved local owner | Cross-owner negative repository tests | S |
| DAT-02 | P4 Jobs | durable states/two lanes/D4/D8 | Jobs/retry/cancel; Jobs | Crash/restart/lane/nonblocking tests | S; G10 for cap/retention |
| PRV-01 | P1/P4 Privacy | versioned disclosure acceptance | Disclosure gate; Settings/async actions | Decline/accept/pre-enqueue tests | S; G3/G6 |
| PRV-02 | P4 Privacy | context refs/redaction policy | Provider request/diagnostics | Inclusion/redaction inspection tests | S; G11 |
| SYS-01 | P1 Architecture | module/port boundaries | OpenAPI client/application ports | Import-boundary and fake-port tests | S |
| SYS-02 | P1/P4 Search | FTS5 projection/ownership | Search/rebuild; Search | FTS/index/stale/filter tests | S |
| SYS-03 | P4 Jobs/frontend | persisted events/result ref | SSE/GET; Jobs and async routes | Reconnect/duplicate/missed-replay tests | S; replay G10 |

### 10.3 NFR traceability

| ID | Phase / owner | Data/invariant | Contract/lifecycle/UX | Evidence/test | Status |
|---|---|---|---|---|---|
| NFR-01 | P5 Frontend | semantic state/focus preferences | Essential route keyboard/AT states | Axe + keyboard + manual screen reader | S |
| NFR-02 | P4–5 Jobs | D4 terminal/result atomicity | Restart reconciliation/GET | Crash/restart integration | S |
| NFR-03 | P1–5 Domain/audit | immutable approvals/evidence/decisions | All governed transitions | Missing/unauthorized transition tests | S |
| NFR-04 | P1–5 Privacy | disclosures/export/delete status | Settings and data lifecycle | API/PW/privacy review | S; G11 |
| NFR-05 | P4–5 Provider/runner | fail-closed policy/quarantine | Schema/policy failure states | Negative no-run/no-mutation tests | S |
| NFR-06 | P4–5 Observability | safe correlations/redaction | Failure→diagnostic UI | Structured-log/redaction tests | S; G11 |
| NFR-07 | P1–5 Architecture | domain ports/OpenAPI isolation | Fake adapters/generated client | Contract/import-boundary tests | S |
| NFR-08 | P4–5 Performance | benchmark metadata/results | Async navigation/search | Representative recordings, no threshold | S; threshold approval |
| NFR-09 | P2–5 Testability | deterministic rule/contract versions | No live model in domain tests | Unit/property/curated regression suites | S |
| NFR-10 | P4–5 Portability | capability detection/support metadata | Supported/missing/incompatible states | OS/toolchain matrix tests | S; G5/G6 |
| NFR-11 | P1–5 Compatibility | versioned DB/manifests/overlays/artifacts/jobs | Migration/rebuild/recovery | Alembic representative upgrades | S; G11 |

### 10.4 Later traceability

| Requirement | Post-MVP treatment |
|---|---|
| RUN-04 | Runner port may add Go only after separate runtime/toolchain/threat-model approval. |
| AI-03 | OpenRouter/DeepSeek may implement the existing provider port; no MVP contract depends on them. |
| SAAS-01 | Hosted authorization must separate ordinary learner suggestions from editorial publication. |
| SAAS-02 | Postgres, object storage, managed queues, API models, remote isolation and hosted identity replace ports without changing domain contracts. |
| Other candidates | Scheduling, voice and company-specific preparation require separately approved scope. Payments, teams, social, gamification and mobile are not assumed future commitments. |

## 11. Delivery sequence

| Phase | Entry criteria | Deliverables/migrations/APIs/routes | Fixtures/tests/manual review | Exit and recovery gate |
|---|---|---|---|---|
| 1. MVP foundation | Curriculum/role decisions sufficient to seed reviewed v1; schema conventions approved | Owner/roles, profile/goals, canonical graph, D1 publisher skeleton, D11 diagnostics, overlays/projection, disclosures, OpenAPI client; activate `/`, onboarding, roadmap, settings shell, not-found; initial Alembic schema | Approved/unapproved graph, paused diagnostic, two goals; repository/property/OpenAPI/router/PW tests | Approved graph visible only with approval; atomic goal confirmation; no silent mutation; recoverable migration/startup. G1/G2/G4 cannot remain unresolved for exit. |
| 2. MVP learning and evidence | P1 graph/goal/UoW stable; source and assessment review process available | Topic layers, generation contract/cache, imports, evidence, rubrics/disputes, derived progress, notebook/review; activate Topic, Evidence and learning portions of Reports/Search; migrations for all records | Cache/import/transfer/tombstone/time-state/valid-alternative fixtures; unit/integration/PW/content review | Complete learning flow with qualified evidence, no inferred completion, no review penalty. G3/G9 and derived-state rules approved. |
| 3. MVP interview | Bundle taxonomy/scenarios approved; evidence/eval service stable | Independent Refresher/Questions submodes, editable bundles, Practice and focused Mock, terminal Reports; interview migrations/APIs | Practice/Mock timing, safe exit exact draft, adaptive turn, transcript-only arbitrary-input fixtures; PW/manual UX | No Learn gate; no active Mock feedback; consolidated terminal result only. G4/G9 approved. |
| 4. MVP AI and hands-on | Provider/runner/source operational decisions approved; jobs schema proven | D7 adapters, source retrieval, D4/D8 worker, SSE, D1 v2 publish, D9 merge, Java runner, FTS rebuild and operational Jobs; provider/job/runner migrations | Fake adapters, schema quarantine, v1→v2 merge, crash/retry/cancel, SSE reconnect, runner threat cases, disclosure/redaction | Restart-safe jobs, atomic results/merge, truthful static/runtime labels, Java capability demonstrated. G3/G5/G6/G7/G8/G10 required. |
| 5. MVP-hardening | All MVP Must journeys function and no unresolved safety defect | Upgrade/recovery fixtures, accessibility, privacy/log review, performance recordings, content/rubric review, cleanup/janitor validation | Full pytest/Vitest/RTL/Playwright, screen reader, threat model, migration matrix, representative benchmark report | No critical omission in Must/NFR matrix; recoverable failures demonstrated. G10/G11 settled enough for release. |
| Post-MVP | Separate PRD/approval | Only Later ledger items | Separate acceptance | No implicit continuation from MVP. |

## 12. Risks and approval gates

### 12.1 Risk and decision-gate table

| Risk | Evidence/indicator | Mitigation | Contingency | Owner / stop point |
|---|---|---|---|---|
| Wrong or overconfident AI output | Disputes, invalid schemas, unsupported claims | Validation, quarantine, provenance, rubric/source review | Disable affected generation/evaluation; retain authored content | Product/content TBD; stop before P2/P4 exit |
| Silent learner-plan mutation | Projection/audit mismatch | D2 proposals only, immutable overlay history, property tests | Disable automation; manual controls remain | Engineering; stop immediately |
| Unapproved/partial canonical publication | Readable half-seed or missing approval | Approval-last UoW, read joins, immutable triggers | Roll back/re-publish new version | Editorial/engineering; stop before P1 exit |
| Bad canonical merge | Pin moved without all resolutions | D9 transaction, base→latest recomputation | Roll back; preserve base pin | Engineering; stop P4 |
| Overconfident evidence transfer | Transfer classified as mastery | Read-only refs/corrections/tombstone tests | Downgrade to unverified and audit | Product; stop P2 |
| Source/license misuse | Unknown license/snapshot right | Approved source registry/status | Withdraw source/artifact; preserve provenance label | Content/legal TBD; stop content release |
| Provider CLI incompatibility/auth loop | No first output/repeated retry | Heartbeat classification/version matrix | Mark unavailable; curated/static flow | Engineering; stop P4 provider activation |
| Job loss/duplicate spend | Restart ambiguity or duplicate result | Durable dedupe, terminal atomicity, reconciliation | Quarantine conflict; manual retry | Engineering; stop P4 |
| Runner harms host/misleads learner | Orphan, limit/cleanup failure, unsupported claim | Disabled-by-policy option, explicit confirmation, argv, limits, labels | Disable runner; retain static workflow | Eng/security TBD; stop before activation |
| PID reuse during reconciliation | Recorded PID no longer same process | Persist/verify spawn identity before signal | Do not kill; cleanup-failed/manual recovery | Eng/security; stop reconciliation release |
| Storage exhaustion | Unbounded imports/output/jobs | Approved configurable caps and visible failures | Disable new enqueue/export cleanup advice | Product/engineering TBD; stop P4 |
| Deletion damages transferred state | Unshown cross-goal references | Immutable impact snapshot, D5 atomic transaction | Rollback/failure; no partial state | Product/privacy; stop Settings delete |
| FTS stale/incorrect scope | Results leak another goal or old graph | Ownership join, projection version, fallback | Mark unavailable; deterministic fallback | Engineering |
| Accessibility regresses in async states | Keyboard/screen-reader cannot recover | Component primitives, focus/status tests | Block hardening exit | Frontend/a11y owner TBD |
| Invented readiness/performance claim | UI/acceptance uses unapproved threshold | Versioned definitions; recorded measurements only | Remove claim/threshold | Product; stop release |
| External telemetry privacy risk | Outbound events without consent | Local-only default | Keep external telemetry disabled | Product/privacy; G12 |

### 12.2 Recommended defaults requiring approval

These are bounded recommendations, not adopted decisions:

1. Keep the runner disabled until a first-run risk acknowledgement, then require confirmation for every fresh run.
2. Limit the MVP database exercise connector to a learner-supplied configured database; do not manage a database instance.
3. Ship no external telemetry in MVP; retain local guardrail events only.
4. Use a versioned JSON manifest plus referenced UTF-8 payload files for export, pending data-lifecycle approval.
5. Treat a withdrawn source as unavailable for new generation while retaining its provenance/status in existing artifacts; exact snapshot and replacement rules still require source-policy approval.

### 12.3 Blocking approval questions, prioritized

1. **Curriculum spine:** Which Java/Spring Boot/AWS topics and representative connected System Design/RDB topics constitute reviewed MVP? Which DSA relations are scenario-relevant?
2. **Editorial policy:** What evidence and review criteria must accompany an approval by the MVP designated editorial role?
3. **Source policy:** Which sources and licenses are approved, and what snapshot, cache, withdrawal and replacement rules apply?
4. **Role taxonomy:** What learner-facing mid/senior/staff competency descriptions acknowledge company-title variation?
5. **Supported platform matrix:** Which OS, Java/Python versions, JDK/build tools and unsupported configurations are documented?
6. **Provider operations:** Which Codex and Claude CLI versions are supported, and how are installation and authentication discovered safely?
7. **Runner posture:** Disabled-until-enabled or first-run acknowledgement? What resource/output/temp limits and cleanup posture are approved?
8. **Database exercises:** User-supplied connection only or product-managed local instance?
9. **Assessment design:** Which representative initial/delayed and Practice/Mock scenarios, rubric versions and role-level breadth are approved? This also gates the deterministic derived-state rules.
10. **Size and retention:** Limits for imports, artifacts, transcripts, generated content, job/event history, runner output and temporary files; diagnostic/session expiry.
11. **Data lifecycle:** Exact export package/version, transcript inclusion, delete recovery, backups, logs, redaction, retention and support-access posture.
12. **Telemetry:** Whether any external telemetry is allowed later, with what consent, disclosure, minimization and deletion rules.

Implementation must stop at the relevant phase exit rather than silently selecting an answer.

## 13. Final completeness audit

- All 60 PRD `Must` requirements and NFR-01 through NFR-11 are individually traced.
- Appendix H D1–D11 is preserved.
- All 14 approved routes are covered; `/app/$pageId` validation and not-found behavior remain.
- Exactly two learning paths remain: Learn and Interview Prep. My learning and operational tools are not additional paths.
- Refresher and Questions remain independently reachable within Interview Prep without adding canonical routes.
- The selected navigation hierarchy, responsive model, terminology, control placement, approval boundaries, limitation labels, disclosures and focused Mock experience are preserved.
- Resume and Recommended next remain separate.
- Evidence, not viewing or Run, establishes qualified progress.
- localStorage, deterministic feedback, fixture evaluation, bundled search, simulated jobs and missing backend behavior were not promoted into production architecture.
- MVP, MVP-hardening, Later/Post-MVP, TBD and unsupported work remain distinct.
- No source license, numerical limit, OS matrix, provider command/version, performance threshold, retention guarantee, sandbox property, recovery guarantee, readiness claim or interview/job outcome guarantee was invented.
- The specification was written to this Markdown file only; no application or PRD file was modified.
- Nothing was installed, migrated, published, executed through a runner or deployed.

