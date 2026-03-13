# QA Review: Phase PR1

**Date:** 2026-03-11
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 8/8 | **Should-haves:** 4/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | Test file cites SPEC.md 13.2, 22.1, 22.2. All three deliverables (BE-C1, BE-C2, BE-H2) have dedicated test classes. |
| M2 | Negative Tests | PASS | test_update_status_raises_for_invalid_transition, test_approve_fact_only_approves_owned_facts, test_delete_fact_only_deletes_owned_facts, test_get_run_returns_zeros_when_no_usage_stats, test_list_all_returns_empty_for_unknown_user |
| M3 | Security Boundaries | PASS | Memory endpoints pass user_id to store; runs endpoint filters by user_id; no hardcoded secrets; no unsafe fallbacks |
| M4 | Determinism | PASS | No wall-clock deps in assertions; duration_ms test uses timedelta (deterministic). No network calls. |
| M5 | Implementation Completeness | PASS | All 3 deliverables implemented: runs join usage_stats, memory user-scoped, RunService async. No TODO/FIXME. |
| M6 | No Silent Error Swallowing | PASS | No new bare except blocks. Pre-existing noqa-suppressed BLE001 blocks in runner.py and chat.py all have logging. |
| M7 | Wiring Completeness | PASS | runs_router and memory_router already registered in app.py. RunService used by runner.py (async calls). _NoOpRunService updated to async. |
| M8 | Domain Isolation | PASS | No cross-domain imports. memory_store.py stays in private_worker. |
| S1 | Error Handling & Boundaries | PASS | Empty usage stats handled (zeros/empty strings). 404 on missing run. Memory store returns False/None on missing facts. |
| S2 | Code Consistency | PASS | Follows existing patterns: success_envelope, trace_id_ctx, AuthUser, async session.execute(select(...)). |
| S3 | Migration & Rollback | N/A | No DB schema changes in PR1. |
| S4 | Documentation | PASS | Docstrings on all public methods. Type annotations present. |
| S5 | Integration Smoke Test | OPEN | Tests mock the DB session (AsyncMock). No non-mocked integration test exists for PR1. The MemoryStore tests are closest to integration (real MemoryStore instance) but all endpoint tests use mocked sessions. |

## Test Plan Coverage
No formal test plan was written for PR1 prior to implementation. The 19 tests cover all three deliverables with both happy-path and error-path scenarios. Missing: a non-mocked integration test calling the endpoint through TestClient with a real in-memory DB.

## Spec Compliance

**SPEC.md 22.1 (Run Schema):** The list_runs and get_run endpoints now return real model, provider, tokens_in, tokens_out, cost_usd, and duration_ms by joining the usage_stats table. This matches the spec's run schema fields. PASS.

**SPEC.md 13.2 (Long-Term Memory):** The Memory Audit UI endpoints (list, approve, update, delete) now pass user_id to the MemoryStore, preventing cross-user data access. The read path is correctly scoped. PASS.

**SPEC.md 22.2 (Event Stream):** RunService.append_event is now async. The runner.py _persist_event is async and awaits the service. PASS.

## Test Coverage

| Spec Requirement | Test(s) | Status |
|---|---|---|
| BE-C1: list_runs with usage | TestListRunsUsageJoin (3 tests) | Covered |
| BE-C1: get_run with usage | TestGetRunUsageJoin (2 tests) | Covered |
| BE-C2: list_all user-scoped | test_list_all_filters_by_user_id, test_list_all_returns_empty_for_unknown_user | Covered |
| BE-C2: update_status user-scoped | test_approve_fact_only_approves_owned_facts | Covered |
| BE-C2: delete user-scoped | test_delete_fact_only_deletes_owned_facts | Covered |
| BE-C2: persist() public | test_update_fact_uses_public_persist_method | Covered |
| BE-H2: RunService async | TestRunServiceAsync (8 tests) | Covered |
| BE-H2: _NoOpRunService async | Smoke test verified | Covered |
| BE-H2: runner._persist_event async | Smoke test verified | Covered |

## Anti-Pattern Scan Results

**M6 (bare except / blind exception):**
- `src/noa/runs/service.py:138`: `except Exception: # noqa: BLE001` -- pre-existing, has logging (warning + exc_info). Not new.
- `src/noa/orchestrator/runner.py`: 5 `except Exception: # noqa: BLE001` blocks -- all pre-existing, all have logging. Not new.
- `src/noa/api/v1/chat.py`: 5 `except Exception: # noqa: BLE001` blocks -- all pre-existing, all have logging. Not new.

