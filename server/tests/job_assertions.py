"""Assertions for the asynchronous durable worker."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient


def wait_for_job(
    client: TestClient, response_or_job_id, expected: str = "succeeded", timeout: float = 5
) -> dict[str, object]:
    job_id = (
        response_or_job_id
        if isinstance(response_or_job_id, str)
        else response_or_job_id.json()["job_id"]
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = client.get(f"/api/v1/jobs/{job_id}")
        if current.status_code == 200 and current.json()["status"] == expected:
            return current.json()
        time.sleep(0.01)
    raise AssertionError(
        f"job {job_id} did not reach {expected}; latest={current.json()}"
    )
