# QA Review: Hardening Phase (HD)

**Date:** 2026-03-08
**Verdict:** FAIL
**Reviewer:** qa-review agent (review mode)
**Commit:** 9c5a873 (hardening: resolve 5 partially-resolved findings)

## Checklist Score
**Must-haves:** 4/8 | **Should-haves:** 2/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | FAIL | Zero new tests added for 5 findings |
| M2 | Negative Tests | FAIL | No negative/error-path tests |
| M3 | Security Boundaries | FAIL | Google tokens stored plaintext despite SPEC requiring encryption; replay endpoint exposes any user's events |
| M4 | Determinism | PASS | No time-dependent test assertions |
| M5 | Implementation Completeness | FAIL | Checkpointer wired but never called; GovernanceWrapper.execute user_id not called from anywhere |
| M6 | No Silent Error Swallowing | PASS | `except Exception: # noqa: BLE001` in registration.py:115 has logging |
| M7 | Wiring Completeness | PASS | set_app() called, PostgresCheckpointer wired, replay endpoint reachable |
| M8 | Domain Isolation | PASS | No cross-domain imports |
| S1 | Error Handling & Boundaries | OPEN | Fire-and-forget task in _persist_google_tokens has no error handling |
| S2 | Code Consistency | OPEN | ruff check has 2 lint errors in changed files (I001, F401) |
| S3 | Migration & Rollback | PASS | Migration 007 has downgrade() |
| S4 | Documentation | PASS | Docstrings present with spec refs |
| S5 | Integration Smoke Test | OPEN | Imports work; no behavioral integration test |

## Test Plan Coverage
No test plan was created for this hardening phase (it bypassed the pipeline). Zero new tests were added. Three existing QC8 tests now FAIL due to breaking changes introduced by this commit.

## Spec Compliance

### H8 — Rate Limiting (user_id wiring)
- **RateLimiter.check()**: Correctly accepts `user_id` kwarg and keys by `(user_id, action)`. PASS.
- **GovernanceWrapper.execute()**: Correctly accepts `user_id` kwarg and passes to `RateLimiter.check()`. PASS.
- **Actual callers**: GovernanceWrapper is NOT imported or called from any other module in `src/noa/` except itself and its test file. The wrapper is an orphan — no production code path invokes `execute(user_id=...)`. **NOT WIRED in production.**

### M5 — SSE Replay
- **replay_run_events()**: Queries `RunEvent` table, filters by `run_id`, orders by timestamp, skips `after_event_id`. Semantics are correct. PASS (functional logic).
- **Auth bypass**: Endpoint requires `require_auth` but does NOT filter by user. Any authenticated user can read any run's events by guessing `run_id`. **SECURITY ISSUE.**
- **Regression**: Adding `db=Depends(get_db_session)` broke 2 existing QC8 tests that call the function directly without a DB session.

### M10 — Google Token Persistence
- **GoogleCredential model**: Created with `access_token_enc` and `refresh_token_enc` columns.
- **SPEC violation**: SPEC.md line 686 says "Google OAuth2 refresh token: Postgres (encrypted column)". The `_enc` suffix and docstring claim encryption, but **tokens are stored as plaintext**. No encryption/decryption anywhere.
- **Fire-and-forget**: `loop.create_task(_save())` creates an unawaited task. Errors are silenced. The log message "persisted (env + DB)" fires BEFORE the task completes.
- **user_id hardcoded**: `uuid.UUID(int=0)` — not the actual user's ID.
- **Upsert fragility**: `select(GoogleCredential).limit(1)` without user filter — wrong row updated if >1 users exist.

### A1 — app.state-backed DI
- **set_app()**: Called in `create_app()` at line 278. PASS.
- **Dual storage**: Each setter writes to both module global and `app.state`. Each getter tries `app.state` first, falls back to global. Correct pattern. PASS.
- **reset_all()**: Clears both globals and `_app_instance`. PASS.

