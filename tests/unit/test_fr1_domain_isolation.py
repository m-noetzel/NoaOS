"""FR1: Domain Isolation & Privacy Enforcement — tests.

Spec refs: SPEC.md §4.1 (domain isolation), §8.3 (privacy enforcement)
Phase: FR1

Findings resolved: BE-C3, BE-H8, BE-H11

Test plan:
  Happy paths:
    - Thread created in private mode has domain="private"
    - Thread created in external mode has domain="external"
    - list_threads with privacy_mode=private returns only private threads
    - list_threads with privacy_mode=external returns only external threads
    - Memory tool listed in private mode
    - All providers returned in external mode, only ollama in private mode
  Negative paths:
    - list_threads with privacy_mode=private does NOT return external threads
    - list_threads with privacy_mode=external does NOT return private threads
    - Cannot access messages of private thread in external mode (403)
    - Cannot access messages of external thread in private mode (403)
    - Memory tool hidden in external mode (BE-H8)
    - External providers hidden in private mode (BE-H11)
  Integration:
    - Chat endpoint with existing thread_id + mismatched domain returns 403
    - New thread via chat inherits privacy_mode as domain
  Tool gateway:
    - Dispatching memory tool in external mode raises PermissionError (pre-existing, verify)
"""

# ruff: noqa: S105, S106, E501
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.fr1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_db_with_threads(
    *,
    user_id: uuid.UUID | None = None,
    private_thread_id: uuid.UUID | None = None,
    external_thread_id: uuid.UUID | None = None,
):
    """Create an in-memory SQLite DB seeded with one private and one external thread.

    Returns (factory, user_id, private_tid, external_tid).
    """
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    from noa.db.models.base import Base
    from noa.db.models.conversation import Conversation

    uid = user_id or uuid.uuid4()
    priv_tid = private_thread_id or uuid.uuid4()
    ext_tid = external_thread_id or uuid.uuid4()

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        session.add(Conversation(id=priv_tid, user_id=uid, title="Private Thread", domain="private"))
        session.add(Conversation(id=ext_tid, user_id=uid, title="External Thread", domain="external"))
        await session.commit()

    return factory, uid, priv_tid, ext_tid


async def _make_empty_db():
    """Create an empty in-memory SQLite DB."""
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    from noa.db.models.base import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _build_app(factory, user_id: uuid.UUID):
    """Build a test FastAPI app with auth + DB overrides."""
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


def _patch_tools_auth(factory, user_id: uuid.UUID):
    """Monkey-patch the tools module's require_auth and get_db_session.

    The tools router uses its own patchable require_auth (not the global one),
    so we must monkey-patch it directly on the module.
    """
    from noa.api.v1 import tools as tools_mod
    from noa.auth.middleware import AuthUser

    original_auth = tools_mod.require_auth
    original_db = tools_mod.get_db_session

    async def _fake_auth():
        return AuthUser(user_id=user_id, session_id=uuid.uuid4())

    async def _fake_db():
        async with factory() as session:
            yield session

    tools_mod.require_auth = _fake_auth  # type: ignore[assignment]
    tools_mod.get_db_session = _fake_db  # type: ignore[assignment]

    return tools_mod, original_auth, original_db


# ---------------------------------------------------------------------------
# BE-C3: Thread domain scoping — list_threads
# ---------------------------------------------------------------------------


