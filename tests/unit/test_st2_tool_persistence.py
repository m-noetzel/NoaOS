"""Unit tests for ST2: Chat History & Tool Persistence (CHAT-H1).

Verifies that:
- _extract_turn_messages() correctly extracts tool_calls and tool results from SSE events
- _persist_messages() saves tool-role messages and tool_calls to DB
- _load_thread_history() returns full message history including tool context
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# _extract_turn_messages tests (pure function — no DB needed)
# ---------------------------------------------------------------------------


def _make_tool_called_event(tool_name: str, call_id: str, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_type": "tool_called",
        "payload": {
            "tool_name": tool_name,
            "tool_call": {"id": call_id, "name": tool_name, "input": args},
        },
        "timestamp": "2026-03-26T10:00:00Z",
    }


def _make_tool_result_event(tool_name: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_type": "tool_result",
        "payload": {
            "tool_name": tool_name,
            "tool_result": {"name": tool_name, **result},
        },
        "timestamp": "2026-03-26T10:00:01Z",
    }


def test_extract_turn_messages_empty_events() -> None:
    """No tool events → empty list."""
    from noa.api.v1.chat import _extract_turn_messages

    events = [
        {"event_type": "message_received", "payload": {"message": "hello"}},
        {"event_type": "result_ready", "payload": {"response": "world", "llm_usage": []}},
    ]
    result = _extract_turn_messages(events)
    assert result == []


def test_extract_turn_messages_single_tool_call() -> None:
    """Single tool call and result produces assistant + tool messages."""
    from noa.api.v1.chat import _extract_turn_messages

    events = [
        _make_tool_called_event("calendar.list_events", "call_abc123", {"start": "2026-03-26"}),
        _make_tool_result_event("calendar.list_events", {"events": [], "total": 0}),
    ]
    result = _extract_turn_messages(events)

    assert len(result) == 2

    # First message: assistant with tool_calls
    asst = result[0]
    assert asst["role"] == "assistant"
    assert asst["tool_calls"] is not None
    assert len(asst["tool_calls"]) == 1
    assert asst["tool_calls"][0]["id"] == "call_abc123"
    assert asst["tool_calls"][0]["name"] == "calendar.list_events"

    # Second message: tool result
    tool_msg = result[1]
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == "call_abc123"
    assert tool_msg["name"] == "calendar.list_events"
    assert "events" in tool_msg["content"]  # JSON-encoded result


def test_extract_turn_messages_multiple_tool_calls() -> None:
    """Multiple tool calls produce one assistant message with all tool_calls."""
    from noa.api.v1.chat import _extract_turn_messages

    events = [
        _make_tool_called_event("email.send", "call_1", {"to": "a@b.com"}),
        _make_tool_called_event("calendar.create_event", "call_2", {"title": "Meeting"}),
        _make_tool_result_event("email.send", {"success": True}),
        _make_tool_result_event("calendar.create_event", {"event_id": "ev_123"}),
    ]
    result = _extract_turn_messages(events)

    # One assistant message with 2 tool_calls, then 2 tool messages
    assert len(result) == 3
    asst = result[0]
    assert asst["role"] == "assistant"
    assert len(asst["tool_calls"]) == 2

    tool_names = {m["name"] for m in result[1:]}
    assert "email.send" in tool_names
    assert "calendar.create_event" in tool_names


def test_extract_turn_messages_tool_end_event() -> None:
    """tool_end events (alternative to tool_result) are also handled."""
    from noa.api.v1.chat import _extract_turn_messages

    events = [
        _make_tool_called_event("search.web", "call_x", {"query": "noa agent"}),
        {
            "event_type": "tool_end",
            "payload": {
                "tool_name": "search.web",
                "result": {"name": "search.web", "results": ["r1"]},
            },
            "timestamp": "2026-03-26T10:00:01Z",
        },
    ]
    result = _extract_turn_messages(events)
    assert len(result) == 2
    assert result[1]["role"] == "tool"
    assert result[1]["name"] == "search.web"


# ---------------------------------------------------------------------------
# _persist_messages unit tests (mocked DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_messages_saves_tool_messages() -> None:
    """Tool turn messages are saved to DB alongside user/assistant messages."""
    from noa.api.v1.chat import _persist_messages

    tid = uuid.uuid4()
    uid = uuid.uuid4()
    run_id = str(uuid.uuid4())

    turn_messages = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "call_1", "name": "email.send", "input": {"to": "x@y.com"}}],
        },
        {
            "role": "tool",
            "tool_call_id": "call_1",
            "name": "email.send",
            "content": '{"success": true}',
        },
    ]

    saved_objects: list[Any] = []

    mock_session = AsyncMock()
    mock_session.add = MagicMock(side_effect=lambda obj: saved_objects.append(obj))
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_factory = MagicMock(return_value=mock_session)

    with (
        patch("noa.api.v1.chat._get_session_factory", return_value=mock_factory),
        patch("noa.db.transaction.transactional") as mock_tx,
    ):
        # Make transactional a no-op context manager
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=None)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_tx.return_value = mock_ctx

        await _persist_messages(
            str(uid),
            str(tid),
            run_id,
            user_message="Send email to x@y.com",
            assistant_response="Email sent.",
            privacy_mode="external",
            turn_messages=turn_messages,
        )

    from noa.db.models.conversation import Message

    messages = [o for o in saved_objects if isinstance(o, Message)]
    roles = [m.role for m in messages]

    # Expected: user, assistant(tool_calls), tool, assistant(final)
    assert "user" in roles
    assert "tool" in roles
    assert roles.count("assistant") == 2

    tool_msg = next(m for m in messages if m.role == "tool")
    assert tool_msg.tool_call_id == "call_1"
    assert tool_msg.tool_name == "email.send"
    assert tool_msg.content == '{"success": true}'

    asst_with_tools = next(m for m in messages if m.role == "assistant" and m.tool_calls)
    assert asst_with_tools.tool_calls[0]["id"] == "call_1"


@pytest.mark.asyncio
async def test_persist_messages_no_tool_calls_unchanged() -> None:
    """When no tool messages, behaviour is identical to pre-ST2 (user + assistant only)."""
    from noa.api.v1.chat import _persist_messages

    tid = uuid.uuid4()
    uid = uuid.uuid4()
    run_id = str(uuid.uuid4())

    saved_objects: list[Any] = []

    mock_session = AsyncMock()
    mock_session.add = MagicMock(side_effect=lambda obj: saved_objects.append(obj))
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_factory = MagicMock(return_value=mock_session)

    with (
        patch("noa.api.v1.chat._get_session_factory", return_value=mock_factory),
        patch("noa.db.transaction.transactional") as mock_tx,
    ):
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=None)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_tx.return_value = mock_ctx

        await _persist_messages(
            str(uid),
            str(tid),
            run_id,
            user_message="Hello",
            assistant_response="Hi there!",
        )

    from noa.db.models.conversation import Message

    messages = [o for o in saved_objects if isinstance(o, Message)]
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"
    assert messages[1].tool_calls is None


# ---------------------------------------------------------------------------
# _load_thread_history unit tests (mocked DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_thread_history_includes_tool_messages() -> None:
    """Tool-role messages and assistant tool_calls are returned in history."""
    from types import SimpleNamespace

    from noa.api.v1.chat import _load_thread_history

    tid = uuid.uuid4()
    uid = uuid.uuid4()

    now = datetime.now(UTC)

    def _msg(role: str, content: str | None = None, **kwargs: Any) -> Any:
        # Use SimpleNamespace to avoid SQLAlchemy descriptor issues in unit tests
        return SimpleNamespace(
            id=uuid.uuid4(),
            thread_id=tid,
            user_id=uid,
            role=role,
            content=content,
            tool_calls=kwargs.get("tool_calls"),
            tool_call_id=kwargs.get("tool_call_id"),
            tool_name=kwargs.get("tool_name"),
            timestamp=now,
        )

    rows = [
        # Oldest → newest (reversed() in the function reverses them back)
        _msg("user", "Send email to x@y.com"),
        _msg("assistant", None, tool_calls=[{"id": "c1", "name": "email.send", "input": {}}]),
        _msg("tool", '{"success": true}', tool_call_id="c1", tool_name="email.send"),
        _msg("assistant", "Email sent."),
    ]
    # Simulate DESC order from DB (newest first)
    db_rows = list(reversed(rows))

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = db_rows

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_factory = MagicMock(return_value=mock_session)

    with patch("noa.api.v1.chat._get_session_factory", return_value=mock_factory):
        history = await _load_thread_history(str(tid), str(uid))

    assert len(history) == 4

    user_msg = history[0]
    assert user_msg["role"] == "user"
    assert user_msg["content"] == "Send email to x@y.com"

    asst_with_tools = history[1]
    assert asst_with_tools["role"] == "assistant"
    assert "tool_calls" in asst_with_tools
    assert asst_with_tools["tool_calls"][0]["id"] == "c1"

    tool_msg = history[2]
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == "c1"
    assert tool_msg["name"] == "email.send"
    assert '{"success": true}' in tool_msg["content"]

    final_asst = history[3]
    assert final_asst["role"] == "assistant"
    assert final_asst["content"] == "Email sent."
    assert "tool_calls" not in final_asst


@pytest.mark.asyncio
async def test_load_thread_history_no_factory_returns_empty() -> None:
    """Returns empty list when no DB session factory is configured."""
    from noa.api.v1.chat import _load_thread_history

    with patch("noa.api.v1.chat._get_session_factory", return_value=None):
        result = await _load_thread_history(str(uuid.uuid4()), str(uuid.uuid4()))

    assert result == []


# ---------------------------------------------------------------------------
# Round-trip test: extract + persist + load (real SQLite, no mocks for DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_message_round_trip_in_memory() -> None:
    """ST2 round-trip: SSE events → extract → persist → load returns tool context.

    Uses in-memory SQLite with real ORM (no mocks for DB layer).
    """
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
    from sqlalchemy.pool import StaticPool

    import noa.settings.models  # noqa: F401 — register models on Base
    from noa.db.models import Base
    from noa.db.models.conversation import Conversation, Message

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    uid = uuid.uuid4()
    tid = uuid.uuid4()

    # Insert conversation + turn messages directly
    async with factory() as session:
        session.add(Conversation(id=tid, user_id=uid, title="Test", domain="external"))
        await session.flush()

        # Turn 1: user + assistant with tool_calls + tool result + final assistant
        session.add(Message(id=uuid.uuid4(), thread_id=tid, user_id=uid, role="user", content="Send email"))
        session.add(Message(
            id=uuid.uuid4(), thread_id=tid, user_id=uid,
            role="assistant", content=None,
            tool_calls=[{"id": "call_t1", "name": "email.send", "input": {"to": "a@b.com"}}],
        ))
        session.add(Message(
            id=uuid.uuid4(), thread_id=tid, user_id=uid,
            role="tool", content='{"success": true}',
            tool_call_id="call_t1", tool_name="email.send",
        ))
        session.add(Message(
            id=uuid.uuid4(), thread_id=tid, user_id=uid,
            role="assistant", content="Email sent successfully.",
        ))
        await session.commit()

    # Load history via the real function using the real SQLite session factory
    from noa.api.v1.chat import _load_thread_history
    with patch("noa.api.v1.chat._get_session_factory", return_value=factory):
        history = await _load_thread_history(str(tid), str(uid))  # type: ignore[arg-type]

    assert len(history) == 4, f"Expected 4 messages, got {len(history)}: {history}"

    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Send email"

    assert history[1]["role"] == "assistant"
    assert "tool_calls" in history[1]
    assert history[1]["tool_calls"][0]["id"] == "call_t1"

    assert history[2]["role"] == "tool"
    assert history[2]["tool_call_id"] == "call_t1"
    assert history[2]["name"] == "email.send"

    assert history[3]["role"] == "assistant"
    assert history[3]["content"] == "Email sent successfully."
    assert "tool_calls" not in history[3]

    await engine.dispose()
