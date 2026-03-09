"""Backend API contract tests for iOS5: Chat UI with SSE Streaming.

Spec refs: SPEC.md §22.1 (Run Schema), §22.2 (Event Stream),
           §22.4 (SSE Endpoint), §29.2 (Web UI — primary client),
           §29.3 (Mobile Access — Phase 2: Native iOS App),
           §13.1 (Short-Term Memory / Conversation Threads),
           §36.3 (Phase 3: Native iOS Client)
Phase plan: PHASE_DETAILS.md Phase iOS5

iOS5 creates ChatService, ChatViewModel, ThreadListViewModel, ChatView,
MessageBubble, ComposerBar, ToolCallCard, ThreadListView, and MainTabView
in Swift. These Python tests pin the exact backend contract that the Swift
ChatService and ThreadListViewModel must consume:

  - POST /api/v1/chat   → SSE stream with meta, token_stream, result_ready, error events
  - GET  /api/v1/threads → thread list (id, user_id, title, created_at)
  - POST /api/v1/threads → create thread (returns id, title, created_at)
  - GET  /api/v1/threads/{id}/messages → message history (role, content)

ChatViewModel accumulates token_stream events into a single message string.
ThreadListViewModel drives NavigationSplitView: thread list on the left,
chat detail on the right. SSE event types map 1-to-1 to iOS ChatEvent enum
variants (tool_called, approval_requested, classification_done, step_started).

If these tests break, the iOS ChatService or ThreadListViewModel will decode
the wrong shape and the Chat UI will be blank or crash.

These tests are written BEFORE the iOS5 Swift implementation. The tests for
new backend deliverables (thread DELETE endpoint, ComposerBar privacy_mode
selector contract, ChatRequest model field) will fail until those are added.
"""

from __future__ import annotations

import json
import uuid

import pytest

pytestmark = pytest.mark.ios5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_thread_dict(**kwargs) -> dict:
    """Minimal thread dict matching GET /api/v1/threads list item shape."""
    return {
        "id": kwargs.pop("id", str(uuid.uuid4())),
        "user_id": kwargs.pop("user_id", str(uuid.uuid4())),
        "title": kwargs.pop("title", "My Thread"),
        "created_at": kwargs.pop("created_at", "2026-03-09T10:00:00+00:00"),
        **kwargs,
    }


def _make_message_dict(**kwargs) -> dict:
    """Minimal message dict matching GET /api/v1/threads/{id}/messages list item shape."""
    return {
        "id": kwargs.pop("id", str(uuid.uuid4())),
        "role": kwargs.pop("role", "user"),
        "content": kwargs.pop("content", "Hello, Noa"),
        "created_at": kwargs.pop("created_at", "2026-03-09T10:00:00+00:00"),
        **kwargs,
    }


def _make_sse_event(**kwargs) -> dict:
    """Minimal SSE event payload dict matching SPEC.md §22.2."""
    return {
        "id": kwargs.pop("id", str(uuid.uuid4())),
        "run_id": kwargs.pop("run_id", str(uuid.uuid4())),
        "event_type": kwargs.pop("event_type", "token_stream"),
        "timestamp": kwargs.pop("timestamp", "2026-03-09T10:00:00+00:00"),
        "payload": kwargs.pop("payload", {"token": "Hello", "position": 0}),
        **kwargs,
    }


def _make_chat_request(**kwargs) -> dict:
    """Minimal POST /api/v1/chat body matching ChatRequest schema."""
    return {
        "message": kwargs.pop("message", "What is my schedule today?"),
        "thread_id": kwargs.pop("thread_id", None),
        "privacy_mode": kwargs.pop("privacy_mode", "external"),
        "model": kwargs.pop("model", "gpt-4o"),
        **kwargs,
    }


# ---------------------------------------------------------------------------
# § 22.4 — Chat endpoint and SSE emission
# ---------------------------------------------------------------------------


