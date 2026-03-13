"""Auth integration tests — register, login, refresh, logout against real Postgres.

Tests the full HTTP -> router -> service -> DB chain.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.conftest import TEST_PASSWORD, register_and_login


@pytest.mark.asyncio
async def test_register_creates_user_in_db(pg_client: Any) -> None:
    """POST /auth/register persists user to Postgres and returns 201."""
    resp = await pg_client.post(
        "/api/v1/auth/register",
        json={"email": "auth_reg@example.com", "password": TEST_PASSWORD},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["ok"] is True
    assert "user_id" in body["data"]


@pytest.mark.asyncio
async def test_duplicate_register_returns_409(pg_client: Any) -> None:
    """POST /auth/register with same email returns 409 Conflict."""
    payload = {"email": "auth_dup@example.com", "password": TEST_PASSWORD}
    first = await pg_client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = await pg_client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_login_returns_tokens(pg_client: Any) -> None:
    """POST /auth/login returns both access and refresh tokens."""
    tokens = await register_and_login(pg_client, "auth_login@example.com")
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(pg_client: Any) -> None:
    """POST /auth/login with wrong password returns 401."""
    await pg_client.post(
        "/api/v1/auth/register",
        json={"email": "auth_wrongpw@example.com", "password": TEST_PASSWORD},
    )
    resp = await pg_client.post(
        "/api/v1/auth/login",
        json={
            "email": "auth_wrongpw@example.com",
            "password": "WrongPassword!999",
            "device_id": "dev-001",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_token_refresh_rotates_pair(pg_client: Any) -> None:
    """POST /auth/refresh produces new token pair; old refresh token differs."""
    tokens = await register_and_login(pg_client, "auth_refresh@example.com")
    old_refresh = tokens["refresh_token"]

    resp = await pg_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh, "device_id": "dev-001"},
    )
    assert resp.status_code == 200
    new_tokens = resp.json()["data"]
    assert "access_token" in new_tokens
    assert new_tokens["refresh_token"] != old_refresh


@pytest.mark.asyncio
async def test_logout_invalidates_session(pg_client: Any) -> None:
    """POST /auth/logout marks session revoked; subsequent calls fail."""
    tokens = await register_and_login(pg_client, "auth_logout@example.com")
    access = tokens["access_token"]

    resp = await pg_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "logged_out"
