# IDK-009 — Assessment and derived-state decision

Phase 0, blocking decision. This document records the approved assessment scenario registry and content, rubric dimensions and qualitative outcome representation, valid-alternative and ambiguity rules, derived-state rule set, and review-scheduling parameters. Approval resolves the policy/content decision; it does not claim production activation before the implementation and review evidence in section 11 passes.

## 1. Status and versions

Approved as decision version 1.0 on 2026-08-13.

Owner and approver: content/assessment owner, per PRD §13. Approval was directed through the project implementation request.

| Contract | Approved version |
| --- | --- |
| Scenario registry | `assessment-scenarios-v1` |
| Scenario content revision | `idk009-v1-r1` |
| Hands-on rubric | `hands-on-rubric-v1` |
| Practice rubric | `practice-rubric-v1` |
| Mock rubric | `mock-rubric-v1` |
| Outcome representation | `qualitative-outcomes-v1` |
| Ambiguity policy | `assessment-ambiguity-v1` |
| Derived-state rules | `derived-state-v1` |
| Review schedule | `review-schedule-v1` |

## 2. Fixed boundaries

This decision applies PRD EVAL-01/EVAL-02, PRG-01/PRG-02, HND-03, RET-01/RET-03, and Appendix H D6. These invariants are mandatory:

- An assessment records its scenario revision, rubric version, assumptions, dimension outcomes, rationale, and evidence references. A different valid approach is not a failure merely because it differs from an example answer.
- Facts and mechanical invariants are distinct from choices and trade-offs. A defensible trade-off is a positive qualitative outcome, not a lesser score.
- Re-evaluation appends an immutable successor and preserves history. No result is overwritten.
- An unresolved ambiguity is explicit. The ambiguous part has exactly zero positive or negative derived-state effect.
- Derived state is the deterministic server-side function `f(eligible evidence, corrections/confirmations, explicit now, rule_version)`.
- A learner correction remains the displayed LearningState until explicitly superseded. Aggregate dimensions apply the separately specified correction semantics in section 9; recomputation never silently changes the correction itself.
- Viewing, elapsed time, imports, generated text, fixture output, review scheduling, and Run without Submit are not assessment evidence.
- The only persisted classification values are `likely_known`, `partial`, `unverified`, and `new`. The learner-facing label for `likely_known` is “likely known.” None means completion, mastery, hiring probability, or a job/interview guarantee.
- Detailed/simple progress is presentation-only. Dismissing or disabling review changes suggestions only and has zero derived-state effect.
- Static review never claims compilation, execution, production, AWS, or hostile-code isolation.

## 3. Approved assessment breadth

These are evaluator calibration boundaries, not learner-facing role descriptions. IDK-004 remains the authority for onboarding copy and company-title variation.

| Level | Required assessment breadth |
| --- | --- |
| Mid-level | Make a bounded service or data-path change correct and testable; diagnose direct failure; explain local operational consequences. |
| Senior | Own an end-to-end multi-service/data flow; reason about partial failure, recovery, rollout, observability, and competing system choices. |
| Staff | Set cross-system and multi-team decision boundaries; plan migration and rollback; expose second-order failure, capacity, cost, ownership, and exception-governance consequences. |

Company-specific claims and real-company names are prohibited.

## 4. Scenario registry contract

`scenario_id` is the versioned structural identity. All approved rows use content revision `idk009-v1-r1`. A copy-only wording correction creates a new content revision under the same `scenario_id`; changing level, kind, topic binding, capability, paired initial, rubric, or assessment boundary creates a new `scenario_id` version. Every assessment persists both values.

IDK-001 has not approved canonical topic stable IDs. Therefore `topic_binding_key` is the exact assessment-owned semantic binding. Production activation maps each key to one approved canonical topic stable ID and records that mapping with the scenario revision; the mapping may not be inferred from prose. This is an integration binding, not a new content decision.

IDK-204 owns persistence and validation of that mapping, consuming the approved graph published by IDK-102 after IDK-001. Mechanism tests may use synthetic mappings. An assessment cannot become authoritative until its exact mapping exists; the scenario consumers do not invent or infer a topic ID.

All six dimensions of the referenced rubric are required for every v1 scenario. The first two common dimensions are critical. Version 1 has no optional or `not-observed` dimension behavior.

