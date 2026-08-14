"""Unit tests for `yuno.modules.canonical.validation.validate_basis_ref`
(IDK-002 §4's `basis_ref` contract,
`docs/decisions/IDK-002-editorial-approval-criteria.md:53-75`).

Same table-driven idiom as `test_canonical_validation.py`: build a payload
engineered to violate exactly one rule, assert the specific
`ViolationCode` fires, and prove a fully valid payload produces zero
violations for both the "initial" and "diff" `review_kind` paths.
"""

from __future__ import annotations

import copy
import json
from typing import Any

from yuno.modules.canonical.validation import ViolationCode, validate_basis_ref

_MANIFEST_HASH = "a" * 64
_LATEST_LABEL = "fixture-graph-v1"


def _counted_review(**overrides: Any) -> dict[str, Any]:
    base = {"result": "pass", "topics_reviewed": 2, "topics_total": 2}
    base.update(overrides)
    return base


def _valid_payload(*, review_kind: str = "initial") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "basis_ref_version": "editorial-approval-basis-v1",
        "policy_identifier": "editorial-approval-criteria-v1",
        "reviewed_manifest_hash": _MANIFEST_HASH,
        "checklist_completed_at": "2026-08-14T12:00:00.000000Z",
        "review_kind": review_kind,
        "diff_against_version_label": _LATEST_LABEL if review_kind == "diff" else None,
        "curriculum_boundary_review": {
            "result": "pass",
            "topics_reviewed": 4,
            "topics_total": 4,
        },
        "dsa_scenario_review": {
            "result": "pass",
            "dsa_topics_reviewed": 1,
            "dsa_topics_total": 1,
        },
        "dag_identity_review": {
            "result": "pass",
            "reused_stable_ids_confirmed": 0,
            "reused_stable_ids_total": 0,
        },
        "source_citation_review": {
            "structural_result": "pass",
            "structural_claims_reviewed": 3,
            "structural_claims_total": 3,
            "live_check_sample_size": 5,
            "live_check_population_size": 20,
            "live_check_result": "pass",
        },
        "layer_reversal_review": {
            "result": "pass",
            "topics_reviewed": 4,
            "topics_total": 4,
        },
        "half_seed_immutability_check": {"result": "pass"},
        "diff_review": (
            {"result": "pass", "items_reviewed": 2, "items_total": 2}
            if review_kind == "diff"
            else None
        ),
        "approver_is_sole_content_author": True,
    }
    return payload


def _dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload)


def _validate(
    payload: dict[str, Any],
    *,
    manifest_hash: str = _MANIFEST_HASH,
    published_version_labels: tuple[str, ...] = (),
):
    return validate_basis_ref(
        _dump(payload),
        manifest_hash=manifest_hash,
        published_version_labels=published_version_labels,
    )


def _codes(result) -> set[ViolationCode]:
    return {violation.code for violation in result.violations}


# --- Happy paths. ------------------------------------------------------------


def test_valid_initial_basis_ref_with_no_published_versions_has_no_violations() -> None:
    result = _validate(
        _valid_payload(review_kind="initial"), published_version_labels=()
    )
    assert result.is_valid
    assert result.violations == ()


def test_valid_diff_basis_ref_with_one_published_version_has_no_violations() -> None:
    result = _validate(
        _valid_payload(review_kind="diff"),
        published_version_labels=(_LATEST_LABEL,),
    )
    assert result.is_valid
    assert result.violations == ()


# --- JSON / shape. ------------------------------------------------------------


def test_not_json_at_all_is_rejected() -> None:
    result = validate_basis_ref(
        "not json {{{", manifest_hash=_MANIFEST_HASH, published_version_labels=()
    )
    assert _codes(result) == {ViolationCode.BASIS_REF_NOT_VALID_JSON}


def test_json_array_is_rejected() -> None:
    result = validate_basis_ref(
        "[1, 2, 3]", manifest_hash=_MANIFEST_HASH, published_version_labels=()
    )
    assert _codes(result) == {ViolationCode.BASIS_REF_NOT_OBJECT}


def test_json_scalar_is_rejected() -> None:
    result = validate_basis_ref(
        '"just a string"', manifest_hash=_MANIFEST_HASH, published_version_labels=()
    )
    assert _codes(result) == {ViolationCode.BASIS_REF_NOT_OBJECT}


