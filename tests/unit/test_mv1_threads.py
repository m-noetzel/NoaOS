"""MV1: Threads & Messages Real DB Queries — unit tests.

Spec refs: SPEC.md §10.1 (Conversation/Message models)
Phase plan: PHASE_DETAILS.md Phase MV1

Tests verify that:
  - list_threads() queries the real DB (not stubs)
  - list_messages() queries the real DB and enforces user ownership (404)
  - create_thread() persists a new Conversation row
  - delete_thread() removes the Conversation row (and returns 404 for wrong user)

All tests use in-memory SQLite with seeded data following the same pattern
as test_ios11_integration_polish.py TestApprovalDecideResponseShape.
"""

# ruff: noqa: S105, S106, E501
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.mv1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_thread_db(
    *,
    user_id: uuid.UUID | None = None,
    thread_id: uuid.UUID | None = None,
    title: str = "Test Thread",
    add_messages: int = 0,
    other_user_id: uuid.UUID | None = None,
):
    """Create an in-memory async SQLite DB.

    Optionally seeds one Conversation belonging to ``user_id`` (and ``other_user_id``
    if supplied) and ``add_messages`` Message rows for that conversation.
    SQLite does not enforce FK constraints without PRAGMA, so we skip User rows.

    Returns (factory, user_id, thread_id).
    """
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    from noa.db.models.base import Base
    from noa.db.models.conversation import Conversation, Message

    uid = user_id or uuid.uuid4()
    tid = thread_id or uuid.uuid4()

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        conv = Conversation(id=tid, user_id=uid, title=title)
        session.add(conv)

        for i in range(add_messages):
            msg = Message(
                thread_id=tid,
                user_id=uid,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
                timestamp=datetime(2026, 3, 10, 12, 0, i, tzinfo=UTC),
            )
            session.add(msg)

        if other_user_id is not None:
            other_conv = Conversation(
                id=uuid.uuid4(), user_id=other_user_id, title="Other user thread"
            )
            session.add(other_conv)

        await session.commit()

    return factory, uid, tid


def _build_app_with_overrides(factory, user_id: uuid.UUID):
    """Return a FastAPI app with auth + DB overrides applied."""
    from noa.api.app import create_app
    from noa.api.deps import get_db_session
    from noa.auth.middleware import AuthUser, require_auth

    app = create_app()

    async def _fake_auth():
        return AuthUser(user_id=user_id, session_id=uuid.uuid4())

    async def _fake_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[require_auth] = _fake_auth
    app.dependency_overrides[get_db_session] = _fake_db
    return app


# ---------------------------------------------------------------------------
# list_threads tests
# ---------------------------------------------------------------------------


class TestListThreads:
    """GET /api/v1/threads — real DB queries."""

    @pytest.mark.asyncio
    async def test_empty_db_returns_empty_list(self, monkeypatch):
        """Empty DB → list_threads returns []."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")

        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )

        from noa.db.models.base import Base

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        user_id = uuid.uuid4()

        app = _build_app_with_overrides(factory, user_id)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/threads")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["data"] == []

    @pytest.mark.asyncio
    async def test_seeded_thread_visible_in_list(self, monkeypatch):
        """After inserting a Conversation, it appears in list_threads."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")

        user_id = uuid.uuid4()
        thread_id = uuid.uuid4()
        factory, uid, tid = await _make_thread_db(
            user_id=user_id, thread_id=thread_id, title="My Chat"
        )

        app = _build_app_with_overrides(factory, uid)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/threads")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        data = body["data"]
        assert len(data) == 1
        assert data[0]["id"] == str(tid)
        assert data[0]["title"] == "My Chat"
        assert "created_at" in data[0]
        assert "updated_at" in data[0]

    @pytest.mark.asyncio
    async def test_wrong_user_thread_not_visible(self, monkeypatch):
        """Threads belonging to another user are NOT returned."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")

        owner_id = uuid.uuid4()
        requester_id = uuid.uuid4()
        factory, _, tid = await _make_thread_db(user_id=owner_id, title="Private Thread")

        app = _build_app_with_overrides(factory, requester_id)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/threads")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body["data"] == [], "Other user's thread must not be returned"

    @pytest.mark.asyncio
    async def test_multiple_threads_returned_ordered_desc(self, monkeypatch):
        """Multiple threads are returned; most recently created comes first."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")

        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )

        from noa.db.models.base import Base
        from noa.db.models.conversation import Conversation

        user_id = uuid.uuid4()
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with factory() as session:
            for i in range(3):
                conv = Conversation(
                    user_id=user_id,
                    title=f"Thread {i}",
                    created_at=datetime(2026, 3, 10, 12, 0, i, tzinfo=UTC),
                )
                session.add(conv)
            await session.commit()

        app = _build_app_with_overrides(factory, user_id)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/threads")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 3
        # Most recently created (Thread 2) should be first
        assert data[0]["title"] == "Thread 2"
        assert data[-1]["title"] == "Thread 0"