| Scenario ID | Level / kind | Topic binding key | Capability | Rubric | Paired initial |
| --- | --- | --- | --- | --- | --- |
| `mid-order-idempotency-initial-v1` | Mid / initial | `event-idempotency` | `implement` | `hands-on-rubric-v1` | — |
| `mid-inventory-redelivery-delayed-v1` | Mid / delayed | `event-idempotency` | `implement` | `hands-on-rubric-v1` | `mid-order-idempotency-initial-v1` |
| `mid-spring-latency-practice-v1` | Mid / practice | `spring-data-path-diagnosis` | `diagnose` | `practice-rubric-v1` | — |
| `mid-order-lifecycle-mock-v1` | Mid / mock | `service-reliability-reasoning` | `defend` | `mock-rubric-v1` | — |
| `senior-checkout-partial-failure-initial-v1` | Senior / initial | `distributed-failure-recovery` | `defend` | `hands-on-rubric-v1` | — |
| `senior-fulfillment-backlog-delayed-v1` | Senior / delayed | `distributed-failure-recovery` | `defend` | `hands-on-rubric-v1` | `senior-checkout-partial-failure-initial-v1` |
| `senior-zero-downtime-schema-practice-v1` | Senior / practice | `relational-schema-evolution` | `defend` | `practice-rubric-v1` | — |
| `senior-commerce-reliability-mock-v1` | Senior / mock | `service-reliability-reasoning` | `defend` | `mock-rubric-v1` | — |
| `staff-platform-migration-initial-v1` | Staff / initial | `platform-evolution` | `defend` | `hands-on-rubric-v1` | — |
| `staff-regional-audit-delayed-v1` | Staff / delayed | `platform-evolution` | `defend` | `hands-on-rubric-v1` | `staff-platform-migration-initial-v1` |
| `staff-cascading-failure-practice-v1` | Staff / practice | `systemic-failure-containment` | `defend` | `practice-rubric-v1` | — |
| `staff-multiregion-evolution-mock-v1` | Staff / mock | `multi-region-evolution` | `defend` | `mock-rubric-v1` | — |

Delayed eligibility is based on UTC calendar dates: a delayed submission is eligible when `date(delayed.submitted_at) >= date(initial.submitted_at) + 7 days`. This matches `derived-state-v1`'s UTC-date memo boundary and avoids an intra-day cache transition.

Capability projection is exact-only in version 1. An assessment contributes only to a target cell with the same capability value. Neither a higher nor lower capability is projected into a different cell; missing approved assessment content remains visible as an evidence gap.

## 5. Approved scenario content

The text below is normative content revision `idk009-v1-r1`. Each scenario permits any solution that satisfies its constraints with sound mechanics and explicit consequences.

### 5.1 Mid-level

#### `mid-order-idempotency-initial-v1`

- Prompt: “Implement or precisely design a Spring Boot order handler for at-least-once payment events. Events may be duplicated and reordered. PostgreSQL is available. A process can crash after database commit but before acknowledgement. You cannot use a distributed transaction. Show the transaction/idempotency boundary, failure behavior, and tests.”
- Disclosed assumptions: a stable payment-event ID exists; one order may receive multiple legitimate payment events; broker acknowledgement is separate from the database transaction.
- Expected artifact: code/pseudocode or precise design, schema constraint, failure-window analysis, and concurrency/replay tests.
- Accepted alternatives: an idempotency record and business mutation in one transaction; or an equivalent unique business/event key plus atomic upsert/update. Both must return the durable winner on replay.
- Constraint-breaking near miss: check-then-insert outside the business transaction, or acknowledging before durable commit.
- Cross-question: “What result is returned when acknowledgement is lost after commit and another process handles the duplicate concurrently?”
- Static limitation: “Static review can inspect the declared transaction and idempotency boundaries, but cannot execute concurrent commits or broker redelivery.”

#### `mid-inventory-redelivery-delayed-v1`

- Prompt: “Repair an inventory-reservation consumer after replayed shipment events produce duplicate and out-of-order updates. Concurrent workers may read stale reservation versions, and a worker may restart between database commit and acknowledgement. Preserve legitimate later shipment updates and show how the repair is tested.”
- Disclosed assumptions: shipment-event IDs and per-reservation versions are stable; PostgreSQL optimistic or unique constraints are available; no order/payment code or identifiers from the paired scenario may be reused.
- Expected artifact: repaired handler/design, version/idempotency invariant, restart behavior, and changed-domain concurrency tests.
- Accepted alternatives: atomic version-guarded update plus processed-event record; or a monotonic event-version constraint with idempotent transition logic.
- Constraint-breaking near miss: treating every duplicate as a new reservation or rejecting every later legitimate event after the first.
- Cross-question: “How does the handler distinguish a duplicate from a legitimate later shipment state after restart?”
- Static limitation: “Static review can inspect update guards and tests, but cannot reproduce database scheduling, process restart, or broker ordering.”

