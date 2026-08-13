# IDK-010 — Size, retention, and data-lifecycle policy

Phase 0, blocking decision. This document records the approved product/privacy limits, retention schedule, export contract, deletion and backup posture, and logging/support policy. Approval does not claim enforcement before the engineering gaps and privacy-review evidence are complete.

## 1. Status

Approved as policy version 1.0 on 2026-08-13; engineering enforcement and privacy-review evidence remain pending.

Owner and approver: product/privacy owner, per PRD §13. Approval was recorded through the project conversation using section 14.7's exact approval statement.

## 2. The question

Sources: PRD §14 Q10–Q11; IMPLEMENTATION_SPEC §12.3 Q10–Q11.

What limits apply to imports, artifacts, transcripts, generated content, execution output, temporary files, and retained jobs? How long may diagnostic sessions and event history remain? What are the precise export format and versioning rules, transcript-inclusion policy, delete-recovery guarantees, backup posture, and logging retention, redaction, and support-access rules?

## 3. Why it is blocking

This decision gates:

- Production activation and privacy acceptance of IDK-409's export, delete, and structured-logging flows.
- Production values for diagnostic expiry, overlay-proposal limits, pending-job limits, queue-age promotion, job janitor cleanup, and SSE replay retention.
- The G10/G11 portion of the consolidated IDK-503 privacy review and Phase 4/5 content exit.

It does not gate the already-tested mechanisms for durable operations, tombstoning and dependent-state downgrades, immutable delete impact snapshots, safe log-field redaction, or configurable caps and expiry.

## 4. Decision principles that are already fixed

The approver selects values within these existing product invariants; this record does not reopen them.

- The MVP is local-first and has one local owner.
- Export must be documented and versioned, and must mark unavailable or tombstoned content rather than fabricate it.
- Delete confirmation must use an immutable impact snapshot and reject a changed snapshot.
- Evidence deletion uses the D5 tombstone and dependent-state downgrade transaction.
- Ordinary logs must not contain credentials, tokens, cookies, authorization headers, provider authentication environment values, AWS keys or connection secrets, unrelated environment variables, avoidable absolute user paths or usernames, raw prompts, transcripts, artifact bodies, or quarantined raw output.
- Learner-visible failures expose a safe classification, not a raw stack trace or internal diagnostic.
- The API must not promise SSE replay beyond retained events.
- No external telemetry is included in MVP.

## 5. Size and count decisions

Every row requires an approved numeric value and unit, an enforcement point, the learner-visible rejection behavior, and whether the limit is per item, operation, goal, owner, or installation.

| Category | Decision required | Approved value / unit | Scope | Rejection behavior | Evidence / rationale |
| --- | --- | --- | --- | --- | --- |
| Import originals | Maximum bytes per import and maximum retained imports | 10 MiB/item; 100/owner | Item and owner | `413 import-too-large` or `409 import-count-limit`; no partial write | Protect local SQLite/disk use while accommodating text imports |
| Import statements | Maximum statements per import and pending/unreviewed statements | 10,000/import; 50,000 unreviewed/owner | Import and owner | Reject parsed set atomically | Bound parse/review work and database growth |
| Evidence and artifacts | Maximum payload bytes and retained item count | 10 MiB/item; 10,000/owner | Item and owner | `413 evidence-too-large` or `409 evidence-count-limit`; prior evidence unchanged | Bound learner-content storage |
| Generated content | Maximum body bytes and retained versions/items | 2 MiB/body; 5,000/owner | Body and owner | `generated-content-limit`; no partial artifact | Generated content is text-dominant and reproducible |
| Interview transcripts | Maximum turns and bytes per session and per owner | 1,000 turns and 10 MiB/session; 200 sessions/owner | Session and owner | Preserve current run; require export/deletion before continuing | Bound sensitive transcript volume |
| Runner input | Maximum declared files and aggregate input bytes | 100 files; 10 MiB/run | Run | Reject before process creation | Bound pre-spawn work and disk use |
| Runner output | Maximum stdout/stderr bytes per stream and per run | 1 MiB/stream; 2 MiB/run | Stream and run | Truncate with explicit marker and terminal limit classification | Prevent output-driven exhaustion |
| Runner temporary storage | Maximum bytes and file count per run | 256 MiB; 10,000 files/run | Run | Cancel safely and clean workspace | Bound local execution storage |
| Pending overlay proposals | Maximum pending proposals per goal | 25/goal | Goal | `409 pending-cap-exceeded`; no insert | Retains tested engineering value as approved policy |
| Pending jobs | Maximum queued/running jobs per owner | 100/owner | Owner | `429 pending-job-cap`; no reservation | Retains tested engineering value as approved policy |