class TestListThreadsDomainFiltering:
    """GET /api/v1/threads?privacy_mode=X — only returns threads in that domain."""

    @pytest.mark.asyncio
    async def test_list_private_threads_excludes_external(self, monkeypatch):
        """list_threads with privacy_mode=private must not return external threads."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory, uid, priv_tid, ext_tid = await _make_db_with_threads()
        app = _build_app(factory, uid)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/threads?privacy_mode=private")

        assert resp.status_code == 200
        data = resp.json()["data"]
        ids = [t["id"] for t in data]
        assert str(priv_tid) in ids
        assert str(ext_tid) not in ids

    @pytest.mark.asyncio
    async def test_list_external_threads_excludes_private(self, monkeypatch):
        """list_threads with privacy_mode=external must not return private threads."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory, uid, priv_tid, ext_tid = await _make_db_with_threads()
        app = _build_app(factory, uid)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/threads?privacy_mode=external")

        assert resp.status_code == 200
        data = resp.json()["data"]
        ids = [t["id"] for t in data]
        assert str(ext_tid) in ids
        assert str(priv_tid) not in ids

    @pytest.mark.asyncio
    async def test_list_threads_default_is_external(self, monkeypatch):
        """list_threads without privacy_mode defaults to external domain."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory, uid, priv_tid, ext_tid = await _make_db_with_threads()
        app = _build_app(factory, uid)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/threads")

        assert resp.status_code == 200
        data = resp.json()["data"]
        ids = [t["id"] for t in data]
        assert str(ext_tid) in ids
        assert str(priv_tid) not in ids


# ---------------------------------------------------------------------------
# BE-C3: Thread creation — domain stored on conversation
# ---------------------------------------------------------------------------


class TestCreateThreadDomain:
    """POST /api/v1/threads — domain is persisted on the Conversation row."""

    @pytest.mark.asyncio
    async def test_create_private_thread_stores_domain(self, monkeypatch):
        """Creating a thread with domain=private stores domain='private' in DB."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory = await _make_empty_db()
        uid = uuid.uuid4()
        app = _build_app(factory, uid)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/threads",
                json={"title": "Private Thread", "domain": "private"},
            )

        assert resp.status_code == 200
        result = resp.json()["data"]
        assert result["domain"] == "private"

        # Verify persisted in DB
        from sqlalchemy import select

        from noa.db.models.conversation import Conversation

        async with factory() as session:
            row = (await session.execute(select(Conversation))).scalar_one()
        assert row.domain == "private"

    @pytest.mark.asyncio
    async def test_create_external_thread_stores_domain(self, monkeypatch):
        """Creating a thread with domain=external stores domain='external' in DB."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory = await _make_empty_db()
        uid = uuid.uuid4()
        app = _build_app(factory, uid)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/threads",
                json={"title": "External Thread", "domain": "external"},
            )

        assert resp.status_code == 200
        result = resp.json()["data"]
        assert result["domain"] == "external"

    @pytest.mark.asyncio
    async def test_create_thread_default_domain_is_external(self, monkeypatch):
        """Creating a thread without specifying domain defaults to external."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory = await _make_empty_db()
        uid = uuid.uuid4()
        app = _build_app(factory, uid)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/threads",
                json={"title": "New Thread"},
            )

        assert resp.status_code == 200
        result = resp.json()["data"]
        assert result["domain"] == "external"


# ---------------------------------------------------------------------------
# BE-C3: Thread messages — domain mismatch returns 403
# ---------------------------------------------------------------------------


class TestThreadMessagesDomainCheck:
    """GET /api/v1/threads/{id}/messages?privacy_mode=X — 403 on domain mismatch."""

    @pytest.mark.asyncio
    async def test_access_private_thread_in_external_mode_returns_403(self, monkeypatch):
        """Accessing a private thread's messages in external mode returns 403."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory, uid, priv_tid, ext_tid = await _make_db_with_threads()
        app = _build_app(factory, uid)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/api/v1/threads/{priv_tid}/messages?privacy_mode=external"
            )

        assert resp.status_code == 403
        # Error message should reference the domain mismatch
        body_str = str(resp.json()).lower()
        assert "domain" in body_str

    @pytest.mark.asyncio
    async def test_access_external_thread_in_private_mode_returns_403(self, monkeypatch):
        """Accessing an external thread's messages in private mode returns 403."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory, uid, priv_tid, ext_tid = await _make_db_with_threads()
        app = _build_app(factory, uid)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/api/v1/threads/{ext_tid}/messages?privacy_mode=private"
            )

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_access_private_thread_in_private_mode_succeeds(self, monkeypatch):
        """Accessing a private thread's messages in private mode succeeds."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory, uid, priv_tid, ext_tid = await _make_db_with_threads()
        app = _build_app(factory, uid)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/api/v1/threads/{priv_tid}/messages?privacy_mode=private"
            )

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_access_external_thread_in_external_mode_succeeds(self, monkeypatch):
        """Accessing an external thread's messages in external mode succeeds."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory, uid, priv_tid, ext_tid = await _make_db_with_threads()
        app = _build_app(factory, uid)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/api/v1/threads/{ext_tid}/messages?privacy_mode=external"
            )

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# BE-C3: DELETE /{thread_id} — domain check
# ---------------------------------------------------------------------------


