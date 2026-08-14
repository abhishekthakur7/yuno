# IDK-001 — MVP curriculum spine

Status: approved

Decision version: `1.0`

Policy identifier: `mvp-curriculum-spine-v1`

Approval date: 2026-08-14

Approver role: content owner / designated editorial approver, per PRD §13

This document records the approved answer to PRD §14 Q1 / IMPLEMENTATION_SPEC §12.3 Q1: the MVP canonical topic list with stable IDs, the prerequisite/relationship graph, curriculum scope tags demonstrating the CUR-01 boundary, and the DSA-topic-to-scenario bindings CUR-02 requires — specific enough for IDK-102's offline publisher to load as a manifest, and for IDK-002's checklist to be run against item by item. The content owner approved it on 2026-08-14 (§19). Approval settles which topics form the MVP spine. It does not claim any content is authored (IDK-201), any source is registered (IDK-003 §12), or that any graph version has been published — §14's implementation conditions are unchanged by approval, and §15's gaps remain open.

## 1. Decision and boundary

The proposed spine is 53 topics across all six subjects `ALLOWED_SUBJECTS` permits (`java`, `spring_boot`, `aws`, `system_design`, `rdb`, `dsa`), connected by 74 relations (67 `prerequisite`, 7 `scenario`, 0 `related`). Every topic/relation maps onto exactly the three tables IMPLEMENTATION_SPEC §4.3 fixes and no others:

| Table | What this document supplies |
| --- | --- |
| `topic_identities` | §7's `stable_id`/`stable_slug` pairs (identical strings — §6). |
| `topics` | §7's full row for all 53 topics: title, subject, scope_tags, level_tag, target_capability, recommended_layer, checkpoint_start/end. |
| `topic_relations` | §8's 74 rows: from/to stable ID, type, rationale. |

No column beyond IMPLEMENTATION_SPEC §4.3's list is used. No `content_revisions` rows are proposed — authoring Markdown per layer is IDK-201's job, explicitly Out of scope for IDK-001 per IMPLEMENTATION_TICKETS.md. This document reserves the checkpoint numbering and topic/relation identities IDK-201 authors into; it does not author content itself.

Teachability is bounded by IDK-003 §4's registry: IETF RFCs, PostgreSQL docs, Spring Framework/Boot docs at Tier A (snapshot + quotation); Oracle Java SE/JLS, OpenJDK JEPs, AWS docs at Tier B (link-only). This spine leans on that boundary directly:

| Subject | Primary approved source | Tier | Consequence |
| --- | --- | --- | --- |
| `java` | Oracle Java SE Docs / JLS; OpenJDK JEPs | B | No quotation beyond a title/heading; original prose, linked, never reproduced excerpt. |
| `spring_boot` | Spring Framework/Boot Reference Docs | A | Quotation up to the 400-char excerpt cap available. |
| `aws` | AWS Documentation | B | Same link-only constraint as `java`. |
| `system_design` | IETF RFCs where standards-level; otherwise routine self-contained reasoning (spec §6.5) | A / uncited | Most claims are trade-off reasoning needing no citation; standards-level claims (e.g. HTTP method idempotence) cite RFC 9110. |
| `rdb` | PostgreSQL Documentation | A | Full quotation available; no Tier B fallback needed. |
| `dsa` | No dedicated row; complexity/structure claims are routine (spec §6.5); a concrete Java API claim cites Oracle Java SE Docs | B (partial) | No `dsa` topic depends on an unapproved/forbidden source. |

No topic in §7 requires Stack Overflow, Wikipedia, a company blog, a paid course, or any other IDK-003 §5 forbidden/unapproved source.

## 2. What is already fixed and not reopened

- **The schema.** `topic_identities`/`topics`/`topic_relations` (spec §4.3), enforced by `canonical/validation.py`: `ALLOWED_SUBJECTS` is exactly the six named above; `go`/`golang`/`go_aws` may not appear as `subject` or in `scope_tags`; every `dsa` topic needs ≥1 `SCENARIO` relation; relations form a DAG except `RELATED`. Unchanged here — this is content built to pass that validator unmodified.
- **IDK-002's review criteria** (approved 2026-08-14): the seven-item checklist, sampling rules, `basis_ref` contract. This document is written to be reviewable under it (§13); it does not relax it.
- **IDK-003's source registry** (approved 2026-08-14), bound to directly in §1.
- **IDK-004's vocabulary** (approved 2026-08-13): three levels (`Mid-level`, `Senior`, `Staff`), six capabilities (`know`, `understand`, `choose`, `implement`, `diagnose`, `defend`). §11 uses these exactly.
- **IDK-009's scenario registry** (approved 2026-08-13): twelve scenarios, eight `topic_binding_key` values. §9's DSA bindings and §11's levels are built consistent with it, not duplicating it. IDK-009 §4 already notes IDK-001 has not approved stable IDs and that IDK-204 later maps each `topic_binding_key` to one; this document is the source of the IDs that mapping will target.
- **IDK-008's no-connector posture** (approved 2026-08-14). §12 confirms every `rdb` topic stays inside it.
- **No in-app authoring/publication (D1).** This spine is consumed only by the offline `scripts/publish_canonical.py` tool.

## 3. What this unblocks, and what still gates publication

Approval (§19) settles the curriculum question, so IDK-001 no longer blocks anything as a *decision*. These remain gated on implementation, not on this decision:

- IDK-102's production publish run: its "publish the real v1" criterion needs §14's manifest, authored content, and a recorded `basis_ref`, none of which exist.
- IDK-201's authored topic layers, which now have a concrete topic list and checkpoint range to author into.
- Phase 1/2 content exit, per IMPLEMENTATION_TICKETS.md's "Phase exit semantics" — approval is the decision half; the applied-to-shipped-artifacts half remains.

Does not gate: IDK-102's own fixture-based mechanism tests, which run against `server/tests/fixtures/canonical/data/v1_approved.json` and siblings — synthetic, non-production, independent of this document.

What changed: the blocking condition is no longer a missing or unreviewed decision — it is unbuilt implementation.

## 4. Evidence checklist: where each item is now addressed

Each item the original framing draft required is now supplied, and was reviewed under IDK-002's checklist (§13) before approval.