The pre-existing engineering defaults in `server/src/yuno/config.py` did not themselves establish policy. Policy version 1.0 now independently approves `overlay_proposal_pending_cap = 25` and `pending_job_cap = 100`; every other default must still be reconciled with this document.

## 6. Retention and expiry decisions

For each category, specify when the clock starts, whether retention is time- or count-based, what happens at expiry, whether expiry is suspended by an active operation, and what audit/provenance record survives cleanup.

| Category | Decision required | Approved duration / count | Clock starts | Expiry action | Surviving metadata |
| --- | --- | --- | --- | --- | --- |
| Abandoned diagnostics | Session expiry | 30 days | Last update | Expire; remove seed/answer bodies | ID, `expired` state, version refs, timestamps, hashes |
| Completed diagnostics | Session and answer retention | Until goal deletion | Goal deletion | Remove seed/answer bodies | Minimal status, version refs, timestamps, hashes |
| Imports and originals | Original, parsed, and reviewed data retention | Until import or parent-goal deletion | Explicit delete | Remove original/corrected text atomically | IDs, parser version, hashes, decisions, timestamps, audit facts |
| Generated artifacts | Content and provenance retention | Until parent-goal deletion | Goal deletion | Remove bodies/references atomically | IDs, versions, hashes, provenance, timestamps, audit facts |
| Practice and Mock transcripts | Active, completed, cancelled, and draft retention | Draft/active: 30 days inactivity; terminal: until session or goal deletion | Last activity or explicit delete | Remove raw turns/drafts/answers/feedback | IDs, state, versions, timestamps, hashes, audit facts |
| Job records | Terminal job and attempt retention | 30 days | Terminal timestamp | Purge operational payloads, diagnostics, attempts, results after reconciliation | Domain result and audit records |
| Job events / SSE | Event retention and maximum replay window | 7 days or newest 10,000/owner, whichever is smaller | Event timestamp/count cap | Expire oldest terminal events | No event-body archive; GET remains authoritative |
| Runner output | Output-chunk retention | 7 days | Terminal timestamp | Delete chunks/referenced output | State, limit classification, hashes, timestamps, audit facts |
| Runner temporary files | Success, failure, cancellation, crash, and startup-janitor cleanup timing | Immediate on terminal path; 1-hour crash/startup janitor | Terminal state or last verified process activity | Delete workspace | Runner record and safe cleanup classification |
| Export operations | Operation metadata and generated package retention | Package: 24 hours; metadata/hash: 30 days | Completion | Delete package, then operation metadata | No package copy or archive |
| Delete operations | Operation metadata, impact snapshot, and audit retention | Lifetime of local database | Entire-installation erasure | Removed only with database | IDs, hashes, scope, status, timestamps |
| Structured logs | Rotation size, total retention, and disposal behavior | 14 days or 50 MiB; five 10 MiB files | Event time and aggregate cap | Delete expired/oldest file | No secondary archive |

Queue-age promotion is approved at 5 minutes. Terminal runner-workspace janitor retention is approved at 1 hour; the current 24-hour engineering placeholder must be replaced.

## 7. Export decision

The approver must record all of the following as one internally consistent export contract.

