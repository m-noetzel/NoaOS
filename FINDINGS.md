# NoaOS Project Audit — Findings

**Audit date:** 2026-03-07
**Scope:** Full codebase review (backend, frontend, Docker, DB, orchestrator, workers, tools)

> Previous findings from the user are incorporated and expanded below.

---

## Executive Summary

The project has a well-thought-out architecture (dual-domain isolation, policy engine, audit hash chain) and solid planning artifacts. However, the implementation has significant gaps between what the models/spec describe and what actually runs. Several subsystems are skeleton-only (workers, approvals, artifact storage). The code that does exist has critical issues around async/sync mixing, domain isolation violations, missing database indexes, and security weaknesses in token handling and input validation.

**Verdict:** The project is not production-ready. It needs focused work on making the existing code correct before adding new features.

---

## Table of Contents

1. [Critical — Must Fix Before Any Deployment](#1-critical)
2. [High — Fix Before Beta](#2-high)
3. [Medium — Fix Before Production](#3-medium)
4. [Architecture & Design Issues](#4-architecture)
5. [Incomplete / Skeleton-Only Subsystems](#5-incomplete)
6. [User-Reported Issues (Status)](#6-user-reported)

---

## 1. Critical

### C1. Async/Sync Mismatch in Tool Dispatch (Runtime Crash)

**Files:** `src/noa/orchestrator/nodes/tools.py:133-143`, `:186-200`

`_dispatch_registry()` and `_dispatch_gateway()` call `loop.run_in_executor()` but **never await the result**. The return value is a `Future` object, not a dict. Downstream code that calls `.get("error")` on these results will crash with `AttributeError`.

Additionally, `asyncio.run()` inside a thread while another loop is running creates nested event loops, which is fragile and can raise `RuntimeError` depending on the Python version.

```python
# Current (broken):
result: dict[str, Any] = loop.run_in_executor(pool, lambda: asyncio.run(...))
return result  # Returns Future, not dict!

# Correct: make tool_node async and await, or use synchronous dispatch
```

**Impact:** Any tool call through registry/gateway will fail at runtime.

---

### C2. Domain Isolation Violation — External Worker Imports Private Worker

**File:** `src/noa/external_worker/llm/router.py:114-119`

The `ProviderRouter.from_settings()` directly imports and instantiates `OllamaClient` from `noa.private_worker.ollama_client`. This breaks the SPEC.md dual-domain separation — the external worker package should have zero imports from the private worker package.

```python
from noa.private_worker.ollama_client import OllamaClient  # VIOLATION
```

**Same pattern:** `src/noa/tools/memory.py:16` imports `MAX_N_RESULTS` from `noa.private_worker.rpc`.

**Fix:** Move `OllamaClient` to a shared `noa.llm.providers` module. Move `MAX_N_RESULTS` to `noa.constants` or a shared contract module.

---

### C3. Audit Hash Chain Race Condition

**File:** `src/noa/audit/service.py:52-62` (sync), `:116-130` (async)

Both `create_entry()` and `create_entry_async()` compute the previous hash by querying the latest entry, then insert a new entry. Under concurrent load, two entries can read the same "latest" and both chain from it, **permanently breaking the hash chain**.

**Fix:** Use `SELECT ... FOR UPDATE` (pessimistic locking) or an advisory lock when creating audit entries.

---

### C4. Schema Drift — Model vs Migration Mismatch

Two columns exist in ORM models but are **missing from migrations**:

| Model Field | File | Migration Status |
|---|---|---|
| `Approval.domain` | `db/models/approval.py:29` | Missing from `001_initial_schema.py` |
| `UsageStats.task_id` | `db/models/usage.py:36` | Missing from `001_initial_schema.py` |

**Impact:** ORM `INSERT` statements referencing these columns will fail against the actual database schema. New migration (005) needed.

---

### C5. JWT Secret Key Falls Back to Empty String

**File:** `src/noa/auth/middleware.py:33`

```python
secret = settings.secret_key or ""
```

If `secret_key` is `None` (no env var set, non-production), JWT tokens are signed with an empty string. Any attacker can forge valid tokens by signing with `""`.

**Fix:** Refuse to start if `secret_key` is unset. Remove the `or ""` fallback entirely.

---

### C6. Token Storage in localStorage (XSS-Vulnerable)

**Files:** `web/src/auth/tokens.ts`, `web/src/api/client.ts`

Access tokens and refresh tokens are stored in `localStorage`. Any XSS vulnerability (compromised dependency, injected script) can exfiltrate both tokens, giving full account access.

**Fix:** Store tokens in httpOnly, Secure, SameSite=Strict cookies. Use a CSRF token for state-changing requests.

---

## 2. High

### H1. Workers Are Skeleton-Only — No Actual Endpoints

**Files:** `src/noa/external_worker/app.py`, `src/noa/private_worker/app.py`

Both worker apps only have `/health` endpoints. The external worker has no `/v1/complete` for LLM routing. The private worker has no `/rpc` endpoint for memory/DLP. All handler code, RPC schemas, and Ollama client exist but are **not wired into any FastAPI routes**.

**Impact:** The entire dual-domain architecture exists in code but is not functional. LLM calls go through `ProviderRouter` inside the API process, bypassing container isolation entirely.

---

### H2. No Database Indexes (Performance Cliff)

**File:** `alembic/versions/001_initial_schema.py`

Zero performance indexes are created. Critical missing indexes:

| Table | Column(s) | Used By |
|---|---|---|
| `audit_log` | `timestamp` | Retention purge, time-range queries |
| `audit_log` | `user_id` | Per-user audit queries |
| `audit_log` | `trace_id` | Trace correlation |
| `messages` | `thread_id` | Conversation loading |
| `run_events` | `run_id` | SSE event streaming |
| `usage_stats` | `(user_id, timestamp)` | Cost summaries |
| `task_queue` | `(status, queued_at)` | Queue polling |

**Impact:** All queries degrade to O(n) full table scans as data grows.

---

### H3. AuditService Instantiation Bypasses `__init__`

**File:** `src/noa/api/app.py:80`

```python
svc = AuditService.__new__(AuditService)
```

This creates an `AuditService` without calling `__init__`, leaving it in an undefined state. If `__init__` ever gains required initialization, this will silently break.

**Fix:** Properly instantiate `AuditService` or refactor the audit callback to not need a class instance.

---

### H4. Settings Repository Commits Inside Repository Layer

**File:** `src/noa/settings/repository.py:47-48`

```python
await self._session.flush()
await self._session.commit()
```

Repositories should never control transaction boundaries — that's the service layer's responsibility. This premature `commit()` makes it impossible to perform atomic multi-step operations that include settings updates.

**Fix:** Remove `commit()` from repository. Let the caller (service/endpoint) control the transaction.

---

### H5. Bare `except Exception: pass` Throughout Codebase

**Files:** `app.py:54,111,123,150`, `chat.py:107,156,159,206`, `cost.py:72,122`, `health.py:42,80`, and many more.

At least 15 locations silently swallow exceptions. This hides:
- Database connection failures
- Session initialization errors
- Authentication bypass conditions
- Data corruption

Each swallowed exception should be replaced with specific exception types, proper logging with trace_id, and appropriate error responses.

---

### H6. No Input Validation on Email Recipients

**File:** `src/noa/tools/gmail.py:100`

The `to` parameter in `send_email()` is passed directly to the Gmail API without any validation. A misbehaving LLM could:
- Send to arbitrary recipients
- Embed CC/BCC addresses
- Target internal network addresses

**Fix:** Parse and validate email format, reject multi-recipient injection, optionally whitelist domains.

---

### H7. Tool Capability Default is "Allow"

**File:** `src/noa/tools/capabilities.py:55-58`

Tools not present in the `TOOL_CAPABILITIES` dict default to **allowed**. This violates the principle of least privilege — any new tool is automatically permitted without explicit grant.

**Fix:** Change default to deny. Every tool must be explicitly added to the capabilities map.

---

### H8. Rate Limiting Is Process-Local and Per-Action (Not Per-User)

**Files:** `src/noa/auth/service.py:36-40`, `src/noa/tools/rate_limiter.py:42`

- Auth rate limiting uses an in-memory dict that resets on process restart
- Tool rate limiting tracks calls per action globally, not per user — one user hitting the limit blocks everyone
- Neither survives multi-process deployment

**Fix:** Use Redis or database-backed rate limiting, keyed by `(user_id, action)`.

---

### H9. Google AI Provider Missing Tool Call `id` Field

**File:** `src/noa/external_worker/llm/google_ai.py:119-126`

The Anthropic and OpenAI parsers extract `"id"` from tool calls. The Google AI parser omits it entirely. Downstream code (agent node, tool node) expects `id` for deduplication and result matching.

**Fix:** Generate a synthetic ID: `"id": uuid.uuid4().hex` for Google AI tool calls.

---

### H10. Notion HTML Sanitization Is Regex-Based and Incomplete

**File:** `src/noa/tools/notion.py:19-27`

Only `<script>` tags are stripped. Missing: `onerror`, `onload` event handlers, SVG-based XSS, data URIs, CSS injection vectors.

**Fix:** Use a proper HTML sanitization library (DOMPurify on frontend, bleach or similar on backend).

---

## 3. Medium

### M1. Idempotency Implementation Is Dead Code

**File:** `src/noa/api/middleware.py:21-41`

`extract_idempotency_key()` is defined per SPEC.md S25.4 but **never called**. No endpoint checks for duplicate requests. The memory tool generates a new UUID per call (`memory.py:74`), defeating idempotency entirely.

---

### M2. No CSRF Protection

**Files:** `src/noa/api/app.py:254-259`, `web/src/api/client.ts`

CORS allows `*` methods and `*` headers. No CSRF token is generated or validated. Write operations (POST, PUT, DELETE) are unprotected against cross-site request forgery.

---

### M3. Retention Scheduler Never Actually Purges

**File:** `src/noa/api/app.py:196-206`

The `_PurgeProxy` class always logs "purge skipped" and returns 0. The real `AuditService.purge_expired()` is sync-only but the app runs an async engine, so the proxy was added as a workaround. Result: audit logs grow forever.

**Fix:** Make `purge_expired()` async or run it via a background thread with a sync session.

---

### M4. No Content-Security-Policy Headers

The web frontend doesn't set CSP headers. This means inline scripts and external resource loading are unrestricted, weakening XSS mitigations.

---

### M5. SSE Reconnection Loses Events

**File:** `web/src/api/sse.ts:135-146`

On disconnect, the SSE client reconnects to the same endpoint but doesn't send `Last-Event-ID`. Events emitted during the disconnect window are lost. The backend has no event replay API.

---

### M6. Approval Expiry Never Enforced

**File:** `src/noa/policy/approval.py:77-92`

`expire_stale()` exists but is never called. Pending approvals persist forever.

---

### M7. Step-Up Auth Defined But Not Enforced

**File:** `src/noa/policy/engine.py:68-70`

`requires_step_up_auth()` returns `True` for high-risk actions but no code checks it. High-risk tool approvals don't require re-authentication.

---

### M8. Cost Endpoint Returns 200 on Database Error

**File:** `src/noa/api/v1/cost.py:72-74`

```python
except Exception:
    return success_envelope(data=[], trace_id=rid)  # HTTP 200!
```

Client cannot distinguish "no costs" from "database unreachable".

---

### M9. ContractViolationTracker Window Never Pruned

**File:** `src/noa/private_worker/rpc.py:206-249`

`violation_count` returns `len(self._violations)` (total ever) instead of filtering by the 24-hour window. After 3 violations total (not 3 within 24h), alerts trigger permanently.

---

### M10. Google Refresh Tokens Not Persisted

**File:** `src/noa/tools/google_auth.py:61-62`

Refresh tokens are stored in-memory only. Every API restart forces users to re-authenticate with Google.

---

### M11. Inconsistent User ID Extraction from JWT

**Files:** `chat.py:64`, `settings.py:48`, `cost.py:38-44`

Three different patterns for extracting user identity:
```python
user.get("user_id", user.get("sub", ""))  # chat.py — fallback to ""
uuid.UUID(user["sub"])                     # settings.py — KeyError if missing
user.get("user_id", user.get("sub", ""))  # cost.py — duplicate of chat.py
```

**Fix:** Create a typed `AuthUser` dataclass/TypedDict. Parse once in `require_auth`, pass structured object.

---

### M12. Mixed Sync/Async Service Layer

- `RunService` accepts sync `Session`
- `SettingsRepository` accepts `AsyncSession`
- `AuditService` has both sync and async methods

This inconsistency makes it unclear whether the app is sync-first or async-first and creates the sync-in-async antipattern seen in `chat.py:142-155`.

---

### M13. Backup Script Errors Silently Ignored

**File:** `src/noa/maintenance/backup.py:111`

`subprocess.run(..., check=False)` means backup failures produce no error. The full `os.environ` is also passed to the script, leaking all secrets.

---

### M14. No Frontend Request Timeouts

**File:** `web/src/api/client.ts`

`fetch()` calls have no `AbortController` timeout. If the backend hangs, the UI freezes indefinitely.

---

## 4. Architecture & Design Issues

### A1. Global Mutable State Instead of Dependency Injection

**Files:** `app_state.py` (6 module-level globals), `nodes/agent.py:20` (`_router`), `nodes/tools.py:20-23` (`_registry`, `_gateway`)

All major services are stored in module-level globals set at startup via `set_*()` functions. This makes testing hard (must set/reset globals), prevents parallel test execution, and creates implicit dependencies that aren't visible in function signatures.

**Proper pattern:** Use FastAPI's `app.state` or dependency injection throughout.

---

### A2. ProviderRouter Is Both Router and Factory

**File:** `src/noa/external_worker/llm/router.py:74-119`

`ProviderRouter.from_settings()` instantiates all 4 LLM clients internally. Adding a new provider requires modifying this method. Clients should be injected, not created inside the router.

---

### A3. Orchestrator State Not Fully Initialized

**File:** `src/noa/orchestrator/runner.py:95-106`

`initial_state` dict is missing `model_config` and `tool_rounds` fields that `AgentState` declares. The agent node reads `model_config` for per-node model routing (MR8 feature), which silently doesn't work because the field is never set.

---

### A4. Checkpointer Is an Empty Stub

**File:** `src/noa/orchestrator/checkpointer.py`

Contains only a docstring. No run state persistence exists. If the orchestrator crashes mid-run, all state is lost. SPEC.md S10.1 (persistent state backed by Postgres) is unfulfilled.

---

### A5. No Transaction Abstraction

Services manually call `flush()` and sometimes `commit()` with no consistent pattern. There's no `@transactional` decorator or unit-of-work pattern. Easy to forget to flush, and impossible to compose multiple service calls atomically.

---

## 5. Incomplete / Skeleton-Only Subsystems

These subsystems have code structure but are not functional end-to-end:

| Subsystem | Status | What's Missing |
|---|---|---|
| **External Worker** | Skeleton | No LLM endpoint; only `/health` |
| **Private Worker** | Skeleton | No RPC endpoint; handlers exist but aren't wired to routes |
| **Artifact Storage** | Stub | Download endpoint always returns 404; no storage backend |
| **Approval Workflow** | Stub | List endpoint always returns `[]`; no approval creation or decision flow |
| **Idempotency** | Dead code | Key extraction exists but is never called |
| **Checkpointer** | Empty file | No state persistence for orchestrator runs |
| **MCP Adapter** | Stub | `execute()` raises `NotImplementedError` |
| **Step-Up Auth** | Dead code | Policy checks exist but nothing enforces them |
| **Audit Log Queries** | Missing | Retention purges exist but no read API for users |
| **Cost Tracking** | Partial | Usage recording works; display endpoint has DB error masking |

---

## 6. User-Reported Issues (Status)

| Original Finding | Root Cause | Status |
|---|---|---|
| "Settings lässt sich nicht permanent speichern" | `SettingsRepository.upsert()` commits correctly, but the API endpoint doesn't propagate errors from DB failures (bare `except`). Also, API keys are stored in DB but env vars take priority (`service.py:78-83`), so DB-stored keys may appear overridden. | **Confirmed** — needs error surfacing + UX clarity |
| "Cost tracking missing" | `_record_usage()` in `chat.py` persists to `usage_stats`, and `cost.py` queries it. But `cost.py:72` swallows DB errors and returns empty `data=[]`, making it appear broken. Also, `task_id` column missing from migration causes insert failures. | **Confirmed** — schema drift (C4) + error masking (M8) |
| "Chat run only a simulation" | The `OrchestratorRunner` invokes a real LangGraph graph, but the tool dispatch is broken (C1: returns `Future` not `dict`). Workers are skeletons (H1). The LLM call itself works if `ProviderRouter` has valid API keys. | **Confirmed** — tool calls crash, workers not wired |
| "Wo in der app sehe ich verfügbare Tools?" | No UI component for listing available tools. The backend has `GET /api/v1/tools` endpoint but no frontend page consumes it. | **Confirmed** — frontend page missing |
| "Hardcoded `_DEV_SECRET`" | Production validator exists (`config.py:93-99`) but dev/test modes accept the default. Combined with C5 (empty string fallback), this is a security risk. | **Confirmed** — see C5 |

---

## Recommended Fix Order

**Phase 1 — Make it correct (stop the crashes):**
1. C1: Fix async tool dispatch (returns `Future` instead of result)
2. C4: Add migration 005 for missing columns (`domain`, `task_id`)
3. C5: Remove empty string JWT secret fallback
4. H5: Replace bare `except` blocks with specific error handling (at least in `chat.py`, `app.py`)
5. A3: Initialize all `AgentState` fields in runner

**Phase 2 — Make it secure:**
6. C6: Move tokens to httpOnly cookies + CSRF
7. C3: Add pessimistic locking for audit hash chain
8. H6: Validate email recipients
9. H7: Change tool capability default to deny
10. H10: Use proper HTML sanitization for Notion content

**Phase 3 — Make it functional:**
11. H1: Wire worker endpoints (private RPC, external LLM)
12. C2: Fix domain isolation (move shared code to shared modules)
13. H2: Add database indexes
14. M3: Fix retention purge (async implementation)
15. M11: Standardize user identity extraction

**Phase 4 — Make it robust:**
16. H4: Remove `commit()` from repository layer
17. A1: Migrate to proper dependency injection
18. M12: Unify sync/async service layer
19. A5: Add transaction context manager
20. Remaining medium issues

---

## 7. Frontend / UI Issues

### Overall Assessment

The frontend is a well-built React + TypeScript app with proper routing, auth flow, React Query for data fetching, and polished visual design. TypeScript compiles cleanly, build succeeds, and the component architecture is solid. However, there are several functional bugs, UX gaps, and a critical BASE_URL mismatch that will break SSE in development.

---

### UI-C1. SSE BASE_URL Differs From API Client BASE_URL (Broken in Dev)

**Files:** `web/src/api/client.ts:5` vs `web/src/api/sse.ts:4`

```typescript
// client.ts — correct for Vite proxy
const BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

// sse.ts — WRONG: bypasses Vite proxy, hits backend directly
const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
```

The API client defaults to `""` (relative path), letting the Vite proxy at `/api` forward to `http://localhost:8000`. But the SSE client defaults to `"http://localhost:8000"`, which makes SSE requests go **directly to the backend** instead of through the proxy. This causes:
- CORS failures in development (browser blocks cross-origin SSE)
- Auth header mismatch (proxy handles cookies/headers differently)
- The entire chat streaming feature is broken in dev mode

**Fix:** Change `sse.ts` BASE_URL default to `""` to match `client.ts`.

---

### UI-C2. Chat `currentRunId` Is Never Set From SSE Meta Event

**File:** `web/src/pages/Chat.tsx:59,133-147`

`currentRunId` is initialized as `null` (line 59) and the SSE `handleSSEEvent` callback never calls `setCurrentRunId()`. The SSE meta event contains `run_id` (backend sends it as the first event), but the handler doesn't extract it:

```typescript
// The meta event is processed in handleSSEEvent but run_id is never captured
case "token_stream":
  setStreamingContent((prev) => prev + (event.data.token as string));
  break;
// No case for "meta" to extract run_id!
```

**Impact:** `ActivityStream` receives `runId={currentRunId || undefined}` which is always `undefined`. Activity stream links to run details won't work. The SSE client internally captures `run_id` for reconnection (sse.ts:101-103) but never exposes it back to the Chat component.

**Fix:** Add a `"meta"` case in `handleSSEEvent` that calls `setCurrentRunId(event.data.run_id)`.

---

### UI-C3. Logout Does Not Clear React Query Cache

**File:** `web/src/auth/AuthContext.tsx:64-69`

```typescript
const logout = useCallback(() => {
  apiRequest("/api/v1/auth/logout", { method: "POST" }).catch(() => {});
  clearTokens();
  setIsAuthenticated(false);
  // Missing: queryClient.clear()
}, []);
```

When the user logs out, all cached API data (threads, messages, settings, runs, costs) remains in the React Query cache. If another user logs in on the same machine, they see the previous user's data until queries refetch.

**Fix:** Import `useQueryClient` and call `queryClient.clear()` on logout.

---

### UI-H1. Provider Dropdown Contains "google" — Types Only Allow "ollama" | "anthropic" | "openai"

**File:** `web/src/pages/Settings.tsx:88` vs `web/src/api/types.ts:49`

```typescript
// Settings.tsx
<SelectItem value="google">Google AI</SelectItem>

// types.ts
export type Provider = "ollama" | "anthropic" | "openai";
```

Selecting "Google AI" sets `provider` to `"google"`, which is not a valid `Provider` type. The backend's `ProviderRouter` uses `"google_ai"` as the provider key. This will cause the LLM call to fail silently or fall back to default.

**Fix:** Either add `"google_ai"` to the `Provider` type and use it in the dropdown, or change the backend to accept `"google"`.

---

### UI-H2. Model Dropdown Is Hardcoded and Doesn't Match Provider

**File:** `web/src/pages/Settings.tsx:100-108`

All models from all providers are shown in a single flat list regardless of which provider is selected. Selecting "OpenAI" provider + "Claude Sonnet 4" model creates an invalid combination that the backend will reject or ignore.

**Fix:** Filter the model dropdown based on the selected provider. Or fetch available models from a backend endpoint.

---

### UI-H3. Budget Inputs Accept Negative Numbers and Invalid Values

**File:** `web/src/pages/Settings.tsx:135,139`

```html
<Input type="number" value={dailyBudget} onChange={(e) => setDailyBudget(e.target.value)} />
```

No `min="0"` attribute. No validation that daily < monthly. User can set budget to `-100` or `NaN`. `parseFloat()` on empty string returns `NaN`, which gets sent to the backend.

**Fix:** Add `min="0"` and `step="0.01"`. Validate daily <= monthly before save.

---

### UI-H4. No Error Boundaries — API Failures Crash Entire Page

**File:** `web/src/App.tsx`

No `<ErrorBoundary>` wrapper around routes. If any React Query fetch throws an unhandled error during render, the entire page goes white with no recovery. React's default error behavior is to unmount the component tree.

**Fix:** Add a React error boundary at the `ProtectedRoute` level that shows a "Something went wrong" message with a retry button.

---

### UI-H5. Memory Delete Has No Confirmation Dialog

**File:** `web/src/pages/Memory.tsx:140,192`

Clicking the delete button immediately fires `deleteMutation.mutate(fact.id)` with no confirmation. A single misclick permanently deletes a memory fact.

**Fix:** Show an `AlertDialog` asking "Delete this fact?" before executing.

---

### UI-M1. Index Page Is a Placeholder

**File:** `web/src/App.tsx:51`

The `"/"` route renders `<Chat />`, which is correct. But `web/src/pages/Index.tsx` exists as an unused "Welcome to Your Blank App" placeholder that's never routed to. Dead code.

---

### UI-M2. No Pagination on Runs, Artifacts, Cost Records

**Files:** `web/src/pages/Runs.tsx`, `web/src/pages/Artifacts.tsx`, `web/src/pages/Cost.tsx`

All list pages fetch the complete dataset and render everything. With hundreds or thousands of items, this will cause:
- Slow initial load
- Browser memory pressure
- Unresponsive scrolling

**Fix:** Add cursor-based or offset pagination. Backend endpoints already accept `limit`/`offset` query params (but frontend doesn't use them).

---

### UI-M3. SSE Event Types Not Validated Before Processing

**File:** `web/src/api/sse.ts:107-114`

```typescript
const eventName = currentEvent || parsed.event_type || "unknown";
this.options.onEvent({
  event: eventName as SSEEventType,  // Unsafe type assertion
  data: parsed.payload ?? parsed,
});
```

The `as SSEEventType` cast provides no runtime validation. If the backend sends an unexpected event type (or a compromised response injects one), it passes through unchecked.

---

### UI-M4. Streaming Content Not Added to Message History

**File:** `web/src/pages/Chat.tsx:133-147`

When `result_ready` fires, `streamingContent` is cleared (line 141) but the final assistant response is never added to the local message list. The user only sees it after `messagesRes` refetches (triggered by staleTime expiry or manual navigation). There's a visible "flash" where the streamed text disappears momentarily.

**Fix:** On `result_ready`, invalidate the messages query immediately, or append the assistant message to local state.

---

### UI-M5. Thread Names Are Always "New Thread"

**File:** `web/src/pages/Chat.tsx:90`

```typescript
body: JSON.stringify({ title: "New Thread" }),
```

Every new thread is named "New Thread". No prompt for a name, and no auto-naming based on the first message content.

**Fix:** Either prompt for a title, or auto-generate from the first message (e.g., "Budget review" from "Can you review my budget?").

---

### UI-M6. No Tools Page in Navigation

**File:** `web/src/components/layout/AppSidebar.tsx:25-33`

The sidebar has no link to a "Tools" page. The backend has a `GET /api/v1/tools` endpoint to list available tools and their capabilities, but there's no frontend page to display or manage them. This was one of the user's original findings: "Wo in der app sehe ich verfügbare Tools?"

**Fix:** Add a Tools page that fetches from `/api/v1/tools` and shows tool name, description, risk tier, and enabled/disabled status.

---

### UI-M7. Cost Charts Have No Loading or Empty States

**File:** `web/src/pages/Cost.tsx:85-93,102-112`

When data is loading, the chart areas are blank (no skeleton, no spinner). When there's no cost data, the charts render with zero data points and empty axes instead of showing "No cost data yet".

---

### UI-M8. Settings Changes Don't Immediately Affect Chat

**File:** `web/src/pages/Chat.tsx:77-84`

Settings are loaded once into Chat's local state. If the user changes settings (model, provider, privacy mode) in the Settings page and navigates back to Chat, the old values persist until the next React Query refetch (30s staleTime). The Chat state is initialized from the query result only on first mount.

**Fix:** Use the settings query data directly instead of copying to local state, or invalidate the cache on navigation.

---

### UI-M9. No Notification Badges on Sidebar

**File:** `web/src/components/layout/AppSidebar.tsx`

The sidebar shows no count badges for pending approvals, active queue items, or unread activity. The user must visit each page to discover pending work.

**Fix:** Fetch counts from `/api/v1/approvals/pending` and `/api/v1/queue` and display badges on sidebar items.

---

### UI-M10. JS Bundle Is 965 KB (No Code Splitting)

**Build output:** Single chunk of 965 KB (278 KB gzipped).

All pages and all UI components are in one bundle. The `recharts` library alone is ~300 KB. Pages like Cost (with charts) and RunDetail (with graph visualization) should be lazy-loaded.

**Fix:** Use `React.lazy()` + `Suspense` for route-level code splitting. Move heavy dependencies (recharts, run graph) into separate chunks.
