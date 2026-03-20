"""Agent node — invokes LLM with bounded autonomy.

Spec refs: SPEC.md S2.2 (bounded inner autonomy, max tool calls).

invoke_llm is a module-level async function that calls ProviderRouter.complete().
set_router() must be called at app startup to wire the router.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Coroutine
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

# Module-level streaming token callback.
# Set by the runner before graph execution so token events flow back to the SSE
# stream without coupling the LangGraph node to the runner's async queue.
# Signature: async callable that receives a single token string.
_stream_callback: Callable[[str], Coroutine[Any, Any, None]] | None = None


def set_stream_callback(
    callback: Callable[[str], Coroutine[Any, Any, None]] | None,
) -> None:
    """Set (or clear) the token streaming callback.

    The runner calls this before graph execution to wire token events into
    the SSE stream.  Pass ``None`` to disable streaming (non-streaming path).
    """
    global _stream_callback  # noqa: PLW0603
    _stream_callback = callback


def get_stream_callback() -> (
    Callable[[str], Coroutine[Any, Any, None]] | None
):
    """Return the current stream callback (or None)."""
    return _stream_callback


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


async def invoke_llm_stream(
    model: str,
    messages: list[dict[str, Any]],
    *,
    privacy_mode: str = "external",
    max_tokens: int = 4096,
    temperature: float | None = None,
    token_callback: Callable[[str], Coroutine[Any, Any, None]] | None = None,
) -> LLMResponse:
    """Invoke the LLM via ProviderRouter in streaming mode.

    Calls ``token_callback(chunk)`` for each incremental token, then returns
    the full ``LLMResponse`` once the stream is complete.

    Falls back to non-streaming ``invoke_llm`` if the router does not support
    streaming or if no callback is provided.

    Args:
        model: Model identifier (e.g. "anthropic/claude-haiku").
        messages: Conversation messages.
        privacy_mode: "external" or "private".
        max_tokens: Maximum tokens to generate.
        temperature: Optional sampling temperature.
        token_callback: Async callable invoked with each partial token string.

    Returns:
        LLMResponse with content and empty tool_calls (streaming skips tools).

    Raises:
        RuntimeError: If no router is configured.
    """
    if _router is None:
        msg = (
            "invoke_llm_stream: no router configured "
            "— call set_router() at startup"
        )
        raise RuntimeError(msg)

    if token_callback is None:
        # No callback — fall through to standard non-streaming path
        return await invoke_llm(
            model,
            messages,
            privacy_mode=privacy_mode,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    # Parse provider/model from composite string
    provider: str | None = None
    model_name: str | None = None
    if "/" in model:
        provider, model_name = model.split("/", 1)
    else:
        model_name = model

    stream_kwargs: dict[str, Any] = {
        "messages": messages,
        "max_tokens": max_tokens,
        "privacy_mode": privacy_mode,
        "provider": provider,
        "model": model_name,
    }
    if temperature is not None:
        stream_kwargs["temperature"] = temperature

    stream: AsyncGenerator[dict[str, Any], None] = (
        await _router.complete_stream(**stream_kwargs)
    )

    final_chunk: dict[str, Any] = {}
    async for chunk in stream:
        if chunk.get("type") == "token":
            await token_callback(chunk["content"])
        elif chunk.get("type") == "complete":
            final_chunk = chunk

    return LLMResponse(
        content=final_chunk.get("content", ""),
        tool_calls=final_chunk.get("tool_calls", []),
        usage=final_chunk.get("usage", {}),
        provider=final_chunk.get("provider", ""),
        model=final_chunk.get("model", ""),
    )


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


def _parse_react_thoughts(
    content: str,
    existing_thoughts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Parse 'Thought: ...' lines from LLM response into ThoughtStep dicts.

    Args:
        content: Raw LLM response text.
        existing_thoughts: Previously accumulated thought steps.

    Returns:
        Updated list of thought step dicts with keys: step, text, action.
    """
    thoughts = list(existing_thoughts)
    step_offset = len(thoughts)
    for i, line in enumerate(content.splitlines()):
        stripped = line.strip()
        if stripped.startswith("Thought:"):
            text = stripped[len("Thought:"):].strip()
            thoughts.append(
                {
                    "step": step_offset + i + 1,
                    "text": text,
                    "action": None,
                }
            )
    return thoughts


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

    # OI1: Inject plan and/or ReAct instruction into the system message.
    use_react: bool = bool(state.get("use_react", False))
    plan: str | None = state.get("plan")

    if use_react or plan:
        # Find the system message and inject context into it.
        augmented_messages: list[dict[str, Any]] = []
        system_injected = False
        for msg in messages:
            if msg.get("role") == "system" and not system_injected:
                extra_parts: list[str] = []
                if plan:
                    extra_parts.append(f"Plan:\n{plan}")
                if use_react:
                    extra_parts.append(
                        "Think step by step. Before each action, write your"
                        " reasoning as 'Thought: ...' on its own line. After"
                        " observing tool results, reflect with another"
                        " 'Thought: ...' before proceeding."
                    )
                existing = msg.get("content", "")
                new_content = existing + "\n\n" + "\n\n".join(extra_parts)
                augmented_messages.append(
                    {"role": "system", "content": new_content.strip()}
                )
                system_injected = True
            else:
                augmented_messages.append(msg)
        if not system_injected and (plan or use_react):
            # No system message yet — prepend one.
            extra_parts = []
            if plan:
                extra_parts.append(f"Plan:\n{plan}")
            if use_react:
                extra_parts.append(
                    "Think step by step. Before each action, write your"
                    " reasoning as 'Thought: ...' on its own line. After"
                    " observing tool results, reflect with another"
                    " 'Thought: ...' before proceeding."
                )
            augmented_messages.insert(
                0,
                {"role": "system", "content": "\n\n".join(extra_parts)},
            )
        messages = augmented_messages

    # Use streaming when a token callback is registered and no tools are
    # requested (streaming does not support tool calls).
    cb = _stream_callback
    use_streaming = cb is not None and not available_tools
    if use_streaming:
        response = await invoke_llm_stream(
            model,
            messages,
            privacy_mode=privacy_mode,
            max_tokens=max_tokens,
            temperature=temp,
            token_callback=cb,
        )
    else:
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

    # OI1: Parse ReAct thought steps from the response content.
    if use_react and content:
        existing_thoughts: list[dict[str, Any]] = list(state.get("thoughts") or [])
        parsed_thoughts = _parse_react_thoughts(content, existing_thoughts)
    else:
        parsed_thoughts = list(state.get("thoughts") or [])

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
        "thoughts": parsed_thoughts,
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
