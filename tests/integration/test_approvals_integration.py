"""Approvals integration tests — create, list pending, decide against real Postgres."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from tests.integration.conftest import register_and_login


async def _create_approval_direct(
    pg_app: Any,
    user_id: uuid.UUID,
    run_id: uuid.UUID,
    *,
    risk_tier: str = "medium",
) -> Any:
    """Insert an approval directly into DB (bypasses the orchestrator)."""
    from noa.api import app_state
    from noa.db.models.approval import Approval

    sf = app_state.get_session_factory()
    assert sf is not None

    approval = Approval(
        id=uuid.uuid4(),
        run_id=run_id,
        user_id=user_id,
        risk_tier=risk_tier,
        preview_text="Integration test approval",
        decision="pending",
        domain="external",
        requested_at=datetime.now(UTC),
    )
    async with sf() as session:
        session.add(approval)
        await session.commit()
        await session.refresh(approval)

    return approval


async def _create_run_direct(pg_app: Any, user_id: uuid.UUID, thread_id: uuid.UUID) -> Any:
    """Insert a run directly into DB."""
    from noa.api import app_state
    from noa.db.models.run import Run

    sf = app_state.get_session_factory()
    assert sf is not None

    run = Run(
        id=uuid.uuid4(),
        thread_id=thread_id,
        user_id=user_id,
        status="pending",
        risk_tier="medium",
        privacy_mode="external",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    async with sf() as session:
        session.add(run)
        await session.commit()
        await session.refresh(run)

    return run


async def _create_thread_direct(pg_app: Any, user_id: uuid.UUID) -> Any:
    """Insert a conversation/thread directly into DB."""
    from noa.api import app_state
    from noa.db.models.conversation import Conversation

    sf = app_state.get_session_factory()
    assert sf is not None

    conv = Conversation(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Approval Test Thread",
        created_at=datetime.now(UTC),
    )
    async with sf() as session:
        session.add(conv)
        await session.commit()
        await session.refresh(conv)

    return conv


@pytest.mark.asyncio
async def test_list_pending_approvals_empty(pg_client: Any) -> None:
    """GET /approvals/pending returns empty list for new user."""
    tokens = await register_and_login(pg_client, "approvals_empty@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = await pg_client.get("/api/v1/approvals/pending", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_pending_approval_appears_in_list(pg_client: Any, pg_app: Any) -> None:
    """An approval created in DB for user X is visible in their pending list."""
    tokens = await register_and_login(pg_client, "approvals_list@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Extract user_id from the token payload
    from noa.auth.jwt import decode_token

    import os
    payload = decode_token(tokens["access_token"], secret_key=os.environ["SECRET_KEY"])
    user_id = uuid.UUID(payload["sub"])

    # Create prerequisite data
    conv = await _create_thread_direct(pg_app, user_id)
    run = await _create_run_direct(pg_app, user_id, conv.id)
    approval = await _create_approval_direct(pg_app, user_id, run.id)

    # Verify it appears
    resp = await pg_client.get("/api/v1/approvals/pending", headers=headers)
    assert resp.status_code == 200
    ids = [a["id"] for a in resp.json()["data"]]
    assert str(approval.id) in ids


@pytest.mark.asyncio
async def test_decide_approval_approved(pg_client: Any, pg_app: Any) -> None:
    """POST /approvals/{id}/decide with 'approved' updates the decision in DB."""
    tokens = await register_and_login(pg_client, "approvals_decide@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    from noa.auth.jwt import decode_token

    import os
    payload = decode_token(tokens["access_token"], secret_key=os.environ["SECRET_KEY"])
    user_id = uuid.UUID(payload["sub"])

    conv = await _create_thread_direct(pg_app, user_id)
    run = await _create_run_direct(pg_app, user_id, conv.id)
    approval = await _create_approval_direct(pg_app, user_id, run.id)

    resp = await pg_client.post(
        f"/api/v1/approvals/{approval.id}/decide",
        json={"decision": "approved"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["decision"] == "approved"

    # Pending list should now be empty
    pending = await pg_client.get("/api/v1/approvals/pending", headers=headers)
    ids = [a["id"] for a in pending.json()["data"]]
    assert str(approval.id) not in ids


@pytest.mark.asyncio
async def test_user_scoping_approvals(pg_client: Any, pg_app: Any) -> None:
    """Approval for user A is not visible to user B."""
    tokens_a = await register_and_login(pg_client, "approvals_scope_a@example.com")
    tokens_b = await register_and_login(pg_client, "approvals_scope_b@example.com")
    headers_b = {"Authorization": f"Bearer {tokens_b['access_token']}"}

    from noa.auth.jwt import decode_token

    import os
    payload_a = decode_token(tokens_a["access_token"], secret_key=os.environ["SECRET_KEY"])
    user_id_a = uuid.UUID(payload_a["sub"])

    conv = await _create_thread_direct(pg_app, user_id_a)
    run = await _create_run_direct(pg_app, user_id_a, conv.id)
    await _create_approval_direct(pg_app, user_id_a, run.id)

    # User B sees empty
    resp = await pg_client.get("/api/v1/approvals/pending", headers=headers_b)
    assert resp.json()["data"] == []
