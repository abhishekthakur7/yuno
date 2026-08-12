from __future__ import annotations

import pytest

from yuno.modules.learning_content.domain import (
    Capability,
    Checkpoint,
    MentalModelLayer,
    TopicLayer,
    validate_checkpoint,
    validate_layer_progression,
)
from yuno.shared.domain.errors import DomainValidationError


def test_checkpoint_contract_requires_all_fields_and_30_to_60_minutes() -> None:
    valid = Checkpoint(
        scenario="Two consumers race to apply one command.",
        constraints=("The duplicate key is stable.",),
        target_capability=Capability.IMPLEMENT,
        expected_artifact="A transaction-bound idempotency implementation.",
        estimated_minutes=45,
        rubric=("The race arbiter is explicit.",),
        assumptions=("The database supports a unique key.",),
        evidence_criterion="A submitted revision explains the atomic boundary.",
        limitation="Static review cannot prove runtime transaction behavior.",
    )
    validate_checkpoint(valid)

    with pytest.raises(DomainValidationError, match="between 30 and 60"):
        validate_checkpoint(Checkpoint(**{**valid.__dict__, "estimated_minutes": 29}))
    with pytest.raises(DomainValidationError, match="evidence_criterion"):
        validate_checkpoint(Checkpoint(**{**valid.__dict__, "evidence_criterion": " "}))


def test_later_layer_may_refine_but_never_reverse_an_earlier_claim() -> None:
    validate_layer_progression(
        (
            MentalModelLayer(TopicLayer.ESSENTIAL, ("delivery-can-repeat",)),
            MentalModelLayer(TopicLayer.IMPLEMENTATION, ("unique-key-arbitrates",)),
        )
    )

    with pytest.raises(DomainValidationError, match="reverses earlier"):
        validate_layer_progression(
            (
                MentalModelLayer(TopicLayer.ESSENTIAL, ("delivery-can-repeat",)),
                MentalModelLayer(
                    TopicLayer.PRODUCTION,
                    ("monitor-redelivery",),
                    reverses_claim_ids=("delivery-can-repeat",),
                ),
            )
        )
