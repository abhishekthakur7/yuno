"""Integration tests proving the spec §5.1 API contract: request/
correlation ids, the server-resolved owner seam (DAT-01), the error
envelope, and the `Idempotency-Key`/`If-Match` header guards.

`/api/v1/health` (`api/routes/system.py`) is the only real route, and it
exercises none of `api/dependencies.py`'s owner/idempotency/if-match seams.
The owner-seam, error-envelope and header-guard tests below mount throwaway
routes on a small, locally constructed `FastAPI` app (`_build_probe_app`)
that reuses the real `yuno.api.dependencies`/`yuno.api.errors`/
`yuno.api.middleware` code -- nothing under `yuno/api/routes/**` is touched.
"""

from __future__ import annotations

import inspect
from collections.abc import Iterator

import pytest
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import Engine

from yuno.api.app import create_app
from yuno.api.dependencies import get_owner_id, idempotency_key, if_match
from yuno.api.errors import register_exception_handlers
from yuno.api.middleware import CorrelationIdMiddleware
from yuno.config import Settings
from yuno.modules.identity.service import ensure_local_owner
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.errors import ConflictError, NotFoundError, RoleNotGrantedError
from yuno.shared.infrastructure import alembic_guard

_ERROR_ENVELOPE_KEYS = {"code", "message", "request_id", "correlation_id", "retryable"}


class _ProbeBody(BaseModel):
    note: str = "unused"


def _build_probe_app(uow_factory: UnitOfWorkFactory, owner_id: str) -> FastAPI:
    """A throwaway app exercising the shared dependency/error-handling
    seams that `/health` never touches. Reuses the real
    `register_exception_handlers`/`CorrelationIdMiddleware` so what's under
    test is production code, not a reimplementation of it.

    `app.state.owner_id` is set directly here, mirroring how `create_app`'s
    lifespan caches it after `ensure_local_owner` -- this probe app has no
    lifespan of its own, so nothing else would populate it.
    """
    app = FastAPI()
    app.state.uow_factory = uow_factory
    app.state.owner_id = owner_id
    router = APIRouter(prefix="/api/v1")

    @router.get("/_probe/owner")
    def probe_owner(owner_id: str = Depends(get_owner_id)) -> dict[str, str]:
        return {"owner_id": owner_id}

    @router.post("/_probe/owner")
    def probe_owner_body(
        payload: _ProbeBody, owner_id: str = Depends(get_owner_id)
    ) -> dict[str, str]:
        return {"owner_id": owner_id, "note": payload.note}

    @router.post("/_probe/idempotent")
    def probe_idempotent(key: str = Depends(idempotency_key)) -> dict[str, str]:
        return {"key": key}

    @router.patch("/_probe/match")
    def probe_match(value: str = Depends(if_match)) -> dict[str, str]:
        return {"value": value}

    @router.get("/_probe/boom")
    def probe_boom() -> dict[str, str]:
        raise NotFoundError("probe entity not found", recovery_action="try a different id")

    @router.get("/_probe/boom-with-job")
    def probe_boom_with_job() -> dict[str, str]:
        raise ConflictError(
            "a job is already running for this resource",
            job_id="job-01ARZ3NDEKTSV4RRFFQ69G5FAV",
        )

    @router.get("/_probe/role-not-granted")
    def probe_role_not_granted() -> dict[str, str]:
        raise RoleNotGrantedError("Role 'designated_editorial_approver' is not granted.")

    app.include_router(router)
    register_exception_handlers(app)
    app.add_middleware(CorrelationIdMiddleware)
    return app


@pytest.fixture
def probe_client(uow_factory: UnitOfWorkFactory) -> Iterator[TestClient]:
    """The local owner must already exist for `get_owner_id` to resolve --
    the probe app has no lifespan of its own to provision it (unlike
    `create_app`), so this fixture does it explicitly via the same
    `identity_service.ensure_local_owner` production code uses, then seeds
    `app.state.owner_id` from the id it returns.
    """
    with uow_factory() as uow:
        owner = ensure_local_owner(uow, "Test Owner")
        uow.commit()

    with TestClient(_build_probe_app(uow_factory, owner.id)) as test_client:
        yield test_client


# --- GET /api/v1/health ---


def test_health_returns_200_and_live_alembic_head_revision(client: TestClient) -> None:
    script = ScriptDirectory.from_config(alembic_guard.build_alembic_config())
    expected_head = script.get_current_head()

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["schema_revision"] == expected_head


# --- Request/correlation ids ---


