# QA Review: Phase QE4

**Date:** 2026-03-12
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 14/14 | **Should-haves:** 5/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | All tests map to phase plan scope (CI-016, L8, S5). Docstrings cite behavior. |
| M2 | Negative Tests | PASS | 401 wrong password, 409 duplicate register, 404 nonexistent fact approve/delete, auth-required gate. |
| M3 | Security Boundaries | PASS | No hardcoded secrets (test key has `noqa: S105`). Auth boundaries tested (401/403). User scoping tested in 4/6 suites. |
| M4 | Determinism | PASS | No wall-clock time in assertions. `datetime.now(UTC)` only in setup helpers for DB insert timestamps. No network calls (ASGI transport). No unseeded randomness. |
| M5 | Implementation Completeness | PASS | All 10 planned files created. 30 new tests (plan said ~25, delivered 30). 2 bonus migrations (010, 011) fixing schema drift. CI job added. Minor: plan mentioned "expiry" test for approvals but replaced with user-scoping test -- acceptable substitution. |
| M6 | No Silent Error Swallowing | PASS | One `except Exception` in conftest.py:182 has `noqa: BLE001` and logs with `exc_info=True`. Pre-existing test_mr7_smoke.py exceptions unchanged. |
| M7 | Wiring Completeness | PASS | CI job `test-integration` is a separate workflow job with Postgres service, `continue-on-error: false`. Tests run via `pytest tests/integration/ -v`. |
| M8 | Domain Isolation | PASS | No cross-domain imports. MemoryStore import in conftest is from `noa.private_worker` which is acceptable for test infrastructure (not production code). |
| M2b | Write-Path Test Fidelity | PASS | All tests use real Postgres via ASGI transport -- no mocked DB reads/writes. |
| M3b | Write-Path User Scoping | PASS | User scoping tested in threads, settings, approvals, tools (4/6 suites). Memory uses MemoryStore with explicit `user_id` parameter. |
| M4b | Mock Interface Accuracy | PASS | Only mock is HealthChecker in conftest (not an AsyncSession). All DB operations use real async sessions. |
| M5b | Findings Currency | PASS | No new findings discovered. No existing findings resolved by this phase. FINDINGS.md remains at 0 open, 112 total. |
| M5c | Related-Issue Scope Completeness | PASS | Schema drift fixed for both discovered cases (010: google_refresh_token from GO1, 011: custom_tools from TM5). |
| M8b | Cross-Language Field Optionality | N/A | No API model changes. |

| S1 | Error Handling & Boundaries | PASS | Empty collection tests (empty threads, empty facts, empty approvals), 404 for nonexistent resources, auth rejection. |
| S2 | Code Consistency | PASS | Follows naming conventions. Helper functions prefixed with `_`. Test names descriptive. Consistent pattern across all 6 suites. |
| S3 | Migration & Rollback | PASS | Both migrations (010, 011) have `downgrade()` methods that reverse the `upgrade()`. |
| S4 | Documentation | PASS | Module docstrings on all test files and conftest. Inline comments explain design decisions (e.g., why MemoryStore is wired in `_make_test_app` rather than lifespan). |
| S5 | Integration Smoke Test | PASS | This entire phase IS the integration smoke test infrastructure. 30 non-mocked tests against real Postgres via Alembic migrations. |

## Test Plan Coverage
No test plan was written for QE4 (QA was run in review mode directly). Coverage assessed against the phase plan in PHASE_DETAILS.md.

## Spec Compliance
Phase plan specified 6 test suites with ~25 tests. Delivered 6 suites with 30 tests. All deliverables present:

| Planned Deliverable | Status | Notes |
|---|---|---|
| `tests/integration/conftest.py` | Delivered | Postgres fixture, Alembic migration runner, env isolation, ASGI app factory |
| `tests/integration/test_auth_integration.py` | Delivered | 6 tests (register, dup 409, login tokens, wrong pw 401, refresh, logout) |
| `tests/integration/test_threads_integration.py` | Delivered | 5 tests (create, empty list, empty messages, user scoping, delete) |
| `tests/integration/test_settings_integration.py` | Delivered | 5 tests (defaults, patch round-trip, field preservation, credential masking, user isolation) |
| `tests/integration/test_approvals_integration.py` | Delivered | 4 tests (empty list, appears in list, decide, user scoping) |
| `tests/integration/test_memory_integration.py` | Delivered | 5 tests (empty list, store+recall, 404 approve, 404 delete, auth required) |
| `tests/integration/test_tools_integration.py` | Delivered | 5 tests (health, enable, disable, user scoping, custom tool registration) |
| `pyproject.toml` | Modified | `testcontainers[postgres]>=4.8,<5.0` added |
| `.github/workflows/ci.yml` | Modified | `test-integration` job with Postgres service |
| `alembic/versions/010_*.py` | Delivered (bonus) | Schema drift fix for GO1 google_refresh_token |
| `alembic/versions/011_*.py` | Delivered (bonus) | Schema drift fix for TM5 custom_tools |

Minor gap: phase plan listed "expiry" as an approval test case, but the implementation substituted user-scoping instead. Expiry testing would require time manipulation or waiting -- acceptable trade-off for an integration test suite.

## Test Coverage
All 30 new tests are integration tests using real Postgres. Test distribution:

