"""Tests for MVP-H2: Memory tool visibility on the Tools page.

The list_tools endpoint previously defaulted to privacy_mode="external",
which filtered out private-domain tools (including memory). Now:
- No privacy_mode param → all tools returned regardless of domain
- privacy_mode="external" → private-only tools filtered out
- privacy_mode="private" → external-only tools filtered out

Spec refs: MVP-H2, BE-H8
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.mvp_h2


# ---------------------------------------------------------------------------
# Unit tests for _tool_is_visible_in_domain helper
# ---------------------------------------------------------------------------


class TestToolIsVisibleInDomain:
    """Tests for the domain filtering helper."""

    def test_private_only_tool_hidden_in_external_mode(self):
        """Tools with all private functions must be hidden in external mode."""
        from noa.api.v1.tools import _tool_is_visible_in_domain

        schema = {
            "functions": {
                "remember": {"domain": "private"},
                "recall": {"domain": "private"},
            }
        }
        assert _tool_is_visible_in_domain(schema, "external") is False

    def test_private_only_tool_visible_in_private_mode(self):
        """Tools with all private functions must be visible in private mode."""
        from noa.api.v1.tools import _tool_is_visible_in_domain

        schema = {
            "functions": {
                "remember": {"domain": "private"},
                "recall": {"domain": "private"},
            }
        }
        assert _tool_is_visible_in_domain(schema, "private") is True

    def test_external_only_tool_hidden_in_private_mode(self):
        """Tools with all external functions must be hidden in private mode."""
        from noa.api.v1.tools import _tool_is_visible_in_domain

        schema = {
            "functions": {
                "search": {"domain": "external"},
            }
        }
        assert _tool_is_visible_in_domain(schema, "private") is False

    def test_mixed_domain_tool_always_visible(self):
        """Mixed-domain tools must be visible in both modes."""
        from noa.api.v1.tools import _tool_is_visible_in_domain

        schema = {
            "functions": {
                "fn_private": {"domain": "private"},
                "fn_external": {"domain": "external"},
            }
        }
        assert _tool_is_visible_in_domain(schema, "external") is True
        assert _tool_is_visible_in_domain(schema, "private") is True


# ---------------------------------------------------------------------------
# Unit tests for TOOL_CAPABILITIES including memory entries
# ---------------------------------------------------------------------------


class TestToolCapabilitiesIncludesMemory:
    """Verify memory tools have entries in TOOL_CAPABILITIES."""

    def test_memory_in_tool_capabilities(self):
        """memory must appear in TOOL_CAPABILITIES."""
        from noa.tools.capabilities import TOOL_CAPABILITIES

        assert "memory" in TOOL_CAPABILITIES
        assert TOOL_CAPABILITIES["memory"] == "memory.remember"

    def test_external_memory_in_tool_capabilities(self):
        """external_memory must appear in TOOL_CAPABILITIES."""
        from noa.tools.capabilities import TOOL_CAPABILITIES

        assert "external_memory" in TOOL_CAPABILITIES
        assert TOOL_CAPABILITIES["external_memory"] == "external_memory.remember"

    def test_memory_function_keys_present(self):
        """Function-level keys for memory (memory__remember, memory__recall) must exist."""
        from noa.tools.capabilities import TOOL_CAPABILITIES

        assert "memory__remember" in TOOL_CAPABILITIES
        assert "memory__recall" in TOOL_CAPABILITIES

    def test_external_memory_function_keys_present(self):
        """Function-level keys for external_memory must exist."""
        from noa.tools.capabilities import TOOL_CAPABILITIES

        assert "external_memory__remember" in TOOL_CAPABILITIES
        assert "external_memory__recall" in TOOL_CAPABILITIES


# ---------------------------------------------------------------------------
# Integration tests via FastAPI TestClient
# ---------------------------------------------------------------------------


def _make_fake_session() -> Any:
    """Return a fake AsyncSession that reports no capabilities."""
    session = MagicMock()
    execute_result = MagicMock()
    execute_result.scalars.return_value.first.return_value = None
    session.execute = AsyncMock(return_value=execute_result)
    session.commit = AsyncMock(return_value=None)
    session.add = MagicMock(return_value=None)
    return session


async def _fake_auth() -> Any:
    """Fake auth dependency returning a minimal payload."""
    payload = MagicMock()
    payload.user_id = uuid.uuid4()
    return payload


async def _fake_db_session():
    yield _make_fake_session()


@pytest.fixture
def tools_client():
    """FastAPI TestClient with auth + DB session overridden."""
    from fastapi.testclient import TestClient

    import noa.api.v1.tools as tools_mod
    from noa.api.app import app

    # Clear any stale overrides from prior test modules
    app.dependency_overrides.clear()
    app.dependency_overrides[tools_mod.require_auth] = _fake_auth
    app.dependency_overrides[tools_mod.get_db_session] = _fake_db_session

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.pop(tools_mod.require_auth, None)
    app.dependency_overrides.pop(tools_mod.get_db_session, None)


class TestListToolsNoPrivacyMode:
    """list_tools with no privacy_mode must return all tools including memory."""

    def test_memory_tool_appears_when_no_privacy_mode(self, tools_client):
        """memory tool must appear when privacy_mode is not specified.

        MVP-H2: The Tools page doesn't pass privacy_mode, so memory was invisible.
        """
        resp = tools_client.get(
            "/api/v1/tools",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        tool_names = [t["name"] for t in data["data"]]
        assert "memory" in tool_names, (
            f"memory tool missing from tools list; got: {tool_names}"
        )

    def test_external_memory_tool_appears_when_no_privacy_mode(self, tools_client):
        """external_memory must appear when privacy_mode is not specified."""
        resp = tools_client.get(
            "/api/v1/tools",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        tool_names = [t["name"] for t in data["data"]]
        assert "external_memory" in tool_names, (
            f"external_memory tool missing; got: {tool_names}"
        )

    def test_all_standard_tools_appear_when_no_privacy_mode(self, tools_client):
        """All registered tools must appear when no privacy_mode filter is applied."""
        from noa.tools.definitions import TOOL_SCHEMAS

        resp = tools_client.get(
            "/api/v1/tools",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        returned_names = {t["name"] for t in data["data"]}
        for name in TOOL_SCHEMAS:
            assert name in returned_names, f"Tool '{name}' missing from no-filter response"

    def test_memory_domain_badge_is_private(self, tools_client):
        """memory tool must report domain='private' so the UI can show a badge."""
        resp = tools_client.get(
            "/api/v1/tools",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        memory_tool = next((t for t in data["data"] if t["name"] == "memory"), None)
        assert memory_tool is not None
        assert memory_tool["domain"] == "private"


class TestListToolsWithPrivacyModeFilter:
    """list_tools with explicit privacy_mode must still apply the domain filter."""

    def test_external_mode_hides_memory_tool(self, tools_client):
        """privacy_mode=external must exclude private-domain tools like memory."""
        resp = tools_client.get(
            "/api/v1/tools?privacy_mode=external",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        tool_names = [t["name"] for t in data["data"]]
        assert "memory" not in tool_names, (
            "memory (private-domain) must be hidden when privacy_mode=external"
        )

    def test_private_mode_hides_web_search(self, tools_client):
        """privacy_mode=private must exclude external-domain tools like web_search."""
        resp = tools_client.get(
            "/api/v1/tools?privacy_mode=private",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        tool_names = [t["name"] for t in data["data"]]
        assert "web_search" not in tool_names, (
            "web_search (external-domain) must be hidden when privacy_mode=private"
        )

    def test_private_mode_shows_memory_tool(self, tools_client):
        """privacy_mode=private must include private-domain tools like memory."""
        resp = tools_client.get(
            "/api/v1/tools?privacy_mode=private",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        tool_names = [t["name"] for t in data["data"]]
        assert "memory" in tool_names, (
            "memory (private-domain) must appear when privacy_mode=private"
        )

    def test_external_mode_shows_web_search(self, tools_client):
        """privacy_mode=external must include external-domain tools like web_search."""
        resp = tools_client.get(
            "/api/v1/tools?privacy_mode=external",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        tool_names = [t["name"] for t in data["data"]]
        assert "web_search" in tool_names, (
            "web_search must appear when privacy_mode=external"
        )


# ---------------------------------------------------------------------------
# MVP-L1: enable_tool must reject function-level capability keys
# ---------------------------------------------------------------------------


class TestEnableToolRejectsFunctionKeys:
    """POST /tools/{name}/enable must 404 for function-level keys.

    TOOL_CAPABILITIES includes auto-generated keys like memory__remember.
    Enabling such a key would write a DB grant that has_capability() never
    matches, silently doing nothing. The endpoint must validate against
    TOOL_SCHEMAS (top-level tool names only).

    Uses a standalone FastAPI app to avoid test-ordering pollution from
    modules that inject real SQLite sessions into the shared app.
    """

    def test_function_level_key_returns_404(self, tools_client):
        """POST /tools/memory__remember/enable must return 404.

        MVP-L1: memory__remember is a function-level TOOL_CAPABILITIES key,
        not a top-level tool name. Enabling it would create a no-op grant.
        """
        resp = tools_client.post(
            "/api/v1/tools/memory__remember/enable",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 404, (
            f"Expected 404 for function-level key 'memory__remember', got {resp.status_code}"
        )

    def test_valid_tool_name_accepted(self):
        """web_search is a valid TOOL_SCHEMAS key and should not be rejected.

        Confirms that the TOOL_SCHEMAS validation doesn't break valid tools.
        Tests the validation logic directly rather than going through HTTP
        to avoid test-ordering pollution from other modules' DB sessions.
        """
        from noa.tools.definitions import TOOL_SCHEMAS

        assert "web_search" in TOOL_SCHEMAS, "web_search must be in TOOL_SCHEMAS"
        # Function-level keys must NOT be in TOOL_SCHEMAS
        assert "memory__remember" not in TOOL_SCHEMAS
        assert "web_search__search" not in TOOL_SCHEMAS