| Item | Decision required | Approved decision | Evidence / rationale |
| --- | --- | --- | --- |
| Package format | Container and manifest representation | One canonical UTF-8 JSON document | Simplest portable local representation |
| Format identifier | Stable product-qualified format name | `yuno-portable-export` | Distinguishes product and contract |
| Initial version | Exact version string and compatibility meaning | `1.0` | Major is compatibility boundary; minor is additive |
| Filename convention | Exact deterministic or timestamped convention | `yuno-export-v1-YYYYMMDDTHHMMSSZ.json`, UTC completion time | Stable, sortable, and local-only |
| Text encoding | Manifest and referenced text encoding | UTF-8 without BOM; sorted keys; no insignificant whitespace | Deterministic representation |
| Integrity | Required hashes/checksums and what they cover | SHA-256 of canonical top-level `data`, recorded in `integrity` | Detects package alteration |
| Inventory | Required profile, goals, overlays, evidence, notebook, reviews, imports, generated artifacts, and provenance fields | Envelope plus all categories listed in section 14.3 | Matches PRD portable-representation scope |
| Tombstones | Exact unavailable marker and retained metadata | Stable IDs/safe metadata, `availability: unavailable`, reason `tombstoned` | Never fabricate or silently omit |
| Missing referenced content | Exact unavailable marker and reason vocabulary | `tombstoned`, `source-missing`, `raw-original-excluded`, `policy-excluded` | Stable machine-readable reasons |
| Interview transcripts | Included, excluded, or separately consented; state-by-state rules | Raw bodies excluded from v1; safe run metadata plus `policy-excluded` marker | Privacy-minimizing MVP scope |
| Raw import originals | Included or excluded and why | Excluded; reviewed metadata plus `raw-original-excluded` marker | Avoid exporting untrusted/raw input by default |
| Quarantined provider output | Included or excluded and why | Raw output excluded; safe ID/hash/schema/classification only | Quarantine cannot become trusted output |
| Runner output | Included or excluded and why | Bodies excluded; safe logical filenames/hashes/versions/state/classifications only | Avoid exporting execution bodies by default |
| Package storage | Location, permissions, at-rest protection, and cleanup | Local database package body for 24 hours; no secondary copy; learner controls downloads | Short operational lifetime |
| Delivery | How the learner receives or inspects a completed package | Owner-scoped local API download | No network transfer or remote store |
| Version evolution | Backward-read guarantees, migration posture, and deprecation rules | Semantic versioning; major for breaking changes, minor for additive optional fields; reject unsupported major | Explicit compatibility boundary |

This table is approved but not fully configured or enforced. Production export remains fail-closed until section 14.6's export gaps are implemented and privacy-review evidence passes.

## 8. Delete, recovery, and backup decision

| Item | Decision required | Approved decision | Evidence / rationale |
| --- | --- | --- | --- |
| Delete meaning | Logical tombstone, physical removal, or staged combination by data category | Irreversible goal tombstone plus removal of goal-owned sensitive bodies and app-managed files; minimal integrity metadata remains | Matches D5 and privacy-minimizing body retention |
| Recovery window | Duration and exact recoverable scope, or an explicit no-recovery guarantee | None; no undelete in MVP | Simple and truthful local posture |
| Recovery authority | Who can initiate recovery and how identity/intent is verified | Not applicable; recovery does not exist | No hidden recovery path |
| Physical purge | Trigger, schedule, retry behavior, and failure visibility | Durable delete job removes live bodies/references atomically or through reconciled cleanup; failure remains visible | Application deletion, not forensic media sanitization |
| Cross-goal effects | Required treatment of transferred evidence and dependent LearningState | D5 tombstones and downgrades commit atomically with delete | Existing fixed invariant |
| Audit survival | Which non-content audit facts survive deletion and for how long | IDs, hashes, versions, impact, status, and timestamps for database lifetime; no raw bodies | Integrity without content retention |
| Local backups | Whether backups exist, where they are stored, and how they are protected | Yuno creates none in MVP | No backup or recovery claim |
| Backup inclusion | Which data, tombstones, logs, exports, and secrets are included or excluded | Not applicable to Yuno; external user/OS backups are outside app control | Must be disclosed in delete copy |
| Backup retention | Number/age of retained backups and deletion propagation | Not applicable to Yuno; no propagation guarantee to external backups | Avoid false guarantees |
| Restore | Supported restore scope, verification, failure behavior, and user messaging | No supported in-app restore; a user-provided database must pass schema/migration startup checks | No recovery guarantee |
| Lost-device / corrupt-database posture | Explicit guarantee or explicit absence of guarantee | No recovery guarantee; user-managed encrypted device backup is an external choice | Honest local-only posture |

