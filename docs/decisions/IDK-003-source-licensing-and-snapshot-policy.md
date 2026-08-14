# IDK-003 — Source licensing, snapshot, and withdrawal policy

Status: approved as product policy; the per-row legal gates in §4 and the whole of §5.1 remain uncleared

Decision version: `1.0`

Policy identifier: `source-policy-v1`

Approval date: 2026-08-14

Approver role: content owner, per PRD §13, acting in the content-owner capacity only — no legal reviewer has examined this document

This document settles which source classes may be cited in production learner-facing content, the exact license basis relied on for each, what may be stored locally and for how long, what must be rendered as attribution, and the withdrawal/unavailability/replacement state machine IMPLEMENTATION_SPEC §6.5 requires. It is a product policy record, not legal advice: every license characterization reflects the drafting engineer's research against each publisher's own well-known terms, not an attorney's opinion, and several rows below are marked as needing the reviewer's own confirmation before use even once this document is approved. This document does not itself approve any source — no row is live until section 16's approval statement is recorded. It does not change CNT-04 or PRV-02, does not redefine the `sources`/`source_snapshots`/`claims`/`citations` schema shape fixed by IMPLEMENTATION_SPEC §4.3, does not redefine live retrieval mechanics (IDK-404) or the generated-content cache/staleness contract (IDK-207), and does not reopen any category IDK-010 already decided.

## 1. Decision and boundary

This resolves PRD §14 Q3 / spec §12.3 Q3 for the `provenance` module: an initial approved source registry by publisher and license basis (§4); an unapproved-pending-review bucket and a forbidden-source denial list (§5); numeric snapshot/cache/excerpt limits with named enforcement points (§6); a mandatory attribution contract (§7); the withdrawal/unavailability/replacement state machine, including whether a stored snapshot may keep being served after withdrawal — the ticket's sharpest open question (§8); a citation staleness rule (§9); and the closed production vocabulary for `sources.license_status`/`availability_status` (§11).

Per the IDK-003 stop point: no real external source may be cited in production content, and no snapshot may be retained beyond engineering test fixtures, until a content owner / legal reviewer records §16's approval statement. Until then `generated_artifacts`, `claims`, and `citations` continue against synthetic fixture sources only, as they do today, and IDK-201's `/app/topic-studio` Sources sub-view and IDK-408's `/app/search` stay fixture-only.

## 2. What is already fixed and not reopened

