"""Tests for Run/Event model & SSE streaming — Phase OC2.

Spec refs: SPEC.md §22.1, §22.2, §22.3, §22.4, §22.5
Phase plan: MASTER_PLAN.md Phase OC2

Tests cover: Run CRUD service (create, status transitions, query),
Event append service (ordered, append-only), SSE endpoint,
Artifact metadata, and authentication requirements.

Updated to async RunService (BE-H2 / PR1).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.oc2

FAKE_PW_HASH = "fakehash"  # noqa: S105

# All valid event types per §22.2
VALID_EVENT_TYPES = [
    "message_received",
    "classification_done",
    "step_started",
    "token_stream",
    "tool_called",
    "tool_result",
    "approval_requested",
    "approval_received",
    "artifact_created",
    "result_ready",
    "error",
]

VALID_STATUSES = [
    "pending", "running", "awaiting_approval",
    "completed", "failed", "cancelled",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
async def engine():
    """In-memory async SQLite engine for run tests."""
    from sqlalchemy.pool import StaticPool

    from noa.db.models import Base

    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture()
async def db(engine):
    """Async session that rolls back after each test."""
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session, session.begin():
        yield session
        await session.rollback()


@pytest.fixture()
async def user_id(db):
    """Create a test user and return its ID."""
    from noa.db.models.user import User

    user = User(
        id=uuid.uuid4(),
        email="runs-test@example.com",
        password_hash=FAKE_PW_HASH,
        display_name="Run Tester",
    )
    db.add(user)
    await db.flush()
    return user.id


@pytest.fixture()
async def thread_id(db, user_id):
    """Create a test conversation and return its ID."""
    from noa.db.models.conversation import Conversation

    conv = Conversation(id=uuid.uuid4(), user_id=user_id, title="Test Thread")
    db.add(conv)
    await db.flush()
    return conv.id


@pytest.fixture()
def run_service(db):
    """Instantiate the RunService with a test session."""
    from noa.runs.service import RunService

    return RunService(db)


# ---------------------------------------------------------------------------
# 1. Run creation — correct initial state (§22.1)
# ---------------------------------------------------------------------------

class TestRunCreation:
    """Run service creates runs with correct initial state per §22.1."""

    async def test_create_run_returns_complete_record(self, run_service, user_id, thread_id):
        """Service creates a run with all §22.1 fields populated."""
        run = await run_service.create_run(
            user_id=user_id,
            thread_id=thread_id,
            summary="Test run",
        )

        assert run.id is not None
        assert run.user_id == user_id
        assert run.thread_id == thread_id
        assert run.status == "pending"
        assert run.risk_tier == "low"
        assert run.privacy_mode == "private"
        assert run.summary == "Test run"
        assert run.created_at is not None
        assert run.updated_at is not None

    async def test_create_run_with_custom_risk_tier(self, run_service, user_id, thread_id):
        """Run can be created with a specified risk_tier."""
        run = await run_service.create_run(
            user_id=user_id,
            thread_id=thread_id,
            risk_tier="high",
        )
        assert run.risk_tier == "high"

    async def test_create_run_with_external_privacy(self, run_service, user_id, thread_id):
        """Run can be created with external privacy mode."""
        run = await run_service.create_run(
            user_id=user_id,
            thread_id=thread_id,
            privacy_mode="external",
        )
        assert run.privacy_mode == "external"

    async def test_create_run_persists_to_db(self, run_service, user_id, thread_id):
        """Run is flushed and queryable from the session."""
        run = await run_service.create_run(user_id=user_id, thread_id=thread_id)
        found = await run_service.get_run(run.id)
        assert found is not None
        assert found.status == "pending"


# ---------------------------------------------------------------------------
# 2. Status transitions — valid work, invalid rejected (§22.1)
# ---------------------------------------------------------------------------

class TestStatusTransitions:
    """Run status transitions follow the valid state machine."""

    async def test_pending_to_running(self, run_service, user_id, thread_id):
        """pending -> running is a valid transition."""
        run = await run_service.create_run(user_id=user_id, thread_id=thread_id)
        updated = await run_service.update_status(run.id, "running")
        assert updated.status == "running"

    async def test_running_to_completed(self, run_service, user_id, thread_id):
        """running -> completed is a valid transition."""
        run = await run_service.create_run(user_id=user_id, thread_id=thread_id)
        await run_service.update_status(run.id, "running")
        updated = await run_service.update_status(run.id, "completed")
        assert updated.status == "completed"

    async def test_running_to_failed(self, run_service, user_id, thread_id):
        """running -> failed is a valid transition."""
        run = await run_service.create_run(user_id=user_id, thread_id=thread_id)
        await run_service.update_status(run.id, "running")
        updated = await run_service.update_status(run.id, "failed")
        assert updated.status == "failed"

    async def test_running_to_awaiting_approval(self, run_service, user_id, thread_id):
        """running -> awaiting_approval is valid."""
        run = await run_service.create_run(user_id=user_id, thread_id=thread_id)
        await run_service.update_status(run.id, "running")
        updated = await run_service.update_status(run.id, "awaiting_approval")
        assert updated.status == "awaiting_approval"

    async def test_invalid_transition_rejected(self, run_service, user_id, thread_id):
        """completed -> running is invalid and raises ValueError."""
        run = await run_service.create_run(user_id=user_id, thread_id=thread_id)
        await run_service.update_status(run.id, "running")
        await run_service.update_status(run.id, "completed")
        with pytest.raises(ValueError, match="Invalid.*transition"):
            await run_service.update_status(run.id, "running")

    async def test_cancel_from_pending(self, run_service, user_id, thread_id):
        """pending -> cancelled is valid."""
        run = await run_service.create_run(user_id=user_id, thread_id=thread_id)
        updated = await run_service.update_status(run.id, "cancelled")
        assert updated.status == "cancelled"

    async def test_cancel_from_running(self, run_service, user_id, thread_id):
        """running -> cancelled is valid."""
        run = await run_service.create_run(user_id=user_id, thread_id=thread_id)
        await run_service.update_status(run.id, "running")
        updated = await run_service.update_status(run.id, "cancelled")
        assert updated.status == "cancelled"


# ---------------------------------------------------------------------------
# 3. Event appending — ordered and append-only (§22.2)
# ---------------------------------------------------------------------------

class TestEventAppending:
    """Events are ordered and append-only per §22.2."""

    async def test_append_event_returns_event(self, run_service, user_id, thread_id):
        """Appending an event returns the created RunEvent."""
        run = await run_service.create_run(user_id=user_id, thread_id=thread_id)
        event = await run_service.append_event(
            run_id=run.id,
            event_type="message_received",
            payload={"text": "hello"},
        )
        assert event.id is not None
        assert event.run_id == run.id
        assert event.event_type == "message_received"
        assert event.payload == {"text": "hello"}
        assert event.timestamp is not None

    async def test_events_ordered_by_timestamp(self, run_service, user_id, thread_id):
        """Events for a run come back ordered by timestamp."""
        run = await run_service.create_run(user_id=user_id, thread_id=thread_id)
        await run_service.append_event(run.id, "message_received", {"text": "hi"})
        await run_service.append_event(
            run.id, "classification_done", {"privacy_mode": "private"},
        )
        await run_service.append_event(run.id, "result_ready", {"response_text": "Hello!"})

        events = await run_service.list_events(run.id)
        assert len(events) == 3
        assert events[0].event_type == "message_received"
        assert events[1].event_type == "classification_done"
        assert events[2].event_type == "result_ready"
        # Timestamps are non-decreasing
        for i in range(len(events) - 1):
            assert events[i].timestamp <= events[i + 1].timestamp

    async def test_events_persist_to_db(self, run_service, user_id, thread_id):
        """Events are persisted and queryable."""
        from sqlalchemy import select

        from noa.db.models.run import RunEvent

        run = await run_service.create_run(user_id=user_id, thread_id=thread_id)
        await run_service.append_event(run.id, "message_received", {"text": "hi"})

        result = await run_service._session.execute(
            select(RunEvent).where(RunEvent.run_id == run.id)
        )
        found = result.scalars().all()
        assert len(found) == 1


# ---------------------------------------------------------------------------
# 4. Event types — all §22.2 event types supported
# ---------------------------------------------------------------------------

class TestEventTypes:
    """All event types from §22.2 table are accepted."""

    @pytest.mark.parametrize("event_type", VALID_EVENT_TYPES)
    async def test_valid_event_type_accepted(
        self, run_service, user_id, thread_id, event_type,
    ):
        """Each §22.2 event type can be appended."""
        run = await run_service.create_run(user_id=user_id, thread_id=thread_id)
        event = await run_service.append_event(run.id, event_type, {})
        assert event.event_type == event_type

    async def test_invalid_event_type_rejected(self, run_service, user_id, thread_id):
        """Unknown event types are rejected."""
        run = await run_service.create_run(user_id=user_id, thread_id=thread_id)
        with pytest.raises(ValueError, match="Invalid event type"):
            await run_service.append_event(run.id, "not_a_real_event", {})


# ---------------------------------------------------------------------------
# 5. Artifact metadata — artifacts linked to runs (§22.3)
# ---------------------------------------------------------------------------

class TestArtifactMetadata:
    """Artifact metadata service links artifacts to runs per §22.3."""

    async def test_create_artifact(self, run_service, user_id, thread_id):
        """Artifact can be created and linked to a run."""
        run = await run_service.create_run(user_id=user_id, thread_id=thread_id)
        artifact = await run_service.create_artifact(
            run_id=run.id,
            artifact_type="file",
            name="output.txt",
            mime_type="text/plain",
            size_bytes=1024,
            storage_ref="/artifacts/output.txt",
        )
        assert artifact.id is not None
        assert artifact.run_id == run.id
        assert artifact.type == "file"
        assert artifact.name == "output.txt"
        assert artifact.mime_type == "text/plain"
        assert artifact.size_bytes == 1024
        assert artifact.storage_ref == "/artifacts/output.txt"
        assert artifact.created_at is not None

    async def test_list_artifacts_for_run(self, run_service, user_id, thread_id):
        """Artifacts can be listed by run_id."""
        run = await run_service.create_run(user_id=user_id, thread_id=thread_id)
        await run_service.create_artifact(
            run_id=run.id, artifact_type="file",
            name="a.txt", mime_type="text/plain",
            size_bytes=100, storage_ref="/artifacts/a.txt",
        )
        await run_service.create_artifact(
            run_id=run.id, artifact_type="diff",
            name="b.diff", mime_type="text/x-diff",
            size_bytes=200, storage_ref="/artifacts/b.diff",
        )
        artifacts = await run_service.list_artifacts(run.id)
        assert len(artifacts) == 2


# ---------------------------------------------------------------------------
# 6. Run query — runs queryable by thread, user, status (§22.5)
# ---------------------------------------------------------------------------

class TestRunQuery:
    """Runs are queryable by various filters per §22.5."""

    async def test_query_by_thread(self, run_service, user_id, thread_id):
        """Runs can be filtered by thread_id."""
        await run_service.create_run(user_id=user_id, thread_id=thread_id)
        results = await run_service.list_runs(thread_id=thread_id)
        assert len(results) >= 1
        assert all(r.thread_id == thread_id for r in results)

    async def test_query_by_user(self, run_service, user_id, thread_id):
        """Runs can be filtered by user_id."""
        await run_service.create_run(user_id=user_id, thread_id=thread_id)
        results = await run_service.list_runs(user_id=user_id)
        assert len(results) >= 1
        assert all(r.user_id == user_id for r in results)

    async def test_query_by_status(self, run_service, user_id, thread_id):
        """Runs can be filtered by status."""
        run = await run_service.create_run(user_id=user_id, thread_id=thread_id)
        await run_service.update_status(run.id, "running")

        pending = await run_service.list_runs(status="pending")
        running = await run_service.list_runs(status="running")

        assert all(r.status == "pending" for r in pending)
        assert any(r.status == "running" for r in running)

    async def test_get_run_by_id(self, run_service, user_id, thread_id):
        """A single run can be fetched by ID."""
        run = await run_service.create_run(user_id=user_id, thread_id=thread_id)
        found = await run_service.get_run(run.id)
        assert found is not None
        assert found.id == run.id

    async def test_get_run_not_found(self, run_service):
        """Non-existent run_id returns None."""
        found = await run_service.get_run(uuid.uuid4())
        assert found is None


# ---------------------------------------------------------------------------
# 7. SSE endpoint — events stream correctly (§22.4)
# ---------------------------------------------------------------------------

class TestSSEEndpoint:
    """SSE endpoint streams events for a run per §22.4."""

    @pytest.fixture()
    def _app(self):
        """Create a test app with runs router."""
        from noa.api.app import create_app

        return create_app()

    @pytest.mark.asyncio
    async def test_sse_requires_auth(self, _app):
        """SSE endpoint returns 401/403 without auth."""
        import httpx

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=_app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"/api/v1/runs/{uuid.uuid4()}/events")
            assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_sse_endpoint_exists(self, _app):
        """SSE endpoint is registered and responds (even if 401)."""
        import httpx

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=_app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"/api/v1/runs/{uuid.uuid4()}/events")
            # Should not be 404 — endpoint exists
            assert resp.status_code != 404


# ---------------------------------------------------------------------------
# 8. Run lifecycle — status updates update timestamp (§22.5)
# ---------------------------------------------------------------------------

class TestRunLifecycle:
    """Run lifecycle management ensures updated_at changes."""

    async def test_updated_at_changes_on_status_update(self, run_service, user_id, thread_id):
        """updated_at is refreshed when status changes."""
        run = await run_service.create_run(user_id=user_id, thread_id=thread_id)
        original_updated = run.updated_at
        await run_service.update_status(run.id, "running")
        updated_run = await run_service.get_run(run.id)
        assert updated_run.updated_at >= original_updated

    async def test_summary_can_be_updated(self, run_service, user_id, thread_id):
        """Run summary can be updated after creation."""
        run = await run_service.create_run(user_id=user_id, thread_id=thread_id)
        updated = await run_service.update_run(run.id, summary="Updated summary")
        assert updated.summary == "Updated summary"