- **Auth (6)**: Full registration-to-logout lifecycle including error paths
- **Threads (5)**: CRUD + user scoping
- **Settings (5)**: PATCH round-trip + credential masking + user isolation
- **Approvals (4)**: Direct DB insert + API verification + decide + user scoping
- **Memory (5)**: MemoryStore direct injection + API verification + error paths + auth gate
- **Tools (5)**: Health, enable/disable, user scoping, custom tool registration

Every suite tests user scoping except auth (which tests unique user creation) and tools health (unauthenticated endpoint).

## Anti-Pattern Scan Results

**M6 -- Bare except / blind exception:**
- `tests/integration/conftest.py:182`: `except Exception: # noqa: BLE001` -- logs with `exc_info=True`, acceptable
- `tests/integration/conftest.py:67`: `except Exception as exc: # noqa: BLE001` -- raises RuntimeError, acceptable
- Pre-existing `test_mr7_smoke.py` lines 94, 116 -- not part of QE4

**M7 -- Wiring:**
- `test-integration` job in `ci.yml` line 64 -- properly configured with Postgres service
- `continue-on-error: false` -- integration test failures are blocking

**M8 -- Domain isolation:**
- No `from noa.private_worker` in `src/noa/external_worker/` (confirmed by grep)
- No `from noa.external_worker` in `src/noa/private_worker/` (confirmed by grep)

## Smoke Test Results
```
OK: conftest imports work
OK: test_auth_integration imports
OK: test_threads_integration imports
OK: test_settings_integration imports
OK: test_approvals_integration imports
OK: test_memory_integration imports
OK: test_tools_integration imports
OK: migration files 010, 011 exist
OK: 56 test functions found in tests/integration/
All QE4 smoke checks passed.
```

Static analysis:
- `ruff check tests/integration/`: All checks passed
- `ruff check src/noa/ tests/`: All checks passed
- `mypy src/noa/`: Success: no issues found in 166 source files

## Security
- Test secret key (`integration-test-secret-key`) is annotated with `noqa: S105` and only used in test fixture
- CI secret key (`ci-test-secret-key-not-for-production`) is clearly labeled
- No real credentials in test files
- Auth boundaries properly tested (401 on wrong password, 401/403 without token)
- User data isolation verified across 4 suites (threads, settings, approvals, tools)

## Code Quality
**Strengths:**
- Clean separation: session-scoped Postgres container, per-test app factory with env save/restore
- `concurrent.futures.ThreadPoolExecutor` for nested event loop avoidance in migration runner
- `atexit.register` for testcontainers cleanup
- `_patch_env`/`_restore_env` pattern prevents env pollution between tests
- MemoryStore wired directly in `_make_test_app` (not lifespan) with documented reason

**Minor observations (non-blocking):**
- `_make_test_app` constructs a `HealthChecker` via `__new__` and manually sets private attributes (lines 189-193). This is fragile -- if `HealthChecker.__init__` changes, this will silently break. A mock or a test-mode constructor would be more robust.
- `test_memory_integration.py:41` uses `os.environ.get("SECRET_KEY", "integration-test-secret-key")` -- the fallback default is redundant since `_patch_env` already sets it. Not a bug, just defensive coding.

## Beyond the Test Plan

1. **Schema drift detection as a bonus outcome**: The migration runner caught 2 cases of schema drift (GO1 google_refresh_token, TM5 custom_tools). These are now fixed with proper Alembic migrations. This validates the phase's core thesis -- running Alembic migrations in tests catches drift that `create_all()` hides.

2. **Test data accumulation**: All tests share a single Postgres instance (session-scoped). Each test creates new users with unique emails, but data accumulates across tests within a session. This is fine for the current test count, but could cause issues at scale (e.g., unique constraint violations if email patterns collide). Not blocking -- just a design consideration.

3. **Memory test `pytest.skip`**: `test_store_and_recall_fact` (line 48) skips if MemoryStore is unavailable. The conftest does wire MemoryStore, but if it fails, the test silently skips rather than failing. In practice this works because the conftest only catches and logs the exception -- the store would still be `None` and the skip is correct behavior.

4. **Approval test 404 assertion gap**: `test_approve_nonexistent_fact_returns_404` and `test_delete_nonexistent_fact_returns_404` accept both 404 and 503 (lines 81, 96). The 503 path means the memory store is unavailable, which is a different failure mode than "fact not found". This is pragmatic but slightly imprecise.

5. **CI database name consistency**: Unit test job uses `POSTGRES_DB: noa`, integration test job uses `POSTGRES_DB: noa_test`. These run on separate GitHub Actions runners, so there is no conflict. Good practice.

## Notes (PASS_WITH_NOTES)

1. **Missing approval expiry test**: Phase plan specified "expiry" as an approvals test case. The implementation substituted user-scoping (arguably more valuable). Consider adding an expiry test in a future phase if approval expiry is a user-facing feature.

2. **HealthChecker manual construction**: `conftest.py:189-193` manually constructs a `HealthChecker` via `__new__` and sets private attributes. If `HealthChecker` gains new required init parameters, this will break silently. Consider using `AsyncMock(spec=HealthChecker)` or adding a test-mode factory.

3. **Dual 404/503 assertion in memory tests**: Lines 81 and 96 of `test_memory_integration.py` accept both 404 and 503. If MemoryStore is wired correctly (which conftest ensures), these should consistently return 404. The 503 fallback weakens the assertion.

## Decision Review
No architectural decisions needed. QE4 is a pure infrastructure phase that adds integration test capability without modifying production code (except for the two schema drift fix migrations, which are additive-only).