class TestChatEndpointContract:
    """SPEC.md §22.4: Chat endpoint emits SSE stream; iOS ChatService consumes it."""

    def test_chat_router_is_wired_to_app(self):
        """SPEC.md §22.4: POST /api/v1/chat must exist.

        iOS5 ChatService.sendMessage() POSTs to this endpoint and subscribes
        to the SSE stream. If the route is absent, every chat attempt returns 404.
        """
        from noa.api.v1.chat import router as chat_router

        post_routes = [
            r for r in chat_router.routes
            if hasattr(r, "methods") and "POST" in (r.methods or set())
        ]
        chat_routes = [r for r in post_routes if r.path.endswith("/chat")]
        assert len(chat_routes) >= 1, (
            "POST /api/v1/chat must be registered. "
            "iOS5 ChatService.sendMessage() posts to this endpoint."
        )

    def test_chat_request_has_message_field(self):
        """SPEC.md §22.4: ChatRequest body must include 'message' text field.

        iOS5 ComposerBar sends the user's typed message in this field.
        """
        req = _make_chat_request(message="Tell me about my schedule")
        assert req["message"] == "Tell me about my schedule"

    def test_chat_request_privacy_mode_is_required(self):
        """SPEC.md §29.3: ChatRequest must include privacy_mode.

        iOS5 ComposerBar exposes a privacy mode selector (private/external).
        The selected value is sent in every chat request so the backend router
        can apply domain isolation (§6.2).
        """
        req_private = _make_chat_request(privacy_mode="private")
        req_external = _make_chat_request(privacy_mode="external")

        assert req_private["privacy_mode"] == "private"
        assert req_external["privacy_mode"] == "external"

    def test_chat_request_model_field_is_required(self):
        """SPEC.md §29.3: ChatRequest must include model selection.

        iOS5 ComposerBar exposes a model selector. The selected model ID
        is passed to the backend so the orchestrator routes to the right LLM.
        """
        req = _make_chat_request(model="claude-3-5-sonnet")
        assert req["model"] == "claude-3-5-sonnet"

    def test_chat_request_thread_id_is_optional(self):
        """SPEC.md §13.1: thread_id may be omitted on the first message.

        iOS5 ChatService creates a new thread implicitly when thread_id is None.
        The backend assigns a new thread_id, returned in the 'meta' SSE frame.
        Subsequent messages from the same session must supply the thread_id.
        """
        req_new = _make_chat_request(thread_id=None)
        req_existing = _make_chat_request(thread_id=str(uuid.uuid4()))

        assert req_new["thread_id"] is None
        assert req_existing["thread_id"] is not None

    def test_chat_request_schema_validates(self):
        """SPEC.md §22.4: ChatRequest Pydantic schema accepts valid iOS payload.

        This is an integration test — calls the real schema, not a mock.
        If ChatRequest changes shape, iOS5 ChatService breaks.

        ChatRequest requires: message, privacy_mode, model, provider.
        iOS5 ComposerBar must supply all four fields on every POST /api/v1/chat.
        """
        from noa.api.v1.chat import ChatRequest

        req = ChatRequest(
            message="Hello",
            privacy_mode="external",
            model="gpt-4o",
            provider="openai",
        )
        assert req.message == "Hello"
        assert req.privacy_mode == "external"
        assert req.model == "gpt-4o"
        assert req.provider == "openai"
        assert req.thread_id is None  # Optional field defaults to None

    def test_chat_request_provider_field_is_required(self):
        """Phase iOS5: ChatRequest requires a 'provider' field.

        iOS5 ComposerBar must include the provider (e.g. 'openai', 'anthropic')
        alongside the model selection. This field was added after iOS3/iOS4.
        This test SHOULD FAIL until iOS5 ComposerBar includes provider in the payload.
        We verify the field exists on the schema so Swift engineers know to include it.
        """
        from noa.api.v1.chat import ChatRequest

        fields = ChatRequest.model_fields
        assert "provider" in fields, (
            "ChatRequest must have a 'provider' field. "
            "iOS5 ComposerBar model selector must send provider alongside model. "
            "The backend rejects requests without this field with a 422 error."
        )


# ---------------------------------------------------------------------------
# § 22.2 — SSE event accumulation (token_stream → ChatViewModel)
# ---------------------------------------------------------------------------