class TestDeleteThreadDomainCheck:
    """DELETE /api/v1/threads/{id}?privacy_mode=X — 403 on domain mismatch."""

    @pytest.mark.asyncio
    async def test_delete_private_thread_in_external_mode_returns_403(self, monkeypatch):
        """Deleting a private thread in external mode returns 403."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory, uid, priv_tid, ext_tid = await _make_db_with_threads()
        app = _build_app(factory, uid)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(
                f"/api/v1/threads/{priv_tid}?privacy_mode=external"
            )

        assert resp.status_code == 403
        body_str = str(resp.json()).lower()
        assert "domain" in body_str

    @pytest.mark.asyncio
    async def test_delete_external_thread_in_private_mode_returns_403(self, monkeypatch):
        """Deleting an external thread in private mode returns 403."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory, uid, priv_tid, ext_tid = await _make_db_with_threads()
        app = _build_app(factory, uid)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(
                f"/api/v1/threads/{ext_tid}?privacy_mode=private"
            )

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_private_thread_in_private_mode_succeeds(self, monkeypatch):
        """Deleting a private thread in private mode succeeds."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory, uid, priv_tid, ext_tid = await _make_db_with_threads()
        app = _build_app(factory, uid)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(
                f"/api/v1/threads/{priv_tid}?privacy_mode=private"
            )

        assert resp.status_code == 200
        assert resp.json()["data"]["deleted"] == str(priv_tid)

    @pytest.mark.asyncio
    async def test_delete_external_thread_in_external_mode_succeeds(self, monkeypatch):
        """Deleting an external thread in external mode succeeds."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory, uid, priv_tid, ext_tid = await _make_db_with_threads()
        app = _build_app(factory, uid)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(
                f"/api/v1/threads/{ext_tid}?privacy_mode=external"
            )

        assert resp.status_code == 200
        assert resp.json()["data"]["deleted"] == str(ext_tid)


# ---------------------------------------------------------------------------
# BE-H8: Memory tool hidden in external mode
# ---------------------------------------------------------------------------