def test_json_null_is_rejected() -> None:
    result = validate_basis_ref(
        "null", manifest_hash=_MANIFEST_HASH, published_version_labels=()
    )
    assert _codes(result) == {ViolationCode.BASIS_REF_NOT_OBJECT}


# --- Missing / unknown top-level fields. --------------------------------------


def test_missing_basis_ref_version_is_rejected() -> None:
    payload = _valid_payload()
    del payload["basis_ref_version"]
    result = _validate(payload)
    assert ViolationCode.BASIS_REF_MISSING_FIELD in _codes(result)


def test_missing_curriculum_boundary_review_is_rejected() -> None:
    payload = _valid_payload()
    del payload["curriculum_boundary_review"]
    result = _validate(payload)
    assert ViolationCode.BASIS_REF_MISSING_FIELD in _codes(result)


def test_missing_approver_is_sole_content_author_is_rejected() -> None:
    payload = _valid_payload()
    del payload["approver_is_sole_content_author"]
    result = _validate(payload)
    assert ViolationCode.BASIS_REF_MISSING_FIELD in _codes(result)


def test_unknown_extra_top_level_key_is_rejected() -> None:
    payload = _valid_payload()
    payload["totally_unexpected_field"] = "surprise"
    result = _validate(payload)
    assert ViolationCode.BASIS_REF_UNKNOWN_FIELD in _codes(result)


# --- Literal fields. -----------------------------------------------------------


def test_wrong_basis_ref_version_literal_is_rejected() -> None:
    payload = _valid_payload()
    payload["basis_ref_version"] = "wrong-version"
    result = _validate(payload)
    assert ViolationCode.BASIS_REF_VERSION_MISMATCH in _codes(result)


def test_wrong_policy_identifier_literal_is_rejected() -> None:
    payload = _valid_payload()
    payload["policy_identifier"] = "wrong-policy"
    result = _validate(payload)
    assert ViolationCode.BASIS_REF_POLICY_IDENTIFIER_MISMATCH in _codes(result)


# --- reviewed_manifest_hash cross-check. ----------------------------------------


def test_reviewed_manifest_hash_not_matching_manifest_hash_argument_is_rejected() -> (
    None
):
    payload = _valid_payload()
    payload["reviewed_manifest_hash"] = "b" * 64
    result = _validate(payload, manifest_hash=_MANIFEST_HASH)
    assert ViolationCode.BASIS_REF_MANIFEST_HASH_MISMATCH in _codes(result)


# --- review_kind vs. publish state. ---------------------------------------------


def test_review_kind_initial_when_a_version_is_already_published_is_rejected() -> None:
    payload = _valid_payload(review_kind="initial")
    result = _validate(payload, published_version_labels=(_LATEST_LABEL,))
    assert ViolationCode.BASIS_REF_REVIEW_KIND_PUBLISHED_STATE_MISMATCH in _codes(
        result
    )


def test_review_kind_diff_when_no_version_is_published_is_rejected() -> None:
    payload = _valid_payload(review_kind="diff")
    result = _validate(payload, published_version_labels=())
    assert ViolationCode.BASIS_REF_REVIEW_KIND_PUBLISHED_STATE_MISMATCH in _codes(
        result
    )


def test_review_kind_invalid_literal_is_rejected() -> None:
    payload = _valid_payload()
    payload["review_kind"] = "bogus"
    result = _validate(payload)
    assert ViolationCode.BASIS_REF_REVIEW_KIND_INVALID in _codes(result)


# --- diff_against_version_label. -----------------------------------------------


def test_review_kind_diff_with_null_diff_against_version_label_is_rejected() -> None:
    payload = _valid_payload(review_kind="diff")
    payload["diff_against_version_label"] = None
    result = _validate(payload, published_version_labels=(_LATEST_LABEL,))
    assert ViolationCode.BASIS_REF_DIFF_AGAINST_VERSION_LABEL_INVALID in _codes(result)


def test_review_kind_diff_with_label_naming_a_non_latest_version_is_rejected() -> None:
    payload = _valid_payload(review_kind="diff")
    payload["diff_against_version_label"] = "some-older-version"
    result = _validate(
        payload, published_version_labels=(_LATEST_LABEL, "some-older-version")
    )
    assert ViolationCode.BASIS_REF_DIFF_AGAINST_VERSION_LABEL_INVALID in _codes(result)