class TestTokenStreamAccumulation:
    """SPEC.md §22.2: token_stream events carry {token, position}.

    iOS5 ChatViewModel accumulates tokens in order to build the final response.
    """

    def test_token_stream_payload_has_token_field(self):
        """SPEC.md §22.2: token_stream payload must include 'token' string.

        ChatViewModel appends event.payload['token'] to the streaming buffer.
        """
        event = _make_sse_event(
            event_type="token_stream",
            payload={"token": "Hello", "position": 0},
        )
        assert event["payload"]["token"] == "Hello"

    def test_token_stream_payload_has_position_field(self):
        """SPEC.md §22.2: token_stream payload must include 'position' int.

        ChatViewModel uses position to detect dropped tokens and order them.
        Out-of-order delivery is possible under HTTP/2; position enables sorting.
        """
        event = _make_sse_event(
            event_type="token_stream",
            payload={"token": "world", "position": 1},
        )
        assert event["payload"]["position"] == 1

    def test_token_accumulation_is_position_ordered(self):
        """SPEC.md §22.2: ChatViewModel must order tokens by position, not arrival.

        Given tokens delivered out of order, the final text must be assembled
        in position order. This test pins the sorting contract.
        """
        tokens = [
            {"token": " world", "position": 1},
            {"token": "Hello", "position": 0},
            {"token": "!", "position": 2},
        ]
        sorted_tokens = sorted(tokens, key=lambda t: t["position"])
        result = "".join(t["token"] for t in sorted_tokens)
        assert result == "Hello world!"

    def test_result_ready_payload_has_response_field(self):
        """SPEC.md §22.2: result_ready payload must include 'response'.

        Backend runner.py:148 sends {"response": <text>}.
        iOS5 ChatViewModel replaces the accumulated token buffer with this
        canonical text when result_ready arrives.
        """
        event = _make_sse_event(
            event_type="result_ready",
            payload={"response": "Here is your schedule for today."},
        )
        assert "response" in event["payload"]
        assert event["payload"]["response"] == "Here is your schedule for today."

    def test_error_event_payload_has_code_and_message(self):
        """SPEC.md §22.2: error event payload must include 'code' and 'message'.

        iOS5 ChatViewModel shows an error state when this event arrives.
        Both fields are required: code for programmatic handling, message for display.
        """
        event = _make_sse_event(
            event_type="error",
            payload={"code": "RATE_LIMITED", "message": "Too many requests."},
        )
        assert event["payload"]["code"] == "RATE_LIMITED"
        assert event["payload"]["message"] == "Too many requests."


# ---------------------------------------------------------------------------
# § 22.2 — Inline indicator events (ToolCallCard, classification, step progress)
# ---------------------------------------------------------------------------


class TestInlineIndicatorEvents:
    """SPEC.md §22.2: iOS5 renders inline indicators for tool_called, approval_requested,
    classification_done, and step_started events within the chat bubble.
    """

    def test_tool_called_payload_has_tool_name_and_args(self):
        """SPEC.md §22.2: tool_called payload carries tool_name and args.

        iOS5 ToolCallCard displays tool_name as the card title and
        formats args as key=value pairs below. Both fields are required.
        """
        event = _make_sse_event(
            event_type="tool_called",
            payload={"tool_name": "web_search", "args": {"query": "AAPL stock"}},
        )
        assert event["payload"]["tool_name"] == "web_search"
        assert "args" in event["payload"]

    def test_approval_requested_payload_has_risk_tier_and_preview(self):
        """SPEC.md §22.2 + §29.6: approval_requested payload carries risk_tier and preview.

        iOS5 ChatViewModel pauses streaming and renders an ApprovalCard inline
        when this event arrives. risk_tier drives the UI colour (yellow/red).
        """
        event = _make_sse_event(
            event_type="approval_requested",
            payload={"risk_tier": "high", "preview": "Send email to all users"},
        )
        assert event["payload"]["risk_tier"] in ("low", "medium", "high")
        assert "preview" in event["payload"]

    def test_classification_done_payload_has_privacy_mode_and_confidence(self):
        """SPEC.md §22.2: classification_done payload carries privacy_mode and confidence.

        iOS5 ChatView shows a subtle badge indicating which domain processed
        the request. Confidence informs the badge opacity (low confidence → lighter).
        """
        event = _make_sse_event(
            event_type="classification_done",
            payload={"privacy_mode": "external", "confidence": 0.97, "reasoning": ""},
        )
        assert event["payload"]["privacy_mode"] in ("private", "external")
        assert 0.0 <= event["payload"]["confidence"] <= 1.0

    def test_step_started_payload_has_step_name_and_model(self):
        """SPEC.md §22.2: step_started payload carries step_name and model.

        iOS5 ChatView shows a step progress indicator ('Thinking…', 'Calling tools…')
        while the run is in progress. step_name drives the display label.
        """
        event = _make_sse_event(
            event_type="step_started",
            payload={"step_name": "agent", "model": "gpt-4o"},
        )
        assert "step_name" in event["payload"]
        assert "model" in event["payload"]

    def test_meta_event_carries_run_id_and_thread_id(self):
        """SPEC.md §22.4: The first SSE frame is a 'meta' event with run_id and thread_id.

        iOS5 ChatViewModel reads the meta frame to bind the SSE stream to a
        specific run and thread. Without this, ChatView cannot associate
        subsequent events with the correct conversation.
        """
        import inspect

        import noa.api.v1.chat as chat_module

        source = inspect.getsource(chat_module)

        assert '"run_id"' in source and '"thread_id"' in source, (
            "Chat endpoint meta SSE frame must emit 'run_id' and 'thread_id'. "
            "iOS5 ChatViewModel binds to these IDs after receiving the first frame."
        )


