# PRD — Backend Engineer Learning & Interview Prep

**Version:** 0.2 Draft — architecture decisions D1–D11 resolved after adversarial review (Appendix H)  
**Date:** 2026-08-09  
**Status:** Draft — owner and approvers TBD

## 1. Executive brief and decision register

Build a localhost-first web application for existing mid-, senior-, and staff-level backend engineers who want to develop or refresh practical Java/Spring Boot microservices and AWS capability, and prepare for generic product-company backend interviews. The product has exactly two paths—**Learn** and **Interview Prep**. Subjects sit beneath either path and can reuse learner context and qualified evidence.

The outcome is defensible capability: a learner can implement, diagnose, justify, and retain decisions in representative scenarios. Completion alone is not success.

| Decision | Status | Rationale |
| --- | --- | --- |
| Initial curriculum spine | MVP | Java/Spring Boot microservices plus AWS; System Design and RDB cover representative connected topics only. |
| Product shape | Must | Localhost-first modular monolith, designed with future hosted multi-user seams. |
| Learning model | Must | Visible roadmap, problem-first adaptive checklist, evidence-led recommendations. |
| Content governance | Must/MVP | Versioned canonical graph; AI drafts require designated editorial approval before canonical publication. |
| Model integration | MVP | Local Codex 5.6 Terra/high default, Claude alternative, provider adapter and validated contracts. |
| Hands-on boundary | Must | Controlled local subprocesses for Java compile/test first; never assert production, sandbox, or AWS proof. |
| Out of MVP | Locked | Auth, sync, tenancy, billing, teams, voice, real AWS, payments, mobile, gamification, company-specific prep, beginner curricula. |
| Architecture decisions | Resolved v0.2 | Eleven cross-cutting decisions (publication posture, roadmap projection, content cache, job recovery, evidence transfer, derived state, provider transport, worker lanes, merge atomicity, import mapping, diagnostic persistence) adversarially reviewed and recorded in Appendix H; where earlier prose conflicts, Appendix H governs. |

## 2. Problem, principles, scope, and non-goals

Experienced engineers often have uneven, stale, or context-poor knowledge. Generic courses hide the roadmap, rigidly prescribe a sequence, overstate completion, and turn interview preparation into memorized answers. This product provides a correction-friendly plan whose depth is proportional to the learner’s goal and whose evidence is inspectable.

### Product principles

- **Capability over completion.** Record evidence for capability rather than declaring mastery from consumption.
- **Learner agency.** Recommendations never silently change a learner’s roadmap, depth, ordering, or inferred knowledge.
- **Roadmap first.** The whole roadmap remains visible; a topic view is layered and self-contained.
- **Claim-appropriate authority.** Use authoritative sources appropriate to each factual, standards, trade-off, or industry claim; citations are traceability, not an authority badge.
- **Calibrated automation.** AI can draft and personalize; canonical publication and personal-plan changes remain explicit human decisions.
- **Safe, honest execution.** Static review does not claim runtime behavior, and local execution is neither a security sandbox nor production validation.

### Scope

MVP serves a single local owner. Learn supports the bounded curriculum; Interview Prep provides independently reachable Refresher and Questions modes. The application persists local services and data, may use disclosed network access for configured model providers and authoritative source retrieval, and does not support a strict offline mode.

### Non-goals

- Teaching absolute beginners or providing a comprehensive Java, AWS, System Design, RDB, or DSA curriculum.
- Company-specific interviewing, recruiting workflow, voice coaching, scheduling, social features, teams, payments, mobile applications, or gamification.
- Real AWS provisioning or claims that an artifact was tested in AWS/production.
- User authentication, cloud sync, multi-tenancy, billing, or remote code execution in MVP.

## 3. Users, jobs, glossary, and information architecture

### Users and jobs

| User | Assumed baseline | Primary job | Evidence of success | Primary risk |
| --- | --- | --- | --- | --- |
| Mid-level backend engineer | Has shipped backend code but has uneven production exposure. | Close implementation and diagnostic gaps while learning the Java/AWS ecosystem. | Implements a bounded service change, diagnoses a supplied failure, and explains the choice. | Mistaking framework familiarity for production competence. |
| Senior backend engineer | Has production ownership in at least one stack. | Refresh breadth and defend trade-offs under interview pressure. | Handles role-level scenarios, follow-up questions, and revisions with consistent reasoning. | Memorizing answers without transferring them to new constraints. |
| Staff-level backend engineer | Routinely evaluates architecture across teams or systems. | Validate architecture, diagnosis, and leadership-adjacent reasoning without being forced through basics. | Compares alternatives, identifies second-order failure modes, and defends decisions under challenge. | Being given shallow examples or a rigid beginner sequence. |

### Glossary

- **Canonical graph:** versioned editorial curriculum with stable IDs, relationships, prerequisites, level, and version.
- **Personal overlay:** user-specific proposed or approved plan changes layered over canonical content.
- **Evidence:** observable learner artifact, response, rubric result, self-correction, or assessment outcome—not a completion flag.
- **Capability ladder:** `know`, `understand`, `choose`, `implement`, `diagnose`, `defend`.
- **Goal workspace:** a learner-owned objective with its own roadmap, evidence, notebook, and progress view.
- **Bridge:** a small prerequisite or context insertion recommended at a detected gap.
- **Readiness:** a qualified, explainable view of current evidence; never a guarantee of interview or job outcome.

### Information architecture

1. Home / goal workspaces
2. Learn
   - Test yourself: optional adaptive diagnostic
   - roadmap
   - topic workspace: context, tutor conversation, notebook, review, progress
3. Interview Prep
   - Refresher
   - Questions
   - Practice
   - Mock
4. Evidence, review queue, and notebook
5. Settings: profile, imports, providers/network, accessibility, progress detail, data export/delete

## 4. Bounded curriculum and learning model

The canonical MVP spine is Java/Spring Boot microservices plus AWS. It may link to representative System Design and relational database topics where they help explain or evaluate the spine; neither area is promised as comprehensive. DSA appears only when directly relevant to a selected scenario. Go plus AWS is Later.

Each topic carries an intended capability target, prerequisite relationships, source provenance, recommended layer depth, and checkpoint candidates. Available layers are:

| Layer | Purpose |
| --- | --- |
| Essential | Mental model and minimum terminology. |
| Implementation | Practical construction choices and artifacts. |
| Internals | Relevant mechanics and constraints. |
| Production | Operational behavior, observability, resilience, and cost context. |
| Alternatives | Reasoned competing approaches. |
| Failures | Common failure modes, diagnosis, and recovery. |
| Interview | Explanation, trade-off, and defense framing. |
| Sources | Provenance, citations, and source notes. |

