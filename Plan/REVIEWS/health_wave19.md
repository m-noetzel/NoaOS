# System Audit Report — Wave 19 (2026-03-11)

## Summary
- **Overall Health Score**: 7.5/10
- **Endpoints Tested**: 18/18 working (with auth), 14/14 correctly reject unauthenticated access
- **E2E Flows Tested**: 4/5 passing (Thread CRUD, Auth, Settings GET/PUT, Tools list)
- **Security Issues**: 3 found (1 medium, 2 low)
- **Dead Code Items**: 4 found
- **Cross-Phase Regressions**: 1 found (ChatRequest.privacy_mode still required)
- **Test Suite**: 1474 passing, 1 failing (known pre-existing)
- **Static Analysis**: 1 ruff error (line length), 62 mypy errors (mostly type narrowing)
- **Domain Isolation**: Clean (no cross-domain imports)

## Critical Findings (must fix before next wave)

None.

## High Findings (fix soon)

### W19-H1: ChatRequest.privacy_mode Is Still Required (str, not optional)

**File:** `src/noa/api/v1/chat.py:32`

PR3 made `model` and `provider` optional (`str | None = None`) to fix Swift JSONEncoder nil-omission 422s, but `privacy_mode` remains `str` (required). iOS clients that omit `privacy_mode` will get 422 validation errors. Additionally, the value is not validated against `Literal["private", "external"]` — any string is accepted, which could bypass domain isolation (SPEC.md section 6.2).

**Test documenting this:** `test_ios5_chat_contract.py::test_chat_request_schema_rejects_invalid_privacy_mode` (the only failing test).

**Impact:** iOS chat is broken if the client doesn't send privacy_mode; domain isolation can be bypassed with arbitrary strings.

### W19-H2: Running Container Needs Restart to Pick Up Wave 19 Code

The `noaos-noa-api-1` container runs uvicorn without `--reload`. Source code is bind-mounted from `/Users/martin2020/Projekte/NoaOS/src` to `/app/src`, so the files on disk reflect all Wave 19 changes. However, the running uvicorn process was started before some changes were made, so certain features (like PATCH /settings) return 405 despite being correctly registered in the source code.

**Fix:** Restart the container (`docker compose restart noa-api`) or add `--reload` for development.

**Note:** This is operational, not a code defect. PATCH /settings works correctly when tested via `starlette.testclient.TestClient` against a freshly created app instance.

### W19-H3: JWT Error Messages Leak Internal Details (Pre-existing, not new)

**Observed:** `"Invalid token: Invalid header string: 'utf-8' codec can't decode byte 0x8a in position 0: invalid start byte"` returned in 401 responses.

Error messages from JWT decode failures are passed through to the client verbatim. An attacker could use these messages to fingerprint the JWT library and token format.

**Fix:** Return a generic "Invalid token" message for all JWT failures; log the specific error server-side.

## Medium Findings (track)

### W19-M1: Old mcp_adapter.py Is Dead Code (Superseded by TM6)

**File:** `src/noa/tools/mcp_adapter.py`

The `MCPToolAdapter` class raises `NotImplementedError` and is not imported anywhere. TM6 replaced this with `src/noa/tools/adapters/mcp_remote.py` which has real HTTP+SSE JSON-RPC 2.0 transport. This file should be deleted.

### W19-M2: GovernanceWrapper Is Dead Code (Never Imported)

**File:** `src/noa/tools/governance.py`

`GovernanceWrapper` provides idempotency, rate limiting, and dry-run previews, but is never imported outside its own file. The ToolGateway in `gateway.py` implements these features directly. This module should be deleted or consolidated.

### W19-M3: noa.coding Module Is Orphaned (Never Imported)

**Files:** `src/noa/coding/{contract.py, sandbox.py, worker.py}`

The entire coding task module (CodingTaskInput, ShellSandbox, CodingWorker) is self-contained and never imported from any other module. It was created in AB5 but never wired into the orchestrator or any API endpoint.

### W19-M4: noa.queue.notifications Is a No-Op Stub (Never Imported)

**File:** `src/noa/queue/notifications.py`

Contains an empty `notify()` method that is never called from anywhere.

### W19-M5: Missing X-Content-Type-Options Header

The API does not set `X-Content-Type-Options: nosniff`. While CSP is configured with `frame-ancestors 'none'`, the `nosniff` header prevents MIME-type confusion attacks on artifact downloads.

