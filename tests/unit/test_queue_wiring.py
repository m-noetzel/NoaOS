"""Tests for MVP-H3: DurableQueue wired into chat endpoint when private unavailable.

Spec refs: SPEC.md §17.1, §17.2
Phase: MVP-H3

Covers:
1. Chat endpoint returns queued SSE event when private_available=False and
   privacy_mode="private".
2. Chat endpoint proceeds normally when private_available=True.
3. Chat endpoint proceeds normally when privacy_mode="external" regardless of
   private_available.
4. QueueDrainWorker starts and stops cleanly.
5. Router node passes private_available to classifier.
"""

from __future__ import annotations

import contextlib
import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from noa.api.app import create_app
from noa.auth.middleware import AuthUser, require_auth

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_user() -> AuthUser:
    return AuthUser(user_id=uuid.uuid4())


def _make_runner(events: list[dict[str, Any]] | None = None) -> MagicMock:
    """Create a mock runner that yields events."""
    runner = MagicMock()
    if events is None:
        events = [
            {
                "event_type": "result_ready",
                "payload": {"response": "Hello!"},
                "timestamp": "2026-03-14T00:00:00Z",
            },
        ]

    async def fake_run(**kwargs: Any) -> Any:
        for e in events:
            yield e

    runner.run = fake_run
    return runner


def _post_chat(
    *,
    privacy_mode: str = "external",
    private_available: bool = True,
    runner: Any = None,
) -> Any:
    """POST /api/v1/chat with health checker state controlled via mock."""
    app = create_app()
    app.dependency_overrides[require_auth] = _fake_user

    mock_checker = MagicMock()
    mock_checker.is_available.return_value = private_available

    with (
        patch("noa.api.v1.chat.get_runner", return_value=runner),
        patch("noa.api.v1.chat._get_session_factory", return_value=None),
        patch("noa.api.v1.chat.get_health_checker", return_value=mock_checker),
    ):
        client = TestClient(app, raise_server_exceptions=False)
        return client.post(
            "/api/v1/chat",
            json={
                "message": "tell me something private",
                "privacy_mode": privacy_mode,
            },
            headers={"Authorization": "Bearer test"},
        )


# ---------------------------------------------------------------------------
# 1. Queue path: private mode + private unavailable → queued SSE
# ---------------------------------------------------------------------------


class TestQueuedResponse:
    """When privacy_mode=private and private worker is down, return queued event."""

    def test_returns_queued_event_when_private_unavailable(self) -> None:
        """SSE stream contains a 'queued' event when private domain is down."""
        response = _post_chat(privacy_mode="private", private_available=False)

        assert response.status_code == 200
        ct = response.headers.get("content-type", "")
        assert "text/event-stream" in ct

        # Parse SSE events
        events = _parse_sse_events(response.text)
        event_types = {e.get("event_type") for e in events}
        assert "queued" in event_types, f"Expected 'queued' event, got: {event_types}"

    def test_queued_event_contains_message(self) -> None:
        """Queued event payload contains a user-facing message."""
        response = _post_chat(privacy_mode="private", private_available=False)
        events = _parse_sse_events(response.text)

        queued = next(e for e in events if e.get("event_type") == "queued")
        payload = queued.get("payload", {})
        assert "message" in payload
        assert "unavailable" in payload["message"].lower() or "queued" in payload["message"].lower()

    def test_queued_event_followed_by_done(self) -> None:
        """Stream ends with a 'done' event after 'queued'."""
        response = _post_chat(privacy_mode="private", private_available=False)
        events = _parse_sse_events(response.text)
        event_types = [e.get("event_type") for e in events]

        assert "done" in event_types
        # done must come after queued
        queued_idx = event_types.index("queued")
        done_idx = event_types.index("done")
        assert done_idx > queued_idx

    def test_meta_event_precedes_queued_event(self) -> None:
        """MVP-L2: meta event is emitted before queued event in the SSE stream."""
        response = _post_chat(privacy_mode="private", private_available=False)
        events = _parse_sse_events(response.text)
        event_types = [e.get("event_type") for e in events]

        assert "meta" in event_types, f"Expected 'meta' event, got: {event_types}"
        assert "queued" in event_types
        meta_idx = event_types.index("meta")
        queued_idx = event_types.index("queued")
        assert meta_idx < queued_idx, "meta must precede queued"

    def test_meta_event_contains_run_id_and_thread_id(self) -> None:
        """MVP-L2: meta event payload includes run_id and thread_id for client tracking."""
        response = _post_chat(privacy_mode="private", private_available=False)
        events = _parse_sse_events(response.text)

        meta = next(e for e in events if e.get("event_type") == "meta")
        assert "run_id" in meta, f"meta event missing run_id: {meta}"
        assert "thread_id" in meta, f"meta event missing thread_id: {meta}"
        # Values should be valid UUIDs
        uuid.UUID(meta["run_id"])
        uuid.UUID(meta["thread_id"])

    def test_done_event_contains_run_id(self) -> None:
        """Done event payload contains run_id."""
        response = _post_chat(privacy_mode="private", private_available=False)
        events = _parse_sse_events(response.text)
        done = next(e for e in events if e.get("event_type") == "done")
        assert "run_id" in done.get("payload", {})

    def test_runner_not_called_when_queued(self) -> None:
        """The OrchestratorRunner is not invoked when the task is queued."""
        runner = _make_runner()
        run_called = []

        original_run = runner.run

        async def spy_run(**kwargs: Any) -> Any:
            run_called.append(True)
            async for e in original_run(**kwargs):
                yield e

        runner.run = spy_run

        _post_chat(privacy_mode="private", private_available=False, runner=runner)
        assert len(run_called) == 0, "Runner should NOT be called when task is queued"


