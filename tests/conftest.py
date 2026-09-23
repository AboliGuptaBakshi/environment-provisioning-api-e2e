"""Pytest fixtures for isolated provisioning API end-to-end tests."""

import threading
import uuid

import pytest

from app.server import create_server
from tests.helpers import request_json


@pytest.fixture
def api_server(tmp_path):
    """Run an ephemeral HTTP server with a fresh database for each test."""
    server = create_server(
        port=0,
        db_path=str(tmp_path / "assessment.sqlite3"),
        step_delay=0.08,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.fixture
def base_url(api_server):
    """Base URL for the test's isolated API server."""
    host, port = api_server.server_address
    return f"http://{host}:{port}"


@pytest.fixture
def create_environment(base_url):
    """Return a helper that submits a uniquely named valid environment request."""
    def create(**overrides):
        payload = {
            "name": f"assessment-{uuid.uuid4().hex[:12]}",
            "region": "us-east",
            "size": "small",
        }
        payload.update(overrides)
        status, result = request_json(base_url, "/environments", "POST", payload)
        return payload, status, result

    return create
