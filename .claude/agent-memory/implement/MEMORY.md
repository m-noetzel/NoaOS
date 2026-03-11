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

## Test Patterns That Work

- Real DB sessions via `conftest.py` fixtures (in-memory SQLite with StaticPool)
- FastAPI TestClient / httpx.AsyncClient for endpoint tests
- Mock only: external HTTP APIs (httpx), filesystem, network
- Never mock: internal services, DB, function under test
- At least 1 integration test per phase exercising full flow

## Test Patterns That Fail QA

- Constructor/existence tests (`assert obj is not None`)
- Over-mocked tests (3+ mocks = testing mocks)
- Source inspection tests (`inspect.getsource()`) — pass even if code path unreachable
- Tests that only verify stub responses match stub schemas
