# Code Reviewer Memory

## Project Patterns (confirmed)

### Auth
- Auth uses httpOnly cookies for actual tokens; `localStorage.noa_authenticated` is the JS-readable flag (`src/auth/tokens.ts`).
- `AuthGuard` reads `hasTokens()` which checks `localStorage`. E2E tests must call `loginViaUI()` to set this flag — `page.evaluate(() => localStorage.setItem(...))` is an alternative shortcut.
- `AuthContext.logout()` fires a best-effort POST to `/api/v1/auth/logout` then calls `clearTokens()` synchronously. No redirect is performed by the context — Navigation after logout is the page's responsibility (Login.tsx does it via navigate after `useAuth`).

### SSE Client
- `SSEClient` (`src/api/sse.ts`) uses raw `fetch()` with manual SSE parsing. Playwright `page.route()` intercepts this correctly since it intercepts at the network level.
- `SSEClient` only reconnects if `this.runId` is set (populated from the `meta` event). Tests that omit the meta event will not trigger reconnect.
- An empty-line separator in SSE body dispatches the event; the formatter in `e2e/helpers/sse-mock.ts` uses `\n\n` between events which is correct.

### Testing Conventions
- Vitest unit tests live in `web/src/test/`; Playwright E2E tests live in `web/e2e/`.
- `test:e2e` = `playwright test`; `test:e2e:ui` opens the interactive UI; `test:e2e:report` shows last HTML report.
- The Wave 16 E2E fixture pattern: `setupApiMocks(page)` first, then specific overrides, then `loginViaUI(page)`.