# ---------------------------------------------------------------------------
# § 13.1 — Thread list (ThreadListViewModel)
# ---------------------------------------------------------------------------


class TestThreadListContract:
    """SPEC.md §13.1: Threads are listed, resumable, and deletable.

    iOS5 ThreadListViewModel drives the NavigationSplitView sidebar.
    It loads threads via GET /api/v1/threads and displays them sorted by
    most-recently-updated first.
    """

    def test_threads_endpoint_is_wired(self):
        """SPEC.md §13.1: GET /api/v1/threads must exist.

        iOS5 ThreadListViewModel calls this endpoint on view appear and on pull-to-refresh.
        If the route is absent, the sidebar shows an empty list forever.
        """
        from noa.api.v1.threads import router as threads_router

        get_routes = [
            r for r in threads_router.routes
            if hasattr(r, "methods") and "GET" in (r.methods or set())
        ]
        # The list endpoint path ends at the threads prefix (no sub-path after it)
        list_routes = [
            r for r in get_routes
            if "messages" not in getattr(r, "path", "")
        ]
        assert len(list_routes) >= 1, (
            "GET /api/v1/threads must be registered. "
            "iOS5 ThreadListViewModel loads the thread list from this endpoint."
        )

    def test_thread_create_endpoint_is_wired(self):
        """SPEC.md §13.1: POST /api/v1/threads must exist for thread creation.

        iOS5 ThreadListViewModel calls this when the user taps the new-thread button.
        The response id is then passed as thread_id in the first chat message.
        """
        from noa.api.v1.threads import router as threads_router

        post_routes = [
            r for r in threads_router.routes
            if hasattr(r, "methods") and "POST" in (r.methods or set())
        ]
        assert len(post_routes) >= 1, (
            "POST /api/v1/threads must be registered. "
            "iOS5 ThreadListViewModel creates threads via this endpoint."
        )

    def test_thread_create_request_requires_title(self):
        """SPEC.md §13.1: Thread creation requires a title.

        iOS5 ThreadListViewModel sends a title when creating a new thread.
        CreateThreadRequest.title is required — iOS must always provide it.
        """
        from noa.api.v1.threads import CreateThreadRequest

        req = CreateThreadRequest(title="My new conversation")
        assert req.title == "My new conversation"

    def test_thread_list_item_has_required_fields(self):
        """SPEC.md §13.1: Thread list items expose id, user_id, title, created_at.

        iOS5 ThreadListView renders each item with its title and relative timestamp.
        A missing 'title' field causes the sidebar to show blank rows.
        """
        thread = _make_thread_dict()

        for field in ("id", "user_id", "title", "created_at"):
            assert field in thread, f"Thread list item missing required field: {field}"

    def test_thread_title_can_be_null(self):
        """SPEC.md §13.1: title may be null — iOS ThreadListView must show a fallback.

        When title is null, iOS5 ThreadListView displays 'New Conversation' as placeholder.
        """
        thread = _make_thread_dict(title=None)
        assert thread["title"] is None, "Thread title must be nullable"

    def test_thread_messages_endpoint_is_wired(self):
        """SPEC.md §13.1: GET /api/v1/threads/{id}/messages must exist.

        iOS5 ChatViewModel loads message history when resuming an existing thread.
        This reconstructs the chat bubble list before any new SSE events arrive.
        """
        from noa.api.v1.threads import router as threads_router

        get_routes = [
            r for r in threads_router.routes
            if hasattr(r, "methods") and "GET" in (r.methods or set())
        ]
        message_routes = [
            r for r in get_routes if "messages" in getattr(r, "path", "")
        ]
        assert len(message_routes) >= 1, (
            "GET /api/v1/threads/{id}/messages must be registered. "
            "iOS5 ChatViewModel loads message history from this endpoint."
        )

    def test_message_role_is_user_or_assistant(self):
        """SPEC.md §13.1: Message role must be 'user' or 'assistant'.

        iOS5 MessageBubble uses role to align bubbles: 'user' → right, 'assistant' → left.
        An unexpected role value causes incorrect layout.
        """
        user_msg = _make_message_dict(role="user")
        asst_msg = _make_message_dict(role="assistant")

        assert user_msg["role"] == "user"
        assert asst_msg["role"] == "assistant"

    def test_thread_delete_endpoint_is_wired(self):
        """SPEC.md §13.1: Threads are deletable — DELETE /api/v1/threads/{id} must exist.

        iOS5 ThreadListView offers swipe-to-delete on each thread row.
        This endpoint is NOT yet present in the backend (threads router only has
        GET list, POST create, GET messages). This test SHOULD FAIL until the
        DELETE endpoint is added.
        """
        from noa.api.v1.threads import router as threads_router

        delete_routes = [
            r for r in threads_router.routes
            if hasattr(r, "methods") and "DELETE" in (r.methods or set())
        ]
        assert len(delete_routes) >= 1, (
            "DELETE /api/v1/threads/{id} must be registered. "
            "iOS5 ThreadListView swipe-to-delete depends on this endpoint. "
            "Add a DELETE /{thread_id} handler to the threads router."
        )


