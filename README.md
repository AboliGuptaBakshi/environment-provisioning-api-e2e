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

Setup and run instructions will be added with the API implementation. The intended test command is `python -m pytest` from the repository root.

## Repository map

- `app/`: REST API and simulated provisioning lifecycle.
- `tests/`: API-level end-to-end tests, fixtures, and bounded polling helper.
- `requirements.md`: scope, risk-based strategy, and requirement-to-test traceability.
- `.github/workflows/tests.yml`: CI pass/fail gate.
- `AI_LOG.md`: chronological record of AI-assisted work and decisions.

## What I would test next

After the assessment core: idempotent retries, concurrent requests, cancellation, recovery after process restart, and provider-specific integration behavior. These are outside the frozen scope.
