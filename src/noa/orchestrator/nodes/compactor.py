"""Context compaction node — summarizes older messages when approaching context limit.

CC1: When conversation history grows close to the model's context window,
compact by summarising older messages and keeping only recent ones intact.
This preserves conversational continuity without losing important context.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

logger = logging.getLogger(__name__)

# Default number of most-recent messages to preserve verbatim after compaction.
DEFAULT_KEEP_RECENT: int = 6

# Default cheap model used for the compaction summary call.
COMPACTION_MODEL: str = "openai/gpt-4o-mini"

# System prompt for the compaction LLM call.
_SUMMARY_SYSTEM = (
    "Summarize the following conversation history concisely. "
    "Preserve key facts, decisions, user preferences, names, "
    "and any pending tasks. "
    "Output only the summary text, no preamble."
)


async def compact_messages(
    messages: list[dict[str, Any]],
    invoke_fn: Callable[..., Coroutine[Any, Any, Any]],
    *,
    keep_recent: int = DEFAULT_KEEP_RECENT,
    model: str = COMPACTION_MODEL,
) -> tuple[list[dict[str, Any]], bool]:
    """Summarize older messages, keeping the most recent ``keep_recent`` intact.

    The compaction call uses a cheap LLM (``model``) to produce a prose
    summary of the messages that would otherwise be truncated.  The summary
    is injected as a ``system`` message tagged with ``"is_compaction_boundary"``
    so that downstream code can identify where compaction occurred.

    If there are too few messages to compact (``<= keep_recent + 1``) the
    function returns the original list unchanged with ``did_compact=False``.

    Args:
        messages: Current conversation message list.
        invoke_fn: Async callable with the same signature as ``invoke_llm``
            in ``nodes/agent.py`` — ``invoke_fn(model, messages, *, tools, ...)``
            — returns an object with a ``content`` attribute.
        keep_recent: Number of tail messages to preserve verbatim.
        model: Model identifier for the summarisation call.

    Returns:
        A tuple ``(new_messages, did_compact)`` where ``new_messages`` is
        the (potentially shorter) message list and ``did_compact`` indicates
        whether compaction happened.
    """
    if len(messages) <= keep_recent + 1:
        return messages, False

    old_messages = messages[:-keep_recent]
    recent_messages = messages[-keep_recent:]

    # Build the transcript for the summarisation prompt
    lines: list[str] = []
    for m in old_messages:
        role = m.get("role", "unknown")
        content = m.get("content", "")
        if content:
            if isinstance(content, str):
                lines.append(f"{role}: {content}")
            else:
                # Structured content — best-effort text extraction
                lines.append(f"{role}: [structured content]")

    transcript = "\n".join(lines)

    summary_prompt: list[dict[str, Any]] = [
        {"role": "system", "content": _SUMMARY_SYSTEM},
        {"role": "user", "content": transcript},
    ]

    try:
        response = await invoke_fn(model, summary_prompt, tools=None)
        summary_text: str = (
            response.content
            if hasattr(response, "content")
            else str(response)
        )
    except Exception:  # noqa: BLE001
        logger.warning(
            "Compaction LLM call failed — skipping compaction",
            exc_info=True,
        )
        return messages, False

    if not summary_text.strip():
        logger.warning("Compaction produced empty summary — skipping")
        return messages, False

    summary_message: dict[str, Any] = {
        "role": "system",
        "content": f"[Context Summary — earlier conversation]\n{summary_text}",
        "is_compaction_boundary": True,
    }

    new_messages = [summary_message, *recent_messages]
    logger.info(
        "Context compacted: %d messages → %d (kept %d recent, summarised %d)",
        len(messages),
        len(new_messages),
        len(recent_messages),
        len(old_messages),
    )
    return new_messages, True
