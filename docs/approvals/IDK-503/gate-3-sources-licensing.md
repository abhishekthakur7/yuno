# IDK-503 gate 3 — Source licensing, snapshot and withdrawal policy (CNT-04)

- Gate: Source licensing, snapshot and withdrawal policy (CNT-04)
- Reviewer role required: designated editorial approver (content owner)
- Inspection date: 2026-08-14
- Decision under review: `docs/decisions/IDK-003-source-licensing-and-snapshot-policy.md` — Status: approved, Decision version `1.0`, Policy identifier `source-policy-v1`, Approval date 2026-08-14, Approver role "content owner, per PRD §13" (decision doc lines 3–11, §15 approval record, §16 approval statement). The doc itself records the legal-gate column as advisory, not a blocker, and explicitly states approval settles the policy question only — it does not make any source usable, since §12's implementation evidence "does not exist" (doc §15, line 216).
- Implementing tickets: IDK-207 (citations/claims); no ticket has yet shipped §12's required evidence (registry population, license-status CHECK, `withdrawal_reason`/`superseded_by_source_id` columns, tier-aware retrieval, purge path, excerpt cap, failure-threshold job, frontend attribution/withdrawal-copy fixes). IDK-201, IDK-404, IDK-408 own the still-fixture-only surfaces cited below.
- Disposition: blocking-finding
- Attestation: pending — designated editorial approver has not signed this gate.

## Inspected artifacts

| Artifact | What it is | How inspected |
| --- | --- | --- |
| `server/yuno.db` | Local dev SQLite DB | `sqlite3 server/yuno.db "SELECT license_status, availability_status, origin, count(*) FROM sources GROUP BY 1,2,3;"` and same for `source_snapshots.status` |
| `server/.e2e.db` | E2E-run SQLite DB, not production | Same queries as above |
| `sources` / `source_snapshots` schema | Live DDL | `sqlite3 server/yuno.db ".schema sources"` / `".schema source_snapshots"` |
| `server/src/yuno/modules/provenance/models.py` | `SourceRow` ORM model | Read; grepped for `license_status`, `availability_status`, `withdrawal_reason`, `superseded_by_source_id` |
| `server/src/yuno/modules/provenance/repository.py` | `SqlAlchemySourceRepository` | Read method list (lines 40–70) |
| `server/src/yuno/modules/provenance/adapters.py` | `HttpSourceRetrievalAdapter.retrieve`, `_read_bounded`, `remove_unreferenced_snapshots` | Read lines 25, 55–162, 265 |
| `server/src/yuno/modules/provenance/service.py` | `run_source_retrieval_job` | Grepped for consecutive-failure/72-hour logic |
| `server/src/yuno/api/provider_runtime.py` | `ClaimPayload`/`CitationPayload` | Read/grepped lines 46–105 for excerpt-length validation |
| `server/src/yuno/api/contracts.py` | `SourceResponse`/`SourceSnapshotResponse` | Grepped lines 1134–1155 for field presence |
| `src/selected/core/CorePages.tsx` | `ArtifactProvenanceDetails` (Sources/provenance sub-view), Reports page tombstone banner | Read lines 542–553, 995–1022 |
| `server/src/yuno/api/routes/provenance.py` | `require_disclosure` gate on source retrieval | Grepped for `source-retrieval`/`source-network-v1` |
| `server/src/yuno/migrations/versions/e10d1a0c0100_policy_1_0_body_separation_and_retention.py` | Citation-required-on-publish triggers | Grepped for `trg_claims_required_citation_on_published_insert`/`_on_publish` |
| `server/tests/integration/test_generated_content_api.py:233` | Fixture source row | Grepped for `fixture-approved` |
| `grep -rn "withdrawal_reason\|superseded_by_source_id" server/src/yuno/` | Repo-wide search for §12 schema additions | Confirmed zero matches |

## Findings