- The `sources`/`source_snapshots`/`claims`/`citations` schema, the D3 cache key, and the claim-type vocabulary (`fact`, `trade-off`, `routine`, `disputed`, `comparative`, `time-or-version-dependent`) are fixed by spec §4.3 and implemented in `server/src/yuno/modules/provenance/models.py` and `learning_content/domain.py`. This decision fixes only the `license_status`/`availability_status` value vocabulary those columns hold (§11).
- CNT-04's claim-appropriate-authority rule and spec §6.5's "sensitive, disputed, comparative, or time/version-dependent claims expose claim-level support" are already enforced: `ClaimPayload`/`CitationPayload` in `server/src/yuno/api/provider_runtime.py` (lines 90–105) reject a sensitive/non-routine claim with no citation, and SQLite triggers `trg_claims_required_citation_on_published_insert`/`_on_publish` (`server/src/yuno/migrations/versions/e10d1a0c0100_policy_1_0_body_separation_and_retention.py`) enforce it at the database level. This decision supplies the real sources those citations point at; it does not touch the enforcement.
- Source retrieval is disclosed and explicit (spec §6.5, §12.2 default #5), gated by `require_disclosure(..., category="source-retrieval", disclosure_version="source-network-v1")` in `server/src/yuno/api/routes/provenance.py`. Unweakened here.
- IDK-404 already fixes that one failed retrieval attempt never mutates a source's stored status. §8 builds the automatic-`unavailable` rule on top of that, not against it.
- IDK-010 §4's principles apply without restatement (local-first, one owner, no raw bodies in logs, no external telemetry). IDK-010 §5–§9 fix limits for imports, evidence, generated content, transcripts, runner I/O, jobs, exports, deletes, and logs — none mention `sources` or `source_snapshots`. §6 below fills that gap without touching any category IDK-010 decided.

## 3. Rejected alternatives

- **Blanket-approve "official documentation" without a per-publisher check** — would assert an unverified permission.
- **Approve Stack Overflow content because CC BY-SA 4.0 is real** — its share-alike and per-post pseudonymous-attribution obligations conflict with a model that mixes short excerpts from many sources into one generated body; user Q&A also fails PRD §9's authority bar. Forbidden in §5 regardless.
- **Treat every withdrawal identically, no reason taxonomy** — cannot answer whether a stored snapshot may keep serving, which §8 must answer. A `withdrawal_reason` vocabulary is required to separate a license-driven withdrawal from a content-driven one.
- **Auto-withdraw after one failed retrieval** — contradicts IDK-404's fixed invariant. §8 instead sets a multi-attempt, time-boxed threshold for `unavailable` and reserves `withdrawn` for an explicit human decision.
- **Unlimited local retention of full snapshot bodies** — unbounded storage/legal exposure; §6 sets a per-snapshot byte cap, a per-source retained-snapshot count, and a license-triggered purge.
- **Excerpts up to IDK-010's 2 MiB generated-content cap** — contrary to PRD §9's "concise claim-linked citations" resolution; §6 sets a much smaller ceiling as product policy, not a fair-use determination.
- **A de facto fourth `availability_status` for "superseded"** — would leave no lineage. §8 instead adds a `superseded_by_source_id` reference, keeping the existing three-value CHECK intact per AGENTS.md's preference for the smallest sufficient change.

## 4. Approved initial source registry

Each row is a source class (publisher plus document family), not one URL; individual `sources` rows are added under a class only after this document, or a numbered successor, is approved. Tier A rows may store a full-body local snapshot and quote the §6 excerpt; Tier B rows may only be linked and cited by metadata. "Legal gate" states whether, beyond this document's own approval, the row needs the reviewer's own additional confirmation before first production use.

| Source class | Publisher | License basis (named) | Tier | What it permits | Legal gate |
| --- | --- | --- | --- | --- | --- |
| IETF RFC series (rfc-editor.org, datatracker.ietf.org) | IETF Trust | IETF Trust Legal Provisions (TLP), governing RFC copyright under BCP 78 | A | Full verbatim reproduction/storage of an unmodified RFC with its required legend; quotation; no modified/derivative version presented as the standard itself | Not required beyond document approval |
| PostgreSQL Documentation (postgresql.org/docs) | PostgreSQL Global Development Group | The PostgreSQL License — a permissive license whose grant explicitly extends to "this software and its documentation" | A | Use, copy, modify, redistribute for any purpose including inside generated lessons, provided the copyright notice is retained; no warranty implied | Not required beyond document approval |
| Spring Framework / Spring Boot Reference Documentation (docs.spring.io) | Broadcom Inc. (Spring project), sourced from `github.com/spring-projects/spring-framework` and `.../spring-boot` | Apache License 2.0 — the reference-guide sources live in the same repository, under the same root `LICENSE`, as the framework/Boot code | A | Reproduction, quotation, modified/derivative use with attribution and a statement of changes; no share-alike | **Required** — confirm the docs.spring.io pages in use are still generated from the Apache-2.0 repository as of citation date; the surrounding site carries its own Broadcom site-level terms outside the versioned repo content |
| Oracle Java SE Documentation; Java Language Specification (docs.oracle.com) | Oracle America, Inc. | Oracle's standard website Terms of Use; no open license identified for the text itself | B | Linking and citation-metadata reference only; no reproduction right asserted | Not required for Tier B; **required** before this row is ever promoted beyond Tier B |
| OpenJDK JEP index and specification pages (openjdk.org) | Oracle / OpenJDK community | Site copyright notice; no open license identified | B | Linking and citation-metadata reference only | Same as the Oracle row |
| AWS Documentation (docs.aws.amazon.com) | Amazon Web Services, Inc. | AWS Site Terms; no open license identified | B | Linking and citation-metadata reference only | Same as the Oracle row |

These six classes cover the ticket's curriculum scope — Java language/platform, Spring Boot, AWS, relational databases (PostgreSQL) — plus the standards layer (RFCs) underlying distributed-systems claims used across `docs/decisions/IDK-009-assessment-and-derived-state.md`'s scenario registry. No row fills a curriculum gap with a license basis that cannot be defended; system-design claims outside these classes stay unsourced (self-contained, expandable-provenance content per spec §6.5) until a further class clears review.

## 5. Unapproved and forbidden sources

### 5.1 Unapproved, pending legal review

Candidates PRD §9 contemplates ("credible attributed expert/industry material when appropriate") but not approved here. No row in this bucket may be added under any tier until a legal reviewer confirms terms per publisher (per source, for individual authors) — this document's own approval does not clear these.

| Source class | Why it is not resolved here |
| --- | --- |
| Individually authored technical blogs, conference-talk transcripts, self-published books excerpted online | Terms vary per author/platform and default to all-rights-reserved; no generic basis is verifiable without checking each publisher |
| Company engineering blogs offered as "credible attributed industry material" (PRD §9) | Same reason; typically all-rights-reserved, and some platforms carry conflicting syndication terms |
| Wikipedia | Real license (CC BY-SA 4.0), but its share-alike obligation raises the same mixed-source conflict as Stack Overflow, and crowd-edited general reference does not meet PRD §9's "official documentation, standards, primary research" bar; not planned for use pending an explicit legal + editorial decision |

### 5.2 Forbidden — never a source, regardless of license

- **Paid/paywalled content** (O'Reilly Learning, Pluralsight, Educative, LeetCode Premium, purchased textbooks). Yuno cannot verify a learner's own paid entitlement or redistribute paywalled material.
- **Scraped aggregator content.** An aggregator's right to republish cannot be verified, and it supplies no claim-appropriate authority under CNT-04; the primary publisher, if approved, is cited instead.
- **Stack Overflow / Stack Exchange content.** CC BY-SA 4.0 under the Stack Exchange Network Terms of Service is real, but its share-alike and per-post pseudonymous-attribution obligations conflict with a mixed-source citation model, and user Q&A fails PRD §9's authority bar for MVP.
- **Content with no identifiable license or publisher.** Copyright defaults to all rights reserved absent an affirmative grant.
- **Competitor course material** (named interview-prep/system-design platforms, paid bootcamp curricula) — forbidden as a product/competitive rule independent of copyright status.
- **Model-generated text treated as a source.** A model's own output — any provider, including Yuno's own generation pipeline — is never a citable source for another claim. Not a licensing question: it follows from PRD §9 ("citations alone do not make generated text correct or canonical") and spec §6.5 ("citation presence never establishes truth"). Only the primary material a model may have been prompted with can be a source; its synthesis of that material never is.

## 6. Snapshot, cache, and excerpt rules

IDK-010 §5–§8 include no row for `sources`/`source_snapshots`; this section fills that gap without reopening any category IDK-010 decided. One MiB is 1,048,576 bytes, per IDK-010's convention.

| Category | Approved value | Enforcement point | Rationale |
| --- | --- | --- | --- |
| Tier A full-body snapshot size | 10 MiB per snapshot | `HttpSourceRetrievalAdapter._read_bounded`/`_validate_content_type`, `provenance/adapters.py` — already enforces exactly this via `MAX_RESPONSE_BYTES` | Matches IDK-010 §14.1's other 10 MiB per-item ceilings (imports, evidence) even though IDK-010 omits this category |
| Tier B body storage | None. Only a SHA-256 `content_hash`, canonical URL, and retrieval timestamp are persisted; the body is hashed in memory and discarded | Not implemented — the adapter always persists the full body today regardless of `license_status` (§13) | A link-only basis grants no reproduction right; storing the body would exceed it even if never redistributed further |
| Retained snapshots per source | 20, oldest-first pruning among snapshots with no live `citations.source_snapshot_id` reference; a cited snapshot is never pruned | Not implemented — no janitor exists; `remove_unreferenced_snapshots` only removes filesystem blobs with zero citation references, not aged rows | Bounds disk growth from repeat retrieval without ever silently removing a citation's evidentiary basis |
| `sources`/`source_snapshots` metadata retention | Lifetime of the local database; no timed expiry | No IDK-010 expiry job includes these tables | The registry is curated, low-cardinality, deliberately approved — unlike high-volume learner content, expiring it would silently invalidate historical citations |
| Inline verbatim excerpt length | 400 characters (~75 words) maximum per citation, set off as a quotation, adjacent to its locator | Not implemented — `ClaimPayload`/`CitationPayload` (`provider_runtime.py`, lines 46–105) validate presence/uniqueness but no length bound | Keeps in-context citations concise per PRD §9's "citations vs. overload" resolution; a product-policy ceiling, not a fair-use determination |
| License-revocation purge | Immediate deletion of every snapshot's persisted body for a source withdrawn with reason `license-revoked`/`license-changed-incompatible`; the metadata row (hash, timestamps, status) is retained | Not implemented — no purge-by-license-event path exists; only reference-count pruning does | Re-serving a full copy after the permitting license ends is a fresh exposure on every serve, independent of citation references |

Tier A retrieval already respects the 10 MiB cap and rejects non-approved content types, redirects, embedded credentials, and non-public IP resolution (`adapters.py` lines 55–162); this policy adopts that behavior as-is and does not weaken it.

## 7. Attribution contract

Every rendered citation — Sources sub-view, generated content, Reports/Evidence provenance — must show inline, never deferred to a footer or a separate page:

1. **Publisher** (`sources.publisher`).
2. **Title** (`sources.title`).
3. **Canonical URL** as an actual link (`sources.canonical_url`), for every tier including link-only Tier B — the link is the entire permitted use for Tier B and must never be omitted.
4. **Retrieval timestamp** of the referenced snapshot (`source_snapshots.retrieved_at`), or "not yet retrieved — citation references the live source only" when no snapshot exists.
5. **License identifier**, resolved from §11's closed vocabulary to the named basis (e.g. "PostgreSQL License" or "link-only, no reproduction") — not the raw `license_status` string alone.
6. **Version/revision label** where the source is versioned (RFC number, Spring Boot minor-version docs, PostgreSQL major-version docs) — `source_snapshots.version_label`, already captured from `ETag`/`Last-Modified` by the adapter.

Fields 1–3 are required for every citation without exception; fields 4–6 are required whenever the underlying data exists. Attribution is never satisfied by a generic "Sources" link elsewhere on the page.

## 8. Withdrawal, unavailability, and replacement state machine

`sources.availability_status` keeps its existing three-value CHECK (`available`, `unavailable`, `withdrawn`) — no fourth value is added. This decision fixes each value's meaning, the transitions between them, and two new nullable columns not in the schema today: `withdrawal_reason` and `superseded_by_source_id` (§12).

**`available`** — default state for an approved, currently retrievable source with a recognized `license_status`.

**`unavailable`** — transient and reversible. Entered automatically only after **3 consecutive independent retrieval attempts fail, spanning at least 72 hours** — never after one attempt, which is IDK-404's fixed invariant. A subsequent successful retrieval returns the source to `available` automatically; no editorial action is needed either way.

**`withdrawn`** — terminal-for-new-use, entered only by explicit editorial action, never inferred from retrieval failures. Every transition carries a `withdrawal_reason` from §11's fixed vocabulary. A withdrawn source is never reinstated to `available`; if its content later becomes suitable again, it is re-approved as a **new** `sources` row with fresh provenance, consistent with the existing `trg_sources_no_insert_replace` trigger, which already forbids reinserting a reused `id`.

**What the learner sees.** `withdrawn` and `unavailable` are different facts and must not render identically. Today `src/selected/core/CorePages.tsx` (line 549) renders both with the same string, `` `${title} is ${availability_status}` `` — this policy requires that closed (§13): `unavailable` reads as a transient degradation, `withdrawn` as a permanent editorial decision. Neither ever hides a citation — spec §6.5 already fixes that withdrawn/unavailable sources "remain visible with status and last known provenance."

**Already-generated content.** Nothing is rewritten or deleted. `claims`/`citations` are immutable once published (`trg_claims_published_no_update`/`_no_delete`, `trg_citations_no_update`/`_no_delete`/`_no_insert_replace`), so a citation keeps pointing at exactly the source and snapshot it referenced at generation time. Per D3 (owned by IDK-207), regeneration happens only on explicit action or a key-changing event; withdrawal is not one of the six D3 key components and is not, by itself, a key-changing event under IDK-207's current definition — so withdrawal does not automatically flag prior content as D3-stale today. This does not redefine D3 (out of scope for IDK-003); it records the fact for IDK-207/IDK-404 to consume if they add withdrawal as a future key-changing event.

**May a stored snapshot keep being served after withdrawal — decided explicitly.** It depends on `withdrawal_reason`, not `availability_status` alone:

- `license-revoked` or `license-changed-incompatible`: the persisted full-body file stops being served immediately, including through any provenance-detail view, and is purged per §6. Continuing to re-serve a complete stored copy after its permitting license ends is a fresh act of distribution on every serve, not a historical fact protected by having been lawful when made.
- `publisher-retracted`, `factually-superseded`, or `registry-declined`: the original storage grant was never revoked; the stored snapshot's metadata and, for Tier A, its body may keep appearing in Sources/provenance detail views labeled `withdrawn` with its reason, for audit and historical-citation purposes only — never as the basis for a new excerpt or citation.
- In every case, previously generated text that already quoted or relied on the source keeps showing as-is, per the rule above; this is distinct from whether the raw snapshot file itself keeps being served through a detail view.

**Replacement.** A new `sources` row, approved through the same §4 process, never a reuse of the withdrawn row's `id`. Lineage runs old→new: the withdrawn row's `superseded_by_source_id` points at the new row's `id`. Evidence required: the same §4 evidence as any new registry row, plus an editorial note naming the withdrawn source it replaces and confirming that claims/citations which depended on it have been reviewed — not necessarily regenerated, but reviewed — for continued accuracy. Existing citations against the withdrawn source are never rewritten to point at the replacement; only new claims/citations may cite it going forward.

## 9. Staleness

This is citation/source staleness — whether a source's live content may have drifted since retrieval — distinct from D3 artifact staleness (IDK-207's personalization-snapshot mismatch driven by profile/evidence/provider/cache-key changes). The two are not wired together today; this section defines only the source side, leaving D3 mechanics to IDK-207/IDK-404, consistent with the ticket's exclusion of "cache-key/staleness mechanics for generated content" from IDK-003's scope.

**Detection.** Both tiers store a `content_hash` (Tier A from the persisted body, Tier B from the in-memory-hashed, discarded body). A fresh retrieval whose hash differs from the most recent `source_snapshots.content_hash` means drift. Detection runs on a **180-day re-check cadence** for every `available` source, or immediately on crossing the §8 `unavailable` threshold, or on any explicit content-owner-initiated re-retrieval. A mismatch never overwrites the prior row — `source_snapshots` is immutable (`trg_source_snapshots_no_update`/`_no_delete`/`_no_insert_replace`) — it creates a new snapshot; every citation keeps pointing at the specific snapshot it referenced.

**What a stale citation may claim.** Only what it asserted as of its recorded `retrieved_at` timestamp — a historical fact about the source at that time — never the source's current live state, without that timestamp visibly attached (§7 field 4) and, once a newer conflicting snapshot exists, a visible staleness indicator. This mirrors D3's "generated before your correction — regenerate?" pattern (IDK-207) applied to the source side.

## 10. What this policy forbids

- Citing any source outside §4's approved registry once populated; using any §5.1 row before it clears its own legal review under a new registry version.
- Full-body local storage beyond the approved tier: no persisted body for Tier B; no Tier A snapshot over 10 MiB.
- Any inline verbatim excerpt beyond 400 characters per citation, regardless of tier.
- Any automatic `withdrawn` transition, ever; any automatic `unavailable` transition from fewer than 3 consecutive failures spanning under 72 hours.
- Automatic reinstatement of a withdrawn source to `available` — reinstatement is always a new registry row.
- Continued serving of a stored full-body snapshot after a `license-revoked`/`license-changed-incompatible` withdrawal.
- Any §5.2 forbidden-class source becoming a `sources` row, regardless of any license it individually carries.
- Recording a model's own generated output as a `sources` row or citing it as a claim's support.
- Rendering a citation without publisher, title, and canonical URL inline, or deferring attribution to a footer or separate page.
- Presenting a stale citation (§9) as reflecting a source's current state without its retrieval timestamp and, where applicable, a staleness indicator.

## 11. `sources.license_status` and `sources.availability_status` vocabulary

`availability_status` — unchanged CHECK constraint in `provenance/models.py`:

| Value | Meaning fixed by this policy |
| --- | --- |
| `available` | Default state for an approved, currently retrievable source. |
| `unavailable` | Transient, reversible; entered automatically only per §8's 3-attempt/72-hour rule; never by editorial action. |
| `withdrawn` | Terminal-for-new-use; entered only by explicit editorial action; always carries a `withdrawal_reason`. |

`license_status` — today free text with only a non-blank CHECK; this policy fixes the closed **production** vocabulary, to be enforced by a new CHECK (§12):

| Value | Meaning |
| --- | --- |
| `approved-open-license` | The named §4 license permits full local snapshot storage (§6 Tier A limits) and inline quotation up to the excerpt cap. |
| `approved-link-only` | Linking and metadata citation only; no body persisted or quoted beyond the source's own title/heading text. |

`fixture-approved` — the value every current test fixture uses (e.g. `server/tests/integration/test_generated_content_api.py`, line 233) — is synthetic and must never appear on a production row.

`withdrawal_reason` (new nullable column, required when `availability_status = 'withdrawn'`):

| Value | Meaning |
| --- | --- |
| `license-revoked` | The relied-on license basis was withdrawn by the publisher. |
| `license-changed-incompatible` | The publisher changed terms to a basis this policy does not approve. |
| `publisher-retracted` | The publisher removed/retracted the content, independent of license. |
| `factually-superseded` | Confirmed outdated/incorrect and unsuitable for continued citation. |
| `registry-declined` | Editorial decision the class should no longer be trusted, independent of the other reasons. |

`source_snapshots.status` — unchanged (`available`, `unavailable`, `withdrawn`, `failed`); not altered by this policy.

## 12. Required removal and implementation evidence

None of the following exists today; it is the evidence IDK-201/IDK-207/IDK-404/IDK-408 (or a dedicated `provenance` follow-up ticket) must supply before any real source is cited in production, per §1's stop point:

1. Add a CHECK on `sources.license_status` enumerating exactly `approved-open-license`/`approved-link-only`, plus nullable `withdrawal_reason` (CHECK-constrained to §11's five values, required exactly when `withdrawn`) and `superseded_by_source_id` columns (`provenance/models.py`, `SourceRow`, with an Alembic migration).
2. Add a repository update path for source status/reason/replacement. `SqlAlchemySourceRepository` (`provenance/repository.py`, lines 40–70) exposes `add_source`/`get_source`/`list_sources` only — no `update_source` exists, so no code path can transition a source's status today.
3. Branch `HttpSourceRetrievalAdapter.retrieve` (`provenance/adapters.py`) on `license_status`: persist the full body only for `approved-open-license`; compute and discard the body, persisting only the hash, for `approved-link-only`.
4. Add the license-revocation full-body purge path (a new function beside `remove_unreferenced_snapshots`), triggered by `withdrawal_reason` in (`license-revoked`, `license-changed-incompatible`).
5. Add 400-character excerpt-length validation to `CitationPayload`/`ClaimPayload` (`api/provider_runtime.py`).
6. Add the automatic 3-attempt/72-hour `unavailable` transition, and its reset-on-success, to `run_source_retrieval_job` (`provenance/service.py`); today a failed retrieval leaves `availability_status` untouched entirely, with no consecutive-failure counter at all.
7. Add a real production registry-population path — a seed/publish step, analogous to D1's offline canonical publisher, inserting `sources` rows attributed to the content-owner/legal-reviewer role — replacing the test-only `add_source` call sites (`test_generated_content_api.py`, `test_interview_api.py`, `test_notebook_review_api.py`) as the only current source of `sources` rows.
8. Update the Sources sub-view and Reports/Evidence provenance rendering (`src/selected/core/CorePages.tsx`, lines 543–552 and 997–1022) to render canonical URL as a link, retrieval timestamp, resolved license identifier, and version label per §7, and distinct `withdrawn`/`unavailable` copy per §8 instead of today's identical string.
9. Add the 180-day (or failure-triggered) staleness re-check job (§9) and the 20-per-source retained-snapshot janitor (§6); neither exists today.

## 13. Known enforcement gaps

- Every `sources` row in the codebase today is a test fixture with `license_status = "fixture-approved"`, `origin = "fixture"`; no production source has ever been registered — matching the IDK-003 ticket's "no source is marked approved" criterion exactly.
- `HttpSourceRetrievalAdapter` cannot honor a link-only tier: it downloads and permanently stores the entire response body (up to 10 MiB) for any approved `canonical_url` regardless of `license_status`. The moment a real Tier B source existed, retrieving it today would over-retain content the license does not permit storing.
- No code path can transition `availability_status` at all; the only way a source's status changes today would be a direct database write outside the domain layer, which this policy forbids.
- `unavailable` and `withdrawn` render with identical copy in both places the frontend surfaces them (`CorePages.tsx` lines 549 and 1021), contradicting §8's requirement that they read as distinguishable facts.
- Nothing purges a full-body snapshot on a license event; `remove_unreferenced_snapshots` removes a blob only once zero citations reference it — a different condition from "this license no longer permits storing it."
- Attribution as rendered omits four of §7's six fields: canonical URL as a link, retrieval timestamp, resolved license identifier, and version label are present in `SourceResponse`/`SourceSnapshotResponse` (`api/contracts.py`, lines 1134–1155) but read by neither frontend site.
- Source withdrawal is not one of D3's six cache-key components and is not an IDK-207 key-changing event today, so withdrawal does not automatically flag prior generated content as stale; only the client-computed citation banner reflects it.
- `owner_role_grants.role` (`learner`, `designated_editorial_approver`) has no distinct value for "content owner / legal reviewer"; the single local owner may act in both capacities, but no role attribution records which capacity a given `sources`-row approval was made under, unlike D1's explicit grant for canonical publication.

These gaps must close and be independently verified before production activation; this document's approval, if granted, resolves the policy question only, mirroring IDK-010 §12's stop-point pattern.

## 14. Change control

`source-policy-v1` is immutable once approved. Adding or removing a registry row, changing a tier, the excerpt cap, the automatic-`unavailable` threshold, or the `withdrawal_reason` vocabulary requires a new decision version carrying the same content-owner/legal-reviewer approval. Existing `claims`/`citations` retain the license/tier basis that applied at their `source_snapshots.retrieved_at` timestamp even if a later version changes or withdraws that source — no retroactive relicensing of a citation already made. Removing a source from the registry never deletes or edits an existing citation of it; it only stops new citations against it going forward, exactly as §8's `withdrawn` state already requires.

## 15. Approval record

| Approver | Role | Date | Decision | Version | Basis |
| --- | --- | --- | --- | --- | --- |
| MVP local owner | Content owner (content-owner capacity only; not a legal reviewer) | 2026-08-14 | Approved without changes, as product policy | 1.0 | Sections 1–14 and the project implementation request |

The approval settles the policy question: the tier model, the snapshot/cache/excerpt limits, the attribution contract, the withdrawal/replacement state machine, the closed status vocabularies, and the §5.2 denial list are now this product's rules.

It clears no source for use. Three things specifically remain open, and approving this document did not close any of them:

1. **The legal-reviewer capacity was not exercised.** PRD §13 names the approver role as "content owner / legal reviewer". Only the content-owner half is recorded above. Every license characterization in §4 is engineering research against publishers' own published terms, not an attorney's opinion, exactly as the lead paragraph states.
2. **The Spring Framework / Spring Boot row's legal gate is still Required** (§4). It may not be used until someone confirms the `docs.spring.io` pages in question are still generated from the Apache-2.0 repository, separately from Broadcom's site-level terms.
3. **Every §5.1 row remains unapproved.** This document's approval explicitly does not clear individually authored blogs, company engineering blogs, or Wikipedia.

§1's stop point therefore still holds in practice: no real source may be cited in production content until §12's implementation evidence exists and the gates above are cleared. Approval resolved the policy, not the readiness.

## 16. Approval statement

The content owner recorded:

`Approved IDK-003 source-policy-v1 — registry, snapshot/cache/excerpt rules, attribution contract, and withdrawal/replacement state machine — in sections 1–14 without changes.`

Recorded as a named deviation from that sentence: the approver acted in the content-owner capacity only. The legal-reviewer confirmation that §4's Spring row and all of §5.1 require has not been obtained, and this approval does not substitute for it.