def test_review_kind_initial_with_non_null_diff_against_version_label_is_rejected() -> (
    None
):
    payload = _valid_payload(review_kind="initial")
    payload["diff_against_version_label"] = _LATEST_LABEL
    result = _validate(payload, published_version_labels=())
    assert ViolationCode.BASIS_REF_DIFF_AGAINST_VERSION_LABEL_INVALID in _codes(result)


def test_review_kind_initial_with_non_null_diff_review_is_rejected() -> None:
    payload = _valid_payload(review_kind="initial")
    payload["diff_review"] = {"result": "pass", "items_reviewed": 1, "items_total": 1}
    result = _validate(payload, published_version_labels=())
    assert ViolationCode.BASIS_REF_DIFF_REVIEW_INVALID in _codes(result)


def test_review_kind_diff_with_null_diff_review_is_rejected() -> None:
    payload = _valid_payload(review_kind="diff")
    payload["diff_review"] = None
    result = _validate(payload, published_version_labels=(_LATEST_LABEL,))
    assert ViolationCode.BASIS_REF_DIFF_REVIEW_INVALID in _codes(result)


# --- "reviewed must equal total" mismatches, one per nested review object. -----


def test_curriculum_boundary_reviewed_not_equal_total_is_rejected() -> None:
    payload = _valid_payload()
    payload["curriculum_boundary_review"] = _counted_review(
        topics_reviewed=3, topics_total=4
    )
    result = _validate(payload)
    assert ViolationCode.BASIS_REF_REVIEWED_COUNT_MISMATCH in _codes(result)


def test_dsa_scenario_reviewed_not_equal_total_is_rejected() -> None:
    payload = _valid_payload()
    payload["dsa_scenario_review"] = {
        "result": "pass",
        "dsa_topics_reviewed": 0,
        "dsa_topics_total": 1,
    }
    result = _validate(payload)
    assert ViolationCode.BASIS_REF_REVIEWED_COUNT_MISMATCH in _codes(result)


def test_dag_identity_confirmed_not_equal_total_is_rejected() -> None:
    payload = _valid_payload()
    payload["dag_identity_review"] = {
        "result": "pass",
        "reused_stable_ids_confirmed": 1,
        "reused_stable_ids_total": 2,
    }
    result = _validate(payload)
    assert ViolationCode.BASIS_REF_REVIEWED_COUNT_MISMATCH in _codes(result)


def test_source_citation_structural_reviewed_not_equal_total_is_rejected() -> None:
    payload = _valid_payload()
    payload["source_citation_review"]["structural_claims_reviewed"] = 1
    payload["source_citation_review"]["structural_claims_total"] = 3
    result = _validate(payload)
    assert ViolationCode.BASIS_REF_REVIEWED_COUNT_MISMATCH in _codes(result)


def test_layer_reversal_reviewed_not_equal_total_is_rejected() -> None:
    payload = _valid_payload()
    payload["layer_reversal_review"] = _counted_review(
        topics_reviewed=1, topics_total=4
    )
    result = _validate(payload)
    assert ViolationCode.BASIS_REF_REVIEWED_COUNT_MISMATCH in _codes(result)


def test_diff_review_items_reviewed_not_equal_total_is_rejected() -> None:
    payload = _valid_payload(review_kind="diff")
    payload["diff_review"] = {"result": "pass", "items_reviewed": 1, "items_total": 2}
    result = _validate(payload, published_version_labels=(_LATEST_LABEL,))
    assert ViolationCode.BASIS_REF_REVIEWED_COUNT_MISMATCH in _codes(result)


# --- Blank strings, count field types, notes. -----------------------------------


def test_blank_nested_result_string_is_rejected() -> None:
    payload = _valid_payload()
    payload["half_seed_immutability_check"] = {"result": "   "}
    result = _validate(payload)
    assert ViolationCode.BASIS_REF_BLANK_FIELD in _codes(result)


def test_blank_required_top_level_string_is_rejected() -> None:
    payload = _valid_payload()
    payload["checklist_completed_at"] = "   "
    result = _validate(payload)
    assert ViolationCode.BASIS_REF_BLANK_FIELD in _codes(result)