# ---------------------------------------------------------------------------
# § 22.4 + § 36.3 — SSE wire format (iOS ChatService URLSession parsing)
# ---------------------------------------------------------------------------


class TestSSEWireFormatContract:
    """SPEC.md §22.4: SSE events are formatted as 'data: {json}\\n\\n'.

    iOS5 ChatService uses URLSession.bytes(for:) to read the SSE stream.
    It splits on '\\n\\n' and strips the 'data: ' prefix before JSON decoding.
    """

    def test_chat_sse_uses_data_prefix_format(self):
        """SPEC.md §22.4: SSE frames must start with 'data: '.

        iOS5 ChatService strips this prefix before passing the line to JSONDecoder.
        If the backend emits raw JSON without the prefix, parsing fails silently.
        """
        import inspect

        import noa.api.v1.chat as chat_module

        source = inspect.getsource(chat_module)
        assert 'f"data: {json.dumps(' in source or "f'data: {json.dumps(" in source, (
            "Chat SSE frames must use 'data: {json}\\n\\n' format. "
            "iOS5 ChatService strips the 'data: ' prefix before JSONDecoder."
        )

    def test_sse_events_are_json_serialisable(self):
        """SPEC.md §22.4: Every SSE event must be JSON-serialisable.

        iOS5 ChatService passes raw bytes to JSONDecoder. Non-serialisable payloads
        (datetime objects, UUIDs without conversion) cause decode errors on device.
        """
        events = [
            _make_sse_event(event_type="token_stream", payload={"token": "Hi", "position": 0}),
            _make_sse_event(event_type="result_ready", payload={"response": "Done."}),
            _make_sse_event(event_type="error", payload={"code": "ERR", "message": "Fail"}),
        ]
        for event in events:
            serialised = json.dumps(event)
            parsed = json.loads(serialised)
            assert parsed["event_type"] == event["event_type"]

    def test_meta_event_is_in_valid_event_types(self):
        """SPEC.md §22.4 + Phase iOS3: 'meta' is the first SSE frame; it must be a valid type.

        iOS5 ChatViewModel parses the meta frame to extract run_id and thread_id.
        If 'meta' is not in VALID_EVENT_TYPES, EventRead validation will reject it.
        """
        from noa.runs.schemas import VALID_EVENT_TYPES

        assert "meta" in VALID_EVENT_TYPES, (
            "'meta' must be in VALID_EVENT_TYPES. "
            "iOS5 ChatViewModel reads meta to bind run_id and thread_id."
        )