### 5.2 Senior

#### `senior-checkout-partial-failure-initial-v1`

- Prompt: “Design checkout across order, payment, and inventory when payment may succeed while reservation times out, retries and compensation can race, and two-phase commit is unavailable. Define durable invariants, client-visible states, retry/compensation ownership, an incident playbook, and verification.”
- Disclosed assumptions: every command has a stable idempotency key; services own separate databases; a durable message mechanism is available; temporary pending states are acceptable.
- Expected artifact: decision record/diagram, state transitions, invariants, recovery and reconciliation plan, operational signals, and tests.
- Accepted alternatives: choreography with transactional outbox and idempotent consumers; or orchestration with durable steps/compensations. Either must define convergence and manual-repair boundaries.
- Constraint-breaking near miss: claiming exactly-once delivery or atomic cross-service rollback without a mechanism.
- Cross-question: “Who owns reconciliation when payment is durable but both the reservation response and compensation acknowledgement are lost?”
- Static limitation: “Static review can assess declared invariants and recovery logic, but cannot validate live service timing, payment-provider behavior, or production convergence.”

#### `senior-fulfillment-backlog-delayed-v1`

- Prompt: “After a fulfillment deployment, queue lag grows from seconds to two hours. A small set of poison messages is retried indefinitely, old and new schema versions coexist, and burst traffic continues. Diagnose, contain, recover, and evolve the consumer without losing accepted work or hiding incompatible messages.”
- Disclosed assumptions: messages have stable IDs and schema versions; consumer concurrency is configurable; a dead-letter or quarantine store is available; replay is auditable.
- Expected artifact: evidence-led diagnosis, containment steps, safe backlog recovery, schema/version posture, replay controls, and recurrence prevention.
- Accepted alternatives: version-aware consumers with poison quarantine; or staged compatibility adapters plus bounded retry and replay. Both must protect ordering/invariants where required.
- Constraint-breaking near miss: unlimited immediate retries, or dropping incompatible messages to reduce lag.
- Cross-question: “How do you raise throughput without multiplying poison-message load or violating per-entity ordering?”
- Static limitation: “Static review can inspect the recovery plan and consumer logic, but cannot validate queue throughput, deployment behavior, or production message history.”

### 5.3 Staff

#### `staff-platform-migration-initial-v1`

- Prompt: “Migrate a shared order-command platform used by six independently deployed teams without a flag-day cutover. Current teams use mixed Spring versions and inconsistent retry libraries. Define ownership, compatibility, SLOs, staged adoption, exception governance, rollback, observability, and second-order risks while teams continue feature delivery.”
- Disclosed assumptions: contracts can be versioned; teams control their deployment dates; a compatibility test environment exists; the platform team cannot force synchronized release.
- Expected artifact: migration decision, compatibility boundary, adoption stages, success/reversal criteria, governance and exception process, operating model, and risk register.
- Accepted alternatives: a thin shared protocol plus team-owned adapters; or a platform library/service with compatibility contracts. Either must avoid hidden lockstep and define escape/rollback paths.
- Constraint-breaking near miss: mandatory synchronized cutover or a central library upgrade with no mixed-version compatibility contract.
- Cross-question: “What evidence triggers rollback when platform metrics improve but two teams’ recovery time worsens?”
- Static limitation: “Static review can assess contracts, rollout, and governance, but cannot prove organization adoption, live SLOs, or migration economics.”

#### `staff-regional-audit-delayed-v1`

- Prompt: “Evolve a regional audit-event platform owned by independent teams. Records must remain in their permitted region, producers and consumers run mixed schema versions, historical poison data must remain replayable, and no flag-day migration is allowed. Define contracts, staged migration, incident ownership, exceptions, rollback, and evidence of safe adoption.”
- Disclosed assumptions: region is known at event creation; schema IDs are durable; regional replay stores exist; cross-region control metadata may contain no audit payload.
- Expected artifact: cross-team contract and ownership model, residency-safe topology, schema/replay migration, incident posture, adoption evidence, and reversal criteria.
- Accepted alternatives: regional logs with a global metadata control plane; or fully regional control/data planes with federated governance. Either must satisfy residency and replay constraints.
- Constraint-breaking near miss: copying raw audit payloads into a global recovery queue or requiring synchronized consumer upgrades.
- Cross-question: “How is a global schema rollback coordinated when one region has already replayed data under the new version?”
- Static limitation: “Static review can inspect topology and governance, but cannot verify residency enforcement, regional failure behavior, or cross-team adoption.”

