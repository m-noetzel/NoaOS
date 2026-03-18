"""Agent node — invokes LLM with bounded autonomy.

Spec refs: SPEC.md S2.2 (bounded inner autonomy, max tool calls).

invoke_llm is a module-level async function that calls ProviderRouter.complete().
set_router() must be called at app startup to wire the router.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from noa.cost.pricing import estimate_cost
from noa.orchestrator.state import AgentState

if TYPE_CHECKING:
    from noa.external_worker.llm.router import ProviderRouter

# Maximum tool calls the agent will forward per step (S2.1 cost/iteration limits).
MAX_TOOL_CALLS = 10

# Module-level router reference, set at startup via set_router().
_router: ProviderRouter | None = None


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


def set_router(router: ProviderRouter) -> None:
    """Set the module-level ProviderRouter. Called at app startup."""
    global _router  # noqa: PLW0603
    _router = router


def get_router() -> ProviderRouter | None:
    """Return the current ProviderRouter (or None if not configured)."""
    return _router


async def invoke_llm(
    model: str,
    messages: list[dict[str, Any]],
    *,
    privacy_mode: str = "external",
    max_tokens: int = 4096,
    tools: list[dict[str, Any]] | None = None,
    temperature: float | None = None,
) -> LLMResponse:
    """Invoke the LLM via ProviderRouter.

    Args:
        model: Model identifier (e.g. "anthropic/claude-haiku").
        messages: Conversation messages.
        privacy_mode: "external" or "private".
        max_tokens: Maximum tokens to generate.
        tools: Optional list of available tool metadata dicts.

    Returns:
        LLMResponse with content and tool_calls.

    Raises:
        RuntimeError: If no router is configured.
    """
    if _router is None:
        msg = (
            "invoke_llm: no router configured "
            "— call set_router() at startup"
        )
        raise RuntimeError(msg)

    # Parse provider from model string
    provider: str | None = None
    model_name: str | None = None
    if "/" in model:
        provider, model_name = model.split("/", 1)
    else:
        model_name = model

    complete_kwargs: dict[str, Any] = {
        "messages": messages,
        "max_tokens": max_tokens,
        "privacy_mode": privacy_mode,
        "provider": provider,
        "model": model_name,
        "tools": tools,
    }
    if temperature is not None:
        complete_kwargs["temperature"] = temperature
    result: dict[str, Any] = await _router.complete(**complete_kwargs)

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
        model = state.get("selected_model") or "openai/gpt-4.1"
    privacy_mode = state.get("privacy_mode", "external")

    available_tools = state.get("available_tools") or []
    max_tokens: int = cast(int, state.get("max_tokens") or 4096)
    raw_temp = state.get("temperature")
    temp: float | None = float(cast(float, raw_temp)) if raw_temp is not None else None
    response = await invoke_llm(
        model,
        messages,
        privacy_mode=privacy_mode,
        max_tokens=max_tokens,
        tools=available_tools or None,
        temperature=temp,
    )

    raw_tool_calls: list[dict[str, Any]] = response.tool_calls or []
    # Enforce bounded autonomy: cap tool calls.
    # Read limit from state (user-configured) with fallback to module constant.
    tool_call_limit = int(state.get("max_tool_calls") or MAX_TOOL_CALLS)
    tool_calls = raw_tool_calls[:tool_call_limit]

    content: str = response.content or ""

    # Track token usage from this LLM call.
    usage = response.usage or {}
    input_tokens = usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)
    provider_name = response.provider or ""
    model_name = response.model or ""
    cost = estimate_cost(
        provider=provider_name,
        model=model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    usage_record: dict[str, Any] = {
        "provider": provider_name,
        "model": model_name,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": float(cost),
    }
    prev_usage: list[dict[str, Any]] = list(state.get("llm_usage", []))
    prev_usage.append(usage_record)

    result: dict[str, Any] = {
        "tool_calls": tool_calls,
        "llm_usage": prev_usage,
    }

    if not tool_calls:
        # No more tool calls — this is the final agent turn.
        # Set response even if content is empty (LLM legitimately
        # finished without text after a tool round).
        result["response"] = content

    # Build assistant message.
    # When tools are called, include tool_use info so the next
    # iteration can provide tool_result messages.
    new_message: dict[str, Any] = {
        "role": "assistant",
        "content": content,
    }
    if tool_calls:
        new_message["tool_calls"] = tool_calls
    result["messages"] = list(messages) + [new_message]

    return result
