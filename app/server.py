"""Small asynchronous environment provisioning REST API simulator."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


VALID_REGIONS = {"us-east"}
VALID_SIZES = {"small", "medium"}
RESOURCES = ("network", "compute")
INJECTABLE_FAILURES = {"compute"}
FAILURE_MESSAGE = "Injected failure while creating resource 'compute'"


@contextmanager
def database(path: str):
    """Commit successful work and always close the connection."""
    db = sqlite3.connect(path)
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize_database(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with database(path) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS environments (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, region TEXT NOT NULL,
                size TEXT NOT NULL, status TEXT NOT NULL, created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS operations (
                id TEXT PRIMARY KEY, environment_id TEXT NOT NULL,
                status TEXT NOT NULL, error TEXT,
                FOREIGN KEY(environment_id) REFERENCES environments(id)
            );
            CREATE TABLE IF NOT EXISTS resources (
                id TEXT PRIMARY KEY, environment_id TEXT NOT NULL,
                name TEXT NOT NULL, status TEXT NOT NULL,
                FOREIGN KEY(environment_id) REFERENCES environments(id)
            );
            """
        )


def row_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def provision(db_path: str, environment_id: str, operation_id: str,
              fail_resource: str | None, step_delay: float) -> None:
    """Create resources in order and publish terminal state after persistence."""
    for resource in RESOURCES:
        if step_delay:
            time.sleep(step_delay)
        with database(db_path) as db:
            db.row_factory = sqlite3.Row
            if fail_resource == resource:
                db.execute(
                    "DELETE FROM resources WHERE environment_id=?", (environment_id,)
                )
                db.execute(
                    "UPDATE environments SET status='FAILED' WHERE id=?", (environment_id,)
                )
                db.execute(
                    "UPDATE operations SET status='FAILED', error=? WHERE id=?",
                    (FAILURE_MESSAGE, operation_id),
                )
                return
            db.execute(
                "INSERT INTO resources(id, environment_id, name, status) VALUES (?, ?, ?, 'READY')",
                (str(uuid.uuid4()), environment_id, resource),
            )
    with database(db_path) as db:
        db.execute("UPDATE environments SET status='READY' WHERE id=?", (environment_id,))
        db.execute("UPDATE operations SET status='SUCCEEDED' WHERE id=?", (operation_id,))