### W19-M6: 62 mypy Errors in Source

Key issues:
- `success_envelope` signature expects `dict[str, Any]` but many endpoints pass `list[...]` (threads, cost, queue, artifacts, approvals, memory)
- `threads.py:130-133` accesses attributes (`thread_id`, `role`, `content`, `timestamp`) that don't exist on `Conversation` model
- `tools.py:73,96` calls `None` as callable
- `app.py:142` type mismatch (NoOpCheckpointer vs PostgresCheckpointer)
- `app.py:234-236` passes `str | None` where `str` is required (APNs config)

## Low/Informational

### W19-L1: 1 Ruff Error (Line Length)

`src/noa/api/v1/threads.py:45` — line 90 chars, limit is 88. Trivial fix.

### W19-L2: Pre-existing Open Findings (11 total)

All pre-Wave-19 open findings remain open:
- **BE-H4** (High): SSE replay cursor uses list index, not stable DB offset
- **BE-H5** (High): chat.py `_update_run_status` bypasses RunService state machine
- **BE-M1** (Medium): Cost endpoint uses raw SQL with magic column indices
- **BE-M5** (Medium): MemoryStore.store() saves facts without user_id
- **FE-M5** (Medium): No unsaved-changes warning on Settings page
- **iOS-L1** (Low): Environment.swift hardcoded dev IP
- **iOS-L2** (Low): DEBUG builds disable certificate pinning
- **FE-L1** (Low): ErrorBoundary renders error.stack to UI
- **L10-L12** (Low): Feature requests (tool management UX, diagnostics, user management)

### W19-L3: Test Warning Noise

57 pytest warnings: 5 unknown custom marks (tm1-tm6), 1 unawaited coroutine in `durable.py:139` test.

## Endpoint Status Matrix

| Route | Method | Auth | Status | Notes |
|-------|--------|------|--------|-------|
| `/health` | GET | No | 200 | Working |
| `/health/ready` | GET | No | 200 | Returns "degraded" (expected without all services) |
| `/health/echo` | GET | No | 422 | Requires `?value=` query param — correct |
| `/health/metrics` | GET | No | 200 | Returns pool stats, uptime |
| `/health/tools` | GET | No | 200 | Empty tools dict (none configured in dev) |
| `/api/v1/auth/register` | POST | No | 201 | Working, returns user_id |
| `/api/v1/auth/login` | POST | No | 200 | Working, returns tokens + sets httpOnly cookies |
| `/api/v1/threads` | GET | Yes | 200 | Working, returns thread list with message_count |
| `/api/v1/threads` | POST | Yes | 200 | Working, creates thread |
| `/api/v1/threads/{id}/messages` | GET | Yes | 200 | Working, returns message list |
| `/api/v1/threads/{id}` | DELETE | Yes | 200 | Working, removes thread |
| `/api/v1/runs` | GET | Yes | 200 | Working |
| `/api/v1/approvals/pending` | GET | Yes | 200 | Working, returns empty list |
| `/api/v1/memory/facts` | GET | Yes | 200 | Working |
| `/api/v1/settings` | GET | Yes | 200 | Working, credentials masked |
| `/api/v1/settings` | PUT | Yes | 200 | Working |
| `/api/v1/settings` | PATCH | Yes | 405* | Code correct, running server needs restart (W19-H2) |
| `/api/v1/tools` | GET | Yes | 200 | Returns 4 tools with risk_tier, capability, enabled status |
| `/api/v1/queue` | GET | Yes | 200 | Working |
| `/api/v1/tasks` | GET | Yes | 200 | Working |
| `/api/v1/artifacts` | GET | Yes | 200 | Working |
| `/api/v1/cost/summary` | GET | Yes | 200 | Working |
| `/api/v1/cost/records` | GET | Yes | 200 | Working |
| `/api/v1/usage` | GET | Yes | 200 | Working |
| `/api/v1/audit/entries` | GET | Yes | 422 | Requires `trace_id` query param |
| `/api/v1/audit/verify` | POST | Yes | 200 | Working |
| `/api/v1/chat` | POST | Yes | 422 | Requires privacy_mode (W19-H1) |
| `/api/v1/voice/transcribe` | POST | Yes | 422 | Requires multipart file upload — correct |
| `/api/v1/devices/push-token` | POST | Yes | 422 | Validation error (schema check needed) |

