# IDK-010 — Size, retention, and data-lifecycle policy

Phase 0, blocking decision. This document frames the product/privacy decision and the evidence required to approve it. It adopts no limit, duration, export format, recovery promise, backup posture, or support-access policy.

## 1. Status

Open / awaiting product and privacy approval.

Owner: product/privacy owner, per PRD §13. Approver identity is TBD. This document does not name an approver.

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
| Import originals | Maximum bytes per import and maximum retained imports | | | | |
| Import statements | Maximum statements per import and pending/unreviewed statements | | | | |
| Evidence and artifacts | Maximum payload bytes and retained item count | | | | |
| Generated content | Maximum body bytes and retained versions/items | | | | |
| Interview transcripts | Maximum turns and bytes per session and per owner | | | | |
| Runner input | Maximum declared files and aggregate input bytes | | | | |
| Runner output | Maximum stdout/stderr bytes per stream and per run | | | | |
| Runner temporary storage | Maximum bytes and file count per run | | | | |
| Pending overlay proposals | Maximum pending proposals per goal | | | | |
| Pending jobs | Maximum queued/running jobs per owner | | | | |

The current engineering defaults in `server/src/yuno/config.py` are test and development values, not proposals or approved production values. In particular, `overlay_proposal_pending_cap = 25` and `pending_job_cap = 100` must not be treated as policy approval.

## 6. Retention and expiry decisions

For each category, specify when the clock starts, whether retention is time- or count-based, what happens at expiry, whether expiry is suspended by an active operation, and what audit/provenance record survives cleanup.

| Category | Decision required | Approved duration / count | Clock starts | Expiry action | Surviving metadata |
| --- | --- | --- | --- | --- | --- |
| Abandoned diagnostics | Session expiry | | | | |
| Completed diagnostics | Session and answer retention | | | | |
| Imports and originals | Original, parsed, and reviewed data retention | | | | |
| Generated artifacts | Content and provenance retention | | | | |
| Practice and Mock transcripts | Active, completed, cancelled, and draft retention | | | | |
| Job records | Terminal job and attempt retention | | | | |
| Job events / SSE | Event retention and maximum replay window | | | | |
| Runner output | Output-chunk retention | | | | |
| Runner temporary files | Success, failure, cancellation, crash, and startup-janitor cleanup timing | | | | |
| Export operations | Operation metadata and generated package retention | | | | |
| Delete operations | Operation metadata, impact snapshot, and audit retention | | | | |
| Structured logs | Rotation size, total retention, and disposal behavior | | | | |

Queue-age promotion and janitor timing also require approved values. The current engineering defaults `background_job_age_promotion_seconds = 300` and `job_janitor_retention_seconds = 86400` demonstrate the mechanism only and are not approved policy.

## 7. Export decision

The approver must record all of the following as one internally consistent export contract.

| Item | Decision required | Approved decision | Evidence / rationale |
| --- | --- | --- | --- |
| Package format | Container and manifest representation | | |
| Format identifier | Stable product-qualified format name | | |
| Initial version | Exact version string and compatibility meaning | | |
| Filename convention | Exact deterministic or timestamped convention | | |
| Text encoding | Manifest and referenced text encoding | | |
| Integrity | Required hashes/checksums and what they cover | | |
| Inventory | Required profile, goals, overlays, evidence, notebook, reviews, imports, generated artifacts, and provenance fields | | |
| Tombstones | Exact unavailable marker and retained metadata | | |
| Missing referenced content | Exact unavailable marker and reason vocabulary | | |
| Interview transcripts | Included, excluded, or separately consented; state-by-state rules | | |
| Raw import originals | Included or excluded and why | | |
| Quarantined provider output | Included or excluded and why | | |
| Runner output | Included or excluded and why | | |
| Package storage | Location, permissions, at-rest protection, and cleanup | | |
| Delivery | How the learner receives or inspects a completed package | | |
| Version evolution | Backward-read guarantees, migration posture, and deprecation rules | | |

Until this table is approved and configured, production export remains fail-closed. The implementation's fixture version is test evidence only.

## 8. Delete, recovery, and backup decision

| Item | Decision required | Approved decision | Evidence / rationale |
| --- | --- | --- | --- |
| Delete meaning | Logical tombstone, physical removal, or staged combination by data category | | |
| Recovery window | Duration and exact recoverable scope, or an explicit no-recovery guarantee | | |
| Recovery authority | Who can initiate recovery and how identity/intent is verified | | |
| Physical purge | Trigger, schedule, retry behavior, and failure visibility | | |
| Cross-goal effects | Required treatment of transferred evidence and dependent LearningState | | |
| Audit survival | Which non-content audit facts survive deletion and for how long | | |
| Local backups | Whether backups exist, where they are stored, and how they are protected | | |
| Backup inclusion | Which data, tombstones, logs, exports, and secrets are included or excluded | | |
| Backup retention | Number/age of retained backups and deletion propagation | | |
| Restore | Supported restore scope, verification, failure behavior, and user messaging | | |
| Lost-device / corrupt-database posture | Explicit guarantee or explicit absence of guarantee | | |