### 5.4 Practice

#### `mid-spring-latency-practice-v1`

- Prompt: “A Spring endpoint stays below 120 ms p95 at low load but reaches 2.4 s p95 at 150 requests/second. Traces show requests waiting for database connections and transactions holding connections during a downstream HTTP call. Separate observations from hypotheses, give a bounded diagnostic sequence, recommend a remediation, and state how you would verify it and what it could worsen.”
- Disclosed assumptions: the trace timestamps are trustworthy; the shown database wait and downstream-call spans cover the affected requests; no infrastructure change occurred during the measurement window.
- Expected response: an observation/hypothesis split, ordered diagnostic steps, one bounded remediation, falsifying/confirming signals, and an explicit consequence.
- Hint, visible only after request: “Name the resource that queues, then identify what holds it longer as concurrency rises.”
- Accepted alternatives: move the remote call outside a shortened transaction with an explicit consistency strategy; or redesign the workflow asynchronously. Both require consequence and verification.
- Constraint-breaking near miss: only increase the connection pool with no capacity/dependency analysis.
- Adaptive target: “What happens to database load and downstream concurrency if the pool is doubled?”
- Evaluation limitation: “The supplied traces support reasoning about this captured window; they do not prove production causality or the behavior of an unobserved dependency.”

#### `senior-zero-downtime-schema-practice-v1`

- Prompt: “Add a required customer-region field to a large PostgreSQL orders table while old and new Spring instances coexist. Writes cannot stop, p99 latency may not exceed 300 ms during rollout, and rollback must remain possible until verification completes. Sequence schema and application changes, backfill, validation, observability, and rollback.”
- Disclosed assumptions: old instances ignore the new field; new instances can temporarily tolerate its absence; the database supports online validation primitives but their production cost still requires measurement.
- Expected response: a reversible ordered migration, mixed-version read/write behavior, bounded backfill, verification gates, failure handling, and rollback criteria.
- Hint, visible only after request: “Separate compatibility, population, validation, and enforcement into reversible stages.”
- Accepted alternatives: expand/backfill/validate/contract with dual-compatible reads/writes; or a shadow table/sidecar migration with an atomic final cutover. Both must preserve mixed-version compatibility.
- Constraint-breaking near miss: add a non-null column with a blocking default and deploy readers/writers simultaneously.
- Adaptive target: “What exact evidence makes it safe to enforce the constraint and remove compatibility code?”
- Evaluation limitation: “The answer can be checked for sequencing and invariants, but actual lock duration, backfill load, and p99 impact require runtime measurement.”

#### `staff-cascading-failure-practice-v1`

- Prompt: “A 20-minute downstream degradation causes retries across twelve services, triples request volume, exhausts shared database connections, and delays unrelated workloads. Define immediate containment, capacity and retry policy, ownership boundaries, observability, exception governance, and the learning loop. Teams must remain able to ship independently.”
- Disclosed assumptions: request and retry telemetry is correlated across the twelve services; ownership boundaries are known; emergency configuration changes can be rolled out independently; the shared database cannot be treated as infinite capacity.
- Expected response: an incident containment sequence, system-wide retry/capacity policy, ownership and exception model, measurable guardrails, rollback, and follow-through.
- Hint, visible only after request: “Separate per-hop retry behavior from the system-wide retry budget and overload signal.”
- Accepted alternatives: centrally governed retry budgets with local implementation; or platform-enforced admission/backpressure with explicit team exceptions. Both require ownership and rollback.
- Constraint-breaking near miss: add retries at every hop or scale the database without removing amplification.
- Adaptive target: “How do you prevent an approved exception from recreating correlated amplification six months later?”
- Evaluation limitation: “The response can expose decision and control quality, but cannot prove live capacity, organizational adoption, or correlated-failure behavior.”

### 5.5 Mock

#### `mid-order-lifecycle-mock-v1`