def test_negative_count_field_is_rejected() -> None:
    payload = _valid_payload()
    payload["curriculum_boundary_review"] = _counted_review(
        topics_reviewed=-1, topics_total=-1
    )
    result = _validate(payload)
    assert ViolationCode.BASIS_REF_COUNT_FIELD_INVALID in _codes(result)


def test_boolean_count_field_is_rejected() -> None:
    payload = _valid_payload()
    payload["curriculum_boundary_review"] = _counted_review(
        topics_reviewed=True, topics_total=4
    )
    result = _validate(payload)
    assert ViolationCode.BASIS_REF_COUNT_FIELD_INVALID in _codes(result)


def test_string_count_field_is_rejected() -> None:
    payload = _valid_payload()
    payload["curriculum_boundary_review"] = _counted_review(
        topics_reviewed="4", topics_total=4
    )
    result = _validate(payload)
    assert ViolationCode.BASIS_REF_COUNT_FIELD_INVALID in _codes(result)


def test_notes_absent_is_valid() -> None:
    payload = _valid_payload()
    assert "notes" not in payload
    result = _validate(payload)
    assert result.is_valid


def test_notes_present_as_string_is_valid() -> None:
    payload = _valid_payload()
    payload["notes"] = "Elaboration only, never a substitute for structured fields."
    result = _validate(payload)
    assert result.is_valid


def test_notes_wrong_type_is_rejected() -> None:
    payload = _valid_payload()
    payload["notes"] = 12345
    result = _validate(payload)
    assert ViolationCode.BASIS_REF_INVALID_FIELD_TYPE in _codes(result)


# --- §6: a basis_ref with every structured field blank and substance only in
# notes must fail -- proven by requiring every required string field
# non-blank and every nested object's sub-keys present (no separate ad-hoc
# "blankness" rule is added on top, per the module's approach). -----------------


def test_all_structured_fields_blank_with_only_notes_populated_fails() -> None:
    payload = _valid_payload()
    payload["basis_ref_version"] = ""
    payload["policy_identifier"] = ""
    payload["reviewed_manifest_hash"] = ""
    payload["checklist_completed_at"] = ""
    payload["curriculum_boundary_review"] = {}
    payload["dsa_scenario_review"] = {}
    payload["dag_identity_review"] = {}
    payload["source_citation_review"] = {}
    payload["layer_reversal_review"] = {}
    payload["half_seed_immutability_check"] = {}
    payload["notes"] = "Trust me, I reviewed everything thoroughly."
    result = _validate(payload)
    assert not result.is_valid
    codes = _codes(result)
    assert ViolationCode.BASIS_REF_BLANK_FIELD in codes
    assert ViolationCode.BASIS_REF_MISSING_FIELD in codes


# --- Multiple independent violations are all reported together. ----------------


def test_multiple_independent_violations_are_all_reported_together() -> None:
    payload = _valid_payload(review_kind="initial")
    payload["basis_ref_version"] = "wrong"
    payload["reviewed_manifest_hash"] = "not-the-hash"
    payload["curriculum_boundary_review"] = _counted_review(
        topics_reviewed=1, topics_total=4
    )
    payload["totally_unexpected_field"] = "surprise"
    result = _validate(
        payload, manifest_hash=_MANIFEST_HASH, published_version_labels=()
    )
    codes = _codes(result)
    assert ViolationCode.BASIS_REF_VERSION_MISMATCH in codes
    assert ViolationCode.BASIS_REF_MANIFEST_HASH_MISMATCH in codes
    assert ViolationCode.BASIS_REF_REVIEWED_COUNT_MISMATCH in codes
    assert ViolationCode.BASIS_REF_UNKNOWN_FIELD in codes
    assert len(result.violations) >= 4


def test_deepcopy_of_valid_payload_used_for_manifest_hash_still_matches() -> None:
    """Sanity check that `_valid_payload` and `_MANIFEST_HASH` stay in sync
    across a defensive copy, so mutation-based tests above never share
    accidental state."""
    payload = copy.deepcopy(_valid_payload())
    result = _validate(payload)
    assert result.is_valid


# --- published_version_labels=None: offline shape validation. ------------------
#
# `None` means "published state unknown to this caller" and skips *only* the
# two checks that genuinely need database state -- everything else,
# including the internal-consistency shape rules for the very same fields,
# must still fire.


