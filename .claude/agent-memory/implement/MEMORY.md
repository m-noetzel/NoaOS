# Implement Agent Memory

## Environment

- All Python commands: `docker exec noa-dev ...`
- Frontend tests: `cd web && npm run test` (on host)
- iOS tests: run on host via Swift Package Manager
- Static gates: `docker exec noa-dev python -m ruff check src/` + `docker exec noa-dev python -m mypy src/ --ignore-missing-imports`

## Wiring Patterns (confirmed across 18 waves)

### FastAPI Router Registration
- New routers go in `src/noa/api/v1/{name}.py`
- Register in `src/noa/api/app.py` via `app.include_router(router, prefix="/api/v1/{name}", tags=["{Name}"])`
- Always verify: `docker exec noa-dev python -c "from noa.api.app import app; print([r.path for r in app.routes])"`

### Service Wiring
- Services instantiated in `app.py` lifespan or via `app.state`
- DI pattern: store on `app.state.{service_name}`, retrieve via `Depends()` or `request.app.state`
- **Critical pitfall:** "Wired in class, not at startup" — implementing a service class but never instantiating it in `app.py` lifespan. Tests pass because they manually inject. Always grep `app.py` for your new class name after implementing.

### iOS Swift Patterns
- SPM package at `ios/Noa/Package.swift` (no .xcodeproj)
- Test target: `NaoTests` (Nao, not Noa — naming inconsistency)
- swift-tools-version: 6.0 with strict concurrency
- Actors for services (APIClient, SSEClient, AuthService, etc.)
- @Observable + @MainActor for ViewModels
- ServiceFactory.swift is the composition root

## Frontend Patterns (confirmed in PR5)

### Module-level callback registration for cross-boundary decoupling
When a module (`client.ts`) cannot import React hooks but needs to trigger React navigation, use a module-level callback registration pattern:
```ts
let _onSessionExpired: (() => void) | null = null;
export function registerSessionExpiredHandler(handler: () => void): void { _onSessionExpired = handler; }
function redirectToLogin(): void { if (_onSessionExpired) { _onSessionExpired(); } else { window.location.href = "/login"; } }
```
The React context wires up the handler in `useEffect`. Falls back to direct navigation in tests/non-React contexts.

### Authenticated artifact downloads
Never use `<a href>` for protected resources. Use `fetch` with `Authorization: Bearer` header, create blob URL, click programmatically, revoke after timeout:
```ts
const blobUrl = URL.createObjectURL(blob);
try { link.click(); } finally { setTimeout(() => URL.revokeObjectURL(blobUrl), 1000); }
```

### iOS ASWebAuthenticationSession protocol pattern (GO3)
For OAuth flows that use ASWebAuthenticationSession, define a `WebAuthSessionProviding` protocol:
```swift
public protocol WebAuthSessionProviding: Sendable {
    func authenticate(url: URL, callbackURLScheme: String) async throws -> URL
}
```
The live adapter wraps `ASWebAuthenticationSession` with a `withCheckedThrowingContinuation`. The mock can inject any URL/error without triggering real browser flows. The `actor` service takes `any WebAuthSessionProviding` — no `@MainActor` needed on the service itself.

The live `ASWebAuthSessionAdapter` is iOS-only (use `#if canImport(AuthenticationServices) && !os(macOS)`) so the SPM package compiles on macOS without AuthenticationServices framework.

Callback scheme: use `"noaapp"`. Backend redirects to `noaapp://oauth/callback?google=connected` when `X-Noa-iOS-Redirect` header is set.

### iOS BiometricError pattern matching
`BiometricError.unknown` has an associated value, so `==` comparison doesn't work. Use pattern matching:
```swift
if case .userCancelled = error as? BiometricError { /* deliberate cancel */ }
```
Only set `isBiometricError = true` for non-cancel errors (`.authenticationFailed`, `.lockedOut`, etc.) — `.userCancelled` is intentional, don't show retry.

### iOS upload timeout with structured concurrency
Race work task against sleep task using `withThrowingTaskGroup`:
```swift
try await withThrowingTaskGroup(of: T.self) { group in
    group.addTask { try await work() }
    group.addTask { try await Task.sleep(...); throw CancellationError() }
    let result = try await group.next()!
    group.cancelAll()
    return result
}
```

### Vitest module mocks for components with sub-dependencies
For components that import other components unavailable in jsdom, use `vi.doMock` in `beforeEach` (not `vi.mock` at module level) to avoid hoisting issues. Use named exports consistently.

### apiRequest skipAuthRetry pattern (AU1)
When extending `apiRequest` options with custom properties that must not be forwarded to `fetch`, destructure them before the closure:
```ts
const { skipAuthRetry, ...fetchOptions } = options;
const makeRequest = async () => { /* uses fetchOptions, not options */ };
```
This prevents custom options from leaking into fetch's RequestInit.

### Auth startup session check pattern (AU1)
For startup session verification that must not trigger the 401-refresh retry loop, use raw `fetch` (not `apiRequest`) in a React effect with `isLoading=true` until resolved.

