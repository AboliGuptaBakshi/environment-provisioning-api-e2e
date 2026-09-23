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

## Local setup

Requires Python 3.11 or newer. Install the test dependency with:

```sh
python3 -m pip install -r requirements-dev.txt
```

```sh
python3 -m app
```

The API listens at `http://127.0.0.1:8080` by default. Run the end-to-end suite from the repository root in another terminal:

```sh
python3 -m pytest -v
```

Set `PROVISIONING_DB` to choose a SQLite file and `PROVISIONING_STEP_DELAY_SECONDS` to adjust the simulated delay per resource step. The assessment simulator allows per-request deterministic failure injection using `failure_injection: {"resource": "compute"}`; see [requirements.md](requirements.md) for the resulting-state policy.

## Repository map

- `app/`: REST API and simulated provisioning lifecycle.
- `tests/`: API-level pytest scenarios, `conftest.py` fixtures, and bounded polling helper.
- `requirements.md`: scope, risk-based strategy, and requirement-to-test traceability.
- `.github/workflows/tests.yml`: CI pass/fail gate.
- `AI_LOG.md`: chronological record of AI-assisted work and decisions.

## What I would test next

After the assessment core: idempotent retries, concurrent requests, cancellation, recovery after process restart, and provider-specific integration behavior. These are outside the frozen scope.
