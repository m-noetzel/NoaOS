# NoaOS Project Audit — Findings

**Audit date:** 2026-03-07
**Scope:** Full codebase review (backend, frontend, Docker, DB, orchestrator, workers, tools)

> Previous findings from the user are incorporated and expanded below.

---

## Tracking Summary

| ID | Severity | Title | Status | Resolved By |
|----|----------|-------|--------|-------------|
| C1 | Critical | Async/Sync Mismatch in Tool Dispatch | **Resolved** | QC1 |
| C2 | Critical | Domain Isolation Violation — External→Private Import | **Resolved** | QC4 |
| C3 | Critical | Audit Hash Chain Race Condition | **Resolved** | QC2 |
| C4 | Critical | Schema Drift — Model vs Migration Mismatch | **Resolved** | QC1 |
| C5 | Critical | JWT Secret Key Falls Back to Empty String | **Resolved** | QC1 |
| C6 | Critical | Token Storage in localStorage (XSS-Vulnerable) | **Resolved** | QC2 |
| H1 | High | Workers Are Skeleton-Only — No Actual Endpoints | **Resolved** | QC4 |
| H2 | High | No Database Indexes (Performance Cliff) | **Resolved** | QC5 |
| H3 | High | AuditService Instantiation Bypasses `__init__` | **Resolved** | QC1 |
| H4 | High | Settings Repository Commits Inside Repository Layer | **Resolved** | QC3 |
| H5 | High | Bare `except Exception: pass` Throughout Codebase | **Resolved** | QC3 |
| H6 | High | No Input Validation on Email Recipients | **Resolved** | QC2 |
| H7 | High | Tool Capability Default is "Allow" | **Resolved** | QC2 |
| H8 | High | Rate Limiting Is Process-Local and Per-Action | **Resolved** | QC8 + HD (per-user in ToolGateway dispatch; GovernanceWrapper is unused dead code) |
| H9 | High | Google AI Provider Missing Tool Call `id` Field | **Resolved** | QC4 |
| H10 | High | Notion HTML Sanitization Is Regex-Based | **Resolved** | QC2 |
| M1 | Medium | Idempotency Implementation Is Dead Code | **Resolved** | QC8 |
| M2 | Medium | No CSRF Protection | **Resolved** | QC2 |
| M3 | Medium | Retention Scheduler Never Actually Purges | **Resolved** | QC5 |
| M4 | Medium | No Content-Security-Policy Headers | **Resolved** | QC2 |
| M5 | Medium | SSE Reconnection Loses Events | **Resolved** | QC8 + HD (replay queries run_events with user_id auth filter) |
| M6 | Medium | Approval Expiry Never Enforced | **Resolved** | QC5 |
| M7 | Medium | Step-Up Auth Defined But Not Enforced | **Resolved** | QC8 |
| M8 | Medium | Cost Endpoint Returns 200 on Database Error | **Resolved** | QC3 |
| M9 | Medium | ContractViolationTracker Window Never Pruned | **Resolved** | QC5 |
| M10 | Medium | Google Refresh Tokens Not Persisted | **Resolved** | QC8 + HD (Fernet-encrypted tokens in google_credentials table) |
| M11 | Medium | Inconsistent User ID Extraction from JWT | **Resolved** | QC3 |
| M12 | Medium | Mixed Sync/Async Service Layer | **Resolved** | QC5 |
| M13 | Medium | Backup Script Errors Silently Ignored | **Resolved** | QC3 |
| M14 | Medium | No Frontend Request Timeouts | **Resolved** | QC8 |
| A1 | Arch | Global Mutable State Instead of DI | **Resolved** | QC8 + HD (app.state-backed DI with module fallback) |
| A2 | Arch | ProviderRouter Is Both Router and Factory | **Resolved** | QC8 |
| A3 | Arch | Orchestrator State Not Fully Initialized | **Resolved** | QC1 |
| A4 | Arch | Checkpointer Is an Empty Stub | **Resolved** | QC8 + HD (PostgresCheckpointer with save/load called in runner.run()) |
| A5 | Arch | No Transaction Abstraction | **Resolved** | QC8 |
| UI-C1 | Critical | SSE BASE_URL Differs From API Client | **Resolved** | QC6 |
| UI-C2 | Critical | Chat `currentRunId` Never Set From SSE | **Resolved** | QC6 |
| UI-C3 | Critical | Logout Does Not Clear React Query Cache | **Resolved** | QC6 |
| UI-H1 | High | Provider Dropdown Contains Invalid "google" | **Resolved** | QC6 |
| UI-H2 | High | Model Dropdown Is Hardcoded, Doesn't Match Provider | **Resolved** | QC6 |
| UI-H3 | High | Budget Inputs Accept Negative Numbers | **Resolved** | QC6 |
| UI-H4 | High | No Error Boundaries — API Failures Crash Page | **Resolved** | QC6 |
| UI-H5 | High | Memory Delete Has No Confirmation Dialog | **Resolved** | QC6 |
| UI-M1 | Medium | Index Page Is a Placeholder | **Resolved** | QC7 |
| UI-M2 | Medium | No Pagination on Runs, Artifacts, Cost Records | **Resolved** | QC7 |
| UI-M3 | Medium | SSE Event Types Not Validated Before Processing | **Resolved** | QC7 |
| UI-M4 | Medium | Streaming Content Not Added to Message History | **Resolved** | QC7 |
| UI-M5 | Medium | Thread Names Are Always "New Thread" | **Resolved** | QC7 |
| UI-M6 | Medium | No Tools Page in Navigation | **Resolved** | QC7 |
| UI-M7 | Medium | Cost Charts Have No Loading or Empty States | **Resolved** | QC7 |
| UI-M8 | Medium | Settings Changes Don't Immediately Affect Chat | **Resolved** | QC7 |
| UI-M9 | Medium | No Notification Badges on Sidebar | **Resolved** | QC7 |
| UI-M10 | Medium | JS Bundle Is 965 KB (No Code Splitting) | **Resolved** | QC7 |

| H11 | High | Replay Endpoint Missing User Authorization Filter | **Resolved** | HD (user_id filter via Run join) |
| M15 | Medium | HD Commit Breaks 3 Existing QC8 Tests | **Resolved** | HD (tests updated for new behavior) |

