# Scope and test specification

## System under test

A generic Python REST API simulates provisioning one kind of environment and its resources. It provides a realistic asynchronous lifecycle without connecting to a cloud provider. Tests exercise the API and inspect persisted API state.

## Workflow contract

1. `POST /environments` accepts `{ "name": ..., "region": ..., "size": ... }` and returns HTTP 202 with environment and operation IDs.
2. Provisioning runs asynchronously and creates `network` followed by `compute` resources.
3. `GET /operations/{id}` exposes `PENDING`, `SUCCEEDED`, or `FAILED` and its error, if any.
4. `GET /environments/{id}` exposes environment configuration, lifecycle state, and created resources. Filtered `GET /environments?name=...` and `GET /operations?environment_name=...` support no-state validation checks.

The supported region is `us-east`; sizes are `small` and `medium`. Names must be 1–63 characters and contain only letters, digits, and hyphens. On failure, previously created resources are retained and returned with a failed environment state. For deterministic assessment testing, the simulator accepts optional `failure_injection: {"resource": "compute"}`; this fails at that named step after network creation. Failure injection is configurable and enabled by default for local/assessment use.

The API is a small Python standard-library HTTP server with SQLite persistence; tests use HTTP over localhost and Python's built-in `unittest` runner. This avoids external runtime dependencies while exercising the actual REST boundary.

## Requirements and traceability

| ID | Requirement | Planned verification |
|---|---|---|
| R1 | A valid request is accepted with environment and operation identifiers. | Submit via REST; assert response fields and retrieve the identified records. |
| R2 | Successful provisioning reaches a terminal success state within a bounded client deadline. | Poll operation using a monotonic deadline; assert terminal state. |
| R3 | A successful environment reflects requested configuration and has the complete expected resource set. | Read environment and resources after success; assert values and completeness. |
| R4 | Invalid or unsupported input is rejected with useful validation details and creates no environment or operation. | Submit representative invalid requests; assert field errors and query the environment list by unique name to confirm no state was created. |
| R5 | A deterministic injected resource failure produces a terminal failed operation and stable reason. | Request failure at a named provisioning step; assert operation state and reason. |
| R6 | State after partial failure follows the documented cleanup/retention policy. | Read environment and resources after injected failure; assert exact resulting state. |
| R7 (stretch) | Repeating a request with the same idempotency key does not create a duplicate environment. | Repeat request and assert stable identity and single resulting environment. |

## Risk-based strategy

Prioritize lifecycle correctness and externally visible state because false success or orphaned partial resources are the highest-impact outcomes in provisioning. Next cover invalid requests that might start unintended work, and bounded polling so a hung operation cannot stall CI. Cover representative inputs rather than every permutation. Keep the retry/idempotency case as stretch work after core behaviors pass.

## Core test cases

1. Happy path: submit a valid request, poll to success, then verify requested configuration and all expected resources.
2. Invalid input: omit a required value and supply an unsupported value; verify useful validation and no created environment or operation.
3. Injected partial failure: fail at a named resource step; verify terminal failure, stable reason, and the documented state of resources already created.
4. Client timeout: use a deliberately slow operation and a short monotonic deadline; verify the test helper exits within its bound and reports the last observed state. A client deadline is not interpreted as proof that the service operation itself failed.
5. State consistency: verify success is asserted only after the environment is ready and its required resources are observable.
6. Stretch: repeat a request with the same idempotency key and verify there is no duplicate.

## Determinism and independence

Failure injection will be per request and target a named provisioning step, with a stable reason. Tests will not depend on randomness, global mutable switches, or timing alone to trigger failure. Each test will create uniquely named state and query it using returned identifiers. Polling uses a monotonic deadline and reports the last observed state on timeout. Assertions cover resulting records/resources, not only HTTP status codes. Fixtures will own API lifecycle and cleanup/isolation; tests should pass independently and in any order.

## Explicit exclusions

- Real cloud providers, cloud credentials, account setup, and billing.
- UI tests; the REST API is the selected real interface.
- Authentication, authorization, quotas, and multi-tenancy.
- Broad load, performance, chaos, and security testing.
- Multiple environment types, complex dependency graphs, and exhaustive validation permutations.
- Provider-specific behavior, production-grade rollback guarantees, and idempotency unless stretch time permits.

## CI gate

The CI workflow runs `python -m unittest discover -s tests -v` using the standard library. A nonzero test result fails the workflow; the readiness gate is a passing workflow.