### Known Dead Code in Wave 16
- `AUTH_STATE_PATH` in `web/e2e/fixtures.ts` is exported but never imported by any test. It was presumably scaffolded for `storageState`-based auth (Playwright's persistent auth) but that pattern was abandoned in favour of `loginViaUI()`.

### Settings page selectors
- Settings page budget inputs lack `htmlFor` associations; tests reach them via `page.locator('input[type="number"]').first()` (daily) and `.nth(1)` (monthly). This is fragile — if field order changes the tests silently break.

### DB Migrations (alembic)
- Migrations live in `alembic/versions/`, currently 001–007.
- The `device_push_tokens` table (model: `DevicePushToken`, iOS1 phase) has NO migration as of 007. The model is registered in `src/noa/db/models/__init__.py` but no `alembic/versions/008_*.py` exists.
- The upsert in `devices.py` uses `index_elements=["device_id"]` but the model declares no `UniqueConstraint` on `device_id` — the unique index required for the upsert must come from the (missing) migration.

### iOS1 Push Notification Backend (Phase iOS1)
- `APNsService._http_client` is always `None` at construction — no init method or lifespan hook. All real `send()` calls hit the `no_client` early-return path.
- `APNsService` is never instantiated or DI-wired in `app.py` (L10 violation, dead code).
- `DeviceTokenRequest.platform` and `PushPayload.notification_type` are plain `str` — no Literal/enum enforcement.
- `ApprovalBatcher` holds in-process dict state; not safe across worker processes or restarts.
- SPEC §29.5 is Phase 2 (native iOS). Implementing backend early is acceptable, but the table must still be migrated.

### iOS4 Auth Flow (Phase iOS4)
- **Critical contract break**: iOS `LoginRequest` sends `{username, password}`; backend expects `{email, device_id, password}`. Will return HTTP 422 on every login attempt.
- **Critical contract break**: iOS `RefreshRequest` sends `{refresh_token}`; backend expects `{refresh_token, device_id}`. Will return HTTP 422 on every refresh.
- **Critical architecture mismatch**: Backend `AuthTokenResponse` body contains ONLY `{token_type, expires_in, authenticated}` (tokens are in httpOnly cookies, C6). iOS `AuthService` decodes `AuthTokens` (which requires `access_token` + `refresh_token` in body) — decode will fail at runtime; iOS can never obtain tokens.
- `AuthViewModel` uses `nonisolated(unsafe)` on `isAuthenticated`/`errorMessage`/`tokenExpiresAt`. Not actor-isolated, so concurrent `loginAttempt` tasks can race on these properties. Swift 6 strict concurrency does NOT protect non-actor classes.
- `access_token_expire_minutes` default in `Settings` = 30 min; `AuthTokenResponse.expires_in` default = 900s (15 min) — inconsistent. Auth.py derives `expires_in` from `settings.access_token_expire_minutes * 60` (1800s) but the schema default says 900.
- `Settings` now has both `noa_env` and `environment` fields. Production guard only checks `noa_env`; `environment` field is duplicative and unguarded.
- T5 in `KeychainServiceTests` never asserts anything useful — `_ = result` is a non-test.
- `handleAppForeground()` threshold check: `expiry.timeIntervalSinceNow <= 60` — when token has NEVER been set (`tokenExpiresAt == nil`) after boot (fresh Keychain read on init), foreground will silently skip refresh even if a token exists. Auth state after cold-start may have `isAuthenticated=true` but `tokenExpiresAt=nil` indefinitely until next login.

### iOS5 Chat UI (Phase iOS5)
- **Critical delivery gap**: 9 of the 9 Swift files claimed as iOS5 deliverables do not exist in the repository (ChatService, ChatViewModel, ThreadListViewModel, ChatView, MessageBubble, ComposerBar, ToolCallCard, ThreadListView, MainTabView). Only `ChatModels.swift` (which predates iOS5) was present.
- `Package.swift` now uses `swift-tools-version: 6.0` (updated from 5.9 in iOS3). Swift 6 concurrency is now enforced at build time.
- `SSEClient` was refactored to a proper `actor` in iOS5 prep — fixes the `@unchecked Sendable` data-race concern from iOS3 notes.
- `ChatModels.swift` (iOS5 models file) has `ChatRequest` missing `privacy_mode` and `provider` fields — contradicts the backend schema and the test contract pinned in `test_ios5_chat_contract.py`.
- Backend `DELETE /api/v1/threads/{thread_id}` endpoint is a stub — returns `{"deleted": "<uuid>"}` with no DB interaction. No actual deletion occurs.
- `threads.py` list endpoint returns a hardcoded mock response (not real DB data) — all existing thread endpoints are stubs.
- The 32 contract tests in `test_ios5_chat_contract.py` pass because they only test Python-layer schema imports and dict shapes — they do not exercise the actual Swift UI code.
- `test_chat_request_schema_rejects_invalid_privacy_mode` is a self-documenting failing test: it documents that ChatRequest does NOT validate `privacy_mode` (accepts "public") — the test passes only because the code path that would fail falls into the except clause.

### iOS11 Integration & Polish (Phase iOS11)
- `decide_approval` endpoint in `approvals.py` returns a hardcoded `"risk_tier": "high"` regardless of the actual approval's stored `risk_tier`. The `ApprovalService.decide()` method exists and returns the full `Approval` ORM object including its real `risk_tier` — the endpoint never calls it. This is a correctness bug and an input-validation gap (any string is accepted for `decision`).
- The endpoint is a stub that does not persist decisions to the DB. `ApprovalService.decide()` in `src/noa/policy/approval.py` is the correct service to call.
- `ApprovalDecision.decision` is a plain `str` with no `Literal["approved", "denied"]` constraint, allowing any string to be stored.
- Test `test_health_endpoint_returns_200_without_auth` at line 533 calls `asyncio.get_event_loop().run_until_complete()` inside a sync test — this is deprecated in Python 3.10+ and will fail on Python 3.12 if the loop is already closed. Should use `@pytest.mark.asyncio` or `asyncio.run()`.
- Tests in `TestApprovalDecideResponseShape` pass because they only verify the stub returns `risk_tier` and `decided_at` — they do not verify the values are correct or come from the database.

### TM2 Tools API Enrichment (Phase TM2)
- **Missing Alembic migration**: `tool_capabilities` table was created in migration 004. The `function_name` column added in TM2 has NO corresponding migration (009 does not exist). The ORM model in `src/noa/db/models/tool_capability.py` declares it, but any deployed DB will error on queries referencing this column.
- `disable_function` endpoint (`DELETE /{tool_name}/{function_name}`) does NOT validate that `tool_name`/`function_name` exist in `TOOL_SCHEMAS` before calling `revoke()`. Always returns 200+revoked even for unknown tools/functions. The sibling `enable_function` endpoint correctly validates both.
- `DbCapabilityChecker.grant()` has no uniqueness guard — repeated calls create duplicate rows in `tool_capabilities`. No `UniqueConstraint` on `(user_id, tool_name, function_name)` and no upsert logic.
- The `_db_engine` fixture in `TestFunctionCapabilityChecker` uses `asyncio.get_event_loop_policy().new_event_loop().run_until_complete(...)` — this creates a dangling event loop. The three `@pytest.mark.asyncio` tests in the same class each create their own in-memory engine independently (correct), so the `_db_engine`/`db_session` fixtures are effectively unused scaffolding (dead fixtures).
- Route ordering in `tools.py`: `POST /{name}/health` (line 293) and `POST /{name}/credentials` (line 317) are registered AFTER `POST /{tool_name}/{function_name}/enable` (line 224). FastAPI matches by specificity, not registration order for path-parameter routes, so `/{name}/health` will shadow `/{tool_name}/{function_name}/enable` when called as e.g. `POST /gmail/health/enable` — but this is unlikely in practice. No collision for the designed URL patterns.
- `TOOL_CAPABILITIES` loop at module load time (capabilities.py lines 31-36) silently overwrites any manually pre-populated function-level key. All function keys map to the tool-level capability string — correct for the current design but could confuse future maintainers.

### PR1 Backend Critical Fixes (Phase PR1)
- `runs.py` `replay_run_events`: `after_event_id` filtering uses Python enumeration index (`idx > after_event_id`), not a stable DB cursor. SSE reconnect semantics are broken — a reconnecting client may skip or duplicate events if any event is inserted or deleted.
- `chat.py` double status update: `_make_run_service` returns `_NoOpRunService`, so runner's `update_status` calls are no-ops. `_update_run_status` at end of stream uses raw SQL `UPDATE` that bypasses the state machine in `RunService.update_status`. Currently harmless but architecturally fragile.
- `runs.py` `func.max(provider)` / `func.max(model_name)`: for multi-model runs this returns the lexicographically greatest string, not the primary or last model. Tokens/cost sum correctly.
- `memory.py` `update_fact`: mutates the dict returned by `get_by_id` directly — works because `get_by_id` returns a live reference into `_facts`. Fragile if `get_by_id` is ever refactored to return a copy.
- `MemoryStore.store()` never populates `user_id` on the stored fact — tests work around this by directly writing `store._facts[fact_id]["user_id"] = uid`. This means new facts created via the orchestrator have no `user_id` and will be invisible to all `list_all(user_id=x)` calls.

### FR2 Memory & Session Fixes
- **Startup ordering bug pattern**: `register_tools(gateway)` in `app.py` lifespan runs at line ~119 but the external MemoryStore is wired at line ~311. `_register_external_memory` always calls `get_external_memory_store()` at registration time and returns `None`, so external_memory tool is silently never registered. Order matters: store must be wired BEFORE `register_tools()`.
- **ARCH L1 violation in lifespan**: `app.py` imports `from noa.private_worker.memory_store import MemoryStore` directly. The pre-existing private-worker import (line 296) was tolerated, but the new BE-H9 import adds another violation of the "API layer never imports from workers directly" rule.
- **Shared volume for both private and external memory stores**: The external MemoryStore is wired to write `/data/memory/external`, but both containers (noa-api and private-worker) share the `private-data` volume — the external-worker container has no `/data` volume at all. This is architecturally intentional (the external MemoryStore lives in the API process), but no external-worker-side volume was needed.
- **`asyncio.get_event_loop().run_until_complete()` in sync tests**: This pattern appeared in test_fr2 at line 528 (same as iOS11 tests). Deprecated in Python 3.10+, fails on 3.12 when loop is already closed.

### FR4 Chat & Streaming UX (Phase FR4)
- `tool_start`, `tool_end`, and `step` are in frontend `VALID_SSE_EVENTS` and `SSEEventType` but the backend runner (`runner.py`) never emits them. `ActivityStream` handles them gracefully if they arrive — but they won't from the current orchestrator. Tests for UX-H10 exercise the component in isolation (pass synthetic events directly) and pass.
- `EventTimeline.tsx` line 143 reads `event.data.response_text` for the `result_ready` event, but the runner emits the field as `payload.response` (not `response_text`). The timeline's result_ready row always shows nothing.
- `Chat.tsx` has no cleanup `useEffect` to call `sseClientRef.current.disconnect()` on unmount. A tab navigation away mid-stream leaves an orphaned SSEClient consuming connection and calling React state setters on an unmounted component.
- UX-H9 deduplication uses content-matching (`m.content === optimisticUserMessage.content`). Two identical messages in quick succession will deduplicate incorrectly. Low risk in practice (single-user, personal assistant).
- `optimisticUserMessage` is set to `null` at `result_ready` (line 231) before the query refetch completes. If `invalidateQueries` is slow, there's a brief window where the user message disappears from the chat.
- `_PROMPTS_DIR` path computation in `settings.py`: `Path(__file__).parent × 5 / "prompts"` — correctly resolves to project root / prompts.
- SSE keepalive (`: keepalive\n\n`) is correctly silently ignored by the frontend SSE parser: `:...` lines don't match `id:`, `event:`, `data:` prefixes and the empty line with no accumulated `currentData` fires no event.
- Settings router `/api/v1/settings/system-prompt` GET+PUT wired into `app.py` via `settings_router` (line 446). Correctly registered.

### iOS3 Networking Layer (Phase iOS3)
- SPM package at `ios/Noa/Package.swift` — no `.xcodeproj` (spec said create one; delivered as SPM library instead).
- `swift-tools-version: 5.9`; no `swiftLanguageVersions: [.v6]` — Swift 6 strict concurrency not enforced at build time despite claim.
- `APIClient` is an `actor` — correct for thread-safe token refresh.
- `SSEClient` is `final class: @unchecked Sendable` with mutable fields (`capturedRunId`, `capturedThreadId`, `lastEventId`) written from an internal `Task`. Not data-race-safe under Swift 6 strict concurrency. Acceptable risk for iOS3 scaffold; flag in future phases.
- `SSEError.maxReconnectsExceeded` is declared but never thrown — actual exhaustion throws the underlying `Error`. Dead enum case.
- `SSEClient` has no 401 handling on the streaming connection. Token expiry mid-stream will drain all reconnect attempts and fail. Acceptable in iOS3 (auth is iOS4); must be addressed in iOS4/iOS5.
- `appendingPathComponent(endpoint)` where endpoint starts with `/` — Foundation strips the leading slash correctly for simple base URLs, but would produce wrong URLs if baseURL ever gains a non-root path.
- `test_networkError_returnsTypedError` tests a 500 response, not an actual `URLError` — real network-level error path is untested.
- Keychain access level `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly` — correct choice for device identity.
- Idempotency-Key generated fresh per write request via `UUID().uuidString` inside `buildRequest` — correctly unique per call.