| iOS11-M1 | Medium | Approval Decide Endpoint Is a Stub (No DB Persistence) | **Resolved** | iOS11-fix |
| iOS11-M2 | Medium | Approval Decide Returns Hardcoded risk_tier="high" | **Resolved** | iOS11-fix |
| BE-C1 | Critical | Runs Endpoint Returns Hardcoded Zeros for Cost/Token/Model | **Resolved** | PR1 |
| BE-C2 | Critical | Memory Endpoints Not User-Scoped (Cross-User Data Leak) | **Resolved** | PR1 |
| BE-H1 | High | Credential Store Is In-Memory Only (Lost on Restart) | **Resolved** | PR4 |
| BE-H2 | High | RunService Uses Sync ORM .query() on Async Session | **Resolved** | PR1 |
| BE-H3 | High | Settings Only Has PUT But PrivacyToggle Sends PATCH (405) | **Resolved** | PR2 |
| BE-M1 | Medium | Cost Endpoint Uses Raw SQL With Magic Column Indices | **Resolved** | Wave20-cleanup |
| BE-M2 | Medium | Memory Update Uses Private _persist() Method | **Resolved** | PR1 |
| BE-M3 | Medium | Artifact Download No Path Traversal Guard | **Resolved** | PR4 |
| BE-M4 | Medium | No Structured Logging Context (user_id, trace_id) in Exceptions | **Resolved** | PR4 |
| BE-M5 | Medium | MemoryStore.store() Saves Facts Without user_id (Write Path Not Scoped) | **Resolved** | Wave20-cleanup |
| BE-H4 | High | SSE Replay Cursor Uses List Index, Not Stable DB Offset (Reconnect Unreliable) | **Resolved** | Wave20-cleanup |
| BE-H5 | High | chat.py _update_run_status Raw UPDATE Bypasses RunService State Machine | **Resolved** | Wave20-cleanup |
| FE-C1 | Critical | PrivacyToggle Uses PATCH Method — Backend Returns 405 | **Resolved** | PR2 |
| FE-H1 | High | Chat Thread Creation Race — Message Sent Before Thread Exists | **Resolved** | PR2 |
| FE-H2 | High | RunDetail Uses Unsafe `as unknown as` Type Coercion | **Resolved** | PR2 |
| FE-M1 | Medium | TopBar "Online" Status Indicator Is Hardcoded (Never Reflects Real State) | **Resolved** | PR5 |
| FE-M2 | Medium | Session Expiry Hard-Redirects via window.location (Breaks React State) | **Resolved** | PR5 |
| FE-M3 | Medium | Artifact Download Bypasses Auth Headers | **Resolved** | PR5 |
| FE-M4 | Medium | CredentialModal Has No Empty-Value Validation | **Resolved** | PR5 |
| FE-M5 | Medium | No Unsaved-Changes Warning on Settings Page | **Resolved** | Wave20-cleanup |
| iOS-H1 | High | Offline Queue Never Drained on Network Restore | **Resolved** | PR3 |
| iOS-H2 | High | SSE Stream Not Cancelled on Thread Switch (Resource Leak) | **Resolved** | PR3 |
| iOS-H3 | High | AuthGuard Shows Login Without Attempting Token Refresh | **Resolved** | PR3 |
| iOS-H4 | High | ComposerBar Has No Provider/Model Selectors (Sends nil) | **Resolved** | PR3 |
| iOS-M1 | Medium | MainTabView ViewModels Created Without Lifecycle Cleanup | **Resolved** | PR5 |
| iOS-M2 | Medium | ChatView loadHistory Race on Rapid Thread Switching | **Resolved** | PR5 |
| iOS-M3 | Medium | Biometric Auth Failure Has No Recovery UI | **Resolved** | PR5 |
| iOS-M4 | Medium | Batch Deny Has No Confirmation Dialog | **Resolved** | PR5 |
| iOS-M5 | Medium | VoiceService Has No User-Facing Timeout/Cancel UI | **Resolved** | PR5 |
| iOS-L1 | Low | Environment.swift Hardcoded Dev IP (Crash if Unavailable) | **Resolved** | Wave20-cleanup |
| iOS-L2 | Low | DEBUG Builds Completely Disable Certificate Pinning | **Resolved** | QE3 |
| FE-L1 | Low | ErrorBoundary Renders error.stack to UI (Exposes Internals) | **Resolved** | Wave20-cleanup |
| W19-H1 | High | ChatRequest.privacy_mode Still Required (str, not optional); No Literal validation | **Resolved** | PR7 |
| W19-H3 | High | JWT Error Messages Leak Internal Details (Library Fingerprinting) | **Resolved** | PR7 |
| W19-M1 | Medium | Dead Code: mcp_adapter.py (superseded by TM6 mcp_remote.py) | **Resolved** | PR7 (retained: has active tests; not wired to running app) |
| W19-M2 | Medium | Dead Code: GovernanceWrapper in governance.py (never imported) | **Resolved** | PR7 (retained: has active tests; not wired to running app) |
| W19-M3 | Medium | Dead Code: noa.coding module (never wired into system) | **Resolved** | PR7 (deleted: no tests in Docker container) |
| W19-M4 | Medium | noa.queue.notifications is a no-op stub | **Resolved** | PR7 (retained: NotificationService has active tests in test_durable_queue.py) |
| W19-M5 | Medium | Missing X-Content-Type-Options: nosniff Security Header | **Resolved** | PR7 |
| W19-M6 | Medium | success_envelope signature only accepts dict, not list | **Resolved** | PR7 (data param: dict[str, Any] \| list[Any]) |

