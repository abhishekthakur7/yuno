from dataclasses import replace
from random import Random

import pytest

from yuno.modules.evidence_evaluation.domain import (
    Assessment,
    AssessmentDimensionResult,
    AssessmentState,
    DimensionOutcome,
    Evidence,
    ProgressClassification,
    ProgressCorrection,
    ProgressEvidence,
    ProgressTransfer,
    derive_progress,
)

NOW = "2026-08-12T12:00:00.000000Z"


def _item(topic: str, suffix: str, outcome: DimensionOutcome, *, ambiguous=False, is_critical=False):
    evidence = Evidence(f"e-{suffix}", "owner", "goal", topic, "fixture", "implement", suffix, "summary", "test", "2026-08-01T00:00:00.000000Z")
    assessment = Assessment(f"a-{suffix}", "owner", "goal", evidence.id, None, "rubric", "fixture-v0", AssessmentState.AMBIGUITY_UNRESOLVED if ambiguous else AssessmentState.FEEDBACK_READY, "task", "implement", None, None, "fixture", (), (), (), (), (), (), (), "feedback", None, None, (), (), None, False, "2026-08-01T00:00:00.000000Z")
    dimension = AssessmentDimensionResult(f"d-{suffix}", "owner", "goal", assessment.id, "rd", outcome, "why", (evidence.id,), is_critical)
    return ProgressEvidence(evidence, assessment, (dimension,))


def _two_dimension_item(
    topic: str,
    suffix: str,
    *,
    critical_outcome: DimensionOutcome,
    noncritical_outcome: DimensionOutcome,
):
    """One assessment with two clear dimension results: `rd-critical`
    (`is_critical=True`) and `rd-noncritical` (`is_critical=False`), for
    proving IDK-009 section 9.2's critical-dimension precedence rule.
    """
    evidence = Evidence(f"e-{suffix}", "owner", "goal", topic, "fixture", "implement", suffix, "summary", "test", "2026-08-01T00:00:00.000000Z")
    assessment = Assessment(f"a-{suffix}", "owner", "goal", evidence.id, None, "rubric", "fixture-v0", AssessmentState.FEEDBACK_READY, "task", "implement", None, None, "fixture", (), (), (), (), (), (), (), "feedback", None, None, (), (), None, False, "2026-08-01T00:00:00.000000Z")
    dimensions = (
        AssessmentDimensionResult(f"d-{suffix}-critical", "owner", "goal", assessment.id, "rd-critical", critical_outcome, "why", (evidence.id,), True),
        AssessmentDimensionResult(f"d-{suffix}-noncritical", "owner", "goal", assessment.id, "rd-noncritical", noncritical_outcome, "why", (evidence.id,), False),
    )
    return ProgressEvidence(evidence, assessment, dimensions)


def test_not_demonstrated_is_the_fifth_closed_outcome_vocabulary_member():
    assert {member.value for member in DimensionOutcome} == {
        "pass",
        "trade-off",
        "factual-correction",
        "not-demonstrated",
        "ambiguity-unresolved",
    }