### A4 — PostgresCheckpointer
- **PostgresCheckpointer**: Has `save()` and `load()` with upsert semantics. Correct implementation. PASS (class itself).
- **Wired at startup**: `app.py:132-141` creates `PostgresCheckpointer` and passes to `OrchestratorRunner`. PASS.
- **Never called**: `runner.py` stores `self._checkpointer` on line 33 but **never references it again**. No `save()` or `load()` call anywhere in `run()`. The checkpointer is dead code in the runner. **NOT USED.**
- **NoOpCheckpointer breaking change**: QC8 tests expect `NotImplementedError` from `NoOpCheckpointer.save/load`. HD changed it to no-op (silent return). Test `test_noop_checkpointer_raises_not_implemented` now FAILS.

## Anti-Pattern Scan Results

### M6: Bare except / blind exception
```
src/noa/tools/registration.py:115: except Exception:  # noqa: BLE001
src/noa/api/app.py:56,113,122,145,168,231: except Exception: # noqa: BLE001 (pre-existing)
```
The registration.py exception at line 115 has a logger.warning — acceptable per L9.

### M7: Wiring
- `runs_router` registered in `app.py:328` — PASS
- `set_app(app)` called in `create_app()` — PASS
- `PostgresCheckpointer` created and passed to `OrchestratorRunner` — PASS (wiring exists)

### M8: Domain isolation
```
grep "from noa.private_worker" src/noa/external_worker/ → No matches
grep "from noa.external_worker" src/noa/private_worker/ → No matches
```
CLEAN.

## Smoke Test Results
```
OK: governance imports
OK: runs imports
OK: registration imports
OK: app_state imports
OK: checkpointer imports
OK: checkpoint model import
OK: google_credential model import
OK: models __init__ exports
OK: GovernanceWrapper.execute has user_id param
OK: NoOpCheckpointer.save does not raise
OK: NoOpCheckpointer.load returns None
OK: replay_run_events has db param
OK: RateLimiter.check has user_id param
All smoke tests passed.
```

## Ruff Check Results
```
src/noa/api/v1/runs.py: I001 Import block is un-sorted or un-formatted
src/noa/db/models/google_credential.py: F401 `sqlalchemy.String` imported but unused
```
Two lint errors in changed files.

## Test Regression Results
3 existing tests FAIL after this commit:
1. `test_qc8_architecture.py::TestA4NoOpCheckpointer::test_noop_checkpointer_raises_not_implemented` — NoOpCheckpointer no longer raises NotImplementedError
2. `test_qc8_architecture.py::TestM5SSEReplay::test_replay_endpoint_returns_events_after_id` — `AttributeError: 'Depends' object has no attribute 'execute'` (DB session not mocked)
3. `test_qc8_architecture.py::TestM5SSEReplay::test_replay_endpoint_returns_empty_for_unknown_event` — same AttributeError

## Security

### BLOCKING: Plaintext Google OAuth tokens in DB (M3)
**File:** `src/noa/tools/registration.py:95-102`
**Spec:** SPEC.md line 686: "Google OAuth2 refresh token: Postgres (encrypted column)"
The column names (`access_token_enc`, `refresh_token_enc`) and model docstring claim encryption, but no encryption is applied. Raw OAuth tokens are stored as plaintext Text columns. An attacker with DB read access (SQL injection, backup compromise, stolen dump) gets full Google API access.

### BLOCKING: Replay endpoint auth bypass (M3)
**File:** `src/noa/api/v1/runs.py:100-106`
The query `select(RunEvent).where(RunEvent.run_id == run_id)` does not include a `user_id` filter. Any authenticated user can read any other user's run events by enumerating UUIDs. The `user` parameter is accepted from `require_auth` but never used.

## Code Quality