# ---------------------------------------------------------------------------
# list_messages tests
# ---------------------------------------------------------------------------


class TestListMessages:
    """GET /api/v1/threads/{thread_id}/messages — real DB queries."""

    @pytest.mark.asyncio
    async def test_empty_thread_returns_empty_list(self, monkeypatch):
        """Thread with no messages → list_messages returns []."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")

        user_id = uuid.uuid4()
        factory, uid, tid = await _make_thread_db(user_id=user_id, add_messages=0)

        app = _build_app_with_overrides(factory, uid)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/threads/{tid}/messages")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["data"] == []

    @pytest.mark.asyncio
    async def test_messages_returned_ordered_asc(self, monkeypatch):
        """Messages are returned in ascending timestamp order."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")

        user_id = uuid.uuid4()
        factory, uid, tid = await _make_thread_db(
            user_id=user_id, add_messages=3
        )

        app = _build_app_with_overrides(factory, uid)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/threads/{tid}/messages")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 3
        # Verify ascending order by created_at
        timestamps = [m["created_at"] for m in data]
        assert timestamps == sorted(timestamps)

    @pytest.mark.asyncio
    async def test_message_fields_present(self, monkeypatch):
        """Each message has id, role, content, created_at fields."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")

        user_id = uuid.uuid4()
        factory, uid, tid = await _make_thread_db(
            user_id=user_id, add_messages=1
        )

        app = _build_app_with_overrides(factory, uid)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/threads/{tid}/messages")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 1
        msg = data[0]
        assert "id" in msg
        assert "role" in msg
        assert "content" in msg
        assert "created_at" in msg
        assert msg["role"] == "user"
        assert msg["content"] == "Message 0"

    @pytest.mark.asyncio
    async def test_wrong_thread_id_returns_404(self, monkeypatch):
        """Requesting messages for a non-existent thread_id returns 404."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")

        user_id = uuid.uuid4()
        factory, uid, _ = await _make_thread_db(user_id=user_id)

        nonexistent_tid = uuid.uuid4()
        app = _build_app_with_overrides(factory, uid)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/threads/{nonexistent_tid}/messages")
        app.dependency_overrides.clear()

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_wrong_user_thread_returns_404(self, monkeypatch):
        """Accessing another user's thread for messages returns 404."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")

        owner_id = uuid.uuid4()
        requester_id = uuid.uuid4()
        factory, _, tid = await _make_thread_db(user_id=owner_id, add_messages=2)

        app = _build_app_with_overrides(factory, requester_id)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/threads/{tid}/messages")
        app.dependency_overrides.clear()

        assert response.status_code == 404, (
            "Requesting messages for another user's thread must return 404, "
            f"got {response.status_code}"
        )


# ---------------------------------------------------------------------------
# create_thread tests
# ---------------------------------------------------------------------------


class TestCreateThread:
    """POST /api/v1/threads — persists a new Conversation row."""

    @pytest.mark.asyncio
    async def test_create_thread_returns_created_data(self, monkeypatch):
        """POST /threads returns id, title, created_at, updated_at."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")

        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )

        from noa.db.models.base import Base

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        user_id = uuid.uuid4()

        app = _build_app_with_overrides(factory, user_id)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/threads", json={"title": "New Thread"})
        app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        data = body["data"]
        assert "id" in data
        assert data["title"] == "New Thread"
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_created_thread_visible_in_list(self, monkeypatch):
        """Thread created via POST is subsequently returned by GET /threads."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")

        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )

        from noa.db.models.base import Base

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        user_id = uuid.uuid4()

        app = _build_app_with_overrides(factory, user_id)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_resp = await client.post(
                "/api/v1/threads", json={"title": "Persistent Thread"}
            )
            list_resp = await client.get("/api/v1/threads")
        app.dependency_overrides.clear()

        assert create_resp.status_code == 200
        created_id = create_resp.json()["data"]["id"]

        assert list_resp.status_code == 200
        ids = [t["id"] for t in list_resp.json()["data"]]
        assert created_id in ids, "Newly created thread must appear in GET /threads"


# ---------------------------------------------------------------------------
# delete_thread tests
# ---------------------------------------------------------------------------


class TestDeleteThread:
    """DELETE /api/v1/threads/{thread_id} — removes Conversation row."""

    @pytest.mark.asyncio
    async def test_delete_thread_returns_deleted_id(self, monkeypatch):
        """DELETE returns envelope with deleted thread id."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")

        user_id = uuid.uuid4()
        factory, uid, tid = await _make_thread_db(user_id=user_id)

        app = _build_app_with_overrides(factory, uid)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(f"/api/v1/threads/{tid}")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["data"]["deleted"] == str(tid)

    @pytest.mark.asyncio
    async def test_delete_wrong_user_thread_returns_404(self, monkeypatch):
        """DELETE for another user's thread returns 404."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")

        owner_id = uuid.uuid4()
        requester_id = uuid.uuid4()
        factory, _, tid = await _make_thread_db(user_id=owner_id)

        app = _build_app_with_overrides(factory, requester_id)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(f"/api/v1/threads/{tid}")
        app.dependency_overrides.clear()

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# run_id propagation tests (rating-button fix)
# ---------------------------------------------------------------------------


class TestRunIdInMessages:
    """Verify run_id is stored on Message rows and returned by list_messages.

    Root cause: RatingButtons in the frontend returns null when runId is
    undefined.  Fix: persist run_id on every Message and include it in
    the GET /threads/{id}/messages response.
    """

    @pytest.mark.asyncio
    async def test_run_id_returned_in_messages_list(self, monkeypatch):
        """Messages with a run_id must expose that field in the API response."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")

        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )

        from noa.db.models.base import Base
        from noa.db.models.conversation import Conversation, Message

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        user_id = uuid.uuid4()
        thread_id = uuid.uuid4()
        run_id = str(uuid.uuid4())

        async with factory() as session:
            session.add(Conversation(id=thread_id, user_id=user_id, title="T"))
            session.add(Message(
                thread_id=thread_id,
                user_id=user_id,
                role="user",
                content="Hello",
                run_id=run_id,
            ))
            session.add(Message(
                thread_id=thread_id,
                user_id=user_id,
                role="assistant",
                content="Hi there!",
                run_id=run_id,
            ))
            await session.commit()

        app = _build_app_with_overrides(factory, user_id)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/threads/{thread_id}/messages",
                params={"privacy_mode": "external"},
            )
        app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        messages = body["data"]
        assert len(messages) == 2
        for msg in messages:
            assert "run_id" in msg, "run_id must be present in each message object"
            assert msg["run_id"] == run_id, "run_id value must match what was stored"

    @pytest.mark.asyncio
    async def test_run_id_none_when_not_set(self, monkeypatch):
        """Messages without a run_id expose null (not missing key) in the response."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")

        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )

        from noa.db.models.base import Base
        from noa.db.models.conversation import Conversation, Message

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        user_id = uuid.uuid4()
        thread_id = uuid.uuid4()

        async with factory() as session:
            session.add(Conversation(id=thread_id, user_id=user_id, title="T"))
            session.add(Message(
                thread_id=thread_id,
                user_id=user_id,
                role="user",
                content="Old message without run_id",
            ))
            await session.commit()

        app = _build_app_with_overrides(factory, user_id)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/threads/{thread_id}/messages",
                params={"privacy_mode": "external"},
            )
        app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        messages = body["data"]
        assert len(messages) == 1
        assert "run_id" in messages[0], "run_id key must always be present"
        assert messages[0]["run_id"] is None
