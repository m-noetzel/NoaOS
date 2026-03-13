# QA Test Plan: Phase QC3 — Error Handling & Observability

**Date:** 2026-03-07
**Phase:** QC3
**Author:** qa-review agent (test-plan mode)
**Findings addressed:** H4, H5, M8, M11, M13

---

## Context

This plan is produced **before** implementation. It defines behaviors that must be testable after the code is written. The `/write-tests` skill must derive concrete test cases directly from this plan.

QC3 has a deceptively wide surface area. The five findings span six source files and touch the repository layer, auth middleware, API endpoints, and a subprocess utility. Each fix interacts with the others — in particular, M11 (AuthUser dataclass) directly affects H5 (the error paths triggered when user_id extraction fails) and M8 (cost endpoint error handling).

---

## Critical Observations from Reading the Code

Before listing tests, here are adversarial observations that tests must address:

1. **H4 — The `commit()` violation is real.** `SettingsRepository.upsert()` calls `flush()` + `commit()` on the injected session. Removing `commit()` means the *caller* must commit. The settings endpoint (`PUT /api/v1/settings`) currently does not call `session.commit()` — it relies on the repository to do it. After the fix, the endpoint or a session-scope dependency must commit or the change will silently rollback.

2. **M8 — Both cost endpoints are affected.** `cost_summary` (line 72) and `cost_records` (line 122) both catch `Exception` and return `success_envelope(data=[], ...)` — HTTP 200. Both must be fixed to return HTTP 500 (or equivalent error envelope with non-2xx) on DB errors.

3. **M11 — Three incompatible extraction patterns today.** `chat.py:64` uses `user.get("user_id", user.get("sub", ""))` — falls back to `""` if both keys absent, then `uuid.UUID("")` raises `ValueError`. `settings.py:48` uses `user["sub"]` — raises `KeyError` if absent (unhandled, becomes 500). `cost.py:38-44` duplicates `chat.py` pattern but also has `uuid.UUID(user_id)` that fails on empty string. A unified `AuthUser` object must prevent these failure modes.

4. **M13 — Two separate issues in `backup.py:run_backup_script()`.** First: `check=False` silently swallows non-zero exit codes. Second: `merged_env = {**os.environ, **(env or {})}` passes the **entire current process environment** (which may include `DATABASE_URL`, `SECRET_KEY`, `ANTHROPIC_API_KEY`, etc.) to a subprocess. Both must be fixed independently.

5. **H5 — app.py lifespan `except Exception: pass` is explicitly exempted** by FINDINGS.md as a pre-existing design decision ("Allow running without DB for health-only testing"). This exception must NOT be removed without first having a DB-free testing alternative. Tests must verify that the exempted block still logs at WARNING level, not silently drops.

---

## Test Suite Structure

Tests go in `tests/unit/test_qc3_error_handling.py`.

One integration-class test must exist that calls real functions without mocking all internals (satisfies M2/S5 integration requirement).

---

## Test Group 1: H4 — Repository Transaction Boundary

