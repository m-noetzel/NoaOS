# Noa Codebase Audit Report — 2026-03-16

## 1. FEATURES BUILT BUT NOT WIRED (Critical)

Complete implementations that exist in the codebase but are **never called by production code**.

### Backend

| Feature | File | Issue |
|---------|------|-------|
| **GovernanceWrapper** | `src/noa/tools/governance.py` | Full idempotency/rate-limit/preview wrapper. Never imported by any production code. The `ToolGateway` reimplements all the same governance (idempotency, rate limits) independently. Two parallel implementations of the same spec requirements. |
| **ToolScopeRegistry** | `src/noa/tools/scopes.py` | Scope-based tool filtering with predefined scopes (email_draft, research, scheduling). Only imported by `api/v1/tools.py` for the API endpoint, but the **orchestrator never uses it** — tools are not filtered by scope during execution. |
| **PolicyEngine.requires_preview()** | `src/noa/policy/engine.py:85` | Method defined but never called from anywhere. |
| **policy/preview.py** | `src/noa/policy/preview.py` | Entire module — `generate_preview()` for dry-run previews. Never imported by production code. Only referenced in tests. |
| **ToolRegistry** (from interface.py) | `src/noa/tools/interface.py:42` | Imported in `nodes/tools.py` but **`set_registry()` is never called** at startup. The gateway path always wins. ToolRegistry is dead infrastructure. |
| **IdempotencyStore** | `src/noa/tools/idempotency.py` | Only imported by `GovernanceWrapper` which itself is dead code. The `ToolGateway` has its own idempotency cache. |
| **RateLimiter** class | `src/noa/tools/rate_limiter.py` | Same — only used by dead `GovernanceWrapper`. `ToolGateway` has its own rate limiter. |
| **MCPToolAdapter** (legacy) | `src/noa/tools/mcp_adapter.py` | Deprecated stub. Never imported anywhere. |
| **load_custom_tools()** | `src/noa/tools/registration.py:372` | Function exists to load custom tools from DB at startup but is **never called** from `app.py` lifespan or `wire_llm_pipeline()`. Custom tools registered via API endpoint but never restored on restart. |
| **capability_checker on gateway** | `src/noa/tools/gateway.py:104` | `gateway.capability_checker` is declared and checked in dispatch, but **never set** in production. `DbCapabilityChecker` exists but is only used in the tools API endpoint, not wired to the gateway. |
| **discover_tools / discovered_tools_to_schemas** | `src/noa/tools/mcp_discovery.py:69,110` | MCP auto-discovery functions exist but are never called from production. Only tested. |
| **generate_preview** (governance.py) | `src/noa/tools/governance.py:28` | Duplicate of the one in `policy/preview.py`, also dead. |

### Frontend

| Feature | File | Issue |
|---------|------|-------|
| **JSONViewer** | `web/src/components/shared/JSONViewer.tsx` | Component defined but never imported or rendered anywhere. |
| **~20 shadcn/ui components** | `web/src/components/ui/` | Components like `aspect-ratio`, `carousel`, `hover-card`, `input-otp`, `menubar`, `navigation-menu`, `pagination`, `resizable`, `slider`, `toggle-group`, `context-menu`, `command`, etc. are installed but never used. (Typical shadcn bloat — low priority.) |
| **use-mobile hook** | `web/src/hooks/use-mobile.tsx` | Only imported by `sidebar.tsx` which itself has minimal usage. |

---

## 2. DUPLICATED GOVERNANCE SYSTEMS (Architectural Issue)

The single biggest design problem: **two complete governance stacks exist in parallel**.

**Stack A — `ToolGateway`** (the one actually used):
- Idempotency cache (`_idempotency_cache`)
- Rate limiter (`_rate_limits`, `_per_user_rate_calls`)
- Dry-run preview (`dry_run` parameter)
- Domain isolation
- Capability check
- Policy/approval check
- Telemetry + audit callback

**Stack B — `GovernanceWrapper` + friends** (entirely dead):
- `GovernanceWrapper` (idempotency + rate limit + preview)
- `IdempotencyStore` (TTL-based dedup)
- `RateLimiter` (sliding window)
- `generate_preview()` (two implementations!)
- `ToolInterface` / `ToolRegistry`

The gateway won and Stack B was abandoned, but Stack B was never cleaned up. This is ~400 lines of dead code.

---

## 3. UNWIRED FEATURES — DETAILED TRACE

### 3.1 Capability Checker — built, checked, never set