1. **Ruff lint errors** (S2): `I001` unsorted imports in `runs.py`, `F401` unused `String` import in `google_credential.py`.
2. **Misleading log message** (S4): `registration.py:114` logs "Google refresh token persisted (env + DB)" before the async DB task completes.
3. **Hardcoded user_id** (S2): `uuid.UUID(int=0)` in `registration.py:100` — should use the actual authenticated user's ID.
4. **Fire-and-forget task** (S1): `loop.create_task(_save())` with no result handling. Exceptions in `_save()` produce only `asyncio` unhandled task warnings.
5. **`select().limit(1)` without user filter** (S1): `registration.py:91` — if multiple users exist, updates wrong credential.

## Beyond the Test Plan

### GovernanceWrapper is an orphan
`GovernanceWrapper` is defined in `src/noa/tools/governance.py` and tested in `test_tool_governance.py`, but it is never imported or instantiated by any production code. The `ToolGateway` handles rate limiting and idempotency independently. Adding `user_id` to `GovernanceWrapper.execute()` is correct but has zero runtime effect because nothing calls it.

### PostgresCheckpointer is wired but unused
The checkpointer is created and passed to `OrchestratorRunner(checkpointer=checkpointer)`, which stores it as `self._checkpointer`. But `runner.py`'s `run()` method never calls `self._checkpointer.save()` or `self._checkpointer.load()`. SPEC.md S10.1 says "persistent state backed by Postgres" and S13.1 says "LangGraph checkpointer (AsyncPostgresSaver)" — neither is fulfilled because the save/load is never invoked.

### Replay endpoint skipping events by index is fragile
The replay uses `enumerate(rows, start=1)` and skips rows where `idx <= after_event_id`. This means `after_event_id` is a positional index, not a stable event identifier. If events are deleted or the order changes, the index-based approach returns wrong events. A proper implementation would use the event's actual `id` (UUID) or a monotonic sequence number stored in the DB.

## Blocking Issues

1. **3 test regressions** — `tests/unit/test_qc8_architecture.py`: NoOpCheckpointer behavior change (1 test) + replay_run_events signature change (2 tests). Tests must pass before merge.

2. **Plaintext token storage** — `src/noa/tools/registration.py:95-102`, `src/noa/db/models/google_credential.py:24-25`: SPEC.md line 686 requires "encrypted column" for Google OAuth refresh tokens. Column names claim `_enc` but no encryption is applied. Either encrypt before storage or remove the misleading naming and document the deviation.

3. **Replay endpoint authorization bypass** — `src/noa/api/v1/runs.py:100-106`: No user_id filter in query. Any authenticated user can read any run's events. Add `.where(RunEvent.user_id == user_id)` or join through the `runs` table to verify ownership.

4. **Zero new tests** — 5 findings resolved with no new tests. Each finding needs at least one behavioral test:
   - H8: Test that `GovernanceWrapper.execute(user_id=...)` passes user_id to rate limiter
   - M5: Test replay endpoint with a mocked DB session containing events
   - M10: Test that `_persist_google_tokens` calls session.commit with encrypted token
   - A1: Test that `set_app()` makes values retrievable from `app.state`
   - A4: Test that `PostgresCheckpointer.save()` creates/updates a row

5. **PostgresCheckpointer never called** — `src/noa/orchestrator/runner.py:33`: `self._checkpointer` is stored but `save()`/`load()` are never invoked in `run()`. A4 requires the checkpointer to actually persist state, not just exist.

6. **GovernanceWrapper.execute(user_id=...) never called from production code** — `src/noa/tools/governance.py:86-93`: No module imports or calls `GovernanceWrapper.execute()`. H8 resolution claims user_id is "wired through GovernanceWrapper" but there are zero callers.

## Decision Review

This commit resolved 5 findings by implementing the mechanism (class methods, DB models, startup wiring) but failed to complete the last mile in 3 of 5 cases:
- **H8**: Mechanism exists but GovernanceWrapper is not called from production code
- **M10**: DB table exists but tokens are not encrypted per spec
- **A4**: Checkpointer exists but runner never calls save/load

This matches the "wired in class, not at startup" anti-pattern identified in QC5 and QC8 retros. The pattern repeats because there is no integration test that exercises the full path.