class TestToolDomainFiltering:
    """GET /api/v1/tools?privacy_mode=X — memory tool filtered by domain.

    The tools router has its own patchable require_auth (see tools.py),
    so we must monkey-patch it directly.
    """

    @pytest.mark.asyncio
    async def test_memory_tool_excluded_in_external_mode(self, monkeypatch):
        """Memory tool (domain=private) must not appear in external mode."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory = await _make_empty_db()
        uid = uuid.uuid4()

        tools_mod, orig_auth, orig_db = _patch_tools_auth(factory, uid)
        try:
            app = _build_app(factory, uid)
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/tools?privacy_mode=external")
        finally:
            tools_mod.require_auth = orig_auth
            tools_mod.get_db_session = orig_db

        assert resp.status_code == 200
        tool_names = [t["name"] for t in resp.json()["data"]]
        assert "memory" not in tool_names

    @pytest.mark.asyncio
    async def test_memory_tool_included_in_private_mode(self, monkeypatch):
        """Memory tool (domain=private) must appear in private mode."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory = await _make_empty_db()
        uid = uuid.uuid4()

        tools_mod, orig_auth, orig_db = _patch_tools_auth(factory, uid)
        try:
            app = _build_app(factory, uid)
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/tools?privacy_mode=private")
        finally:
            tools_mod.require_auth = orig_auth
            tools_mod.get_db_session = orig_db

        assert resp.status_code == 200
        tool_names = [t["name"] for t in resp.json()["data"]]
        assert "memory" in tool_names

    @pytest.mark.asyncio
    async def test_external_tools_excluded_in_private_mode(self, monkeypatch):
        """External tools (web_search, gmail, etc.) must not appear in private mode."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory = await _make_empty_db()
        uid = uuid.uuid4()

        tools_mod, orig_auth, orig_db = _patch_tools_auth(factory, uid)
        try:
            app = _build_app(factory, uid)
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/tools?privacy_mode=private")
        finally:
            tools_mod.require_auth = orig_auth
            tools_mod.get_db_session = orig_db

        assert resp.status_code == 200
        tool_names = [t["name"] for t in resp.json()["data"]]
        # External-only tools should not be listed
        assert "web_search" not in tool_names
        assert "gmail" not in tool_names


# ---------------------------------------------------------------------------
# BE-H8: _tool_is_visible_in_domain unit test
# ---------------------------------------------------------------------------


class TestToolIsVisibleInDomain:
    """Unit tests for _tool_is_visible_in_domain helper."""

    def test_private_only_tool_hidden_in_external(self):
        from noa.api.v1.tools import _tool_is_visible_in_domain

        schema = {"functions": {"f": {"domain": "private"}}}
        assert _tool_is_visible_in_domain(schema, "external") is False

    def test_private_only_tool_visible_in_private(self):
        from noa.api.v1.tools import _tool_is_visible_in_domain

        schema = {"functions": {"f": {"domain": "private"}}}
        assert _tool_is_visible_in_domain(schema, "private") is True

    def test_external_only_tool_visible_in_external(self):
        from noa.api.v1.tools import _tool_is_visible_in_domain

        schema = {"functions": {"f": {"domain": "external"}}}
        assert _tool_is_visible_in_domain(schema, "external") is True

    def test_external_only_tool_hidden_in_private(self):
        from noa.api.v1.tools import _tool_is_visible_in_domain

        schema = {"functions": {"f": {"domain": "external"}}}
        assert _tool_is_visible_in_domain(schema, "private") is False

    def test_mixed_domain_tool_always_visible(self):
        from noa.api.v1.tools import _tool_is_visible_in_domain

        schema = {
            "functions": {
                "f1": {"domain": "private"},
                "f2": {"domain": "external"},
            }
        }
        assert _tool_is_visible_in_domain(schema, "external") is True
        assert _tool_is_visible_in_domain(schema, "private") is True


# ---------------------------------------------------------------------------
# BE-H11: Providers filtered by domain
# ---------------------------------------------------------------------------


class TestProviderDomainFiltering:
    """GET /api/v1/settings/providers?privacy_mode=X — providers filtered by domain."""

    @pytest.mark.asyncio
    async def test_private_mode_returns_only_ollama(self, monkeypatch):
        """In private mode only ollama is returned."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory = await _make_empty_db()
        uid = uuid.uuid4()
        app = _build_app(factory, uid)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/settings/providers?privacy_mode=private")

        assert resp.status_code == 200
        providers = resp.json()["data"]
        names = [p["name"] for p in providers]
        assert names == ["ollama"]

    @pytest.mark.asyncio
    async def test_external_mode_returns_all_providers(self, monkeypatch):
        """In external mode all providers including external ones are returned."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory = await _make_empty_db()
        uid = uuid.uuid4()
        app = _build_app(factory, uid)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/settings/providers?privacy_mode=external")

        assert resp.status_code == 200
        providers = resp.json()["data"]
        names = [p["name"] for p in providers]
        assert "anthropic" in names
        assert "openai" in names
        assert "ollama" in names

    @pytest.mark.asyncio
    async def test_external_providers_not_in_private_mode(self, monkeypatch):
        """anthropic and openai must NOT be returned in private mode."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory = await _make_empty_db()
        uid = uuid.uuid4()
        app = _build_app(factory, uid)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/settings/providers?privacy_mode=private")

        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()["data"]]
        assert "anthropic" not in names
        assert "openai" not in names

    @pytest.mark.asyncio
    async def test_providers_default_to_external_mode(self, monkeypatch):
        """Without privacy_mode param, defaults to external (all providers)."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory = await _make_empty_db()
        uid = uuid.uuid4()
        app = _build_app(factory, uid)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/settings/providers")

        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()["data"]]
        assert "anthropic" in names


# ---------------------------------------------------------------------------
# Tool gateway: memory dispatch blocked in external mode (verify BE-C3)
# ---------------------------------------------------------------------------


class TestToolGatewayDomainEnforcement:
    """ToolGateway dispatches are blocked by domain at runtime."""

    @pytest.mark.asyncio
    async def test_memory_tool_dispatch_blocked_in_external_mode(self):
        """Dispatching memory tool with privacy_mode=external raises PermissionError."""
        from noa.tools.gateway import ToolGateway, ToolRequest, ToolResponse

        class _FakeMemoryAdapter:
            domain = "private"

            async def execute(self, request: ToolRequest) -> ToolResponse:
                return ToolResponse(result={"ok": True})

        gw = ToolGateway()
        gw.register("memory", _FakeMemoryAdapter())  # type: ignore[arg-type]

        req = ToolRequest(
            tool="memory",
            function="remember",
            args={"fact": "test"},
            privacy_mode="external",
        )

        with pytest.raises(PermissionError, match="[Pp]rivate-domain"):
            await gw.dispatch(req)

    @pytest.mark.asyncio
    async def test_memory_tool_dispatch_allowed_in_private_mode(self):
        """Dispatching memory tool with privacy_mode=private succeeds."""
        from noa.tools.gateway import ToolGateway, ToolRequest, ToolResponse

        class _FakeMemoryAdapter:
            domain = "private"

            async def execute(self, request: ToolRequest) -> ToolResponse:
                return ToolResponse(result={"stored": True})

        gw = ToolGateway()
        gw.register("memory", _FakeMemoryAdapter())  # type: ignore[arg-type]

        req = ToolRequest(
            tool="memory",
            function="remember",
            args={"fact": "test"},
            privacy_mode="private",
        )

        resp = await gw.dispatch(req)
        assert resp.error is None
        assert resp.result == {"stored": True}


# ---------------------------------------------------------------------------
# BE-C3: Conversation model domain column
# ---------------------------------------------------------------------------


class TestConversationDomainColumn:
    """Conversation model has a domain column with correct default."""

    @pytest.mark.asyncio
    async def test_conversation_default_domain_is_external(self):
        """Conversation.domain defaults to 'external' when not specified."""
        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )

        from noa.db.models.base import Base
        from noa.db.models.conversation import Conversation

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        uid = uuid.uuid4()

        async with factory() as session:
            conv = Conversation(user_id=uid, title="Test")
            session.add(conv)
            await session.commit()
            await session.refresh(conv)

        assert conv.domain == "external"

    @pytest.mark.asyncio
    async def test_conversation_domain_private_stored_and_retrieved(self):
        """domain='private' is stored and retrieved from DB correctly."""
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )

        from noa.db.models.base import Base
        from noa.db.models.conversation import Conversation

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        uid = uuid.uuid4()

        async with factory() as session:
            conv = Conversation(user_id=uid, title="Private", domain="private")
            session.add(conv)
            await session.commit()
            tid = conv.id

        async with factory() as session:
            row = (
                await session.execute(select(Conversation).where(Conversation.id == tid))
            ).scalar_one()

        assert row.domain == "private"