Learning is a problem-first adaptive checklist, not a fixed course. The app recommends the next useful topic, layer, bridge, retrieval, or assessment based on evidence and learner choices. Checkpoints should generally fit a 30–60 minute session; a learner can jump, skip, reorder, change depth, or correct inferences at any time.

## 5. Core journeys and recovery

### Goal onboarding

1. The learner chooses Learn or Interview Prep, then selects a subject or target role and level.
2. The application reuses the global learner profile and shows the relevant experience, strengths, weaknesses, and evidence for confirmation or correction.
3. Learn onboarding optionally accepts Markdown/plain-text notes; Interview Prep onboarding optionally accepts Markdown/plain-text questions.
4. The learner may skip or take an adaptive diagnostic whose next questions change with their responses and confidence.
5. The application generates and shows the whole roadmap with inferred knowledge states, depth recommendations, sources, and imported coverage.
6. Before creating the goal, the learner may jump through the preview, skip or reorder topics, override depth, and correct inferences.
7. Creating a later goal reuses durable profile data and proposes conservative evidence transfer without transferring completion.

### Learn journey

1. Learner creates or selects a goal workspace and sees the entire roadmap.
2. They select a topic or recommended problem, review the required context, then work through chosen layers.
3. They produce evidence through a response, decision, artifact, code, design, or review.
4. The app returns visible rubric-based feedback, suggests a bridge or next action, and queues optional retention work.
5. Learner accepts, postpones, dismisses, or edits recommendations; the overlay and evidence history explain what changed.

### Interview Prep journey

1. Learner opens Refresher or Questions directly, with no Learn-path prerequisite.
2. They select role/level context, a bundle, subject, or question.
3. In Practice, they may request hints and receive immediate feedback plus adaptive follow-ups. In Mock, the interviewer still asks adaptive follow-up questions one at a time, but gives no hints or evaluative feedback during the run.
4. The app presents rubric, assumptions, cited factual corrections/trade-offs, and next steps. Mock feedback is consolidated at the end.

### Recovery behaviors

If an inference is wrong, the learner marks it likely known, partial, unverified, or new and may correct it. If a prerequisite is absent, the app offers an inline bridge and a placement recommendation; the learner may add, postpone, or dismiss it. Failed model, source, runner, import, or job states remain visible with retry/cancel where safe and without inventing results.

## 6. Functional requirements

Strength uses **Must**, **Should**, or **Later**. MVP items form a coherent release. A Should item is removable without breaking the core flow, safety, or a Must acceptance condition. Later has no MVP dependency.

