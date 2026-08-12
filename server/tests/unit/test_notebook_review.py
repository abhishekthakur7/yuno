from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from yuno.modules.notebook_review.domain import (
    FIXTURE_SCHEDULING_VERSION,
    ReviewItem,
    ReviewItemStatus,
    ReviewPromptType,
    default_review_preferences,
)
from yuno.modules.notebook_review.service import FixtureReviewScheduler
from yuno.shared.domain.errors import DomainValidationError


def test_fixture_preferences_are_optional_versioned_and_match_approved_settings() -> (
    None
):
    preferences = default_review_preferences(
        "owner-1", "goal-1", "2026-08-12T12:00:00.000000Z"
    )

    assert preferences.enabled
    assert preferences.duration_minutes == 15
    assert preferences.cadence.value == "twice-weekly"
    assert preferences.retrieval_enabled
    assert preferences.varied_context_enabled
    assert preferences.scheduling_version == FIXTURE_SCHEDULING_VERSION == "fixture-v0"
    assert preferences.row_version == 1


def test_review_prompt_and_status_domains_are_closed_and_items_are_immutable() -> None:
    assert {item.value for item in ReviewPromptType} == {
        "recall",
        "explanation",
        "application",
    }
    assert {item.value for item in ReviewItemStatus} == {
        "ready",
        "due",
        "dismissed",
        "disabled",
        "generation-failed",
        "completed",
    }

    item = ReviewItem(
        "review-1",
        "owner-1",
        "goal-1",
        "topic-1",
        "prompt-ref-1",
        ReviewPromptType.RECALL,
        "Recall the duplicate boundary.",
        "The idempotency record and business mutation commit together.",
        ReviewItemStatus.READY,
        None,
        None,
        None,
        FIXTURE_SCHEDULING_VERSION,
        None,
        1,
        "2026-08-12T12:00:00.000000Z",
        "2026-08-12T12:00:00.000000Z",
    )
    with pytest.raises(FrozenInstanceError):
        item.answer = "silently replaced"  # type: ignore[misc]

    scheduler = FixtureReviewScheduler()
    first = scheduler.schedule(
        item, "My recalled answer", "2026-08-12T12:00:00.000000Z"
    )
    replay = scheduler.schedule(
        item, "My recalled answer", "2026-08-12T12:00:00.000000Z"
    )
    assert replay == first
    assert first.status is ReviewItemStatus.COMPLETED
    assert first.scheduling_version == FIXTURE_SCHEDULING_VERSION
    with pytest.raises(DomainValidationError, match="must not be blank"):
        scheduler.schedule(item, " \n ", "2026-08-12T12:00:00.000000Z")
