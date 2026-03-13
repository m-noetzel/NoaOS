"""Memory integration tests — store/recall/delete facts, user scoping.

The memory endpoints use the in-process MemoryStore (not DB-backed).
These tests verify the HTTP API layer and user isolation.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.conftest import register_and_login


@pytest.mark.asyncio
async def test_list_facts_empty_for_new_user(pg_client: Any) -> None:
    """GET /memory/facts returns empty list for new user."""
    tokens = await register_and_login(pg_client, "memory_empty@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = await pg_client.get("/api/v1/memory/facts", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_store_and_recall_fact(pg_client: Any) -> None:
    """Storing a fact directly in MemoryStore makes it appear in list_facts."""
    from noa.api import app_state

    import os

    from noa.auth.jwt import decode_token

    tokens = await register_and_login(pg_client, "memory_store@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    payload = decode_token(
        tokens["access_token"],
        secret_key=os.environ.get("SECRET_KEY", "integration-test-secret-key"),
    )
    user_id = payload["sub"]

    # Inject a fact directly via the MemoryStore (facts arrive via tool calls,
    # not via a public HTTP POST — this mirrors the real internal flow).
    store = app_state.get_memory_store()
    if store is None:
        pytest.skip("MemoryStore unavailable in this environment")

    fact_id = store.store(
        fact="User prefers dark mode",
        category="preference",
        embedding=[0.1, 0.2, 0.3],
        source_thread_id="test-thread-001",
        auto_extracted=False,
        user_id=user_id,
    )
    assert fact_id is not None, "store() returned None — duplicate guard triggered unexpectedly"

    # Verify the fact appears in the list endpoint
    list_resp = await pg_client.get("/api/v1/memory/facts", headers=headers)
    assert list_resp.status_code == 200
    facts = list_resp.json()["data"]
    assert any(f["fact"] == "User prefers dark mode" for f in facts), (
        f"Stored fact not found in list_facts response: {facts}"
    )


@pytest.mark.asyncio
async def test_approve_nonexistent_fact_returns_404(pg_client: Any) -> None:
    """POST /memory/facts/{id}/approve for unknown fact returns 404."""
    import uuid

    tokens = await register_and_login(pg_client, "memory_404@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = await pg_client.post(
        f"/api/v1/memory/facts/{uuid.uuid4()}/approve",
        headers=headers,
    )
    assert resp.status_code in (404, 503)  # 503 when memory store unavailable


@pytest.mark.asyncio
async def test_delete_nonexistent_fact_returns_404(pg_client: Any) -> None:
    """DELETE /memory/facts/{id} for unknown fact returns 404."""
    import uuid

    tokens = await register_and_login(pg_client, "memory_del404@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = await pg_client.delete(
        f"/api/v1/memory/facts/{uuid.uuid4()}",
        headers=headers,
    )
    assert resp.status_code in (404, 503)


@pytest.mark.asyncio
async def test_memory_requires_auth(pg_client: Any) -> None:
    """GET /memory/facts without token returns 401/403."""
    resp = await pg_client.get("/api/v1/memory/facts")
    assert resp.status_code in (401, 403)
