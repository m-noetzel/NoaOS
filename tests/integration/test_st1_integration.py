"""Integration tests for ST1: Run Lifecycle Fixes.

TECH-M4: Orphan run recovery on startup. Uses real Postgres DB.
"""

from __future__ import annotations

import base64
import json as _json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from tests.integration.conftest import register_and_login


async def _decode_user_id(access_token: str) -> uuid.UUID:
    """Extract user_id (sub claim) from a JWT access token."""
    payload_b64 = access_token.split(".")[1]
    padding = 4 - len(payload_b64) % 4
    payload_bytes = base64.urlsafe_b64decode(payload_b64 + "=" * padding)
    payload = _json.loads(payload_bytes)
    return uuid.UUID(payload["sub"])


async def _create_thread(client: Any, headers: dict[str, str]) -> uuid.UUID:
    resp = await client.post(
        "/api/v1/threads",
        json={"title": "ST1 Test Thread"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


@pytest.mark.asyncio
async def test_orphan_run_recovery(pg_app: Any) -> None:  # noqa: I001
    """Runs stuck in 'running' longer than 5 min are marked 'failed' by recovery.

    Test flow:
    1. Register a user and create a thread via the API.
    2. Directly insert a Run row with status='running' and created_at=now()-400s.
    3. Call _recover_orphaned_runs() directly.
    4. Verify the row is now status='failed'.
    """
    from noa.api import app_state
    from noa.api.app import _recover_orphaned_runs
    from noa.db.models.run import Run

    sf = app_state.get_session_factory()
    assert sf is not None, "session factory must be set for integration test"

    transport = httpx.ASGITransport(app=pg_app)  # type: ignore[arg-type]
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        tokens = await register_and_login(client, "orphan_recovery@example.com")
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        thread_id = await _create_thread(client, headers)

    user_id = await _decode_user_id(tokens["access_token"])

    # Insert an orphaned run directly (created 400s ago, past the 300s cutoff)
    orphaned_run_id = uuid.uuid4()
    old_created_at = datetime.now(UTC) - timedelta(seconds=400)

    async with sf() as session, session.begin():
        run = Run(
            id=orphaned_run_id,
            thread_id=thread_id,
            user_id=user_id,
            status="running",
            created_at=old_created_at,
            updated_at=old_created_at,
        )
        session.add(run)

    # Call the real orphan recovery function from app.py
    await _recover_orphaned_runs()

    # Verify the specific run is now failed in DB
    async with sf() as session:
        db_result = await session.execute(
            select(Run).where(Run.id == orphaned_run_id)
        )
        recovered_run = db_result.scalar_one()

    assert recovered_run.status == "failed", (
        f"Expected status='failed', got '{recovered_run.status}'"
    )
    assert recovered_run.summary == "orphaned: process restarted"


@pytest.mark.asyncio
async def test_recent_running_run_not_recovered(pg_app: Any) -> None:  # noqa: I001
    """Runs in 'running' created less than 5 minutes ago are NOT recovered.

    These are genuinely active runs that should not be interrupted.
    """
    from noa.api import app_state
    from noa.api.app import _recover_orphaned_runs
    from noa.db.models.run import Run

    sf = app_state.get_session_factory()
    assert sf is not None

    transport = httpx.ASGITransport(app=pg_app)  # type: ignore[arg-type]
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        tokens = await register_and_login(client, "recent_running@example.com")
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        thread_id = await _create_thread(client, headers)

    user_id = await _decode_user_id(tokens["access_token"])

    # Insert a run only 60 seconds old (well within the 300s cutoff)
    recent_run_id = uuid.uuid4()
    recent_created_at = datetime.now(UTC) - timedelta(seconds=60)

    async with sf() as session, session.begin():
        run = Run(
            id=recent_run_id,
            thread_id=thread_id,
            user_id=user_id,
            status="running",
            created_at=recent_created_at,
            updated_at=recent_created_at,
        )
        session.add(run)

    # Call the real orphan recovery function — should NOT touch the recent run
    await _recover_orphaned_runs()

    # Verify the run is still 'running'
    async with sf() as session:
        db_result = await session.execute(
            select(Run).where(Run.id == recent_run_id)
        )
        still_running = db_result.scalar_one()

    assert still_running.status == "running", (
        "Recent running run must NOT be marked failed by orphan recovery"
    )
