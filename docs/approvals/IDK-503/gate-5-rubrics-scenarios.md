# IDK-503 gate 5 — Representative assessment scenarios and rubric versions

- Gate: HND-03 scenario review; DEP-03 layer-reversal regression review
- Reviewer role required: designated editorial approver
- Inspection date: 2026-08-14
- Decision under review: docs/decisions/IDK-009-assessment-and-derived-state.md, approved as decision version 1.0 on 2026-08-13 (content/assessment owner; see its §12 approval table)
- Implementing tickets: IDK-201 (layers/DEP-03), IDK-204 (evidence/evaluation/rubric registry), IDK-205 (derived-state-v1), IDK-405 (hands-on/HND-03), IDK-302, IDK-303
- Disposition: blocking-finding
- Attestation: pending — designated editorial approver has not signed this gate.

## Inspected artifacts

| Artifact | What it is | How inspected |
| --- | --- | --- |
| `server/yuno.db` | Local dev SQLite DB | `sqlite3 yuno.db "SELECT * FROM rubrics;"` / `rubric_dimensions` — both tables return zero rows |
| `server/.e2e.db` | E2E-run SQLite DB | Same queries against `.e2e.db` — both tables return zero rows |
| `server/src/yuno/modules/hands_on/models.py:30-32` | `HandsOnWorkRow` schema | Read; `CheckConstraint("scenario_status IN ('fixture')")` |
| `server/src/yuno/modules/evidence_evaluation/domain.py:11-32` | `TransferClassification`, `RubricStatus`, `AssessmentState`, `DimensionOutcome` enums | Read |
| `server/src/yuno/modules/evidence_evaluation/domain.py:340-420` | Per-topic classification/derivation logic | Read |
| `server/src/yuno/modules/learning_content/domain.py:334-370` | `MentalModelLayer` / `validate_layer_progression` | Read |
| `server/tests/unit/test_learning_content.py:36-52` | `test_later_layer_may_refine_but_never_reverse_an_earlier_claim` | Read + ran `uv run --directory server pytest tests/unit/test_learning_content.py -k reverse -q` → 1 passed |
| `server/tests/unit/test_derived_progress.py:97-102` | `test_ambiguity_unresolved_has_exactly_zero_metric_delta`, `assert "completion" not in repr(expected).lower()` | Read + ran `uv run --directory server pytest tests/unit/test_derived_progress.py -q` → 5 passed |
| `server/tests/integration/test_evidence_evaluation.py:84-116` | Rubric fixture used by evaluation tests | Read |
| `server/src/yuno/migrations/versions/e205f6a2c4d1_derived_progress.py:34`, `e10d1a0c0100_policy_1_0_body_separation_and_retention.py:575-587`, `6834679f0af4_learner_roadmap_overlays.py:40,127,339` | Persisted classification CHECK constraints | Read |
| Repo-wide grep for `assessment-scenarios-v1`, `hands-on-rubric-v1`, `practice-rubric-v1`, `mock-rubric-v1`, the 12 `scenario_id`s in IDK-009 §4, the 6 stable dimension IDs in IDK-009 §6, `not-demonstrated`, `critical dimension` | Confirms shipped presence/absence of the approved content identifiers and vocabulary | `rg` across `/Users/abhishekthakur/Developer/i-dont-know` and `server/` |

## Findings