| W20-C1 | Critical | CI Pipeline Will Fail on First Push (ruff + mypy errors) | **Resolved** | Wave20-cleanup |
| W20-H1 | High | GOOGLE_REDIRECT_URI Not in docker-compose.yml (Production OAuth Broken) | **Resolved** | Wave20-cleanup |
| W20-H2 | High | Token Encryption Key Reads JWT_SECRET_KEY But Compose Passes JWT_SECRET | **Resolved** | Wave20-cleanup |
| W20-M1 | Medium | OAuth State Store Has No TTL (Memory Leak on Abandoned Flows) | **Resolved** | Wave20-cleanup |
| W20-M2 | Medium | noa-api Dockerfile Missing HEALTHCHECK Directive | **Resolved** | Wave20-cleanup |
| W20-MED-3 | Medium | Web-CI E2E step has continue-on-error: true (failures non-blocking) | **Resolved** | QE3 |
| W20-MED-4 | Medium | NotImplementedError stubs in tools.py and mcp_adapter.py lack clear intent docs | **Resolved** | QE3 |
| | | **── P0: Domain Isolation (Core Architecture) ──** | | |
| BE-C3 | Critical | Domain switch does not isolate data — chats, threads, and other state carry over between private and external domains | **Resolved** | FR1 |
| BE-H8 | High | Memory tool visible in external domain despite privacy_mode=private — domain isolation violated | **Resolved** | FR1 |
| BE-H11 | High | OpenAI selectable as provider in private domain — external-only providers must be hidden when in private mode | **Resolved** | FR1 |
| | | **── P1: Broken Core Features ──** | | |
| BE-H7 | High | Approved memory facts not persisted — Memory page shows 0 facts after approving a memory | **Resolved** | FR2 |
| BE-H10 | High | Private memory tool broken — health "Unconfigured", remember/recall functions disabled, switching to private mode doesn't fix it | **Resolved** | FR2 |
| BE-H6 | High | Memory facts lost on API restart — /data volume not mounted on noa-api container | **Resolved** | FR2 |
| BE-H9 | High | No memory store for external domain — agent has no long-term memory when running in external mode | **Resolved** | FR2 |
| BE-H12 | High | Logout not fully clearing session — user sometimes still logged in after restart despite logging out | **Resolved** | FR2 |
| W21-H1 | High | DELETE /threads returns 500 -- usage_stats FK missing ondelete CASCADE/SET NULL | **Resolved** | FR3 |
| UX-H1 | High | SSE connection fails on calendar tool calls (e.g. create event) | **Resolved** | FR4 |
| UX-H6 | High | Notion connected but agent can't read anything | **Resolved** | FR6 |
| UX-H7 | High | Cost dashboard values don't match — daily and monthly show identical $0.08 despite different token counts | **Resolved** | FR5 |
| iOS-H5 | High | Noa iOS app not connected to backend — cannot communicate with the API | **Resolved** | FR6 |
| W21-H2 | High | Backup container crash-looping -- setpgid permission denied from DE3 hardening | **Resolved** | FR3 |
| | | **── P2: Chat Experience ──** | | |
| UX-H9 | High | User message not shown immediately after sending — hidden until agent finishes responding | **Resolved** | FR4 |
| UX-H10 | High | No visible agent activity stream — tool selection, execution steps, and reasoning not shown during processing | **Resolved** | FR4 |
| UX-H5 | High | Tool call details in chat don't show exact data (e.g. Tavily results missing) | **Resolved** | FR4 |
| UX-M3 | Medium | No rename option for thread names in sidebar — user cannot edit thread titles | **Resolved** | FR6 |
| UX-H2 | High | Send button disabled when text field is empty — should always be enabled | **Resolved** | FR4 |
| | | **── P3: Cost & Governance ──** | | |
| UX-H8 | High | No settings UI for per-provider pricing — only default model priced, other providers show no cost | **Resolved** | FR5 |
| UX-H11 | High | Budget limits from Settings not displayed on Cost dashboard — no progress bar, threshold, or warning against configured limits | **Resolved** | FR5 |
| UX-M1 | Medium | Costs not shown anywhere in the UI (runs, chat, dashboard) | **Resolved** | FR5 |
| UX-M7 | Medium | Cost dashboard missing breakdown by process (run/task) and by tool — only shows model and provider | **Resolved** | FR5 |
| UX-H4 | High | Runs page nearly empty — tool calls, costs, and details not displayed | **Resolved** | FR5 |
| UX-M4 | Medium | No settings for agent execution limits — missing max tool calls per task, max retries, timeout, and other governance parameters | **Resolved** | FR6 |
| | | **── P4: Tools Management ──** | | |
| UX-M8 | Medium | Tools page needs "All / Usable" toggle to switch between showing all tools vs only currently available ones | **Resolved** | FR6 |
| UX-M9 | Medium | Tools page missing search/filter function | **Resolved** | FR6 |
| UX-M10 | Medium | No setting to enable/disable specific tools per process scope (email writing, research, scheduling, etc.) | **Resolved** | FR6 |
| | | **── P5: Missing Pages & Features ──** | | |
| UX-M2 | Medium | No "human-in-the-loop" / approvals toggle in Settings UI | **Resolved** | FR6 |
| UX-M5 | Medium | Artifacts page completely empty — no artifacts displayed even after agent runs | **Resolved** | FR5 |
| UX-M6 | Medium | Queue page completely empty — no queued tasks shown | **Resolved** | FR5 |
| UX-H3 | High | System prompt not stored in repo `prompts/` dir; no save button in UI | **Resolved** | FR4 |
| | | **── P6: Low / DevOps ──** | | |
| W21-M1 | Medium | /docs and /openapi.json exposed unconditionally (no env gating) | **Resolved** | FR3 |
| W21-M2 | Medium | traceability.py --check overwrites manual TRACEABILITY.md sections | **Resolved** | FR3 |
| UX-L1 | Low | Noa logo/icon in top-left squeezes awkwardly when sidebar toggles — should maintain fixed size | **Resolved** | FR6 |
| FR3-L1 | Low | Migration chain not tested — test suite uses create_all, so a broken down_revision reference (e.g. referencing a migration added by a concurrent branch) never surfaces in tests. Discovered: migration 015 (FR3) references down_revision="014" but 014 was missing from the FR3 worktree; alembic history crashed with KeyError. | **Resolved** | MVP-fixes |
| FR6-L1 | Low | Scope overrides (`_scope_overrides` in `src/noa/api/v1/tools.py`) are in-memory only — lost on server restart. User scope configurations (PATCH /tools/scopes/{scope_name}) are not persisted to DB. A future phase should persist to a JSON column on UserSettings or a separate table. | **Resolved** | MVP-fixes |
| W22-H1 | High | Agent limit settings are dead-end stores — `max_tool_calls`, `max_retries`, `timeout_seconds` are stored in DB and served by the settings API but the orchestrator never reads them. Users configure execution limits that the agent ignores entirely. Violates "no dead-end stores" rule. | **Resolved** | MVP-fixes |
| W22-H2 | High | `approvals_enabled` toggle is a dead-end store — stored in settings, served by API, but neither the policy engine nor the orchestrator checks it. Toggling "Human-in-the-loop approvals" off in the UI has no effect on approval flow execution. | **Resolved** | MVP-fixes |
| W22-M1 | Medium | Runs and Cost endpoints not filtered by domain — `/api/v1/runs` and `/api/v1/cost/*` show data from all domains regardless of active privacy mode. FR1 isolated threads/messages by domain but did not extend the pattern to runs and cost records. | **Resolved** | MVP-fixes |
| W22-M2 | Medium | No Pydantic validation constraints on agent limit fields — `max_tool_calls`, `max_retries`, `timeout_seconds` accept negative values (e.g. `max_tool_calls=-99`) without error. `Field(ge=1)` / `Field(ge=0, le=...)` constraints missing from `UpdateSettingsRequest`. | **Resolved** | MVP-fixes |
| MVP-M1 | Medium | QueueDrainWorker is a semantic dead-end — drain worker marks queued private.chat tasks as "processing" but never calls the runner to actually dispatch them. Tasks queued when private domain is unavailable are permanently stuck in "processing" state and never executed. The user-facing "queued" SSE message is not fulfilled. Phase 2 deferred per source docstring. | **Resolved** | MVP-fixes-2 |
| MVP-M2 | Medium | Queued chat path creates no Run/Conversation DB rows — when privacy_mode=private and private domain unavailable, the queue path skips `_make_run_service()`. No Run row, no Conversation row created. Queued requests are invisible on the Runs page. Phase 2 dispatch implementation will need to create these rows from the queue payload. | **Resolved** | MVP-fixes-2 |
| MVP-L1 | Low | enable_tool endpoint accepts function-level capability keys — TOOL_CAPABILITIES now includes auto-generated keys like `memory__remember`. POST /tools/memory__remember/enable returns 200 with a no-op DB grant (tool_name='memory__remember' never matched by has_capability which checks tool_name='memory'). Confusing but not a security issue. | **Resolved** | MVP-fixes-2 |
| MVP-L2 | Low | Queued SSE stream missing meta event — the normal chat path emits a `meta` event (with run_id, thread_id) as the first SSE frame. The queued path emits `queued` directly without a preceding `meta`. Clients relying on `meta` for run_id tracking may miss it. | **Resolved** | MVP-fixes-2 |
| MVP-L3 | Low | QueueDrainWorker task stuck in "processing" on crash — DurableQueue.poll() only returns status="queued" tasks. If the API container crashes between the first session.commit() (status→"processing") and completion of _dispatch_task, the task is permanently stuck. Manual DB intervention required to recover. No timeout recovery exists for "processing" state. | **Resolved** | MVP-fixes-3 |
| AUTH-H1 | High | `apiRequest` 401-handler fires on login endpoint — credential failures shown as "Session expired" | Open | — |
| AUTH-H2 | High | Auth state split between httpOnly cookies and localStorage flag can desync — startup shows "Session expired" without user action | Open | — |
| AUTH-M1 | Medium | In-memory auth rate limiting (H8) marked resolved in QC8 but never actually migrated — class-level dict still in `service.py` | Open | — |
| AUTH-M2 | Medium | No session validity check on app startup — `isAuthenticated` initialised from localStorage flag without verifying cookies are live | Open | — |