| ID | Area | Requirement | Strength | Delivery | Acceptance |
| --- | --- | --- | --- | --- | --- |
| CORE-01 | Product | Provide exactly Learn and Interview Prep as top-level learning paths; retain separate subjects. | Must | MVP | Navigation exposes both paths and no third path; each can be entered independently. |
| CORE-02 | Audience | Position the product for existing mid/senior/staff backend engineers and exclude absolute-beginner curricula. | Must | MVP | Onboarding and catalog labels state intended audience; no beginner track is offered. |
| CORE-03 | Goals | Support one global learner profile and multiple independent goal workspaces. | Must | MVP | A learner can create, switch, resume, export, and delete more than one goal without mixing goal-specific progress. |
| CORE-04 | Transfer | Reuse durable profile context and propose conservative evidence transfer across goals without transferring completion. | Must | MVP | A new goal shows likely-known, partial, unverified, and new classifications with evidence and correction controls. |
| CORE-05 | Roadmap control | Keep the whole roadmap visible and allow jump, skip, and reorder actions. | Must | MVP | These controls remain available before and after goal creation; no action is silently reversed by adaptation. |
| ONB-01 | Onboarding | Collect minimal progressive setup: path, subject or role+level, reused experience, explicit job-level competency target, and goal name. | Must | MVP | Learner can complete or edit each choice before roadmap confirmation. |
| ONB-02 | Onboarding | Offer optional Markdown/plain-text notes for Learn, questions for Interview Prep, and an optional adaptive diagnostic. | Must | MVP | Every option can be skipped; diagnostic questions adapt to responses/confidence; imported claims remain untrusted until verified. |
| ONB-03 | Onboarding | Show full roadmap preview before creating a goal workspace. | Must | MVP | Preview includes topics, inferred states, and recommended depth; learner can correct before saving. |
| LRN-01 | Learning | Show the whole roadmap continuously available from the Learn workspace. | Must | MVP | Learner can return to roadmap from any topic without losing context. |
| LRN-02 | Learning | Provide self-contained topic pages with stable layered content, context tutor, topic-attached conversation, notebook, review, and progress. | Must | MVP | A topic can be understood and worked without hidden prerequisite navigation; conversation is linked to that topic. |
| LRN-03 | Learning | Use problem-first checklist recommendations and the capability ladder. | Must | MVP | Each assigned action names target capability and expected evidence. |
| LRN-04 | Adaptation | Restrict adaptation to recommendations, emphasis, examples, exercises, bridges, and proposed ordering. | Must | MVP | Automated operations cannot hide topics or mutate roadmap/overlay state without explicit learner approval; adaptive emphasis/examples/exercises flow through the recommendation and review channels, never by silently rewriting cached lesson artifacts (Appendix H, D3). |
| DEP-01 | Depth | Recommend depth by goal and evidence, while allowing per-topic layer/depth override. | Must | MVP | User override remains after refresh and is shown separately from recommendation. |
| DEP-02 | Depth | Use 30–60 minute checkpoint candidates without treating time as completion proof. | Must | MVP | Checkpoints state estimated session range and evidence criterion. |
| DEP-03 | Progressive disclosure | Keep every revealed layer accurate on its own and expose material qualifications without teaching a convenient half-truth. | Must | MVP | Content fixtures reject explanations whose later layer reverses rather than refines the learner's mental model. |
| GAP-01 | Gaps | Detect or allow declaration of a prerequisite/context gap and show an inline bridge. | Must | MVP | Bridge includes why, relationship, and proposed placement. |
| GAP-02 | Gaps | Let learner add, postpone, or dismiss a bridge; preserve the choice. | Must | MVP | No bridge is added silently; history records decision and reason if supplied. |
| INT-01 | Interview | Make Refresher and Questions independently accessible under Interview Prep. | Must | MVP | Learner reaches either with no Learn completion requirement. |
| INT-02 | Interview | Support generic product-company role/level context and editable recommended bundles. | Must | MVP | Bundles can be copied/edited; MVP contains no company-specific claims. |
| INT-03 | Interview | Offer behavioral and leadership as optional interview subjects. | Must | MVP | Either subject can be added or removed from a recommended bundle without changing technical subject scope. |
| REF-01 | Refresher | Provide targeted concise refreshers linked to subjects, layers, sources, and evidence gaps. | Must | MVP | Refresher can open from an interview subject and link back to cited source context. |
| QPR-01 | Practice | Provide text Practice with optional hints, rubric feedback, retry, and adaptive follow-up questions. | Must | MVP | Feedback identifies rubric dimensions and learner can retry without losing prior attempt. |
| QPR-02 | Practice | Classify answer feedback into facts and trade-offs where relevant. | Must | MVP | UI distinguishes factual correction from valid alternative reasoning. |
| QMK-01 | Mock | Provide text Mock with adaptive interviewer follow-up questions but no hints or evaluative feedback during a run. | Must | MVP | Questions are asked one at a time and adapt to prior answers; hint and feedback controls remain unavailable until completion. |
| QMK-02 | Mock | Provide consolidated rubric feedback only after Mock completion. | Must | MVP | End report includes assumptions, evidence, open ambiguities, and suggested practice. |
| IMP-01 | Imports | Import Markdown/plain-text Learn notes or Interview questions from onboarding and goal Settings as untrusted seed coverage. | Must | MVP | Parsed statements retain original text/provenance and are never converted directly to canonical truth, evidence, or completion. |
| IMP-02 | Imports | Verify, map, deduplicate, and let the learner correct imported material. | Must | MVP | The review visibly flags wrong, outdated, inapplicable, duplicate, incomplete, or uncertain items; original input remains inspectable. |
| NBK-01 | Notebook | Maintain one notebook per goal workspace with auto-collected and user-curated entries. | Must | MVP | Every entry is labeled auto or user and may link topic/evidence/source. |
| RET-01 | Review | Offer a configurable, optional review queue supporting retrieval, spacing, interleaving, and context variation. | Must | MVP | Learner can configure or dismiss reviews; queue never blocks roadmap actions. |
| RET-02 | Review | Let the learner enable/disable review and tune duration, cadence, and review types per goal. | Must | MVP | Changes affect future suggestions, never block roadmap access, and do not create a readiness penalty. |
| RET-03 | Retrieval practice | Prompt recall, explanation, or application before revealing the answer and use response/confidence to schedule later review. | Must | MVP | A review item records attempt, optional confidence, feedback/correction, next interval, and later varied-context result. |
| PRG-01 | Progress | Default to detailed progress: coverage, proficiency, retention, and readiness; offer a simple display setting. | Must | MVP | Detailed values include definitions/evidence links; simple mode does not delete data. |
| PRG-02 | Progress | Represent knowledge as likely known, partial, unverified, or new and never as inferred completion. | Must | MVP | All inferred status UI uses these states and exposes correction control. |
| EVAL-01 | Evaluation | Show rubric and assumptions for evaluation; support multiple valid solutions. | Must | MVP | Evaluation records dimension-level rationale and does not fail a valid alternate solely for differing approach. |
| EVAL-02 | Evaluation | Support dispute/re-evaluation history and preserve unresolved ambiguity without readiness penalty. | Must | MVP | Learner can request re-evaluation; history shows prior result; unresolved marker does not reduce readiness. |
| HND-01 | Hands-on | Support scenario → artifact/code/design/decision → visible rubric review → adaptive cross-question → revision → evidence. | Must | MVP | Completed hands-on record links each stage and revision evidence. |
| HND-02 | Hands-on | Label static reviews as static and never claim runtime behavior from them. | Must | MVP | Static-only result contains an explicit limitation label. |
| HND-03 | Scenario realism | Match examples and exercises to the target role using credible production constraints, alternatives, incidents, and failure modes. | Must | MVP | Reviewed scenario fixtures for each exposed level avoid generic toy domains unless an atomic concept genuinely requires one. |
| RUN-01 | Runner | Run local Java compile/test first; allow Python only where relevant and optional local database connector. | Must | MVP | Java is supported in MVP validation; Python/DB capability is advertised only when configured. |
| RUN-02 | Runner | Require explicit run confirmation, temporary workspace, argv execution, controlled environment, cleanup, cancel, and structured output. | Must | MVP | Run record displays command arguments, lifecycle state, output, cleanup result, and cancellation outcome. |
| RUN-03 | Runner | Enforce configured time/resource limits and state that controlled subprocesses are not a sandbox. | Must | MVP | Limit breach ends the run and returns structured status; UI/docs include the limitation. |
| RUN-04 | Runner | Offer Go execution support. | Later | Post-MVP | Go support is absent from MVP acceptance and runner policies can be extended. |
| CNT-01 | Content | Model canonical topics as versioned graph nodes with stable IDs, prerequisites, relationships, level, and version. | Must | MVP | Graph validation rejects missing stable ID/version or invalid relationships. |
| CNT-02 | Content | Maintain a personal overlay for roadmap ordering, skips, depth, and accepted proposals. | Must | MVP | Overlay changes do not mutate canonical content and are attributable to learner approval. |
| CNT-03 | Generated content | Generate and cache personalized learner-facing lessons, explanations, examples, exercises, refreshers, and questions with provenance. | Must | MVP | Each artifact identifies its goal/topic context, approved canonical version, provider/model, generation time, imports used, and supporting sources. |
| CNT-04 | Sources and citations | Use authoritative sources appropriate to the claim and disclose citations progressively. | Must | MVP | Sensitive, disputed, comparative, or time/version-dependent claims expose claim-level support; routine reading remains self-contained with expandable details. |
| CUR-01 | Curriculum | Bound MVP canonical content to Java/Spring Boot microservices plus AWS and representative connected System Design/RDB topics. | Must | MVP | Catalog scope statement and graph tags show boundaries; no comprehensive coverage claim. |
| CUR-02 | Curriculum | Include DSA only where scenario-relevant and defer Go+AWS. | Must | MVP | DSA nodes require scenario relationship; Go+AWS is marked Later. |
| CUR-03 | Publication | Keep AI-assisted canonical drafts unpublished until designated editorial approval; allow authored or curated corrections. | Must | MVP | A draft cannot appear in a published canonical graph before a valid approval record exists. MVP has no in-app publication UI; publication happens via offline publish tooling that writes the approval record (Appendix H, D1). |
| CUR-04 | Updates | Present published canonical updates as opt-in diff/merge proposals to active goals. | Must | MVP | Existing goal state is unchanged until the learner accepts all or selected changes; conflicts and impacts are visible. At least one two-version fixture exercises the diff/merge path (Appendix H, D1/D9). |
| SET-01 | Settings | Provide profile, imports, provider/network disclosure, accessibility, progress-display, export, and delete controls. | Must | MVP | Settings changes persist locally and expose their effect. |
| SET-02 | Accessibility | Use accessibility-oriented components and keyboard-operable essential flows. | Must | MVP-hardening | Keyboard and assistive-technology checks cover onboarding, roadmap, questions, feedback, notebook, and settings. |
| AI-01 | AI | Run personalized generation and evaluation through schema-validated domain contracts. | Must | MVP | Invalid output is rejected/quarantined; accepted output records provider/model/time/input references and cannot directly mutate governed state. |
| AI-02 | AI | Use configurable local Codex 5.6 Terra/high invocation by default and Claude as an alternative. | Must | MVP | Provider selection routes through one adapter; unavailable provider produces recoverable error. |
| AI-03 | AI | Add future provider adapters for OpenRouter and DeepSeek without changing domain contracts. | Later | Post-MVP | No MVP flow depends on these providers. |
| DAT-01 | Data | Persist local owner-scoped data with an owner_id seam and no MVP authentication. | Must | MVP | Built-in local owner is assigned to created records; no login flow is required. |
| DAT-02 | Data | Store jobs durably and process them with one worker process exposing an interactive lane and a background lane. | Must | MVP | Restart-safe queued/running/failed/succeeded states are queryable; an in-flight background job never blocks an interactive conversational turn (Appendix H, D4/D8). |
| PRV-01 | Network disclosure | Permit network access for configured model providers and source retrieval only with clear disclosure. | Must | MVP | Before first use and in Settings, the learner can see destination category, operation purpose, and data categories that may leave the device; strict offline support is not claimed. |
| PRV-02 | Data minimization | Send only the context required for the disclosed model/source operation and redact avoidable secrets from logs. | Must | MVP | Provider requests and diagnostic logs can be inspected against documented inclusion/redaction rules. |
| SYS-01 | Architecture | Implement the locked local stack and modular monolith ports for models, identity, runners, persistence, search, and sources. | Must | MVP | Repository uses specified primary stack and dependency direction permits port substitution. |
| SYS-02 | Search | Use SQLite FTS5 for local search in MVP. | Must | MVP | Topic/content search works without a vector database. |
| SYS-03 | Events | Deliver job/progress updates via SSE. | Must | MVP | Client reconnect or error state is visible and query fallback remains available. |
| SAAS-01 | Future SaaS | Prevent an ordinary SaaS learner from publishing canonical content. | Later | Post-MVP | Future authorization separates personal suggestions from designated editorial publication. |
| SAAS-02 | Future SaaS | Preserve seams for Postgres, object storage, managed queue, API model access, remote isolated runner, and Google/email identity. | Later | Post-MVP | Architecture appendix defines replacement boundaries without MVP implementation dependency. |

