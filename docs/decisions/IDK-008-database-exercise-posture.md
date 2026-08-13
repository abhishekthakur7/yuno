# IDK-008 — Database-exercise posture

Status: approved

Decision version: `1.0`

Policy identifier: `database-exercise-posture-v1`

Approval date: 2026-08-14

Approver role: engineering owner, acting through the implementation request that directed approval and recording of IDK-008

This decision approves no executable database connector for MVP. It resolves the learner-supplied-versus-product-managed question by adopting neither execution posture in version 1.0. Approval requires IDK-406 to remove a false placeholder capability; it does not claim that removal is already implemented and does not activate the Java runner.

## 1. Decision and product boundary

MVP exposes no relational or database execution capability. Subject to IDK-001/002 curriculum and editorial approval, Yuno's mechanisms may teach representative RDB topics and may accept SQL, schema, query-plan, transaction, migration, or design artifacts for explicitly labelled static review. It does not open a learner database connection or infer runtime behavior from that review.

The optional wording in PRD RUN-01 does not require a connector to ship: Java compile/test is the MVP runtime validation, while a database capability may be advertised only when configured. Version 1.0 chooses absence rather than defining a second execution system without an approved credential, network, engine, operation, or lifecycle contract.

## 2. Rejected execution postures

Version 1.0 rejects both alternatives for MVP:

- **Learner-supplied connection:** Yuno does not accept a host, port, URI/DSN, database, username, password, passfile, certificate, JDBC driver, or other connection input and opens no database socket.
- **Product-managed instance:** Yuno does not install, download, initialize, provision, discover, start, stop, seed, reset, migrate, upgrade, back up, restore, or remove a database instance, server, role, schema, data directory, container, or virtual machine.

Yuno never invokes a database CLI, container engine, package manager, database server binary, or driver on behalf of an exercise. The product's own SQLite application database is never an exercise target.

## 3. Capability and request contract

`GET /runner/capabilities` contains only capabilities implemented under an approved execution policy. Relational/database execution is absent from the response; it is not returned as `supported`, `missing`, `incompatible`, disabled, or coming soon. A configuration string, installed client, listening database, or environment variable cannot create a capability.

Runner confirmation and run contracts contain no relational language or database operation. There is no legacy rejection discriminator, compatibility endpoint, or relational domain enum. The one retired raw signature that receives a mandated regression test is a `POST /runner/confirmations` JSON body whose otherwise-valid Java-confirmation fields contain `"language":"relational"`; it is an ordinary invalid request under the closed Java-only schema and returns the standard `422` validation envelope before the route/UoW. Other unknown fields or invalid discriminator values follow the ordinary closed-schema validation contract and do not receive a relational-specific path. SQL text submitted through an artifact/static-review contract is learner content, not a runner discriminator, and remains eligible for static review.

No confirmation, runner record, job, output chunk, database setting, structured credential/endpoint record, artifact mutation, or evidence row is created by an invalid runner request. IDK-406 tests the exact retired signature above, representative ordinary unknown-field validation, schema-error precedence, and zero side effects; it does not preserve a relational-specific response path.

## 4. Static RDB learning

RDB curriculum and hands-on scenarios are eligible for later approved content under IDK-001/002. A learner may submit SQL or database-design text as an ordinary hands-on artifact when that content ships. IDK-405's static evaluator may review syntax, reasoning, assumptions, trade-offs, transaction semantics, migration sequencing, query design, or expected behavior that can be justified from the submitted artifact and approved sources.

Every such result uses IDK-405's mandatory review-specific limitation and must communicate all of these semantic clauses: no database connection; no statement/query-plan/migration/concurrency execution; and no proof of runtime, persistence, performance, locking, or production behavior. There is deliberately no global exact sentence reused across unrelated reviews. IDK-405 owns the hands-on assertion, IDK-302 owns it for the approved RDB Practice record, and IDK-503 reviews the shipped cross-surface wording. Static Submit never reads connector configuration or credentials and creates no runner record.

## 5. Java runner and security boundary