**Open:** 6 | **Partially Resolved:** 0 | **Resolved:** 159 | **Total:** 165

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

### H11. Replay Endpoint Missing User Authorization Filter

**File:** `src/noa/api/v1/runs.py:100-106`

The `replay_run_events` endpoint requires authentication via `require_auth` but does not filter the query by `user_id`. The query `select(RunEvent).where(RunEvent.run_id == run_id)` returns all events for the given run regardless of who owns it. Any authenticated user can read any other user's run events by providing a valid (or guessed) `run_id`.

**Impact:** Information disclosure — run event payloads may contain conversation content, tool call arguments, and tool results.

**Fix:** Join through the `runs` table and add `.where(Run.user_id == user_id)` to verify the authenticated user owns the run.

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

### M15. HD Commit Breaks 3 Existing QC8 Tests

**Commit:** 9c5a873

Three pre-existing QC8 tests fail after the hardening commit:

1. `TestA4NoOpCheckpointer::test_noop_checkpointer_raises_not_implemented` — NoOpCheckpointer was changed from raising `NotImplementedError` to silently returning (no-op), but the test was not updated.
2. `TestM5SSEReplay::test_replay_endpoint_returns_events_after_id` — `replay_run_events` now requires a `db` parameter (Depends injection) that the test does not provide.
3. `TestM5SSEReplay::test_replay_endpoint_returns_empty_for_unknown_event` — Same `db` parameter issue.

**Fix:** Update the 3 tests to match the new behavior: mock the DB session for replay tests, and change the NoOpCheckpointer test to assert no-raise behavior.

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

---

## 10. Production Readiness Audit (2026-03-11)

Full-stack audit by new tech lead. Focus: real user flows, broken data paths, production blockers.

### Backend Critical & High

#### BE-C1. Runs Endpoint Returns Hardcoded Zeros for Cost/Token/Model

**Files:** `src/noa/api/v1/runs.py:48-53,87-92`

Both `list_runs` and `get_run` return hardcoded empty strings and zeros for `model`, `provider`, `tokens_in`, `tokens_out`, `cost_usd`, `duration_ms`. The Run ORM model doesn't have these fields — they should be joined from `usage_stats`.

**Impact:** Users see $0.00 cost for all runs. Run detail page shows no model/provider info. Cost data IS recorded in `usage_stats` but never surfaced through runs.

#### BE-C2. Memory Endpoints Not User-Scoped (Cross-User Data Leak)

**File:** `src/noa/api/v1/memory.py:30-41`

`store.list_all()` returns ALL facts for ALL users. The `AuthUser` is extracted but never used for filtering. Same issue in approve, update, and delete — no ownership check.

**Impact:** Privacy violation. User A sees User B's memory facts. Any authenticated user can modify/delete any fact.

#### BE-H1. Credential Store Is In-Memory Only

**File:** `src/noa/api/v1/tools.py:32-34`

