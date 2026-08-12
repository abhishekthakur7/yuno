"""Framework-free import entities and the deterministic parser/normalizer."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

from yuno.shared.domain.errors import DomainValidationError

PARSER_VERSION = "imports-v1"


class ImportType(StrEnum):
    MARKDOWN = "markdown"
    PLAIN_TEXT = "plain_text"


class ImportStatus(StrEnum):
    SELECTED = "selected"
    PARSING = "parsing"
    PARSED_UNTRUSTED = "parsed-untrusted"
    LEARNER_REVIEW = "learner-review"
    APPLIED = "applied"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TrustState(StrEnum):
    UNTRUSTED = "untrusted"
    VERIFIED = "verified"
    DISMISSED = "dismissed"


class MappingState(StrEnum):
    UNMAPPED = "unmapped"
    MAPPED = "mapped"
    DUPLICATE = "duplicate"


class MappingDecision(StrEnum):
    APPROVED = "approved"
    REVOKED = "revoked"


class StatementDecisionType(StrEnum):
    CORRECTED = "corrected"
    VERIFIED = "verified"
    DISMISSED = "dismissed"


@dataclass(frozen=True)
class ImportRecord:
    id: str
    owner_id: str
    goal_id: str | None
    import_type: ImportType
    original_content: bytes
    original_hash: str
    parser_version: str
    status: ImportStatus
    failure_code: str | None
    failure_reference: str | None
    row_version: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ParsedStatement:
    sequence: int
    original_text: str
    original_hash: str
    normalized_text: str
    normalized_hash: str
    confidence: float


@dataclass(frozen=True)
class ImportStatement:
    id: str
    owner_id: str
    import_id: str
    sequence: int
    parser_version: str
    original_text: str
    original_hash: str
    normalized_text: str
    normalized_hash: str
    confidence: float
    duplicate_of_statement_id: str | None
    trust_state: TrustState
    mapping_state: MappingState
    corrected_text: str | None
    row_version: int
    created_at: str
    updated_at: str

    @property
    def effective_text(self) -> str:
        return self.corrected_text or self.original_text


@dataclass(frozen=True)
class ImportStatementDecision:
    id: str
    owner_id: str
    statement_id: str
    decision_type: StatementDecisionType
    value: str | None
    decided_at: str


@dataclass(frozen=True)
class ImportStatementMapping:
    id: str
    owner_id: str
    goal_id: str
    statement_id: str
    topic_stable_id: str
    graph_version_id: str
    decision: MappingDecision
    accepted_at: str
    revoked_at: str | None


@dataclass(frozen=True)
class TopicImportHash:
    owner_id: str
    goal_id: str
    graph_version_id: str
    topic_stable_id: str
    imports_hash: str
    updated_at: str


@dataclass(frozen=True)
class ImportParseResult:
    parser_version: str
    original_hash: str
    statements: tuple[ImportStatement, ...]
    warnings: tuple[str, ...]
    duplicate_candidates: tuple[str, ...]


@dataclass(frozen=True)
class ImportIdempotencyRecord:
    id: str
    owner_id: str
    operation: str
    idempotency_key: str
    request_hash: str
    response_json: str
    created_at: str


_MARKDOWN_PREFIX = re.compile(
    r"^(?:#{1,6}\s+|[-+*]\s+|>\s+|\d{1,9}[.)]\s+|\[[ xX]\]\s+)"
)
_WHITESPACE = re.compile(r"\s+")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def normalize_statement(value: str) -> str:
    """Return the parser-versioned identity form used for deduplication."""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = _MARKDOWN_PREFIX.sub("", normalized.strip())
    normalized = _WHITESPACE.sub(" ", normalized)
    return normalized.casefold().strip()


def normalized_hash(value: str) -> str:
    return sha256_bytes(normalize_statement(value).encode("utf-8"))


def parse_source(
    source: bytes, *, parser_version: str = PARSER_VERSION
) -> tuple[ParsedStatement, ...]:
    """Parse exact UTF-8 bytes without consulting time, state, or providers."""
    if parser_version != PARSER_VERSION:
        raise DomainValidationError(
            f"Unsupported import parser version '{parser_version}'."
        )
    try:
        text = source.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise DomainValidationError("Import source must be valid UTF-8.") from exc

    parsed: list[ParsedStatement] = []
    for line in text.splitlines():
        original = line.strip()
        normalized = normalize_statement(original)
        if not normalized:
            continue
        parsed.append(
            ParsedStatement(
                sequence=len(parsed) + 1,
                original_text=original,
                original_hash=sha256_bytes(original.encode("utf-8")),
                normalized_text=normalized,
                normalized_hash=sha256_bytes(normalized.encode("utf-8")),
                confidence=1.0,
            )
        )
    return tuple(parsed)