| # | Decision requirement | Shipped reality (with citation) | Verdict |
| --- | --- | --- | --- |
| 1 | Three approved rubric manifests (`hands-on-rubric-v1`, `practice-rubric-v1`, `mock-rubric-v1`) with six named stable dimensions, loaded and version-gated (IDK-009 §1, §6; ticket §11 IDK-204) | No row in `rubrics` or `rubric_dimensions` in `server/yuno.db` or `server/.e2e.db` (both empty). No occurrence anywhere in `server/` of the strings `hands-on-rubric-v1`, `practice-rubric-v1`, `mock-rubric-v1`, or any of the six stable dimension IDs (`factual-and-mechanical-correctness`, `assumptions-and-constraints`, `solution-and-system-reasoning`, `trade-offs-and-consequences`, `failures-and-recovery`, `verification-and-defensibility`) — confirmed by repo-wide `rg`. The only shipped rubric content is a test fixture at `server/tests/integration/test_evidence_evaluation.py:84-115`: `Rubric(..., "fixture-v0", RubricStatus.FIXTURE, ...)` with two dimensions, `reasoning` and `trade-offs`. | not shipped |
| 2 | Twelve approved scenario records (`mid-order-idempotency-initial-v1` … `staff-multiregion-evolution-mock-v1`) with content revision `idk009-v1-r1` (IDK-009 §4-§5; ticket §11 line "IDK-503: manually review all twelve shipped records") | No `scenario_id` field exists anywhere in `server/src` or `server/tests`; none of the twelve approved scenario IDs appear anywhere in the repo (`rg` returned zero hits outside the decision doc itself). `server/src/yuno/modules/hands_on/models.py:30-32` — `HandsOnWorkRow.__table_args__` has `CheckConstraint("scenario_status IN ('fixture')")`, i.e. the schema literally forbids any non-`'fixture'` scenario status. There is nothing to review for representativeness/role-appropriateness because no approved-content record exists; what exists is architecturally placeholder ("fixture") content only. | not shipped |
| 3 | DEP-03: a later mental-model layer may refine but never reverse an earlier claim, with an inspectable regression artifact | `server/src/yuno/modules/learning_content/domain.py:334-338` (`MentalModelLayer.reverses_claim_ids`) and `:361-370` (`validate_layer_progression`, raises `DomainValidationError` on `f"{layer.layer.value} reverses earlier mental-model claims: {names}."`). Regression test `server/tests/unit/test_learning_content.py:36-52`, `test_later_layer_may_refine_but_never_reverse_an_earlier_claim`, ran green (`1 passed`). | matches |
| 4 | Ambiguity/valid-alternative: exactly zero derived-state effect for an unresolved ambiguity; a defensible trade-off is not a lesser score (IDK-009 §2, §6, §8.2) | `server/tests/unit/test_derived_progress.py:97-102`, `test_ambiguity_unresolved_has_exactly_zero_metric_delta`, ran green and asserts coverage/proficiency/retention/readiness are unchanged by an ambiguous dimension. `server/src/yuno/modules/evidence_evaluation/domain.py:352-364` computes `outcomes`/`ambiguity_only` by excluding `DimensionOutcome.AMBIGUITY_UNRESOLVED` results. However the shipped classification (`domain.py:376-390`) has no concept of a "critical dimension" (no `is_critical`/`critical_dimension` identifier anywhere in `server/` per `rg`), so it cannot implement IDK-009 §9.2's precedence rule ("Either critical dimension is `factual-correction` or `not-demonstrated` → `unverified`, precedence over every row below"); it instead treats any `FACTUAL_CORRECTION` outcome uniformly regardless of which dimension produced it. | mismatch |
| 5 | Closed five-value stored outcome vocabulary: `pass`, `trade-off`, `factual-correction`, `not-demonstrated`, `ambiguity-unresolved` (IDK-009 §6) | `server/src/yuno/modules/evidence_evaluation/domain.py:29-33` — `DimensionOutcome` enum has only four members: `PASS`, `TRADE_OFF`, `FACTUAL_CORRECTION`, `AMBIGUITY_UNRESOLVED`. `not-demonstrated` does not exist anywhere in `server/` (`rg -in "not.demonstrated"` → zero hits). | not shipped |
| 6 | No inference becomes completion anywhere in shipped code (IDK-009 §2: "None means completion, mastery, hiring probability, or a job/interview guarantee") | `server/src/yuno/modules/evidence_evaluation/domain.py` classification enum is `ProgressClassification` limited to `LIKELY_KNOWN`/`PARTIAL`/`UNVERIFIED`/`NEW`; `server/tests/unit/test_derived_progress.py:93` explicitly asserts `"completion" not in repr(expected).lower()`, ran green. Repo-wide `rg` for "completion"/"mastery"/"hiring" near classification/contracts code returns no hits. | matches |
| 7 | Persisted classification values are exactly `likely_known`, `partial`, `unverified`, `new` (IDK-009 §2, literal backticked strings) | Shipped value is `likely-known` (hyphen), not `likely_known` (underscore) — `server/src/yuno/modules/evidence_evaluation/domain.py:11` (`TransferClassification.LIKELY_KNOWN = "likely-known"`), `server/src/yuno/modules/roadmap/domain.py:59` (`LearningClassification.LIKELY_KNOWN = "likely-known"`), and CHECK constraints in `server/src/yuno/migrations/versions/e205f6a2c4d1_derived_progress.py:34`, `e10d1a0c0100_policy_1_0_body_separation_and_retention.py:575-587`, `6834679f0af4_learner_roadmap_overlays.py:40,127,339` all use `'likely-known'`. | mismatch |
| 8 | DEP-03 editorial reversal-regression review needs an inspectable artifact for the human reviewer | Same as row 3: `server/tests/unit/test_learning_content.py:36-52` is a concrete, runnable artifact the editorial approver can point to and re-run. | matches |

## Blocking findings

### 1. No approved rubric manifests shipped

