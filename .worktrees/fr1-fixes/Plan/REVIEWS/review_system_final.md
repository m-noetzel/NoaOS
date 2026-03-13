# QA Review: System-Wide Production Readiness

**Date:** 2026-03-10
**Verdict:** FAIL (architectural)
**Reviewer:** qa-review agent (review mode)
**Scope:** Full system -- backend, iOS client, web frontend, infrastructure

## Checklist Score
**Must-haves:** 4/8 | **Should-haves:** 3/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | All waves have tests with spec refs; 1313 passing |
| M2 | Negative Tests | PASS | Error paths tested per phase (auth, validation, not-found) |
| M3 | Security Boundaries | **FAIL** | 4 blocking issues: auth type mismatch crash, approval IDOR, secret_key fallback, push never sends |
| M4 | Determinism | PASS | No wall-clock assertions in tests; monotonic time used for rate limiting |
| M5 | Implementation Completeness | **FAIL** | list_runs is a stub returning empty; voice chat mode creates random thread; push never actually sends |
| M6 | No Silent Error Swallowing | **FAIL** | 6 ruff violations unfixed (3 BLE001 + 2 F401 + 1 E501); retention.py has 4 bare except blocks |
| M7 | Wiring Completeness | **FAIL** | APNs _http_client never initialized; push hooks log but never call send(); list_runs returns hardcoded empty |
| M8 | Domain Isolation | PASS | No cross-domain imports (verified by grep); Docker networks correctly separated |
| S1 | Error Handling & Boundaries | OPEN | queue.py has no user_id filter; memory facts are globally shared (no user isolation) |
| S2 | Code Consistency | OPEN | 3 endpoints still use `payload["sub"]` while require_auth returns AuthUser dataclass |
| S3 | Migration & Rollback | PASS | 8 migrations in sequence, all have downgrade() |
| S4 | Documentation | PASS | Type annotations present; inline comments on non-obvious logic |
| S5 | Integration Smoke Test | PASS | All 17 routers import; app factory creates successfully; modules are reachable |

## Executive Summary

The Noa system has impressive breadth -- 17 waves delivered, 1313 tests passing, 0 open findings, dual-domain Docker isolation, iOS client with Swift 6 strict concurrency, and Playwright E2E tests. The architecture is well-conceived. However, there are **production-blocking issues** that would cause runtime crashes or security vulnerabilities in deployment.

The four most critical issues are:

1. **Runtime crash in 3 endpoints** (voice.py, devices.py): `require_auth` returns `AuthUser` dataclass, but these endpoints index it as a dict (`payload["sub"]`). Any call to `/api/v1/voice/transcribe`, `/api/v1/devices/push-token`, or `/api/v1/devices/push-token` (DELETE) will crash with `TypeError`.

2. **Approval IDOR vulnerability**: `decide_approval` does not verify the authenticated user owns the approval. Any authenticated user can approve/deny any other user's pending approval by guessing the UUID.

3. **AuthService secret_key or "" fallback**: `auth/service.py` lines 82 and 123 use `self._settings.secret_key or ""`. While the middleware (`require_auth`) correctly rejects empty keys, the token *creation* path in `AuthService.login()` and `AuthService.refresh()` will sign tokens with an empty string if `secret_key` is None. The production validator catches this for `noa_env=production`, but development mode is unprotected.

4. **APNs push is completely non-functional**: `APNsService._http_client` is always `None`. No code ever initializes it. `send()` always returns `SendResult(success=False, reason="no_client")`. Push hooks in `RunService._notify_push` log "Push notification queued" but never actually look up device tokens or call `send()`.

---

## Blocking Issues

### B1: Runtime crash -- AuthUser subscript in voice.py and devices.py

**Files:**
- `src/noa/api/v1/voice.py:67` -- `user_id = uuid.UUID(payload["sub"])`
- `src/noa/api/v1/devices.py:37` -- `user_id = uuid.UUID(payload["sub"])`
- `src/noa/api/v1/devices.py:69` -- `user_id = uuid.UUID(payload["sub"])`

**Why:** `require_auth` returns `AuthUser(user_id=UUID, session_id=str|None)` -- a frozen dataclass. Accessing it with `["sub"]` raises `TypeError: 'AuthUser' object is not subscriptable`. These 3 endpoints crash on every authenticated request.

**Fix:** Change to `user_id = payload.user_id` (or accept `AuthUser` type annotation instead of `dict[str, Any]`).