`_credential_store: dict[tuple[str, str], dict[str, str]] = {}` with TODO comment. All API keys entered by users are lost on container restart.

#### BE-H2. RunService Uses Sync ORM .query() on Async Session

**File:** `src/noa/runs/service.py:51-70`

`RunService.get_run()`, `list_runs()`, `update_status()` all use `self._session.query(Run)` — the legacy sync ORM interface. When called with an AsyncSession, this raises errors. The runs API endpoint (runs.py) does its own async queries, but the chat pipeline that creates/updates runs via RunService may fail.

#### BE-H3. Settings Only Has PUT, PrivacyToggle Sends PATCH

**Files:** `src/noa/api/v1/settings.py:52` (only `@router.put("")`), `web/src/components/shared/PrivacyToggle.tsx:21` (sends `PATCH`)

The privacy mode toggle in the TopBar sends a PATCH request, but the backend only defines a PUT handler. Result: 405 Method Not Allowed. The privacy toggle silently fails.

### Backend Medium

#### BE-M1. Cost Endpoint Uses Raw SQL With Magic Column Indices

**File:** `src/noa/api/v1/cost.py:56-76`

Uses `text("SELECT COALESCE(SUM(...))...")` with `row[1]`, `row[2]` index access. Fragile — any column reorder breaks silently.

#### BE-M2. Memory Update Uses Private _persist() Method

**File:** `src/noa/api/v1/memory.py:91`

`store._persist(str(fact_id))` with `# noqa: SLF001` suppression. Breaks encapsulation, blocks future storage migration.

#### BE-M3. Artifact Download No Path Traversal Guard

**File:** `src/noa/api/v1/artifacts.py:60-90`

`Path(artifact.storage_ref)` from DB is served via `FileResponse` without verifying it's within the allowed artifact directory. Could serve arbitrary files if `storage_ref` is manipulated.

#### BE-M4. No Structured Logging Context in Exception Handlers

Multiple files log exceptions without `user_id` or `trace_id`, making production debugging very difficult.

### Frontend Critical & High

#### FE-C1. PrivacyToggle Uses PATCH Method — Backend Returns 405

**File:** `web/src/components/shared/PrivacyToggle.tsx:21`

Sends `method: "PATCH"` but backend settings endpoint only supports PUT. The optimistic UI update makes it LOOK like it worked (icon flips), but the onSettled refetch reverts it. User thinks privacy mode changed but it didn't.

#### FE-H1. Chat Thread Creation Race — Message Sent Before Thread Exists

**File:** `web/src/pages/Chat.tsx:237-253`

When user sends first message (no active thread), `createThreadMutation.mutate(title)` fires (async, non-awaited), then immediately proceeds to SSE connect with `thread_id: activeThread` which is still `null`. Backend receives message with no thread_id.

#### FE-H2. RunDetail Uses Unsafe Type Coercion

**File:** `web/src/pages/RunDetail.tsx:35`

`as unknown as` double-cast masks API response shape mismatches. Will silently produce runtime errors if the actual response structure changes.

### Frontend Medium

#### FE-M1. TopBar "Online" Status Is Hardcoded

**File:** `web/src/components/layout/TopBar.tsx:22-25`

Always shows green "Online" indicator regardless of actual connection state. Misleading when backend is down or SSE disconnects.

#### FE-M2. Session Expiry Hard-Redirects via window.location

**File:** `web/src/api/client.ts:108`

`window.location.href = "/login"` bypasses React Router, loses all component state. Should use AuthContext logout flow instead.

#### FE-M3. Artifact Download Bypasses Auth Headers

Artifact download uses direct `link.href` assignment, not the `apiRequest()` function, so auth headers aren't included.

#### FE-M4. CredentialModal Has No Empty-Value Validation

Users can save empty API keys. No error feedback on save failure.

#### FE-M5. No Unsaved-Changes Warning on Settings Page

User can navigate away after editing settings without saving. No prompt, silent data loss.

### iOS High

#### iOS-H1. Offline Queue Never Drained on Network Restore

**File:** `ios/Noa/Sources/Noa/Services/APIClient.swift:103-118`

APIClient enqueues requests when offline, but `NetworkMonitorService.startMonitoring()` is never called. Queue items sit in Documents directory forever. User never knows messages weren't sent.

#### iOS-H2. SSE Stream Not Cancelled on Thread Switch

**File:** ChatViewModel — when user switches threads, previous SSE stream task is not cancelled. Multiple streams can run simultaneously, causing wrong-thread messages to appear.

#### iOS-H3. AuthGuard Shows Login Without Attempting Token Refresh

**File:** `ios/Noa/Sources/Noa/Views/Auth/AuthGuard.swift:18-24`

Checks `isAuthenticated` but doesn't call `handleAppForeground()` to refresh expired tokens. Users with expired (but refreshable) tokens see LoginView unnecessarily.

#### iOS-H4. ComposerBar Has No Provider/Model Selectors

Chat requests send `provider: nil, model: nil`. If backend requires these fields or defaults to an unconfigured provider, chat fails.

### iOS Medium

#### iOS-M1. MainTabView ViewModels Without Lifecycle Cleanup

ViewModels with active SSE streams are created in `init` but never cleaned up on dismiss. Memory leak potential.

#### iOS-M2. ChatView loadHistory Race on Rapid Thread Switching

Multiple `loadHistory()` calls can overlap. Last one to complete wins, potentially showing wrong thread's messages.

#### iOS-M3. Biometric Auth Failure Has No Recovery UI

If biometric fails on high-risk approval, view stays open with no feedback. User can repeatedly tap Approve.

#### iOS-M4. Batch Deny Has No Confirmation Dialog

Multiple high-risk approvals can be denied with a single tap, no confirmation or biometric gate.

#### iOS-M5. VoiceService No User-Facing Timeout/Cancel UI

120s timeout with no progress indicator or cancel button. App appears frozen during slow uploads.

### iOS Low

#### iOS-L1. Environment.swift Hardcoded Dev IP

`URL(string: "http://100.106.15.98:8000")!` — force unwrap crashes if IP changes.

#### iOS-L2. DEBUG Builds Disable Certificate Pinning Entirely

`#if DEBUG` returns plain URLSession. If debug binary connects to production, MITM is possible.

---

### Frontend Low

#### FE-L1. ErrorBoundary Renders error.stack to UI (Exposes Internals)

