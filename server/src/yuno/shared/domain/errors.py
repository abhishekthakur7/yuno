"""Domain/application error taxonomy.

The API layer (owned by a later agent) catches `YunoError` subclasses and
maps them to the spec §5.1 error envelope: `code`, `message`, `request_id`,
`correlation_id`, `retryable`, and the optional `field_errors`,
`current_state`, `job_id`, `recovery_action` carried on each instance here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class YunoError(Exception):
    """Base class for every domain/application error.

    Concrete subclasses fix `code`, `http_status` and `retryable` as class
    attributes with a sensible default per error kind (spec §5.1's
    principal statuses). `message` is required; the remaining detail
    fields are optional and default to `None`.
    """

    code: str = "internal_error"
    http_status: int = 500
    retryable: bool = False

    def __init__(
        self,
        message: str,
        *,
        field_errors: Sequence[Mapping[str, Any]] | None = None,
        current_state: str | None = None,
        job_id: str | None = None,
        recovery_action: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.field_errors = field_errors
        self.current_state = current_state
        self.job_id = job_id
        self.recovery_action = recovery_action


class MalformedRequestError(YunoError):
    """400 — the request could not be parsed or failed transport-level validation."""

    code = "malformed_request"
    http_status = 400
    retryable = False


class NotFoundError(YunoError):
    """404 — resource absent, or present but outside the caller's owner/goal scope."""

    code = "not_found"
    http_status = 404
    retryable = False


class ConflictError(YunoError):
    """409 — invalid state transition or other write conflict."""

    code = "conflict"
    http_status = 409
    retryable = False


class MockFeedbackWithheldError(ConflictError):
    """409 — Mock hints and evaluation remain unavailable before completion."""

    code = "mock_feedback_withheld"


class IdempotencyConflictError(YunoError):
    """409 — an `Idempotency-Key` was reused with a different request payload."""

    code = "idempotency_key_reused"
    http_status = 409
    retryable = False


class GoneError(YunoError):
    """410 — resource expired or tombstoned."""

    code = "gone"
    http_status = 410
    retryable = False


class PreconditionFailedError(YunoError):
    """412 — stale `If-Match`, or a required disclosure has not been accepted."""

    code = "precondition_failed"
    http_status = 412
    retryable = False


class DomainValidationError(YunoError):
    """422 — domain or schema validation violation."""

    code = "domain_validation_error"
    http_status = 422
    retryable = False


class LockedError(YunoError):
    """423 — the operation is locked (e.g. conflicting exclusive action in progress)."""

    code = "locked"
    http_status = 423
    retryable = False


class PayloadTooLargeError(YunoError):
    http_status = 413
    retryable = False


class ImportTooLargeError(PayloadTooLargeError):
    code = "import-too-large"


class ImportCountLimitError(ConflictError):
    code = "import-count-limit"


class ImportStatementLimitError(ConflictError):
    code = "import-statement-limit"


class EvidenceTooLargeError(PayloadTooLargeError):
    code = "evidence-too-large"


class EvidenceCountLimitError(ConflictError):
    code = "evidence-count-limit"


class GeneratedContentLimitError(DomainValidationError):
    code = "generated-content-limit"


class InterviewTranscriptLimitError(ConflictError):
    code = "interview-transcript-limit"


class RunnerInputLimitError(DomainValidationError):
    code = "runner-input-limit"


class UnsupportedExportVersionError(DomainValidationError):
    code = "unsupported-export-version"


class OverlayPendingCapError(ConflictError):
    code = "pending-cap-exceeded"


class PendingJobCapError(YunoError):
    code = "pending-job-cap"
    http_status = 429
    retryable = False


class UnavailableError(YunoError):
    """503 — service, migration, provider or runner temporarily unavailable."""

    code = "unavailable"
    http_status = 503
    retryable = True


class RoleNotGrantedError(YunoError):
    """422 — the acting owner lacks a required role grant.

    Not `403`: spec §5.1's principal statuses are exactly
    `400/404/409/410/412/422/423/429/503/504` — `401`/`403` appear nowhere in
    `IMPLEMENTATION_SPEC.md`. That omission is deliberate, not incidental:
    PRD DAT-01 specifies no MVP authentication (there is exactly one
    server-resolved local owner), so "forbidden" has no meaning in this
    system. A missing role grant (e.g. the `designated_editorial_approver`
    grant IDK-102 checks before publishing) is instead a domain/schema
    violation of that owner's own state — squarely `422`. The distinct
    `role_not_granted` code preserves the specific reason for callers that
    want to branch on it.
    """

    code = "role_not_granted"
    http_status = 422
    retryable = False
