# QA Review: Phase QC4 + QC5

**Date:** 2026-03-07
**Verdict:** FAIL
**Reviewer:** qa-review agent

## Checklist Score
**Must-haves:** 5/8 | **Should-haves:** 3/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | All 35 tests have docstrings citing SPEC.md or PHASE_DETAILS.md |
| M2 | Negative Tests | PASS | Error paths covered: ProviderRouter not configured (503), unknown task_type, invalid RPC, violation threshold |
| M3 | Security Boundaries | PASS | No hardcoded secrets, domain isolation enforced at import level |
| M4 | Determinism | PASS | ContractViolationTracker uses `time.monotonic()`, not wall-clock. Retention tests use `datetime.now(UTC)` only for DB fixture setup (not assertions) |
| M5 | Implementation Completeness | FAIL | **H2: alembic migration `006_performance_indexes.py` not created** (only model-level indexes, no migration). **M3+M6: app.py lifespan still uses `_PurgeProxy` — does not pass real AuditService or approval_service to RetentionScheduler** |
| M6 | No Silent Error Swallowing | PASS | retention.py `except Exception:` blocks all call `logger.exception()`. M6 is `noqa: BLE001` suppressed with justification |
| M7 | Wiring Completeness | FAIL | **M3 fix is not wired: app.py lifespan passes `_PurgeProxy` (always returns 0) to RetentionScheduler, never the real AuditService with `purge_expired_async`. M6 approval_service is never passed to RetentionScheduler in app.py** |
| M8 | Domain Isolation | PASS | No cross-domain imports. AST scan and runtime import test both pass |
| S1 | Error Handling & Boundaries | PASS | Empty payload, bad task_type, disconnected router all tested |
| S2 | Code Consistency | PASS | Naming follows conventions; shared module in `noa.llm` correctly layered |
| S3 | Migration & Rollback | OPEN | `006_performance_indexes.py` migration never created — indexes exist in models but cannot be applied to existing databases without migration |
| S4 | Documentation | PASS | Type annotations and docstrings present throughout |
| S5 | Integration Smoke Test | OPEN | QC4 has a real import-chain integration test (`test_provider_router_import_does_not_load_private_worker`). QC5 has a real SQLite integration test for `purge_expired_async`. However both worker endpoint tests accept 502/503 as "wired" — weak integration signal |

---

## Spec Compliance

### QC4

| Finding | Requirement | Status |
|---------|-------------|--------|
| C2 | `OllamaClient` in `noa.llm.providers` (shared) | PASS |
| C2 | `MAX_N_RESULTS` in `noa.constants` | PASS |
| C2 | No cross-domain imports in `external_worker` or `private_worker` | PASS |
| H1 | External worker has `POST /v1/complete` endpoint | PASS |
| H1 | Private worker has `POST /rpc` endpoint | PASS |
| H9 | Google AI tool calls have synthetic `id` field | PASS |

### QC5

| Finding | Requirement | Status |
|---------|-------------|--------|
| H2 | Performance indexes defined on 7 tables | PASS (models) |
| H2 | Alembic migration `006_performance_indexes.py` created | **FAIL — missing** |
| M3 | `AuditService.purge_expired_async` implemented | PASS |
| M3 | `purge_expired_async` actually called in app.py lifespan | **FAIL — `_PurgeProxy` still used** |
| M6 | `RetentionScheduler` accepts `approval_service` parameter | PASS |
| M6 | `approval_service` passed in `app.py` lifespan | **FAIL — not wired** |
| M9 | `ContractViolationTracker.violation_count` filters 24h window | PASS |
| M12 | `RunService.create_run` is async | PASS |
| M12 | `RunService.append_event` is async | PASS |
| M12 | `AuditService.purge_expired` alias is async | PASS (but see regression below) |

---

## Test Coverage

### QC4 (15 tests)

| Test Class | Spec Reference | Coverage Quality |
|------------|---------------|-----------------|
| `TestDomainIsolationImports` (3) | SPEC §6.2, ARCH L3 | Solid — AST scan |
| `TestSharedModuleLocation` (4) | PLAN QC4/C2, SPEC §9.1 | Solid — import + AST |
| `TestExternalWorkerCompleteEndpoint` (2) | PLAN QC4/H1 | Weak: accepts 503 as success |
| `TestPrivateWorkerRpcEndpoint` (3) | SPEC §9.1, §9.2 | Weak: accepts error responses as wired |
| `TestGoogleAIToolCallId` (2) | PLAN QC4/H9 | Solid |
| `TestDomainIsolationIntegration` (1) | SPEC §6.2 | Solid |

**Gap:** No negative test verifies that a private-mode request to an external provider raises `PrivacyViolationError`.

### QC5 (20 tests)