| Original checklist item | Addressed by |
| --- | --- |
| Candidate topic list with stable IDs | §7 (53 topics, every `Topic` column) |
| Prerequisite/relationship graph draft | §8 (74 relations) |
| Curriculum scope tags demonstrating the boundary (CUR-01) | §7's `scope_tags` column plus §12 |
| DSA-topic-to-scenario relation for every DSA node (CUR-02) | §9 (5 topics, 7 relations, justified) |
| Written confirmation Go+AWS is entirely absent | §12; no token in §7/§8/§9 matches `go`/`golang`/`go_aws` |

## 5. Topic count and review-cost commitment

**53 topics** — a deliberate size that directly commits the content owner to a review cost under IDK-002 §5's exhaustive-review default: 53/53 curriculum-boundary reviews (§3.1), 5/5 DSA-scenario reviews (§3.2, small by CUR-02's own design), 74/74 relation re-confirmations (§3.3) plus 0 reused-`stable_id` continuity reviews (first version — §6 fixes the rule for v2), and up to 53×7=371 layer-adjacency pairs (§3.5) *if* every topic eventually authors all eight layers — far fewer at launch, since `recommended_layer` names only the anchor layer and this document authors no content (§1).

Why 53:

- **Too small is not credible.** A spine that skipped transactions, concurrency, or partial-failure reasoning fails PRD §7/§8 before a learner opens it. 53 is the minimum letting every one of IDK-009's eight `topic_binding_key` values map to a non-vacuous canonical topic (§9).
- **Too large breaks exhaustive review.** IDK-002 §5 requires 100% topic review for curriculum-boundary and layer-reversal, no sampling exception, and §6 flags that MVP's single-owner design usually makes `creator_owner_id` and `approver_owner_id` the same person — this is one person's exhaustive read, not a team's. 53 keeps that tractable within one publish cycle; a spine 3–4x larger (200+ topics, closer to the "comprehensive coverage" claim §12 forbids) would make solo exhaustive review implausible without silently sampling (forbidden by §5).
- **The split is uneven by design.** `spring_boot` (13) and `java` (11) are largest — CUR-01's named core. `aws` (10) and `system_design` (8) are next — CUR-01's required connected breadth. `rdb` (6) stays smaller — IDK-008 already bounds it to static content, no connector. `dsa` (5) is smallest — CUR-02's explicit "only where scenario-relevant."

## 6. Stable-ID naming and retirement rule

**Naming rule.** `stable_id` = `{subject-prefix}-{concept}`: `subject-prefix` is the kebab-case `subject` value (`java`, `spring-boot`, `aws`, `system-design`, `rdb`, `dsa`), fixed for the ID's life even across a `level_tag`/`target_capability`/`recommended_layer` change (content-revision facts, not identity). `concept` is 2–5 kebab-case words naming durable subject matter — never a level, layer, or capability. Uniqueness is the `topic_identities.stable_id` PK; an author checks the full active-plus-retired list before minting, so a retired ID is never reissued. `stable_slug` equals `stable_id` in v1 — both already kebab-case/URL-safe, and a second string with no v1 use case would violate AGENTS.md's "avoid speculative abstractions"; the schema keeps them separate so a later version *can* diverge them without touching `stable_id`. Applied throughout §7, e.g. `spring-boot-idempotent-request-handling`.