The approved policy must distinguish deletion from the live database, physical purge, backup expiry, and audit retention. Settings copy may claim only what this table approves.

## 9. Logging and support-access decision

The fixed redaction categories in section 4 are the minimum. Approval must additionally settle:

| Item | Decision required | Approved decision | Evidence / rationale |
| --- | --- | --- | --- |
| Allowed fields | Exhaustive ordinary-log allowlist by event family | Event, UTC timestamp, level, request/correlation/owner/goal/job/provider-request/runner/run IDs, method, route template, status code, provider, lifecycle, fixed classification | Correlation without raw content |
| Additional redaction | Any categories beyond the fixed minimum | Query strings, bodies, user agent, IP address, email/display name, arbitrary exception message, and unknown fields denied by default | Reduce unintended personal/internal data |
| Rotation | Per-file size/count or equivalent local rotation rule | Five files, at most 10 MiB each | 50 MiB hard aggregate cap |
| Retention | Maximum log age and total disk budget | 14 days or 50 MiB, whichever is reached first | Short operational/debug window |
| Storage protection | Location, permissions, and at-rest posture | OS application-data directory restricted to local account; no separate encryption claim | Align with local ownership |
| Learner access | Whether and how the local owner can inspect/export/delete logs | Direct filesystem inspection/deletion; no hidden copy | Learner-controlled local data |
| Support access | None, learner-mediated bundle, or another explicitly approved model | None; no remote access, upload, telemetry forwarding, or support credential | Local-only MVP |
| Support consent | Scope, expiry, revocation, and visible disclosure if access exists | Not applicable; no support access | Any future mechanism needs a new approval |
| Incident handling | What may be preserved beyond ordinary retention and under whose authority | No automatic override; local owner may manually copy a file | Avoid hidden retention |
| Verification | Representative redaction and rotation evidence required for release | Allowlist/redaction, rotation/expiry, owner-only path, no transport, provider/runner failure tests | Required before production activation |

No remote support access or automatic log upload exists by implication. Any such capability would require an explicit approved decision and must remain consistent with the separate external-telemetry gate.

## 10. Required review evidence

The product/privacy owner reviews one representative local dataset containing:

- Two goals with transferred evidence and dependent LearningState records.
- Available and tombstoned evidence payloads.
- An import original and reviewed statements.
- A generated artifact with provenance references.
- A completed and a cancelled transcript-bearing session.
- A successful and failed provider-backed job with safe diagnostics.
- Runner output and temporary-file records, if runner activation is in scope.

The review package must include:

- [ ] A sample export checked field by field against the approved inventory and exclusions.
- [ ] Proof that unavailable/tombstoned content is marked, not fabricated or silently omitted.
- [ ] A delete preflight and completed-delete record showing the approved live-data, audit, recovery, and backup behavior.
- [ ] Captured structured logs showing required correlations and absence of every prohibited category.
- [ ] Evidence that configured size, count, expiry, rotation, and cleanup limits match the approved tables.
- [ ] Learner-facing Settings copy checked against the approved guarantees.

## 11. Configuration and implementation handoff

After approval, engineering maps every adopted value to configuration, validation, cleanup scheduling, Settings copy, and tests. The handoff must identify any approved value for which no enforcement mechanism exists; approval alone does not make an unenforced limit true.

Before production activation, engineering must at minimum replace the unset export policy and review every current placeholder in `server/src/yuno/config.py`. No current default becomes production policy merely because it exists in code.

## 12. Production-activation stop point

- Production export remains disabled until the approved export contract and cleanup are enforced.
- Settings must not promise the approved retention, deletion, or logging behavior until the matching enforcement and tests ship.
- IDK-409 cannot pass its manual privacy acceptance, and IDK-503 cannot close G10/G11, until section 10's review evidence passes.
- Policy approval closes IDK-010's decision question; it does not waive implementation or privacy-review evidence.

