"""Tools integration tests — capability grants, custom tool registration, tool call logging."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.conftest import register_and_login


@pytest.mark.asyncio
async def test_tools_health_endpoint(pg_client: Any) -> None:
    """GET /health/tools returns 200 with tools list."""
    resp = await pg_client.get("/health/tools")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "tools" in body["data"]


@pytest.mark.asyncio
async def test_enable_tool_grants_capability(pg_client: Any) -> None:
    """POST /tools/{name}/enable grants capability for authenticated user."""
    tokens = await register_and_login(pg_client, "tools_enable@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = await pg_client.post("/api/v1/tools/web_search/enable", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "granted"
    assert data["tool"] == "web_search"


@pytest.mark.asyncio
async def test_disable_tool_revokes_capability(pg_client: Any) -> None:
    """DELETE /tools/{name} revokes previously granted capability."""
    tokens = await register_and_login(pg_client, "tools_disable@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Enable first
    await pg_client.post("/api/v1/tools/web_search/enable", headers=headers)

    # Disable via DELETE
    resp = await pg_client.delete("/api/v1/tools/web_search", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "revoked"


@pytest.mark.asyncio
async def test_tool_capability_user_scoped(pg_client: Any) -> None:
    """Capability granted to user A is not visible to user B."""
    tokens_a = await register_and_login(pg_client, "tools_scope_a@example.com")
    tokens_b = await register_and_login(pg_client, "tools_scope_b@example.com")
    headers_a = {"Authorization": f"Bearer {tokens_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {tokens_b['access_token']}"}

    # User A enables web_search
    await pg_client.post("/api/v1/tools/web_search/enable", headers=headers_a)

    # User B's list should not show web_search as enabled
    resp_b = await pg_client.get("/api/v1/tools", headers=headers_b)
    assert resp_b.status_code == 200
    tools = resp_b.json()["data"]
    web_search_tool = next(
        (t for t in tools if t.get("name") == "web_search"), None
    )
    if web_search_tool is not None:
        # User B should not have it enabled
        assert web_search_tool.get("enabled") is not True


@pytest.mark.asyncio
async def test_custom_tool_registration(pg_client: Any) -> None:
    """POST /api/v1/tools registers a custom tool in DB — returns 201."""
    tokens = await register_and_login(pg_client, "tools_custom@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    custom_tool = {
        "name": "my_integration_test_tool",
        "description": "A test custom tool from QE4 integration tests",
        "base_url": "https://api.example.com",
        "auth_type": "none",
        "domain": "external",
        "functions": [
            {
                "name": "search",
                "description": "Search for something",
                "http_method": "POST",
                "path": "/search",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"],
                },
            }
        ],
    }

    resp = await pg_client.post(
        "/api/v1/tools",
        json=custom_tool,
        headers=headers,
    )
    # 201 on success; tool may already exist if session DB is shared
    assert resp.status_code in (201, 409)