**Spec ref:** ARCH_INVARIANTS.md L1 (layering rules — repositories don't own transactions), FINDINGS.md H4

### 1.1 Repository does not call `commit()` on the session

```
TestSettingsRepositoryTransactionBoundary.test_upsert_does_not_commit
```

- Create a `MagicMock()` AsyncSession (not AsyncMock — we need to assert method calls)
- Call `SettingsRepository.upsert(user_id, {...})`
- Assert `session.commit.assert_not_called()` — commit must never be invoked
- Assert `session.flush.call_count >= 0` — flush is acceptable, commit is not

**Why this matters:** If commit remains in the repo, any multi-step operation (e.g., create user + upsert settings in one transaction) will prematurely commit the partial state.

### 1.2 Repository still calls `flush()` to make the row visible

```
TestSettingsRepositoryTransactionBoundary.test_upsert_calls_flush
```

- Same mock setup as 1.1
- Assert `session.flush.assert_called_once()` — flush must still happen so the row is visible in the same transaction before the caller commits

### 1.3 Caller (settings endpoint) commits after upsert

```
TestSettingsRepositoryTransactionBoundary.test_settings_endpoint_commits_after_upsert
```

- This is an integration test: use an in-memory SQLite + async session OR a mock session
- Call `update_settings` handler directly (or via TestClient) with a valid JWT
- Assert the row is actually persisted (SELECT after the call finds it)
- **This test verifies the fix is end-to-end, not just that commit was removed from the repo**

**Failure mode to detect:** After removing commit from the repo, if no one else calls commit, the update silently disappears. This is the most likely regression from the H4 fix.

### 1.4 Multiple upserts in the same transaction do not partially commit

```
TestSettingsRepositoryTransactionBoundary.test_two_upserts_atomic_rollback
```

- Begin a transaction
- Call `upsert()` twice
- Roll back the transaction
- Assert neither upsert is visible in the DB
- **Purpose:** Proves atomicity is preserved after commit is removed

---

## Test Group 2: H5 — Exception Handling Quality

**Spec ref:** ARCH_INVARIANTS.md L9, FINDINGS.md H5

### 2.1 cost.py error path logs with exc_info, not silently

```
TestExceptionHandlingQuality.test_cost_summary_db_error_logs_warning
```

- Mock the session factory to raise `sqlalchemy.exc.OperationalError`
- Call the cost summary endpoint
- Assert `logger.warning` was called with `exc_info=True` (existing behavior in current code)
- Assert the response is NOT HTTP 200 (new requirement — see M8 tests below)

### 2.2 chat.py `_make_run_service` inner except logs, not silently drops

```
TestExceptionHandlingQuality.test_make_run_service_db_error_logs
```

- The inner `except Exception: pass` at `chat.py:159` (S110) is pre-existing. After QC3, it must at minimum log at DEBUG level.
- Mock `factory()` to raise `Exception("connection refused")`
- Assert a log entry was emitted (capture with `caplog` fixture)
- Assert the function still returns a `_NoOpRunService` (graceful degradation)

### 2.3 health.py pool stats except logs at DEBUG not silently drops

```
TestExceptionHandlingQuality.test_metrics_pool_stats_error_does_not_swallow_silently
```

- The `except Exception` at `health.py:80` catches pool stat failures. It logs `logger.debug(...)` — this is acceptable. Test must verify the log is emitted.
- Mock `engine.pool.size()` to raise `AttributeError`
- Assert `caplog` contains a debug-level entry
- Assert metrics endpoint still returns HTTP 200 (pool stats are optional)

### 2.4 app.py lifespan DB-skip except STILL logs at WARNING

```
TestExceptionHandlingQuality.test_lifespan_db_skip_emits_warning
```

- The `except Exception: pass` at `app.py:151` (noqa S110) is the single exempted case
- After QC3, this must be replaced with `logger.warning(...)` even though we keep the `pass`
- Test: patch `create_async_engine_from_config` to raise, capture logs, assert WARNING was emitted

### 2.5 Negative test: no exception handler returns HTTP 200 on DB error for non-optional endpoints

```
TestExceptionHandlingQuality.test_no_silent_200_on_db_error_cost_summary
TestExceptionHandlingQuality.test_no_silent_200_on_db_error_cost_records
```

- Covered in Group 3 (M8) — cross-reference here

---

## Test Group 3: M8 — Cost Endpoint HTTP 500 on Database Error

**Spec ref:** ARCH_INVARIANTS.md L9 rule 3 ("An `except` block must never return HTTP 200"), FINDINGS.md M8

### 3.1 Cost summary returns HTTP 500 when DB raises OperationalError

```
TestCostEndpointErrorCodes.test_cost_summary_returns_500_on_db_error
```

- Use FastAPI `TestClient` with app where session factory raises `sqlalchemy.exc.OperationalError`
- Send `GET /api/v1/cost/summary` with a valid JWT
- Assert response status code is **500** (not 200)
- Assert response body has `"ok": false` (standard error envelope)
- Assert response body does NOT have `"data": []` (that's the masking pattern)

### 3.2 Cost records returns HTTP 500 when DB raises OperationalError

```
TestCostEndpointErrorCodes.test_cost_records_returns_500_on_db_error
```

- Same pattern as 3.1 for `GET /api/v1/cost/records`
- Assert 500 not 200
- Assert error envelope present

### 3.3 Cost summary still returns HTTP 200 with empty list when factory is None (no DB configured)

```
TestCostEndpointErrorCodes.test_cost_summary_returns_200_when_no_factory
```

- The "no DB configured" path (`factory is None`) must stay as HTTP 200 with `data=[]`
- This is intentional graceful degradation, distinct from a DB error
- Set `_get_session_factory` to return `None`
- Assert response is 200, `data` is empty list

**This distinction is critical:** `factory is None` = no DB wired (dev mode) = return empty 200. `factory() raises` = DB wired but unreachable = return 500.

### 3.4 Cost records returns HTTP 200 with empty list when factory is None

```
TestCostEndpointErrorCodes.test_cost_records_returns_200_when_no_factory
```

- Same pattern as 3.3 for `/cost/records`

### 3.5 Error response includes trace_id for correlation

```
TestCostEndpointErrorCodes.test_cost_error_response_includes_trace_id
```

- On DB error, the 500 response body must include `trace_id` in the meta or error fields
- Assert `response.json()["meta"]["trace_id"]` is a non-empty string

---

## Test Group 4: M11 — Unified AuthUser Extraction

**Spec ref:** SPEC.md §5.1 (authentication), FINDINGS.md M11

### 4.1 `require_auth` returns an `AuthUser` typed object (not raw dict)

```
TestAuthUserExtraction.test_require_auth_returns_authuser
```

- Call `require_auth` with a mock JWT containing `sub` = valid UUID string
- Assert the returned object is an `AuthUser` instance (or a TypedDict with `user_id` field)
- Assert `result.user_id` is a `uuid.UUID` (not a string)

### 4.2 `AuthUser.user_id` is populated from `sub` claim

```
TestAuthUserExtraction.test_authuser_extracts_from_sub_claim
```

- Mock JWT payload: `{"type": "access", "sub": "550e8400-e29b-41d4-a716-446655440000"}`
- Assert `auth_user.user_id == uuid.UUID("550e8400-e29b-41d4-a716-446655440000")`

### 4.3 JWT missing `sub` raises HTTP 401, not 500

```
TestAuthUserExtraction.test_jwt_missing_sub_raises_401_not_500
```

- Create a token with a payload that has `type: access` but no `sub` field
- Call the endpoint (e.g., `GET /api/v1/settings`)
- Assert HTTP 401 is returned, not 500
- **Before the fix:** `settings.py` would raise `KeyError` on `user["sub"]` → unhandled → 500

### 4.4 JWT with non-UUID `sub` raises HTTP 422, not 500

```
TestAuthUserExtraction.test_jwt_sub_non_uuid_raises_422_not_500
```

- JWT payload: `{"type": "access", "sub": "not-a-uuid"}`
- Assert response is 422 or 400 (validation error), not 500
- **Before the fix:** `uuid.UUID("not-a-uuid")` raises `ValueError` → unhandled → 500

### 4.5 chat.py uses AuthUser's `user_id` directly (no `.get()` fallback chains)

```
TestAuthUserExtraction.test_chat_endpoint_uses_authuser_user_id
```

- Inspect `chat.py` source — assert `user.get("user_id", user.get("sub", ""))` pattern is NOT present
- OR: call chat endpoint with a JWT that has `sub` but no `user_id` key, assert it works correctly
- This verifies the old fallback chain is gone

### 4.6 cost.py uses AuthUser's `user_id` directly (no duplicate extraction)

```
TestAuthUserExtraction.test_cost_endpoint_uses_authuser_user_id
```

- Same as 4.5 for cost endpoints
- Assert `user.get("user_id", user.get("sub", ""))` is gone from `cost.py`

### 4.7 settings.py uses AuthUser's `user_id` (was KeyError-prone `user["sub"]`)

```
TestAuthUserExtraction.test_settings_endpoint_uses_authuser_user_id
```

- Same as 4.5 for settings endpoint
- The old `user["sub"]` direct access must be gone

### 4.8 Negative: empty `user_id` string no longer reaches UUID constructor

```
TestAuthUserExtraction.test_empty_user_id_never_reaches_uuid_constructor
```

- With the old code: `user.get("user_id", user.get("sub", ""))` could produce `""`, then `uuid.UUID("")` raises `ValueError`
- After the fix, `AuthUser` construction in `require_auth` must fail fast with 401, before any endpoint sees a bad user_id
- Mock JWT with `sub: ""` → assert 401 is returned at the middleware layer

---

## Test Group 5: M13 — Backup Script Error Propagation and Env Safety

**Spec ref:** SPEC.md §10.5, FINDINGS.md M13

### 5.1 `run_backup_script` raises on non-zero exit code (check=True behavior)

```
TestBackupScriptSafety.test_run_backup_raises_on_nonzero_exit
```

- Create a temp script that exits 1
- Assert `run_backup_script()` raises `subprocess.CalledProcessError`
- **Before the fix:** it returns a `CompletedProcess` with `returncode=1` and no error is raised
- **Critical:** This test will FAIL before implementation (red phase requirement)

### 5.2 The function signature allows callers to opt into check=False for monitoring uses

```
TestBackupScriptSafety.test_run_backup_allows_check_false_opt_out
```

- If the fix adds a `check: bool = True` parameter, verify that `check=False` still returns `CompletedProcess` without raising
- This preserves backward compatibility for callers who want to inspect the result

### 5.3 Whitelist-only env vars are passed, not full `os.environ`

```
TestBackupScriptSafety.test_run_backup_does_not_leak_os_environ
```

- Set a dangerous env var in the process: `os.environ["SECRET_KEY"] = "should-not-leak"`
- Create a script that echoes `$SECRET_KEY`
- Call `run_backup_script(script, env={"BACKUP_PASSPHRASE": "test"})`
- Assert `SECRET_KEY` does NOT appear in stdout
- **Before the fix:** `{**os.environ, ...}` passes `SECRET_KEY` through to the subprocess

### 5.4 Caller-provided env vars ARE passed through

```
TestBackupScriptSafety.test_run_backup_passes_caller_env_vars
```

- Call with `env={"BACKUP_PASSPHRASE": "secret", "PGHOST": "db"}` and a script that echoes them
- Assert both appear in output
- This verifies the whitelist approach still works for legitimate backup vars

### 5.5 Required environment variables for backup are documented in function signature

```
TestBackupScriptSafety.test_run_backup_has_env_parameter
```

- Inspect the function signature — `env` parameter must exist and be the only way to pass secrets to the subprocess
- No `os.environ` passthrough should remain

### 5.6 CalledProcessError from failed backup includes returncode and stderr

```
TestBackupScriptSafety.test_backup_error_includes_diagnostic_info
```

- Create a script that exits 1 with stderr `"pg_dump: could not connect"`
- Assert the raised `CalledProcessError` has `returncode == 1`
- Assert `exc.stderr` contains `"pg_dump"` (the actual error message)

### 5.7 Timeout still works (existing behavior must be preserved)

```
TestBackupScriptSafety.test_run_backup_timeout_raises_timeout_expired
```

- Create a script that `sleep 10`
- Call with `timeout=1`
- Assert `subprocess.TimeoutExpired` is raised
- **Existing test covers this — verify it still passes after the check=True change**

---

## Test Group 6: Integration Smoke Test (S5 requirement)

**Spec ref:** QA_CHECKLIST.md S5

### 6.1 Import smoke test — all modified modules load without error

```
TestQC3Imports.test_all_modified_modules_import
```

- Import each affected module in sequence:
  - `from noa.settings.repository import SettingsRepository`
  - `from noa.api.v1.cost import router as cost_router`
  - `from noa.api.v1.chat import router as chat_router`
  - `from noa.api.v1.settings import router as settings_router`
  - `from noa.auth.middleware import require_auth, AuthUser`
  - `from noa.maintenance.backup import run_backup_script`
- Assert each import succeeds (no ImportError)

### 6.2 Settings upsert round-trip — remove commit from repo, commit via caller

```
TestQC3Integration.test_settings_upsert_persists_via_caller_commit
```

- Use in-memory SQLite with async adapter (or real Postgres if available via conftest)
- Create a session, create a `SettingsRepository`, call `upsert()`
- Commit the session *outside* the repository
- Open a new session and assert the row exists
- **This is the non-mocked integration test required by S5 and QA_CHECKLIST.md S5**

### 6.3 AuthUser flows through chat endpoint to usage recording

```
TestQC3Integration.test_authuser_propagates_to_usage_recording
```

- Create a mock runner that yields a `result_ready` event with `llm_usage`
- Call the chat endpoint with a JWT having `sub = <valid UUID>`
- Assert `_record_usage` is called with the correct `user_id` (UUID string, not raw dict)
- This verifies M11 fix connects all the way through the chat pipeline

---

## Edge Cases and Security Scenarios

### EC-1: `sub` claim is a valid UUID but not in the database

- Test that the application doesn't crash — 200 with empty data is acceptable
- The user_id parsing should succeed even if there are no DB rows for that user

### EC-2: Session factory raises immediately on instantiation (not on query)

- Distinct from the "DB query fails" case tested in 3.1
- `factory()` itself raises `Exception` (e.g., connection pool exhausted before context manager entry)
- Both cost endpoints must return 500

### EC-3: `run_backup_script` called with a script that has no read permission

- Should raise `PermissionError` or `subprocess.CalledProcessError`
- Must NOT silently succeed

### EC-4: JWT `sub` contains a UUID with uppercase letters

- `UUID("550E8400-E29B-41D4-A716-446655440000")` is valid Python — assert AuthUser handles it
- Case-insensitive UUID parsing

### EC-5: Concurrent upserts to the same user_id

- Without `commit()` in the repo, the session-level transaction prevents conflicts
- Test that two concurrent `upsert()` calls in the same session don't produce duplicate rows (SQLite single-writer serializes this naturally)

---

## Anti-Pattern Contracts Tests Must Enforce

These must be checked by tests (not just static analysis), because ruff noqa suppressions exist:

1. `cost.py` `except Exception` blocks must NOT return `success_envelope(...)` — they must return an error response (HTTPException or error envelope with 5xx status)
2. `settings/repository.py` must NOT call `session.commit()` — verified by mock call assertion
3. `backup.py:run_backup_script` must NOT contain `{**os.environ, ...}` — verified by behavioral test (5.3 above)
4. All endpoints must receive an `AuthUser` object (or equivalent typed struct) rather than extracting user_id from a raw `dict` with fallback chains

---

## What Must NOT Be Tested (Scope Boundary)

- `health.py` `except Exception` blocks (pool stats, DB check): these are legitimately catch-all for optional monitoring data. They log (or will log after QC3) and degrade gracefully — not a silent swallow. Tests must verify they log, not that they disappear.
- `app.py` LLM pipeline wiring `except Exception: noqa BLE001` blocks: pre-existing design decision, startup graceful degradation. QC3 must ensure they at minimum log at WARNING. Tests verify logging, not removal.
- The QC3 scope does NOT include fixing `M12` (mixed sync/async service layer) or `M3` (retention never purging).

---

## Files Where Tests Must Go

```
tests/unit/test_qc3_error_handling.py
```

All tests in this file must carry:
```python
"""Tests for Phase QC3: Error Handling & Observability.

Covers: H4 (repository transaction boundaries), H5 (exception handling quality),
M8 (cost endpoint error codes), M11 (unified AuthUser extraction),
M13 (backup script error propagation and env safety).

Spec refs: ARCH_INVARIANTS.md L9, L1; FINDINGS.md H4, H5, M8, M11, M13
Phase plan: MASTER_PLAN.md Phase QC3
"""
```

Each test class must reference its finding ID in the docstring.

---

## Implementation Checklist for `/write-code`

These are the behaviors that must be implemented, derived from the tests above:

| Finding | Required Change | Verified By |
|---------|----------------|-------------|
| H4 | Remove `commit()` from `SettingsRepository.upsert()` | Tests 1.1, 1.2, 1.3, 1.4 |
| H4 | Add `commit()` call in settings endpoint or session dependency | Test 1.3 |
| H5/app.py | Add `logger.warning()` to the bare `except Exception: pass` at line 151 | Test 2.4 |
| H5/chat.py | `_make_run_service` inner except must log at DEBUG, not be silent | Test 2.2 |
| H5/health.py | Pool stats except already logs — verify it survives refactor | Test 2.3 |
| M8 | `cost_summary` must raise `HTTPException(500)` on DB error | Tests 3.1, 3.5 |
| M8 | `cost_records` must raise `HTTPException(500)` on DB error | Tests 3.2, 3.5 |
| M8 | `factory is None` path stays as HTTP 200 empty | Tests 3.3, 3.4 |
| M11 | Create `AuthUser` dataclass in `noa.auth.middleware` with `user_id: uuid.UUID` | Tests 4.1, 4.2 |
| M11 | `require_auth` returns `AuthUser` (parsed, typed) not raw `dict` | Tests 4.1–4.4 |
| M11 | `chat.py`, `cost.py`, `settings.py` updated to use `AuthUser.user_id` | Tests 4.5–4.7 |
| M11 | Empty/missing `sub` → 401 at middleware level, not 500 at endpoint | Tests 4.3, 4.8 |
| M13 | `run_backup_script` defaults to `check=True` | Tests 5.1, 5.6 |
| M13 | `run_backup_script` passes only caller-provided env, not `os.environ` | Tests 5.3, 5.4 |

---

## Risk Assessment

**Highest regression risk:** M11 — changing `require_auth` return type from `dict` to `AuthUser` will break every endpoint that uses `user: dict[str, Any] = Depends(require_auth)`. The type annotation change is mechanical but affects `chat.py`, `cost.py`, `settings.py`, `audit.py`, `tasks.py`, `threads.py`, `memory.py`, `usage.py`, `runs.py`, `approvals.py`, `artifacts.py`, and `tools.py`. If only the QC3 files are updated and others are left with `dict` expectations, mypy will catch it but runtime may not if dict-compatible attribute access is used.

**Second highest risk:** H4 — after removing `commit()` from the repository, the settings endpoint must explicitly commit. If the DI session (`get_db_session`) is not configured to auto-commit on scope exit, settings changes will silently disappear. Test 1.3 is the only guard against this.

**Third risk:** M13 — changing `check=False` to `check=True` will make existing callers in `test_backup.py` that test for `returncode != 0` raise instead. These tests will need to be updated to catch `CalledProcessError`.