## 13. Approval record

| Approver | Role | Date | Decision | Policy version | Evidence reference |
| --- | --- | --- | --- | --- | --- |
| Product/privacy owner | Product/privacy owner | 2026-08-13 | Approved without changes | 1.0 | Section 14 and exact approval statement recorded in project conversation |

Decision values: `approved`, `changes requested`. Every decision cell in sections 5–9 is complete or explicitly marked not applicable. Production lifecycle claims still require enforcement and section 10's review evidence.

## 14. Approved MVP policy 1.0

Status: approved without changes on 2026-08-13 through section 14.7's exact approval statement. Sections 5–9 are the normative transcription; this section preserves the approved proposal and its rationale.

The approved policy applies four external principles:

- Define processing and deletion capabilities from a documented privacy-risk profile rather than treating a framework as automatic compliance ([NIST Privacy Framework FAQ](https://www.nist.gov/privacy-framework/frequently-asked-questions)).
- Keep each category only as long as its stated product purpose requires, with a category-specific schedule ([ICO storage-limitation guidance](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/data-protection-principles/a-guide-to-the-data-protection-principles/storage-limitation/)).
- Exclude or sanitize secrets and sensitive bodies, restrict access, cap disk consumption, and dispose of logs at the end of their defined retention period ([OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)).
- Do not describe application-level record deletion as forensic media sanitization; device disposal is a separate, sensitivity-based process ([NIST SP 800-88 Rev. 2](https://csrc.nist.gov/pubs/sp/800/88/r2/final)).

The sources do not prescribe Yuno-specific numeric limits. The values below began as product recommendations inferred for a single-owner, local SQLite MVP dominated by text, code, and metadata; policy approval adopts them as Yuno's MVP limits. They protect responsiveness and disk use while leaving ample room for ordinary learning activity.

### 14.1 Approved size and count limits

| Category | Proposed value | Scope and enforcement | Learner-visible failure |
| --- | --- | --- | --- |
| Import originals | 10 MiB per import; 100 retained imports | Per item and owner, checked before persistence | `413 import-too-large` or `409 import-count-limit`, with the limit and a delete/export action |
| Import statements | 10,000 per import; 50,000 unreviewed per owner | Checked after deterministic parse but before statements commit | Reject the whole parse atomically; no partial statement set |
| Evidence and learner artifacts | 10 MiB per payload; 10,000 retained records per owner | Checked before append | `413 evidence-too-large` or `409 evidence-count-limit`; existing evidence remains unchanged |
| Generated content | 2 MiB per body; 5,000 retained artifacts per owner | Checked before authoritative artifact publication | Job fails safely with `generated-content-limit`; no partial artifact |
| Interview transcripts | 1,000 turns and 10 MiB per session; 200 sessions per owner | Checked before each turn append and run creation | Preserve the current draft/run and require export or deletion before continuing |
| Runner input | 100 declared files and 10 MiB aggregate | Checked before confirmation and rechecked before spawn | Reject before process creation |
| Runner output | 1 MiB per stream and 2 MiB aggregate per run | Enforced while capturing output | Truncate with an explicit marker; terminal result states the limit |
| Runner temporary storage | 256 MiB and 10,000 files per run | Enforced by the runner boundary | Cancel the run, record a safe limit classification, and clean the workspace |
| Pending overlay proposals | 25 per goal | Existing configured cap | `409 pending-cap-exceeded`; no proposal inserted |
| Pending jobs | 100 per owner | Existing configured cap | `429 pending-job-cap`; no job reserved |

One mebibyte (MiB) means 1,048,576 bytes. Limits apply to decoded stored bytes, not compressed transfer size. A request that crosses multiple limits reports the first deterministic validation failure and commits nothing.

### 14.2 Approved retention schedule

| Category | Proposed retention | Clock and expiry action | Surviving metadata |
| --- | --- | --- | --- |
| Abandoned diagnostics | 30 days | From last update; expire the session and remove seed/answer bodies | Session ID, terminal `expired` state, graph/version refs, timestamps, and hashes |
| Completed diagnostics | Until its goal is deleted | Goal deletion removes seed/answer bodies | Minimal session status, version refs, timestamps, and hashes |
| Imports and originals | Until explicit import deletion or parent-goal deletion | Remove original and corrected text in the delete transaction | Import ID, type, parser version, hashes, decisions, timestamps, and audit facts |
| Generated artifacts | Until parent-goal deletion | Remove generated bodies and body references in the delete transaction | Artifact/provenance IDs, versions, hashes, provider/model IDs, timestamps, and audit facts |
| Practice and Mock transcripts | Draft/active: 30 days after last activity; completed/cancelled: until session or goal deletion | Remove raw turn, draft, answer, and feedback bodies | Run/turn IDs, state, versions, timestamps, hashes, and audit facts |
| Job records and attempts | 30 days after terminal state | Purge operational payloads, raw internal diagnostics, attempts, and results after dependent operations reconcile | Domain result and audit records remain authoritative |
| Job events / SSE | 7 days or the newest 10,000 events per owner, whichever is smaller | Expire oldest terminal events; clients reconcile through `GET /jobs/{id}` | No event-body archive |
| Runner output | 7 days after terminal state | Delete output chunks and referenced output files | Runner state, limit classification, hashes, timestamps, and audit facts |
| Runner temporary files | Immediate cleanup after every terminal path; crash/startup janitor removes workspaces older than 1 hour | From last verified process activity | Runner record and safe cleanup classification |
| Export package | 24 hours after completion | Delete package body; mark operation result expired | Export operation ID, format version, scope, status, timestamps, and package hash for 30 days |
| Delete operations | For the lifetime of the local database | Immutable impact snapshot and non-content audit record remain | IDs, hashes, scope, status, and timestamps only |
| Structured logs | 14 days or 50 MiB total, whichever is reached first | Five 10 MiB files; delete the oldest rotated file and any file older than 14 days | No separate log archive |

Background job age promotion remains 5 minutes. Terminal runner workspace janitor retention changes from the engineering placeholder of 24 hours to the approved 1 hour. Learning records with an active purpose remain until the learner deletes the owning item or goal; operational exhaust has a short fixed lifetime.

### 14.3 Approved export contract

| Item | Proposed decision |
| --- | --- |
| Package | One canonical UTF-8 JSON document |
| Format identifier and version | `yuno-portable-export` / `1.0` |
| Filename | `yuno-export-v1-YYYYMMDDTHHMMSSZ.json`, using the UTC completion timestamp |
| JSON representation | Sorted object keys, no insignificant whitespace, UTF-8 without BOM |
| Integrity | Top-level `integrity` with `algorithm: sha256` and a digest of the canonical `data` object |
| Required envelope | `product`, `format`, `version`, `exported_at`, `scope`, `data`, `integrity` |
| Inventory | Profile, goals, graph pins, personal overlays and proposals, evidence metadata and available payloads, notebook, review preferences/items/attempts, diagnostic metadata, import metadata, generated-artifact metadata, and provenance/source/claim/citation references |
| Tombstones and missing bodies | Retain stable IDs and safe metadata; set `availability: unavailable` and one stable reason: `tombstoned`, `source-missing`, `raw-original-excluded`, or `policy-excluded` |
| Interview transcripts | Excluded from v1; include only run IDs, state, versions, timestamps, hashes, and `availability: unavailable`, reason `policy-excluded` |
| Raw import originals | Excluded; parsed/reviewed metadata remains, with reason `raw-original-excluded` |
| Quarantined provider output | Excluded entirely except safe quarantine ID/hash/schema/failure classification metadata |
| Runner inputs and output bodies | Excluded; retain run IDs, declared logical filenames, hashes, toolchain/limit versions, state, timestamps, and safe classifications |
| Delivery and storage | Owner-scoped local API download; package body retained in the local database for 24 hours, then expired; the learner controls any downloaded copy |
| Evolution | Semantic format versioning: major for breaking meaning/removal, minor for additive optional fields; importers must reject unsupported major versions |

The package is portable data, not a database backup and not a restore promise.

### 14.4 Approved delete, recovery, and backup posture

| Item | Proposed decision |
| --- | --- |
| Goal deletion | Irreversible after the durable job completes. The goal disappears from active UI/search; goal-owned sensitive bodies are removed; required D5 evidence tombstones and dependent LearningState downgrades commit atomically. |
| Retained history | Minimal immutable IDs, hashes, version/provenance links, impact snapshot, timestamps, and audit facts remain. Raw learner, transcript, import, generated, provider, and runner bodies do not. |
| Recovery | No built-in recovery window and no undelete operation in MVP. The confirmation UI must say this explicitly. |
| Physical purge | Remove live database rows/body references and app-managed files during the delete transaction or its atomically reconciled cleanup. This is application-level deletion, not a forensic media-sanitization guarantee. |
| Local backups | Yuno creates no automatic backups in MVP. OS-, filesystem-, VM-, and user-created backups are outside Yuno's control and may retain deleted data until their own expiry. |
| Backup restore | No supported in-app restore workflow or recovery guarantee. A user-provided database copy must independently pass the existing schema and migration startup checks. |
| Entire installation erasure | The learner removes the configured SQLite database, app-managed export/source/runner directories, and rotated logs while Yuno is stopped. Device transfer/disposal follows the operating system or media owner's sanitization process. |
| Lost or corrupt device | No recovery guarantee. Settings and documentation must recommend user-managed encrypted device backup only as an external choice, without claiming Yuno manages it. |

### 14.5 Approved logging and support posture

| Item | Proposed decision |
| --- | --- |
| Ordinary-log allowlist | Event name, UTC timestamp, level, request/correlation/owner/goal/job/provider-request/runner/run IDs, HTTP method and route template, status code, provider name, lifecycle, and fixed diagnostic classification |
| Redaction | Keep the fixed section 4 exclusions; also reject query strings, request/response bodies, user-agent strings, IP addresses, email/display names, arbitrary exception messages, and unknown fields by default |
| Rotation and retention | Owner-only local files, five files of at most 10 MiB, maximum age 14 days, maximum aggregate 50 MiB |
| Storage protection | OS application-data directory with permissions restricted to the local account; no separate Yuno-managed encryption claim |
| Learner access | The local owner may inspect or delete the files through the filesystem; no hidden copy or secondary archive |
| Support access | None. No remote access, automatic upload, telemetry forwarding, or support credential exists in MVP |
| Support sharing | A learner may manually share a file at their own discretion; Yuno provides no automatic bundle in MVP |
| Incident preservation | No automatic retention override. The local owner may manually copy relevant logs before expiry |
| Verification | Unit and integration tests cover allowlisting/redaction, rotation boundaries, expiry, owner-only path creation, absence of remote transport, and representative provider/runner failures |

### 14.6 Known enforcement gaps before approval can activate production policy

The approved policy intentionally identifies work rather than treating documentation as enforcement:

- Most approved byte/count limits do not yet exist as configuration or validation.
- Diagnostic, transcript, import, generated-content, job/event, runner-output, and export-package expiry jobs do not yet implement this schedule.
- Several append-only tables currently reject deletion; retaining their integrity metadata while removing bodies requires explicit body/reference separation and forward migrations.
- Goal deletion currently removes the D5-governed evidence payloads but does not yet remove every goal-owned sensitive body named in section 14.4.
- Export does not yet expose the approved envelope, filename/download representation, canonical-data digest, or expiry cleanup.
- Structured logs are safely allowlisted but currently use stderr rather than the approved owner-only rotated local files.
- Settings does not yet display the approved no-recovery/no-backup wording or the relevant configured limits and expiry periods.

These gaps must be implemented and verified after approval; until then, section 12's stop point remains in force.

### 14.7 Approval statement

The product/privacy owner approved this policy by recording:

`Approved IDK-010 recommended MVP policy 1.0 in section 14 without changes.`

No exception was recorded. Sections 5–9 contain the normative transcription, section 13 records policy version 1.0 and the approval date, and section 14.6 remains the required engineering gap list before production activation.