**M7 (wiring):** runs_router and memory_router registered in app.py. Confirmed.

**M8 (domain isolation):**
- `grep "from noa.private_worker" src/noa/external_worker/`: No matches.
- `grep "from noa.external_worker" src/noa/private_worker/`: No matches.
Clean.

## Smoke Test Results

```
runs.py: list_runs=list_runs, get_run=get_run, routes=5
memory.py: list_facts, approve_fact, update_fact, delete_fact
MemoryStore.list_all(user_id=...) -> []
MemoryStore.get_by_id(user_id=...) -> None
MemoryStore.update_status(user_id=...) -> False
MemoryStore.delete(user_id=...) -> False
MemoryStore.persist() exists: OK
RunService: all methods are async: OK
OrchestratorRunner._persist_event is async: OK
_NoOpRunService: all methods are async: OK
UsageStats model: usage_stats
All smoke tests PASSED
```

## Security

- **User-scoped memory:** All four memory endpoints (list, approve, update, delete) pass `str(user.user_id)` to the store. Cross-user access prevented at the store level.
- **User-scoped runs:** list_runs filters by `Run.user_id == user.user_id`. get_run also filters by user_id. No IDOR on runs endpoints.
- No hardcoded secrets or unsafe fallback defaults in changed files.

## Code Quality

- Clean: ruff check passes on all 6 changed source files.
- Consistent use of `func.coalesce` for NULL-safe aggregation.
- Duration_ms computed from `updated_at - created_at` -- simple and correct.
- The `or ""` / `or 0` fallbacks in the aggregation result handling are defensive (double-safety after coalesce). Acceptable.

## Beyond the Test Plan

### Note 1: MemoryStore.store() does not accept user_id

The `store()` method (called by the orchestrator's `_handle_remember`) does not accept or set `user_id` on facts. Facts stored via the orchestrator pipeline will have no `user_id` field, so `list_all(user_id=...)` will never return them. This means the Memory Audit UI shows zero facts even when facts exist.

**Impact:** The write path and read path are disconnected on user_id. This is a pre-existing gap not introduced by PR1, but PR1's user-scoping makes it visible. The fix is to add `user_id` as a parameter to `store()` and ensure the orchestrator passes it.

**Severity:** High (data invisible to user). Recommend tracking in FINDINGS.md.

### Note 2: RuntimeWarning in tests

`session.add` is called on an `AsyncMock` session, producing `RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited`. This happens because `session.add()` is a sync method in SQLAlchemy but AsyncMock makes all attribute access return coroutines. Use `MagicMock` for the session with `execute` and `flush` explicitly set as `AsyncMock` to avoid this.

### Note 3: No integration test with real DB

All endpoint tests use `AsyncMock` for the DB session. While the MemoryStore tests exercise real code paths (good), there's no test that creates an actual `AsyncSession` with an in-memory SQLite DB, inserts a Run + UsageStats, and calls `list_runs`. This is the recurring "tests pass with mocks but fail with real DB" risk. Non-blocking for PR1 but should be addressed in PR6 (Integration Tests phase).

## Notes (PASS_WITH_NOTES)

1. **MemoryStore.store() lacks user_id parameter** -- facts created via the orchestrator are invisible to the user-scoped API. Pre-existing but now more impactful. Should be tracked as a finding and addressed in PR4 (BE-M2: MemoryStore interface).

2. **No non-mocked integration test** -- S5 open. Should be addressed in PR6. The MemoryStore tests are behavioral (real class, no mocks) which partially satisfies S5.

3. **RuntimeWarning from AsyncMock on session.add** -- cosmetic but indicates test infrastructure could be tighter. Use MagicMock with selective AsyncMock attributes.

## Decision Review

PR1 delivers all three stated fixes correctly. The runs endpoint now returns real usage data instead of hardcoded zeros. Memory endpoints are user-scoped. RunService is fully async. The implementation is clean and well-tested with 19 new tests plus 0 regressions in existing test suites (37 test_runs.py + 36 test_mv2/qc5 tests all pass).

The main gap is the write-side user_id missing from `store()`, which is outside PR1's scope but worth tracking.
