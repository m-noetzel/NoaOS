"""FR6 — Tools, Settings & Polish tests.

Tests for:
- UX-H6: Notion credential save auto-grants notion.read capability
- UX-M2: approvals_enabled governance toggle (PATCH /settings)
- UX-M3: Thread rename endpoint (PATCH /api/v1/threads/{id})
- UX-M4: Agent limits saved/loaded via settings (max_tool_calls, max_retries, timeout_seconds)
- UX-M10: Tool scopes GET + PATCH
- L10: Per-function enable/disable wired in Tools page backend

Spec refs: SPEC.md §11, §19 (tool governance), §2.1 (scopes)

Pattern: in-memory SQLite + create_app() + dependency_overrides
"""

# ruff: noqa: S105, S106, E501
from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Shared in-memory DB factory
# ---------------------------------------------------------------------------


async def _make_db():
    """Return (factory, engine) with all tables created."""
    import noa.settings.models  # noqa: F401 — registers UserSettings on Base.metadata
    from noa.db.models.base import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return factory, engine


def _build_app(factory: Any, user_id: uuid.UUID):
    """Minimal app with required routers, auth + DB overridden."""
    from noa.api.app import create_app
    from noa.api.app_state import set_session_factory
    from noa.api.deps import get_db_session
    from noa.auth.middleware import AuthUser, require_auth

    app = create_app()
    set_session_factory(factory)

    async def _fake_auth():
        return AuthUser(user_id=user_id, session_id=uuid.uuid4())

    async def _fake_db():
        async with factory() as sess:
            yield sess

    app.dependency_overrides[require_auth] = _fake_auth
    app.dependency_overrides[get_db_session] = _fake_db
    return app


# ---------------------------------------------------------------------------
# UX-M3: Thread rename — PATCH /api/v1/threads/{thread_id}
# ---------------------------------------------------------------------------


