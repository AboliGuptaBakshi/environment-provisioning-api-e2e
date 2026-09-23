"""End-to-end tests against an ephemeral real HTTP server."""

import tempfile
import threading
import time
import unittest
import uuid
from urllib.parse import quote

from app.server import create_server
from tests.helpers import request_json, wait_for_operation


class ProvisioningApiE2ETests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.server = create_server(
            port=0,
            db_path=f"{self.temp_dir.name}/assessment.sqlite3",
            step_delay=0.08,
        )
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=2)
        self.temp_dir.cleanup()

    def create_environment(self, **overrides):
        payload = {
            "name": f"assessment-{uuid.uuid4().hex[:12]}",
            "region": "us-east",
            "size": "small",
        }
        payload.update(overrides)
        status, result = request_json(self.base_url, "/environments", "POST", payload)
        return payload, status, result

    def assert_rejected_without_state(self, payload, expected_field):
        status, result = request_json(
            self.base_url, "/environments", "POST", payload
        )
        self.assertEqual(status, 400, result)
        self.assertEqual(result["error"], "validation_error")
        self.assertIn(expected_field, result["details"])

        query = quote(payload["name"], safe="")
        status, environments = request_json(
            self.base_url, f"/environments?name={query}"
        )
        self.assertEqual(status, 200, environments)
        self.assertEqual(environments["items"], [])

        status, operations = request_json(
            self.base_url, f"/operations?environment_name={query}"
        )
        self.assertEqual(status, 200, operations)
        self.assertEqual(operations["items"], [])

    def test_happy_path_persists_configuration_and_complete_resources(self):
        payload, status, accepted = self.create_environment()
        self.assertEqual(status, 202, accepted)
        self.assertEqual(accepted["status"], "PENDING")
        self.assertTrue(accepted["environment_id"])
        self.assertTrue(accepted["operation_id"])

        operation = wait_for_operation(self.base_url, accepted["operation_id"])
        self.assertEqual(operation["status"], "SUCCEEDED", operation)
        self.assertIsNone(operation["error"])
        status, environment = request_json(
            self.base_url, f"/environments/{accepted['environment_id']}"
        )
        self.assertEqual(status, 200, environment)
        self.assertEqual(environment["status"], "READY")
        self.assertEqual(environment["name"], payload["name"])
        self.assertEqual(environment["region"], payload["region"])
        self.assertEqual(environment["size"], payload["size"])
        self.assertEqual(environment["resources"], [
            {"name": "compute", "status": "READY"},
            {"name": "network", "status": "READY"},
        ])

    def test_missing_size_is_rejected_without_creating_environment_or_operation(self):
        payload = {"name": f"invalid-{uuid.uuid4().hex}", "region": "us-east"}
        self.assert_rejected_without_state(payload, "size")

    def test_unsupported_region_is_rejected_without_creating_environment_or_operation(self):
        payload = {
            "name": f"invalid-{uuid.uuid4().hex}",
            "region": "moon-1",
            "size": "small",
        }
        self.assert_rejected_without_state(payload, "region")

    def test_non_string_region_is_rejected_without_creating_environment_or_operation(self):
        payload = {
            "name": f"invalid-{uuid.uuid4().hex}",
            "region": {"unexpected": "object"},
            "size": "small",
        }
        self.assert_rejected_without_state(payload, "region")

    def test_injected_partial_failure_is_terminal_and_retains_prior_resource(self):
        _payload, status, accepted = self.create_environment(
            failure_injection={"resource": "compute"}
        )
        self.assertEqual(status, 202, accepted)
        operation = wait_for_operation(self.base_url, accepted["operation_id"])
        self.assertEqual(operation["status"], "FAILED", operation)
        self.assertEqual(operation["error"], "Injected failure while creating resource 'compute'")

        status, environment = request_json(
            self.base_url, f"/environments/{accepted['environment_id']}"
        )
        self.assertEqual(status, 200, environment)
        self.assertEqual(environment["status"], "FAILED")
        self.assertEqual(environment["resources"], [{"name": "network", "status": "READY"}])

    def test_client_deadline_reports_last_state_and_operation_can_finish_later(self):
        _payload, status, accepted = self.create_environment()
        self.assertEqual(status, 202, accepted)
        started = time.monotonic()
        with self.assertRaisesRegex(TimeoutError, "last state:.*PENDING"):
            wait_for_operation(self.base_url, accepted["operation_id"], timeout=0.01)
        self.assertLess(time.monotonic() - started, 0.5)

        operation = wait_for_operation(self.base_url, accepted["operation_id"], timeout=2)
        self.assertEqual(operation["status"], "SUCCEEDED", operation)
        status, environment = request_json(
            self.base_url, f"/environments/{accepted['environment_id']}"
        )
        self.assertEqual(status, 200, environment)
        self.assertEqual(environment["status"], "READY")
        self.assertEqual(len(environment["resources"]), 2)


if __name__ == "__main__":
    unittest.main()