### Linux arm64 web test environment
The workspace Linux arm64 environment is missing `@rollup/rollup-linux-arm64-gnu` and `@swc/core-linux-arm64-gnu` native binaries. Web tests (vitest) cannot run on this Linux host — only on the macOS host (darwin-arm64). Frontend test verification requires the macOS host or the noa-dev Docker container.

## Recurring Pitfalls (confirmed across multiple phases)

### 1. Dead-end stores
Data written but never read = QA FAIL. Before storing anything, verify the read path exists. Every POST needs an observable GET.

### 2. Alembic migrations
When adding/modifying DB columns, ALWAYS create a migration. Tests pass via `Base.metadata.create_all()` but production will crash. Check `alembic/versions/` for the next sequence number.

### 3. Backend contract alignment with iOS
iOS `APIClient` expects specific JSON shapes. When modifying backend responses, check Swift model `Decodable` conformance. Key mismatches: `success_envelope` wrapping, field names (`privacy_mode` vs `domain`), auth token delivery (httpOnly cookies, not JSON body).

### 4. Async/sync boundaries
- FastAPI endpoints are async; services may be sync or async
- `asyncio.ensure_future()` for fire-and-forget from sync context (acceptable, not ideal)
- Never make a sync method async without updating ALL callers (broke 54 tests in QC5)

### 5. Domain isolation
`noa.private_worker` and `noa.external_worker` never import from each other. Shared code goes in `noa.llm.providers` or `noa.constants`.

### 6. Exception handling
- No bare `except:` — ruff E722 enforces
- No blind `except Exception:` without logging — ruff BLE001 enforces
- Use `# noqa: BLE001` sparingly and always add a log call

### 7. AuthUser dataclass — no email field
`AuthUser` (middleware.py — cannot modify) only has `user_id` and `session_id`. To return email from an endpoint, query the DB directly.

## Test Patterns That Work

- Real DB sessions via `conftest.py` fixtures (in-memory SQLite with StaticPool)
- FastAPI TestClient / httpx.AsyncClient for endpoint tests
- Mock only: external HTTP APIs (httpx), filesystem, network
- Never mock: internal services, DB, function under test
- At least 1 integration test per phase exercising full flow

## Postgres Integration Test Pattern (confirmed QE4)

- `tests/integration/conftest.py` uses `TEST_DATABASE_URL` env var (dev container: `postgresql+asyncpg://noa:kindness@postgres:5432/noa_test`)
- Falls back to testcontainers when `TEST_DATABASE_URL` unset (CI with Docker-in-Docker support)
- `noa-dev` container does NOT have Docker socket — testcontainers doesn't work there
- `pg_url` fixture is **session-scoped** (runs Alembic migrations once, drops+recreates `alembic_version` table)
- `pg_app` fixture is **function-scoped** (calls `app_state.reset_all()` before+after each test)
- Run integration tests: `docker exec -e TEST_DATABASE_URL="postgresql+asyncpg://noa:kindness@postgres:5432/noa_test" noa-dev python -m pytest tests/integration/ -v --tb=short --ignore=tests/integration/test_mr7_smoke.py --ignore=tests/integration/test_network_isolation.py`
- pyproject.toml per-file-ignores for `tests/integration/**/*.py` includes `I001` (import sort — lazy imports inside functions need specific ordering)
- Schema drift pitfall: ORM models added in a wave without a migration will fail integration tests but pass SQLite unit tests (create_all bypasses Alembic). Always check `alembic/versions/` when adding DB columns.

### Pre-existing failure tracking
When tests fail during FR work, always verify whether failures existed at HEAD before your changes with `git stash && python3 -m pytest <failing_tests>; git stash apply stash@{0}`. This prevents false alarm debugging. The 5 pre-existing failures in Wave 22 (as of FR6): `test_capability_strings_use_dot_notation`, `test_enable_grants_capability`, `test_known_tool_without_grant_denied`, `test_gateway_blocks_high_risk_without_step_up`, `test_gateway_allows_high_risk_with_step_up`.

### AsyncMock pitfall with SQLAlchemy result proxies
`AsyncMock()` makes ALL attribute accesses return coroutines, including `.scalars()`, `.first()`, etc. When a test mocks `session.execute()` with `AsyncMock`, calling `result.scalars().first()` fails with `'coroutine' object has no attribute 'first'`. Solution: use `MagicMock` for the execute return value, only `AsyncMock` for the method itself: `mock_session.execute = AsyncMock(return_value=MagicMock())`.

### DB session in credential endpoints
When an endpoint needs best-effort DB access (not mandatory for response), use `get_session_factory()` from `app_state` directly rather than adding `session: AsyncSession = Depends(get_db_session)` to the endpoint signature. This way tests that don't wire a DB session still get 200 responses. See `_auto_grant_capability()` in `tools.py` for the pattern.

## Test Patterns That Fail QA

- Constructor/existence tests (`assert obj is not None`)
- Over-mocked tests (3+ mocks = testing mocks)
- Source inspection tests (`inspect.getsource()`) — pass even if code path unreachable
- Tests that only verify stub responses match stub schemas