- Prompt: “Design and defend an order-status API and event flow. Clients retry timed-out writes, a downstream shipping service can be unavailable for 30 minutes, duplicate events occur, and operators must explain whether an order is pending, accepted, or needs repair.”
- Disclosed assumptions: PostgreSQL and a durable broker are available; one service owns the order state; no real-time global transaction exists.
- Accepted alternatives: synchronous acceptance plus outbox-driven shipping; or explicit asynchronous command acceptance. Both must define client idempotency and repair.
- Constraint-breaking near miss: report success before durable acceptance or expose only a generic failure after partial commit.
- Adaptive targets: transaction boundary, duplicate handling, observable states, and recovery ownership.

#### `senior-commerce-reliability-mock-v1`

- Prompt: “Design a checkout flow with 99.95% monthly availability, 300 ms p99 for durable order acceptance, no silent oversell, and payment/inventory dependencies that can throttle or time out. Defend consistency, retry, backpressure, repair, and observability choices.”
- Disclosed assumptions: temporary pending orders are allowed; services own separate stores; no two-phase commit; traffic can burst to five times baseline.
- Accepted alternatives: durable orchestration; or event choreography with explicit reconciliation. Both must meet the same constraints and expose residual uncertainty.
- Constraint-breaking near miss: unbounded retry or an exactly-once claim without a durable dedupe/convergence mechanism.
- Adaptive targets: overload, retry storms, data repair, monitoring, and safe evolution.

#### `staff-multiregion-evolution-mock-v1`

- Prompt: “Evolve a multi-region commerce platform while teams continue weekly delivery. One region may be unavailable for 15 minutes; order acceptance targets 99.95% availability; recovery-point objective is five minutes; some payment actions cannot be duplicated; and cross-region capacity costs must remain bounded. Define decision boundaries, data consistency, blast radius, migration, observability, and reversal criteria.”
- Disclosed assumptions: region-local durable storage exists; asynchronous cross-region replication is available; legal residency constraints are supplied per data class; no instantaneous global consensus guarantee is assumed.
- Accepted alternatives: region-affine orders with controlled failover; or globally coordinated identifiers plus region-local execution. Both must address RPO, duplicate-sensitive actions, and rollback economics.
- Constraint-breaking near miss: active-active writes with no conflict/duplicate policy, or failover that violates stated residency.
- Adaptive targets: regional failure, degraded dependencies, team ownership, migration economics, exceptions, and reversal evidence.

All scenario provenance is `decision:IDK-009:1.0/content:idk009-v1-r1`, approved by the content/assessment owner on 2026-08-13. Claim-level source references required for learner-facing factual corrections remain subject to IDK-003; lack of an approved source fails that correction closed rather than changing scenario approval.

## 6. Rubrics and qualitative outcomes

All three rubric versions use the same stable dimensions so delayed, cross-mode, and ambiguity carry-forward comparisons are deterministic. Mode-specific guidance changes the bar, not the dimension identity.

| Stable dimension | Critical | Hands-on guidance | Practice guidance | Mock guidance |
| --- | --- | --- | --- | --- |
| `factual-and-mechanical-correctness` | Yes | Artifact preserves required mechanics/invariants. | Claims and diagnostic mechanics are accurate. | Claims remain accurate across the transcript. |
| `assumptions-and-constraints` | Yes | Material assumptions are explicit and compatible. | Observations, hypotheses, assumptions, and constraints are separated. | Missing information is identified and reasoning stays within constraints. |
| `solution-and-system-reasoning` | No | Artifact is implementable, testable, and operable at the role bar. | Implementation/diagnosis is bounded and actionable. | Scope and depth meet the role bar under follow-up. |
| `trade-offs-and-consequences` | No | Alternatives and consequences connect to constraints. | A valid choice and what it worsens are explicit. | Choices remain defensible as constraints change. |
| `failures-and-recovery` | No | Failure windows, containment, recovery, and residual risk are addressed. | Failure, recovery, and prevention are addressed. | Diagnosis, containment, recovery, and prevention are coherent. |
| `verification-and-defensibility` | No | Verification and static/runtime limits are truthful. | Confirming/falsifying tests or signals are named. | Answer is structured, consistent, revisable, and evidence-led. |

The closed stored outcome vocabulary is:

| Outcome | Meaning |
| --- | --- |
| `pass` | The required fact, invariant, reasoning step, or behavior is supported. |
| `trade-off` | A non-unique choice is defensible under stated assumptions and its consequences are explicit. |
| `factual-correction` | A material claim/mechanic is false, or a required correctness/safety invariant is missing. Feedback names the exact correction. |
| `not-demonstrated` | The response supplies insufficient evidence for the dimension without making a specific false factual/mechanical claim. Feedback names what was not demonstrated. |
| `ambiguity-unresolved` | Prompt, source, runtime evidence, or evaluator uncertainty prevents a defensible judgment. Weak or terse evidence is evaluated as such, not labelled ambiguous. |

`trade-off` is permitted only for `trade-offs-and-consequences`. A positive result on every other dimension is `pass`. The two critical dimensions therefore require `pass`; `trade-off` can never satisfy factual correctness or constraint adherence. Every result has non-blank rationale and evidence references.

## 7. Valid alternatives and corrections

- Rubrics define invariants and observable consequences, not one canonical architecture.
- Facts and version-dependent mechanics require claim-appropriate support. Choices are evaluated against disclosed assumptions, prompt constraints, and consequences.
- An alternative cannot receive `factual-correction` solely because it differs from an example. It receives that outcome when it violates a stated constraint or material invariant.
- The accepted alternatives and near misses in section 5 are normative curated cases. Automated regression may add detail but may not narrow the accepted set to one design.
- A static limitation is recorded as a limitation, not converted into learner fault.

## 8. Ambiguity and re-evaluation

### 8.1 Persisted contract

Each assessment persists `scenario_id`, `scenario_content_revision`, `assessment_phase` (`initial`, `delayed`, `practice`, or `mock`), and `paired_initial_assessment_id`. The pair is required exactly when phase is `delayed` and is null for every other phase. It references an earlier eligible submitted initial assessment with the same owner, goal, exact mapped topic/capability, and the registry-declared paired initial `scenario_id`. Service and database constraints reject every mismatch. Each unresolved dimension has one immutable ambiguity record:

| Field | Rule |
| --- | --- |
| `policy_version` | Exactly `assessment-ambiguity-v1`. |
| `cause` | One of `prompt`, `source`, `runtime-evidence`, `evaluator`. |
| `rubric_dimension_result_id` | The current `ambiguity-unresolved` result; unique. |
| `competing_interpretations` | At least two non-blank alternatives. |
| `resolution_needed` | Non-blank clarification or evidence needed. |
| `carried_from_dimension_result_id` | Nullable reference to the pre-attempt effective clear result for the same owner, goal, topic/capability cell, and stable dimension. |

Before persisting the attempt, the service resolves the effective clear result for every ambiguous dimension using section 9.2 and records its ID, or null when none exists. The referenced result is immutable. Its original assessment timestamp remains its ordering timestamp; ambiguity does not make old evidence newer.

### 8.2 Neutrality rules

1. A clear dimension in a mixed assessment contributes normally.
2. An ambiguous dimension contributes its recorded carried result. A null carry contributes nothing.
3. An all-ambiguous assessment therefore creates no assessed-dimension contribution and leaves the exact pre-attempt cell classification unchanged, including correction-only and transfer-only baselines. It cannot create coverage or move any classification.
4. These rules apply to every assessment, not only re-evaluation.
5. An ambiguity successor may exclude its predecessor as an active assessment while its explicit carry references the predecessor's immutable dimension result. This is lineage, not double-counting.
6. A later clear result supersedes an older carried result under the ordering rule. History remains inspectable.
7. The learner may dispute any assessment and request append-only re-evaluation.

## 9. `derived-state-v1`

### 9.1 Eligible inputs and cells

The approved graph and goal target capability define required `(topic stable ID, capability)` cells. Each `topic_binding_key` is mapped to an approved topic stable ID before activation.

Eligible assessment input is immutable submitted evidence with a schema-valid active assessment under an approved scenario/rubric revision. Fixture/unapproved content, tombstoned/rejected evidence, raw imports, page views, elapsed time, scheduling records, generated text, and Run without Submit are excluded. Capability matching is exact as specified in section 4.

### 9.2 Effective dimension outcomes

For each cell and stable dimension:

1. Start with clear results from active assessment tips plus clear results reached by an active ambiguity record's `carried_from_dimension_result_id`.
2. Exclude an ambiguity result itself. A carried result retains its original assessment timestamp and ID.
3. Select the newest clear result by `(assessment.created_at, assessment.id, dimension_result.id)` lexicographically. Thus a later clear repair can supersede an older factual correction; an ambiguity cannot change precedence.
4. Keep every older contradiction in supporting references and uncertainty, but do not average it into a hidden score.