## 7. Assessment, evidence, progress, notebook, and review

Assessments evaluate the ladder appropriate to the task, with explicit rubric dimensions such as correctness, assumptions, constraints, trade-offs, communication, diagnosis, and defensibility. A response can be strong despite a different valid design. Factual judgments use authoritative, claim-appropriate evidence; trade-offs are evaluated against stated assumptions and consequences.

Evidence is append-only where practical: attempts, feedback, learner corrections, revisions, source snapshots, and accepted plan changes have timestamps and links. Progress summarizes evidence as coverage, proficiency, retention, and readiness. It must show uncertainty and contradictions rather than flattening them into a completion percentage.

Evidence transfer is conservative and inspectable. A new goal can reuse durable profile context and relevant evidence, but classifies it as likely known, partially transferable, unverified, or new against that goal's target bar. It never transfers a topic completion flag as mastery, never hides the topic, and lets the learner correct the inference.

The per-goal notebook collects useful system-generated entries (for example, a decision or misconception) and user notes; entries are always labeled. The optional review queue creates retrieval prompts with spacing, interleaving, and changed context. Dismissing a review is a preference signal, not a readiness penalty.

## 8. Interview Prep

Interview Prep is not a gated capstone. Refresher gives rapid, source-linked revisitation of relevant concepts. Questions supports editable recommended bundles across technical subjects and optional behavioral/leadership; role and level are generic product-company context only.

Practice is conversational text assessment: hints may be requested, feedback is visible per attempt, retries are supported, and adaptive follow-ups target assumptions or evidence gaps. Mock simulates a bounded text interview: the interviewer asks adaptive follow-up questions one at a time, but hints and evaluative feedback are unavailable until the run ends; feedback is then consolidated. Neither mode reports a hiring prediction or company-specific readiness guarantee.

## 9. Content, imports, citations, and governance

MVP learner-facing lessons, explanations, examples, exercises, refreshers, and questions are AI-generated from the approved canonical graph, goal context, relevant evidence, and approved imports, then cached and versioned for consistency. Canonical graph material may begin as AI-assisted drafts and may receive authored or curated corrections. Every AI-assisted canonical draft remains unpublished until a designated editorial approver records approval.

Generated content is personalized and progressively disclosed, preserves provenance, and links claims to sources appropriate to their type: official documentation, standards/specifications, primary research, or credible attributed expert/industry material when appropriate. Sources make a claim inspectable; citations alone do not make generated text correct or canonical.

Imported text is a seed, not truth. The system parses it into inspectable statements, marks them untrusted, maps and deduplicates them, and visibly flags wrong, outdated, inapplicable, incomplete, or uncertain material. The learner can verify, correct, expand, or dismiss the proposed coverage. Personal overlay proposals always need explicit learner approval. Published canonical revisions are presented as opt-in diffs and merge choices; a future ordinary SaaS learner is never permitted to publish canonical content.

### Tension resolutions

| Tension | Resolution |
| --- | --- |
| Generation vs. authority | AI personalizes and drafts; factual confidence comes from claim-appropriate evidence, while canonical status requires editorial approval. Citations alone confer neither. |
| Local vs. network | Data and services are local by default; configured model/source network calls are disclosed and allowed. Strict offline operation is unsupported. |
| Roadmap vs. adaptation | Canonical roadmap stays visible and stable; adaptation produces explicit recommendations and learner-approved overlay changes only. |
| Citations vs. overload | Surface concise claim-linked citations in context, with full source/provenance in the Sources layer; citations do not themselves establish authority. |

## 10. Product architecture and future seams

The MVP is a modular monolith: React, TypeScript, Vite, TanStack Router and Query, Tailwind, accessibility-oriented Radix/shadcn-style primitives, Markdown, and CodeMirror on the client; FastAPI, Pydantic, SQLAlchemy, Alembic, SQLite FTS5, a database job table with one worker, and SSE on the server. API types are generated from OpenAPI. Tooling/tests use uv, pnpm, pytest, Vitest, React Testing Library, and Playwright.

Ports isolate model providers, identity, local runners, persistence, search, and sources. Manifests plus Markdown hold authored content. No orchestration library is required or prohibited. The MVP deliberately avoids Redis, Kafka, Kubernetes, vector databases, Electron, and early microservices.