**Severity:** Critical -- 3 endpoints completely broken.

---

### B2: Approval IDOR -- decide_approval has no ownership check

**File:** `src/noa/api/v1/approvals.py:74-76`

The query is:
```python
select(Approval).where(Approval.id == approval_id)
```

There is no `.where(Approval.user_id == user_id)` filter. Any authenticated user can approve or deny any other user's pending approval by providing the approval UUID.

**Comparison:** `list_pending_approvals` (line 40) correctly filters by `Approval.user_id == user_id`. The decide endpoint does not.

**Fix:** Add `.where(Approval.user_id == user_id)` to the select statement.

**Severity:** High -- authorization bypass allowing cross-user approval manipulation.

---

### B3: AuthService signs tokens with empty string when secret_key is None

**File:** `src/noa/auth/service.py:82,123`

```python
secret = self._settings.secret_key or ""
```

In development mode (default), `secret_key` defaults to `_DEV_SECRET` ("dev-secret-key-change-in-production") which is OK. But if someone sets `SECRET_KEY=""` or `SECRET_KEY` is explicitly empty, tokens get signed with `""`. While `require_auth` at line 59-62 checks `if not settings.secret_key: raise RuntimeError(...)`, this only protects token *validation*. Token *creation* in login/refresh uses the `or ""` fallback and would succeed, creating tokens signed with an empty key that can never be validated.

**Fix:** Remove `or ""` from both lines. Fail at token creation time if `secret_key` is unset.

**Severity:** Medium-High -- defense-in-depth gap. The middleware catches it on verification, but the creation path should not create unverifiable tokens.

---

### B4: APNs push notification pipeline is completely non-functional

**Files:**
- `src/noa/push/apns.py:63` -- `self._http_client: object | None = None` (never initialized)
- `src/noa/push/apns.py:123-125` -- `if self._http_client is None: return SendResult(success=False, reason="no_client")`
- `src/noa/runs/service.py:105-108` -- `_notify_push` logs but never calls `apns.send()`
- `src/noa/api/app.py:213-219` -- APNsService is instantiated but `_http_client` is never set

The entire push notification feature is decorative:
1. `APNsService` is instantiated in app lifespan (good)
2. `RunService._notify_push` calls `should_notify()` (good) and logs "queued" (misleading)
3. But `_notify_push` never looks up device tokens from DB and never calls `apns.send()`
4. Even if it did call `send()`, `_http_client` is None, so it would return "no_client"

**Fix:** (a) Initialize `_http_client` (httpx.AsyncClient with HTTP/2); (b) In `_notify_push`, query `DevicePushToken` for the user's device tokens and call `apns.send()` for each.

**Severity:** High -- feature advertised as implemented but zero functionality.

---

### B5: list_runs returns hardcoded empty data

**File:** `src/noa/api/v1/runs.py:23-29`

```python
@router.get("")
async def list_runs(...) -> dict[str, Any]:
    rid = trace_id_ctx.get("")
    return success_envelope(data={"events": []}, trace_id=rid)
```

This is a stub that ignores all parameters and returns empty. The `RunService.list_runs()` method exists with proper DB queries but is never called from this endpoint.

**Fix:** Query the DB for the user's runs, filtered by `user_id`.

**Severity:** Medium -- the endpoint is reachable and "works" (200 OK) but returns no data regardless of actual runs.

---

### B6: Ruff violations unfixed -- 6 errors fail the merge gate

```
BLE001 src/noa/external_worker/llm/anthropic.py:90
BLE001 src/noa/external_worker/llm/openai.py:88
BLE001 src/noa/orchestrator/runner.py:162
F401   src/noa/api/v1/audit.py:33 (unused AuditService import)
F401   src/noa/db/models/google_credential.py:11 (unused String import)
E501   src/noa/api/v1/voice.py:82 (line too long)
```

The first 3 are `except Exception:` blocks without `# noqa: BLE001`. The anthropic/openai ones parse error responses (reasonable code, just needs noqa). The runner.py one re-raises as an error event (also reasonable, needs noqa). The 2 F401s are dead imports. The E501 is a long comment line.

**Fix:** Add noqa suppression to the 3 BLE001 blocks; remove the 2 unused imports; wrap the long line.

**Severity:** Medium -- blocks the `ruff check` merge gate.

---

## Non-Blocking Issues (PASS_WITH_NOTES items)

### N1: Queue endpoint has no user_id filter

