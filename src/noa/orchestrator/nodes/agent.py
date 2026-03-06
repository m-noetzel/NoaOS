"""Agent node — invokes LLM with bounded autonomy.

Spec refs: SPEC.md S2.2 (bounded inner autonomy, max tool calls).

invoke_llm is a module-level async function that calls ProviderRouter.complete().
set_router() must be called at app startup to wire the router.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from noa.orchestrator.state import AgentState

# Maximum tool calls the agent will forward per step (S2.1 cost/iteration limits).
MAX_TOOL_CALLS = 10

# Module-level router reference, set at startup via set_router().
_router: Any | None = None


@dataclass
class LLMResponse:
    """Thin wrapper around ProviderRouter response dict.

    Provides `.content` and `.tool_calls` attribute access expected by agent_node.
    """

    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    provider: str = ""
    model: str = ""


def set_router(router: Any) -> None:
    """Set the module-level ProviderRouter. Called at app startup."""
    global _router  # noqa: PLW0603
    _router = router


def get_router() -> Any | None:
    """Return the current ProviderRouter (or None if not configured)."""
    return _router


async def invoke_llm(
    model: str,
    messages: list[dict[str, Any]],
    *,
    privacy_mode: str = "external",
    max_tokens: int = 4096,
) -> LLMResponse:
    """Invoke the LLM via ProviderRouter.

    Args:
        model: Model identifier (e.g. "anthropic/claude-haiku").
        messages: Conversation messages.
        privacy_mode: "external" or "private".
        max_tokens: Maximum tokens to generate.

    Returns:
        LLMResponse with content and tool_calls.

    Raises:
        RuntimeError: If no router is configured.
    """
    if _router is None:
        msg = "invoke_llm: no router configured — call set_router() at startup"
        raise RuntimeError(msg)

    # Parse provider from model string (e.g. "anthropic/claude-haiku" → "anthropic")
    provider: str | None = None
    model_name: str | None = None
    if "/" in model:
        provider, model_name = model.split("/", 1)
    else:
        model_name = model

    result: dict[str, Any] = await _router.complete(
        messages=messages,
        max_tokens=max_tokens,
        privacy_mode=privacy_mode,
        provider=provider,
        model=model_name,
    )

    return LLMResponse(
        content=result.get("content", ""),
        tool_calls=result.get("tool_calls", []),
        usage=result.get("usage", {}),
        provider=result.get("provider", ""),
        model=result.get("model", ""),
    )


async def agent_node(state: AgentState) -> dict[str, Any]:
    """Call the LLM and return tool_calls / response. Async pure function."""
    messages = state.get("messages", [])
    # Prefer per-node model_config over legacy selected_model (MR8).
    mc = state.get("model_config")
    if mc and "agent" in mc:
        model = mc["agent"]
    else:
        model = state.get("selected_model", "anthropic/claude-haiku")
    privacy_mode = state.get("privacy_mode", "external")

    response = await invoke_llm(model, messages, privacy_mode=privacy_mode)

    raw_tool_calls: list[dict[str, Any]] = response.tool_calls or []
    # Enforce bounded autonomy: cap tool calls.
    tool_calls = raw_tool_calls[:MAX_TOOL_CALLS]

    content: str = response.content or ""

    result: dict[str, Any] = {"tool_calls": tool_calls}

    if not tool_calls and content:
        result["response"] = content

    # Append assistant message to conversation.
    new_message: dict[str, Any] = {"role": "assistant", "content": content}
    result["messages"] = list(messages) + [new_message]

    return result
