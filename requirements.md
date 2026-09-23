# Scope and test specification

## System under test

A generic Python REST API simulates provisioning one kind of environment and its resources. It provides a realistic asynchronous lifecycle without connecting to a cloud provider. Tests exercise the API and inspect persisted API state.

## Workflow contract

1. `POST /environments` accepts `{ "name": ..., "region": ..., "size": ... }` and returns HTTP 202 with environment and operation IDs.
2. Provisioning runs asynchronously and creates `network` followed by `compute` resources.
3. `GET /operations/{id}` exposes `PENDING`, `SUCCEEDED`, or `FAILED` and its error, if any.
4. `GET /environments/{id}` exposes environment configuration, lifecycle state, and created resources. Filtered `GET /environments?name=...` and `GET /operations?environment_name=...` support no-state validation checks.
5. `DELETE /environments/{id}` synchronously deletes a `READY` or `FAILED` environment and its resources, returning `204 No Content`; its completed operation records remain available as history. Deleting while `PROVISIONING` returns `409 Conflict`; deleting an unknown ID returns `404 Not Found`. A deleted environment is no longer returned by GET or the filtered environment list.

The supported region is `us-east`; sizes are `small` and `medium`. Names must be 1–63 characters and contain only letters, digits, and hyphens. On an injected `compute` failure, the simulator deletes resources already created for that environment and marks both the environment and operation failed in the same database transaction. The resulting environment has no resources. For deterministic assessment testing, the simulator accepts optional `failure_injection: {"resource": "compute"}`; this fails at that named step after network creation. Failure injection is configurable and enabled by default for local/assessment use.

The API is a small Python standard-library HTTP server with SQLite persistence; pytest tests use HTTP over localhost to exercise the actual REST boundary. Pytest is the only test dependency.

## Requirements and traceability

| ID | Requirement | Planned verification |
|---|---|---|
| R1 | A valid request is accepted with environment and operation identifiers. | Submit via REST; assert response fields and retrieve the identified records. |
| R2 | Successful provisioning reaches a terminal success state within a bounded client deadline. | Poll operation using a monotonic deadline; assert terminal state. |
| R3 | A successful environment reflects requested configuration and has the complete expected resource set. | Read environment and resources after success; assert values and completeness. |
| R4 | Invalid or unsupported input is rejected with useful validation details and creates no environment or operation. | Separate pytest cases cover malformed JSON, a missing required size, unsupported region, and non-string region; each checks the relevant error and confirms both environment and operation lists remain empty for its unique name. |
| R5 | A deterministic injected `compute` failure produces a terminal failed operation and stable reason. | Inject failure after network creation; poll to `FAILED` and assert the stable error. |
| R6 | An injected `compute` failure rolls back resources already created for that environment. | Read the failed environment and assert its resource list is empty. |
| R7 | Deleting a `READY` or `FAILED` environment removes it and its resources while preserving operation history; deleting while `PROVISIONING` is rejected. | For `READY` and `FAILED` environments, DELETE and assert `204`, GET returns `404`, and the completed operation remains readable. For the conflict case, GET and assert `PROVISIONING` immediately before DELETE, then assert `409`. |
| R8 | GET for an unknown or deleted environment returns `404 Not Found`. | GET a unique nonexistent ID and assert `{"error":"not_found"}`; the delete lifecycle also checks the deleted ID. |
| R9 (stretch) | Repeating a request with the same idempotency key does not create a duplicate environment. | Repeat request and assert stable identity and single resulting environment. |

## Risk-based strategy

Prioritize lifecycle correctness and externally visible state because false success or orphaned partial resources are the highest-impact outcomes in provisioning. For deletion, cover state-appropriate acceptance/rejection, disappearance of the environment and resources, and retention of operation history; accidental deletion during provisioning and loss of audit history are key risks. Next cover invalid requests that might start unintended work, and bounded polling so a hung operation cannot stall CI. Cover representative inputs rather than every permutation. Keep the retry/idempotency case as stretch work after core behaviors pass.

## Core test cases

1. Happy path: submit a valid request, poll to success, then verify requested configuration and all expected resources.
2. Missing required size: verify a field-level validation error and no environment or operation.
3. Unsupported region: verify a field-level validation error and no environment or operation.
4. Non-string region: verify malformed value handling, a field-level validation error, and no environment or operation.
5. Malformed JSON: send an invalid JSON document; assert `400 invalid_json` and no environment or operation.
6. Injected `compute` failure: fail after network creation; verify terminal failure, stable reason, and that rollback removes all previously created resources.
7. Client timeout: use a deliberately slow operation and a short monotonic deadline; verify the test helper exits within its bound and reports the last observed state. A client deadline is not interpreted as proof that the service operation itself failed.
8. State consistency: verify success is asserted only after the environment is ready and its required resources are observable.
9. Delete a ready environment: assert `204`, then verify GET and filtered listing show it is absent while its completed operation remains available.
10. Delete a failed environment: inject the deterministic `compute` failure, wait for and verify environment state `FAILED`, assert DELETE returns `204`, GET returns `404`, and the failed operation history remains readable.
11. GET a nonexistent environment: assert `404 Not Found` and the not-found error payload.
12. Delete while provisioning: use a server fixture with a controlled longer provisioning delay, GET and assert the environment is `PROVISIONING` immediately before DELETE, assert `409 Conflict`, and verify provisioning continues to its normal successful state.
13. Stretch: repeat a request with the same idempotency key and verify there is no duplicate.

## Determinism and independence

Failure injection will be per request and target a named provisioning step, with a stable reason. Tests will not depend on randomness, global mutable switches, or timing alone to trigger failure. Each test will create uniquely named state and query it using returned identifiers. Polling uses a monotonic deadline and reports the last observed state on timeout. Assertions cover resulting records/resources, not only HTTP status codes. Fixtures will own API lifecycle and cleanup/isolation; tests should pass independently and in any order.

## Explicit exclusions

- Real cloud providers, cloud credentials, account setup, and billing.
- UI tests; the REST API is the selected real interface.
- Authentication, authorization, quotas, and multi-tenancy.
- Broad load, performance, chaos, and security testing.
- Multiple environment types, complex dependency graphs, and exhaustive validation permutations.
- Provider-specific behavior, production-grade rollback guarantees, and idempotency unless stretch time permits. The simulator's injected-failure cleanup only demonstrates deterministic rollback of its own records.

## CI gate

The CI workflow installs `requirements-dev.txt` and runs `python -m pytest -v`. A nonzero test result fails the workflow; the readiness gate is a passing workflow.
