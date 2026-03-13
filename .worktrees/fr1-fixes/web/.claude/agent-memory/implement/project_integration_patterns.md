---
name: Noa integration test patterns — ASGI TestClient + live Swift tests
description: Patterns used in PR6 for real integration tests (no internal mocks)
type: project
---

## Python ASGI Integration Tests (PR6)

File: `tests/unit/test_pr6_integration.py`

Pattern for testing real endpoint flows:
1. Create an in-memory SQLite DB with `Base.metadata.create_all`
2. Override `require_auth` to return a known `AuthUser(user_id=...)`
3. Override `get_db_session` to yield from the in-memory factory
4. Create app via `create_app()` (fresh instance per test)
5. Use `ASGITransport + AsyncClient` for HTTP calls
6. Clear `app.dependency_overrides` in teardown

Only mock the auth guard (not optional — real JWT verification needs env vars).
Never mock service classes, repositories, or the DB itself.

## Swift Live Tests (PR6)

File: `ios/Noa/Tests/NaoTests/Integration/PR6LiveBackendTests.swift`

Pattern for live HTTP tests against Docker backend:
- Use `URLSession(configuration: .ephemeral)` — never `URLSession.shared` (cookies leak)
- Skip gracefully with `XCTSkip` if backend unreachable
- Register fresh users with `UUID()` to avoid email conflicts
- The backend's OpenAPI schema may differ from source if Docker not rebuilt
  → Check `curl http://localhost:8000/openapi.json` for actual required fields

## Wiring verified in PR6
- Thread CRUD is real DB (MV1 wired)
- Settings round-trip is real DB (SettingsRepository)
- MemoryStore.list_all() is user-scoped (user_id filtering)
- Approval list is real DB (MV2 wired)
- Auth endpoints use real password hashing
- Artifact endpoints require auth (401 without token)