| Test Class | Spec Reference | Coverage Quality |
|------------|---------------|-----------------|
| `TestPerformanceIndexes` (7) | SPEC §28.7, §14, §17.2 | Solid — model inspection |
| `TestRetentionPurge` (3) | PLAN QC5/M3, SPEC §28.7 | Solid — real SQLite integration |
| `TestApprovalExpiry` (2) | PLAN QC5/M6 | Tests class API, not app.py wiring |
| `TestContractViolationWindow` (4) | SPEC §9.4 | Solid |
| `TestRunServiceAsync` (4) | PLAN QC5/M12 | Tests API shape only; no behavioral async test |

**Gap:** No test verifies that `app.py` passes a real `AuditService` (with `purge_expired_async`) to `RetentionScheduler` — the test at line 184-203 mocks the service and passes, but `app.py` still uses `_PurgeProxy`.

**Gap:** No test verifies that `approval_service` is actually passed to the scheduler in production startup.

---

## Anti-Pattern Scan Results

```
# M6: Bare except blocks
No bare except found (across all QC4/QC5 changed files)

# M6: Broad Exception catches
src/noa/maintenance/retention.py:71:        except Exception:
src/noa/maintenance/retention.py:78:            except Exception:
src/noa/maintenance/retention.py:96:        except Exception:
src/noa/maintenance/retention.py:103:            except Exception:

→ All 4 blocks call logger.exception() or logger.info() — no silent swallowing.
  These are in _run_once / run_once for scheduler resilience. Acceptable.

# M7: Router registration in app.py
(all existing routers verified — no new FastAPI routers added in QC4/QC5)

# M8: Cross-domain imports
OK: no private->external leaks (grep confirmed)
OK: no external->private leaks (grep confirmed)
```

---

## Smoke Test Results

```
# 35 QC4+QC5 tests: ALL PASS
pytest tests/unit/test_qc4_domain_isolation.py tests/unit/test_qc5_database_integrity.py
35 passed in 0.26s

# Full test suite regression check:
pytest tests/unit/ -q
68 failed, 986 passed, 39 warnings in 10.34s
```

**Regression failures by file:**

| File | Count | Root Cause |
|------|-------|-----------|
| `test_runs.py` | 54 | QC5 M12: `create_run` and `append_event` made async, but `test_runs.py` calls them synchronously (not marked `asyncio`). All calls return a coroutine object instead of a Run/RunEvent. |
| `test_audit.py` | 3 | QC5 M12: `purge_expired = purge_expired_async` alias makes sync callers get a coroutine. `test_audit.py` calls `svc.purge_expired(retention_days=90)` without `await`. |
| `test_llm_ollama.py` | 5 | QC4 C2: tests patch `noa.private_worker.ollama_client.httpx.AsyncClient`, but `private_worker/ollama_client.py` is now a re-export shim — `httpx` is no longer an attribute of that module. Patches miss. |
| `test_cp4_startup.py` | 2 | Pre-existing: `langgraph` not installed → `OrchestratorRunner` build fails → swallowed by `except Exception` in `wire_llm_pipeline`. Not a new regression from QC4/QC5. |
| `test_orchestrator.py` | 8 | Pre-existing: `langgraph` missing. |
| `test_mr8_model_routing.py` | 1 | Pre-existing: `langgraph` missing. |
| `test_mr9_conditional_edges.py` | 10 | Pre-existing: `langgraph` missing. |
| `test_new_endpoints.py` | 1 | Pre-existing: artifact route count mismatch (unrelated to QC4/QC5). |

**New regressions introduced by QC4/QC5: 62 tests** (54 from `test_runs.py` + 3 from `test_audit.py` + 5 from `test_llm_ollama.py`).

---

## Security

No new security issues introduced.

- No hardcoded secrets in any new/modified file
- Domain isolation correctly enforced at import boundary
- `PrivacyViolationError` raised on private-mode external-provider routing
- No unsafe fallback defaults on secrets

---

## Code Quality

### Concern 1: `purge_expired = purge_expired_async` class-level alias

`audit/service.py:200` — This alias makes the formerly-sync `purge_expired` method async. Any caller that does `svc.purge_expired(retention_days=90)` now gets a coroutine, not a count. The docstring of `purge_expired_async` even says "Alias: keep purge_expired as async (M12 standardization)" — but this is a **silent, backwards-incompatible API change** that broke 3 existing tests without updating callers.

### Concern 2: `_PurgeProxy` still in app.py after M3 fix

`app.py:197-207` — The `_PurgeProxy` class always returns `0` from `purge_expired()`. `RetentionScheduler._purge_audit()` checks for `purge_expired_async` first; `_PurgeProxy` has no such method, so it falls back to calling `purge_expired()` which returns `0`. The M3 fix in `AuditService` is never exercised in production. This means audit log retention is still effectively disabled in the running system.

