# `is_critical` is not exposed in any API contract or client type — recorded decision

- Date: 2026-08-15
- Raised by: IDK-503 re-run, gate 5 (`docs/approvals/IDK-503-rerun-2026-08-15/gate-5-rubrics-scenarios.md`), "Notes and residual risk" — *"`is_critical` is not API-surfaced… the approver should know it cannot currently be inspected or corrected via any API or UI."*
- Decision: **do not surface it.** No contract field, no client type, no rendered control.
- This record grants no approval and changes no approved decision document. It records an engineering decision so the next IDK-503 round does not reopen it as an unexamined gap.

## What is actually true today, verified

- `grep -c is_critical server/openapi.json src/shared/api/schema.d.ts` → `0` and `0`. A repo-wide grep across `src/` returns nothing. The gate's observation is correct.
- `AssessmentDimensionResponse` (`server/src/yuno/api/contracts.py:1016-1021`) carries `dimension_id`, `outcome`, `rationale`, `evidence_refs` — the domain record's fields minus `is_critical`.
- `is_critical` exists in exactly two places in the domain: a derived property on `RubricDimension` (`server/src/yuno/modules/evidence_evaluation/domain.py:622-629`) and a denormalized field on `AssessmentDimensionResult` (`domain.py:705-722`), persisted as `assessment_dimension_results.is_critical` (`server/src/yuno/modules/evidence_evaluation/models.py:401`). `rubric_dimensions` has no such column, deliberately (`models.py:229-232`).
- It is read by exactly one consumer: `derive_progress`'s IDK-009 §9.2 precedence check (`domain.py:378`).

## Why it is not surfaced

1. **It is a constant of the decision, not authored data.** IDK-009 §6 (`docs/decisions/IDK-009-assessment-and-derived-state.md:58`) fixes criticality per *stable* dimension — "The first two common dimensions are critical" — invariant across all three rubric versions. `CRITICAL_STABLE_DIMENSION_IDS` (`domain.py:601-609`) is that mapping. There is nothing an API could let a caller set that would not be a way to contradict IDK-009.

2. **"Cannot be corrected via any API or UI" is the intended property, not a gap.** Making criticality settable would let a rubric manifest omit it or get it wrong, which is precisely the failure mode `models.py:229-232` and `domain.py:600-606` say the derived-property design exists to prevent. A correction surface here would be a defect.

3. **The outcome it drives is already exposed.** The learner-visible artifact of the §9.2 precedence rule is the classification itself, which ships: `ProgressClassification` plus `definition`, `supporting_evidence_refs` and `uncertainty` on `ProgressDimensionResponse` and `LearningStateExplanationResponse` (`contracts.py:533-545`). A per-dimension boolean would add an input to a derivation whose output is already surfaced with its own explanation fields.

4. **Rendering it would require copy that does not exist.** No approved learner-facing string for a "critical dimension" label appears in IDK-009 or IDK-004. Shipping a field the UI cannot legally label is a speculative surface, which `AGENTS.md` rules out.

## What this decision does not claim

It does not claim a learner can today read *why* an assessment that is positive on four dimensions still classifies as `unverified`. The shipped mechanism for that is the `uncertainty` text on the explanation responses. Whether that text actually names the responsible critical dimension **cannot be verified in this tree**: `rubrics`, `rubric_dimensions` and `hands_on_work` all hold zero rows (`sqlite3 -readonly server/yuno.db "SELECT count(*) …"` → `0` on all three; that file is at `4747447ccaa3`, behind head, and is a read-only review artifact), and no approved rubric manifest exists anywhere in the tree (IDK-503 B11). This is an open question owned by IDK-204, not something this record settles.

## Revisit trigger

Reopen this decision when IDK-204 ships the approved rubric manifests and any rubric-inspection surface. A manifest author cannot set criticality and must still be able to see which two stable dimensions carry it; that is a plausible read-only surface, and it is the first point at which exposing the flag would have a real consumer rather than a hypothetical one.