class TestThreadRename:
    """Tests for thread inline rename endpoint."""

    async def test_patch_thread_renames_title(self) -> None:
        """PATCH /threads/{id} updates the thread title."""
        factory, engine = await _make_db()
        user_id = uuid.uuid4()
        app = _build_app(factory, user_id)

        # Create a thread first via the API
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            create_resp = await client.post(
                "/api/v1/threads",
                json={"title": "Original Title"},
                headers={"Authorization": "Bearer fake-token"},
            )
            assert create_resp.status_code == 200
            thread_id = create_resp.json()["data"]["id"]

            # Rename via PATCH
            patch_resp = await client.patch(
                f"/api/v1/threads/{thread_id}",
                json={"title": "Renamed Title"},
                headers={"Authorization": "Bearer fake-token"},
            )
            assert patch_resp.status_code == 200
            data = patch_resp.json()["data"]
            assert data["title"] == "Renamed Title"
            assert data["id"] == thread_id

        await engine.dispose()

    async def test_patch_thread_not_found(self) -> None:
        """PATCH /threads/{unknown_id} returns 404."""
        factory, engine = await _make_db()
        user_id = uuid.uuid4()
        app = _build_app(factory, user_id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            patch_resp = await client.patch(
                f"/api/v1/threads/{uuid.uuid4()}",
                json={"title": "Ghost"},
                headers={"Authorization": "Bearer fake-token"},
            )
            assert patch_resp.status_code == 404

        await engine.dispose()

    async def test_patch_thread_empty_title_rejected(self) -> None:
        """PATCH /threads/{id} with empty title returns 422."""
        factory, engine = await _make_db()
        user_id = uuid.uuid4()
        app = _build_app(factory, user_id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            create_resp = await client.post(
                "/api/v1/threads",
                json={"title": "Has Title"},
                headers={"Authorization": "Bearer fake-token"},
            )
            thread_id = create_resp.json()["data"]["id"]

            patch_resp = await client.patch(
                f"/api/v1/threads/{thread_id}",
                json={"title": "   "},
                headers={"Authorization": "Bearer fake-token"},
            )
            assert patch_resp.status_code == 422

        await engine.dispose()

    async def test_patch_thread_cannot_rename_other_users_thread(self) -> None:
        """PATCH /threads/{id} returns 404 for threads owned by another user."""
        factory, engine = await _make_db()
        owner_id = uuid.uuid4()
        other_user_id = uuid.uuid4()

        # Create thread as owner
        owner_app = _build_app(factory, owner_id)
        async with AsyncClient(transport=ASGITransport(app=owner_app), base_url="http://test") as client:
            create_resp = await client.post(
                "/api/v1/threads",
                json={"title": "Owner's Thread"},
                headers={"Authorization": "Bearer fake-token"},
            )
            thread_id = create_resp.json()["data"]["id"]

        # Try rename as different user
        other_app = _build_app(factory, other_user_id)
        async with AsyncClient(transport=ASGITransport(app=other_app), base_url="http://test") as client:
            patch_resp = await client.patch(
                f"/api/v1/threads/{thread_id}",
                json={"title": "Hijacked"},
                headers={"Authorization": "Bearer fake-token"},
            )
            assert patch_resp.status_code == 404

        await engine.dispose()

    async def test_patch_thread_title_appears_in_list(self) -> None:
        """After rename, GET /threads returns the updated title."""
        factory, engine = await _make_db()
        user_id = uuid.uuid4()
        app = _build_app(factory, user_id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            create_resp = await client.post(
                "/api/v1/threads",
                json={"title": "Before Rename"},
                headers={"Authorization": "Bearer fake-token"},
            )
            thread_id = create_resp.json()["data"]["id"]

            await client.patch(
                f"/api/v1/threads/{thread_id}",
                json={"title": "After Rename"},
                headers={"Authorization": "Bearer fake-token"},
            )

            list_resp = await client.get(
                "/api/v1/threads",
                headers={"Authorization": "Bearer fake-token"},
            )
            threads = list_resp.json()["data"]
            found = next((t for t in threads if t["id"] == thread_id), None)
            assert found is not None
            assert found["title"] == "After Rename"

        await engine.dispose()


# ---------------------------------------------------------------------------
# UX-M2: Approvals toggle — PATCH /api/v1/settings
# ---------------------------------------------------------------------------


class TestApprovalsToggle:
    """Tests for governance approvals_enabled setting."""

    async def test_approvals_enabled_defaults_to_true(self) -> None:
        """GET /settings returns approvals_enabled=True when not set."""
        factory, engine = await _make_db()
        user_id = uuid.uuid4()
        app = _build_app(factory, user_id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/settings",
                headers={"Authorization": "Bearer fake-token"},
            )
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["approvals_enabled"]  # truthy (True or 1)

        await engine.dispose()

    async def test_patch_approvals_disabled(self) -> None:
        """PATCH /settings with approvals_enabled=False persists and reads back."""
        factory, engine = await _make_db()
        user_id = uuid.uuid4()
        app = _build_app(factory, user_id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            patch_resp = await client.patch(
                "/api/v1/settings",
                json={"approvals_enabled": False},
                headers={"Authorization": "Bearer fake-token"},
            )
            assert patch_resp.status_code == 200

            # Read back — compare as falsy (SQLite returns 0 for False)
            get_resp = await client.get(
                "/api/v1/settings",
                headers={"Authorization": "Bearer fake-token"},
            )
            data = get_resp.json()["data"]
            assert not data["approvals_enabled"]

        await engine.dispose()

    async def test_patch_approvals_re_enable(self) -> None:
        """PATCH /settings can re-enable approvals after disabling."""
        factory, engine = await _make_db()
        user_id = uuid.uuid4()
        app = _build_app(factory, user_id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.patch(
                "/api/v1/settings",
                json={"approvals_enabled": False},
                headers={"Authorization": "Bearer fake-token"},
            )
            await client.patch(
                "/api/v1/settings",
                json={"approvals_enabled": True},
                headers={"Authorization": "Bearer fake-token"},
            )
            get_resp = await client.get(
                "/api/v1/settings",
                headers={"Authorization": "Bearer fake-token"},
            )
            data = get_resp.json()["data"]
            assert data["approvals_enabled"]  # truthy

        await engine.dispose()


# ---------------------------------------------------------------------------
# UX-M4: Agent limits
# ---------------------------------------------------------------------------


class TestAgentLimits:
    """Tests for max_tool_calls, max_retries, timeout_seconds settings."""

    async def test_agent_limits_have_defaults(self) -> None:
        """GET /settings returns defaults for agent limits when not set."""
        factory, engine = await _make_db()
        user_id = uuid.uuid4()
        app = _build_app(factory, user_id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/settings",
                headers={"Authorization": "Bearer fake-token"},
            )
            data = resp.json()["data"]
            assert data["max_tool_calls"] == 10
            assert data["max_retries"] == 3
            assert data["timeout_seconds"] == 120

        await engine.dispose()

    async def test_patch_agent_limits_saved(self) -> None:
        """PATCH /settings with custom limits persists and reads back."""
        factory, engine = await _make_db()
        user_id = uuid.uuid4()
        app = _build_app(factory, user_id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            patch_resp = await client.patch(
                "/api/v1/settings",
                json={
                    "max_tool_calls": 5,
                    "max_retries": 1,
                    "timeout_seconds": 60,
                },
                headers={"Authorization": "Bearer fake-token"},
            )
            assert patch_resp.status_code == 200

            get_resp = await client.get(
                "/api/v1/settings",
                headers={"Authorization": "Bearer fake-token"},
            )
            data = get_resp.json()["data"]
            assert data["max_tool_calls"] == 5
            assert data["max_retries"] == 1
            assert data["timeout_seconds"] == 60

        await engine.dispose()

    async def test_patch_agent_limits_partial_update(self) -> None:
        """PATCH /settings with one limit field only changes that field."""
        factory, engine = await _make_db()
        user_id = uuid.uuid4()
        app = _build_app(factory, user_id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.patch(
                "/api/v1/settings",
                json={"max_tool_calls": 20},
                headers={"Authorization": "Bearer fake-token"},
            )

            get_resp = await client.get(
                "/api/v1/settings",
                headers={"Authorization": "Bearer fake-token"},
            )
            data = get_resp.json()["data"]
            assert data["max_tool_calls"] == 20
            # Others stay at default
            assert data["max_retries"] == 3
            assert data["timeout_seconds"] == 120

        await engine.dispose()


# ---------------------------------------------------------------------------
# UX-H6: Notion credential auto-grant
# ---------------------------------------------------------------------------


class TestNotionCapabilityAutoGrant:
    """Tests that saving Notion credentials auto-grants notion.read capability."""

    async def test_store_notion_credentials_grants_capability(self) -> None:
        """POST /tools/notion/credentials auto-grants notion.read capability."""
        import noa.api.v1.tools as tools_mod
        from noa.auth.middleware import AuthUser
        from noa.tools.capabilities import DbCapabilityChecker

        factory, engine = await _make_db()
        user_id = uuid.uuid4()

        from noa.api.app import create_app
        from noa.api.app_state import set_session_factory

        app = create_app()
        set_session_factory(factory)

        async def _fake_auth():
            return AuthUser(user_id=user_id, session_id=uuid.uuid4())

        async def _fake_db():
            async with factory() as sess:
                yield sess

        # Override both the local patchable auth and the real require_auth
        tools_mod.require_auth = _fake_auth  # type: ignore[assignment]
        tools_mod.get_db_session = _fake_db  # type: ignore[assignment]

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/v1/tools/notion/credentials",
                    json={"token": "secret-notion-token"},
                    headers={"Authorization": "Bearer fake-token"},
                )
                assert resp.status_code == 200
                data = resp.json()["data"]
                assert data["capability_granted"] is True

            # Verify capability actually exists in DB
            async with factory() as sess:
                checker = DbCapabilityChecker(sess)
                has_cap = await checker.has_capability(user_id, "notion")
                assert has_cap, "notion.read capability must be granted after credential save"

        finally:
            # Restore module-level references
            tools_mod.require_auth = tools_mod._SELF_REF  # type: ignore[assignment]
            tools_mod.get_db_session = tools_mod._DB_SELF_REF  # type: ignore[assignment]

        await engine.dispose()

    async def test_store_web_search_credentials_grants_capability(self) -> None:
        """POST /tools/web_search/credentials auto-grants search.read capability."""
        import noa.api.v1.tools as tools_mod
        from noa.auth.middleware import AuthUser
        from noa.tools.capabilities import DbCapabilityChecker

        factory, engine = await _make_db()
        user_id = uuid.uuid4()

        from noa.api.app import create_app
        from noa.api.app_state import set_session_factory

        app = create_app()
        set_session_factory(factory)

        async def _fake_auth():
            return AuthUser(user_id=user_id, session_id=uuid.uuid4())

        async def _fake_db():
            async with factory() as sess:
                yield sess

        tools_mod.require_auth = _fake_auth  # type: ignore[assignment]
        tools_mod.get_db_session = _fake_db  # type: ignore[assignment]

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/v1/tools/web_search/credentials",
                    json={"api_key": "tvly-test-key"},
                    headers={"Authorization": "Bearer fake-token"},
                )
                assert resp.status_code == 200

            async with factory() as sess:
                checker = DbCapabilityChecker(sess)
                has_cap = await checker.has_capability(user_id, "web_search")
                assert has_cap, "search.read capability must be granted after credential save"

        finally:
            tools_mod.require_auth = tools_mod._SELF_REF  # type: ignore[assignment]
            tools_mod.get_db_session = tools_mod._DB_SELF_REF  # type: ignore[assignment]

        await engine.dispose()


# ---------------------------------------------------------------------------
# UX-M10: Tool scopes
# ---------------------------------------------------------------------------


class TestToolScopes:
    """Tests for GET /tools/scopes and PATCH /tools/scopes/{scope}."""

    async def test_list_scopes_returns_predefined(self) -> None:
        """GET /tools/scopes returns predefined scopes."""
        import noa.api.v1.tools as tools_mod
        from noa.auth.middleware import AuthUser

        factory, engine = await _make_db()
        user_id = uuid.uuid4()

        from noa.api.app import create_app
        from noa.api.app_state import set_session_factory

        app = create_app()
        set_session_factory(factory)

        async def _fake_auth():
            return AuthUser(user_id=user_id, session_id=uuid.uuid4())

        tools_mod.require_auth = _fake_auth  # type: ignore[assignment]

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/tools/scopes",
                    headers={"Authorization": "Bearer fake-token"},
                )
                assert resp.status_code == 200
                scopes = resp.json()["data"]
                scope_names = [s["name"] for s in scopes]
                assert "email_draft" in scope_names
                assert "research" in scope_names
                assert "scheduling" in scope_names
        finally:
            tools_mod.require_auth = tools_mod._SELF_REF  # type: ignore[assignment]

        await engine.dispose()

    async def test_patch_scope_updates_tools(self) -> None:
        """PATCH /tools/scopes/{scope} updates the tool list."""
        import noa.api.v1.tools as tools_mod
        from noa.auth.middleware import AuthUser

        factory, engine = await _make_db()
        user_id = uuid.uuid4()

        from noa.api.app import create_app
        from noa.api.app_state import set_session_factory

        app = create_app()
        set_session_factory(factory)

        async def _fake_auth():
            return AuthUser(user_id=user_id, session_id=uuid.uuid4())

        tools_mod.require_auth = _fake_auth  # type: ignore[assignment]

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                new_tools = ["web_search__web_search"]
                patch_resp = await client.patch(
                    "/api/v1/tools/scopes/research",
                    json={"tools": new_tools},
                    headers={"Authorization": "Bearer fake-token"},
                )
                assert patch_resp.status_code == 200
                assert patch_resp.json()["data"]["tools"] == new_tools

                # Verify GET reflects the update
                get_resp = await client.get(
                    "/api/v1/tools/scopes",
                    headers={"Authorization": "Bearer fake-token"},
                )
                research = next(
                    s for s in get_resp.json()["data"] if s["name"] == "research"
                )
                assert research["tools"] == new_tools
                assert research["is_custom"] is True
        finally:
            tools_mod.require_auth = tools_mod._SELF_REF  # type: ignore[assignment]
            # Clean up scope override for this user
            tools_mod._scope_overrides.pop(str(user_id), None)

        await engine.dispose()

    async def test_patch_unknown_scope_returns_404(self) -> None:
        """PATCH /tools/scopes/{unknown} returns 404."""
        import noa.api.v1.tools as tools_mod
        from noa.auth.middleware import AuthUser

        factory, engine = await _make_db()
        user_id = uuid.uuid4()

        from noa.api.app import create_app
        from noa.api.app_state import set_session_factory

        app = create_app()
        set_session_factory(factory)

        async def _fake_auth():
            return AuthUser(user_id=user_id, session_id=uuid.uuid4())

        tools_mod.require_auth = _fake_auth  # type: ignore[assignment]

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.patch(
                    "/api/v1/tools/scopes/nonexistent_scope",
                    json={"tools": []},
                    headers={"Authorization": "Bearer fake-token"},
                )
                assert resp.status_code == 404
        finally:
            tools_mod.require_auth = tools_mod._SELF_REF  # type: ignore[assignment]

        await engine.dispose()


# ---------------------------------------------------------------------------
# Migration verification: new settings fields exist in schema
# ---------------------------------------------------------------------------


class TestSettingsSchema:
    """Verify the new governance/limits fields are in the settings model."""

    async def test_user_settings_has_governance_fields(self) -> None:
        """UserSettings ORM model has approvals_enabled, max_tool_calls, etc."""
        from noa.settings.models import UserSettings

        assert hasattr(UserSettings, "approvals_enabled")
        assert hasattr(UserSettings, "max_tool_calls")
        assert hasattr(UserSettings, "max_retries")
        assert hasattr(UserSettings, "timeout_seconds")

    async def test_settings_service_all_fields_includes_new_fields(self) -> None:
        """SettingsService._ALL_FIELDS contains the new governance/limits fields."""
        from noa.settings.service import _ALL_FIELDS

        assert "approvals_enabled" in _ALL_FIELDS
        assert "max_tool_calls" in _ALL_FIELDS
        assert "max_retries" in _ALL_FIELDS
        assert "timeout_seconds" in _ALL_FIELDS

    async def test_settings_defaults_include_governance_values(self) -> None:
        """SettingsService._DEFAULTS has the right default values."""
        from noa.settings.service import _DEFAULTS

        assert _DEFAULTS["approvals_enabled"] is True
        assert _DEFAULTS["max_tool_calls"] == 10
        assert _DEFAULTS["max_retries"] == 3
        assert _DEFAULTS["timeout_seconds"] == 120