def test_response_carries_request_and_correlation_id_headers(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.headers.get("X-Request-Id")
    assert response.headers.get("X-Correlation-Id")


def test_two_requests_get_distinct_request_ids(client: TestClient) -> None:
    first = client.get("/api/v1/health")
    second = client.get("/api/v1/health")
    assert first.headers["X-Request-Id"] != second.headers["X-Request-Id"]


def test_inbound_correlation_id_is_echoed_back(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"X-Correlation-Id": "caller-supplied-id"})
    assert response.headers["X-Correlation-Id"] == "caller-supplied-id"


# --- Owner seam (DAT-01 / spec §5.1: "Client-supplied owner IDs are ignored or rejected") ---


def test_get_owner_id_dependency_takes_no_client_supplied_input() -> None:
    """`get_owner_id` (`api/dependencies.py`) has exactly one parameter,
    the raw ASGI `Request` -- there is no `Header`/`Query`/body parameter
    for any route built on it to ever read a client-supplied owner id
    from. It returns `request.app.state.owner_id`, cached at lifespan
    startup from the provisioned singleton local owner; no database call
    happens on this path at all.
    """
    assert list(inspect.signature(get_owner_id).parameters) == ["request"]


def test_owner_seam_ignores_x_owner_id_header(
    probe_client: TestClient, uow_factory: UnitOfWorkFactory
) -> None:
    with uow_factory() as uow:
        real_owner_id = uow.owners.get_local_owner().id

    response = probe_client.get(
        "/api/v1/_probe/owner", headers={"X-Owner-Id": "attacker-supplied-owner"}
    )

    assert response.status_code == 200
    assert response.json()["owner_id"] == real_owner_id


def test_owner_seam_ignores_owner_id_query_param(
    probe_client: TestClient, uow_factory: UnitOfWorkFactory
) -> None:
    with uow_factory() as uow:
        real_owner_id = uow.owners.get_local_owner().id

    response = probe_client.get(
        "/api/v1/_probe/owner", params={"owner_id": "attacker-supplied-owner"}
    )

    assert response.status_code == 200
    assert response.json()["owner_id"] == real_owner_id


def test_owner_seam_ignores_owner_id_body_field(
    probe_client: TestClient, uow_factory: UnitOfWorkFactory
) -> None:
    with uow_factory() as uow:
        real_owner_id = uow.owners.get_local_owner().id

    response = probe_client.post(
        "/api/v1/_probe/owner",
        json={"owner_id": "attacker-supplied-owner", "note": "hello"},
    )

    assert response.status_code == 200
    assert response.json()["owner_id"] == real_owner_id


# --- Error envelope (spec §5.1) ---


def test_raised_yuno_error_produces_spec_error_envelope(probe_client: TestClient) -> None:
    response = probe_client.get("/api/v1/_probe/boom")

    assert response.status_code == 404
    body = response.json()
    assert _ERROR_ENVELOPE_KEYS <= body.keys()
    assert body["code"] == "not_found"
    assert body["message"] == "probe entity not found"
    assert body["retryable"] is False
    assert body["recovery_action"] == "try a different id"
    assert body["request_id"] == response.headers["X-Request-Id"]
    assert body["correlation_id"] == response.headers["X-Correlation-Id"]