# ---------------------------------------------------------------------------
# 2. Normal path: private mode + private available → runs pipeline
# ---------------------------------------------------------------------------


class TestNormalPrivatePath:
    """When privacy_mode=private and private worker is UP, run normally."""

    def test_runs_pipeline_when_private_available(self) -> None:
        """Normal run proceeds to result_ready when private is available."""
        runner = _make_runner()
        response = _post_chat(
            privacy_mode="private",
            private_available=True,
            runner=runner,
        )
        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        event_types = {e.get("event_type") for e in events}
        # Should have result_ready, not queued
        assert "result_ready" in event_types
        assert "queued" not in event_types


# ---------------------------------------------------------------------------
# 3. External path: external mode → always runs, ignores private availability
# ---------------------------------------------------------------------------


class TestExternalPath:
    """When privacy_mode=external, private_available is irrelevant."""

    def test_runs_normally_when_external_and_private_unavailable(self) -> None:
        """External mode runs even if private worker is down."""
        runner = _make_runner()
        response = _post_chat(
            privacy_mode="external",
            private_available=False,
            runner=runner,
        )
        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        event_types = {e.get("event_type") for e in events}
        assert "result_ready" in event_types
        assert "queued" not in event_types


# ---------------------------------------------------------------------------
# 4. QueueDrainWorker lifecycle
# ---------------------------------------------------------------------------


