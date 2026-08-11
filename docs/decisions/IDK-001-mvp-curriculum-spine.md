# IDK-001 — Frame the MVP curriculum spine decision

Phase 0, blocking decision. This document frames the question and the evidence an approver needs. It selects no answer, proposes no topic, and accepts no candidate.

## 1. Status

Open / awaiting approval.

Owner: content owner / editorial approver, per PRD §13. Approver identity is TBD — PRD §13 and IMPLEMENTATION_TICKETS.md's IDK-001 approval gate both leave it unresolved. This document does not name anyone.

## 2. The question

Source: PRD §14 Q1; IMPLEMENTATION_SPEC §12.3 Q1.

Which Java/Spring Boot/AWS topics and which connected System Design/RDB topics form the minimum reviewed MVP spine? Which DSA relations are scenario-relevant?

## 3. Why it is blocking

Gates:

- The real, non-fixture content used by IDK-102's production publish run — specifically, IDK-102's "publish the real v1" acceptance criterion.
- IDK-201's authored topic layers.
- Phase 1/2 content exit — the approval-gated sense of "exit" defined in IMPLEMENTATION_TICKETS.md's "Phase exit semantics" section, which release, pilot, and any learner-facing content claim depend on.

Does not gate:

- IDK-102's own fixture-based mechanism tests. Those run against a synthetic fixture graph explicitly labelled non-production and do not require this decision to be resolved. More generally, Phase 1 engineering exit (every phase ticket implemented and passing against approved fixtures) does not require any IDK-0xx decision to be resolved.

## 4. Required evidence checklist

An approver completes this checklist. No item is satisfied by this document.

- [ ] Candidate topic list with stable IDs.
- [ ] Prerequisite/relationship graph draft.
- [ ] Curriculum scope tags demonstrating the Java/Spring Boot + AWS boundary (CUR-01).
- [ ] An explicit DSA-topic-to-scenario relation for every proposed DSA node (CUR-02).
- [ ] Written confirmation that Go + AWS is entirely absent from the MVP spine.

## 5. Shape the answer must take

The eventual answer must be expressible as rows in three tables defined in IMPLEMENTATION_SPEC §4.3. No column beyond those listed there is available.

| Table | Columns / constraints the answer must satisfy |
| --- | --- |
| `topic_identities` | `stable_id` (PK), `stable_slug` (UNIQUE), created/retired timestamps. Stable across graph versions. |
| `topics` | Composite PK of graph version + stable ID; title, subject, scope/level tags, target capability, recommended layer, checkpoint range, content revision. Curriculum tags must enforce the CUR-01 boundary; DSA topics require a scenario relation (CUR-02). |
| `topic_relations` | Graph, from/to stable IDs, relation type, rationale; unique tuple. Prerequisite cycles are rejected — the graph must be a DAG; only explicitly configured non-prerequisite relation types may cycle. |

These constraints are structural (stable identity, DAG-shaped relations, curriculum tagging, DSA-requires-scenario-relation). They bound how the answer must be encoded; they do not supply the answer.

## 6. Allowed preliminary work while open

- Build and test the D1 offline publish tool.
- Graph validation: DAG/cycle rejection, stable IDs, curriculum tags.
- Topic/roadmap read-gates.

All of the above run only against a synthetic fixture graph explicitly labelled non-production.

## 7. Stop point

No `canonical_graph_versions` row seeded from this decision may receive an `EditorialApproval` for production learner use, and IDK-102's "publish the real v1" acceptance criterion cannot be reached, until this spine is approved.

`/app/learn-roadmap` and `/app/topic-studio` remain `unavailable` for any goal until a production graph version carries a valid approval record built from this decision.

## 8. Approval record

| Approver | Date | Decision | Reference to approved spine document |
| --- | --- | --- | --- |
| | | | |

Decision values: `approved`, `changes requested`. The referenced document is the artifact this record formalizes: an approved MVP curriculum spine (topic list, stable IDs, relations, DSA scenario bindings) satisfying CUR-01/CUR-02. Table left blank pending review.
