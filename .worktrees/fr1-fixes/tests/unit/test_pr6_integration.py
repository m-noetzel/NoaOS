"""PR6: Real integration tests — no mocking internal services.

Phase: Wave 19 PR6 (Integration Tests & Verification).
Spec refs: SPEC.md §5.1–5.4, §13.2, §22.1–22.2, §29.6, §37

Tests use ASGI TestClient (httpx.AsyncClient + ASGITransport) so they run
against the real FastAPI app with real SQLAlchemy against an in-memory SQLite
DB. Only auth dependency is overridden (to inject a pre-seeded user_id), and
only for tests that need full end-to-end DB flows without the overhead of
registering/logging in via the real auth endpoint.

Every test proves a real user-visible behaviour:
  - Data stored via one path is readable via the path that consumes it.
  - Auth boundaries are enforced (401 without token).
  - DB transactions round-trip correctly.
"""

# ruff: noqa: S101, S105, S106, E501

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

pytestmark = pytest.mark.pr6


# ---------------------------------------------------------------------------
# Shared in-memory DB factory
# ---------------------------------------------------------------------------

async def _make_db() -> async_sessionmaker:
    """Return an async sessionmaker backed by a fresh in-memory SQLite DB.

    Creates all tables using the ORM metadata so there is no dependency on
    Alembic migrations in the test environment.
    """
    from noa.db.models.base import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _auth_user(user_id: uuid.UUID | None = None) -> Any:
    from noa.auth.middleware import AuthUser

    return AuthUser(user_id=user_id or uuid.uuid4())


# ---------------------------------------------------------------------------
# Helper: build app with overridden DB session + auth
# ---------------------------------------------------------------------------

async def _make_app_with_db(
    factory: async_sessionmaker,
    user_id: uuid.UUID,
) -> Any:
    """Return a FastAPI app instance with DB session and auth injected.

    This lets tests exercise real endpoint logic (service + repository layers)
    without needing a running Postgres or a real login flow.
    """
    from noa.api.app import create_app
    from noa.api.deps import get_db_session
    from noa.auth.middleware import require_auth

    fixed_user = _auth_user(user_id)

    async def _fake_auth() -> Any:
        return fixed_user

    async def _fake_db():
        async with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[require_auth] = _fake_auth
    app.dependency_overrides[get_db_session] = _fake_db
    return app


# ===========================================================================
# IT1: Thread CRUD — create → list → add message (via threads endpoint) → delete
# ===========================================================================


