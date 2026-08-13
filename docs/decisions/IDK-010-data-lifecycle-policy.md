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