Future hosting may replace SQLite with Postgres, local files with object storage, the worker with a managed queue, local model invocation with API model access, local subprocesses with a remote isolated runner, and local owner with Google/email identity. These are seams, not MVP work.

## 11. AI, network, and execution safety

The client must disclose network-affecting actions and provider/source destination categories before use and in Settings. A provider adapter accepts structured requests and yields schema-validated domain results; raw model prose cannot directly mutate canonical graph, learner overlay, readiness, or execution policy. Failed validation preserves diagnostic information without treating output as a result.

Local execution accepts declared inputs only, uses argv rather than a shell, creates a temporary run directory, controls environment variables, applies configured resource/time limits, streams structured output, permits cancellation, and attempts cleanup. This is controlled subprocess execution, not a security sandbox. It must not be presented as proof of runtime safety, production behavior, AWS behavior, or an isolated hostile-code environment. No real AWS credentials or provisioning belong in MVP.

## 12. Implementation appendices

### Appendix A — Conceptual data model and invariants

Core entities: `Owner`, `LearnerProfile`, `GoalWorkspace`, `CanonicalGraphVersion`, `Topic`, `TopicRelation`, `Source`, `Claim`, `Citation`, `ContentRevision`, `EditorialApproval`, `PersonalOverlay`, `OverlayProposal`, `LearningState`, `Evidence`, `Assessment`, `AssessmentDispute`, `NotebookEntry`, `ReviewItem`, `InterviewBundle`, `InterviewRun`, `RunnerJob`, `Job`, `ImportRecord`, `ImportStatement`, and `AuditEvent`.

Invariants:

- Canonical `Topic.id` is stable across versions; published graph versions are immutable.
- Prerequisite and relationship references resolve within a graph version; invalid cycles are rejected unless an explicitly supported relationship type permits one.
- A personal overlay references canonical stable IDs and cannot change canonical text or publication state.
- Inferred learner state is one of `likely_known`, `partial`, `unverified`, or `new`; it is not completion.
- Canonical publication requires an editorial approval record. Personal proposal application requires learner approval.
- Evidence and evaluation history preserve prior assessments; re-evaluation appends rather than overwrites.
- Unresolved ambiguity is represented explicitly and cannot reduce readiness by itself.
- Every generated/curated claim can retain provenance links, including unavailable/withdrawn source status.
- All local owner records include `owner_id`, even though MVP has one built-in owner.
- A goal workspace pins exactly one canonical graph version; merge acceptance moves the pin atomically (Appendix H, D9).
- Learner corrections and confirmations are first-class inputs to derived learner state; recomputation never silently reverses them (Appendix H, D6).
- Deleting a goal tombstones evidence referenced read-only by other goals (classification metadata retained, content dropped) and downgrades dependent learning states to `unverified` with an audit entry (Appendix H, D5).
- Version immutability is enforced by the publish tooling itself: it refuses in-place mutation of any version holding an approval record (Appendix H, D1).

### Appendix B — Contracts

**API:** OpenAPI is the source of truth for generated TypeScript client types. Endpoints cover goal/workspace lifecycle, roadmap and overlays, topic content, imports, evidence/assessments/disputes, notebook/review, interview runs, jobs, sources/provenance, settings, export/delete, and canonical diff/merge proposals.

**Provider:** `GenerateRequest` includes purpose, structured context references, capability target, output schema, safety mode, and provider selection. `GenerateResult` includes validated payload, provider/model metadata, timestamp, provenance references, warnings, and failure status. Adapter implementations must not expose provider-specific payloads beyond the port. Transport is CLI subprocess with the controls in Appendix H, D7 (stdin/temp-file context delivery, non-interactive flags, env allowlist, inactivity + absolute timeouts, first-output heartbeat, process-group cancellation, pinned per-provider output contract).

**Jobs/SSE:** Job states are `queued`, `running`, `succeeded`, `failed`, `cancel_requested`, `cancelled`, and `expired` where retention policy requires it. SSE events contain event ID, job ID, state, timestamp, typed progress/result reference, and retryable flag. Clients reconcile with job GET after reconnect. Appendix D's "failed-recoverable" maps to `failed` with `retryable: true`. On restart: `running` → `failed`+retryable, `cancel_requested` → `cancelled`, `queued` resumes. A job's result artifact and terminal state commit in one transaction; retry checks for a committed artifact under the job's dedupe key before re-executing. Retry semantics are typed per job kind: idempotent re-run, cache-checked re-run (generation), resume-with-substitution (interview turns), user-confirmed fresh run (runner). See Appendix H, D4/D8.

**Imports:** import request carries type, source text/reference, parser version, and owner. Result preserves original content reference, extracted statements, confidence only as parsing metadata, untrusted status, and learner verification decisions.

**Evaluation:** request names artifact/answer, task, rubric, assumptions, evidence references, and requested capability. Result includes dimension scores or qualitative outcomes, facts, trade-offs, citations, ambiguities, feedback, cross-question candidate, and a revision invitation. Re-evaluation references the prior evaluation and dispute reason.

**Diff/merge:** canonical update proposal includes base/target graph version, affected topics/relationships/content, conflicts with personal overlay, recommended resolution, learner decision, and audit timestamp. No merge occurs without explicit learner action. Conflicts are resolved inside the acceptance flow with overlay-wins pre-selected; acceptance atomically moves the goal's single version pin and records resolutions as overlay entries against the target version; pending diffs are recomputed base→latest, never chained (Appendix H, D9).

**Generated-content cache:** cache key is `(canonical_graph_version, topic_id, goal_id, layer, topic_mapped_approved_imports_hash, prompt_template_version)`. Live evidence, profile, and provider/model are excluded from the key but recorded in artifact provenance as a personalization snapshot used to surface a visible staleness indicator; regeneration is always an explicit learner action or a key-changing event, and generation jobs are single-flighted per key (Appendix H, D3).

**Voice-extensible:** interfaces may accept modality metadata and transcript/media references later, but MVP exposes text only and has no voice requirement.

### Appendix C — Runner threat model

| Threat / limitation | MVP control | Residual statement |
| --- | --- | --- |
| Shell injection | Construct argv directly; do not invoke a shell. | User code still runs as a controlled local subprocess. |
| Excess CPU/time/output | Configured limits, output capture/truncation policy, cancellation, job state. | Limits are not a hostile-code sandbox guarantee. |
| File pollution | Per-run temporary directory and cleanup record. | Process permissions define remaining host access risk. |
| Environment/secrets leakage | Controlled minimal environment; do not inject AWS credentials. | Local machine policy remains outside product control. |
| Misleading validation | Separate compile/test/static states and limitation labels. | Passing local test is not production/AWS proof. |
| Orphaned process | Cancellation workflow, process tracking, cleanup attempt/status. | OS failures may require manual recovery. |