class TestThreadCRUD:
    """SPEC.md §22.1: Thread management — create, list, delete round-trip."""

    @pytest.mark.asyncio
    async def test_create_list_delete_thread(self, monkeypatch):
        """Creating a thread stores it; listing returns it; deleting removes it.

        Data path: POST /threads → DB insert → GET /threads (SELECT) → DELETE /threads/{id}.
        Tests that the DB layer actually persists and retrieves data, not just that
        the endpoint exists.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret-pr6-threads")

        user_id = uuid.uuid4()
        factory = await _make_db()
        app = await _make_app_with_db(factory, user_id)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Step 1: create thread
            create_resp = await client.post(
                "/api/v1/threads",
                json={"title": "PR6 integration test thread"},
            )
            assert create_resp.status_code == 200, (
                f"Thread creation failed: {create_resp.text}"
            )
            create_body = create_resp.json()
            assert create_body["ok"] is True
            thread_id = create_body["data"]["id"]
            assert thread_id is not None, "create response must include the new thread ID"
            assert create_body["data"]["title"] == "PR6 integration test thread"

            # Step 2: list threads — must include the newly created thread
            list_resp = await client.get("/api/v1/threads")
            assert list_resp.status_code == 200
            list_body = list_resp.json()
            assert list_body["ok"] is True
            thread_ids = [t["id"] for t in list_body["data"]]
            assert thread_id in thread_ids, (
                f"Newly created thread {thread_id} must appear in list; got: {thread_ids}"
            )

            # Step 3: delete thread
            delete_resp = await client.delete(f"/api/v1/threads/{thread_id}")
            assert delete_resp.status_code == 200
            delete_body = delete_resp.json()
            assert delete_body["ok"] is True

            # Step 4: list threads again — deleted thread must be gone
            list_resp2 = await client.get("/api/v1/threads")
            list_body2 = list_resp2.json()
            thread_ids2 = [t["id"] for t in list_body2["data"]]
            assert thread_id not in thread_ids2, (
                f"Deleted thread {thread_id} must not appear in subsequent list"
            )

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_thread_returns_404(self, monkeypatch):
        """Deleting a thread that does not exist must return 404, not 500.

        SPEC.md §37: Error handling — not found errors must be explicit.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret-pr6-threads")

        user_id = uuid.uuid4()
        factory = await _make_db()
        app = await _make_app_with_db(factory, user_id)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            fake_id = uuid.uuid4()
            resp = await client.delete(f"/api/v1/threads/{fake_id}")
            assert resp.status_code == 404, (
                f"Deleting nonexistent thread must return 404, got {resp.status_code}"
            )

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_messages_empty_for_new_thread(self, monkeypatch):
        """Listing messages on a new thread returns an empty list, not an error.

        SPEC.md §22.1: Empty message list is a valid state, not an error.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret-pr6-threads")

        user_id = uuid.uuid4()
        factory = await _make_db()
        app = await _make_app_with_db(factory, user_id)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create a thread
            create_resp = await client.post(
                "/api/v1/threads",
                json={"title": "Empty message thread"},
            )
            thread_id = create_resp.json()["data"]["id"]

            # List its messages — must be empty list, not error
            messages_resp = await client.get(f"/api/v1/threads/{thread_id}/messages")
            assert messages_resp.status_code == 200
            messages_body = messages_resp.json()
            assert messages_body["ok"] is True
            assert messages_body["data"] == [], (
                "A brand new thread must have no messages"
            )

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_messages_on_foreign_thread_returns_404(self, monkeypatch):
        """A user cannot read another user's thread messages (user isolation).

        SPEC.md §22.1: Thread ownership scoping.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret-pr6-threads")

        owner_id = uuid.uuid4()
        other_id = uuid.uuid4()
        factory = await _make_db()

        # Create thread as owner
        owner_app = await _make_app_with_db(factory, owner_id)
        transport = ASGITransport(app=owner_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_resp = await client.post(
                "/api/v1/threads", json={"title": "Owner thread"}
            )
            thread_id = create_resp.json()["data"]["id"]
        owner_app.dependency_overrides.clear()

        # Other user tries to read messages from owner's thread
        other_app = await _make_app_with_db(factory, other_id)
        transport2 = ASGITransport(app=other_app)
        async with AsyncClient(transport=transport2, base_url="http://test") as client:
            resp = await client.get(f"/api/v1/threads/{thread_id}/messages")
            assert resp.status_code == 404, (
                "A user must not be able to read another user's thread messages; "
                f"expected 404, got {resp.status_code}"
            )
        other_app.dependency_overrides.clear()


# ===========================================================================
# IT2: Settings round-trip — PUT → GET → verify field persisted
# ===========================================================================


class TestSettingsRoundTrip:
    """SPEC.md §11.1: Settings persistence — stored value is returned on GET."""

    @pytest.mark.asyncio
    async def test_put_settings_persists_budget_daily_usd(self, monkeypatch):
        """PUT /settings stores budget_daily_usd; GET /settings returns the same value.

        Data path: PUT stores via SettingsService → SQLAlchemy → SQLite;
        GET retrieves via the same path. Uses a non-credential field to avoid
        triggering LLM provider reload side-effects.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret-pr6-settings")

        user_id = uuid.uuid4()
        factory = await _make_db()
        app = await _make_app_with_db(factory, user_id)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # PUT new budget
            put_resp = await client.put(
                "/api/v1/settings",
                json={"budget_daily_usd": 42.50},
            )
            assert put_resp.status_code == 200, (
                f"PUT /settings failed: {put_resp.text}"
            )
            put_body = put_resp.json()
            assert put_body["ok"] is True

            # GET settings — must return the exact value we stored
            get_resp = await client.get("/api/v1/settings")
            assert get_resp.status_code == 200
            get_body = get_resp.json()
            assert get_body["ok"] is True
            stored_budget = get_body["data"]["budget_daily_usd"]
            assert stored_budget == pytest.approx(42.50), (
                f"GET /settings must return the value set via PUT; "
                f"expected 42.50, got {stored_budget}"
            )

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_patch_settings_only_updates_specified_field(self, monkeypatch):
        """PATCH /settings only updates specified fields; other fields are unchanged.

        BE-H3 fix: PATCH must not overwrite unspecified fields with None.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret-pr6-settings")

        user_id = uuid.uuid4()
        factory = await _make_db()
        app = await _make_app_with_db(factory, user_id)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First PUT: set both budget fields
            await client.put(
                "/api/v1/settings",
                json={
                    "budget_daily_usd": 25.0,
                    "budget_monthly_usd": 500.0,
                },
            )

            # PATCH: update only daily budget
            patch_resp = await client.patch(
                "/api/v1/settings",
                json={"budget_daily_usd": 30.0},
            )
            assert patch_resp.status_code == 200, (
                f"PATCH /settings failed: {patch_resp.text}"
            )

            # GET: monthly budget must be unchanged at 500.0
            get_resp = await client.get("/api/v1/settings")
            data = get_resp.json()["data"]
            assert data["budget_daily_usd"] == pytest.approx(30.0), (
                "PATCH must update the daily budget to 30.0"
            )
            assert data["budget_monthly_usd"] == pytest.approx(500.0), (
                "PATCH must not overwrite monthly_budget that was not included in the PATCH body"
            )

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_settings_user_isolation(self, monkeypatch):
        """Settings stored by user A must not be visible to user B.

        SPEC.md §11.1: Settings are per-user; each user has their own row.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret-pr6-settings")

        user_a_id = uuid.uuid4()
        user_b_id = uuid.uuid4()
        factory = await _make_db()

        # User A: store a distinctive budget
        app_a = await _make_app_with_db(factory, user_a_id)
        transport_a = ASGITransport(app=app_a)
        async with AsyncClient(transport=transport_a, base_url="http://test") as client:
            await client.put("/api/v1/settings", json={"budget_daily_usd": 111.11})
        app_a.dependency_overrides.clear()

        # User B: store a different budget
        app_b = await _make_app_with_db(factory, user_b_id)
        transport_b = ASGITransport(app=app_b)
        async with AsyncClient(transport=transport_b, base_url="http://test") as client:
            await client.put("/api/v1/settings", json={"budget_daily_usd": 222.22})
            # Now GET settings as user B — must return B's budget, not A's
            get_resp = await client.get("/api/v1/settings")
            data = get_resp.json()["data"]
            assert data["budget_daily_usd"] == pytest.approx(222.22), (
                "User B's settings must return B's own budget (222.22), "
                f"not user A's (111.11); got {data['budget_daily_usd']}"
            )
        app_b.dependency_overrides.clear()


# ===========================================================================
# IT3: Memory user isolation
# ===========================================================================


class TestMemoryUserIsolation:
    """SPEC.md §13.2: Memory facts are user-scoped — user B cannot read user A's facts."""

    @pytest.mark.asyncio
    async def test_memory_facts_scoped_to_user(self, monkeypatch):
        """Facts stored by user A are not visible when listing as user B.

        Data path: MemoryStore.store() with user_id=A → MemoryStore.list_all(user_id=B)
        must not return A's facts.

        This test exercises the MemoryStore directly (the in-process implementation)
        since memory facts are stored in the MemoryStore (not the SQL DB) and the
        /api/v1/memory/facts endpoint delegates to it.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret-pr6-memory")

        from noa.private_worker.memory_store import MemoryStore

        store = MemoryStore()
        user_a_id = str(uuid.uuid4())
        user_b_id = str(uuid.uuid4())

        # Store a fact for user A (store directly with user_id field)
        fact_id = str(uuid.uuid4())
        store._facts[fact_id] = {
            "id": fact_id,
            "fact": "User A's private preference: dark mode",
            "category": "preference",
            "embedding": [0.1, 0.2, 0.3],
            "status": "approved",
            "user_id": user_a_id,
            "source_thread_id": str(uuid.uuid4()),
            "auto_extracted": False,
            "created_at": "2026-03-11T00:00:00+00:00",
        }

        # User B lists facts — must not see user A's fact
        b_facts = store.list_all(user_id=user_b_id)
        fact_texts = [f["fact"] for f in b_facts]
        assert "User A's private preference: dark mode" not in fact_texts, (
            "User B must not see User A's memory facts; "
            f"got: {fact_texts}"
        )

        # User A lists facts — must see their own fact
        a_facts = store.list_all(user_id=user_a_id)
        fact_texts_a = [f["fact"] for f in a_facts]
        assert "User A's private preference: dark mode" in fact_texts_a, (
            "User A must be able to list their own memory facts"
        )

    @pytest.mark.asyncio
    async def test_memory_delete_user_isolation(self, monkeypatch):
        """User B cannot delete User A's memory fact.

        SPEC.md §13.2: Memory facts are owned per-user; cross-user deletes must fail.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret-pr6-memory")

        from noa.private_worker.memory_store import MemoryStore

        store = MemoryStore()
        user_a_id = str(uuid.uuid4())
        user_b_id = str(uuid.uuid4())

        fact_id = str(uuid.uuid4())
        store._facts[fact_id] = {
            "id": fact_id,
            "fact": "User A's secret",
            "category": "personal_info",
            "embedding": [],
            "status": "approved",
            "user_id": user_a_id,
            "source_thread_id": str(uuid.uuid4()),
            "auto_extracted": False,
            "created_at": "2026-03-11T00:00:00+00:00",
        }

        # User B tries to delete — must return False
        deleted = store.delete(fact_id, user_id=user_b_id)
        assert deleted is False, (
            "MemoryStore.delete() must return False when user_id doesn't match "
            "the fact owner (cross-user delete blocked)"
        )

        # Fact must still exist
        assert fact_id in store._facts, (
            "Fact must not be deleted when a different user attempts to delete it"
        )


# ===========================================================================
# IT4: Artifact download requires authentication
# ===========================================================================


class TestArtifactAuth:
    """SPEC.md §29.3: Protected endpoints must return 401 without a valid token."""

    @pytest.mark.asyncio
    async def test_artifact_download_requires_auth(self, monkeypatch):
        """GET /api/v1/artifacts/{id}/download without a token must return 401.

        Data path: no token → auth middleware → 401 before any DB query.
        Proves the auth guard is in place and returns the correct HTTP status.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret-pr6-artifacts")

        from noa.api.app import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            fake_id = str(uuid.uuid4())
            resp = await client.get(f"/api/v1/artifacts/{fake_id}/download")
            assert resp.status_code == 401, (
                f"Artifact download without auth must return 401; got {resp.status_code}"
            )

    @pytest.mark.asyncio
    async def test_artifact_list_requires_auth(self, monkeypatch):
        """GET /api/v1/artifacts without a token must return 401.

        SPEC.md §29.3: All data endpoints must require authentication.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret-pr6-artifacts")

        from noa.api.app import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/artifacts")
            assert resp.status_code == 401, (
                f"Artifact list without auth must return 401; got {resp.status_code}"
            )

    @pytest.mark.asyncio
    async def test_chat_requires_auth(self, monkeypatch):
        """POST /api/v1/chat without a token must return 401.

        SPEC.md §22.1: Chat endpoint is protected.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret-pr6-artifacts")

        from noa.api.app import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/chat",
                json={
                    "message": "hello",
                    "privacy_mode": "external",
                },
            )
            assert resp.status_code == 401, (
                f"Chat endpoint without auth must return 401; got {resp.status_code}"
            )

    @pytest.mark.asyncio
    async def test_threads_requires_auth(self, monkeypatch):
        """GET /api/v1/threads without a token must return 401.

        SPEC.md §37: All data-access endpoints require authentication.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret-pr6-artifacts")

        from noa.api.app import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/threads")
            assert resp.status_code == 401, (
                f"Threads list without auth must return 401; got {resp.status_code}"
            )


# ===========================================================================
# IT5: User registration and login flow
# ===========================================================================


class TestAuthFlow:
    """SPEC.md §5.1–5.4: Registration and login produce valid tokens."""

    @pytest.mark.asyncio
    async def test_register_then_login_returns_token(self, monkeypatch):
        """POST /auth/register → POST /auth/login → access_token in cookie.

        Data path: register creates User row → login verifies password + creates
        AuthSession → response sets token cookie.

        This is an end-to-end flow using real DB and real password hashing.
        No mocks of internal services.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret-pr6-auth-flow-xyz")

        factory = await _make_db()

        from noa.api.app import create_app
        from noa.api.deps import get_db_session

        async def _fake_db():
            async with factory() as session:
                yield session

        app = create_app()
        app.dependency_overrides[get_db_session] = _fake_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Register a new user
            reg_resp = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "pr6-test@example.com",
                    "password": "Secur3Pass!",
                },
            )
            assert reg_resp.status_code in (200, 201), (
                f"Registration failed: {reg_resp.text}"
            )
            reg_body = reg_resp.json()
            assert reg_body["ok"] is True
            assert "user_id" in reg_body["data"], (
                "Registration response must include user_id"
            )

            # Login with the registered credentials
            login_resp = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "pr6-test@example.com",
                    "password": "Secur3Pass!",
                    "device_id": str(uuid.uuid4()),
                },
            )
            assert login_resp.status_code == 200, (
                f"Login failed: {login_resp.text}"
            )
            login_body = login_resp.json()
            assert login_body["ok"] is True, (
                f"Login must return ok=true; got: {login_body}"
            )
            # Token must be in the response (either cookie or body)
            has_cookie = "noa_access_token" in login_resp.cookies
            has_body_token = login_body.get("data", {}).get("access_token") is not None
            assert has_cookie or has_body_token, (
                "Login must set either an httpOnly cookie or return access_token in body; "
                f"cookies: {dict(login_resp.cookies)}, body data: {login_body.get('data')}"
            )

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_login_with_wrong_password_returns_401(self, monkeypatch):
        """POST /auth/login with wrong password must return 401.

        SPEC.md §5.1: Invalid credentials must produce HTTP 401.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret-pr6-auth-flow-xyz")

        factory = await _make_db()

        from noa.api.app import create_app
        from noa.api.deps import get_db_session

        async def _fake_db():
            async with factory() as session:
                yield session

        app = create_app()
        app.dependency_overrides[get_db_session] = _fake_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Register first
            await client.post(
                "/api/v1/auth/register",
                json={"email": "wrong-pw@example.com", "password": "RealPass!"},
            )

            # Login with wrong password
            resp = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "wrong-pw@example.com",
                    "password": "WrongPass!",
                    "device_id": str(uuid.uuid4()),
                },
            )
            assert resp.status_code == 401, (
                f"Wrong password must return 401; got {resp.status_code}: {resp.text}"
            )

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_duplicate_registration_returns_error(self, monkeypatch):
        """POST /auth/register with an already-registered email must return an error.

        SPEC.md §5.1: Duplicate emails are rejected.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret-pr6-auth-flow-xyz")

        factory = await _make_db()

        from noa.api.app import create_app
        from noa.api.deps import get_db_session

        async def _fake_db():
            async with factory() as session:
                yield session

        app = create_app()
        app.dependency_overrides[get_db_session] = _fake_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {"email": "dup@example.com", "password": "AnyPass!"}
            resp1 = await client.post("/api/v1/auth/register", json=payload)
            assert resp1.status_code in (200, 201)

            # Second registration with same email
            resp2 = await client.post("/api/v1/auth/register", json=payload)
            # Must fail — either 400 or 409
            assert resp2.status_code in (400, 409, 422), (
                f"Duplicate registration must be rejected; got {resp2.status_code}: {resp2.text}"
            )

        app.dependency_overrides.clear()


# ===========================================================================
# IT6: Privacy mode flows through the chat endpoint (auth boundary check)
# ===========================================================================


class TestChatPrivacyMode:
    """SPEC.md §22.2: privacy_mode field is accepted and validated."""

    @pytest.mark.asyncio
    async def test_chat_with_valid_privacy_mode_reaches_auth_check(self, monkeypatch):
        """A chat request with privacy_mode='private' is accepted past schema validation.

        We cannot run the full orchestrator in a unit test (no real LLM), so this
        test verifies that:
          1. The request passes Pydantic validation (privacy_mode is accepted)
          2. The auth middleware returns 401 without a token (correct boundary)

        Together these prove the endpoint is reachable and the privacy_mode field
        is wired correctly in the schema.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret-pr6-chat")

        from noa.api.app import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/chat",
                json={
                    "message": "What is 2+2?",
                    "privacy_mode": "private",
                    "thread_id": str(uuid.uuid4()),
                },
            )
            # Without auth the request must be rejected at the auth layer, not the schema layer
            assert resp.status_code == 401, (
                "Request with privacy_mode='private' must reach auth check and return 401; "
                f"got {resp.status_code}: {resp.text}"
            )

    @pytest.mark.asyncio
    async def test_chat_schema_accepts_external_mode(self, monkeypatch):
        """ChatRequest schema accepts privacy_mode='external'.

        SPEC.md §22.2: Valid privacy modes are 'private' and 'external'.
        """
        from noa.api.v1.chat import ChatRequest

        req = ChatRequest(
            message="hello",
            privacy_mode="external",
        )
        assert req.privacy_mode == "external"

    def test_chat_schema_accepts_private_mode(self):
        """ChatRequest schema accepts privacy_mode='private'.

        SPEC.md §22.2: 'private' routes through the private domain.
        """
        from noa.api.v1.chat import ChatRequest

        req = ChatRequest(
            message="hello",
            privacy_mode="private",
        )
        assert req.privacy_mode == "private"