def test_none_published_labels_still_rejects_diff_with_null_diff_against_version_label() -> (
    None
):
    payload = _valid_payload(review_kind="diff")
    payload["diff_against_version_label"] = None
    result = validate_basis_ref(
        _dump(payload), manifest_hash=_MANIFEST_HASH, published_version_labels=None
    )
    assert ViolationCode.BASIS_REF_DIFF_AGAINST_VERSION_LABEL_INVALID in _codes(result)


def test_none_published_labels_still_rejects_initial_with_non_null_diff_review() -> (
    None
):
    payload = _valid_payload(review_kind="initial")
    payload["diff_review"] = {"result": "pass", "items_reviewed": 1, "items_total": 1}
    result = validate_basis_ref(
        _dump(payload), manifest_hash=_MANIFEST_HASH, published_version_labels=None
    )
    assert ViolationCode.BASIS_REF_DIFF_REVIEW_INVALID in _codes(result)


def test_none_published_labels_still_rejects_diff_with_null_diff_review() -> None:
    payload = _valid_payload(review_kind="diff")
    payload["diff_review"] = None
    result = validate_basis_ref(
        _dump(payload), manifest_hash=_MANIFEST_HASH, published_version_labels=None
    )
    assert ViolationCode.BASIS_REF_DIFF_REVIEW_INVALID in _codes(result)


def test_none_published_labels_still_rejects_initial_with_non_null_diff_against_version_label() -> (
    None
):
    payload = _valid_payload(review_kind="initial")
    payload["diff_against_version_label"] = _LATEST_LABEL
    result = validate_basis_ref(
        _dump(payload), manifest_hash=_MANIFEST_HASH, published_version_labels=None
    )
    assert ViolationCode.BASIS_REF_DIFF_AGAINST_VERSION_LABEL_INVALID in _codes(result)


def test_none_published_labels_does_not_flag_review_kind_disagreeing_with_published_state() -> (
    None
):
    """A `review_kind` that merely disagrees with actual publish state must
    NOT be flagged under `None` (that cross-check needs database state,
    deferred to the caller) but MUST be flagged when a real sequence is
    given."""
    payload = _valid_payload(review_kind="initial")

    none_result = validate_basis_ref(
        _dump(payload), manifest_hash=_MANIFEST_HASH, published_version_labels=None
    )
    assert ViolationCode.BASIS_REF_REVIEW_KIND_PUBLISHED_STATE_MISMATCH not in _codes(
        none_result
    )

    real_result = _validate(payload, published_version_labels=(_LATEST_LABEL,))
    assert ViolationCode.BASIS_REF_REVIEW_KIND_PUBLISHED_STATE_MISMATCH in _codes(
        real_result
    )


def test_none_published_labels_does_not_flag_diff_label_disagreeing_with_latest_published() -> (
    None
):
    """A `diff_against_version_label` that is a well-formed non-blank string
    but does not match the actual latest published label must NOT be
    flagged under `None`, but MUST be flagged when a real sequence names a
    different latest label."""
    payload = _valid_payload(review_kind="diff")
    payload["diff_against_version_label"] = "some-other-version"

    none_result = validate_basis_ref(
        _dump(payload), manifest_hash=_MANIFEST_HASH, published_version_labels=None
    )
    assert ViolationCode.BASIS_REF_DIFF_AGAINST_VERSION_LABEL_INVALID not in _codes(
        none_result
    )

    real_result = _validate(
        payload, published_version_labels=(_LATEST_LABEL, "some-other-version")
    )
    assert ViolationCode.BASIS_REF_DIFF_AGAINST_VERSION_LABEL_INVALID in _codes(
        real_result
    )


def test_none_published_labels_valid_initial_payload_has_no_violations() -> None:
    result = validate_basis_ref(
        _dump(_valid_payload(review_kind="initial")),
        manifest_hash=_MANIFEST_HASH,
        published_version_labels=None,
    )
    assert result.is_valid


def test_none_published_labels_valid_diff_payload_has_no_violations() -> None:
    payload = _valid_payload(review_kind="diff")
    result = validate_basis_ref(
        _dump(payload), manifest_hash=_MANIFEST_HASH, published_version_labels=None
    )
    assert result.is_valid