### Appendix D — Operational states

| Area | States / required behavior |
| --- | --- |
| Onboarding / diagnostic | not-started, in-progress, skipped, paused, resumed, roadmap-preview, confirmed, failed-recoverable; preserve completed answers and never require optional steps. |
| Roadmap / topic | loading, ready, checkpoint-saved, stale-canonical-version, overlay-conflict, bridge-proposed, bridge-postponed/dismissed/accepted, unavailable; retain user control and saved work. |
| Model/source request | idle, preparing, waiting for disclosure, queued, running, succeeded, failed, cancelled; preserve prompt/context references and show retryability. |
| Import | selected, parsing, parsed-untrusted, learner-review, applied, failed, cancelled; never auto-complete. |
| Runner | pending-confirmation, queued, preparing, running, cancel-requested, completed, failed, timed-out/limited, cancelled, cleanup-pending, cleanup-complete/failed. |
| Interview / evaluation | ready, answering, follow-up, submitted, evaluating, feedback-ready, disputed, re-evaluating, ambiguity-unresolved, failed-recoverable; Mock exposes no hints or feedback before completion. |
| Notebook / review | empty, ready, saved, due, dismissed, disabled, generation-failed; empty or disabled review never blocks navigation. |
| Search / Settings | empty, results, stale-index, invalid-setting, saved, export-running/failed/complete, delete-confirmation/running/failed/complete. |
| Canonical draft | authored/curated or AI-draft, validation-failed, pending-editorial-approval, published, superseded. |
| Overlay/diff | proposed, awaiting-learner-decision, accepted, postponed, dismissed, conflict-needs-resolution. |
| SSE | connected, reconnecting, unavailable; client offers observable refresh/query fallback. |

### Appendix E — Non-functional requirements

| ID | Category | Requirement | Acceptance evidence |
| --- | --- | --- |
| NFR-01 | Accessibility | Essential flows are keyboard-operable with semantic labels and visible focus. | Automated checks plus representative manual flow test. |
| NFR-02 | Reliability | Durable jobs survive server restart without ambiguous terminal result. | Integration test covers restart/reconciliation behavior. |
| NFR-03 | Integrity | Canonical versions, overlay decisions, evidence, and approvals are auditable. | Tests reject unauthorized/missing transitions and inspect audit links. |
| NFR-04 | Privacy | Local data and network disclosure are explicit; export/delete are available. | Settings and API tests demonstrate disclosure and requested data operation. |
| NFR-05 | Safety | Runner and model contracts fail closed on policy/schema failure. | Negative tests show no execution or mutation after failure. |
| NFR-06 | Observability | Structured local logs correlate request/job/run IDs without storing avoidable sensitive content. | Failure record links UI state to safe diagnostic record. |
| NFR-07 | Maintainability | Domain ports and OpenAPI client prevent provider or infrastructure leakage. | Contract/unit tests run against a fake adapter. |
| NFR-08 | Performance | Local navigation, roadmap rendering, and search remain responsive while long operations stream asynchronously. | Implementation establishes and records representative local benchmarks rather than inventing PRD thresholds. |
| NFR-09 | Testability | Deterministic domain logic is tested without live models; AI behavior uses curated contract and regression fixtures. | Unit/contract suites cover transfer, mutation protection, citations, rubrics, and provider-schema failures. |
| NFR-10 | Portability | Supported OS/toolchain assumptions and failure messages are documented without assuming every runtime exists. | Runtime-detection tests cover supported, missing, and incompatible toolchain states. |
| NFR-11 | Compatibility | Database, canonical manifests, overlays, generated artifacts, and jobs use versioned migrations. | Upgrade fixtures preserve representative existing local data or stop with a recoverable migration error. |

### Appendix F — Migration, export, delete, and logging seams

Schema migrations use Alembic. Export produces a documented portable representation of profile, goals, overlays, evidence metadata, notebook, reviews, imports, and provenance references; it must indicate unavailable content or sources rather than fabricate them. Delete identifies locally owned data scope and completion/failure status; retention and recovery policy are TBD. Logging is structured and correlates IDs across API, job, provider, and runner operations; field redaction policy, log retention, and support-access model are TBD.

### Appendix G — Traceability matrices

| Outcome | Primary requirements | Verification |
| --- | --- | --- |
| Learner-controlled adaptive roadmap | CORE-03/04/05, ONB-03, LRN-01/04, DEP-01, GAP-01/02, CNT-02, CUR-04 | Playwright flow: second goal, transfer correction, preview, reorder, override, bridge decision, update diff. |
| Defensible learning evidence | LRN-03, EVAL-01/02, HND-01, PRG-01/02, NBK-01, RET-01/02 | API/integration tests and rubric-history UI test. |
| Honest interview prep | INT-01/02, REF-01, QPR-01/02, QMK-01/02 | Practice/Mock behavior and feedback-timing tests. |
| Governed trustworthy content | IMP-01/02, CNT-01/03/04, CUR-01/03/04, AI-01, PRV-01/02 | Graph validation, provenance, citation, approval, disclosure, and import-review tests. |
| Safe local operation | RUN-01/02/03, DAT-02, SYS-02/03, NFR-02/05 | Runner lifecycle, job restart, SSE reconciliation tests. |

### Appendix H — Resolved architecture decisions (D1–D11)

These decisions were adversarially reviewed through two independent lenses (PRD-consistency and runtime failure modes) before adoption; the review's amendments are folded in. Where an ADR conflicts with earlier prose, the ADR governs.

**D1 — Canonical publication posture.** No in-app authoring or publication UI in MVP. The canonical graph is published by offline seed/publish tooling that writes a real `EditorialApproval` record attributed to the designated editorial approver — for MVP, the local owner acting explicitly in that role (see §13); the role stays distinct from "learner" in the data model to preserve SAAS-01. The tooling runs only against a stopped server or writes each version in a single transaction with the approval record last; refuses in-place mutation of any version that already holds an approval record (new version only); and passes the same Alembic head check as the server. Every read path gates on approval-record existence, so a half-seeded version can never reach a roadmap. Subsequent offline-published versions flow through CUR-04 diff/merge, and at least one two-version fixture exercises that path in MVP.

**D2 — Roadmap semantics.** The roadmap is a deterministic projection of the goal-scoped canonical graph version plus the approved personal overlay, with pending `OverlayProposal`s and conflicts rendered as non-mutating annotations. Ordering is a topological sort with stable-ID lexicographic tie-break, so rebuilds never appear to reorder silently. Goal scoping never hides a topic that carries transferred evidence. AI writes only `OverlayProposal` records: each is pinned to the graph version it was generated against, revalidated at acceptance and rejected with a visible reason if stale, applied in a single transaction, deduplicated by content hash while pending, and capped per goal.