- What is missing: `rubrics`/`rubric_dimensions` rows for `hands-on-rubric-v1`, `practice-rubric-v1`, `mock-rubric-v1` with `status = 'approved'` and the six IDK-009 §6 stable dimensions. No such rows, IDs, or dimension names exist anywhere in the codebase or either inspected database.
- Owning ticket: IDK-204 (rubric registry loading/version-gating).
- Evidence of absence: `sqlite3 server/yuno.db "SELECT * FROM rubrics;"` and the same against `server/.e2e.db` both return zero rows; repo-wide `rg` for the three rubric IDs and the six dimension IDs returns zero hits outside `docs/decisions/IDK-009-assessment-and-derived-state.md`.
- What would clear it: IDK-204 ships a migration/seed (or equivalent boot-time loader) that inserts the three `status='approved'` rubric headers and their six-dimension sets matching IDK-009 §6 verbatim, then IDK-503 re-inspects the live rows.

### 2. No approved hands-on/practice/mock scenario content shipped; schema forbids non-fixture scenario status

- What is missing: The twelve `scenario_id` records from IDK-009 §4 (e.g. `mid-order-idempotency-initial-v1`, `staff-multiregion-evolution-mock-v1`) with content revision `idk009-v1-r1`, loaded as non-fixture, review-ready content per ticket §11's line for IDK-302/IDK-303/IDK-405.
- Owning tickets: IDK-405 (hands-on, initial+delayed), IDK-302 (Practice), IDK-303 (Mock).
- Evidence of absence: no `scenario_id` field exists in `server/src/yuno/modules/hands_on/models.py` or elsewhere; `HandsOnWorkRow.__table_args__` (`server/src/yuno/modules/hands_on/models.py:30-32`) declares `CheckConstraint("scenario_status IN ('fixture')")` — the database schema currently accepts only the literal value `'fixture'` for `scenario_status`, so even if approved content existed it could not be persisted as anything other than fixture-labelled.
- What would clear it: IDK-405/IDK-302/IDK-303 ship the twelve approved scenario records (or their role/mode subset) with a real non-fixture status value, the CHECK constraint is widened to admit it, and IDK-503 confirms the shipped titles/prompts/metadata against IDK-009 §5 verbatim, quoting the persisted rows.

### 3. `not-demonstrated` outcome value is entirely unimplemented

- What is missing: The fifth member of IDK-009 §6's closed outcome vocabulary, `not-demonstrated`, used for "insufficient evidence... without making a specific false factual/mechanical claim," and used in the §9.2 classification precedence rule.
- Owning ticket: IDK-204 (evidence/evaluation domain contracts).
- Evidence of absence: `server/src/yuno/modules/evidence_evaluation/domain.py:29-33` — `DimensionOutcome` StrEnum has exactly four members (`pass`, `trade-off`, `factual-correction`, `ambiguity-unresolved`); repo-wide `rg -in "not.demonstrated"` over the whole repository returns zero hits.
- What would clear it: IDK-204 adds `NOT_DEMONSTRATED = "not-demonstrated"` to `DimensionOutcome`, wires it through the classification precedence rule (critical-dimension distinction, §9.2 row 2 and row 4), and a regression test proves the `partial` vs `unverified` split it drives.

## Notes and residual risk

- Row 4 and row 7 (critical-dimension precedence; `likely-known` vs `likely_known` string) are recorded as mismatches, not separately numbered blocking findings, because the underlying mechanism (rubric loading, five-value vocabulary) is itself unshipped per findings 1 and 3 above — fixing those will require revisiting the classification precedence and persisted-value format together. The approver should treat all of findings 1, 3, and the row-4/row-7 mismatches as one connected gap in IDK-204/IDK-205, not independent nits.
- This inspection could not evaluate HND-03 "representative vs fixture placeholder" on the merits (item 2 of the assigned task) because no approved scenario content exists to evaluate; the only shipped scenario content observed anywhere is generic test-fixture text (e.g. `server/tests/integration/test_hands_on_api.py`, `hands_on_scenario_title`/`hands_on_scenario_prompt` columns populated by test setup, not by IDK-009 §5's normative text).
- `server/yuno.db` and `server/.e2e.db` are local dev/e2e databases, not production; absence of rows there is consistent with (but does not by itself prove) absence in any deployed environment — however the schema-level CHECK constraint and repo-wide absence of the approved identifiers make deployment of approved content extremely unlikely without a corresponding code change, which was not found.
- IDK-201's ticket status is "Complete" and DEP-03 layer-reversal is genuinely shipped and tested (finding 3/8) — this is the one sub-scope of gate 5 with a clean inspectable pass.
