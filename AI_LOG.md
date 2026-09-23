# AI interaction log

Chronological record of AI-assisted work for this assessment. Entries capture the user request and the resulting decisions/actions; append to this file as work continues.

## 2026-09-23 — Scope planning

**User request:** Build an automated end-to-end test suite for a platform engineering assessment, with a concise requirements-traced specification, real-interface automation, happy and failure paths (invalid input, partial failure, timeout, post-workflow state), injected failure, CI gate, setup instructions, risk-based strategy, edge cases, exclusions, deterministic independent tests, fixtures/helpers, outcome assertions, next-test ideas, meaningful Git history, and a complete AI interaction log. Prefer locally available Python or TypeScript. Before coding, assess a generic environment provisioning REST API and propose workflow, risks, requirements, tests, exclusions, deterministic injection/state checks, repository layout, and commit milestones.

**Assistant decision:** Recommended a deliberately small REST API simulator with an asynchronous operation lifecycle; Python as the likely quickest route; success, invalid input, named-step injected partial failure, bounded client polling, and resulting-state checks as core. Idempotency was designated stretch. Real cloud integration and broad production concerns were excluded. Proposed a traceable spec, independent API tests, CI gate, and incremental commits.

## 2026-09-23 — Frozen scope and initial structure

**User request:** Freeze the proposed scope, create the initial project structure, then commit it.

**Assistant action:** Workspace was empty and not a Git repository. Selected Python, created `app/`, `tests/`, and `.github/workflows/`, and added this scope/traceability scaffold before initializing Git and making the first milestone commit.

## 2026-09-23 — Minimal API and end-to-end suite

**User request:** Implement the minimal REST API in the frozen scope, do not add stretch features, run the suite, and report the result.

**Assistant implementation:** Added a standard-library HTTP server with SQLite-backed environments, operations, and resources. The API supports asynchronous provisioning, `network` then `compute`, validation, operation and environment reads, filtered environment listing for no-state checks, and per-request failure at `compute`. The documented partial-failure policy retains the already-created network and marks both operation and environment failed. Added real localhost HTTP tests using `unittest`, a monotonic bounded poll helper, local setup instructions, and a GitHub Actions pass/fail workflow. No idempotency feature was added.

**Verification:** Initial sandbox test attempt could not bind an ephemeral localhost port. Reran with the required local-network permission. First run exposed an empty-query parsing issue in the no-state assertion; fixed query parsing and ensured SQLite connections are closed. Final command `python3 -m unittest discover -s tests -v` passed all 4 tests: happy path and resulting state, invalid input/no environment state (including missing and malformed values), injected partial failure/state retention, and client timeout followed by eventual successful completion.

## 2026-09-23 — Separate invalid-input scenarios

**User request:** Replace grouped invalid-input coverage with separate test methods, preserve scope, update traceability if needed, run the full suite, and make one commit.

**Assistant change:** Replaced the parameterized loop/subtests with distinct tests for missing `size`, unsupported `region`, and non-string `region`. Kept common HTTP/no-state assertions in a helper. Updated R4 traceability and the core test-case list. No API functionality changed.

**Verification:** `python3 -m unittest discover -s tests -v` passed all 6 tests, including the three separate invalid-input cases.

## 2026-09-23 — Convert suite to pytest

**User request:** Refactor the six scenarios to pytest, add `conftest.py` fixtures for server lifecycle/base URL/reusable setup, retain request and polling utilities in `helpers.py`, update setup/traceability/CI, run the full suite, and make one commit without expanding scope.

**Assistant change:** Replaced the `unittest.TestCase` class with six pytest test functions. Added per-test server, base URL, and environment-factory fixtures. Kept HTTP request and bounded polling helpers in `tests/helpers.py`. Added `requirements-dev.txt`, updated README and requirement/test runner references, and changed CI to install pytest and run `python -m pytest -v`. No scenarios or API features were added.

**Verification:** Pytest was not installed initially. The first package install attempt was blocked by sandbox network restrictions; installed the declared dependency with network permission. `python3 -m pytest -v` passed all 6 scenarios in 3.63 seconds.

## 2026-09-23 — Deterministic rollback on injected compute failure

**User request:** Implement the proposed behavior for an injected `compute` failure: deterministic rollback of previously created resources; update the test, requirements/traceability, and relevant documentation; run the full suite and make one commit without adding other functionality.

**Assistant change:** In the existing injected-failure transaction, delete resources for that environment before marking its environment and operation failed. Updated the failure test to assert an empty resource list, and documented the simulator's rollback policy and its boundary from production-grade provider rollback. No API endpoints or failure modes were added.

**Verification:** `python3 -m pytest -v` passed all 6 tests, including the rollback assertion.
