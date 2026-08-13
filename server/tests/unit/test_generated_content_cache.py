"""IDK-207 deterministic D3 cache-key and personalization boundaries."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from yuno.modules.learning_content.domain import (
    ArtifactState,
    D3CacheKey,
    GeneratedArtifact,
    GenerateRequest,
    StaleReason,
    TopicLayer,
    d3_cache_key_hash,
    evaluate_artifact_staleness,
)
from yuno.modules.learning_content.service import _validate_generated_content_limits
from yuno.shared.domain.errors import DomainValidationError, GeneratedContentLimitError


def _key() -> D3CacheKey:
    return D3CacheKey(
        canonical_graph_version="graph-v1",
        topic_id="topic-1",
        goal_id="goal-1",
        layer=TopicLayer.ESSENTIAL,
        topic_mapped_approved_imports_hash="imports-v1",
        prompt_template_version="prompt-v1",
    )


def test_generated_content_limits_are_utf8_exact_counted_and_owner_scoped() -> None:
    artifact = GeneratedArtifact(
        "artifact-1",
        "owner-1",
        "goal-1",
        "graph-v1",
        "topic-1",
        TopicLayer.ESSENTIAL,
        "lesson-layer",
        "imports-v1",
        "prompt-v1",
        "key-v1",
        ArtifactState.GENERATING,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        False,
        1,
        "now",
        "now",
        None,
    )
    counts = {"owner-1": 0, "owner-2": 9}
    uow = SimpleNamespace(
        learning_content=SimpleNamespace(
            count_live_artifacts=lambda owner_id: counts.get(owner_id, 0)
        )
    )
    _validate_generated_content_limits(
        uow,
        "owner-1",
        artifact,
        "éé",
        max_body_bytes=4,
        retained_owner_limit=1,
    )
    with pytest.raises(GeneratedContentLimitError):
        _validate_generated_content_limits(
            uow,
            "owner-1",
            artifact,
            "ééx",
            max_body_bytes=4,
            retained_owner_limit=1,
        )
    counts["owner-1"] = 1
    with pytest.raises(GeneratedContentLimitError):
        _validate_generated_content_limits(
            uow,
            "owner-1",
            artifact,
            "x",
            max_body_bytes=4,
            retained_owner_limit=1,
        )


def test_d3_cache_key_is_exactly_the_six_required_components() -> None:
    baseline = _key()
    expected = d3_cache_key_hash(baseline)

    variants = (
        replace(baseline, canonical_graph_version="graph-v2"),
        replace(baseline, topic_id="topic-2"),
        replace(baseline, goal_id="goal-2"),
        replace(baseline, layer=TopicLayer.PRODUCTION),
        replace(baseline, topic_mapped_approved_imports_hash="imports-v2"),
        replace(baseline, prompt_template_version="prompt-v2"),
    )
    assert all(d3_cache_key_hash(variant) != expected for variant in variants)
    assert len({d3_cache_key_hash(variant) for variant in variants}) == len(variants)

    for field in baseline.__dataclass_fields__:
        value = getattr(baseline, field)
        blank = replace(baseline, **{field: "" if isinstance(value, str) else value})
        if isinstance(value, str) and field != "layer":
            with pytest.raises(DomainValidationError, match="must be non-blank"):
                d3_cache_key_hash(blank)


def test_provider_profile_and_evidence_are_snapshot_inputs_not_cache_key_inputs() -> (
    None
):
    baseline = GenerateRequest(
        owner_id="owner-1",
        goal_id="goal-1",
        topic_id="topic-1",
        layer=TopicLayer.ESSENTIAL,
        graph_version="graph-v1",
        imports_hash="imports-v1",
        prompt_template_version="prompt-v1",
        profile_hash="profile-v1",
        evidence_state_hash="evidence-v1",
    )

    def key(request: GenerateRequest) -> D3CacheKey:
        return D3CacheKey(
            request.graph_version,
            request.topic_id,
            request.goal_id,
            request.layer,
            request.imports_hash,
            request.prompt_template_version,
        )

    expected = d3_cache_key_hash(key(baseline))
    assert (
        d3_cache_key_hash(key(replace(baseline, profile_hash="profile-v2"))) == expected
    )
    assert (
        d3_cache_key_hash(key(replace(baseline, evidence_state_hash="evidence-v2")))
        == expected
    )


def test_staleness_comparison_is_pure_and_never_mutates_visible_cached_content() -> (
    None
):
    artifact = GeneratedArtifact(
        "artifact-1",
        "owner-1",
        "goal-1",
        "graph-v1",
        "topic-1",
        TopicLayer.ESSENTIAL,
        "lesson-layer",
        "imports-v1",
        "prompt-v1",
        "key-v1",
        ArtifactState.READY,
        "Visible cached body",
        "visible-body-hash",
        "snapshot-1",
        "job-1",
        "attempt-1",
        "job-1",
        None,
        None,
        False,
        1,
        "2026-08-12T12:00:00.000000Z",
        "2026-08-12T12:00:00.000000Z",
        "2026-08-12T12:00:00.000000Z",
    )
    before = (artifact.id, artifact.body, artifact.body_hash)

    personalization = evaluate_artifact_staleness(
        "key-v1", "key-v1", "snapshot-v1", "snapshot-v2"
    )
    assert personalization == (StaleReason.PERSONALIZATION_SNAPSHOT_MISMATCH,)
    assert (artifact.id, artifact.body, artifact.body_hash) == before

    key_changed = evaluate_artifact_staleness(
        "key-v1", "key-v2", "snapshot-v1", "snapshot-v1"
    )
    assert key_changed == (StaleReason.CACHE_KEY_CHANGED,)
    assert (artifact.id, artifact.body, artifact.body_hash) == before

    both = evaluate_artifact_staleness("key-v1", "key-v2", "snapshot-v1", "snapshot-v2")
    assert both == (
        StaleReason.CACHE_KEY_CHANGED,
        StaleReason.PERSONALIZATION_SNAPSHOT_MISMATCH,
    )