**File:** `web/src/components/ErrorBoundary.tsx:43`

`ErrorBoundary` renders `error.stack` directly into the UI when an unhandled React error is caught. Stack traces expose full file paths, component names, and internal module structure which can assist attackers in understanding the frontend architecture.

```tsx
// Current (exposes internals):
{error.stack && <pre>{error.stack}</pre>}
```

**Fix:** Strip or replace `error.stack` with a generic user-facing message in production builds. Stack traces should only appear in development (`process.env.NODE_ENV === 'development'`).

**Impact:** Low — no direct exploit vector but violates information disclosure best practices. Stack traces are visible to any user who triggers a frontend error.

---

## 8. Auth Stability Findings (AUTH-H1, AUTH-H2, AUTH-M1, AUTH-M2)

Root-cause analysis of the recurring "Login failed - Session expired" UX failure discovered 2026-03-15. These findings explain why the issue persisted across multiple waves that touched auth (QC2, QC8, FR2, PR2, PR3) without resolving it. To be fixed by phase AU1.

---

### AUTH-H1 — `apiRequest` 401-handler fires on login endpoint

**Severity:** High
**File:** `web/src/api/client.ts:122-132`
**Introduced:** QC2 (when the generic retry-on-401 path was added alongside the httpOnly cookie migration)
**Status:** Open — to be fixed by AU1

**Description:**

`apiRequest` is a generic request wrapper that handles any 401 response by attempting token refresh and retrying. It is used for **all** API calls, including `POST /api/v1/auth/login`. When login fails (wrong password, user not found, account locked), the backend returns 401. `apiRequest` intercepts this 401, attempts to call `/api/v1/auth/refresh`, which also fails because there are no valid session cookies (the user is not logged in). The refresh path then calls `clearTokens()`, `redirectToLogin()`, and throws `new Error("Session expired")`.

The result: every login failure — regardless of cause — surfaces to the user as "Login failed - Session expired." The real error message from the backend ("Invalid email or password") is discarded. Users cannot distinguish between wrong credentials, a non-existent account, and a genuine session expiry.

This also means: if the user is on a slow connection and the login POST times out (AbortController fires after 30s), they also see "Session expired." If the backend is down and returns 503, `apiRequest` tries refresh, refresh also fails, "Session expired" appears again.

**Why it wasn't caught earlier:** QC2 introduced the 401 retry logic for the correct reason (auto-refresh expired tokens for authenticated requests). But it was applied as a blanket wrapper over all endpoints without exempting the login path. Subsequent auth waves (QC8, FR2, PR2) fixed auth edge cases without auditing `apiRequest`'s error propagation.

**Fix:** Auth endpoints (`/api/v1/auth/login`, `/api/v1/auth/register`, `/api/v1/auth/forgot-password`, `/api/v1/auth/reset-password`) must not trigger the 401-refresh path. Options: (a) a `skipAuthRetry` option on `apiRequest`, or (b) a separate `authFetch` function for auth endpoints that propagates backend error messages directly. Either way, a 401 from the login endpoint must surface the `detail` field from the backend response, not "Session expired."

---

### AUTH-H2 — Auth state desync between httpOnly cookies and localStorage flag

**Severity:** High
**File:** `web/src/auth/tokens.ts`, `web/src/auth/AuthContext.tsx:21`
**Introduced:** QC2 (as a side-effect of the localStorage → httpOnly cookie migration)
**Status:** Open — to be fixed by AU1

**Description:**

QC2 correctly moved tokens from localStorage to httpOnly cookies to prevent XSS token theft. However, because httpOnly cookies are not readable by JavaScript, a secondary `noa_authenticated` flag was added to localStorage as a proxy. `AuthContext` initialises `isAuthenticated` from `hasTokens()` which reads this flag.

These two stores can desync:

- **Scenario 1 (daily occurrence):** Access token cookie expires after 15 minutes. Refresh token cookie expires after 7 days. If the user closes the browser tab and reopens after the access token has expired but before the refresh token has expired — normal case, the refresh flow handles this. But if the refresh token has also expired (or the `AuthSession` row was invalidated in the DB), the localStorage flag still says `true`. The app loads, `isAuthenticated = true`, any data fetch returns 401, refresh fails, "Session expired" fires.
- **Scenario 2 (after container restart):** If `AuthSession.is_active` rows are not cleaned up, or if the `SECRET_KEY` changes (which would invalidate all existing JWTs), the existing cookies become invalid while localStorage still holds the flag. Same outcome.
- **Scenario 3 (after logout on another tab/device):** Logout clears cookies on the server. But localStorage on a different tab still says authenticated.

**Why it wasn't caught earlier:** FR2 fixed BE-H12 (cookie deletion attributes on logout were mismatched, causing the browser to silently ignore the deletion). That was a real fix. But the startup desync — "localStorage says yes, cookies are invalid" — was never addressed by any wave because it requires a startup validation call that was never built.

**Fix:** On `AuthProvider` mount, call `GET /api/v1/auth/me`. If it returns 200, the session is live — set `isAuthenticated = true`. If it returns 401, clear the localStorage flag and set `isAuthenticated = false`. Show a loading state in `AuthGuard` until this check completes (prevents the flash of authenticated content before the check resolves). Once this is in place, the localStorage flag is redundant and should be removed; auth state should live only in React state, sourced from the `/auth/me` check.

---

### AUTH-M1 — In-memory auth rate limiting not migrated despite H8 being marked resolved

**Severity:** Medium
**File:** `src/noa/auth/service.py:37-39`
**Introduced:** Foundation (F4 — initial auth implementation)
**Incorrectly marked resolved:** QC8
**Status:** Open — to be fixed by AU1 (or accepted as a known limitation)

**Description:**

Finding H8 ("Rate Limiting Is Process-Local") was filed and marked "Resolved (QC8 + hardening)". QC8 did implement per-user DB-backed rate limiting for the tool gateway (`src/noa/tools/rate_limiter.py`). However, the **auth login rate limiting** — `AuthService._failed_attempts` and `AuthService._lockout_until` — was never migrated. These are class-level in-memory dicts:

```python
# src/noa/auth/service.py lines 37-39
_failed_attempts: dict[str, list[datetime]] = {}  # class-level, not instance
_lockout_until: dict[str, datetime] = {}           # class-level, not instance
```