**Reuse vs. retirement.** *Reused*: the identical string appears again in version N+1 denoting the same concept — the default outcome; `title`/`scope_tags`/`level_tag`/`recommended_layer` may be edited, but the concept must not materially change (IDK-002 §3.3's continuity check) — a concept change means minting a new ID, not editing this one's meaning under a preserved string. *Retired*: `topic_identities.retired_at` is set; the identity row persists (audit, read-only evidence references) but the topic drops from the current `topics` table. Eligible only when (a) a v2+ diff review (IDK-002 §3.7) explicitly proposes removal as its own reviewed diff item, and (b) the removal's consequence for any goal carrying evidence/overlay state is reviewed under D9's "archived local topic" path. A retired ID is never reused for a different concept. No ID in this v1 spine is a candidate for either event: v1 has no prior version and nothing is yet approved to retire.

## 7. The proposed topic table

53 topics, every `Topic` column, grouped by subject. `scope_tags` lists the tuple's members. Checkpoint numbering follows the rule in §10.

### 7.1 `java` (11)

| stable_id | title | subject | scope_tags | level_tag | target_capability | recommended_layer | cp_start | cp_end |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `java-language-fundamentals` | Java language fundamentals | java | mvp-spine-v1, cur-01-core, source-tier-b | Mid-level | know | Essential | 0 | 1 |
| `java-oop-and-design-idioms` | OOP design idioms in Java | java | mvp-spine-v1, cur-01-core, source-tier-b | Mid-level | understand | Essential | 1 | 2 |
| `java-collections-core` | Core Java collections | java | mvp-spine-v1, cur-01-core, source-tier-b | Mid-level | understand | Essential | 2 | 3 |
| `java-generics-and-type-system` | Generics and the Java type system | java | mvp-spine-v1, cur-01-core, source-tier-b | Mid-level | understand | Implementation | 3 | 4 |
| `java-exceptions-and-resource-management` | Exceptions and resource management | java | mvp-spine-v1, cur-01-core, source-tier-b | Mid-level | implement | Implementation | 4 | 5 |
| `java-streams-and-functional-style` | Streams and functional-style Java | java | mvp-spine-v1, cur-01-core, source-tier-b | Mid-level | implement | Implementation | 5 | 6 |
| `java-concurrency-fundamentals` | Java concurrency fundamentals | java | mvp-spine-v1, cur-01-core, source-tier-b | Mid-level | understand | Internals | 6 | 7 |
| `java-concurrent-collections-and-executors` | Concurrent collections and executors | java | mvp-spine-v1, cur-01-core, source-tier-b | Senior | implement | Implementation | 7 | 8 |
| `java-memory-model-and-garbage-collection` | Java memory model and garbage collection | java | mvp-spine-v1, cur-01-core, source-tier-b | Senior | understand | Internals | 8 | 9 |
| `java-jvm-performance-diagnostics` | JVM performance diagnostics | java | mvp-spine-v1, cur-01-core, source-tier-b | Staff | diagnose | Production | 9 | 10 |
| `java-testing-with-junit` | Testing Java services with JUnit | java | mvp-spine-v1, cur-01-core, source-tier-b | Mid-level | implement | Implementation | 10 | 11 |

### 7.2 `rdb` (6)

| stable_id | title | subject | scope_tags | level_tag | target_capability | recommended_layer | cp_start | cp_end |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rdb-relational-modeling-and-normalization` | Relational modeling and normalization | rdb | mvp-spine-v1, cur-01-connected, source-tier-a | Mid-level | know | Essential | 11 | 12 |
| `rdb-transactions-and-isolation-levels` | Transactions and isolation levels | rdb | mvp-spine-v1, cur-01-connected, source-tier-a | Mid-level | understand | Internals | 12 | 13 |
| `rdb-indexing-and-query-planning` | Indexing and query planning | rdb | mvp-spine-v1, cur-01-connected, source-tier-a | Senior | diagnose | Production | 13 | 14 |
| `rdb-locking-and-concurrency-control` | Locking and concurrency control | rdb | mvp-spine-v1, cur-01-connected, source-tier-a | Senior | diagnose | Internals | 14 | 15 |
| `rdb-schema-evolution-and-migrations` | Schema evolution and migrations | rdb | mvp-spine-v1, cur-01-connected, source-tier-a | Senior | implement | Production | 15 | 16 |
| `rdb-replication-and-availability` | Replication and availability | rdb | mvp-spine-v1, cur-01-connected, source-tier-a | Staff | choose | Alternatives | 16 | 17 |

### 7.3 `spring_boot` (13)

| stable_id | title | subject | scope_tags | level_tag | target_capability | recommended_layer | cp_start | cp_end |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `spring-boot-core-container-and-di` | Core container and dependency injection | spring_boot | mvp-spine-v1, cur-01-core, source-tier-a | Mid-level | understand | Essential | 17 | 18 |
| `spring-boot-configuration-and-profiles` | Configuration and profiles | spring_boot | mvp-spine-v1, cur-01-core, source-tier-a | Mid-level | implement | Implementation | 18 | 19 |
| `spring-boot-web-mvc-and-rest` | Web MVC and REST | spring_boot | mvp-spine-v1, cur-01-core, source-tier-a | Mid-level | implement | Implementation | 19 | 20 |
| `spring-boot-validation-and-error-handling` | Validation and error handling | spring_boot | mvp-spine-v1, cur-01-core, source-tier-a | Mid-level | implement | Implementation | 20 | 21 |
| `spring-boot-data-jpa-fundamentals` | Spring Data JPA fundamentals | spring_boot | mvp-spine-v1, cur-01-core, source-tier-a | Mid-level | implement | Implementation | 21 | 22 |
| `spring-boot-transactions-and-consistency` | Transaction management and consistency | spring_boot | mvp-spine-v1, cur-01-core, source-tier-a | Senior | implement | Internals | 22 | 23 |
| `spring-boot-connection-pooling-and-datasource-tuning` | Connection pooling and datasource tuning | spring_boot | mvp-spine-v1, cur-01-core, source-tier-a | Senior | diagnose | Production | 23 | 24 |
| `spring-boot-idempotent-request-handling` | Idempotent request and event handling | spring_boot | mvp-spine-v1, cur-01-core, source-tier-a | Mid-level | implement | Implementation | 24 | 26 |
| `spring-boot-security-fundamentals` | Spring Security fundamentals | spring_boot | mvp-spine-v1, cur-01-core, source-tier-a | Mid-level | implement | Implementation | 26 | 27 |
| `spring-boot-observability-and-actuator` | Observability with Actuator | spring_boot | mvp-spine-v1, cur-01-core, source-tier-a | Senior | diagnose | Production | 27 | 28 |
| `spring-boot-resilience-patterns` | Resilience patterns | spring_boot | mvp-spine-v1, cur-01-core, source-tier-a | Senior | choose | Alternatives | 28 | 29 |
| `spring-boot-async-and-scheduling` | Async execution and scheduling | spring_boot | mvp-spine-v1, cur-01-core, source-tier-a | Senior | implement | Implementation | 29 | 30 |
| `spring-boot-testing-strategy` | Spring Boot testing strategy | spring_boot | mvp-spine-v1, cur-01-core, source-tier-a | Mid-level | implement | Implementation | 30 | 31 |

### 7.4 `system_design` (8)

| stable_id | title | subject | scope_tags | level_tag | target_capability | recommended_layer | cp_start | cp_end |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `system-design-http-api-contracts` | HTTP API contracts | system_design | mvp-spine-v1, cur-01-connected, source-tier-a | Mid-level | understand | Essential | 31 | 32 |
| `system-design-caching-strategies` | Caching strategies | system_design | mvp-spine-v1, cur-01-connected, source-tier-a | Senior | choose | Alternatives | 32 | 33 |
| `system-design-load-balancing-and-scaling` | Load balancing and horizontal scaling | system_design | mvp-spine-v1, cur-01-connected, source-tier-a | Senior | choose | Alternatives | 33 | 34 |
| `system-design-partial-failure-and-timeouts` | Partial failure and timeouts | system_design | mvp-spine-v1, cur-01-connected, source-tier-a | Senior | diagnose | Failures | 34 | 35 |
| `system-design-message-delivery-semantics` | Message delivery semantics | system_design | mvp-spine-v1, cur-01-connected, source-tier-a | Senior | defend | Interview | 35 | 37 |
| `system-design-rate-limiting-and-backpressure` | Rate limiting and backpressure | system_design | mvp-spine-v1, cur-01-connected, source-tier-a | Staff | choose | Alternatives | 37 | 38 |
| `system-design-multi-service-data-consistency` | Multi-service data consistency | system_design | mvp-spine-v1, cur-01-connected, source-tier-a | Staff | defend | Interview | 38 | 39 |
| `system-design-migration-and-zero-downtime-evolution` | Zero-downtime platform migration | system_design | mvp-spine-v1, cur-01-connected, source-tier-a | Staff | defend | Interview | 39 | 41 |

### 7.5 `aws` (10)

| stable_id | title | subject | scope_tags | level_tag | target_capability | recommended_layer | cp_start | cp_end |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `aws-core-compute-and-networking-model` | Core compute and networking model | aws | mvp-spine-v1, cur-01-core, source-tier-b | Mid-level | know | Essential | 41 | 42 |
| `aws-iam-fundamentals` | IAM fundamentals | aws | mvp-spine-v1, cur-01-core, source-tier-b | Mid-level | understand | Essential | 42 | 43 |
| `aws-vpc-and-network-isolation` | VPC and network isolation | aws | mvp-spine-v1, cur-01-core, source-tier-b | Senior | understand | Internals | 43 | 44 |
| `aws-s3-storage-model` | S3 storage model | aws | mvp-spine-v1, cur-01-core, source-tier-b | Mid-level | understand | Essential | 44 | 45 |
| `aws-rds-managed-postgres` | RDS for PostgreSQL | aws | mvp-spine-v1, cur-01-core, source-tier-b | Senior | choose | Alternatives | 45 | 46 |
| `aws-elastic-load-balancing` | Elastic Load Balancing | aws | mvp-spine-v1, cur-01-core, source-tier-b | Senior | choose | Alternatives | 46 | 47 |
| `aws-autoscaling-and-capacity` | Auto Scaling and capacity planning | aws | mvp-spine-v1, cur-01-core, source-tier-b | Senior | choose | Alternatives | 47 | 48 |
| `aws-deployment-and-rollout-patterns` | Deployment and rollout patterns | aws | mvp-spine-v1, cur-01-core, source-tier-b | Staff | choose | Alternatives | 48 | 49 |
| `aws-observability-and-cost-guardrails` | Observability and cost guardrails | aws | mvp-spine-v1, cur-01-core, source-tier-b | Staff | diagnose | Production | 49 | 50 |
| `aws-identity-least-privilege-for-services` | Least-privilege service identity | aws | mvp-spine-v1, cur-01-core, source-tier-b | Senior | implement | Implementation | 50 | 51 |

### 7.6 `dsa` (5)

Every row carries ≥1 `SCENARIO` relation — see §9 for the binding and justification.

| stable_id | title | subject | scope_tags | level_tag | target_capability | recommended_layer | cp_start | cp_end |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `dsa-hash-based-lookup-and-idempotency-keys` | Hash-based lookup for idempotency keys | dsa | mvp-spine-v1, cur-02-dsa | Mid-level | implement | Essential | 51 | 52 |
| `dsa-priority-queues-and-heaps` | Priority queues and heaps | dsa | mvp-spine-v1, cur-02-dsa | Staff | choose | Alternatives | 52 | 53 |
| `dsa-graphs-and-topological-ordering` | Graphs and topological ordering | dsa | mvp-spine-v1, cur-02-dsa | Staff | choose | Alternatives | 53 | 54 |
| `dsa-lru-and-bounded-caches` | LRU and bounded caches | dsa | mvp-spine-v1, cur-02-dsa | Mid-level | implement | Implementation | 54 | 55 |
| `dsa-consistent-hashing-and-partitioning` | Consistent hashing and partitioning | dsa | mvp-spine-v1, cur-02-dsa | Staff | choose | Alternatives | 55 | 56 |

## 8. The prerequisite and relationship graph

74 relations: 67 `prerequisite`, 7 `scenario` (§9), 0 `related`. Every `from`/`to` resolves to a §7 topic (no dangling reference); every `(from, to, type)` tuple is unique; the combined `prerequisite`+`scenario` graph (the set `_validate_relation_cycles` checks together, since only `RELATED` is configured to cycle) is acyclic — verified by hand against the same three-color DFS algorithm before this document was finalized. The approver's own DAG re-confirmation (IDK-002 §3.3) must still run the real validator against the published manifest; this is an internal-consistency claim, not a substitute.

### 8.1 `java`-internal (12)

| from | to | type | rationale |
| --- | --- | --- | --- |
| `java-language-fundamentals` | `java-oop-and-design-idioms` | prerequisite | OOP idioms build on language/control-flow basics. |
| `java-language-fundamentals` | `java-collections-core` | prerequisite | Collections usage assumes those basics. |
| `java-collections-core` | `java-generics-and-type-system` | prerequisite | Generic collection APIs motivate bounded types/wildcards. |
| `java-language-fundamentals` | `java-exceptions-and-resource-management` | prerequisite | Exception syntax builds on control-flow basics. |
| `java-collections-core` | `java-streams-and-functional-style` | prerequisite | Streams operate over the collections introduced first. |
| `java-generics-and-type-system` | `java-streams-and-functional-style` | prerequisite | Stream/Collector signatures need that type-system vocabulary. |
| `java-language-fundamentals` | `java-concurrency-fundamentals` | prerequisite | Threading extends the language's execution model. |
| `java-concurrency-fundamentals` | `java-concurrent-collections-and-executors` | prerequisite | Executors are the applied form of concurrency fundamentals. |
| `java-collections-core` | `java-concurrent-collections-and-executors` | prerequisite | Concurrent collections replace the sequential ones first. |
| `java-concurrency-fundamentals` | `java-memory-model-and-garbage-collection` | prerequisite | Happens-before is the formal basis for synchronization. |
| `java-memory-model-and-garbage-collection` | `java-jvm-performance-diagnostics` | prerequisite | Diagnosing GC/heap needs the memory model first. |
| `java-exceptions-and-resource-management` | `java-testing-with-junit` | prerequisite | Testing cleanup/exception paths needs that vocabulary. |

### 8.2 `rdb`-internal (6)

| from | to | type | rationale |
| --- | --- | --- | --- |
| `rdb-relational-modeling-and-normalization` | `rdb-transactions-and-isolation-levels` | prerequisite | Isolation anomalies are defined against the modeled schema. |
| `rdb-transactions-and-isolation-levels` | `rdb-indexing-and-query-planning` | prerequisite | Reading a plan needs the transaction boundary first. |
| `rdb-transactions-and-isolation-levels` | `rdb-locking-and-concurrency-control` | prerequisite | Locking enforces the isolation guarantees introduced first. |
| `rdb-indexing-and-query-planning` | `rdb-schema-evolution-and-migrations` | prerequisite | Safe migration needs plan-aware online-change knowledge. |
| `rdb-locking-and-concurrency-control` | `rdb-schema-evolution-and-migrations` | prerequisite | Zero-downtime migration needs lock-behavior knowledge. |
| `rdb-schema-evolution-and-migrations` | `rdb-replication-and-availability` | prerequisite | Replica topology changes build on migration sequencing. |

### 8.3 `spring_boot` (19)

| from | to | type | rationale |
| --- | --- | --- | --- |
| `java-oop-and-design-idioms` | `spring-boot-core-container-and-di` | prerequisite | Spring's DI model wraps the OOP idioms first. |
| `spring-boot-core-container-and-di` | `spring-boot-configuration-and-profiles` | prerequisite | Config is read into the DI container first. |
| `spring-boot-core-container-and-di` | `spring-boot-web-mvc-and-rest` | prerequisite | Controllers are beans wired through that container. |
| `spring-boot-web-mvc-and-rest` | `spring-boot-validation-and-error-handling` | prerequisite | Validation attaches to the request path MVC defines. |
| `spring-boot-core-container-and-di` | `spring-boot-data-jpa-fundamentals` | prerequisite | Repositories are beans in the same container. |
| `rdb-relational-modeling-and-normalization` | `spring-boot-data-jpa-fundamentals` | prerequisite | JPA mapping applies relational modeling directly. |
| `spring-boot-data-jpa-fundamentals` | `spring-boot-transactions-and-consistency` | prerequisite | Transactions wrap the repository operations first. |
| `rdb-transactions-and-isolation-levels` | `spring-boot-transactions-and-consistency` | prerequisite | `@Transactional` maps the relational isolation model. |
| `spring-boot-transactions-and-consistency` | `spring-boot-connection-pooling-and-datasource-tuning` | prerequisite | Pool sizing is a production concern on those tx boundaries. |
| `spring-boot-transactions-and-consistency` | `spring-boot-idempotent-request-handling` | prerequisite | Idempotent handling composes a check with that tx boundary. |
| `spring-boot-validation-and-error-handling` | `spring-boot-idempotent-request-handling` | prerequisite | Idempotent handling reuses the error contract first. |
| `spring-boot-web-mvc-and-rest` | `spring-boot-security-fundamentals` | prerequisite | Security filters sit in the same request pipeline. |
| `spring-boot-configuration-and-profiles` | `spring-boot-observability-and-actuator` | prerequisite | Actuator surfaces the config/profile model first. |
| `spring-boot-web-mvc-and-rest` | `spring-boot-resilience-patterns` | prerequisite | Retry/circuit-breaking wrap the same calls MVC models. |
| `spring-boot-transactions-and-consistency` | `spring-boot-resilience-patterns` | prerequisite | Resilience must respect the tx boundaries first. |
| `spring-boot-core-container-and-di` | `spring-boot-async-and-scheduling` | prerequisite | Async/scheduled beans are managed by that container. |
| `java-concurrency-fundamentals` | `spring-boot-async-and-scheduling` | prerequisite | Spring's async abstractions layer over Java concurrency. |
| `spring-boot-web-mvc-and-rest` | `spring-boot-testing-strategy` | prerequisite | Test strategy is organized around the MVC layer. |
| `java-testing-with-junit` | `spring-boot-testing-strategy` | prerequisite | Boot test slices extend JUnit fixtures/test doubles. |

### 8.4 `system_design` (13)

| from | to | type | rationale |
| --- | --- | --- | --- |
| `spring-boot-web-mvc-and-rest` | `system-design-http-api-contracts` | prerequisite | API contracts generalize the REST vocabulary first. |
| `system-design-http-api-contracts` | `system-design-caching-strategies` | prerequisite | Cache-key design is scoped to those contracts. |
| `system-design-http-api-contracts` | `system-design-load-balancing-and-scaling` | prerequisite | LB routing assumes the resource shape defined first. |
| `system-design-http-api-contracts` | `system-design-partial-failure-and-timeouts` | prerequisite | Timeout reasoning applies to those defined calls. |
| `spring-boot-resilience-patterns` | `system-design-partial-failure-and-timeouts` | prerequisite | Partial-failure design generalizes per-call resilience. |
| `system-design-partial-failure-and-timeouts` | `system-design-message-delivery-semantics` | prerequisite | Delivery semantics is the messaging case of partial failure. |
| `spring-boot-idempotent-request-handling` | `system-design-message-delivery-semantics` | prerequisite | Delivery semantics generalizes request-level idempotency. |
| `system-design-message-delivery-semantics` | `system-design-rate-limiting-and-backpressure` | prerequisite | Backpressure must account for redelivery/duplication. |
| `system-design-load-balancing-and-scaling` | `system-design-rate-limiting-and-backpressure` | prerequisite | Rate limiting applies at the same routing layer. |
| `system-design-message-delivery-semantics` | `system-design-multi-service-data-consistency` | prerequisite | Saga/outbox build on the delivery-semantics vocabulary. |
| `spring-boot-transactions-and-consistency` | `system-design-multi-service-data-consistency` | prerequisite | Saga/outbox compose local tx boundaries across calls. |
| `system-design-multi-service-data-consistency` | `system-design-migration-and-zero-downtime-evolution` | prerequisite | Zero-downtime migration must preserve consistency invariants. |
| `rdb-schema-evolution-and-migrations` | `system-design-migration-and-zero-downtime-evolution` | prerequisite | Platform migration extends schema-migration sequencing. |

### 8.5 `aws` (12)

| from | to | type | rationale |
| --- | --- | --- | --- |
| `aws-core-compute-and-networking-model` | `aws-iam-fundamentals` | prerequisite | IAM policies are written against that account model. |
| `aws-core-compute-and-networking-model` | `aws-vpc-and-network-isolation` | prerequisite | VPC isolation refines the regional networking model. |
| `aws-core-compute-and-networking-model` | `aws-s3-storage-model` | prerequisite | S3's model is examined against the account/service model. |
| `aws-core-compute-and-networking-model` | `aws-rds-managed-postgres` | prerequisite | RDS is a managed instance of that model. |
| `rdb-relational-modeling-and-normalization` | `aws-rds-managed-postgres` | prerequisite | Choosing RDS needs the relational modeling vocabulary. |
| `aws-core-compute-and-networking-model` | `aws-elastic-load-balancing` | prerequisite | ELB operates within that networking model. |
| `system-design-load-balancing-and-scaling` | `aws-elastic-load-balancing` | prerequisite | ELB is the AWS-specific load-balancing implementation. |
| `aws-elastic-load-balancing` | `aws-autoscaling-and-capacity` | prerequisite | Auto Scaling reacts to ELB's health/routing signals. |
| `aws-autoscaling-and-capacity` | `aws-deployment-and-rollout-patterns` | prerequisite | Rollout patterns sequence against the capacity model. |
| `system-design-migration-and-zero-downtime-evolution` | `aws-deployment-and-rollout-patterns` | prerequisite | AWS rollout is the platform case of migration reasoning. |
| `aws-deployment-and-rollout-patterns` | `aws-observability-and-cost-guardrails` | prerequisite | Guardrails are read against the chosen rollout pattern. |
| `aws-iam-fundamentals` | `aws-identity-least-privilege-for-services` | prerequisite | Least-privilege scoping refines the general IAM model. |

### 8.6 `dsa` prerequisites (5, non-scenario)

| from | to | type | rationale |
| --- | --- | --- | --- |
| `java-collections-core` | `dsa-hash-based-lookup-and-idempotency-keys` | prerequisite | Idempotency-key lookup applies hash-based collections directly. |
| `java-collections-core` | `dsa-priority-queues-and-heaps` | prerequisite | Heaps are compared against the sequential collections first. |
| `java-collections-core` | `dsa-graphs-and-topological-ordering` | prerequisite | Graph adjacency builds on the collection vocabulary first. |
| `dsa-hash-based-lookup-and-idempotency-keys` | `dsa-lru-and-bounded-caches` | prerequisite | LRU composes hash lookup with an eviction ordering. |
| `dsa-hash-based-lookup-and-idempotency-keys` | `dsa-consistent-hashing-and-partitioning` | prerequisite | Consistent hashing generalizes lookup to a ring of nodes. |

The remaining 7 relations — each `dsa` topic's required `SCENARIO` edge — are in §9.

## 9. DSA-to-scenario bindings (CUR-02)

CUR-02 requires DSA only where scenario-relevant; `_validate_dsa_scenario_relations` mechanically rejects a `dsa` topic with zero `SCENARIO` relation. IDK-002 §3.2 goes further: the DSA concept must be "genuinely load-bearing for solving it, not a relation inserted only to satisfy the validator" — a link "present but topically vacuous" fails. Every row states which IDK-009 scenario grounds the binding and why the concept is load-bearing, not decorative.

| from (`dsa`) | to | Grounding IDK-009 scenario / `topic_binding_key` | Why load-bearing |
| --- | --- | --- | --- |
| `dsa-hash-based-lookup-and-idempotency-keys` | `spring-boot-idempotent-request-handling` | `mid-order-idempotency-initial-v1`, `mid-inventory-redelivery-delayed-v1` / `event-idempotency` | The scenario's accepted alternatives ("idempotency record and business mutation in one transaction" or "unique business/event key plus atomic upsert") are a hash-indexed uniqueness check evaluated atomically. Without hashing/collision vocabulary a candidate cannot explain why this prevents the named near miss ("check-then-insert outside the transaction") or answer the scenario's concurrent-duplicate cross-question. |
| `dsa-priority-queues-and-heaps` | `system-design-rate-limiting-and-backpressure` | `staff-cascading-failure-practice-v1` / `systemic-failure-containment` | The scenario needs a system-wide retry budget that drains backlog without amplification; its near miss ("add retries at every hop... without removing amplification") is what an unordered, unbounded queue produces. A heap-backed admission structure is what makes a bounded, ordered drain — and a defensible amplification bound — possible. |
| `dsa-graphs-and-topological-ordering` | `system-design-migration-and-zero-downtime-evolution` | `staff-platform-migration-initial-v1`, `staff-regional-audit-delayed-v1` / `platform-evolution` | The scenario needs staged adoption across six independent teams with no flag-day cutover. Sequencing "who moves before whom" without lockstep is a dependency-graph problem whose safe order is a topological sort; the rollback cross-question depends on which downstream nodes stay reachable from an unmigrated upstream node. |
| `dsa-graphs-and-topological-ordering` | `rdb-schema-evolution-and-migrations` | `senior-zero-downtime-schema-practice-v1` / `relational-schema-evolution` | The scenario's own hint — "separate compatibility, population, validation, and enforcement into reversible stages" — is the same dependency-ordering problem applied to DDL/backfill steps. Reusing the same topic for both bindings shows the concept is general, not scenario-specific trivia restated twice. |
| `dsa-lru-and-bounded-caches` | `system-design-caching-strategies` | `mid-spring-latency-practice-v1` / `spring-data-path-diagnosis` | The scenario's near miss is an *unbounded* fix ("only increase the pool with no capacity analysis"). An LRU/bounded cache caps memory/connection reuse instead of growing unboundedly — directly answering the scenario's own adaptive question about doubling the pool. |
| `dsa-consistent-hashing-and-partitioning` | `system-design-load-balancing-and-scaling` | `staff-multiregion-evolution-mock-v1` / `multi-region-evolution` | The scenario needs bounded cross-region capacity cost under region-affine routing/failover. Consistent hashing bounds how much traffic remaps on a capacity change; naive modulo hashing would remap nearly everything — the unbounded blast radius the scenario's accepted alternatives forbid. |
| `dsa-consistent-hashing-and-partitioning` | `aws-autoscaling-and-capacity` | `staff-multiregion-evolution-mock-v1` / `multi-region-evolution` | The same capacity-cost constraint applies to Auto Scaling group membership changes: a consistent-hashing partition keeps remapped-key fraction proportional to the capacity delta, not the whole fleet — the concrete AWS-side application, not a duplicate abstract claim. |

5 `dsa` topics, 7 `scenario` relations, every relation grounded in a specific IDK-009 scenario ID and its named accepted alternatives or near miss — not merely a `topic_binding_key` label.

## 10. Checkpoint scheme

`checkpoint_start`/`checkpoint_end` is a contiguous half-open range per topic from one running counter across the graph version:

1. Slots are assigned once, in §7's presentation order (`java` → `rdb` → `spring_boot` → `system_design` → `aws` → `dsa`), counter starting at 0.
2. Width (`checkpoint_end − checkpoint_start`) is **2** exactly when the topic anchors an IDK-009 scenario pair with both `initial` and `delayed` phases — the phases need independent problem-first checkpoints, since a delayed checkpoint must present new evidence rather than repeat the initial one (IDK-009 §5: "no order/payment code or identifiers from the paired scenario may be reused"). Every other topic has width **1**.
3. Exactly three topics get width 2, matching IDK-009's three paired-scenario families: `spring-boot-idempotent-request-handling` (`mid-order-idempotency-initial-v1` + `mid-inventory-redelivery-delayed-v1`), `system-design-message-delivery-semantics` (`senior-checkout-partial-failure-initial-v1` + `senior-fulfillment-backlog-delayed-v1`), `system-design-migration-and-zero-downtime-evolution` (`staff-platform-migration-initial-v1` + `staff-regional-audit-delayed-v1`).

50 topics × width 1 plus 3 × width 2 = 56 total slots, 0–56 (§7's tables show the exact values by construction).

This document reserves the integer range only. The seven fields each checkpoint must carry — scenario/constraints, target capability, expected artifact, 30–60 minute session range, rubric/assumptions, evidence criterion, material static/runtime limitation (spec §7.1, DEP-02) — are authored by IDK-201.

## 11. Level and capability mapping

`level_tag`/`target_capability` use exactly IDK-004's vocabulary. `level_tag` names the level at which a topic first becomes required breadth — IDK-004 §3's scopes are cumulative (Senior's end-to-end reasoning presupposes Mid's bounded-service competence; Staff's cross-system scope presupposes Senior's). A learner targeting Staff is expected to also cover every Mid/Senior topic; `level_tag` marks first introduction, not a visibility partition — D2's roadmap projection already shows the whole graph regardless of target level.

| Level | Topics | java | rdb | spring_boot | system_design | aws | dsa |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Mid-level | 24 | 8 | 2 | 8 | 1 | 3 | 2 |
| Senior | 19 | 2 | 3 | 5 | 4 | 5 | 0 |
| Staff | 10 | 1 | 1 | 0 | 3 | 2 | 3 |
| **Total** | **53** | **11** | **6** | **13** | **8** | **10** | **5** |

Intentional shape: `spring_boot` has zero Staff topics because Staff breadth here runs through `system_design` (3) and `aws` (2) — cross-system/cross-team reasoning per IDK-004's Staff scope, deliberately not framed as deeper Spring API surface. `dsa` has zero Senior topics because its Mid (2) and Staff (3) split mirrors IDK-009's own DSA-bearing scenarios: three Mid-phase, three Staff-phase, none Senior-phase.

Capability distribution:

| Capability | know | understand | choose | implement | diagnose | defend |
| --- | --- | --- | --- | --- | --- | --- |
| Topics | 3 | 11 | 12 | 17 | 7 | 3 |

`know`/`understand` cluster at Mid-level orientation topics; `choose` clusters at Senior/Staff trade-off topics (`Alternatives` layer); `implement` is largest since most Mid/Senior topics ask for a testable artifact, per IDK-009 §3's breadth definitions; `defend` is reserved for the three topics anchoring IDK-009's `defend`-capability scenario pairs (§10), matching their `Interview`-layer anchor — Mock is where `defend` is exercised under cross-questioning.

`recommended_layer` never anchors on `Sources` in v1 — it is a cross-cutting citation-depth layer every topic can eventually carry, not a primary teaching mode, and no v1 topic is citation-first as its dominant approach. Usage across the 53 topics: `Essential` 10, `Implementation` 15, `Internals` 6, `Production` 6, `Alternatives` 12, `Failures` 1, `Interview` 3, `Sources` 0.

## 12. What this spine excludes and forbids

- **Go and Go+AWS are entirely absent.** No `subject`, `scope_tags` entry, `stable_id`, title, or rationale in §7/§8/§9 contains `go`, `golang`, or `go_aws` in any case — authored with `_validate_no_go_nodes`'s exact-match token check in mind. CUR-02 defers Go+AWS to Later (IDK-601); PRD §13 places it under Post-MVP.
- **No database *execution* topic implying a connector.** Every `rdb` topic (§7.2) is static/conceptual — modeling, isolation reasoning, reading a plan, lock reasoning, migration sequencing, replication trade-offs — none needs a live connection. Matches IDK-008 §1 exactly: MVP "may teach representative RDB topics" and "accept... artifacts for explicitly labelled static review," never open a connection. IDK-008 §5's Java-only, socket-denied runner boundary is unaffected.
- **No topic requiring a forbidden or unapproved IDK-003 source.** §1 ties every subject to an approved class. Excluded for exactly this reason: any Kafka/RabbitMQ-internals, Redis-specific, Docker/Kubernetes, Maven/Gradle, NoSQL, or MySQL/Oracle-DB-specific topic — none has an approved source class, and PRD §10 already excludes most of this infrastructure from MVP's architecture. Delivery-semantics needs (at-least-once, dedup, dead-lettering) are taught generically (`system-design-message-delivery-semantics`), grounded in routine self-contained content plus RFC 9110 where standards-level — never bound to a broker vendor or its docs.
- **No Stack Overflow, Wikipedia, blog, or company-blog claim** — IDK-003 §5 leaves these unapproved/forbidden.
- **No comprehensive-coverage claim.** 53 topics is an explicit minimum (§5). Deliberately cut, pending a future decision version (§18): AWS services beyond the 10 listed (no Lambda, DynamoDB, SQS/SNS, API Gateway, ECS/EKS, CloudFront — the 10 chosen are load-bearing for this spine's connections and IDK-009's scenarios, not a service catalog); reactive programming (WebFlux/Reactor); Kotlin/Scala; GraphQL/gRPC; front-end/client topics (outside PRD's backend scope); classic algorithm-only DSA staples with no scenario tie — sorting trivia, tree-balancing, dynamic programming, string matching, bit manipulation. These may still surface in Interview Prep's Refresher/Questions (a separate system, spec §5.2, not canonical-graph-gated), but have no non-vacuous CUR-02 scenario tie today.
- **No company-specific claim or real-company name**, per IDK-009 §3 and IDK-004 §2.
- **No hiring, readiness, mastery, or completion claim.** `level_tag`/`target_capability` describe practice scope only, per IDK-004 §2's own prohibition.

## 13. How this spine satisfies IDK-002's approval checklist

Mapping IDK-002 §3's seven items to what this document supplies for inspection — not self-certification; IDK-002 §6 forbids treating a document's own claim as satisfying its checklist.

- **§3.1 Curriculum-boundary (CUR-01).** §7 gives 53/53 topics with `subject`/`scope_tags`; §1's source-tier table and §12's exclusion list state the boundary to check against, including the "no comprehensive coverage" judgment.
- **§3.2 DSA-scenario relation (CUR-02).** §9 gives 5/5 `dsa` topics with per-binding justification tied to a specific IDK-009 scenario ID and its accepted-alternative/near-miss mechanics — built to answer the "topically vacuous" test directly.
- **§3.3 DAG and stable-identity.** §8 gives the full 67-edge prerequisite set plus §9's 7 scenario edges for DAG re-confirmation; §6 fixes the identity rule for v2+. First version: zero reused `stable_id` values, so this sub-item is vacuously satisfied for v1.
- **§3.4 Source/citation spot-check.** Not yet applicable — no `claims`/`citations` exist since no `content_revisions` are proposed (§1); activates once IDK-201 authors content.
- **§3.5 Layer-reversal (DEP-03).** Not yet applicable — no topic has two authored layers yet. §11 records each topic's single anchor layer.
- **§3.6 Half-seed/immutability.** An operational check at actual publish time by IDK-102's D1 tooling; no document pre-satisfies it.
- **§3.7 Diff review.** Not applicable — no prior published version exists; `review_kind` would be `"initial"`, `diff_review` null, per IDK-002 §4.

## 14. Required implementation evidence before IDK-102 can publish it

1. **IDK-201 authors content**: ≥1 `content_revisions` row at each topic's `recommended_layer` (§7) for all 53 topics, closed-schema validated, citing only §1's approved tiers.
2. **IDK-003 §12's registry-population path ships** and the six approved classes are actually registered as `sources` rows before any content cites them.
3. **A manifest is constructed** encoding this document's 53 topics/74 relations (plus IDK-201's revisions), its `manifest_hash` computed by `compute_manifest_hash`, and `validate_manifest` run with zero violations — the authoritative check, superseding §8's hand-verification.
4. **IDK-002's checklist is completed** by the approver against that exact manifest (§13 states what each item inspects); the approver performs every inspection and records the outcome in a validated `basis_ref` (IDK-002 §4).
5. **IDK-102's D1 publisher runs**, inserting version, topics, relations, content revisions, and `EditorialApproval` atomically, last.
6. **§17's stop point lifts** only once all of the above hold and a real `editorial_approvals` row exists for the resulting version.

## 15. Known gaps

- No `content_revisions` exist yet for any of the 53 topics (IDK-201, §14.1).
- No `sources` rows are registered for any of the six approved classes yet (IDK-003 §12/§13, §14.2).
- `topics.level_tag`/`target_capability` carry no database `CHECK` constraint today (IDK-002 §9's own gap); this document's values match IDK-004's vocabulary by construction, but nothing yet rejects a deviating manifest.
- Checkpoint content — the seven required problem-first fields per checkpoint (§10) — is not authored; only the integer range is reserved.
- Whether 53 topics and this exact title/prerequisite/DSA-binding set is the *pedagogically right* curriculum is an editorial judgment this document cannot make for itself — IDK-002 §3.1/§3.2/§3.3's judgment layer, reserved for the human approver.
- §12's v2 candidates (additional AWS services, reactive programming, non-scenario DSA staples, etc.) have no scheduled decision or ticket — named as deliberately deferred, not a committed roadmap.
- No production canonical graph version has ever been published (IDK-002 §9); this document has no precedent instance of its own review.

## 16. Allowed preliminary work while open

- Build and test the D1 offline publish tool.
- Graph validation: DAG/cycle rejection, stable IDs, curriculum tags.
- Topic/roadmap read-gates.
- IDK-201 may begin drafting `content_revisions` for §7's topics ahead of formal approval, provided drafts are clearly marked non-canonical/unapproved and never inserted as, or presented as, an approved version. This document's existence does not itself authorize treating any topic as approved; only §19's recorded approval does.

All of the above run only against a synthetic fixture graph explicitly labelled non-production, or clearly marked non-canonical drafts — never against a version presented to a learner.

## 17. Stop point

§19's approval makes this the "approved MVP curriculum spine document" IMPLEMENTATION_TICKETS.md's IDK-001 approval gate names. The decision-level stop point is lifted.

Two stop points survive it, and neither is waived by approval:

`/app/learn-roadmap` and `/app/topic-studio` remain `unavailable` for any goal until a production graph version carries a valid approval record built from this decision. No such version exists — approving a spine is not publishing one.

No `canonical_graph_versions` row seeded from this decision may receive an `EditorialApproval` for production learner use until §14's six conditions hold: IDK-201 has authored content, IDK-003's registry-population path has registered the sources, a real manifest has passed `validate_manifest` with its computed `manifest_hash`, and IDK-002's checklist has been completed against that exact manifest and recorded in a valid `basis_ref`. This document's approval is an input to that record, not a substitute for it.

## 18. Change control

`mvp-curriculum-spine-v1` is immutable once approved: no topic, relation, scope tag, DSA binding, checkpoint assignment, level, or capability in §7–§11 may be edited, added, or removed in place. Any change — including adding a §12 v2 candidate, correcting a title, or adjusting a prerequisite — requires a new decision version (`mvp-curriculum-spine-v2`, …) reviewed under IDK-002 §3.7's diff-review discipline (every diff item, especially every deletion, reviewed and defensible; no partial review covering only additions).

Stable-ID continuity for v2+: a `stable_id` carried forward unchanged must still denote the same concept (IDK-002 §3.3; §6). A v2 that changes what a topic is fundamentally about mints a new `stable_id` under §6's naming rule and retires the old one under §6's retirement rule — it never silently repurposes an existing identity string, since `topic_identities.stable_id` persists across versions and any goal/evidence/overlay referencing it is entitled to assume its meaning has not shifted. A v2 addition (e.g., a §12 candidate once its source clears an IDK-003 gate) mints a fresh ID under the same rule; it does not retrofit into a v1 identity. A v2 removal follows §6's retirement rule and PRD Appendix H D9's "archived local topic" consequence for any goal carrying evidence against it.

## 19. Approval record

| Approver | Role | Date | Decision | Version | Basis |
| --- | --- | --- | --- | --- | --- |
| MVP local owner | Content owner / designated editorial approver | 2026-08-14 | Approved without changes | 1.0 | Sections 1–18 and the project implementation request |

Decision values: `approved`, `changes requested`. The basis references §1–§18 as reviewed. No `reviewed_manifest_hash` is recorded here because §14's evidence has not yet produced a real manifest to hash; IDK-002 §4 requires that hash on the `editorial_approvals` row created at publish time, which is a separate act this approval does not perform.

## 20. Approval statement

The designated editorial approver recorded:

`Approved IDK-001 recommended mvp-curriculum-spine-v1 policy version 1.0 in sections 1–18 without changes.`

No exception may be recorded through that single-sentence form. A partial approval, or an approval with modifications to any topic, relation, binding, checkpoint, level, or capability assignment, must instead state exactly which section or table row changed and be reissued as a new decision version under §18 — never appended to this sentence as a caveat.

Approval settles the curriculum question and lifts §17's stop point as a *decision* gate. It does not publish anything: §14's six implementation conditions still stand, so no `canonical_graph_versions` row exists, no content is authored, and `/app/learn-roadmap` and `/app/topic-studio` remain unavailable until IDK-201 authors content and IDK-102's publisher runs.