def test_critical_dimension_negative_outcome_forces_unverified_over_partial():
    """IDK-009 section 9.2: a `factual-correction`/`not-demonstrated` result
    on a non-critical dimension only pulls the cell to `partial` (row 4),
    but the same outcome on a critical dimension forces `unverified` (row
    2), taking precedence over every row below it -- even though both cases
    have a clear positive result elsewhere in the same assessment.
    """
    noncritical_not_demonstrated = derive_progress(
        "goal", ("one",),
        (_two_dimension_item("one", "nc-nd", critical_outcome=DimensionOutcome.PASS, noncritical_outcome=DimensionOutcome.NOT_DEMONSTRATED),),
        (), (), NOW, "fixture-v0",
    )
    assert noncritical_not_demonstrated.learning_states[0].classification is ProgressClassification.PARTIAL

    critical_not_demonstrated = derive_progress(
        "goal", ("one",),
        (_two_dimension_item("one", "c-nd", critical_outcome=DimensionOutcome.NOT_DEMONSTRATED, noncritical_outcome=DimensionOutcome.PASS),),
        (), (), NOW, "fixture-v0",
    )
    assert critical_not_demonstrated.learning_states[0].classification is ProgressClassification.UNVERIFIED

    noncritical_factual_correction = derive_progress(
        "goal", ("one",),
        (_two_dimension_item("one", "nc-fc", critical_outcome=DimensionOutcome.PASS, noncritical_outcome=DimensionOutcome.FACTUAL_CORRECTION),),
        (), (), NOW, "fixture-v0",
    )
    assert noncritical_factual_correction.learning_states[0].classification is ProgressClassification.PARTIAL

    critical_factual_correction = derive_progress(
        "goal", ("one",),
        (_two_dimension_item("one", "c-fc", critical_outcome=DimensionOutcome.FACTUAL_CORRECTION, noncritical_outcome=DimensionOutcome.PASS),),
        (), (), NOW, "fixture-v0",
    )
    assert critical_factual_correction.learning_states[0].classification is ProgressClassification.UNVERIFIED

    # Same-cell proficiency rollup (per-topic minimum) carries the split too.
    baseline = derive_progress(
        "goal", ("one",),
        (_two_dimension_item("one", "base", critical_outcome=DimensionOutcome.PASS, noncritical_outcome=DimensionOutcome.PASS),),
        (), (), NOW, "fixture-v0",
    )
    assert baseline.proficiency.classification is ProgressClassification.LIKELY_KNOWN
    assert noncritical_not_demonstrated.proficiency.classification is ProgressClassification.PARTIAL
    assert critical_not_demonstrated.proficiency.classification is ProgressClassification.UNVERIFIED


def test_fixture_derivation_is_pure_under_randomized_replay_order():
    for seed in range(25):
        rng = Random(seed)
        items = []
        for index in range(rng.randint(1, 12)):
            topic = rng.choice(("one", "two"))
            item = _item(topic, f"{seed}-{index}", rng.choice(tuple(DimensionOutcome)))
            extra = replace(
                item.dimensions[0],
                id=f"d-extra-{seed}-{index}",
                rubric_dimension_id="rd-extra",
                outcome=rng.choice(tuple(DimensionOutcome)),
            )
            items.append(replace(item, dimensions=(item.dimensions[0], extra)))

        corrections = []
        for topic in ("one", "two"):
            predecessor = None
            for index in range(rng.randint(0, 4)):
                correction_id = f"c-{seed}-{topic}-{index}"
                corrections.append(
                    ProgressCorrection(
                        correction_id,
                        "owner",
                        "goal",
                        topic,
                        rng.choice(("correction", "confirmation", "gap")),
                        rng.choice(tuple(ProgressClassification)).value,
                        "randomized replay fixture",
                        f"2026-08-{index + 1:02d}T00:00:00.000000Z",
                        predecessor,
                    )
                )
                predecessor = correction_id

        original_items = tuple(items)
        original_corrections = tuple(corrections)
        input_snapshot = repr((original_items, original_corrections))
        expected = derive_progress(
            "goal",
            ("one", "two"),
            original_items,
            original_corrections,
            (),
            NOW,
            "fixture-v0",
        )
        rng.shuffle(items)
        rng.shuffle(corrections)
        items = [replace(item, dimensions=tuple(reversed(item.dimensions))) for item in items]
        replay = derive_progress(
            "goal",
            ("two", "one"),
            tuple(items),
            tuple(corrections),
            (),
            NOW,
            "fixture-v0",
        )
        assert replay == expected
        assert repr((original_items, original_corrections)) == input_snapshot
    assert set(ProgressClassification) == {
        ProgressClassification.LIKELY_KNOWN, ProgressClassification.PARTIAL,
        ProgressClassification.UNVERIFIED, ProgressClassification.NEW,
    }
    assert "completion" not in repr(expected).lower()


