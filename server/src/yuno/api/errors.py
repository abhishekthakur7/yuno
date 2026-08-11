"""Exception → HTTP response translation (spec §5.1 error envelope).

Four handlers cover every response this API returns for a failure:
`YunoError` subclasses map to their own fixed `http_status`; Starlette's
`HTTPException` — which routing raises for an unmatched path or method,
never application code — maps to the same envelope so a `404` looks like
every other principal status; FastAPI's `RequestValidationError`
(malformed/missing request data) maps to `422` with `field_errors`; and
anything else is an unhandled exception mapped to a `500` that includes
none of the exception's own detail, per spec §8.5 (no credentials,
tokens, absolute user paths or raw payload bodies in the response).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from yuno.api.contracts import ErrorResponse, FieldError
from yuno.shared.domain.errors import YunoError
from yuno.shared.domain.ids import new_id

_REQUEST_ID_HEADER = "X-Request-Id"
_CORRELATION_ID_HEADER = "X-Correlation-Id"

# Starlette raises `HTTPException` only from routing, so these are the
# only two statuses that reach `_handle_http_exception` in practice.
# Application code raises `YunoError`, which carries its own `code`.
_ROUTING_ERROR_CODES = {404: "not_found", 405: "method_not_allowed"}


def _request_ids(request: Request) -> tuple[str, str]:
    """Read the ids `middleware.CorrelationIdMiddleware` assigned, falling
    back to fresh ones if that middleware hasn't run.
    """
    request_id = getattr(request.state, "request_id", None) or new_id()
    correlation_id = getattr(request.state, "correlation_id", None) or new_id()
    return request_id, correlation_id


def _respond(
    body: ErrorResponse,
    *,
    status_code: int,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Every error handler funnels through here so the response always
    carries the id headers itself (see `register_exception_handlers` for
    why the generic-500 path can't rely on middleware to add them).
    """
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json", exclude_none=True),
        headers={
            **(headers or {}),
            _REQUEST_ID_HEADER: body.request_id,
            _CORRELATION_ID_HEADER: body.correlation_id,
        },
    )


async def _handle_yuno_error(request: Request, exc: YunoError) -> JSONResponse:
    request_id, correlation_id = _request_ids(request)
    body = ErrorResponse(
        code=exc.code,
        message=exc.message,
        request_id=request_id,
        correlation_id=correlation_id,
        retryable=exc.retryable,
        field_errors=[FieldError(**field_error) for field_error in exc.field_errors]
        if exc.field_errors
        else None,
        current_state=exc.current_state,
        job_id=exc.job_id,
        recovery_action=exc.recovery_action,
    )
    return _respond(body, status_code=exc.http_status)


async def _handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Routing failures (unmatched path, wrong method) use the same
    envelope as every other status. `exc.headers` is preserved because a
    `405` carries `Allow`.
    """
    request_id, correlation_id = _request_ids(request)
    body = ErrorResponse(
        code=_ROUTING_ERROR_CODES.get(exc.status_code, "http_error"),
        message=str(exc.detail),
        request_id=request_id,
        correlation_id=correlation_id,
        retryable=False,
    )
    return _respond(body, status_code=exc.status_code, headers=exc.headers)


async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id, correlation_id = _request_ids(request)
    body = ErrorResponse(
        code="request_validation_error",
        message="The request failed schema validation.",
        request_id=request_id,
        correlation_id=correlation_id,
        retryable=False,
        field_errors=[
            FieldError(
                field=".".join(str(part) for part in error["loc"]),
                message=error["msg"],
            )
            for error in exc.errors()
        ],
    )
    return _respond(body, status_code=422)


async def _handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    request_id, correlation_id = _request_ids(request)
    body = ErrorResponse(
        code="internal_error",
        message="An unexpected error occurred.",
        request_id=request_id,
        correlation_id=correlation_id,
        retryable=False,
    )
    return _respond(body, status_code=500)


def register_exception_handlers(app: FastAPI) -> None:
    """Register the four spec §5.1 exception translations.

    Starlette moves a handler registered for the bare `Exception` class
    onto `ServerErrorMiddleware`, the outermost layer — it runs even for
    exceptions that escape `CorrelationIdMiddleware`. That's why `_respond`
    sets the id headers on every response itself instead of leaving it to
    the middleware, which never resumes to add them on that path.
    """
    app.add_exception_handler(YunoError, _handle_yuno_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(Exception, _handle_unhandled_exception)