def test_unknown_path_produces_spec_error_envelope(client: TestClient) -> None:
    """Routing failures use the same envelope as every other error."""
    response = client.get("/api/v1/this-path-does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert _ERROR_ENVELOPE_KEYS <= body.keys()
    assert body["code"] == "not_found"
    assert body["retryable"] is False
    assert body["request_id"] == response.headers["X-Request-Id"]
    assert body["correlation_id"] == response.headers["X-Correlation-Id"]


def test_wrong_method_produces_spec_error_envelope(client: TestClient) -> None:
    response = client.post("/api/v1/health")

    assert response.status_code == 405
    body = response.json()
    assert _ERROR_ENVELOPE_KEYS <= body.keys()
    assert body["code"] == "method_not_allowed"


# --- Idempotency-Key / If-Match dependencies (spec §5.1) ---


def test_missing_idempotency_key_returns_400(probe_client: TestClient) -> None:
    response = probe_client.post("/api/v1/_probe/idempotent")

    assert response.status_code == 400
    body = response.json()
    assert _ERROR_ENVELOPE_KEYS <= body.keys()
    assert body["code"] == "malformed_request"


def test_present_idempotency_key_is_accepted(probe_client: TestClient) -> None:
    response = probe_client.post(
        "/api/v1/_probe/idempotent", headers={"Idempotency-Key": "key-123"}
    )

    assert response.status_code == 200
    assert response.json() == {"key": "key-123"}


def test_missing_if_match_returns_412(probe_client: TestClient) -> None:
    response = probe_client.patch("/api/v1/_probe/match")

    assert response.status_code == 412
    body = response.json()
    assert _ERROR_ENVELOPE_KEYS <= body.keys()
    assert body["code"] == "precondition_failed"


def test_present_if_match_is_accepted(probe_client: TestClient) -> None:
    response = probe_client.patch("/api/v1/_probe/match", headers={"If-Match": "etag-abc"})

    assert response.status_code == 200
    assert response.json() == {"value": "etag-abc"}


# --- Regression tests ---


def test_openapi_schema_has_no_router_level_202_for_health(client: TestClient) -> None:
    """`api/app.py`'s `api_router` must not declare a router-level
    `202: {"model": JobRefResponse}` response: FastAPI merges router-level
    `responses` into every nested route's OpenAPI and cannot subtract them
    back out per-route, so `/health` -- which can only ever return `200` --
    would document a phantom `202 JobRef` response. Only the
    universally-accurate `default` error response belongs at router level.
    """
    schema = client.app.openapi()
    health_responses = schema["paths"]["/api/v1/health"]["get"]["responses"]

    assert "202" not in health_responses
    assert set(health_responses) == {"200", "default"}


def test_yuno_error_job_id_appears_in_error_envelope(probe_client: TestClient) -> None:
    """`api/errors.py` must pass `exc.job_id` through directly rather than
    `getattr(exc, "job_id", None)`. Spec §5.1 lists `job_id` as a
    legitimate optional field of the error envelope.
    """
    response = probe_client.get("/api/v1/_probe/boom-with-job")

    assert response.status_code == 409
    body = response.json()
    assert _ERROR_ENVELOPE_KEYS <= body.keys()
    assert body["job_id"] == "job-01ARZ3NDEKTSV4RRFFQ69G5FAV"


def test_role_not_granted_error_http_status_is_422() -> None:
    """Spec §5.1's principal statuses are exactly
    `400/404/409/410/412/422/423/429/503/504` -- `401`/`403` appear nowhere
    in the spec, deliberately, since PRD DAT-01 specifies no MVP
    authentication. `RoleNotGrantedError` must not use `403`.
    """
    assert RoleNotGrantedError("unused").http_status == 422


def test_role_not_granted_error_maps_to_422_through_the_api(probe_client: TestClient) -> None:
    """A missing role grant is a domain-policy violation: it surfaces as
    `422` with the distinct `role_not_granted` code.
    """
    response = probe_client.get("/api/v1/_probe/role-not-granted")

    assert response.status_code == 422
    body = response.json()
    assert _ERROR_ENVELOPE_KEYS <= body.keys()
    assert body["code"] == "role_not_granted"


def test_overlong_correlation_id_falls_back_to_generated_id(client: TestClient) -> None:
    """`middleware.CorrelationIdMiddleware` must reject an inbound
    `X-Correlation-Id` longer than its transport-hygiene cap and fall back
    to a freshly generated id instead of reflecting the oversized input.
    """
    huge_value = "a" * 200_001

    response = client.get("/api/v1/health", headers={"X-Correlation-Id": huge_value})

    returned = response.headers["X-Correlation-Id"]
    assert returned != huge_value
    assert len(returned) < 200


def test_correlation_id_with_control_characters_falls_back_to_generated_id(
    client: TestClient,
) -> None:
    """A value can be short and still unsafe. A control character (here, a
    bell character embedded in an otherwise plausible-looking id) must not
    be reflected back into the response header -- the app must validate
    this itself rather than relying on uvicorn's header-value regex as a
    backstop.
    """
    malicious_value = "trace-\x07-id"

    response = client.get("/api/v1/health", headers={"X-Correlation-Id": malicious_value})

    assert response.headers["X-Correlation-Id"] != malicious_value


def test_lifespan_disposes_engine_when_startup_fails(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`api/app.py`'s lifespan must wrap its body in `try`/`finally`
    (matching `migrations/env.py`'s pattern), not call `engine.dispose()`
    only after `yield` -- unreachable when `require_single_head` (or
    `ensure_local_owner`) raises during startup, which would leak the
    connection pool until GC.
    """
    disposed: list[Engine] = []
    original_dispose = Engine.dispose

    def spy_dispose(self: Engine, *args: object, **kwargs: object) -> None:
        disposed.append(self)
        original_dispose(self, *args, **kwargs)

    def _raise_startup_error(engine: Engine) -> int:
        raise RuntimeError("startup boom")

    monkeypatch.setattr(Engine, "dispose", spy_dispose)
    monkeypatch.setattr("yuno.api.app.require_single_head", _raise_startup_error)

    app = create_app(settings)

    with pytest.raises(RuntimeError, match="startup boom"), TestClient(app):
        pass

    assert len(disposed) == 1
