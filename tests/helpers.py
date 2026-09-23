"""HTTP helpers shared by the end-to-end tests."""

import json
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def request_json(base_url: str, path: str, method: str = "GET", body: dict | None = None):
    payload = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(
        base_url + path,
        data=payload,
        method=method,
        headers={"Content-Type": "application/json"} if payload is not None else {},
    )
    try:
        response = urlopen(request, timeout=2)
    except HTTPError as exc:
        response = exc
    with response:
        response_body = response.read().decode("utf-8")
        return response.status, json.loads(response_body) if response_body else None


def wait_for_operation(base_url: str, operation_id: str, timeout: float = 2.0,
                       interval: float = 0.01) -> dict:
    """Poll to terminal state and report the last observed state on deadline."""
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        status, last = request_json(base_url, f"/operations/{operation_id}")
        if status != 200:
            raise AssertionError(f"operation lookup returned HTTP {status}: {last}")
        if last["status"] in {"SUCCEEDED", "FAILED"}:
            return last
        time.sleep(min(interval, max(0, deadline - time.monotonic())))
    raise TimeoutError(f"operation {operation_id} did not finish within {timeout}s; last state: {last}")