**File:** `src/noa/api/v1/queue.py:28-33`

`list_queue` returns all queued/processing tasks globally. The `task_queue` table has no `user_id` column, so this cannot be filtered per-user. In a single-user system this is acceptable; in multi-user it's an information disclosure.

### N2: Memory facts have no user isolation

**File:** `src/noa/api/v1/memory.py:40-41`

`list_facts` calls `store.list_all()` returning all facts for all users. The MemoryStore is file-based and has no per-user partitioning. Same concern as N1.

### N3: Voice chat mode creates random thread

**File:** `src/noa/api/v1/voice.py:124-125`

```python
thread_id = uuid.uuid4()
```

This creates a random thread ID without creating a DB conversation record. The thread_id is returned to the client but doesn't correspond to any real thread. The transcription is not fed into the chat pipeline.

### N4: Retention scheduler exception handling

**File:** `src/noa/maintenance/retention.py:71,78,96,103`

Four `except Exception:` blocks. They all call `logger.exception()` which is correct behavior, and ruff does not flag them (BLE001 considers logger.exception as handling the exception). However, `expire_stale()` at line 76 is called synchronously from an async context -- it should be wrapped in `run_in_executor` if it does I/O.

### N5: 23 test failures (all pre-existing)

- 14 in test_orchestrator.py / test_mr9 -- `ModuleNotFoundError: No module named 'langgraph'` (not installed on host, only in Docker)
- 8 in test_cp4 + test_mr9 -- same langgraph issue
- 1 in test_qc2 -- `FileNotFoundError: /workspace/web/src/auth/tokens.ts` (Docker path, running on host)

These are all pre-existing and documented in MEMORY.md.

### N6: MCP adapter remains a stub

**Files:** `src/noa/tools/mcp_adapter.py:43`, `src/noa/tools/adapters/mcp_remote.py:41`

Both raise `NotImplementedError`. Documented as Phase 2 -- acceptable for Phase 1 deployment.

### N7: APNs config uses `or ""` fallbacks

**File:** `src/noa/api/app.py:215-217`

```python
team_id=settings.apns_team_id or "",
key_path=settings.apns_key_path or "",
bundle_id=settings.apns_bundle_id or "",
```

These create an APNsService with empty strings for critical config. The service would fail at JWT generation time (reading empty key_path), but this is masked because `_http_client` is never initialized so `send()` never reaches JWT generation.

### N8: tools.py hasattr fallback pattern

**File:** `src/noa/api/v1/tools.py:38-39`

```python
payload.user_id if hasattr(payload, "user_id") else uuid.UUID(payload["sub"])
```

This dual-path pattern (AuthUser vs dict) appears in multiple endpoints. The dict path is dead code since require_auth always returns AuthUser. Should be cleaned up for consistency.

---

## Anti-Pattern Scan Results

### M6: Bare except / blind exception
```
ruff check src/ output: 3 BLE001, 2 F401, 1 E501 = 6 errors
```
- `src/noa/external_worker/llm/anthropic.py:90` -- `except Exception:` (no noqa)
- `src/noa/external_worker/llm/openai.py:88` -- `except Exception:` (no noqa)
- `src/noa/orchestrator/runner.py:162` -- `except Exception as exc:` (no noqa)

All 3 are reasonable code (error response parsing, exception-to-event conversion) but need noqa suppression.

### M7: Wiring completeness
- All 17 routers registered in app.py: PASS
- APNsService instantiated in lifespan: PASS (but `_http_client` not initialized)
- Push hooks exist in RunService: PARTIAL (logs only, never calls send)
- list_runs endpoint: STUB (returns empty)

### M8: Domain isolation
```
grep "from noa.private_worker" src/noa/external_worker/ -> No matches
grep "from noa.external_worker" src/noa/private_worker/ -> No matches
```
Domain isolation is clean.

## Smoke Test Results

```
[OK] create_app imports
[OK] Settings() noa_env=development
[OK] AuthUser is dataclass
[FINDING] voice.py/devices.py: AuthUser['sub'] crashes with TypeError
[FINDING] secret_key=None -> empty string in AuthService.login/refresh
[FINDING] APNs _http_client=None -- send() always returns no_client
[FINDING] approvals.py decide: no user_id filter on SELECT
[OK] All 17 routers import successfully
```

Test suite: 1313 passed, 23 failed (all pre-existing), 55 warnings.

## Security

