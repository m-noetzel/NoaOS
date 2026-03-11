"""Tests for TM2: Tools API Enrichment — Functions, Permissions, Metadata.

Spec refs: SPEC.md §12.1-12.4 (MVP Tool Definitions), §21 (Risk Tiers)
Phase plan: PLAN TM2

These tests define the behavioral contract for per-function tool metadata
(risk_tier, domain, parameter schemas) and per-function capability grants.
They are written BEFORE implementation and must fail initially.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.tm2


# ---------------------------------------------------------------------------
# Spec-mandated risk tiers (ground truth from SPEC.md §12.1-12.4, §21)
# ---------------------------------------------------------------------------

EXPECTED_RISK_TIERS: dict[str, dict[str, str]] = {
    "calendar": {
        "list_events": "low",
        "create_event": "medium",
    },
    "gmail": {
        "search_emails": "low",
        "read_email": "low",
        "send_email": "medium",
        "draft_email": "low",
    },
    "notion": {
        "search_pages": "low",
        "read_page": "low",
        "create_page": "medium",
    },
    "web_search": {
        "web_search": "low",
    },
}

# All current MVP tools are in the external domain per SPEC §12.1-12.4
EXPECTED_DOMAINS: dict[str, str] = {
    "calendar": "external",
    "gmail": "external",
    "notion": "external",
    "web_search": "external",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_user_id() -> uuid.UUID:
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


# ---------------------------------------------------------------------------
# Schema-level tests (TOOL_SCHEMAS enrichment)
# ---------------------------------------------------------------------------


class TestToolSchemaRiskTier:
    """Verify TOOL_SCHEMAS carries per-function risk_tier."""

    def test_every_function_has_risk_tier(self):
        """SPEC.md §12.1-12.4: Every tool function must declare a risk_tier."""
        from noa.tools.definitions import TOOL_SCHEMAS

        for tool_name, tool_def in TOOL_SCHEMAS.items():
            for func_name, func_def in tool_def["functions"].items():
                assert "risk_tier" in func_def, (
                    f"{tool_name}.{func_name} missing risk_tier"
                )
                assert func_def["risk_tier"] in {"low", "medium", "high"}, (
                    f"{tool_name}.{func_name} has invalid risk_tier: "
                    f"{func_def['risk_tier']}"
                )

    def test_risk_tiers_match_spec(self):
        """SPEC.md §12.1-12.4, §21: Risk tiers must match the specification exactly."""
        from noa.tools.definitions import TOOL_SCHEMAS

        for tool_name, expected_funcs in EXPECTED_RISK_TIERS.items():
            assert tool_name in TOOL_SCHEMAS, f"Tool {tool_name} missing from schemas"
            for func_name, expected_tier in expected_funcs.items():
                actual = TOOL_SCHEMAS[tool_name]["functions"][func_name]["risk_tier"]
                assert actual == expected_tier, (
                    f"{tool_name}.{func_name}: expected risk_tier "
                    f"'{expected_tier}', got '{actual}'"
                )


class TestToolSchemaDomain:
    """Verify TOOL_SCHEMAS carries per-function domain assignment."""

    def test_every_function_has_domain(self):
        """Each function must declare domain (private/external)."""
        from noa.tools.definitions import TOOL_SCHEMAS

        for tool_name, tool_def in TOOL_SCHEMAS.items():
            for func_name, func_def in tool_def["functions"].items():
                assert "domain" in func_def, (
                    f"{tool_name}.{func_name} missing domain"
                )
                assert func_def["domain"] in {"private", "external"}, (
                    f"{tool_name}.{func_name} has invalid domain: "
                    f"{func_def['domain']}"
                )

    def test_mvp_tools_are_external_domain(self):
        """SPEC.md §12.1-12.4: calendar, gmail, notion, web_search are all external."""
        from noa.tools.definitions import TOOL_SCHEMAS

        for tool_name, expected_domain in EXPECTED_DOMAINS.items():
            for func_name, func_def in TOOL_SCHEMAS[tool_name]["functions"].items():
                assert func_def["domain"] == expected_domain, (
                    f"{tool_name}.{func_name}: expected domain "
                    f"'{expected_domain}', got '{func_def['domain']}'"
                )


# ---------------------------------------------------------------------------
# Capabilities map tests (function-level entries)
# ---------------------------------------------------------------------------


class TestFunctionLevelCapabilities:
    """Verify TOOL_CAPABILITIES includes per-function entries."""

    def test_function_level_keys_exist(self):
        """TOOL_CAPABILITIES has function-level keys."""
        from noa.tools.capabilities import TOOL_CAPABILITIES

        # Each function in TOOL_SCHEMAS should have a corresponding
        # function-level capability key
        from noa.tools.definitions import TOOL_SCHEMAS

        for tool_name, tool_def in TOOL_SCHEMAS.items():
            for func_name in tool_def["functions"]:
                key = f"{tool_name}__{func_name}"
                assert key in TOOL_CAPABILITIES, (
                    f"Missing function-level capability: {key}"
                )

    def test_tool_level_keys_still_exist(self):
        """Backward compat: tool-level keys remain."""
        from noa.tools.capabilities import TOOL_CAPABILITIES

        for tool_name in ["web_search", "calendar", "gmail", "notion"]:
            assert tool_name in TOOL_CAPABILITIES, (
                f"Tool-level capability key '{tool_name}' removed — "
                "breaks backward compat"
            )


# ---------------------------------------------------------------------------
# DB model tests
# ---------------------------------------------------------------------------


class TestToolCapabilityModel:
    """Verify ToolCapability model has function_name column."""

    def test_function_name_column_exists(self):
        """PLAN TM2: ToolCapability must have a function_name column."""
        from noa.db.models.tool_capability import ToolCapability

        assert hasattr(ToolCapability, "function_name"), (
            "ToolCapability missing function_name column"
        )

    def test_function_name_column_is_nullable(self):
        """PLAN TM2: function_name must be nullable (NULL = all functions)."""
        from noa.db.models.tool_capability import ToolCapability

        col = ToolCapability.__table__.columns["function_name"]
        assert col.nullable is True, (
            "function_name must be nullable for backward compatibility"
        )


# ---------------------------------------------------------------------------
# Capability checker tests (backward compat + function isolation)
# ---------------------------------------------------------------------------


class TestFunctionCapabilityChecker:
    """Verify DbCapabilityChecker handles function-level grants."""

    @pytest.fixture
    def _db_engine(self):
        """In-memory SQLite engine with all tables."""
        import asyncio

        from sqlalchemy.ext.asyncio import create_async_engine

        from noa.db.models.base import Base

        engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
        )

        async def _init():
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            return engine

        return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            _init()
        )

    @pytest.fixture
    def db_session(self, _db_engine):
        """Yield an async session bound to the in-memory engine."""
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        maker = async_sessionmaker(
            _db_engine, class_=AsyncSession,
            expire_on_commit=False,
        )

        async def _make():
            async with maker() as s:
                yield s

        # Return a session for use in sync pytest — we'll use asyncio.run
        return maker

    @pytest.mark.asyncio
    async def test_null_function_grants_all(self):
        """NULL function_name grants all functions."""
        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )

        from noa.db.models.base import Base
        from noa.db.models.tool_capability import ToolCapability
        from noa.tools.capabilities import DbCapabilityChecker

        engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        uid = _fake_user_id()

        async with maker() as session:
            # Insert a wildcard grant (function_name=NULL)
            row = ToolCapability(
                user_id=uid,
                tool_name="gmail",
                capability="gmail.send",
                function_name=None,  # wildcard
            )
            session.add(row)
            await session.commit()

            checker = DbCapabilityChecker(session)
            # All gmail functions should be granted via the wildcard
            for func in ["send_email", "read_email", "search_emails", "draft_email"]:
                result = await checker.has_capability(uid, "gmail", func)
                assert result is True, (
                    f"NULL function_name should grant gmail.{func}"
                )

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_function_grant_does_not_grant_siblings(self):
        """PLAN TM2: Granting gmail__send_email must NOT enable gmail__read_email."""
        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )

        from noa.db.models.base import Base
        from noa.db.models.tool_capability import ToolCapability
        from noa.tools.capabilities import DbCapabilityChecker

        engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        uid = _fake_user_id()

        async with maker() as session:
            # Grant only send_email
            row = ToolCapability(
                user_id=uid,
                tool_name="gmail",
                capability="gmail.send",
                function_name="send_email",
            )
            session.add(row)
            await session.commit()

            checker = DbCapabilityChecker(session)
            assert await checker.has_capability(uid, "gmail", "send_email") is True
            assert await checker.has_capability(uid, "gmail", "read_email") is False

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_revoke_function_does_not_revoke_wildcard(self):
        """PLAN TM2: Revoking a function-level grant must preserve wildcard grants."""
        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )

        from noa.db.models.base import Base
        from noa.db.models.tool_capability import ToolCapability
        from noa.tools.capabilities import DbCapabilityChecker

        engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        uid = _fake_user_id()

        async with maker() as session:
            # Insert wildcard + function-specific grant
            session.add(ToolCapability(
                user_id=uid,
                tool_name="gmail",
                capability="gmail.send",
                function_name=None,
            ))
            session.add(ToolCapability(
                user_id=uid,
                tool_name="gmail",
                capability="gmail.send",
                function_name="send_email",
            ))
            await session.commit()

            checker = DbCapabilityChecker(session)
            # Revoke only the function-level grant
            count = await checker.revoke(uid, "gmail", function_name="send_email")
            assert count >= 1

            # Wildcard grant should still be intact
            assert await checker.has_capability(uid, "gmail", "send_email") is True

        await engine.dispose()


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestListToolsEnrichedResponse:
    """Verify GET /api/v1/tools returns nested functions with metadata."""

    @pytest.mark.asyncio
    async def test_list_tools_returns_nested_functions(self):
        """PLAN TM2: GET /api/v1/tools must return tools with nested functions array."""
        from noa.api.app import create_app

        app = create_app()

        # Override auth to return a fake user
        from noa.api.v1 import tools as tools_mod

        uid = _fake_user_id()
        original_auth = tools_mod.require_auth

        async def _fake_auth():
            return MagicMock(user_id=uid)

        tools_mod.require_auth = _fake_auth

        # Override DB session with an in-memory one
        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )

        from noa.db.models.base import Base

        engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async def _fake_db():
            async with maker() as s:
                yield s

        tools_mod.get_db_session = _fake_db

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test",
            ) as client:
                resp = await client.get(
                    "/api/v1/tools",
                    headers={"Authorization": "Bearer test-token"},
                )

            assert resp.status_code == 200
            body = resp.json()
            tools_data = body["data"]
            assert isinstance(tools_data, list)
            assert len(tools_data) > 0

            # Each tool must have a functions array
            for tool in tools_data:
                assert "functions" in tool, (
                    f"Tool '{tool.get('name')}' missing 'functions' array"
                )
                funcs = tool["functions"]
                assert isinstance(funcs, list)
                for fn in funcs:
                    assert "name" in fn
                    assert "description" in fn
                    assert "parameters" in fn
                    assert "risk_tier" in fn
                    assert fn["risk_tier"] in {"low", "medium", "high"}
                    assert "domain" in fn
                    assert fn["domain"] in {"private", "external"}
                    assert "enabled" in fn
        finally:
            tools_mod.require_auth = original_auth
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_list_tools_risk_tiers_match_schema(self):
        """API risk_tier comes from TOOL_SCHEMAS."""
        from noa.api.app import create_app
        from noa.api.v1 import tools as tools_mod

        app = create_app()
        uid = _fake_user_id()
        original_auth = tools_mod.require_auth

        async def _fake_auth():
            return MagicMock(user_id=uid)

        tools_mod.require_auth = _fake_auth

        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )

        from noa.db.models.base import Base

        engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async def _fake_db():
            async with maker() as s:
                yield s

        tools_mod.get_db_session = _fake_db

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test",
            ) as client:
                resp = await client.get(
                    "/api/v1/tools",
                    headers={"Authorization": "Bearer test-token"},
                )

            assert resp.status_code == 200
            tools_data = resp.json()["data"]

            for tool in tools_data:
                tool_name = tool["name"]
                if tool_name not in EXPECTED_RISK_TIERS:
                    continue
                for fn in tool["functions"]:
                    expected = EXPECTED_RISK_TIERS[tool_name].get(fn["name"])
                    if expected is not None:
                        assert fn["risk_tier"] == expected, (
                            f"API {tool_name}.{fn['name']}: expected "
                            f"'{expected}', got '{fn['risk_tier']}'"
                        )
        finally:
            tools_mod.require_auth = original_auth
            await engine.dispose()


class TestFunctionEnableDisableEndpoints:
    """Verify per-function grant/revoke endpoints."""

    @pytest.mark.asyncio
    async def test_grant_function_capability(self):
        """POST /{tool}/{function}/enable grants capability."""
        from noa.api.app import create_app
        from noa.api.v1 import tools as tools_mod

        app = create_app()
        uid = _fake_user_id()
        original_auth = tools_mod.require_auth

        async def _fake_auth():
            return MagicMock(user_id=uid)

        tools_mod.require_auth = _fake_auth

        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )

        from noa.db.models.base import Base

        engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async def _fake_db():
            async with maker() as s:
                yield s

        tools_mod.get_db_session = _fake_db

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test",
            ) as client:
                resp = await client.post(
                    "/api/v1/tools/gmail/send_email/enable",
                    headers={"Authorization": "Bearer test-token"},
                )

            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["tool"] == "gmail"
            assert data["function"] == "send_email"
            assert data["status"] == "granted"
        finally:
            tools_mod.require_auth = original_auth
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_revoke_function_capability(self):
        """DELETE /{tool}/{function} revokes capability."""
        from noa.api.app import create_app
        from noa.api.v1 import tools as tools_mod

        app = create_app()
        uid = _fake_user_id()
        original_auth = tools_mod.require_auth

        async def _fake_auth():
            return MagicMock(user_id=uid)

        tools_mod.require_auth = _fake_auth

        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )

        from noa.db.models.base import Base

        engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async def _fake_db():
            async with maker() as s:
                yield s

        tools_mod.get_db_session = _fake_db

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test",
            ) as client:
                resp = await client.delete(
                    "/api/v1/tools/gmail/send_email",
                    headers={"Authorization": "Bearer test-token"},
                )

            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["tool"] == "gmail"
            assert data["function"] == "send_email"
            assert data["status"] == "revoked"
        finally:
            tools_mod.require_auth = original_auth
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_grant_unknown_tool_returns_404(self):
        """PLAN TM2, L11: Granting capability for unknown tool must be rejected."""
        from noa.api.app import create_app
        from noa.api.v1 import tools as tools_mod

        app = create_app()
        original_auth = tools_mod.require_auth

        async def _fake_auth():
            return MagicMock(user_id=_fake_user_id())

        tools_mod.require_auth = _fake_auth

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test",
            ) as client:
                resp = await client.post(
                    "/api/v1/tools/nonexistent/somefunc/enable",
                    headers={"Authorization": "Bearer test-token"},
                )

            assert resp.status_code == 404
        finally:
            tools_mod.require_auth = original_auth

    @pytest.mark.asyncio
    async def test_grant_unknown_function_returns_404(self):
        """Unknown function on known tool → 404."""
        from noa.api.app import create_app
        from noa.api.v1 import tools as tools_mod

        app = create_app()
        original_auth = tools_mod.require_auth

        async def _fake_auth():
            return MagicMock(user_id=_fake_user_id())

        tools_mod.require_auth = _fake_auth

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test",
            ) as client:
                resp = await client.post(
                    "/api/v1/tools/gmail/nonexistent_function/enable",
                    headers={"Authorization": "Bearer test-token"},
                )

            assert resp.status_code == 404
        finally:
            tools_mod.require_auth = original_auth

    @pytest.mark.asyncio
    async def test_function_enable_requires_auth(self):
        """SPEC.md §21, M3: Per-function enable endpoint must require authentication."""
        from noa.api.app import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/tools/gmail/send_email/enable")

        # Should be 401 or 403 (no auth token)
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_function_disable_requires_auth(self):
        """Per-function disable requires auth."""
        from noa.api.app import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/v1/tools/gmail/send_email")

        assert resp.status_code in (401, 403)


class TestFunctionEnabledStateInListing:
    """Verify per-function enabled state is reflected in GET /api/v1/tools."""

    @pytest.mark.asyncio
    async def test_function_enabled_reflects_grant(self):
        """Only granted function shows enabled=True."""
        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )

        from noa.api.app import create_app
        from noa.api.v1 import tools as tools_mod
        from noa.db.models.base import Base
        from noa.db.models.tool_capability import ToolCapability

        app = create_app()
        uid = _fake_user_id()
        original_auth = tools_mod.require_auth

        async def _fake_auth():
            return MagicMock(user_id=uid)

        tools_mod.require_auth = _fake_auth

        engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        # Pre-populate a function-level grant
        async with maker() as session:
            session.add(ToolCapability(
                user_id=uid,
                tool_name="gmail",
                capability="gmail.send",
                function_name="send_email",
            ))
            await session.commit()

        async def _fake_db():
            async with maker() as s:
                yield s

        tools_mod.get_db_session = _fake_db

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test",
            ) as client:
                resp = await client.get(
                    "/api/v1/tools",
                    headers={"Authorization": "Bearer test-token"},
                )

            assert resp.status_code == 200
            tools_data = resp.json()["data"]

            gmail_tool = next(t for t in tools_data if t["name"] == "gmail")
            funcs_by_name = {f["name"]: f for f in gmail_tool["functions"]}

            assert funcs_by_name["send_email"]["enabled"] is True
            assert funcs_by_name["read_email"]["enabled"] is False
            assert funcs_by_name["search_emails"]["enabled"] is False
        finally:
            tools_mod.require_auth = original_auth
            await engine.dispose()