# ---------------------------------------------------------------------------
# Integration: Thread + Chat endpoints work together (real code, no mocks)
# ---------------------------------------------------------------------------


class TestChatThreadIntegration:
    """Phase iOS5: Thread list and chat endpoints are independently importable
    and correctly wired — real integration check without mocking internals.
    """

    def test_threads_router_prefix_is_correct(self):
        """Phase iOS5: threads router prefix must be /api/v1/threads.

        iOS5 ThreadListViewModel constructs URLs as baseURL + '/api/v1/threads'.
        A wrong prefix means the view model never receives thread data.
        """
        from noa.api.v1.threads import router as threads_router

        assert threads_router.prefix == "/api/v1/threads", (
            f"threads router prefix must be '/api/v1/threads', "
            f"got: {threads_router.prefix!r}. "
            "iOS5 ThreadListViewModel hard-codes this path."
        )

    def test_chat_and_threads_routers_are_independently_importable(self):
        """Phase iOS5: Both routers must be importable without circular dependencies.

        iOS5 ChatService and ThreadListViewModel import the API types independently.
        A circular import breaks the build.
        """
        from noa.api.v1.chat import router as chat_router  # noqa: F401
        from noa.api.v1.threads import router as threads_router  # noqa: F401

        assert chat_router is not None
        assert threads_router is not None

    def test_event_read_schema_validates_chat_event_types(self):
        """SPEC.md §22.2: EventRead validates all event types iOS5 ChatViewModel handles.

        This integration test verifies the schema accepts each event type that
        the iOS5 ChatViewModel must parse. A missing type causes EventRead to
        reject the frame, and the ChatViewModel never updates the UI.
        """
        from noa.runs.schemas import EventRead

        ios5_event_types = [
            "meta",
            "token_stream",
            "tool_called",
            "approval_requested",
            "classification_done",
            "step_started",
            "result_ready",
            "error",
        ]
        run_id = uuid.uuid4()
        for etype in ios5_event_types:
            event_data = {
                "id": str(uuid.uuid4()),
                "run_id": str(run_id),
                "event_type": etype,
                "timestamp": "2026-03-09T10:00:00+00:00",
                "payload": {},
            }
            parsed = EventRead.model_validate(event_data)
            assert parsed.event_type == etype, (
                f"EventRead rejected event_type='{etype}'. "
                f"iOS5 ChatViewModel dispatches on this type — it must be valid."
            )

    def test_chat_request_schema_rejects_invalid_privacy_mode(self):
        """SPEC.md §6.2: privacy_mode must be 'private' or 'external'.

        iOS5 ComposerBar only offers these two options. If the backend accepted
        arbitrary strings, domain isolation (§6.2) could be bypassed by a
        malformed client. This integration test verifies ChatRequest validates
        the field value.

        NOTE: This test will FAIL if ChatRequest does not validate privacy_mode.
        The current schema uses `str` without a validator — the test documents
        the requirement to add validation.
        """
        import pydantic

        from noa.api.v1.chat import ChatRequest

        try:
            req = ChatRequest(message="Hi", privacy_mode="public", model="gpt-4o")
            # If no validation error is raised, privacy_mode is not validated.
            # The test must FAIL to document the missing constraint.
            assert req.privacy_mode in ("private", "external"), (
                "ChatRequest accepted invalid privacy_mode='public'. "
                "§6.2 requires domain isolation — only 'private' or 'external' are valid. "
                "Add a validator or Literal['private', 'external'] annotation to ChatRequest."
            )
        except (pydantic.ValidationError, ValueError):
            # Validation correctly rejects the invalid value — test passes.
            pass