def make_handler(db_path: str, step_delay: float, allow_failure_injection: bool):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ProvisioningAPI/1.0"

        def log_message(self, _format, *_args):
            return

        def respond(self, status: int, payload: dict) -> None:
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def read_json(self) -> dict:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                value = json.loads(self.rfile.read(length))
            except (ValueError, json.JSONDecodeError):
                raise ValueError("Request body must be a JSON object") from None
            if not isinstance(value, dict):
                raise ValueError("Request body must be a JSON object")
            return value

        def do_POST(self):
            if self.path != "/environments":
                self.respond(404, {"error": "not_found"})
                return
            try:
                body = self.read_json()
            except ValueError as exc:
                self.respond(400, {"error": "invalid_json", "message": str(exc)})
                return

            errors = {}
            name = body.get("name")
            region = body.get("region")
            size = body.get("size")
            if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,63}", name):
                errors["name"] = "must be 1-63 characters using letters, digits, or hyphens"
            if not isinstance(region, str) or region not in VALID_REGIONS:
                errors["region"] = "must be one of: us-east"
            if not isinstance(size, str) or size not in VALID_SIZES:
                errors["size"] = "must be one of: small, medium"
            injection = body.get("failure_injection")
            fail_resource = None
            if injection is not None:
                if not allow_failure_injection:
                    errors["failure_injection"] = "is disabled"
                elif (not isinstance(injection, dict) or
                      not isinstance(injection.get("resource"), str) or
                      injection.get("resource") not in INJECTABLE_FAILURES):
                    errors["failure_injection"] = "resource must be compute"
                else:
                    fail_resource = injection["resource"]
            if errors:
                self.respond(400, {"error": "validation_error", "details": errors})
                return

            environment_id, operation_id = str(uuid.uuid4()), str(uuid.uuid4())
            with database(db_path) as db:
                db.execute(
                    "INSERT INTO environments VALUES (?, ?, ?, ?, 'PROVISIONING', ?)",
                    (environment_id, name, region, size, time.time()),
                )
                db.execute(
                    "INSERT INTO operations(id, environment_id, status) VALUES (?, ?, 'PENDING')",
                    (operation_id, environment_id),
                )
            threading.Thread(
                target=provision,
                args=(db_path, environment_id, operation_id, fail_resource, step_delay),
                daemon=True,
            ).start()
            self.respond(202, {
                "environment_id": environment_id,
                "operation_id": operation_id,
                "status": "PENDING",
            })

        def do_DELETE(self):
            segments = urlparse(self.path).path.strip("/").split("/")
            if len(segments) != 2 or segments[0] != "environments":
                self.respond(404, {"error": "not_found"})
                return

            environment_id = segments[1]
            with database(db_path) as db:
                row = db.execute(
                    "SELECT status FROM environments WHERE id=?", (environment_id,)
                ).fetchone()
                if row is None:
                    self.respond(404, {"error": "not_found"})
                    return
                if row[0] == "PROVISIONING":
                    self.respond(409, {
                        "error": "environment_provisioning",
                        "message": "cannot delete an environment while it is provisioning",
                    })
                    return

                db.execute("DELETE FROM resources WHERE environment_id=?", (environment_id,))
                db.execute("DELETE FROM environments WHERE id=?", (environment_id,))

            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            parsed = urlparse(self.path)
            segments = parsed.path.strip("/").split("/")
            with database(db_path) as db:
                db.row_factory = sqlite3.Row
                if parsed.path == "/environments":
                    name = parse_qs(parsed.query, keep_blank_values=True).get("name", [None])[0]
                    if name is None:
                        self.respond(400, {"error": "name_filter_required"})
                        return
                    rows = db.execute(
                        "SELECT id, name, region, size, status FROM environments WHERE name=?",
                        (name,),
                    ).fetchall()
                    self.respond(200, {"items": [row_dict(row) for row in rows]})
                    return
                if parsed.path == "/operations":
                    environment_name = parse_qs(
                        parsed.query, keep_blank_values=True
                    ).get("environment_name", [None])[0]
                    if environment_name is None:
                        self.respond(400, {"error": "environment_name_filter_required"})
                        return
                    rows = db.execute(
                        "SELECT o.id, o.environment_id, o.status, o.error "
                        "FROM operations o JOIN environments e ON e.id=o.environment_id "
                        "WHERE e.name=?",
                        (environment_name,),
                    ).fetchall()
                    self.respond(200, {"items": [row_dict(row) for row in rows]})
                    return
                if len(segments) == 2 and segments[0] == "operations":
                    row = db.execute(
                        "SELECT id, environment_id, status, error FROM operations WHERE id=?",
                        (segments[1],),
                    ).fetchone()
                    if row is None:
                        self.respond(404, {"error": "not_found"})
                    else:
                        self.respond(200, row_dict(row))
                    return
                if len(segments) == 2 and segments[0] == "environments":
                    row = db.execute(
                        "SELECT id, name, region, size, status FROM environments WHERE id=?",
                        (segments[1],),
                    ).fetchone()
                    if row is None:
                        self.respond(404, {"error": "not_found"})
                    else:
                        environment = row_dict(row)
                        resources = db.execute(
                            "SELECT name, status FROM resources WHERE environment_id=? ORDER BY name",
                            (segments[1],),
                        ).fetchall()
                        environment["resources"] = [row_dict(item) for item in resources]
                        self.respond(200, environment)
                    return
            self.respond(404, {"error": "not_found"})

    return Handler


def create_server(host: str = "127.0.0.1", port: int = 8080,
                  db_path: str | None = None, step_delay: float | None = None,
                  allow_failure_injection: bool = True) -> ThreadingHTTPServer:
    db_path = db_path or os.environ.get("PROVISIONING_DB", "provisioning.sqlite3")
    step_delay = (float(os.environ.get("PROVISIONING_STEP_DELAY_SECONDS", "0.05"))
                  if step_delay is None else step_delay)
    initialize_database(db_path)
    return ThreadingHTTPServer(
        (host, port), make_handler(db_path, step_delay, allow_failure_injection)
    )


def main() -> None:
    server = create_server()
    print(f"Provisioning API listening on http://{server.server_address[0]}:{server.server_address[1]}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