The **code that checks** capabilities exists in the gateway dispatch path:

`src/noa/tools/gateway.py:162-174`:
```python
# 1b. Capability check (MR5)
if self.capability_checker is not None and request.user_id is not None:
    has_cap = await self.capability_checker.has_capability(request.user_id, tool)
    if not has_cap:
        return ToolResponse(error=f"Capability denied for tool: {tool}")
```

The **DB-backed implementation** exists and is fully functional:

`src/noa/tools/capabilities.py:64-161` — `DbCapabilityChecker` with `has_capability()`, `grant()`, `revoke()`, all backed by the `tool_capabilities` DB table.

The **API endpoints** exist in `src/noa/api/v1/tools.py` — users can grant/revoke capabilities via REST.

**Where the wire is missing:** In `src/noa/api/app.py:106-124`, when the gateway is created during startup, nobody ever does:

```python
gateway.capability_checker = DbCapabilityChecker(session)
```

So `gateway.capability_checker` stays `None` forever. The `if self.capability_checker is not None` check on line 163 always short-circuits. **Users can grant/revoke capabilities via the API, the data is stored in the DB, but the gateway never enforces it.** Any user can invoke any tool regardless of their capability grants.

### 3.2 Tool Scopes — filterable but never filtered

The **scope system** exists in `src/noa/tools/scopes.py`:
- Predefined scopes like `"email_draft"` → `["gmail__read_email", "gmail__draft_email"]`
- `ToolScopeRegistry` with `get_scope()`, `register_scope()`
- `filter_tools_by_allowlist()` — intersects user tools with task-level restrictions

The **API endpoints** exist in `src/noa/api/v1/tools.py` — the frontend can list scopes and update them.

The **frontend** calls these endpoints on the Tools page (`web/src/pages/Tools.tsx:63` fetches scopes, line 165 saves scope updates).

**Where the wire is missing:** The orchestrator (`src/noa/orchestrator/nodes/tools.py`, `runner.py`, `graph.py`) never calls `filter_tools_by_allowlist()`. When the LLM agent runs, it gets access to **all registered tools** regardless of what scope the user or task is configured for. The scope data is stored and displayed, but it has zero effect on execution. The LLM can call any tool it wants.

### 3.3 Custom Tool Restore — registered once, lost on restart

The **registration API** exists in `src/noa/api/v1/tools.py` — users can register custom HTTP tools with a name, base URL, and auth type. These get saved to the `custom_tools` DB table AND registered in the gateway at request time.

The **restore function** exists:

`src/noa/tools/registration.py:372-391`:
```python
async def load_custom_tools(gateway: ToolGateway, session: AsyncSession) -> None:
    """Load custom tools from DB and register as HTTP adapters in the gateway.
    Called at app startup to restore user-registered custom tools."""
    result = await session.execute(select(CustomTool))
    tools = result.scalars().all()
    for tool in tools:
        adapter = HttpToolAdapter(base_url=tool.base_url, auth_type=tool.auth_type)
        gateway.register(tool.name, adapter)
```

**Where the wire is missing:** `load_custom_tools()` is never called from `app.py`'s `lifespan()` or `wire_llm_pipeline()`. Look at `wire_llm_pipeline()` — after building the gateway it calls `register_tools(gateway)` which registers the built-in tools (web_search, calendar, gmail, notion, memory), but **never calls `load_custom_tools()`**. So every time the app restarts, all user-registered custom tools vanish from the gateway. The DB still has them, the function to restore them exists, but nobody calls it.

### 3.4 Previews — two implementations, zero callers

**Implementation A** — `src/noa/policy/preview.py:22-69`:
`generate_preview(action, args)` — produces human-readable previews like "Send email: To: X, Subject: Y, Body: Z..." for medium/high risk actions.

**Implementation B** — `src/noa/tools/governance.py:28-51`:
`generate_preview(tool_name, function, args)` — nearly identical logic with slightly different signature.

**PolicyEngine declares it should be used** — `src/noa/policy/engine.py:85-87`:
```python
def requires_preview(self, risk_tier: str) -> bool:
    return risk_tier in ("medium", "high")
```

**Where the wire is missing:** The gateway dispatch path (`src/noa/tools/gateway.py:130-269`) has a `dry_run` parameter and can generate a basic preview dict (line 208-218), but it **never calls** `generate_preview()` from either module, and **never calls** `requires_preview()`. The runner (`orchestrator/runner.py`) doesn't call them either. The approval flow creates approvals with `preview_text` but that text comes from the tool call args directly, not from the preview generator.