The resulting cell proficiency is:

| Effective result set | Cell classification |
| --- | --- |
| No clear result | `new`, unless a correction/confirmation/transfer rule below applies. |
| Either critical dimension is `factual-correction` or `not-demonstrated` | `unverified`. This rule takes precedence over every row below. |
| Otherwise, clear results exist but none is positive | `unverified`. |
| Otherwise, some required dimensions are missing, or any non-critical dimension is `factual-correction` or `not-demonstrated` | `partial`. |
| Otherwise, all six required dimensions are present; both critical dimensions and all non-trade-off dimensions are `pass`; trade-off dimension is `pass` or `trade-off` | `likely_known`. |

This ordering makes the function total when independent assessments conflict. “Failed attempt” elsewhere in the plan means a schema-valid assessed attempt with factual corrections; a job/runtime failure creates no assessment and no coverage.

### 9.3 Learner corrections and transfers

The latest unsuperseded learner correction has two explicit effects:

- The topic's displayed LearningState is exactly the learner-selected value until another correction supersedes it.
- The same value replaces the cell proficiency input. It is marked learner-provided, does not create an evidence reference, and does not create delayed retention evidence.

This preserves the correction without claiming it was assessed. A correction to `new` can lower readiness; a correction to `likely_known` can raise proficiency, but retention remains constrained by delayed evidence. A confirmed transfer represents the cell for coverage and supplies at most its conservative transferred classification for proficiency; an unconfirmed transfer supplies `unverified`. Transfers never establish retention.

### 9.4 Goal dimensions

All required cells have equal influence; version 1 has no hidden numeric weights. Goal aggregation is the conservative minimum under `new < unverified < partial < likely_known`.

| Dimension | Deterministic rule |
| --- | --- |
| Coverage | `new` when no cell has a clear assessed result, correction/confirmation, or transfer. `unverified` when represented cells contain only correction/transfer inputs and no clear assessment. `partial` when at least one but not every required cell has a clear assessed result. `likely_known` when every required cell has at least one clear assessed result. Factual-correction and not-demonstrated are still observed assessments; ambiguity-only is not. |
| Proficiency | Per-cell rule from sections 9.2–9.3, then conservative minimum across every required cell. Missing cells are `new`. |
| Retention | Compute per required cell, then take the conservative minimum. With no input the cell is `new`. Correction-only, confirmation-only, transfer-only, or initial/Practice/Mock assessed input without a qualifying delayed result is `unverified`. Among delayed results that satisfy the paired scenario/capability rule and are current, use the effective-dimension algorithm in section 9.2: a critical correction/not-demonstrated or no positive result yields `unverified`, a non-critical correction/not-demonstrated or missing dimension yields `partial`, and all-positive yields `likely_known`. An ambiguity-only delayed attempt preserves the prior qualifying delayed result and otherwise preserves the pre-attempt retention classification. |
| Readiness | Conservative minimum of coverage, proficiency, and retention. Label it “evidence readiness for this goal,” never interview/job probability. |

A delayed result becomes eligible on the seventh UTC date after its paired initial submission and remains current through `date(delayed.submitted_at) + 90 days`, inclusive. On the next UTC date it becomes `unverified` until renewed. The memo input hash uses `now[:10]`, so all rule-driven time changes occur only when that date bucket changes.

Every required cell deliberately needs its own approved initial/delayed pair before it can reach `likely_known` retention. The twelve records in this decision are the representative approved seed, not an assertion that every future canonical goal cell already has content. A goal with a required cell lacking an approved pair remains at most `unverified`, surfaces “no approved delayed assessment,” and cannot be presented as fully ready. Additional pairs require their own recorded content approval and versioned registry entry; they do not inherit approval by resemblance.

Every dimension returns its definition, supporting evidence references, uncertainty, `effective_now`, and `rule_version`. Detailed/simple remains presentation-only.

## 10. `review-schedule-v1`

Review is optional and non-blocking. Its interval ladder is 1, 3, 7, 14, 30, and 60 days. Every generated item stores its current rung before it can be attempted.

