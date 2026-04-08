"""Typed SSE event dicts for the chat streaming protocol.

All events yielded by OrchestratorRunner and emitted by the /chat endpoint
conform to one of these TypedDicts. The ``event_type`` field is the
discriminator used by the frontend to route events.

Spec refs: SPEC.md §22.1, §22.2, §22.4
"""

from __future__ import annotations

from typing import Any, Literal, NotRequired

from typing_extensions import TypedDict


class MetaEvent(TypedDict):
    """First event in every SSE stream — identifies the run and thread.

    Emitted by the chat endpoint before the runner starts.

    OI8: When a domain mismatch is detected, the endpoint auto-creates a new
    thread in the correct domain instead of returning a 403.  In that case the
    meta event includes the redirect fields below so the frontend can update
    its active thread and show a toast.
    """

    event_type: Literal["meta"]
    run_id: str
    thread_id: str
    # OI8: Optional redirect fields — present only when a domain redirect occurred
    redirected: NotRequired[bool]
    original_thread_id: NotRequired[str]
    redirect_reason: NotRequired[str]


class TokenEvent(TypedDict):
    """Incremental LLM token for streaming responses (LS1).

    Emitted by OrchestratorRunner for each token chunk during streaming.
    event_type is ``token_stream``; payload carries the token text and run_id.
    """

    event_type: Literal["token_stream"]
    payload: _TokenPayload


class _TokenPayload(TypedDict):
    token: str
    run_id: str


class DoneEvent(TypedDict):
    """Terminal success event — run completed normally."""

    event_type: Literal["done"]
    payload: _DonePayload


class _DonePayload(TypedDict):
    run_id: str


class ErrorEvent(TypedDict):
    """Terminal error event — run failed."""

    event_type: Literal["error"]
    payload: _ErrorPayload


class _ErrorPayload(TypedDict):
    error: str


class ToolCallEvent(TypedDict):
    """Emitted when a tool is about to be invoked."""

    event_type: Literal["tool_called"]
    payload: _ToolCallPayload
    timestamp: str


class _ToolCallPayload(TypedDict):
    tool_name: str
    tool_call: dict[str, Any]


class ToolStartEvent(TypedDict):
    """Emitted when a tool execution starts (before result)."""

    event_type: Literal["tool_start"]
    payload: _ToolStartPayload
    timestamp: str


class _ToolStartPayload(TypedDict):
    tool_name: str


class ToolEndEvent(TypedDict):
    """Emitted when a tool execution completes (result available)."""

    event_type: Literal["tool_end"]
    payload: _ToolEndPayload
    timestamp: str


class _ToolEndPayload(TypedDict):
    tool_name: str
    result: dict[str, Any]


class ToolResultEvent(TypedDict):
    """Emitted after tool execution with full result (non-approval path)."""

    event_type: Literal["tool_result"]
    payload: _ToolResultPayload
    timestamp: str


class _ToolResultPayload(TypedDict):
    tool_name: str
    tool_result: dict[str, Any]


class ApprovalEvent(TypedDict):
    """Emitted when a tool call requires human approval."""

    event_type: Literal["approval_requested"]
    payload: _ApprovalPayload
    timestamp: str


class _ApprovalPayload(TypedDict):
    tool: str
    function: str
    args: dict[str, Any]
    risk_tier: str


class ResultReadyEvent(TypedDict):
    """Emitted when the LLM has produced its final response."""

    event_type: Literal["result_ready"]
    payload: _ResultReadyPayload
    timestamp: str


class _ResultReadyPayload(TypedDict):
    response: str
    total_cost: float
    llm_usage: list[dict[str, Any]]


class MessageReceivedEvent(TypedDict):
    """Emitted at the start of a run to echo the user message."""

    event_type: Literal["message_received"]
    payload: _MessageReceivedPayload
    timestamp: str


class _MessageReceivedPayload(TypedDict):
    message: str


class ClassificationDoneEvent(TypedDict):
    """Emitted after privacy mode classification."""

    event_type: Literal["classification_done"]
    payload: _ClassificationDonePayload
    timestamp: str


class _ClassificationDonePayload(TypedDict):
    privacy_mode: str
    model: str | None


class StepStartedEvent(TypedDict):
    """Emitted when a graph node completes execution."""

    event_type: Literal["step_started"]
    payload: _StepStartedPayload
    timestamp: str


class _StepStartedPayload(TypedDict):
    step: str


class QueuedEvent(TypedDict):
    """Emitted when a private-domain request is queued (domain unavailable)."""

    event_type: Literal["queued"]
    payload: _QueuedPayload


class _QueuedPayload(TypedDict):
    queue_id: str | None
    message: str


class CompactionEvent(TypedDict):
    """Emitted when context window compaction occurs (CC1).

    Signals the frontend that older messages were summarised to free up
    context space.  The ``messages_before`` / ``messages_after`` counts
    give the frontend enough information to show a visual indicator.
    """

    event_type: Literal["compaction"]
    payload: _CompactionPayload
    timestamp: str


class _CompactionPayload(TypedDict):
    messages_before: int
    messages_after: int
    model: str


# Union type for all valid SSE events emitted by the chat pipeline.
# Used for type narrowing in tests and consumers.
SSEEvent = (
    MetaEvent
    | TokenEvent
    | DoneEvent
    | ErrorEvent
    | ToolCallEvent
    | ToolStartEvent
    | ToolEndEvent
    | ToolResultEvent
    | ApprovalEvent
    | ResultReadyEvent
    | MessageReceivedEvent
    | ClassificationDoneEvent
    | StepStartedEvent
    | QueuedEvent
    | CompactionEvent
)

# All valid event_type literals (kept in sync with SSEEvent union above).
VALID_SSE_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "meta",
        "token_stream",
        "done",
        "error",
        "tool_called",
        "tool_start",
        "tool_end",
        "tool_result",
        "approval_requested",
        "result_ready",
        "message_received",
        "classification_done",
        "step_started",
        "queued",
        "compaction",
        "artifact_created",  # OV9: web search artifact report
    }
)