**D3 — Generated-content cache.** Key: `(canonical_graph_version, topic_id, goal_id, layer, topic_mapped_approved_imports_hash, prompt_template_version)`. Live evidence, profile, and provider/model are excluded from the key but recorded in artifact provenance as a personalization snapshot (evidence/state hash, profile hash, provider/model, generation time). Staleness is surfaced, never silent: the app compares the current snapshot hash with the baked one and offers "generated before your correction — regenerate?". Regeneration is an explicit learner action or follows a key-changing event (accepted canonical merge, newly approved topic-mapped imports). LRN-04's adaptive emphasis/examples/exercises are delivered through the recommendation and review channels, never by rewriting cached lessons. Generation jobs are single-flighted per cache key at enqueue.

**D4 — Job recovery.** "Failed-recoverable" in Appendix D maps to `failed` with `retryable: true`. On restart: `running` → `failed`+retryable with a visible retry; `cancel_requested` → `cancelled` (no retry offer); `queued` resumes normally. A job's result artifact and terminal state commit in one transaction, and retry short-circuits to `succeeded` when a committed artifact already exists under the job's dedupe key — no double token spend. Retry semantics are typed per job kind: idempotent re-run (indexing, import parsing), cache-checked re-run (generation), resume-with-substitution (interview turns), user-confirmed fresh run (runner). Runner and provider jobs persist pid/pgid and temp-dir path at spawn; startup reconciliation kills recorded process groups and sweeps temp dirs before marking jobs failed; a janitor removes terminal-state temp dirs.

**D5 — Evidence scope and transfer.** Evidence is immutable and goal-scoped. Cross-goal transfer creates fresh `LearningState` rows in the new goal that reference source evidence read-only with a classification (`likely_known`/`partial`/`unverified`/`new`); nothing is copied or mutated across goals. Deleting a source goal tombstones evidence referenced elsewhere (classification metadata retained, content dropped) and downgrades dependent LearningStates to `unverified` with an audit entry; this impact is shown before delete confirmation.

**D6 — Derived learner state.** Readiness, coverage, proficiency, retention, and LearningState are computed by a deterministic server-side function `f(evidence, learner corrections/confirmations, now)`. Corrections are first-class inputs the function must respect — recomputation never silently reverses them. `now` is explicit because retention decays; values are recomputed on read with per-goal memoization invalidated in the same transaction as evidence appends. Re-evaluation appends and marks the superseded assessment excluded-from-derivation while preserving history. The rule set encodes that unresolved ambiguity cannot reduce readiness (EVAL-02) and dismissed reviews carry no penalty (RET-02). AI output becomes an input only after schema validation records it as evidence.

**D7 — Provider transport.** Codex 5.6 Terra (default) and Claude (alternative) are invoked as CLI subprocesses behind the provider port: argv construction with prompt/context delivered via stdin or temp file (never argv, which leaks into process listings and logs), stdin otherwise closed to /dev/null, mandatory non-interactive flags, a per-port env allowlist (provider CLIs need HOME/auth/proxy variables; the Java runner keeps its separate minimal environment), an inactivity timeout plus an absolute cap, and a distinct no-first-output heartbeat window mapped to a "provider misconfigured / needs auth" recoverable error rather than a generic timeout. Cancellation and timeout kill the process group, since agent CLIs spawn children. Output truncated by a timeout kill is classified retryable-with-diagnostics, not schema-quarantined. Each adapter pins an explicit output contract (e.g., JSONL event stream or final-line JSON). The low-level subprocess utility is shared with the runner; the ports and their policies are separate, and the PRV-01 disclosure gate sits before enqueue.

**D8 — Worker model.** One durable worker process with two lanes: interactive (tutor/Practice/Mock turns, explicit regenerations) and background (bulk generation, import parsing, indexing, review scheduling), so an in-flight background job never blocks a conversational turn. FIFO within a lane; queue-level dedupe/single-flight on cache key; a pending-jobs cap with visible feedback; background work age-promotes if starved beyond a configured interval. This refines DAT-02's "one worker" as one worker process, not one execution slot.

**D9 — Canonical merge.** A goal pins exactly one canonical graph version. Merge acceptance is atomic per goal: one transaction moves the pin to the target version and records every per-conflict resolution as an overlay entry expressed against the target version. Overlay-wins is the pre-selected recommended resolution inside the merge acceptance flow (`conflict-needs-resolution` precedes `accepted`); canonical never silently overrides a learner choice. A topic deleted upstream while carrying learner evidence or overlay state becomes an explicit "archived local topic" overlay entry. Pending diffs are always recomputed base→latest, never chained.

**D10 — Import mapping.** Statements mapping to no canonical topic are held `unmapped`+untrusted; they never auto-create topics or expand curriculum scope (CUR-01). The learner can manually map a statement to an existing canonical topic or dismiss it; "expanding" proposed coverage (§9) can only target existing canonical topics. Mapping re-runs for unmapped statements when a goal adopts a new graph version; identical unmapped statements are deduplicated. A mapping change updates the imports hash, and affected cached artifacts surface the D3 staleness indicator.

**D11 — Diagnostic persistence.** Diagnostic sessions and answers are first-class persisted entities — explicitly not LearningState — owner-scoped, surviving pause, refresh, and restart per Appendix D, with an expiry/cleanup policy for abandoned sessions. Goal confirmation is a single transaction creating the goal, its LearningStates, and any preview-made overlay edits, pinned to the graph version captured at diagnostic start; a newer version published in the meantime arrives as an ordinary CUR-04 diff proposal.

## 13. Metrics, delivery, dependencies, risks, and acceptance

### Metrics

Primary success measure: compare a learner’s initial and delayed reassessment on representative scenarios, looking for improvement in the ability to implement, diagnose, justify, defend, and retain. Record capability evidence and qualitative learner explanation; do not fabricate baselines, numeric targets, or completion-as-success metrics. Secondary diagnostic signals may include accepted vs. dismissed recommendations, revision activity, review participation, and evaluation disputes, interpreted without penalizing learner agency.

MVP pilot instrumentation should also record guardrails: fabricated or inappropriate citations, unsupported runtime/AWS claims, silent roadmap mutations, overconfident evidence transfer, invalid structured model output, unapproved canonical publication attempts, and level-inappropriate scenarios. Events remain local by default; any external telemetry requires a separate disclosed decision.

### Delivery sequence

