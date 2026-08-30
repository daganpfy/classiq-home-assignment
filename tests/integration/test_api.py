from __future__ import annotations

import os
import time

import httpx
import pytest

from tests.helpers import hadamard_qasm

API_URL = os.getenv("API_URL")

pytestmark = pytest.mark.skipif(
    not API_URL,
    reason="Set API_URL to run integration tests against a live stack.",
)


@pytest.fixture(scope="module")
def client() -> httpx.Client:
    return httpx.Client(base_url=API_URL, timeout=30.0)


def _wait_for_completion(client: httpx.Client, task_id: str, timeout_s: float = 90.0) -> dict:
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        response = client.get(f"/tasks/{task_id}")
        last = response.json()
        if last.get("status") in {"completed", "failed"}:
            return last
        time.sleep(0.4)
    raise AssertionError(f"Task {task_id} did not finish. Last payload: {last}")


def test_submit_process_and_retrieve(client: httpx.Client) -> None:
    response = client.post("/tasks", json={"qc": hadamard_qasm()})
    assert response.status_code == 202
    body = response.json()
    assert body["message"] == "Task submitted successfully."
    assert body["task_id"]

    task_id = body["task_id"]
    result = _wait_for_completion(client, task_id)
    assert result["status"] == "completed"
    assert sum(result["result"].values()) == 1024


def test_get_unknown_task(client: httpx.Client) -> None:
    response = client.get("/tasks/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json() == {"status": "error", "message": "Task not found."}


def test_invalid_qasm_is_rejected(client: httpx.Client) -> None:
    response = client.post("/tasks", json={"qc": "not-a-circuit"})
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert "Invalid QASM3" in payload["message"]


def test_missing_qc_is_rejected(client: httpx.Client) -> None:
    response = client.post("/tasks", json={})
    assert response.status_code == 422


def test_health(client: httpx.Client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["postgres"] is True
    assert body["checks"]["rabbitmq"] is True