On every container restart, these are cleared. The practical effect: a user who has triggered a 30-minute lockout (5 failed attempts within 10 minutes) can bypass it by restarting the Docker stack. More importantly for daily UX: if a user enters the wrong password 5 times, gets locked out, restarts the container, and tries again — the lockout is gone but the password is still wrong, and they continue seeing "Session expired" (AUTH-H1) with no indication they were ever locked out or that their password is incorrect.

**Why it wasn't caught earlier:** QC8's scope was broad (10 deliverables). The H8 resolution in FINDINGS.md was written based on the tool-gateway rate limiting fix, without verifying that the auth-specific rate limiting was also addressed.

**Fix (for AU1):** For a single-user personal system, in-memory rate limiting is an acceptable trade-off — it provides protection within a session and Docker restarts are infrequent. The correct fix is to update the FINDINGS.md resolution note to accurately describe what was and wasn't fixed, and document the known limitation. Full DB-backed auth rate limiting can be a future hardening item if the system ever becomes multi-user.

---

### AUTH-M2 — No session validity check on app startup

**Severity:** Medium
**File:** `web/src/auth/AuthContext.tsx:21`, `web/src/api/v1/auth.py` (missing endpoint)
**Introduced:** QC2 (localStorage flag approach)
**Status:** Open — to be fixed by AU1

**Description:**

There is no `GET /api/v1/auth/me` endpoint (or equivalent). On app startup, `isAuthenticated` is initialised as `hasTokens()` — a synchronous read of the localStorage flag. This is an approximation, not a verification. The app cannot tell whether the httpOnly cookies backing that flag are still valid until the first API call fails.

This is the mechanism that turns a straightforward "your session has expired, please log in" into a confusing multi-step failure: the app loads, renders the main layout, fires several data fetches, one returns 401, the 401 handler fires the session-expired redirect, and the user sees a jarring redirect with an error toast rather than a clean login prompt.

The absence of this endpoint was a design gap, not a regression. No wave planned or implemented a `/auth/me` check because the localStorage flag was treated as sufficient for the single-user case.

**Fix:** Add `GET /api/v1/auth/me` — a thin authenticated endpoint returning `{user_id, email}`. In `AuthProvider`, replace `useState(() => hasTokens())` with `useState(false)` + `isLoading: true`, call `/auth/me` on mount, and resolve `isAuthenticated` from the response. `AuthGuard` shows a loading spinner until resolved. This eliminates the startup desync (AUTH-H2) and gives the user a clean login prompt instead of a "Session expired" redirect.

---

## 9. Resolved Pipeline Issues

Historical issues encountered during pipeline execution (formerly `Plan/ISSUES.md`). All resolved.

| ID | Phase | Severity | Description | Resolution |
|----|-------|----------|-------------|------------|
| I1 | F4 | LOW | Tests use mock session; broad exception assertions | Replaced `pytest.raises(Exception)` with specific error types; mock session kept for unit tests |
| I2 | OC3 | LOW | Audit log query/export endpoint not implemented | Created `src/noa/api/v1/audit.py` with GET/POST endpoints; wired into app.py |
| I3 | DW1 | LOW | Private worker app.py wiring missing; 24h windowing not implemented | HealthChecker in app lifespan; 24h sliding-window stats via `stats_24h()` |
| I4 | DW4 | LOW | Router not wired to PrivacyClassifier; LLM classification deferred | Router delegates to PrivacyClassifier as of DW4 |
| I5 | TI6 | LOW | Tool node not wired; rate limiter fixed-window not sliding-window | Replaced with true sliding-window implementation using timestamp deque |
| I6 | TI6 | LOW | `extract_idempotency_key` case-sensitive for header lookup | Now checks canonical, lowercase, and full case-insensitive fallback per RFC 7230 |



## 9. User E2E Testing Findings (2026-03-11)

| ID | Severity | Title | Status | Fix |
|----|----------|-------|--------|-----|
| L1 | Critical | Settings PUT never commits — changes rolled back on session close | **Resolved** | Added `await session.commit()` in settings endpoint |
| L2 | Critical | Chat fails from UI — defaults to unconfigured Anthropic provider | **Resolved** | Root cause was L1; also fixed privacy_mode default to "external" |
| L3 | High | Model routing ignored — always used constructor default model | **Resolved** | Pass model override through router → client complete() |
| L4 | High | Runs never persisted — sync RunService on async session | **Resolved** | Create Run+Conversation via async session before runner starts |
| L5 | High | Privacy mode override ignored — runner set wrong state key | **Resolved** | Runner now sets `user_privacy_override` (not just `privacy_mode`) |
| L6 | High | GET /api/v1/tools missing — Tools page shows "Failed to load" | **Resolved** | Added list endpoint returning TOOL_CAPABILITIES with per-user enabled status |
| L7 | Medium | Chat error events silently swallowed in UI | **Resolved** | Added toast notification on SSE error events |
| L8 | Medium | No thread deletion in Chat UI | **Resolved** | Added hover delete button with confirmation on thread sidebar |
| L9 | Medium | Cookie secure flag hardcoded True — breaks HTTP dev | **Resolved** | Environment-dependent (strict in prod, lax in dev) |
| L10 | Low | Tool management page (enable/disable connections) | **Resolved** | FR6 |
| L11 | Low | No LangSmith/diagnostics page | Open | Feature request |
| L12 | Low | No user management page | Open | Feature request |
| L13 | Low | Costs not showing despite runs | Partially resolved | Runs now persist; cost recording needs UsageStats schema fix |

## 10. User E2E Testing Findings — UX Session (2026-03-12)

### UX-H1: SSE Connection Fails on Calendar Tool Calls
**Severity:** High
**Status:** Open
**Description:** When the user asks Noa to create a calendar entry, the SSE connection fails. The runner yields all events after `graph.ainvoke()` completes (tool_called, tool_result, result_ready), so if the graph invocation throws during a calendar tool call, only a generic "An error occurred" is returned. Root cause likely: calendar tool execution fails (missing Google credentials/tokens, or OAuth flow not completed), and the error is swallowed by the generic exception handler in `runner.py:222-252`. Need to check Docker logs during a calendar request for the actual error.