IDK-007 `runner-environment-v1` remains Java-only and socket-denied. This decision neither weakens that boundary nor permits a JDBC connection, embedded database, database driver, connection string, network exception, host socket, or database process inside the Java runner.

No structured connector credential or endpoint field may appear in Settings, execution API contracts, persisted runner records, process environments, broker requests, system-generated execution metadata, or generated client types. Learner-authored static prose/artifacts may mention an endpoint or may accidentally contain a secret; that content is not parsed into connector configuration and remains governed by IDK-010 export/privacy and structured-log redaction policy. Generic secret redaction remains defense-in-depth, not evidence that a connector exists.

## 6. Required removal and implementation evidence

IDK-406 removes the obsolete placeholder paths rather than retaining compatibility or fallback behavior:

- `Settings.runner_relational_connector`;
- `RunnerLanguage.RELATIONAL` and every relational value in SQLite checks/migrations;
- the configured-string capability branch that currently reports `supported` without a connection or probe;
- relational request/OpenAPI/generated-client variants and frontend controls/copy;
- conditional relational runner records, operations, fixtures, and tests.

The Java-only constraint migration transactionally deletes any pre-existing `language='relational'` confirmation/runner placeholder rows and their exclusively owned input/body/output dependents before rebuilding the checks. A `kind='runner'` job whose typed request, `run_id`, or result reference targets one of those placeholders is part of that placeholder's exclusively owned operational subgraph: its attempts, events, and result are deleted in the same transaction. Those rows could never represent a successful database operation under the prior service and are explicitly non-authoritative operational placeholders; they are not relabelled, archived, converted to Java, or preserved behind a compatibility table. The migration preserves unrelated jobs and every goal, artifact, and evidence row, then proves no surviving logical request, run, or result reference points at a removed identifier. IDK-406 owns the migration; IDK-501 verifies this single approved obsolete-placeholder removal while all governed learner/domain data remains intact.

Before IDK-406 can pass:

1. Capability JSON, OpenAPI, generated client types, database constraints, settings, and UI expose Java only.
2. The exact retired `POST /runner/confirmations` `"language":"relational"` signature receives the standard `422` schema response before the route/UoW and creates no side effect, even when obsolete environment/configuration text is present; other invalid fields use the same ordinary closed-schema behavior.
3. Tests prove zero database socket/process, confirmation, job, broker request, runner record/output, artifact, or evidence mutation.
4. IDK-405/302 tests prove approved RDB static-review content carries the mandatory semantic limitation clauses while Java remains independently gated by IDK-005/007; IDK-406 proves static review remains usable but does not own content wording.
5. Repository residue scanning finds no relational connector setting, enum member, configured-string detector, disabled placeholder, or compatibility path.

IDK-503 reviews the shipped absence, closed-schema validation/zero-side-effect behavior, review-specific static-limitation clauses, and absence of structured connector credential/endpoint fields. Decision approval creates no Java or database activation evidence.

## 7. Change control

`database-exercise-posture-v1` is immutable. Database execution is not a promised follow-up.

Adding any connector requires a new approved decision and implementation scope that explicitly fixes, at minimum: engine and exact supported versions; driver/parser identities; learner-supplied or managed lifecycle; endpoint and destination policy; TLS and credential storage/redaction/export/delete rules; permitted statements and transaction/mutation semantics; per-run consent; timeout, cancellation, server-session verification, cleanup and residual-resource posture; exact capability/messages; activation evidence; and native/adversarial tests. It cannot be enabled by configuration alone or reuse/weaken the Java environment policy implicitly.

## 8. Approval record

| Approver | Role | Date | Decision | Version | Basis |
| --- | --- | --- | --- | --- | --- |
| Engineering owner | Engineering owner | 2026-08-14 | Approved without changes | 1.0 | Sections 1–7 and the project implementation request |

The approval resolves IDK-008 and removes IDK-406's final decision blocker. IDK-406 becomes Ready for implementation; effective Java execution remains prohibited until its complete implementation, native exact-tuple activation evidence, and shipped threat-model review pass.