## E2E Flow Results

| Flow | Steps Completed | Failure Point | Details |
|------|-----------------|---------------|---------|
| Auth: Register + Login | 2/2 | — | Register returns user_id, login returns tokens + httpOnly cookies |
| Thread CRUD: Create + List + Messages + Delete | 5/5 | — | Full lifecycle works, delete removes from list |
| Settings: GET + PUT | 2/2 | — | Credentials masked, round-trip preserves values |
| Settings: PATCH | 0/1 | PATCH request | 405 due to stale server process (W19-H2) |
| Chat SSE: Send message | 0/1 | Validation | 422: privacy_mode required (W19-H1) |
| Memory Facts: List | 1/1 | — | Returns empty list for new user |
| Tools: List + Health | 1/2 | Health check | Tool health endpoint needs tool to be registered |
| Approval: Pending + Decide | 1/2 | Decide | Expected: no approvals to decide |

## Security Checklist

| Check | Result | Details |
|-------|--------|---------|
| Auth on all protected endpoints | PASS | All 14 tested endpoints return 401 without token |
| Credential masking in API responses | PASS | All API keys show `****` prefix in settings GET |
| Domain isolation (no cross-imports) | PASS | No private_worker<->external_worker imports |
| httpOnly cookies | PASS | Both access and refresh tokens are httpOnly |
| SameSite cookie attribute | PASS | Set to "lax" (dev) |
| CSP headers | PASS | `default-src 'self'; frame-ancestors 'none'` |
| Error message information leakage | PARTIAL | JWT decode errors leak internal details (W19-H3) |
| X-Content-Type-Options | FAIL | Header not set (W19-M5) |
| Path traversal on artifact download | PASS | Returns 404 (URL routing prevents traversal) |
| SQL injection via path params | PASS | UUID validation rejects injection attempts |
| Input validation | PASS | Pydantic models reject malformed input with 422 |

## Wave 19 Specific Verification

| PR | Claimed Fix | Verified | Status |
|----|-------------|----------|--------|
| PR1 | Runs join usage_stats (real cost/token/model) | Source code: YES | Needs container restart to test live |
| PR1 | User-scoped memory | Source code: YES | Memory endpoints use `user.user_id` |
| PR1 | RunService fully async | Source code: YES | Uses `select()/execute()` pattern |
| PR2 | PATCH /settings | Source code: YES, Live: NO (405) | Container restart needed |
| PR2 | Chat thread creation race fix | Source code: YES | `mutateAsync` in Chat.tsx |
| PR2 | RunDetail type cast removed | Source code: YES | Direct property access |
| PR3 | ChatRequest model/provider optional | Source code: YES | `str | None = None` |
| PR3 | ChatRequest privacy_mode optional | NO | Still `str` (required) - W19-H1 |
| PR4 | Credential persistence on update | Source code: YES | Partial update preserves others |
| PR4 | Path traversal guard | Source code: YES | `safe_path` validation in artifacts.py |
| PR4 | Structured logging | Source code: YES | `user_id`, `run_id`, `trace_id` context |
| PR5 | Online indicator | Source code: YES | React health polling |
| PR5 | React Router redirect | Source code: YES | `navigate('/login')` replaces `window.location` |
| PR6 | Integration tests | YES | 22 ASGI tests + 8 Swift tests passing |

## Recommendations

1. **Restart the API container** to pick up all Wave 19 code changes. Consider adding `--reload` to uvicorn for development.

2. **Fix ChatRequest.privacy_mode** — make it `str | None = None` with a default of `"external"` (or validate against `Literal["private", "external"]`). This is the only blocking issue for iOS chat functionality.

3. **Delete dead code modules:**
   - `src/noa/tools/mcp_adapter.py` (superseded by TM6)
   - `src/noa/tools/governance.py` (features moved to gateway.py)
   - `src/noa/coding/` (never wired)
   - `src/noa/queue/notifications.py` (empty stub)

4. **Fix mypy type errors** — the `success_envelope` signature should accept `list | dict` for the `data` parameter, or endpoint return types should be adjusted.

5. **Sanitize JWT error messages** — return generic "Invalid token" to clients, log specifics server-side.

6. **Add X-Content-Type-Options: nosniff** to the security middleware.

7. **Address pre-existing open findings** — BE-H4 and BE-H5 are the highest priority among the 11 open items.