### UX-H2: Send Button Disabled When Text Field Empty
**Severity:** High
**Status:** Open
**Description:** The send button in `Chat.tsx:493-494` has `disabled={!input.trim() || isStreaming}`. The user wants the send button always enabled (or at minimum, not disabled when there's no text). This prevents sending empty messages to trigger the agent for follow-ups or just interacting with the system prompt.
**File:** `web/src/pages/Chat.tsx:494`

### UX-H3: System Prompt Not File-Backed; No Save Button in UI
**Severity:** High
**Status:** Open
**Description:** The system prompt is stored in the DB (`user_settings.system_prompt`) and editable in the chat advanced settings panel. But: (1) There's no `prompts/` directory in the repo for version-controlled prompt templates, (2) The system prompt textarea auto-saves on blur but has no explicit "Save" button, making it unclear whether changes are persisted, (3) The default system prompt is hardcoded in `runner.py:255-307` rather than loaded from a file.
**Files:** `src/noa/orchestrator/runner.py:255-307`, `web/src/pages/Chat.tsx:446-463`

### UX-H4: Runs Page Nearly Empty
**Severity:** High
**Status:** Open
**Description:** The Runs page shows runs but with minimal data. Root causes: (1) Tool call events (tool_called, tool_result) are emitted AFTER `graph.ainvoke()` returns, not during streaming — so they're batch-emitted, not real-time. (2) The `run_events` table stores events but the Runs detail page doesn't fetch/display them. (3) `_persist_messages()` and `_record_usage()` are best-effort post-stream operations in `chat.py:168-174` — if they fail silently, runs have no associated messages or usage data.
**Files:** `src/noa/orchestrator/runner.py:174-190`, `src/noa/api/v1/chat.py:168-174`

### UX-H5: Tool Call Details Don't Show Exact Data (Tavily)
**Severity:** High
**Status:** Open
**Description:** The `ExecutionDetails` component (`web/src/components/chat/ExecutionDetails.tsx`) pairs tool_called with tool_result events by `tool_name`. But the SSE events from the runner emit `tool_call` (nested object) and `tool_result` (nested object) in the payload — the frontend expects `evt.data.tool_name` and `evt.data.args` at the top level, but the runner wraps them as `payload.tool_call` and `payload.tool_result`. This means the UI shows tool names but no arguments or results. The Tavily search results are inside the nested object but the UI can't extract them.
**Files:** `web/src/components/chat/ExecutionDetails.tsx:29-44`, `src/noa/orchestrator/runner.py:174-190`

### UX-H6: Notion Connected But Agent Can't Read
**Severity:** High
**Status:** Open
**Description:** Notion token is configured (`NOTION_TOKEN` env var) and the tool registers at startup. However, the agent may fail to use it because: (1) The tool is registered in the gateway but the user may not have the `notion.read` capability granted in `tool_capabilities` table, (2) The Notion integration may not have access to the specific pages (Notion integrations must be explicitly shared with pages), (3) The `NotionClient` sends requests to `https://api.notion.com/v1` but errors may be swallowed by the gateway's generic error handling. Need to test with a health check and inspect actual API response.
**Files:** `src/noa/tools/notion.py`, `src/noa/tools/registration.py`, `src/noa/tools/capabilities.py`

### UX-M1: Costs Not Shown in UI
**Severity:** Medium
**Status:** Open
**Description:** The Runs list endpoint (`GET /api/v1/runs`) aggregates `usage_stats` rows for cost_usd, tokens_in, tokens_out. But `_record_usage()` in `chat.py` is best-effort and may fail silently, leaving `usage_stats` empty. The frontend Runs page and Chat page don't display cost data even when available. No cost column in the runs table, no per-message cost indicator.
**Files:** `src/noa/api/v1/chat.py` (usage recording), `web/src/pages/Runs.tsx` (display)

### UX-M2: No Approvals / Human-in-the-Loop Toggle in Settings
**Severity:** Medium
**Status:** Open
**Description:** The approvals system exists in the backend (approval rules, pending approvals, step-up auth) but there's no UI toggle in Settings to enable/disable "human-in-the-loop" mode. Users cannot configure which tool actions require approval before execution. The Settings page (`web/src/pages/Settings.tsx`) shows model defaults, budget, credentials, and Google auth — but no approvals/governance section.
**Files:** `web/src/pages/Settings.tsx`, `src/noa/policy/engine.py`

### FR3-L1: Migration Chain Not Tested — Broken down_revision References Not Caught
**Severity:** Low
**Status:** Open
**Description:** The test suite uses `Base.metadata.create_all` to set up in-memory SQLite databases, which bypasses alembic entirely. As a result, a migration that references a `down_revision` pointing to a non-existent file will never cause a test failure — but will cause `alembic history` and `alembic upgrade head` to crash in the worktree (and potentially in staging). Discovered during FR3 QA review: migration 015 references `down_revision="014"` but migration 014 (`014_conversation_domain_column.py`, created by FR1) was not present in the FR3 worktree because it was branched before FR1 merged. Running `alembic history` in the FR3 worktree crashed with `KeyError: '014'`. Fix: add a test `test_migration_chain_intact` that reads all migration files, builds the revision map, and asserts every `down_revision` points to an existing revision (or is None). This should run as part of the unit test suite (no DB required — pure file parsing).
**Files:** `alembic/versions/`, `tests/unit/` (no test exists yet)

### BE-H6: Memory Facts Lost on API Container Restart
**Severity:** High
**Status:** Open
**Description:** The `noa-api` container's `MemoryStore` (imported from `private_worker.handlers`) is initialized with `data_dir=Path("/data/memory")`, but the `private-data` Docker volume is only mounted on `private-worker` and `backup` containers — not on `noa-api`. This means `/data/memory/` doesn't exist in the API container. Facts are held in-memory only and silently lost on every container restart. The `_persist()` method logs a warning but the API continues as if persistence succeeded. Observed: user approved a memory fact, API restarted ("Up 10 minutes" vs other containers "Up About an hour"), fact disappeared. Fix: either mount `private-data:/data` on `noa-api`, or move memory fact management to the `private-worker` (which already has the volume) and have the API proxy to it.
**Files:** `docker-compose.yml`, `src/noa/private_worker/handlers.py:21`, `src/noa/api/app.py:295-298`, `src/noa/private_worker/memory_store.py:221-230`