So: the policy engine knows which actions need previews, two functions exist to generate those previews, but the actual execution path skips all of it. Medium-risk actions (like sending an email) go straight to the approval prompt without showing the user a formatted preview of what will happen.

---

## 4. CODE QUALITY FINDINGS

### Good Practices
- Domain isolation is properly enforced (no cross-worker imports)
- All API routes are mounted in `app.py`
- Orchestrator graph is fully wired (router -> agent -> tools -> responder)
- Frontend routing matches backend endpoints well
- Auth flow (JWT + refresh + httpOnly cookies) is complete
- CORS is properly restricted (no wildcards)
- CSP headers are set
- Content filtering on tool outputs exists
- 30s timeout on all frontend fetch calls

### Issues

**Over-engineering:**
- Dual function naming in `chat.py` — three layers of indirection for app_state access
- `ModelConfig` stores "none" model strings for pure function nodes that never use them
- Verbose approval parsing — hand-parsing tool_name and JSON from a preview_text string field

**Anti-patterns:**
- 71 `except Exception` catches with `# noqa: BLE001` — many swallow errors silently
- Module-level globals for DI (`set_router()`, `set_gateway()`) instead of FastAPI `Depends`
- Heavy `Any` typing defeats static analysis
- Magic strings for privacy mode (`"private"`, `"external"`) — should be Enum
- `TOOL_ALLOWLIST` in `nodes/tools.py` is a hardcoded fallback that doesn't match real tool names
- `.get()` on TypedDict loses type narrowing

**Duplication:**
- Model config defaults in both `model_config.py` and `external_worker/llm/router.py`
- Two `generate_preview()` functions (both dead)
- Tool result parsing logic in both `runner.py` and `nodes/tools.py`

**Simplification opportunities:**
- Hand-rolled idempotency in `chat.py` (O(n) cleanup per request) — could use Redis or a library
- Responder node has 3-level fallback chain hiding upstream bugs
- `app.py` lifespan is 180 lines of try/except blocks — could use a startup registry pattern
- Inconsistent SSE event payload shapes force frontend to handle multiple formats

**Inconsistencies:**
- Exception handling varies across modules (specific vs bare `except Exception`)
- Logging context propagation uses different approaches in different files
- Function result validation mixes `.get()` with direct access

**Frontend:**
- Large component files (Chat.tsx: 759 lines, Settings.tsx: 640 lines) — should be split
- Loose types (multiple `as string` casts, `Record<string, unknown>`)
- Manual SSE event parsing with fallback chains

---

## 5. OVERALL ASSESSMENT

### Code Quality Score: 6.5 / 10

| Dimension | Score | Notes |
|-----------|-------|-------|
| Architecture | 7/10 | Clean domain isolation, proper graph-based orchestrator, good separation of concerns |
| Wiring/Integration | 5/10 | Multiple features built but never connected; capability checker, scopes, custom tool restore, previews all unwired |
| Code Hygiene | 6/10 | ~400 lines of dead governance code, deprecated stubs, duplicated implementations |
| Security | 8/10 | Good CORS, CSP, content filtering, domain isolation, no SQL injection, sanitized logging |
| Testing | 7/10 | 2000+ tests, good coverage, but many test dead features (not production paths) |
| Modern Practices | 7/10 | Async throughout, Pydantic v2, React Query, but too many `Any` types and magic strings |
| Frontend | 7/10 | Clean routing, proper auth flow, lazy loading, but some large components |

---

## 6. PRIORITY ACTIONS

### P0 — Wire or Remove
1. `load_custom_tools()` — call it in startup or delete the function
2. `capability_checker` — wire `DbCapabilityChecker` to gateway or remove the check
3. Delete Stack B entirely (`GovernanceWrapper`, `IdempotencyStore`, `RateLimiter`, `ToolInterface.ToolRegistry`, `MCPToolAdapter`, both `generate_preview()` functions)

### P1 — Quality
1. Remove `TOOL_ALLOWLIST` fallback (dead path since gateway is always set)
2. Centralize model defaults
3. Replace magic strings with Enums
4. Call `requires_preview()` somewhere or remove it
5. Wire `ToolScopeRegistry` into orchestrator or remove scopes

### P2 — Cleanup
1. Remove unused shadcn components
2. Remove `JSONViewer`
3. Split `Chat.tsx` and `Settings.tsx` into smaller components
4. Remove `MCPToolAdapter` legacy stub
