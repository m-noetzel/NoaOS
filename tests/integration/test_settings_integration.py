"""Settings integration tests — PATCH round-trip and credential storage against real Postgres."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.conftest import register_and_login


@pytest.mark.asyncio
async def test_get_settings_returns_defaults(pg_client: Any) -> None:
    """GET /settings returns a settings object for a new user."""
    tokens = await register_and_login(pg_client, "settings_get@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = await pg_client.get("/api/v1/settings", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_patch_settings_round_trip(pg_client: Any) -> None:
    """PATCH /settings persists model preference; GET returns updated value."""
    tokens = await register_and_login(pg_client, "settings_patch@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    patch_resp = await pg_client.patch(
        "/api/v1/settings",
        json={"default_model": "gpt-4o", "default_provider": "openai"},
        headers=headers,
    )
    assert patch_resp.status_code == 200

    get_resp = await pg_client.get("/api/v1/settings", headers=headers)
    assert get_resp.status_code == 200
    data = get_resp.json()["data"]
    assert data["default_model"] == "gpt-4o"
    assert data["default_provider"] == "openai"


@pytest.mark.asyncio
async def test_patch_preserves_unmodified_fields(pg_client: Any) -> None:
    """PATCH with partial body preserves fields not included in the update."""
    tokens = await register_and_login(pg_client, "settings_preserve@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Set two fields
    await pg_client.patch(
        "/api/v1/settings",
        json={"default_model": "claude-3-5-sonnet", "default_provider": "anthropic"},
        headers=headers,
    )

    # Update only one
    await pg_client.patch(
        "/api/v1/settings",
        json={"default_provider": "openai"},
        headers=headers,
    )

    get_resp = await pg_client.get("/api/v1/settings", headers=headers)
    data = get_resp.json()["data"]
    # Model should be preserved
    assert data["default_model"] == "claude-3-5-sonnet"
    assert data["default_provider"] == "openai"


@pytest.mark.asyncio
async def test_credential_stored_and_masked_in_response(pg_client: Any) -> None:
    """PATCH with API key stores it; GET returns masked value not plaintext."""
    tokens = await register_and_login(pg_client, "settings_creds@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    await pg_client.patch(
        "/api/v1/settings",
        json={"tavily_api_key": "tvly-secret-key-12345"},
        headers=headers,
    )

    get_resp = await pg_client.get("/api/v1/settings", headers=headers)
    data = get_resp.json()["data"]
    # Key should not be stored in plaintext in the response
    tavily_val = data.get("tavily_api_key", "")
    assert "tvly-secret-key-12345" not in str(tavily_val)


@pytest.mark.asyncio
async def test_settings_user_isolation(pg_client: Any) -> None:
    """Settings updated by user A are not visible to user B."""
    tokens_a = await register_and_login(pg_client, "settings_iso_a@example.com")
    tokens_b = await register_and_login(pg_client, "settings_iso_b@example.com")
    headers_a = {"Authorization": f"Bearer {tokens_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {tokens_b['access_token']}"}

    await pg_client.patch(
        "/api/v1/settings",
        json={"default_model": "user-a-model"},
        headers=headers_a,
    )

    get_resp = await pg_client.get("/api/v1/settings", headers=headers_b)
    data = get_resp.json()["data"]
    assert data.get("default_model") != "user-a-model"