def test_ambiguity_unresolved_has_exactly_zero_metric_delta():
    baseline = derive_progress("goal", ("known", "unknown"), (_item("known", "ok", DimensionOutcome.PASS),), (), (), NOW, "fixture-v0")
    ambiguous = derive_progress("goal", ("known", "unknown"), (_item("known", "ok", DimensionOutcome.PASS), _item("unknown", "amb", DimensionOutcome.AMBIGUITY_UNRESOLVED, ambiguous=True)), (), (), NOW, "fixture-v0")
    assert ambiguous.coverage == baseline.coverage
    assert ambiguous.proficiency == baseline.proficiency
    assert ambiguous.retention == baseline.retention
    assert ambiguous.readiness == baseline.readiness


def test_standing_correction_is_first_class_until_explicitly_superseded():
    first = ProgressCorrection("c1", "owner", "goal", "one", "correction", "likely-known", "learner says so", "2026-08-01T00:00:00.000000Z", None)
    initial = derive_progress("goal", ("one",), (), (first,), (), NOW, "fixture-v0")
    assert initial.learning_states[0].classification is ProgressClassification.LIKELY_KNOWN
    second = ProgressCorrection("c2", "owner", "goal", "one", "gap", "new", "changed", "2026-08-02T00:00:00.000000Z", "c1")
    changed = derive_progress("goal", ("one",), (), (first, second), (), NOW, "fixture-v0")
    assert changed.learning_states[0].classification is ProgressClassification.NEW
    with pytest.raises(ValueError, match="linear chain"):
        derive_progress("goal", ("one",), (), (first, second, ProgressCorrection("c3", "owner", "goal", "one", "gap", "partial", None, "2026-08-03T00:00:00.000000Z", None)), (), NOW, "fixture-v0")


def test_advancing_now_changes_retention_without_fabricating_evidence():
    item = _item("one", "ok", DimensionOutcome.PASS)
    early = derive_progress("goal", ("one",), (item,), (), (), NOW, "fixture-v0")
    later = derive_progress("goal", ("one",), (item,), (), (), "2027-08-12T12:00:00.000000Z", "fixture-v0")
    assert early.retention.classification != later.retention.classification
    assert early.retention.supporting_evidence_refs == later.retention.supporting_evidence_refs


def test_transfer_is_derived_input_not_override_and_ambiguity_is_zero_delta():
    transfer = ProgressTransfer(
        "t1", "owner", "goal", "one", "source-evidence", ProgressClassification.PARTIAL,
        "conservative transfer", "2026-08-01T00:00:00.000000Z",
    )
    transferred = derive_progress("goal", ("one",), (), (), (transfer,), NOW, "fixture-v0")
    assert transferred.learning_states[0].classification is ProgressClassification.PARTIAL
    assert transferred.learning_states[0].supporting_evidence_refs == ("source-evidence",)
    ambiguous = derive_progress(
        "goal", ("one",),
        (_item("one", "amb-transfer", DimensionOutcome.AMBIGUITY_UNRESOLVED, ambiguous=True),),
        (), (transfer,), NOW, "fixture-v0",
    )
    assert ambiguous.coverage == transferred.coverage
    assert ambiguous.proficiency == transferred.proficiency
    assert ambiguous.readiness == transferred.readiness
    decisive = derive_progress(
        "goal", ("one",), (_item("one", "local", DimensionOutcome.FACTUAL_CORRECTION),),
        (), (transfer,), NOW, "fixture-v0",
    )
    assert decisive.learning_states[0].classification is ProgressClassification.UNVERIFIED
    old = derive_progress(
        "goal", ("one",), (), (), (transfer,), "2027-08-12T00:00:00.000000Z", "fixture-v0"
    )
    assert old.retention.classification is ProgressClassification.UNVERIFIED
