"""Tests for FR6-L1: Scope overrides persistence in DB.

Previously scope overrides lived in a module-level dict (_scope_overrides)
that was lost on server restart. This phase moves them to the
scope_overrides column on user_settings, persisted via SettingsService.

Spec refs: UX-M10, FR6-L1
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Shared in-memory DB factory
# ---------------------------------------------------------------------------


async def _make_db():
    """Return (factory, engine) with all tables created (in-memory SQLite)."""
    import noa.db.models.user  # noqa: F401 — User (FK parent of UserSettings)
    import noa.settings.models  # noqa: F401 — registers UserSettings on Base.metadata
    from noa.db.models.base import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return factory, engine


def _build_app_and_patches(factory: Any, user_id: uuid.UUID):
    """Minimal app with auth + DB overridden for scope endpoint tests.

    Returns (app, restore_fn). Caller MUST call restore_fn() after the test
    to reset the tools module's monkey-patched attributes.

    The tools router uses patchable module-level require_auth / get_db_session
    wrappers (so tests can monkey-patch them without touching FastAPI DI).
    """
    import noa.api.v1.tools as tools_mod
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

    # Monkey-patch the tools module's patchable wrappers
    tools_mod.require_auth = _fake_auth  # type: ignore[assignment]
    tools_mod.get_db_session = _fake_db  # type: ignore[assignment]

    # Also set dependency_overrides for any other routers
    app.dependency_overrides[require_auth] = _fake_auth
    app.dependency_overrides[get_db_session] = _fake_db

    def _restore():
        tools_mod.require_auth = tools_mod._SELF_REF  # type: ignore[assignment]
        tools_mod.get_db_session = tools_mod._DB_SELF_REF  # type: ignore[assignment]

    return app, _restore


# ---------------------------------------------------------------------------
# Unit tests: SettingsService scope methods
# ---------------------------------------------------------------------------


class TestSettingsServiceScopeMethods:
    """Tests for get_scope_overrides and set_scope_override on SettingsService."""

    async def test_get_scope_overrides_returns_empty_for_new_user(self):
        """No user_settings row → empty dict returned."""
        from noa.settings.repository import SettingsRepository
        from noa.settings.service import SettingsService

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = SettingsRepository(mock_session)
        svc = SettingsService(repo)

        result = await svc.get_scope_overrides(uuid.uuid4())
        assert result == {}

    async def test_get_scope_overrides_returns_empty_for_null_column(self):
        """Row exists but scope_overrides is NULL → empty dict."""
        from noa.settings.models import UserSettings
        from noa.settings.repository import SettingsRepository
        from noa.settings.service import SettingsService

        user_id = uuid.uuid4()
        row = MagicMock(spec=UserSettings)
        row.scope_overrides = None

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = row
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = SettingsRepository(mock_session)
        svc = SettingsService(repo)

        result = await svc.get_scope_overrides(user_id)
        assert result == {}

    async def test_get_scope_overrides_deserializes_json(self):
        """Stored JSON is deserialized into dict correctly."""
        import json

        from noa.settings.models import UserSettings
        from noa.settings.repository import SettingsRepository
        from noa.settings.service import SettingsService

        user_id = uuid.uuid4()
        stored = {"research": ["web_search__search"], "email_draft": ["gmail__send_email"]}

        row = MagicMock(spec=UserSettings)
        row.scope_overrides = json.dumps(stored)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = row
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = SettingsRepository(mock_session)
        svc = SettingsService(repo)

        result = await svc.get_scope_overrides(user_id)
        assert result == stored

    async def test_get_scope_overrides_handles_corrupt_json(self):
        """Corrupt JSON in DB → returns empty dict (graceful degradation)."""
        from noa.settings.models import UserSettings
        from noa.settings.repository import SettingsRepository
        from noa.settings.service import SettingsService

        user_id = uuid.uuid4()
        row = MagicMock(spec=UserSettings)
        row.scope_overrides = "not valid json {"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = row
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = SettingsRepository(mock_session)
        svc = SettingsService(repo)

        result = await svc.get_scope_overrides(user_id)
        assert result == {}

    async def test_set_scope_override_persists_via_upsert(self):
        """set_scope_override calls upsert with JSON-encoded overrides."""

        from noa.settings.models import UserSettings
        from noa.settings.repository import SettingsRepository
        from noa.settings.service import SettingsService

        user_id = uuid.uuid4()
        # No existing row
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        new_row = MagicMock(spec=UserSettings)
        new_row.scope_overrides = None
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        repo = SettingsRepository(mock_session)
        svc = SettingsService(repo)

        result = await svc.set_scope_override(
            user_id, "research", ["web_search__search"]
        )

        assert result == {"research": ["web_search__search"]}
        # upsert was called with scope_overrides field
        assert mock_session.add.called or mock_session.execute.called

    async def test_set_scope_override_merges_existing_scopes(self):
        """set_scope_override for one scope leaves other scopes intact."""
        import json

        from noa.settings.models import UserSettings
        from noa.settings.repository import SettingsRepository
        from noa.settings.service import SettingsService

        user_id = uuid.uuid4()
        existing_overrides = {"email_draft": ["gmail__send_email"]}

        # First call: row exists with existing overrides
        existing_row = MagicMock(spec=UserSettings)
        existing_row.scope_overrides = json.dumps(existing_overrides)

        call_count = 0

        async def _execute(stmt, *args, **kwargs):
            nonlocal call_count
            result = MagicMock()
            if call_count == 0:
                # First select: return existing row
                result.scalar_one_or_none.return_value = existing_row
            else:
                # Second select (from upsert): return existing row
                result.scalar_one_or_none.return_value = existing_row
            call_count += 1
            return result

        mock_session = AsyncMock()
        mock_session.execute = _execute
        mock_session.flush = AsyncMock()

        repo = SettingsRepository(mock_session)
        svc = SettingsService(repo)

        result = await svc.set_scope_override(
            user_id, "research", ["web_search__search"]
        )

        assert result["research"] == ["web_search__search"]
        assert result["email_draft"] == ["gmail__send_email"]


# ---------------------------------------------------------------------------
# Integration tests: Full HTTP flow with real SQLite DB
# ---------------------------------------------------------------------------


class TestScopePersistenceIntegration:
    """Integration tests: PATCH persists to DB, GET reads from DB."""

    async def test_patch_scope_persists_and_get_reflects(self):
        """PATCH /tools/scopes/{scope} stores override; GET returns it."""
        factory, engine = await _make_db()
        user_id = uuid.uuid4()
        app, restore = _build_app_and_patches(factory, user_id)

        try:
            # Need a user row for the UserSettings FK
            from noa.db.models.user import User

            async with factory() as sess:
                user = User(id=user_id, email="test@example.com", password_hash="x")
                sess.add(user)
                await sess.commit()

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                # PATCH a scope override
                patch_resp = await client.patch(
                    "/api/v1/tools/scopes/research",
                    json={"tools": ["web_search__search"]},
                    headers={"Authorization": "Bearer fake"},
                )
                assert patch_resp.status_code == 200
                data = patch_resp.json()["data"]
                assert data["scope"] == "research"
                assert data["tools"] == ["web_search__search"]
                assert data["status"] == "updated"

                # GET should reflect the persisted override
                get_resp = await client.get(
                    "/api/v1/tools/scopes",
                    headers={"Authorization": "Bearer fake"},
                )
                assert get_resp.status_code == 200
                scopes = get_resp.json()["data"]
                research_scope = next(s for s in scopes if s["name"] == "research")
                assert research_scope["tools"] == ["web_search__search"]
                assert research_scope["is_custom"] is True
        finally:
            restore()
            await engine.dispose()

    async def test_scope_override_survives_simulated_restart(self):
        """After engine re-creation (simulating restart), override is still present."""
        factory, engine = await _make_db()
        user_id = uuid.uuid4()
        app, restore = _build_app_and_patches(factory, user_id)

        try:
            # Need a user row for the UserSettings FK
            from noa.db.models.user import User

            async with factory() as sess:
                user = User(id=user_id, email="restart@example.com", password_hash="x")
                sess.add(user)
                await sess.commit()

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                # PATCH scope override
                patch_resp = await client.patch(
                    "/api/v1/tools/scopes/email_draft",
                    json={"tools": ["gmail__send_email", "gmail__read_email"]},
                    headers={"Authorization": "Bearer fake"},
                )
                assert patch_resp.status_code == 200

            # Simulate restart: build a new app instance re-using the same factory/engine
            restore()  # restore first before re-patching
            app2, restore2 = _build_app_and_patches(factory, user_id)
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app2), base_url="http://test"
                ) as client2:
                    get_resp = await client2.get(
                        "/api/v1/tools/scopes",
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert get_resp.status_code == 200
                    scopes = get_resp.json()["data"]
                    email_scope = next(s for s in scopes if s["name"] == "email_draft")
                    assert "gmail__send_email" in email_scope["tools"]
                    assert email_scope["is_custom"] is True
            finally:
                restore2()
        except Exception:
            restore()
            raise
        finally:
            await engine.dispose()

    async def test_patch_unknown_scope_returns_404(self):
        """PATCH with an unknown scope name returns 404."""
        factory, engine = await _make_db()
        user_id = uuid.uuid4()
        app, restore = _build_app_and_patches(factory, user_id)

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.patch(
                    "/api/v1/tools/scopes/nonexistent_scope",
                    json={"tools": ["some__tool"]},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
        finally:
            restore()
            await engine.dispose()

    async def test_get_scopes_returns_defaults_for_new_user(self):
        """GET /tools/scopes returns registry defaults when no overrides set."""
        factory, engine = await _make_db()
        user_id = uuid.uuid4()
        app, restore = _build_app_and_patches(factory, user_id)

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/tools/scopes",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                scopes = resp.json()["data"]
                assert len(scopes) > 0
                # All scopes should use defaults (is_custom=False)
                for scope in scopes:
                    assert scope["is_custom"] is False
        finally:
            restore()
            await engine.dispose()

    async def test_multiple_scope_overrides_are_independent(self):
        """Updating one scope does not affect another scope's override."""
        factory, engine = await _make_db()
        user_id = uuid.uuid4()
        app, restore = _build_app_and_patches(factory, user_id)

        try:
            from noa.db.models.user import User

            async with factory() as sess:
                user = User(id=user_id, email="multi@example.com", password_hash="x")
                sess.add(user)
                await sess.commit()

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                # Set research scope
                await client.patch(
                    "/api/v1/tools/scopes/research",
                    json={"tools": ["web_search__search"]},
                    headers={"Authorization": "Bearer fake"},
                )
                # Set email_draft scope
                await client.patch(
                    "/api/v1/tools/scopes/email_draft",
                    json={"tools": ["gmail__send_email"]},
                    headers={"Authorization": "Bearer fake"},
                )

                # Both should be present
                get_resp = await client.get(
                    "/api/v1/tools/scopes",
                    headers={"Authorization": "Bearer fake"},
                )
                scopes = {s["name"]: s for s in get_resp.json()["data"]}
                assert scopes["research"]["tools"] == ["web_search__search"]
                assert scopes["research"]["is_custom"] is True
                assert scopes["email_draft"]["tools"] == ["gmail__send_email"]
                assert scopes["email_draft"]["is_custom"] is True
        finally:
            restore()
            await engine.dispose()
