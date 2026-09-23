# Environment Provisioning API

A small, generic REST API simulator for demonstrating risk-based end-to-end testing of an environment provisioning workflow. It does not provision real cloud resources.

## Frozen assessment scope

- Interface: REST API.
- Implementation: Python.
- Workflow: submit one environment request, receive environment and operation identifiers, poll the asynchronous operation, then inspect resulting environment and resources.
- Core behaviors: valid provisioning, representative request validation, deterministic injected partial failure, bounded client polling, and resulting-state validation.
- Failure policy: the simulator will document and expose what happens to resources created before a failure; tests will assert that policy.
- Test gate: automated end-to-end tests must pass locally and in CI.

Stretch only if the core is complete: idempotency-key behavior and additional edge cases. The detailed requirements and exclusions are in [requirements.md](requirements.md).

## Assessment target and test strategy

This generic environment-provisioning API was chosen because it provides a realistic asynchronous lifecycle—request acceptance, operation polling, resource creation, and deletion—through a real REST interface without requiring cloud credentials, accounts, or paid infrastructure. Its simulated provisioning steps also make important outcomes, including injected failure and rollback, repeatable in a small assessment environment.

The test strategy prioritizes lifecycle correctness and externally visible resulting state. It checks that invalid requests start no work, injected failures roll back previously created resources, and client polling has a bounded deadline. Tests verify persisted environments, resources, and operation history rather than relying on response codes alone. Each test uses isolated state and deterministic failure injection to stay independent and repeatable. Broad load and security testing, real cloud-provider behavior, and production-grade rollback guarantees are explicit exclusions; see [requirements.md](requirements.md) for the full scope.

## Local setup

Requires Python 3.11 or newer. Install the test dependency with:

```sh
python3 -m pip install -r requirements-dev.txt
```

```sh
python3 -m app
```

The API listens at `http://127.0.0.1:8080` by default. An injected `compute` failure rolls back resources already created for that environment and leaves the environment and operation failed. Delete a `READY` or `FAILED` environment with `DELETE /environments/{id}`; it returns `204`, removes the environment and its resources, and preserves completed operation history. The automated delete lifecycle tests cover both `READY` and `FAILED` environments. A delete during `PROVISIONING` returns `409`; GET for a deleted or unknown environment returns `404`. Run the end-to-end suite from the repository root in another terminal:

```sh
python3 -m pytest -v
```

Set `PROVISIONING_DB` to choose a SQLite file and `PROVISIONING_STEP_DELAY_SECONDS` to adjust the simulated delay per resource step. The assessment simulator allows per-request deterministic failure injection using `failure_injection: {"resource": "compute"}`; see [requirements.md](requirements.md) for the resulting-state policy.

## CI gate

GitHub Actions runs the pytest suite on pushes to `main` and on pull requests. The workflow fails when pytest returns a non-zero exit status; a passing workflow is the readiness/release gate for this assessment.

## Repository map

- `app/`: REST API and simulated provisioning lifecycle.
- `tests/`: API-level pytest scenarios, `conftest.py` fixtures, and bounded polling helper.
- `requirements.md`: scope, risk-based strategy, and requirement-to-test traceability.
- `.github/workflows/tests.yml`: CI pass/fail gate.
- `AI_LOG.md`: chronological record of AI-assisted work and decisions.

## What I would test next

After the assessment core: idempotent retries, concurrent requests, cancellation, recovery after process restart, and provider-specific integration behavior. These are outside the frozen scope.