- No item is generated from `new` alone. An all-correction, all-not-demonstrated, or critical-negative result starts at 1 day. A mixed/partial result starts at 3 days. A clear `likely_known` result starts at 7 days. Material correction or critical not-demonstrated takes precedence over every other outcome.
- An assessed review result of `unverified` sets 1 day; `partial` sets 3 days. For `likely_known`, low confidence stays on the stored rung, medium or omitted confidence advances one rung, and high confidence advances two. The ladder caps at 60 days.
- A new item stores an immutable unique `source_assessment_id`; `due_at = source_assessment.created_at + initial_interval` in UTC. Reprocessing the same source is idempotent and never updates or duplicates the item. After an attempt, `due_at = attempted_at + selected_interval`.
- The second and later attempts require a non-blank changed-context reference and hash when varied context is enabled. Its hash must differ from every earlier attempt for that item; context reuse is rejected.
- Preference cadence uses `preferences.updated_at` as a UTC-date anchor. Offer slots are offsets `{0}` modulo 7 for once-weekly, `{0,3}` for twice-weekly, and `{0,2,4}` for three-times-weekly. Compare UTC calendar dates: a due item waits for the first allowed `offer_date >= date(due_at)`; it remains due and never blocks another route.
- On an offer slot, resolve each item's subject from its approved topic. A missing subject or topic mapping fails the item closed as `generation-failed`. Sort subject keys lexicographically; within each subject sort by `(due_at, review_item.id)`; emit the first item from every subject, then the second, until the session budget is full.
- The session budget is `max(1, floor(duration_minutes / 5))`. Changing preferences resets only the cadence anchor and future offer selection; it never rewrites attempts, evidence, or progress.
- Dismiss, disable, generation failure, or an empty queue yields exactly zero progress delta.

Review attempts become assessment evidence only when separately submitted through an approved scenario/rubric assessment path. Scheduling records alone never count.

## 11. Required implementation and review evidence

Approval is not production activation. Before an approved version is presented as authoritative, the owning tickets must demonstrate:

- IDK-204: load and version-gate the three immutable rubric manifests; persist scenario/revision/phase/pair fields, topic mappings, the five-outcome vocabulary, and normalized ambiguity records; enforce approved scenario/rubric/mapping/pair matching; reject fixture/unapproved content in authoritative flows; prove valid alternatives, exact dimension sets, not-demonstrated behavior, mixed ambiguity, all-ambiguity zero delta over assessed/correction/transfer baselines, carried-result scope, and append-only re-evaluation.
- IDK-205: implement `derived-state-v1`; prove deterministic ordering, correction and transfer semantics, conflicting assessments, all classification branches, per-cell retention, seventh/90th/91st UTC-date boundaries, memo rollover, and non-prediction disclosure.
- IDK-206: implement `review-schedule-v1`; prove every initial/result/confidence transition, material-correction precedence, cadence slots, deterministic interleaving, session budget, changed context, and dismiss/disable zero delta.
- IDK-302 loads the three Practice records, IDK-303 loads the three Mock records, and IDK-405 loads the three initial plus three delayed hands-on records. They consume IDK-204's rubric registry and exact topic mappings and prove role/mode/capability/topic matching, Practice hint timing, Mock terminal-only feedback, static/evaluation limitation specificity, and no fixture label.
- IDK-503: manually review all twelve shipped records for level realism, valid alternatives, credible constraints, factual-support posture, no company-specific claim, and no hiring/readiness guarantee.

Until this evidence passes, existing fixture content stays non-production and progress stays explicitly non-authoritative. Approval must not relabel a fixture as reviewed content. Authoritative learner-facing factual corrections additionally remain blocked until IDK-003's approved source policy and claim-level citation posture are implemented; synthetic-source mechanism tests may proceed earlier.

## 12. Change control and approval record

- Assessments retain scenario ID/content revision, rubric version, and ambiguity-policy/lineage references.
- Progress outputs/memos retain derived-rule version; changing eligibility, classification, timing, aggregation, or ambiguity neutrality creates a new version.
- Review items/attempts retain schedule version; changing interval, cadence, ordering, or session-budget behavior creates a new version.
- Existing records are never rewritten to a new meaning. New versions require a content/assessment approval and deterministic regressions before activation.

| Approver | Role | Date | Decision | Version | Evidence reference |
| --- | --- | --- | --- | --- | --- |
| Content/assessment owner | Content/assessment owner | 2026-08-13 | Approved without changes | 1.0 | Sections 2–11 and the project implementation request |

Decision values: `approved`, `changes requested`. This approval resolves IDK-009. IDK-004 separately approves learner-facing role copy; neither decision waives IDK-003's source policy or any implementation/manual-review evidence in section 11.
