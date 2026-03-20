"""Task classifier node — classifies user intent before agent execution."""

from __future__ import annotations

import json
import logging
from typing import Any

from noa.orchestrator.nodes.agent import invoke_llm
from noa.orchestrator.state import AgentState

logger = logging.getLogger(__name__)

TASK_TYPES = ("simple_utility", "execution", "research", "decision_intelligence")

_CLASSIFIER_PROMPT = (
    "Classify the user's message into exactly one task type."
    " Respond with ONLY a JSON object.\n\n"
    "Task types:\n"
    '- "simple_utility": Simple questions, greetings, quick lookups,'
    " unit conversions, translations."
    " No tools needed or just one simple tool call.\n"
    '- "execution": Action-oriented tasks — send email, create event,'
    " set reminder, draft document. Clear single action.\n"
    '- "research": Information gathering — compare options, find information,'
    " summarize topic. May need multiple tool calls and synthesis.\n"
    '- "decision_intelligence": Complex decisions — prioritize options,'
    " diagnose problems, evaluate tradeoffs. Requires structured reasoning.\n\n"
    "User message: {message}\n\n"
    'Respond with: {{"task_type": "<type>", "confidence": <0.0-1.0>}}'
)


async def classifier_node(state: AgentState) -> dict[str, Any]:
    """Classify the user's task type using a cheap LLM call."""
    messages = state.get("messages", [])
    if not messages:
        return {"task_type": "simple_utility"}

    # Get the last user message
    user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break

    if not user_message:
        return {"task_type": "simple_utility"}

    # Use cheap model from model_config, fallback to gpt-4o-mini
    mc = state.get("model_config") or {}
    model = mc.get("classifier") or "openai/gpt-4o-mini"

    # If model is "none", skip classification
    if model == "none":
        return {"task_type": "execution"}

    try:
        prompt = _CLASSIFIER_PROMPT.format(message=user_message)
        result = await invoke_llm(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            tools=[],  # Classifier gets NO tools
            temperature=0.0,
            max_tokens=100,
        )

        task_type = _parse_task_type(result.content)
        logger.info("Classified task as %s (model=%s)", task_type, model)
        return {"task_type": task_type}

    except Exception:  # noqa: BLE001
        logger.warning("Classifier failed, defaulting to execution", exc_info=True)
        return {"task_type": "execution"}


def _parse_task_type(content: str) -> str:
    """Extract task_type from LLM response, with fallback."""
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(content[start:end])
            task_type = str(data.get("task_type", "execution"))
            if task_type in TASK_TYPES:
                return task_type
    except (json.JSONDecodeError, KeyError):
        pass

    # Fallback: check if any task type appears in the text
    content_lower = content.lower()
    for tt in TASK_TYPES:
        if tt in content_lower:
            return str(tt)

    return "execution"  # Safe default
