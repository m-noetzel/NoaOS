"""Threads integration tests — CRUD and user scoping against real Postgres."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.conftest import register_and_login


@pytest.mark.asyncio
async def test_create_thread_persists_to_db(pg_client: Any) -> None:
    """POST /threads creates a thread and it appears in list_threads."""
    tokens = await register_and_login(pg_client, "threads_create@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = await pg_client.post(
        "/api/v1/threads",
        json={"title": "My First Thread"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["title"] == "My First Thread"
    thread_id = data["id"]

    # Verify it appears in list
    list_resp = await pg_client.get("/api/v1/threads", headers=headers)
    assert list_resp.status_code == 200
    ids = [t["id"] for t in list_resp.json()["data"]]
    assert thread_id in ids


@pytest.mark.asyncio
async def test_list_threads_empty_for_new_user(pg_client: Any) -> None:
    """GET /threads returns empty list for a brand-new user."""
    tokens = await register_and_login(pg_client, "threads_empty@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = await pg_client.get("/api/v1/threads", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_list_messages_empty_for_new_thread(pg_client: Any) -> None:
    """GET /threads/{id}/messages returns empty list for a new thread."""
    tokens = await register_and_login(pg_client, "threads_msg@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Create thread
    t = await pg_client.post(
        "/api/v1/threads",
        json={"title": "Thread With No Messages"},
        headers=headers,
    )
    thread_id = t.json()["data"]["id"]

    # List messages — should be empty
    msgs = await pg_client.get(
        f"/api/v1/threads/{thread_id}/messages",
        headers=headers,
    )
    assert msgs.status_code == 200
    assert msgs.json()["data"] == []


@pytest.mark.asyncio
async def test_user_scoping_threads_invisible_cross_user(pg_client: Any) -> None:
    """Threads created by user A are not visible to user B."""
    tokens_a = await register_and_login(pg_client, "threads_scope_a@example.com")
    tokens_b = await register_and_login(pg_client, "threads_scope_b@example.com")
    headers_a = {"Authorization": f"Bearer {tokens_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {tokens_b['access_token']}"}

    # User A creates a thread
    await pg_client.post(
        "/api/v1/threads",
        json={"title": "User A Private Thread"},
        headers=headers_a,
    )

    # User B should see no threads
    resp_b = await pg_client.get("/api/v1/threads", headers=headers_b)
    assert resp_b.status_code == 200
    assert resp_b.json()["data"] == []


@pytest.mark.asyncio
async def test_delete_thread_removes_from_list(pg_client: Any) -> None:
    """DELETE /threads/{id} removes it from the list."""
    tokens = await register_and_login(pg_client, "threads_del@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Create then delete
    t = await pg_client.post(
        "/api/v1/threads",
        json={"title": "To Be Deleted"},
        headers=headers,
    )
    thread_id = t.json()["data"]["id"]

    del_resp = await pg_client.delete(
        f"/api/v1/threads/{thread_id}",
        headers=headers,
    )
    assert del_resp.status_code == 200

    # Thread should be gone from list
    list_resp = await pg_client.get("/api/v1/threads", headers=headers)
    ids = [t["id"] for t in list_resp.json()["data"]]
    assert thread_id not in ids
