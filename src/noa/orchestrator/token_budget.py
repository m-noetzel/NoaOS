"""Token budget management for context window compaction.

CC1: Track estimated token usage across messages and determine when
compaction is needed to stay within the model's context window.
"""

from __future__ import annotations

import json

# Approximate context window sizes per model (in tokens).
# Conservative values — actual limits vary by version.
MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "gpt-4.1": 1048576,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4.1-mini": 1048576,
    "gpt-4.1-nano": 1048576,
    "claude-sonnet-4-20250514": 200000,
    "claude-haiku-4-5-20251001": 200000,
    "llama3.1": 8192,
    "llama3.1:70b": 131072,
    "nomic-embed-text": 8192,
}

# Trigger compaction when estimated token usage exceeds this fraction of the
# context window.  80% leaves headroom for the new response + tool calls.
COMPACTION_THRESHOLD: float = 0.8


def estimate_message_tokens(message: dict) -> int:  # type: ignore[type-arg]
    """Fast token estimation: ~3 chars per token (conservative).

    Args:
        message: A message dict with ``role`` and ``content`` keys.

    Returns:
        Estimated token count including ~4 tokens of message overhead.
    """
    content = message.get("content", "")
    if isinstance(content, str):
        char_count = len(content)
    else:
        # Structured content (list of dicts) — serialise first
        try:
            char_count = len(json.dumps(content))
        except (TypeError, ValueError):
            char_count = 0
    return char_count // 3 + 4  # 4-token message framing overhead


def estimate_total_tokens(messages: list[dict]) -> int:  # type: ignore[type-arg]
    """Estimate total tokens across all messages.

    Args:
        messages: List of message dicts.

    Returns:
        Estimated total token count including a small base overhead.
    """
    return sum(estimate_message_tokens(m) for m in messages) + 10  # base overhead


def get_context_limit(model: str) -> int:
    """Get context window size for a model.

    Strips provider prefix (e.g. ``"openai/gpt-4.1"`` → ``"gpt-4.1"``) before
    looking up the table.  Unknown models default to 128 K.

    Args:
        model: Model identifier string, optionally with provider prefix.

    Returns:
        Context window size in tokens.
    """
    model_name = model.split("/")[-1] if "/" in model else model
    return MODEL_CONTEXT_WINDOWS.get(model_name, 128_000)


def needs_compaction(messages: list[dict], model: str) -> bool:  # type: ignore[type-arg]
    """Check if messages exceed the compaction threshold.

    Args:
        messages: Current conversation messages.
        model: Model identifier used to determine context window.

    Returns:
        ``True`` when estimated tokens exceed ``COMPACTION_THRESHOLD * context_limit``.
    """
    limit = get_context_limit(model)
    estimated = estimate_total_tokens(messages)
    return estimated > int(limit * COMPACTION_THRESHOLD)