### Concern 3: `approval_service` not passed to `RetentionScheduler` in app.py

`app.py:209-215` — The M6 deliverable (wire `expire_stale` into scheduler) was implemented in `RetentionScheduler` but not connected in `app.py`. Stale approvals are never expired in production.

### Concern 4: Module re-export breaks existing patch targets

`private_worker/ollama_client.py` is now a thin re-export. Any test patching `noa.private_worker.ollama_client.httpx` (or similar attributes) will silently miss. The `test_llm_ollama.py` tests demonstrate this exact pattern.

### Concern 5: Handlers module-level MemoryStore pointing to `/data/memory`

`private_worker/handlers.py:21` — `_memory_store = MemoryStore(data_dir=Path("/data/memory"))` runs at import time. In tests, this path does not exist, so `_load_from_disk()` silently skips (path doesn't exist check). Not a crash, but writes to `/data/memory` will fail silently in tests. The `OSError` is caught and logged as a warning in `_persist()`.

---

## Blocking Issues (FAIL)

1. **REGRESSION — `test_runs.py`: 54 tests broken** (`src/noa/runs/service.py`, `tests/unit/test_runs.py`)
   QC5 made `create_run` and `append_event` async (M12). The existing `test_runs.py` tests are synchronous and call these methods without `await`. All 54 tests now receive coroutine objects instead of `Run`/`RunEvent` instances.
   Example failure: `test_runs.py:120` — `AttributeError: 'coroutine' object has no attribute 'id'`

2. **REGRESSION — `test_audit.py`: 3 tests broken** (`src/noa/audit/service.py:200`, `tests/unit/test_audit.py`)
   `purge_expired = purge_expired_async` class alias makes the formerly-sync method async. Existing tests call `svc.purge_expired(retention_days=90)` synchronously and get back a coroutine.
   Example failure: `test_audit.py:356` — `assert <coroutine object AuditService.purge_expired_async ...> == 1`

3. **REGRESSION — `test_llm_ollama.py`: 5 tests broken** (`src/noa/private_worker/ollama_client.py`, `tests/unit/test_llm_ollama.py`)
   QC4 moved `OllamaClient` implementation to `noa.llm.providers.ollama` and made `noa.private_worker.ollama_client` a re-export shim. Tests that patch `noa.private_worker.ollama_client.httpx` now fail with `AttributeError: module 'noa.private_worker.ollama_client' has no attribute 'httpx'`.
   Example failure: `test_llm_ollama.py` — `AttributeError: module 'noa.private_worker.ollama_client' has no attribute 'httpx'`

4. **M5 — Missing alembic migration `006_performance_indexes.py`** (PHASE_DETAILS.md Phase QC5, finding H2)
   The phase plan explicitly lists this as a deliverable. Indexes are added to SQLAlchemy models but there is no migration to apply them to an existing running database. `alembic/versions/` contains only 001-005.

5. **M7 — M3 fix is not wired: `_PurgeProxy` still used in app.py** (`src/noa/api/app.py:197-215`)
   `app.py` lifespan creates a `_PurgeProxy` that always returns `0` and passes it to `RetentionScheduler` instead of a real `AuditService`. The `purge_expired_async` method implemented in QC5 is never called in production. Audit log retention remains disabled.

6. **M7 — M6 approval expiry not wired in app.py** (`src/noa/api/app.py:209-215`)
   `RetentionScheduler` in the lifespan is created without `approval_service=`. Even though the class supports `expire_stale()` integration (tested in isolation), it is never connected to the running system.

---

## Notes

1. The 35 new QC4+QC5 tests are well-structured and have good spec traceability. The test plan quality is high.

2. Worker endpoint tests (`test_complete_endpoint_returns_llm_response`, `test_rpc_endpoint_accepts_valid_request`) accept HTTP 502/503 as "wired" — they test wiring but not behavior. This is acknowledged in the test docstrings but worth noting for future improvement.

3. `purge_expired_async` uses SQLite dialect detection to avoid `asyncio.to_thread` overhead in tests (smart pattern). However the SQLite check uses `getattr(bind, "dialect", None)` which may not work with async engines where `bind` is `None`. Verify in a Postgres context.

4. `ContractViolationTracker` uses `time.monotonic()` which is correct for interval tracking but cannot survive process restarts — violations from a previous process instance are lost. This is acceptable for the current phase but should be noted for production hardening.

---

## Decision Review

No `DECISION_LOG.md` entries found for QC4/QC5 specifically. The code-review fixes (C1-C5 in the phase description) are reflected in the implementation. The reversed re-export direction (OllamaClient canonical in `noa.llm.providers`, `private_worker/ollama_client.py` re-exports) is correct per ARCH_INVARIANTS L3 but broke existing test patch targets — a migration concern that was not caught before merge.