### Auth boundaries
- `require_auth` correctly enforces 401 on all protected endpoints
- httpOnly cookies for web, Bearer tokens for iOS -- dual-path correct
- CORS explicitly configured, wildcard rejected (M2 fix applied)
- CSP headers set via middleware
- Token type validation ("access" only) -- PASS
- Sub claim UUID validation -- PASS

### Authorization gaps
- **B2 (Critical):** `decide_approval` has no ownership check -- any user can decide any approval
- `list_pending_approvals` correctly filters by user_id -- inconsistency shows B2 is a bug, not a design choice
- `queue.py` returns all tasks globally (no user_id column in table)
- `memory.py` returns all facts globally (no user isolation in MemoryStore)

### Secret handling
- `_DEV_SECRET` in config.py -- acceptable for dev, production validator rejects it
- `.env` and `.env.secrets` in .gitignore -- PASS
- Only `.env.example` tracked in git -- PASS
- Keychain-based secret injection (2e7bbf1) -- good practice
- `secret_key or ""` in auth service -- B3 (defense-in-depth gap)

### Token storage
- Web: httpOnly cookies -- PASS (C6 resolved)
- `tokens.ts`: only stores auth flag in localStorage, not tokens -- PASS
- iOS: Keychain via KeychainService -- PASS

## Code Quality

### Positive
- Consistent use of `success_envelope()` for response formatting
- Proper layering in most endpoints (deps -> service -> DB)
- Type annotations throughout
- AuthUser dataclass (M11 fix) eliminates fragile dict access in most endpoints
- ToolGateway has proper idempotency, rate limiting, and telemetry

### Issues
- `hasattr(payload, "user_id") else payload["sub"]` dual-path in 5+ endpoints -- should be cleaned up
- `_make_run_service` in chat.py creates sync session but app is async-first
- RunService methods are sync (`.query()`, `.flush()`) while most DB code is async
- `list_runs` is still a stub
- Voice chat mode is a stub (random thread_id, no pipeline integration)

## Beyond the Test Plan

### Issues not previously identified

1. **Approval flush without commit:** `decide_approval` at line 95 calls `await session.flush()` but never `await session.commit()`. In FastAPI with `get_db_session` dependency, the session lifecycle depends on whether the dependency does auto-commit on exit. If not, the decision is never persisted.

2. **Memory store._persist() is sync file I/O in async endpoint:** `memory.py:91` calls `store._persist(str(fact_id))` which does synchronous file writes. This blocks the event loop.

3. **Thread delete doesn't cascade to messages:** `delete_thread` at line 158 calls `session.delete(conversation)` but there's no ON DELETE CASCADE check. If the DB relationship doesn't cascade, orphaned messages remain.

4. **Cost summary uses raw SQL with NOW():** `cost.py:63` uses `date_trunc('day', NOW())` which is PostgreSQL-specific. Tests with SQLite will fail or produce wrong results.

5. **Voice endpoint: payload type mismatch:** `voice.py:54` annotates `payload: dict[str, Any]` but receives `AuthUser`. The endpoint works accidentally because Python doesn't enforce type annotations at runtime, but it's misleading.

---

## Decision Review

This system has been built through an impressive 17-wave pipeline with 53 findings discovered and resolved, 1313 tests, and thorough QA at each phase. The architecture (dual-domain isolation, policy engine, approval flow, audit hash chain) is well-designed.

However, the system is **not production-ready** due to:
- 3 endpoints that crash at runtime (B1)
- 1 authorization bypass (B2)
- 1 completely non-functional subsystem advertised as working (B4 push)
- 1 stub endpoint returning fake data (B5 list_runs)
- 6 ruff violations failing the merge gate (B6)

The predominant pattern is **implementation drift**: as `require_auth` evolved from returning a raw dict to returning `AuthUser`, some endpoints were not updated. And the push notification feature was built layer-by-layer across multiple phases (iOS1, iOS6) but the final wiring -- initializing the HTTP client and calling send() from hooks -- was never completed.

**Recommended fix order:**
1. B1: Fix AuthUser subscript crashes in voice.py, devices.py (5 min)
2. B2: Add user_id ownership check to decide_approval (2 min)
3. B3: Remove `or ""` from auth service token creation (2 min)
4. B6: Fix ruff violations (5 min)
5. B5: Wire list_runs to RunService (10 min)
6. B4: Initialize APNs HTTP client and complete push pipeline (30 min)
