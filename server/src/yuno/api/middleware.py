"""Per-request correlation assignment and structured completion logging.

Spec §8.5's structured-log fields carry request, correlation, owner, goal,
job, provider-request and runner IDs. This middleware establishes and
propagates the first two and emits body-free request completion/failure events.
"""

from __future__ import annotations

import logging
import re

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from yuno.shared.domain.ids import new_id
from yuno.shared.infrastructure.structured_logging import log_event

REQUEST_ID_HEADER = "X-Request-Id"
CORRELATION_ID_HEADER = "X-Correlation-Id"

# An ordinary transport-hygiene bound, not a product policy value -- the
# same class of limit as a max URL length or a request body size cap. A
# correlation id is a client-generated trace token, not domain data: 200
# characters comfortably covers a UUID (36), a ULID (26), or a W3C
# `traceparent` (55), while stopping a caller from reflecting an
# unbounded value into every response header and error body.
_CORRELATION_ID_MAX_LENGTH = 200

# Safe-character allowlist covering UUIDs, ULIDs and typical trace/span id
# formats. Rejecting anything else (whitespace, control characters
# including CR/LF, other punctuation) means this doesn't rely on uvicorn's
# own header-value regex as the only guard against response-splitting or
# log injection.
_CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


def _clean_correlation_id(raw_value: str | None) -> str | None:
    """Return `raw_value` unchanged if it's present, no longer than
    `_CORRELATION_ID_MAX_LENGTH`, and matches `_CORRELATION_ID_PATTERN`;
    else `None` so the caller falls back to a generated id.
    """
    if (
        raw_value is not None
        and len(raw_value) <= _CORRELATION_ID_MAX_LENGTH
        and _CORRELATION_ID_PATTERN.fullmatch(raw_value)
    ):
        return raw_value
    return None


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Assigns a fresh `request_id` to every request, adopts a conforming
    inbound `X-Correlation-Id` header as `correlation_id` (generating one
    when absent or non-conforming -- see `_clean_correlation_id`), exposes
    both on `request.state`, and echoes both back as response headers.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = new_id()
        correlation_id = (
            _clean_correlation_id(request.headers.get(CORRELATION_ID_HEADER))
            or new_id()
        )

        request.state.request_id = request_id
        request.state.correlation_id = correlation_id

        try:
            response = await call_next(request)
        except Exception:
            log_event(
                "http.request.failed",
                level=logging.ERROR,
                request_id=request_id,
                correlation_id=correlation_id,
                method=request.method,
                route=request.url.path,
                diagnostic_classification="unhandled-request-failure",
            )
            raise

        log_event(
            "http.request.completed",
            request_id=request_id,
            correlation_id=correlation_id,
            method=request.method,
            route=request.url.path,
            status_code=response.status_code,
        )

        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response