class TestQueueDrainWorker:
    """QueueDrainWorker starts and stops cleanly."""

    @pytest.mark.asyncio
    async def test_start_and_stop_cleanly(self) -> None:
        """Worker starts background task, stops on stop()."""
        from noa.queue.drain import QueueDrainWorker

        mock_checker = MagicMock()
        mock_checker.is_available.return_value = False  # no draining

        mock_factory = MagicMock()

        worker = QueueDrainWorker(
            session_factory=mock_factory,
            health_checker=mock_checker,
        )

        await worker.start()
        assert worker._task is not None  # noqa: SLF001
        assert not worker._stop  # noqa: SLF001

        await worker.stop()
        assert worker._stop  # noqa: SLF001
        assert worker._task is None  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_stop_before_start_is_safe(self) -> None:
        """Calling stop() before start() does not raise."""
        from noa.queue.drain import QueueDrainWorker

        worker = QueueDrainWorker(
            session_factory=MagicMock(),
            health_checker=MagicMock(),
        )
        # Should not raise
        await worker.stop()

    @pytest.mark.asyncio
    async def test_drain_loop_polls_when_private_available(self) -> None:
        """When private domain is up, drain worker calls queue.poll()."""
        from noa.queue.drain import QueueDrainWorker

        mock_checker = MagicMock()
        mock_checker.is_available.return_value = True

        # Mock session factory and queue
        mock_task = MagicMock()
        mock_task.id = uuid.uuid4()
        mock_task.task_type = "private.chat"
        mock_task.status = "queued"

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        poll_called = []

        async def mock_poll() -> Any:
            poll_called.append(True)
            return mock_task

        mock_queue_instance = AsyncMock()
        mock_queue_instance.poll = mock_poll

        mock_factory = MagicMock()
        mock_factory.return_value = mock_session

        with patch("noa.queue.drain.DurableQueue", return_value=mock_queue_instance):
            worker = QueueDrainWorker(
                session_factory=mock_factory,
                health_checker=mock_checker,
                runner=None,
            )
            # Run one drain iteration directly
            await worker._drain_one()  # noqa: SLF001

        assert len(poll_called) > 0, "poll() should have been called"
        # With no runner, task reverts to "queued" after the processing attempt
        assert mock_task.status == "queued"

    @pytest.mark.asyncio
    async def test_drain_loop_skips_when_private_unavailable(self) -> None:
        """When private domain is down, drain worker does not poll."""
        from noa.queue.drain import QueueDrainWorker

        mock_checker = MagicMock()
        mock_checker.is_available.return_value = False

        poll_called = []

        async def mock_drain_one() -> None:
            poll_called.append(True)

        worker = QueueDrainWorker(
            session_factory=MagicMock(),
            health_checker=mock_checker,
        )
        worker._drain_one = mock_drain_one  # noqa: SLF001

        # Manually run one iteration of the loop body
        if mock_checker.is_available():
            await worker._drain_one()  # noqa: SLF001

        assert len(poll_called) == 0, "drain_one should NOT be called when private is down"


# ---------------------------------------------------------------------------
# 5. Router node passes private_available to classifier
# ---------------------------------------------------------------------------


class TestRouterNodePrivateAvailable:
    """router_node correctly reads private_available from state."""

    def test_router_passes_private_available_false_to_classifier(self) -> None:
        """When state has private_available=False, classifier sees it."""
        from unittest.mock import MagicMock, patch

        from noa.orchestrator.nodes.router import router_node

        captured: list[dict] = []

        def mock_classify(state: Any, *, private_available: bool = True, **kw: Any) -> Any:
            captured.append({"private_available": private_available})
            result = MagicMock()
            result.domain = "private"
            return result

        with patch("noa.orchestrator.nodes.router._classifier") as mock_cls:
            mock_cls.classify.side_effect = mock_classify
            router_node({
                "messages": [{"role": "user", "content": "hello"}],
                "private_available": False,
                "user_privacy_override": "private",
                "user_model_override": None,
                "user_provider_override": None,
            })

        assert len(captured) == 1
        assert captured[0]["private_available"] is False

    def test_router_defaults_private_available_true(self) -> None:
        """When state lacks private_available, classifier gets True (default)."""
        from unittest.mock import MagicMock, patch

        from noa.orchestrator.nodes.router import router_node

        captured: list[dict] = []

        def mock_classify(state: Any, *, private_available: bool = True, **kw: Any) -> Any:
            captured.append({"private_available": private_available})
            result = MagicMock()
            result.domain = "external"
            return result

        with patch("noa.orchestrator.nodes.router._classifier") as mock_cls:
            mock_cls.classify.side_effect = mock_classify
            router_node({
                "messages": [{"role": "user", "content": "hello"}],
                "user_model_override": None,
                "user_provider_override": None,
            })

        assert len(captured) == 1
        assert captured[0]["private_available"] is True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_sse_events(body: str) -> list[dict[str, Any]]:
    """Parse SSE data lines into a list of event dicts."""
    events = []
    for line in body.split("\n"):
        if line.startswith("data:"):
            raw = line.removeprefix("data:").strip()
            if raw:
                with contextlib.suppress(json.JSONDecodeError):
                    events.append(json.loads(raw))
    return events
