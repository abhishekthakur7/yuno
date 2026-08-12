"""Composition adapters from existing domain ports to the provider port."""

from __future__ import annotations

from dataclasses import asdict
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    TypeAdapter,
    field_validator,
    model_validator,
)

from yuno.modules.evidence_evaluation.domain import (
    AssessmentState,
    DimensionOutcome,
    EvaluationDimensionResult,
    EvaluationRequest,
    EvaluationResult,
)
from yuno.modules.learning_content.domain import (
    GENERATION_CONTRACT_VERSION,
    GENERATION_SCHEMA_VERSION,
    GeneratedCitation,
    GeneratedClaim,
    GenerateRequest,
    GenerateResult,
    TutorRequest,
    TutorResult,
)
from yuno.modules.provider.domain import ProviderInput, ProviderResultState
from yuno.modules.provider.service import execute_provider
from yuno.shared.application.jobs import JobExecution
from yuno.shared.domain.errors import DomainValidationError, UnavailableError
from yuno.shared.domain.hashing import hash_payload


class UnavailableProviderPort:
    provider = "codex"
    adapter_version = "unavailable"
    contract_version = "unavailable"

    def invoke(self, *_args, **_kwargs):
        raise UnavailableError(
            "Provider CLI version and authentication discovery are not approved."
        )


class CitationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: StrictStr
    source_snapshot_id: StrictStr | None = None
    locator: StrictStr
    support_kind: StrictStr
    note: StrictStr | None = None

    @field_validator("source_id", "locator", "support_kind")
    @classmethod
    def nonblank_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("citation value must not be blank")
        return value

    @field_validator("source_snapshot_id", "note")
    @classmethod
    def nonblank_optional(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("optional citation value must not be blank")
        return value


class ClaimPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_text: StrictStr
    claim_type: Literal[
        "fact",
        "trade-off",
        "routine",
        "disputed",
        "comparative",
        "time-or-version-dependent",
    ]
    sensitive: StrictBool = False
    citations: list[CitationPayload] = []

    @field_validator("claim_text")
    @classmethod
    def nonblank_claim(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("claim text must not be blank")
        return value

    @model_validator(mode="after")
    def unique_citations(self):
        keys = [
            (item.source_id, item.source_snapshot_id, item.locator)
            for item in self.citations
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("citations must be unique")
        requires_citation = self.sensitive or self.claim_type in {
            "disputed",
            "comparative",
            "time-or-version-dependent",
        }
        if requires_citation and not self.citations:
            raise ValueError("sensitive and non-routine claims require a citation")
        return self


class GenerationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: StrictStr = Field(min_length=1)
    provenance_refs: list[list[StrictStr]] = []
    warnings: list[StrictStr] = []
    claims: list[ClaimPayload] = []

    @field_validator("body")
    @classmethod
    def nonblank_body(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("body must not be blank")
        return value

    @field_validator("warnings")
    @classmethod
    def nonblank_warnings(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("warnings must not be blank")
        return value

    @model_validator(mode="after")
    def publishable_collections(self):
        if any(
            len(item) != 2 or any(not part.strip() for part in item)
            for item in self.provenance_refs
        ):
            raise ValueError("provenance references must be nonblank pairs")
        if len({tuple(item) for item in self.provenance_refs}) != len(
            self.provenance_refs
        ):
            raise ValueError("provenance references must be unique")
        if len({item.claim_text for item in self.claims}) != len(self.claims):
            raise ValueError("claims must be unique")
        return self


class EvaluationDimensionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dimension_id: StrictStr = Field(min_length=1)
    outcome: Literal["pass", "trade-off", "factual-correction", "ambiguity-unresolved"]
    rationale: StrictStr = Field(min_length=1)
    evidence_refs: list[StrictStr] = []

    @field_validator("dimension_id", "rationale")
    @classmethod
    def nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @field_validator("evidence_refs")
    @classmethod
    def nonblank_refs(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("references must not be blank")
        return value


class EvaluationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: Literal["feedback-ready", "ambiguity-unresolved"]
    dimensions: list[EvaluationDimensionPayload]
    facts: list[StrictStr]
    trade_offs: list[StrictStr]
    citations: list[StrictStr]
    ambiguities: list[StrictStr]
    feedback: StrictStr = Field(min_length=1)
    cross_question_candidate: StrictStr | None = None
    revision_invitation: StrictStr | None = None
    warnings: list[StrictStr]
    limitation_labels: list[StrictStr]

    @field_validator("feedback")
    @classmethod
    def nonblank_feedback(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("feedback must not be blank")
        return value

    @field_validator(
        "facts",
        "trade_offs",
        "citations",
        "ambiguities",
        "warnings",
        "limitation_labels",
    )
    @classmethod
    def nonblank_items(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("list items must not be blank")
        return value

    @field_validator("cross_question_candidate", "revision_invitation")
    @classmethod
    def nonblank_optional(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("optional text must not be blank")
        return value

    @model_validator(mode="after")
    def semantic_consistency(self):
        ids = [item.dimension_id for item in self.dimensions]
        if len(ids) != len(set(ids)):
            raise ValueError("evaluation dimensions must be unique")
        unresolved = bool(self.ambiguities) or any(
            item.outcome == DimensionOutcome.AMBIGUITY_UNRESOLVED.value
            for item in self.dimensions
        )
        if (self.state == AssessmentState.AMBIGUITY_UNRESOLVED.value) != unresolved:
            raise ValueError("evaluation ambiguity state is inconsistent")
        return self


class MockQuestionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: StrictStr = Field(min_length=1)

    @field_validator("question")
    @classmethod
    def nonblank_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must not be blank")
        return value


class TutorPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: StrictStr = Field(min_length=1)
    provenance_references: list[StrictStr] = []
    warnings: list[StrictStr] = []

    @field_validator("body")
    @classmethod
    def nonblank_body(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("body must not be blank")
        return value

    @field_validator("provenance_references", "warnings")
    @classmethod
    def nonblank_items(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("list items must not be blank")
        return value


class MappingValidator:
    def __init__(
        self, purpose: str, *, expected_dimension_ids: tuple[str, ...] = ()
    ) -> None:
        self.purpose = purpose
        self.expected_dimension_ids = expected_dimension_ids

    def validate(self, value: object):
        model = {
            "topic-generation": GenerationPayload,
            "evaluation": EvaluationPayload,
            "mock-next-turn": MockQuestionPayload,
            "tutor-turn": TutorPayload,
        }[self.purpose]
        payload = TypeAdapter(model).validate_python(value, strict=True)
        if isinstance(payload, EvaluationPayload) and self.expected_dimension_ids:
            actual = {item.dimension_id for item in payload.dimensions}
            if actual != set(self.expected_dimension_ids):
                raise ValueError(
                    "evaluation must contain exactly the expected rubric dimensions"
                )
        return payload.model_dump(mode="json")


class ProviderGenerationAdapter:
    provider = "codex"
    model = "configured-provider"

    def __init__(self, app, execution: JobExecution) -> None:
        self._app = app
        self._execution = execution

    def generate(self, request: GenerateRequest) -> GenerateResult:
        result = _execute(
            self._app,
            self._execution,
            request,
            "topic-generation",
            GENERATION_SCHEMA_VERSION,
        )
        payload = result.payload or {}
        try:
            return GenerateResult(
                body=str(payload["body"]),
                provider=result.provider.value,
                model=result.model or "unknown",
                contract_version=GENERATION_CONTRACT_VERSION,
                schema_version=GENERATION_SCHEMA_VERSION,
                generated_at=result.timestamp
                or self._app.state.clock.now().isoformat().replace("+00:00", "Z"),
                provenance_refs=tuple(
                    tuple(item) for item in payload.get("provenance_refs", ())
                ),
                warnings=tuple(str(item) for item in payload.get("warnings", ())),
                claims=tuple(
                    GeneratedClaim(
                        claim_text=item["claim_text"],
                        claim_type=item["claim_type"],
                        sensitive=item.get("sensitive", False),
                        citations=tuple(
                            GeneratedCitation(**citation)
                            for citation in item.get("citations", ())
                        ),
                    )
                    for item in payload.get("claims", ())
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DomainValidationError(
                "Validated generation payload is incomplete."
            ) from exc


class ProviderEvaluationAdapter:
    def __init__(self, app, execution: JobExecution) -> None:
        self._app = app
        self._execution = execution

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        with self._app.state.uow_factory() as uow:
            expected_dimension_ids = tuple(
                dimension.stable_dimension_id
                for dimension in uow.evidence.list_rubric_dimensions(
                    self._execution.request.owner_id, request.rubric_id
                )
            )
        result = _execute(
            self._app,
            self._execution,
            request,
            "evaluation",
            "evaluation-v1",
            expected_dimension_ids=expected_dimension_ids,
        )
        payload = result.payload or {}
        try:
            return EvaluationResult(
                state=AssessmentState(str(payload["state"])),
                dimensions=tuple(
                    EvaluationDimensionResult(
                        str(item["dimension_id"]),
                        DimensionOutcome(str(item["outcome"])),
                        str(item["rationale"]),
                        tuple(str(ref) for ref in item.get("evidence_refs", ())),
                    )
                    for item in payload["dimensions"]
                ),
                facts=tuple(str(item) for item in payload.get("facts", ())),
                trade_offs=tuple(str(item) for item in payload.get("trade_offs", ())),
                citations=tuple(str(item) for item in payload.get("citations", ())),
                ambiguities=tuple(str(item) for item in payload.get("ambiguities", ())),
                feedback=str(payload["feedback"]),
                cross_question_candidate=payload.get("cross_question_candidate"),
                revision_invitation=payload.get("revision_invitation"),
                warnings=tuple(str(item) for item in payload.get("warnings", ())),
                limitation_labels=tuple(
                    str(item) for item in payload.get("limitation_labels", ())
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DomainValidationError(
                "Validated evaluation payload is incomplete."
            ) from exc


class ProviderMockInterviewAdapter:
    def __init__(self, app, execution: JobExecution) -> None:
        self._app = app
        self._execution = execution

    def next_question(self, run) -> str:
        result = _execute(
            self._app, self._execution, run, "mock-next-turn", "mock-turn-v1"
        )
        question = str((result.payload or {}).get("question", "")).strip()
        if not question:
            raise DomainValidationError(
                "Validated Mock next-turn payload is incomplete."
            )
        return question


class ProviderTutorAdapter:
    def __init__(self, app, execution: JobExecution) -> None:
        self._app = app
        self._execution = execution

    def respond(self, request: TutorRequest) -> TutorResult:
        result = _execute(
            self._app, self._execution, request, "tutor-turn", "tutor-turn-v1"
        )
        payload = result.payload or {}
        try:
            return TutorResult(
                body=str(payload["body"]),
                provenance_references=tuple(
                    str(item) for item in payload.get("provenance_references", ())
                ),
                warnings=tuple(str(item) for item in payload.get("warnings", ())),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DomainValidationError(
                "Validated tutor payload is incomplete."
            ) from exc


def _execute(
    app,
    execution: JobExecution,
    value,
    purpose: str,
    schema_version: str,
    *,
    expected_dimension_ids: tuple[str, ...] = (),
):
    request = execution.request
    if not request.disclosure_ref or not request.requested_job_id:
        raise DomainValidationError("Provider job omitted its disclosure reference.")
    context = asdict(value)
    result = execute_provider(
        app.state.uow_factory,
        app.state.provider_port,
        ProviderInput(
            owner_id=request.owner_id,
            goal_id=request.goal_id,
            job_id=request.requested_job_id,
            purpose=purpose,
            context=context,
            context_ref_hash=hash_payload(context),
            disclosure_id=request.disclosure_ref,
            output_schema_version=schema_version,
        ),
        MappingValidator(purpose, expected_dimension_ids=expected_dimension_ids),
        cancelled=execution.cancel_requested,
        record_runtime=execution.record_runtime,
        clock=app.state.clock,
    )
    if result.state is not ProviderResultState.SUCCEEDED or result.payload is None:
        classification = (
            result.failure_classification.value
            if result.failure_classification
            else result.state.value
        )
        raise UnavailableError(f"Provider operation did not succeed: {classification}.")
    return result