| # | Decision requirement | Shipped reality (with citation) | Verdict |
| --- | --- | --- | --- |
| 1 | §11: `sources.license_status` closed production vocabulary (`approved-open-license`, `approved-link-only`), enforced by a new CHECK | `sqlite3 server/yuno.db ".schema sources"` shows only `CONSTRAINT ck_sources_license_status_non_blank CHECK (length(trim(license_status)) > 0)` — free text, no enumerated CHECK. `server/src/yuno/modules/provenance/models.py:25` matches (non-blank only). | not shipped |
| 2 | §12.1: nullable `withdrawal_reason` (CHECK to §11's 5 values, required when `withdrawn`) and `superseded_by_source_id` columns | `sqlite3 server/yuno.db ".schema sources"` shows no such columns. `grep -rln "withdrawal_reason\|superseded_by_source_id" server/src/yuno/` returns zero files. | not shipped |
| 3 | §4: six-class approved registry admitted at stated tier — `sources` rows should exist once implementation ships (though §1 explicitly holds real citation until §12 ships) | `SELECT ... FROM sources GROUP BY license_status, availability_status, origin` on both `server/yuno.db` and `server/.e2e.db` returns zero rows — no `sources` rows of any kind exist in either DB. | not shipped (consistent with §1's own stop-point; no license-value violation possible on an empty table) |
| 4 | §11: `fixture-approved` must never appear on a production row | No production rows exist to check (finding 3); the only occurrence of `fixture-approved` in the codebase is the test fixture at `server/tests/integration/test_generated_content_api.py:233`, `origin="fixture"` per decision doc §13's own citation. | matches (no violation observed, because nothing is shipped to violate it) |
| 5 | §6 Tier B: no persisted body, only hash/URL/timestamp | `HttpSourceRetrievalAdapter.retrieve` (`server/src/yuno/modules/provenance/adapters.py:55-162`) always streams, bounds to `MAX_RESPONSE_BYTES` (10 MiB, line 25), hashes, and persists the full body to `self._root / content_hash` (lines 111-120) with no branch on `license_status` anywhere in the method. | not shipped — Tier A cap (10 MiB) is enforced; Tier B body-suppression is not |
| 6 | §6: 20-per-source retained-snapshot janitor, oldest-first pruning excluding cited snapshots | `remove_unreferenced_snapshots` (`server/src/yuno/modules/provenance/adapters.py:265`) prunes only zero-citation blobs, no age/count-based janitor exists. | not shipped |
| 7 | §6: license-revocation immediate purge of persisted body on `license-revoked`/`license-changed-incompatible` | No purge-by-license-event function exists beside `remove_unreferenced_snapshots`; no `withdrawal_reason` field to trigger it on (finding 2). | not shipped |
| 8 | §6: 400-character inline excerpt cap on `CitationPayload`/`ClaimPayload` | `server/src/yuno/api/provider_runtime.py` `CitationPayload`/`ClaimPayload` (lines 46-105) validate `source_id`/`locator`/`support_kind` non-blank and uniqueness (line 93) but contain no length bound on any citation field. | not shipped |
| 9 | §8: automatic `unavailable` only after 3 consecutive failures spanning ≥72h, auto-reset to `available` on success; no auto-`withdrawn` ever | `run_source_retrieval_job` (`server/src/yuno/modules/provenance/service.py`) has no consecutive-failure counter or time-window logic (grep for "consecutive"/"72"/"hours" returns nothing); repository has no `update_source` method at all (`repository.py:40-70` lists only `add_source`/`get_source`/`list_sources`) — no code path can transition `availability_status`. | not shipped |
| 10 | §8: `unavailable` and `withdrawn` must render distinguishably to the learner, never identical copy | `ArtifactProvenanceDetails` in `src/selected/core/CorePages.tsx:549` renders both as `` `${source.title} is ${source.availability_status}` `` — the interpolated status word differs but the sentence template is identical for both states, matching the decision doc's own §13 citation of this exact line. Reports page (`CorePages.tsx:1021`) renders a third, still-undifferentiated form: `` `Tombstoned source warning: cited source withdrawn or unavailable` `` header covering both states with one shared message. | matches decision doc's documented gap; policy requirement not met |
| 11 | §8/spec §6.5: withdrawn/unavailable sources remain visible with status and last-known provenance, never silently hidden | `CorePages.tsx:549` (Sources sub-view) and `CorePages.tsx:1021` (Reports) both render a persistent warning naming the source and status rather than dropping the citation; claim/citation immutability triggers (`trg_claims_published_no_update`/`_no_delete`, `trg_citations_no_update`/`_no_delete`/`_no_insert_replace`) exist per migration `e10d1a0c0100...py`. | matches (no fabrication/silent drop observed) |
| 12 | §7: attribution must show publisher, title, canonical URL as a link, retrieval timestamp, resolved license identifier, version label — inline, never deferred | `ArtifactProvenanceDetails` (`CorePages.tsx:552`) renders only `citation.source.title`, `citation.locator`, `citation.source.publisher`, and `citation.source.availability_status`. No `canonical_url`, no link element, no `retrieved_at`, no resolved license identifier, no `version_label` appear in this component or the Reports evidence-sources line (`CorePages.tsx:1022`, which renders only `title (availability_status)`). Fields exist server-side in `SourceResponse`/`SourceSnapshotResponse` (`server/src/yuno/api/contracts.py:1134-1155`: `title`, `publisher`, `canonical_url`, `version_label`) but are not read by either frontend site. | not shipped — 4 of 6 required attribution fields absent from both learner-facing surfaces |
| 13 | CNT-04: sensitive/disputed/comparative/time-or-version-dependent claims require citation | `ClaimPayload`/`CitationPayload` reject such a claim with no citation (`provider_runtime.py:90-105`); DB-level triggers `trg_claims_required_citation_on_published_insert` and `trg_claims_required_citation_on_publish` exist verbatim in `server/src/yuno/migrations/versions/e10d1a0c0100_policy_1_0_body_separation_and_retention.py:2224,2227`. | matches |
| 14 | Every shipped claim resolves to a real snapshot row | No production `sources`/`source_snapshots` rows exist (finding 3); the only claims/citations in either DB are against `origin="fixture"` sources per test suite pattern (`test_generated_content_api.py:233`, `test_interview_api.py`, `test_notebook_review_api.py` per decision doc §12.7's own citation, independently corroborated by the empty-table query above). | not shipped — no learner-facing claim resolves to a real (non-fixture) source today |
| 15 | Offline/local-only snapshot capture, no runtime fetch at learner request | `require_disclosure(..., category="source-retrieval", disclosure_version="source-network-v1")` gates retrieval in `server/src/yuno/api/routes/provenance.py:133-134`; retrieval only proceeds through this disclosed, explicit path — not from a bare page render — per spec §6.5/§12.2 default #5 as the decision doc records (§2, line 25). No opposing code path found. | matches |
| 16 | Registry-population path attributed to a content-owner role, replacing test-only `add_source` call sites | `repository.py:41` `add_source` has no distinct content-owner attribution field; `owner_role_grants.role` has only `learner`/`designated_editorial_approver` values (per decision doc §13's own citation, independently confirmed: no seed/publish script or content-owner grant path found in `provenance/` module). | not shipped |

## Blocking findings

### 1. No production source registry exists — every shipped claim is fixture-sourced
- Missing: any `sources`/`source_snapshots` row outside test fixtures; §12's full implementation evidence list (items 1-9 of decision doc §12).
- Owning ticket: no ticket currently owns this — decision doc §12 assigns it to "IDK-201/IDK-207/IDK-404/IDK-408 (or a dedicated `provenance` follow-up ticket)"; none has shipped it. IDK-503's own dependency list includes IDK-207 but IDK-207 has not delivered §12.
- Evidence of absence: `sqlite3 server/yuno.db "SELECT count(*) FROM sources;"` and the equivalent on `server/.e2e.db` both return 0 rows; `repository.py` exposes no `update_source`; `grep -rln "withdrawal_reason\|superseded_by_source_id" server/src/yuno/` returns nothing.
- What would clear it: ship §12 items 1-9 (schema migration adding the CHECK/`withdrawal_reason`/`superseded_by_source_id`, `update_source` repository path, tier-aware retrieval, purge job, excerpt validation, 3-attempt/72h transition job, real registry seed step, frontend attribution/withdrawal-copy fixes) and re-run this gate against the resulting rows.

### 2. Learner-facing attribution omits 4 of 6 required fields (§7)
- Missing: canonical URL as a link, retrieval timestamp, resolved license identifier, version label — in both `ArtifactProvenanceDetails` (Sources/provenance sub-view) and the Reports evidence-sources line.
- Owning ticket: IDK-201 (Sources sub-view)/IDK-207 (Reports/Evidence provenance rendering), per decision doc §12.8.
- Evidence of absence: `src/selected/core/CorePages.tsx:552` renders only title/locator/publisher/availability_status; `CorePages.tsx:1022` renders only title/availability_status; server contract fields `canonical_url`/`version_label` exist in `server/src/yuno/api/contracts.py:1139-1140,1154` but no reference to `canonical_url`, `retrieved_at`, or `version_label` appears anywhere in `CorePages.tsx`.
- What would clear it: render all six §7 fields inline at both call sites and re-inspect.

### 3. `unavailable` and `withdrawn` render with shared/undifferentiated copy (§8)
- Missing: distinct learner-facing copy distinguishing a transient (`unavailable`) from a terminal editorial (`withdrawn`) state.
- Owning ticket: IDK-201/IDK-207 per decision doc §12.8.
- Evidence of absence: `src/selected/core/CorePages.tsx:549` uses one template string for both states (`` `${source.title} is ${source.availability_status}` ``); `CorePages.tsx:1021` uses one combined header ("withdrawn or unavailable") for both.
- What would clear it: two distinct copy templates per §8's "different facts" requirement, re-inspected against shipped strings.

### 4. No automatic `unavailable` transition and no `withdrawal_reason`-gated purge exist (§6, §8)
- Missing: the 3-attempt/72-hour failure counter and reset-on-success in `run_source_retrieval_job`; the license-revocation purge path.
- Owning ticket: not yet assigned per decision doc §12 (candidate: `provenance` follow-up, or IDK-404).
- Evidence of absence: `server/src/yuno/modules/provenance/service.py` `run_source_retrieval_job` contains no consecutive-failure counter, no time-window check; `repository.py` has no `update_source` method, so no code path can write `availability_status`/`withdrawal_reason` at all.
- What would clear it: ship the job logic and repository update path, verify with a targeted test exercising 3 failures spanning 72h before re-inspection.

## Notes and residual risk

- The decision doc (§1, §12, §13, §15) itself states, in its own approved text, that none of the implementation evidence exists and that no real source may be cited until it ships. This inspection independently corroborates every one of those self-declared gaps against the current DB and code state as of 2026-08-14 — none have since closed. The policy question (tier model, vocabulary, state machine, attribution contract) is genuinely settled and internally consistent; what is being gated here is CNT-04's implementation, not IDK-003's authorship, per IDK-503's own scope boundary.
- Because zero `sources` rows exist in either inspected database, no license-value or status-value violation was observed — but this is an artifact of nothing being shipped, not evidence of compliant shipped behavior. Findings 3-16 above should not be read as "passing" in the sense of exercised, populated behavior.
- `server/.e2e.db` and `server/yuno.db` are both local dev/e2e databases, not production; this review draws no inference about a production dataset because none exists yet under this policy.
- This gate cannot reach `inspection-passed-pending-attestation`: CNT-04's learner-facing sign-off surface (§7 attribution, §8 withdrawal-copy differentiation) and the underlying registry (§12) are not shipped. Re-inspection is required after the owning tickets close before this gate can be re-attempted.
