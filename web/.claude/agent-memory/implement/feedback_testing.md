---
name: Testing patterns — real DB, ASGI TestClient, ephemeral URLSession
description: How to write integration tests for Noa that hit real code without internal mocks
type: feedback
---

## Python Integration Tests

Use `httpx.AsyncClient` with `ASGITransport` to test FastAPI endpoints in-process:

```python
from httpx import ASGITransport, AsyncClient
from noa.api.app import create_app
from noa.api.deps import get_db_session
from noa.auth.middleware import require_auth

async def _make_db() -> async_sessionmaker:
    from noa.db.models.base import Base
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Override auth + DB without mocking real service logic
app = create_app()
app.dependency_overrides[require_auth] = lambda: AuthUser(user_id=user_id)
app.dependency_overrides[get_db_session] = lambda: session_from_factory()

async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
    resp = await client.post("/api/v1/threads", json={"title": "test"})
```

Key rules:
- Always call `app.dependency_overrides.clear()` after each test
- Use `create_app()` (not the module-level `app`) so each test gets a fresh instance
- SQLite in-memory with `Base.metadata.create_all` — no Alembic needed in tests
- Registration endpoint returns 201, not 200

## Swift Live Tests (PR6 Pattern)

When Swift tests make real HTTP calls to `http://localhost:8000`:

```swift
// ALWAYS use ephemeral sessions — URLSession.shared carries cookies between tests
// If LB1 logs in and sets a cookie, LB2's unauthenticated test will use that cookie!
private func freshSession() -> URLSession {
    return URLSession(configuration: .ephemeral)
}
```

Email validation: `@test.local` is rejected as a reserved TLD. Use `@example.com`.

The running Docker backend may have a different version of the code than what's in `src/`.
Check `curl http://localhost:8000/openapi.json` to see actual required fields.

## Pre-existing ruff errors

`src/noa/api/v1/threads.py:45` has an E501 line-too-long error that pre-dates PR6.
This is a known pre-existing issue — not introduced by this phase.
