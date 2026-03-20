"""Planner node — selects archetype and generates execution plan.

OI1: Inserted between classifier and agent. For simple_utility tasks the
planner returns immediately (no LLM call). For all other task types it
makes a cheap LLM call to generate a brief numbered plan and sets
``use_react`` for research/decision_intelligence tasks.
"""

from __future__ import annotations

import logging
from typing import Any

from noa.orchestrator.nodes.agent import invoke_llm
from noa.orchestrator.state import AgentState

logger = logging.getLogger(__name__)

# Map task_type → archetype name (None means no planning needed).
ARCHETYPES: dict[str, str | None] = {
    "simple_utility": None,
    "execution": "execution",
    "research": "research",
    "decision_intelligence": "comparative_selection",
}

# Human-readable strategy per archetype injected into the planner prompt.
ARCHETYPE_PROMPTS: dict[str, str] = {
    "execution": (
        "Execute the requested action directly."
        " Verify success before responding."
    ),
    "research": (
        "Gather information from multiple sources."
        " Synthesize findings."
        " Cite sources where possible."
    ),
    "comparative_selection": (
        "Identify all options."
        " Compare on relevant dimensions."
        " Present tradeoffs clearly."
    ),
    "prioritization": (
        "List all items."
        " Apply consistent criteria."
        " Rank with justification."
    ),
    "diagnosis": (
        "Identify symptoms."
        " Generate hypotheses."
        " Test systematically."
        " Explain root cause."
    ),
}

# Task types that benefit from ReAct step-by-step reasoning.
_REACT_TASK_TYPES: frozenset[str] = frozenset({"research", "decision_intelligence"})

_PLANNER_PROMPT_TEMPLATE = (
    "Given this {task_type} task, create a brief execution plan (2-4 steps).\n\n"
    "Archetype: {archetype_name}\n"
    "Strategy: {archetype_prompt}\n\n"
    "User's request: {user_message}\n\n"
    "Respond with a brief numbered plan (no more than 4 steps)."
)


async def planner_node(state: AgentState) -> dict[str, Any]:
    """Select archetype and optionally generate an execution plan.

    Returns immediately (no LLM call) for simple_utility tasks.
    For all other task types makes a cheap LLM call to generate a plan.
    """
    task_type: str = state.get("task_type") or "execution"

    # simple_utility: skip planning entirely.
    if task_type == "simple_utility":
        return {
            "plan": None,
            "archetype": None,
            "use_react": False,
            "thoughts": [],
        }

    archetype: str | None = ARCHETYPES.get(task_type, "execution")
    use_react: bool = task_type in _REACT_TASK_TYPES

    if archetype is None:
        # Shouldn't reach here for non-simple_utility but be safe.
        return {
            "plan": None,
            "archetype": None,
            "use_react": use_react,
            "thoughts": [],
        }

    archetype_prompt = ARCHETYPE_PROMPTS.get(archetype, "")

    # Get the last user message for the prompt.
    messages = state.get("messages", [])
    user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break

    if not user_message:
        # No user message to plan against — return archetype only.
        return {
            "plan": None,
            "archetype": archetype,
            "use_react": use_react,
            "thoughts": [],
        }

    # Use cheap model: prefer "planner" key, then "classifier", then default.
    mc = state.get("model_config") or {}
    model = (
        mc.get("planner")
        or mc.get("classifier")
        or "openai/gpt-4o-mini"
    )

    # If model is "none", skip planning LLM call but keep archetype.
    if model == "none":
        return {
            "plan": None,
            "archetype": archetype,
            "use_react": use_react,
            "thoughts": [],
        }

    prompt = _PLANNER_PROMPT_TEMPLATE.format(
        task_type=task_type,
        archetype_name=archetype,
        archetype_prompt=archetype_prompt,
        user_message=user_message,
    )

    try:
        result = await invoke_llm(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            tools=[],  # Planner gets NO tools
            temperature=0.3,
            max_tokens=300,
        )
        plan = result.content.strip() if result.content else None
        logger.info(
            "Planner generated plan for task_type=%s archetype=%s model=%s",
            task_type,
            archetype,
            model,
        )
    except Exception:  # noqa: BLE001
        logger.warning(
            "Planner LLM call failed for task_type=%s, proceeding without plan",
            task_type,
            exc_info=True,
        )
        plan = None

    return {
        "plan": plan,
        "archetype": archetype,
        "use_react": use_react,
        "thoughts": [],
    }