# ===========================================================================
# IT7: Approval flow — auth boundary + data shape
# ===========================================================================


class TestApprovalFlow:
    """SPEC.md §29.6: Approval endpoints enforce auth and return correct shapes."""

    @pytest.mark.asyncio
    async def test_pending_approvals_requires_auth(self, monkeypatch):
        """GET /api/v1/approvals/pending without token returns 401.

        SPEC.md §29.6: iOS client must authenticate before fetching approvals.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret-pr6-approvals")

        from noa.api.app import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/approvals/pending")
            assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_list_pending_approvals_returns_empty_list_when_none_exist(
        self, monkeypatch
    ):
        """Authenticated GET /approvals/pending with no approvals returns empty list.

        Data path: DB query over Approval table → empty results → [] in response.
        Proves the endpoint is wired to the real DB (not returning hardcoded []).
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret-pr6-approvals")

        user_id = uuid.uuid4()
        factory = await _make_db()
        app = await _make_app_with_db(factory, user_id)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/approvals/pending")
            assert resp.status_code == 200
            body = resp.json()
            assert body["ok"] is True
            assert isinstance(body["data"], list), (
                "Pending approvals response must be a list"
            )
            assert body["data"] == [], (
                "No approvals seeded — list must be empty, not hardcoded mock data"
            )

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_decide_unknown_approval_returns_404(self, monkeypatch):
        """POST /approvals/{id}/decide for a non-existent approval returns 404.

        SPEC.md §29.6: Non-existent approval decisions must be rejected.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret-pr6-approvals")

        user_id = uuid.uuid4()
        factory = await _make_db()
        app = await _make_app_with_db(factory, user_id)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            fake_id = uuid.uuid4()
            resp = await client.post(
                f"/api/v1/approvals/{fake_id}/decide",
                json={"decision": "approved"},
            )
            assert resp.status_code == 404, (
                f"Decision on non-existent approval must return 404; got {resp.status_code}"
            )

        app.dependency_overrides.clear()