1. **MVP foundation:** local owner/data schema, bounded canonical graph/content manifests, global profile, multiple goals, onboarding/adaptive diagnostic, roadmap controls, OpenAPI client, and disclosures.
2. **MVP learning and evidence:** topic layers, overlay/bridges, generated content, imports, notebook, assessment/disputes, detailed/simple progress, optional configurable review, and delayed reassessment.
3. **MVP interview:** independent Refresher and Questions, editable bundles, optional behavioral/leadership, Practice, Mock, and rubric history.
4. **MVP AI and hands-on:** provider adapter, source retrieval/provenance, publication approval, diff/merge, durable jobs/SSE, Java runner, and static-versus-runtime labeling.
5. **MVP-hardening:** recovery and migration fixtures, accessibility checks, AI regression fixtures, privacy review, runner threat-model decision, content/rubric review, and end-to-end pilot readiness.
6. **Post-MVP:** Go + AWS, scheduling/study-time planning, voice, company-specific preparation if separately approved, and hosted auth/storage/queues/model APIs/isolated execution. Payments, teams, social features, gamification, and mobile require separate scope.

### Dependencies and TBD ownership

| Dependency / decision | Need | Owner / approver |
| --- | --- | --- |
| Initial canonical source set and source-license review | Curated content and claim provenance | Content owner TBD / editorial approver TBD |
| Editorial approval policy and designated role | Canonical publication gate | Resolved for MVP: the local owner acts as the designated editorial approver, and seed/publish tooling attributes approval records to this role explicitly (never anonymously). Review criteria and any hosted multi-user approver policy remain TBD. |
| Provider access and local invocation configuration | Codex default / Claude alternative | Engineering owner TBD |
| Runner resource policy and supported local prerequisites | Safe Java execution | Engineering/security owner TBD |
| Data deletion, recovery, and log retention policy | Settings/data lifecycle behavior | Product/privacy owner TBD |

### Qualitative risk register

| Risk | Leading indicator | Mitigation | Contingency | Owner |
| --- | --- | --- | --- | --- |
| AI output is plausible but wrong | Evaluation disputes or unsupported claims | Schema validation, sources, provenance, editorial gate | Quarantine/retract draft and show limitation | TBD |
| Learner feels adaptation is opaque | High correction/dismiss rate or feedback | Visible roadmap, reasons, overlay history, explicit approval | Simplify recommendations and increase user controls | TBD |
| Citation overload harms flow | Learners avoid Sources or report clutter | Layer citations and concise claim links | Reduce default density while retaining traceability | TBD |
| Local runner harms host or misleads learner | Limit breaches, cleanup failures, overclaimed results | Controlled subprocess policy and labels | Disable runner feature; preserve static workflow | TBD |
| Local provider/source calls fail | Repeated failed/retrying jobs | Disclosed configuration, resilient states, retries | Continue with authored/curated content and saved work | TBD |
| Scope expands toward full curriculum/SaaS | New requirements depend on deferred systems | Enforce scope ledger and Later seams | Split into post-MVP roadmap | TBD |

### Acceptance

**Product acceptance:** A learner can create multiple goal workspaces, inspect/correct transferred evidence, preview and alter a visible roadmap, learn from bounded layered topics, produce evidence, use optional review, and independently complete Interview Practice or Mock without unsupported readiness claims. Mock asks adaptive cross-questions while withholding hints and evaluative feedback until completion.

**Engineering acceptance:** The specified local stack is operational; OpenAPI client generation, migrations, durable jobs/one worker, SSE reconciliation, SQLite FTS5 search, test suites, and Java controlled-run lifecycle are verified. Static and runtime results remain distinct.

**Governance/content acceptance:** Published canonical graph is stable-ID/versioned and editorially approved; imports remain untrusted until reviewed; claims retain source/provenance; updates are opt-in diff/merge; personal proposals are explicit; designated roles/owners are documented or left TBD.

## 14. Open questions and final audit checklist

### Open questions

1. **Curriculum boundary (TBD):** Which Java/Spring Boot/AWS topics and which connected System Design/RDB topics form the minimum reviewed MVP spine?
2. **Editorial authority (partially resolved):** For MVP the local owner is the designated editorial approver; approval records are attributed to that role explicitly (§13, Appendix H D1). Still TBD: the evidence and review criteria an approval must satisfy, and the approver policy for any future hosted multi-user deployment.
3. **Source policy (TBD):** Which initial sources are approved, how are licenses/terms reviewed, and what snapshot/cache/withdrawal policy applies?
4. **Local support matrix (TBD):** Which operating systems, Java/Python versions, build tools, and unsupported configurations are documented?
5. **Runner posture (TBD):** Is execution disabled until enabled in Settings, or enabled after a first-run risk acknowledgment; what resource ceilings and cleanup guarantees apply?
6. **Database exercises (TBD):** Does the optional relational connector only connect to a user-supplied database, or also manage a local instance?
7. **Provider operations (partially resolved):** Transport, timeout, environment, cancellation, and output contracts are resolved in Appendix H, D7 (CLI subprocess). Still TBD: per-provider installation and authentication-discovery specifics and supported CLI version ranges.
8. **Assessment design (TBD):** Which representative scenarios and minimum topic breadth define initial and delayed reassessment for each exposed role/level?
9. **User-facing taxonomy (TBD):** Which role-level labels and competency descriptions appear in onboarding while acknowledging company-title variance?
10. **Size and retention limits (TBD):** What limits apply to imports, artifacts, transcripts, generated content, execution output, temporary files, and retained jobs?
11. **Data lifecycle (TBD):** What are precise delete recovery, export package/versioning, transcript inclusion, backup, and logging retention/redaction policies?
12. **Telemetry (TBD):** Is any external telemetry included after MVP, and if so, what explicit consent and disclosure are required?

### Final audit checklist

- [ ] Learn and Interview Prep are the only paths; Refresher and Questions remain independently reachable.
- [ ] MVP curriculum claims remain bounded to Java/Spring Boot microservices + AWS with representative linked System Design/RDB.
- [ ] Whole roadmap, learner corrections, depth/order changes, and optional recommendations are visible and explicit.
- [ ] Inferences never become completion; ambiguity and valid alternatives are handled without an automatic readiness penalty.
- [ ] Practice and Mock have distinct hint/follow-up/feedback behavior.
- [ ] Mock retains adaptive interviewer cross-questioning and withholds only hints and evaluative feedback until completion.
- [ ] Imports, canonical drafts, overlays, updates, sources, and provenance observe their approval and opt-in boundaries.
- [ ] Network use is disclosed; strict offline is not promised; no real AWS is included.
- [ ] Runner labels controlled-subprocess limitations and records confirmation, limits, cancellation, output, and cleanup.
- [ ] Locked stack and future seams are preserved without prematurely adding prohibited infrastructure.
- [ ] No baselines, numerical targets, source licenses, OS matrices, CLI commands, or open-question answers have been fabricated.
