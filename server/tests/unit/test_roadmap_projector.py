from __future__ import annotations

import random

import pytest

from yuno.modules.roadmap.domain import (
    InvalidOrderConstraintError,
    LearnerCorrection,
    LearningClassification,
    OverlayEntry,
    OverlayEntryType,
    RoadmapRelation,
    RoadmapTopic,
    project_roadmap,
    validate_order_constraint,
)


def _topic(stable_id: str) -> RoadmapTopic:
    return RoadmapTopic(
        stable_id,
        stable_id.title(),
        "Java",
        ("core",),
        "Senior",
        "implement",
        "Implementation",
    )


def test_projection_is_permutation_invariant_and_lexically_breaks_ties() -> None:
    original = [
        _topic("topic-z"),
        _topic("topic-a"),
        _topic("topic-m"),
        _topic("topic-b"),
    ]
    relations = [RoadmapRelation("topic-a", "topic-z")]
    expected = ("topic-a", "topic-b", "topic-m", "topic-z")
    versions: set[str] = set()
    rng = random.Random(106)
    for _ in range(100):
        shuffled = original[:]
        rng.shuffle(shuffled)
        projection = project_roadmap(
            graph_version_id="graph-v1",
            topics=shuffled,
            prerequisite_relations=relations,
        )
        assert tuple(item.stable_id for item in projection.topics) == expected
        versions.add(projection.projection_version)
    assert len(versions) == 1


def test_skip_depth_and_correction_annotate_without_hiding_or_overwriting_recommendation() -> (
    None
):
    entries = (
        OverlayEntry(
            "skip",
            "owner",
            "goal",
            "overlay",
            "graph-v1",
            "topic-a",
            OverlayEntryType.SKIP,
            {"skipped": True},
            None,
            "learner",
            "2026-01-01T00:00:00Z",
        ),
        OverlayEntry(
            "depth",
            "owner",
            "goal",
            "overlay",
            "graph-v1",
            "topic-a",
            OverlayEntryType.DEPTH,
            {"depth": "Internals"},
            None,
            "learner",
            "2026-01-01T00:00:01Z",
        ),
    )
    corrections = (
        LearnerCorrection(
            "c",
            "owner",
            "goal",
            "topic-a",
            "correction",
            "partial",
            "I need practice",
            "2026-01-01T00:00:02Z",
        ),
    )
    result = project_roadmap(
        graph_version_id="graph-v1",
        topics=(_topic("topic-a"),),
        prerequisite_relations=(),
        overlay_entries=entries,
        corrections=corrections,
        transferred_evidence_topic_ids=("topic-a",),
    )
    topic = result.topics[0]
    assert topic.is_skipped is True
    assert topic.recommended_depth == "Implementation"
    assert topic.depth_override == "Internals"
    assert topic.classification is LearningClassification.PARTIAL
    assert topic.has_transferred_evidence is True


def test_order_constraint_rejects_prerequisite_reversal_and_indirect_cycle() -> None:
    topics = (_topic("a"), _topic("b"), _topic("c"))
    canonical = (RoadmapRelation("a", "b"),)
    with pytest.raises(InvalidOrderConstraintError, match="prerequisite"):
        validate_order_constraint(topics, canonical, (), RoadmapRelation("b", "a"))
    with pytest.raises(InvalidOrderConstraintError, match="cycle"):
        validate_order_constraint(
            topics, canonical, (RoadmapRelation("b", "c"),), RoadmapRelation("c", "a")
        )
