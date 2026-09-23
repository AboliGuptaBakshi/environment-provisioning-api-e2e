"""Pytest fixtures for isolated provisioning API end-to-end tests."""

import threading
import uuid

import pytest

from app.server import create_server
from tests.helpers import request_json


@pytest.fixture
def api_server_factory(tmp_path):
    """Start isolated servers with configurable provisioning delay for a test."""
    running_servers = []

    def start(step_delay=0.08):
        db_path = tmp_path / f"assessment-{len(running_servers)}.sqlite3"
        server = create_server(port=0, db_path=str(db_path), step_delay=step_delay)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        running_servers.append((server, thread))
        return server

    try:
        yield start
    finally:
        for server, thread in reversed(running_servers):
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


@pytest.fixture
def api_server(api_server_factory):
    """Run an ephemeral HTTP server with a fresh database for each test."""
    return api_server_factory()


@pytest.fixture
def base_url(api_server):
    """Base URL for the test's isolated API server."""
    host, port = api_server.server_address
    return f"http://{host}:{port}"


@pytest.fixture
def slow_base_url(api_server_factory):
    """Provide time to observe the provisioning state before a test action."""
    server = api_server_factory(step_delay=1.0)
    host, port = server.server_address
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
