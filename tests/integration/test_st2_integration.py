"""Integration tests for ST2: Chat History & Tool Persistence (CHAT-H1).

Uses a real PostgreSQL database (via pg_app fixture) to verify that:
1. Tool-aware messages are persisted correctly to the messages table
2. _load_thread_history() returns full tool context from DB
3. The Message model columns (tool_calls, tool_call_id, tool_name) work end-to-end
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from tests.integration.conftest import register_and_login


@pytest.mark.asyncio
async def test_tool_message_columns_persist_and_load(pg_app: Any) -> None:
    """ST2 round-trip: persist tool messages via DB service, load back via _load_thread_history.

    Flow:
    1. Create user via API.
    2. Directly write Message rows with tool_calls / tool_call_id / tool_name.
    3. Call _load_thread_history() to verify all columns are returned correctly.
    """
    from noa.api import app_state
    from noa.api.v1.chat import _load_thread_history
    from noa.db.models.conversation import Conversation, Message

    sf = app_state.get_session_factory()
    assert sf is not None, "session factory must be set for integration test"

    transport = httpx.ASGITransport(app=pg_app)  # type: ignore[arg-type]
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        tokens = await register_and_login(client, "st2_tool_persist@example.com")
        access_token = tokens["access_token"]

        # Decode user_id from JWT
        import base64
        import json as _json
        payload_b64 = access_token.split(".")[1]
        padding = 4 - len(payload_b64) % 4
        uid = uuid.UUID(_json.loads(base64.urlsafe_b64decode(payload_b64 + "=" * padding))["sub"])

        tid = uuid.uuid4()

    # Insert test data directly into the DB
    async with sf() as session:
        session.add(Conversation(id=tid, user_id=uid, title="ST2 Test", domain="external"))
        await session.flush()

        now = datetime.now(UTC)

        # Turn 1 messages
        session.add(Message(
            id=uuid.uuid4(), thread_id=tid, user_id=uid,
            role="user", content="Send an email to alice@example.com",
        ))
        session.add(Message(
            id=uuid.uuid4(), thread_id=tid, user_id=uid,
            role="assistant", content=None,
            tool_calls=[{"id": "call_int_1", "name": "email.send", "input": {"to": "alice@example.com"}}],
        ))
        session.add(Message(
            id=uuid.uuid4(), thread_id=tid, user_id=uid,
            role="tool", content='{"success": true, "message_id": "msg_abc"}',
            tool_call_id="call_int_1", tool_name="email.send",
        ))
        session.add(Message(
            id=uuid.uuid4(), thread_id=tid, user_id=uid,
            role="assistant", content="Email sent to alice@example.com.",
        ))
        await session.commit()

    # Load history via the real function (uses the wired session factory)
    with patch("noa.api.v1.chat._get_session_factory", return_value=sf):
        history = await _load_thread_history(str(tid), str(uid))

    assert len(history) == 4, f"Expected 4 messages, got {len(history)}: {history}"

    # user message
    assert history[0]["role"] == "user"
    assert "alice@example.com" in history[0]["content"]

    # assistant with tool_calls
    asst_tc = history[1]
    assert asst_tc["role"] == "assistant"
    assert "tool_calls" in asst_tc
    tcs = asst_tc["tool_calls"]
    assert isinstance(tcs, list)
    assert len(tcs) == 1
    assert tcs[0]["id"] == "call_int_1"
    assert tcs[0]["name"] == "email.send"

    # tool result
    tool_msg = history[2]
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == "call_int_1"
    assert tool_msg["name"] == "email.send"
    assert "success" in tool_msg["content"]

    # final assistant text
    final = history[3]
    assert final["role"] == "assistant"
    assert "Email sent" in final["content"]
    assert "tool_calls" not in final


@pytest.mark.asyncio
async def test_persist_messages_with_tool_context(pg_app: Any) -> None:
    """_persist_messages() with turn_messages saves all rows correctly."""
    from noa.api import app_state
    from noa.api.v1.chat import _load_thread_history, _persist_messages
    from noa.db.models.conversation import Conversation

    sf = app_state.get_session_factory()
    assert sf is not None

    transport = httpx.ASGITransport(app=pg_app)  # type: ignore[arg-type]
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        tokens = await register_and_login(client, "st2_persist_fn@example.com")
        access_token = tokens["access_token"]

        import base64
        import json as _json
        payload_b64 = access_token.split(".")[1]
        padding = 4 - len(payload_b64) % 4
        uid = uuid.UUID(_json.loads(base64.urlsafe_b64decode(payload_b64 + "=" * padding))["sub"])

    tid = uuid.uuid4()
    run_id = str(uuid.uuid4())

    # Pre-create the conversation so _persist_messages doesn't create a duplicate
    async with sf() as session:
        session.add(Conversation(id=tid, user_id=uid, title="Persist test", domain="external"))
        await session.commit()

    turn_messages = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "call_p1", "name": "calendar.create_event", "input": {"title": "Team sync"}}],
        },
        {
            "role": "tool",
            "tool_call_id": "call_p1",
            "name": "calendar.create_event",
            "content": '{"event_id": "ev_999", "success": true}',
        },
    ]

    with patch("noa.api.v1.chat._get_session_factory", return_value=sf):
        await _persist_messages(
            str(uid),
            str(tid),
            run_id,
            user_message="Schedule a team sync meeting",
            assistant_response="Team sync scheduled.",
            privacy_mode="external",
            turn_messages=turn_messages,
        )

    # Verify by loading history
    with patch("noa.api.v1.chat._get_session_factory", return_value=sf):
        history = await _load_thread_history(str(tid), str(uid))

    # Should be: user, assistant(tool_calls), tool, assistant(final)
    assert len(history) == 4, f"history: {history}"

    roles = [m["role"] for m in history]
    assert roles == ["user", "assistant", "tool", "assistant"]

    asst_tc = history[1]
    assert "tool_calls" in asst_tc
    assert asst_tc["tool_calls"][0]["name"] == "calendar.create_event"

    tool_msg = history[2]
    assert tool_msg["tool_call_id"] == "call_p1"
    assert tool_msg["name"] == "calendar.create_event"

    assert history[3]["content"] == "Team sync scheduled."