The approved policy must distinguish deletion from the live database, physical purge, backup expiry, and audit retention. Settings copy may claim only what this table approves.

## 9. Logging and support-access decision

The fixed redaction categories in section 4 are the minimum. Approval must additionally settle:

| Item | Decision required | Approved decision | Evidence / rationale |
| --- | --- | --- | --- |
| Allowed fields | Exhaustive ordinary-log allowlist by event family | | |
| Additional redaction | Any categories beyond the fixed minimum | | |
| Rotation | Per-file size/count or equivalent local rotation rule | | |
| Retention | Maximum log age and total disk budget | | |
| Storage protection | Location, permissions, and at-rest posture | | |
| Learner access | Whether and how the local owner can inspect/export/delete logs | | |
| Support access | None, learner-mediated bundle, or another explicitly approved model | | |
| Support consent | Scope, expiry, revocation, and visible disclosure if access exists | | |
| Incident handling | What may be preserved beyond ordinary retention and under whose authority | | |
| Verification | Representative redaction and rotation evidence required for release | | |

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

## 12. Stop point while open

- Production export remains disabled.
- Settings must not promise a retention duration, recovery window, backup guarantee, or support-access model.
- Placeholder caps and cleanup timings remain engineering-only.
- IDK-409 cannot pass its manual privacy acceptance, and IDK-503 cannot close G10/G11.

## 13. Approval record

| Approver | Role | Date | Decision | Policy version | Evidence reference |
| --- | --- | --- | --- | --- | --- |
| | Product/privacy owner | | | | |

Decision values: `approved`, `changes requested`. Approval requires every decision cell in sections 5–9 to be complete or explicitly marked `not applicable` with a rationale. A partially completed table does not activate production lifecycle claims.

## 14. Recommended MVP policy — awaiting approval

Status: proposed, not approved. This section supplies a complete candidate for product/privacy review. It does not alter the blank approval tables above or authorize production claims.

The recommendation applies four external principles:

- Define processing and deletion capabilities from a documented privacy-risk profile rather than treating a framework as automatic compliance ([NIST Privacy Framework FAQ](https://www.nist.gov/privacy-framework/frequently-asked-questions)).
- Keep each category only as long as its stated product purpose requires, with a category-specific schedule ([ICO storage-limitation guidance](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/data-protection-principles/a-guide-to-the-data-protection-principles/storage-limitation/)).
- Exclude or sanitize secrets and sensitive bodies, restrict access, cap disk consumption, and dispose of logs at the end of their defined retention period ([OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)).
- Do not describe application-level record deletion as forensic media sanitization; device disposal is a separate, sensitivity-based process ([NIST SP 800-88 Rev. 2](https://csrc.nist.gov/pubs/sp/800/88/r2/final)).

The sources do not prescribe Yuno-specific numeric limits. The values below are product recommendations inferred for a single-owner, local SQLite MVP dominated by text, code, and metadata. They protect responsiveness and disk use while leaving ample room for ordinary learning activity.

### 14.1 Recommended size and count limits

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

### 14.2 Recommended retention schedule

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

Background job age promotion remains 5 minutes. Terminal runner workspace janitor retention changes from the engineering placeholder of 24 hours to the proposed 1 hour. Learning records with an active purpose remain until the learner deletes the owning item or goal; operational exhaust has a short fixed lifetime.

### 14.3 Recommended export contract

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

### 14.4 Recommended delete, recovery, and backup posture

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

### 14.5 Recommended logging and support posture

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

The recommendation intentionally identifies work rather than treating documentation as enforcement:

- Most proposed byte/count limits do not yet exist as configuration or validation.
- Diagnostic, transcript, import, generated-content, job/event, runner-output, and export-package expiry jobs do not yet implement this schedule.
- Several append-only tables currently reject deletion; retaining their integrity metadata while removing bodies requires explicit body/reference separation and forward migrations.
- Goal deletion currently removes the D5-governed evidence payloads but does not yet remove every goal-owned sensitive body named in section 14.4.
- Export does not yet expose the approved envelope, filename/download representation, canonical-data digest, or expiry cleanup.
- Structured logs are safely allowlisted but currently use stderr rather than the proposed owner-only rotated local files.
- Settings does not yet display the proposed no-recovery/no-backup wording or the relevant configured limits and expiry periods.

These gaps must be implemented and verified after approval; until then, section 12's stop point remains in force.

### 14.7 Candidate approval shortcut

The product/privacy owner may approve this entire candidate by recording:

`Approved IDK-010 recommended MVP policy 1.0 in section 14 without changes.`

Any exception must name the section 14 row, replacement value, and rationale. Engineering then transcribes the approved candidate into sections 5–9, assigns the policy version and date in section 13, and implements the gap list before production activation.
