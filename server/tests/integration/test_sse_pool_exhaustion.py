"""P1 (IDK-504 perf run) -- SSE stream lifetime vs. the connection pool.

`GET /api/v1/events` (`stream_events`, `yuno/api/routes/events.py`) polls
`retained_event_frames` once a second until `request.is_disconnected()`
becomes true. A sweep of short-lived browser contexts was observed to
exhaust the SQLAlchemy pool (`QueuePool limit of size 5 overflow 10
reached`), after which data-dependent routes stopped rendering.

Diagnosis (see the P1 packet report for full command/output evidence):
`retained_event_frames` (`events.py:44-53`) is a synchronous, blocking
function called directly from the `stream_events` coroutine
(`events.py:61-88`, before the fix). Nothing in that call path ever
`await`s, so it runs to completion directly on the single ASGI event loop
thread -- while it runs, *no other coroutine in the whole process* (any
other request, any other client's own poll) can make progress. A burst of
concurrently-connecting SSE clients therefore doesn't overlap cheaply the
way async I/O normally would: each connection's first poll fully
serializes behind the last, and while that pile-up is in flight the event
loop cannot even dispatch unrelated `def` routes to their threadpool
workers. Measured directly against this repo's unfixed code: 20
concurrent `GET /api/v1/events` opens, immediately abandoned, made an
unrelated, otherwise ~100ms route (`GET /api/v1/jobs`) take upwards of 10s
and eventually deadlock -- this is what "data-dependent routes stop
rendering" looks like from the client's side.
`request.is_disconnected()` itself was verified separately to work
correctly under a real ASGI server (streams do stop polling once their
client actually disconnects) -- the bug is event-loop starvation from the
blocking call, not a failure to detect disconnects.

This module drives the app through a *real* ASGI server (`uvicorn`
running in a background thread, talked to over a genuine loopback TCP
socket via `httpx`) rather than Starlette's `TestClient`/`httpx.
ASGITransport`. Both of those drive the whole app through a single
`portal.call(...)`/`await self.app(...)` that only returns once the
*entire* response body is complete -- see `_TestClientTransport.
handle_request` (`starlette/testclient.py:299-305`) and `ASGITransport.
handle_async_request` (`httpx/_transports/asgi.py:134-146`): both
implement `receive()` as "return `http.disconnect` once the response is
already complete". Since `stream_events` never completes its body until
`is_disconnected()` fires, driving it through either of those transports
deadlocks. Confirmed manually (not as a test here, because the hang is
permanent and would leave a zombie thread polling forever for the rest of
the test session): a bare `TestClient(app).get("/api/v1/events")` for
this route, run on a background thread and joined with a 6s timeout, was
still alive/un-returned after the timeout, both before and after the fix
below -- the deadlock is in the *test transport*, not the route. Only a
real ASGI server, where disconnect delivery is driven by an actual socket
callback independent of response completion and where unrelated requests
are genuinely concurrent, can exercise the code path this ticket is
about.
"""

from __future__ import annotations

import socket
import threading
import time
from typing import Self

import httpx
import uvicorn
from fastapi import FastAPI

from yuno.api.app import create_app
from yuno.config import Settings


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class _ThreadedServer:
    """Runs the real ASGI app under `uvicorn` on a loopback socket.

    A background thread gives the server its own asyncio event loop, so
    (a) disconnects are detected the way production detects them -- via
    the transport's socket callback -- rather than being gated on the
    whole response completing (see module docstring), and (b) requests
    are genuinely concurrent, which is exactly the condition this bug
    depends on.
    """

    def __init__(self, app: FastAPI) -> None:
        self.app = app
        self.port = _free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        config = uvicorn.Config(
            app, host="127.0.0.1", port=self.port, log_level="warning"
        )
        self.server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self.server.run, daemon=True)

    def __enter__(self) -> Self:
        self._thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started and time.monotonic() < deadline:
            time.sleep(0.02)
        assert self.server.started, "uvicorn did not report startup within 10s"
        deadline = time.monotonic() + 10
        while not hasattr(self.app.state, "engine") and time.monotonic() < deadline:
            time.sleep(0.02)
        assert hasattr(self.app.state, "engine"), "app lifespan did not finish startup"
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.server.should_exit = True
        self._thread.join(timeout=10)


def _open_and_abandon(base_url: str, results: list, idx: int) -> None:
    """Opens one SSE connection, reads a frame, then abruptly closes the
    socket without consuming the rest of the (infinite) stream -- the
    same thing a browser tab close does to a live `EventSource`.

    Records `("ok", status_code)` or `("error", repr(exc))` into
    `results[idx]` instead of raising, so a burst of N of these (run
    concurrently, one thread each) can be joined and inspected without
    one failure hiding the others.
    """
    try:
        with (
            httpx.Client(timeout=15.0) as client,
            client.stream("GET", f"{base_url}/api/v1/events") as response,
        ):
            lines = response.iter_lines()
            next(lines)
            results[idx] = ("ok", response.status_code)
        # Exiting the `with` blocks above closes the connection without
        # draining the body -- httpx cannot keep-alive a partially read
        # stream, so it tears down the socket, which the OS reports to
        # the server as a real TCP close.
    except Exception as exc:  # noqa: BLE001 - captured as a result, not a raise
        results[idx] = ("error", repr(exc))


def test_concurrent_sse_burst_does_not_starve_unrelated_routes_or_leak_the_pool(
    settings: Settings,
) -> None:
    """Reproduces the IDK-504 perf-run symptom: a sweep of short-lived
    browser contexts opening `/api/v1/events` concurrently and vanishing
    mid-stream.

    On the unfixed code this either times out outright or makes an
    unrelated, otherwise near-instant route (`GET /api/v1/jobs`) take far
    longer than any reasonable bound, because the blocking DB read inside
    `stream_events` runs directly on the event loop thread (see module
    docstring for the measured numbers). The fix runs that read via
    `starlette.concurrency.run_in_threadpool`.
    """
    app = create_app(settings)
    with _ThreadedServer(app) as server:
        pool = app.state.engine.pool

        client_count = 20
        results: list[object] = [None] * client_count
        threads = [
            threading.Thread(
                target=_open_and_abandon, args=(server.base_url, results, i)
            )
            for i in range(client_count)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)

        assert all(not thread.is_alive() for thread in threads), (
            f"{sum(t.is_alive() for t in threads)}/{client_count} SSE client "
            "threads never returned within 20s"
        )
        errors = [r for r in results if r is not None and r[0] == "error"]
        assert not errors, (
            f"{len(errors)}/{client_count} SSE connections failed: {errors[:5]}"
        )

        # The actual regression check: a concurrent, unrelated,
        # data-dependent route must stay responsive. This is what "data
        # -dependent routes stop rendering" looks like from a client.
        with httpx.Client(timeout=10.0) as client:
            start = time.monotonic()
            response = client.get(f"{server.base_url}/api/v1/jobs")
            elapsed = time.monotonic() - start
        assert response.status_code == 200
        assert elapsed < 3.0, (
            f"GET /api/v1/jobs took {elapsed:.2f}s immediately after a "
            f"{client_count}-connection SSE burst -- the event loop was "
            "starved by the blocking per-poll DB read instead of releasing "
            "it to other coroutines."
        )

        # Direct pool evidence, per the ticket's ask: checked-out
        # connections must return to zero once every client is gone, not
        # stay pinned near the ceiling.
        time.sleep(1.0)
        assert pool.checkedout() == 0, (
            f"engine.pool.status()={pool.status()!r} -- connections are "
            "still checked out after every client disconnected"
        )
