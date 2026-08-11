"""Self-test for `tests.fixtures.canonical` (IDK-102 task: "Ships MVP
fixtures", spec §6.1 step 8). Proves the fixture package itself is
internally correct -- every "valid" fixture actually validates clean,
every "invalid" fixture trips exactly its documented violation set, and
every loaded fixture carries the non-production label -- so a downstream
validation/publisher agent can trust `load_fixture` without re-deriving
these facts itself.

This file owns and tests only `tests/fixtures/canonical/**`; it does not
touch any other agent's test file (per the ticket's file-ownership rule).
"""

from __future__ import annotations

import pytest

from tests.fixtures.canonical import (
    CANONICAL_FIXTURE_NAMES,
    EXPECTED_VIOLATIONS,
    NON_PRODUCTION_LABEL,
    load_fixture,
)
from yuno.modules.canonical.validation import validate_manifest

_VALID_FIXTURES = ("v1_approved", "v2_approved", "half_seeded")
_INVALID_FIXTURES = tuple(EXPECTED_VIOLATIONS)


def test_fixture_inventory_matches_valid_plus_invalid_partition() -> None:
    assert set(CANONICAL_FIXTURE_NAMES) == set(_VALID_FIXTURES) | set(_INVALID_FIXTURES)


@pytest.mark.parametrize("name", CANONICAL_FIXTURE_NAMES)
def test_every_fixture_carries_the_non_production_label(name: str) -> None:
    fixture = load_fixture(name)
    assert fixture.non_production_label == NON_PRODUCTION_LABEL
    assert "SYNTHETIC" in fixture.non_production_label
    assert "NOT PRODUCTION" in fixture.non_production_label


@pytest.mark.parametrize("name", CANONICAL_FIXTURE_NAMES)
def test_every_fixture_stable_id_and_title_is_transparently_synthetic(name: str) -> None:
    fixture = load_fixture(name)
    for topic in fixture.manifest.topics:
        if topic.stable_id:  # the missing-stable-id fixture has one blank stable_id on purpose
            assert topic.stable_id.startswith("fixture-")
        assert "[SYNTHETIC]" in topic.title or topic.title.startswith("[SYNTHETIC]")


@pytest.mark.parametrize("name", _VALID_FIXTURES)
def test_valid_fixtures_pass_manifest_validation(name: str) -> None:
    fixture = load_fixture(name)
    result = validate_manifest(fixture.manifest)
    assert result.is_valid, result.violations


def test_v1_and_v2_are_each_independently_valid_and_independently_labelled() -> None:
    v1 = load_fixture("v1_approved")
    v2 = load_fixture("v2_approved")
    assert v1.manifest.version_label != v2.manifest.version_label
    assert v1.manifest.manifest_hash != v2.manifest.manifest_hash
    assert validate_manifest(v1.manifest).is_valid
    assert validate_manifest(v2.manifest).is_valid
    assert v1.approval is not None
    assert v2.approval is not None


def test_v2_drops_a_v1_topic_and_carries_others_forward_by_stable_id() -> None:
    """The canonical-graph-expressible half of spec §6.1 step 8's
    "upstream-deleted topic carrying local state" fixture -- see the
    loader module's "Honest gap" docstring for what this does NOT cover.
    """
    v1_ids = {t.stable_id for t in load_fixture("v1_approved").manifest.topics}
    v2_ids = {t.stable_id for t in load_fixture("v2_approved").manifest.topics}
    assert "fixture-topic-gamma" in v1_ids
    assert "fixture-topic-gamma" not in v2_ids
    carried_forward = v1_ids & v2_ids
    assert carried_forward, "expected at least one stable_id to persist across v1 -> v2"


def test_half_seeded_fixture_has_no_approval() -> None:
    fixture = load_fixture("half_seeded")
    assert fixture.approval is None
    assert validate_manifest(fixture.manifest).is_valid


@pytest.mark.parametrize("name", _INVALID_FIXTURES)
def test_invalid_fixtures_trip_exactly_their_expected_violations(name: str) -> None:
    fixture = load_fixture(name)
    result = validate_manifest(fixture.manifest)
    assert not result.is_valid
    codes = {violation.code for violation in result.violations}
    assert codes == EXPECTED_VIOLATIONS[name]


def test_unknown_fixture_name_raises_key_error() -> None:
    with pytest.raises(KeyError):
        load_fixture("does-not-exist")
