"""Pytest end-to-end scenarios against the real provisioning HTTP API."""

import time
import uuid
from urllib.parse import quote

import pytest

from tests.helpers import request_json, wait_for_operation


def assert_rejected_without_state(base_url, payload, expected_field):
    status, result = request_json(base_url, "/environments", "POST", payload)
    assert status == 400, result
    assert result["error"] == "validation_error"
    assert expected_field in result["details"]

    query = quote(payload["name"], safe="")
    status, environments = request_json(base_url, f"/environments?name={query}")
    assert status == 200, environments
    assert environments["items"] == []

    status, operations = request_json(
        base_url, f"/operations?environment_name={query}"
    )
    assert status == 200, operations
    assert operations["items"] == []


def test_happy_path_persists_configuration_and_complete_resources(base_url, create_environment):
    payload, status, accepted = create_environment()
    assert status == 202, accepted
    assert accepted["status"] == "PENDING"
    assert accepted["environment_id"]
    assert accepted["operation_id"]

    operation = wait_for_operation(base_url, accepted["operation_id"])
    assert operation["status"] == "SUCCEEDED", operation
    assert operation["error"] is None
    status, environment = request_json(
        base_url, f"/environments/{accepted['environment_id']}"
    )
    assert status == 200, environment
    assert environment["status"] == "READY"
    assert environment["name"] == payload["name"]
    assert environment["region"] == payload["region"]
    assert environment["size"] == payload["size"]
    assert environment["resources"] == [
        {"name": "compute", "status": "READY"},
        {"name": "network", "status": "READY"},
    ]


def test_missing_size_is_rejected_without_creating_environment_or_operation(base_url):
    payload = {"name": f"invalid-{uuid.uuid4().hex}", "region": "us-east"}
    assert_rejected_without_state(base_url, payload, "size")


def test_unsupported_region_is_rejected_without_creating_environment_or_operation(base_url):
    payload = {
        "name": f"invalid-{uuid.uuid4().hex}",
        "region": "moon-1",
        "size": "small",
    }
    assert_rejected_without_state(base_url, payload, "region")


def test_non_string_region_is_rejected_without_creating_environment_or_operation(base_url):
    payload = {
        "name": f"invalid-{uuid.uuid4().hex}",
        "region": {"unexpected": "object"},
        "size": "small",
    }
    assert_rejected_without_state(base_url, payload, "region")


def test_malformed_json_is_rejected_without_creating_environment_or_operation(base_url):
    name = f"invalid-{uuid.uuid4().hex}"
    malformed_body = (
        f'{{"name":"{name}","region":"us-east","size":"small",}}'
    )
    status, result = request_json(
        base_url, "/environments", method="POST", body=malformed_body
    )
    assert status == 400, result
    assert result == {
        "error": "invalid_json",
        "message": "Request body must be a JSON object",
    }

    query = quote(name, safe="")
    status, environments = request_json(base_url, f"/environments?name={query}")
    assert status == 200
    assert environments["items"] == []
    status, operations = request_json(
        base_url, f"/operations?environment_name={query}"
    )
    assert status == 200
    assert operations["items"] == []


def test_injected_compute_failure_rolls_back_prior_resources(
    base_url, create_environment
):
    _payload, status, accepted = create_environment(
        failure_injection={"resource": "compute"}
    )
    assert status == 202, accepted
    operation = wait_for_operation(base_url, accepted["operation_id"])
    assert operation["status"] == "FAILED", operation
    assert operation["error"] == "Injected failure while creating resource 'compute'"

    status, environment = request_json(
        base_url, f"/environments/{accepted['environment_id']}"
    )
    assert status == 200, environment
    assert environment["status"] == "FAILED"
    assert environment["resources"] == []


def test_delete_ready_environment_removes_it_and_its_resources(
    base_url, create_environment
):
    payload, status, accepted = create_environment()
    assert status == 202, accepted
    operation = wait_for_operation(base_url, accepted["operation_id"])
    assert operation["status"] == "SUCCEEDED", operation

    status, response = request_json(
        base_url, f"/environments/{accepted['environment_id']}", method="DELETE"
    )
    assert status == 204
    assert response is None

    status, response = request_json(
        base_url, f"/environments/{accepted['environment_id']}"
    )
    assert status == 404
    assert response == {"error": "not_found"}
    status, listed = request_json(
        base_url, f"/environments?name={quote(payload['name'], safe='')}"
    )
    assert status == 200
    assert listed["items"] == []

    status, operation_history = request_json(
        base_url, f"/operations/{accepted['operation_id']}"
    )
    assert status == 200
    assert operation_history["status"] == "SUCCEEDED"


def test_get_nonexistent_environment_returns_not_found(base_url):
    environment_id = str(uuid.uuid4())
    status, response = request_json(base_url, f"/environments/{environment_id}")
    assert status == 404
    assert response == {"error": "not_found"}


def test_delete_while_provisioning_returns_conflict(slow_base_url):
    payload = {
        "name": f"assessment-{uuid.uuid4().hex[:12]}",
        "region": "us-east",
        "size": "small",
    }
    status, accepted = request_json(
        slow_base_url, "/environments", method="POST", body=payload
    )
    assert status == 202, accepted
    assert accepted["status"] == "PENDING"

    status, response = request_json(
        slow_base_url,
        f"/environments/{accepted['environment_id']}",
        method="DELETE",
    )
    assert status == 409
    assert response["error"] == "environment_provisioning"

    operation = wait_for_operation(
        slow_base_url, accepted["operation_id"], timeout=3
    )
    assert operation["status"] == "SUCCEEDED", operation
    status, environment = request_json(
        slow_base_url, f"/environments/{accepted['environment_id']}"
    )
    assert status == 200
    assert environment["status"] == "READY"


def test_client_deadline_reports_last_state_and_operation_can_finish_later(
    base_url, create_environment
):
    _payload, status, accepted = create_environment()
    assert status == 202, accepted
    started = time.monotonic()
    with pytest.raises(TimeoutError, match="last state:.*PENDING"):
        wait_for_operation(base_url, accepted["operation_id"], timeout=0.01)
    assert time.monotonic() - started < 0.5

    operation = wait_for_operation(base_url, accepted["operation_id"], timeout=2)
    assert operation["status"] == "SUCCEEDED", operation
    status, environment = request_json(
        base_url, f"/environments/{accepted['environment_id']}"
    )
    assert status == 200, environment
    assert environment["status"] == "READY"
    assert len(environment["resources"]) == 2
