"""Evaluator node — scores agent response against a quality rubric.

Spec ref: SPEC.md — EV1 (Evaluation Node).

After the responder produces the final response, this node calls a cheap LLM
to score it against rubric dimensions. Based on the overall score:
  - pass    (overall >= 3.0): proceed to __end__
  - reroute (overall >= 2.0, < 3.0): re-run agent with feedback (max 2 cycles)
  - flag    (overall < 2.0): proceed to __end__ with flagged verdict

simple_utility tasks skip evaluation entirely to avoid wasted tokens.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from noa.orchestrator.nodes.agent import invoke_llm
from noa.orchestrator.state import AgentState

logger = logging.getLogger(__name__)

# Verdict thresholds (defaults; overridden per-run via eval_config in state)
_DEFAULT_PASS_THRESHOLD = 3.0
_DEFAULT_REROUTE_THRESHOLD = 2.0
_DEFAULT_MAX_REROUTE_CYCLES = 2

# Rubric dimensions by task type
_BASE_DIMENSIONS = [
    "goal_alignment",
    "completeness",
    "grounding",
    "confidence_honesty",
    "actionability",
]
# execution tasks use a lightweight 2-dimension rubric (single tool call context)
_EXECUTION_DIMENSIONS = [
    "goal_alignment",
    "actionability",
]
# research adds source quality, recency, and reasoning coherence
_RESEARCH_EXTRA_DIMENSIONS = ["source_quality", "recency", "reasoning_coherence"]
# decision_intelligence adds option coverage, tradeoff clarity, and reasoning coherence
_DECISION_EXTRA_DIMENSIONS = [
    "option_coverage", "tradeoff_clarity", "reasoning_coherence"
]

_RUBRIC_VERSION = "v2"

_EVALUATOR_PROMPT = """\
You are a quality evaluator for an AI assistant. Score the following response \
against the rubric dimensions below. Each dimension is scored 1-5 using the \
anchor examples provided.

User message: {user_message}

Agent response: {response}

Rubric dimensions with anchor examples:
{dimensions_list}

Respond with ONLY a JSON object:
{{"scores": {{"dimension_name": score, ...}}, "reasoning": "brief reason"}}
"""

# Per-dimension rubric definitions with anchor examples (ARCH-EV2)
_DIMENSION_RUBRICS: dict[str, str] = {
    "goal_alignment": (
        "goal_alignment (does the response address what the user asked for?)\n"
        "  1 = Response ignores user's request entirely\n"
        "  3 = Partially addresses the request but misses key aspects\n"
        "  5 = Fully addresses every aspect of the user's request"
    ),
    "completeness": (
        "completeness (is the response thorough and detailed enough?)\n"
        "  1 = Response is a single sentence with no detail\n"
        "  3 = Covers main points but lacks supporting details\n"
        "  5 = Comprehensive coverage with relevant details and context"
    ),
    "grounding": (
        "grounding (are claims accurate and supported?)\n"
        "  1 = Contains fabricated facts or hallucinations\n"
        "  3 = Mostly accurate with some unsupported claims\n"
        "  5 = All claims supported by evidence or clearly marked as opinion"
    ),
    "confidence_honesty": (
        "confidence_honesty (is uncertainty appropriately acknowledged?)\n"
        "  1 = Presents uncertain info as absolute fact\n"
        "  3 = Generally appropriate confidence but occasionally overconfident\n"
        "  5 = Perfectly calibrated — admits uncertainty where appropriate"
    ),
    "actionability": (
        "actionability (can the user act on this response?)\n"
        "  1 = User cannot act on this response\n"
        "  3 = Some actionable elements but unclear next steps\n"
        "  5 = Clear, specific next steps the user can take immediately"
    ),
    "source_quality": (
        "source_quality (are sources cited and credible?)\n"
        "  1 = No sources cited or all sources are unreliable\n"
        "  3 = Some credible sources but incomplete attribution\n"
        "  5 = All claims backed by high-quality, properly attributed sources"
    ),
    "recency": (
        "recency (is the information current and up-to-date?)\n"
        "  1 = Information is clearly outdated or stale\n"
        "  3 = Mostly current with some potentially outdated elements\n"
        "  5 = All information is current and reflects the latest available knowledge"
    ),
    "reasoning_coherence": (
        "reasoning_coherence (is the reasoning logical and well-structured?)\n"
        "  1 = Reasoning is contradictory or internally inconsistent\n"
        "  3 = Reasoning is mostly sound but has minor gaps or jumps\n"
        "  5 = Reasoning is rigorous, stepwise, and fully coherent"
    ),
    "option_coverage": (
        "option_coverage (are all relevant options/alternatives presented?)\n"
        "  1 = Only one option presented when multiple clearly exist\n"
        "  3 = Two or more options covered but some significant alternatives omitted\n"
        "  5 = All relevant options presented with appropriate scope"
    ),
    "tradeoff_clarity": (
        "tradeoff_clarity (are pros/cons and tradeoffs clearly explained?)\n"
        "  1 = No tradeoffs mentioned despite clear differences between options\n"
        "  3 = Tradeoffs mentioned but not clearly explained or compared\n"
        "  5 = Each option's tradeoffs are clearly explained with concrete criteria"
    ),
}


def _get_dimensions(task_type: str | None) -> list[str]:
    """Return the rubric dimensions for the given task type.

    OV4: Task-type-specific dimension sets:
    - execution: lightweight 2-dimension rubric (goal_alignment + actionability)
    - research: full base + source_quality + recency + reasoning_coherence
    - decision_intelligence: full base + option_coverage + tradeoff_clarity
      + reasoning_coherence
    - other/None: full 5-dimension base rubric
    """
    if task_type == "execution":
        return list(_EXECUTION_DIMENSIONS)
    if task_type == "research":
        return list(_BASE_DIMENSIONS) + list(_RESEARCH_EXTRA_DIMENSIONS)
    if task_type == "decision_intelligence":
        return list(_BASE_DIMENSIONS) + list(_DECISION_EXTRA_DIMENSIONS)
    # default: full base rubric (simple tasks, unknown task type)
    return list(_BASE_DIMENSIONS)


def _build_dimensions_list(dimensions: list[str]) -> str:
    """Build the formatted rubric text for the evaluator prompt."""
    lines = []
    for dim in dimensions:
        rubric = _DIMENSION_RUBRICS.get(dim)
        if rubric:
            lines.append(rubric)
        else:
            lines.append(f"{dim} (score 1-5)")
    return "\n\n".join(lines)


def _compute_overall(scores: dict[str, float]) -> float:
    """Compute the mean score across all dimensions."""
    if not scores:
        return 0.0
    return sum(scores.values()) / len(scores)


def _compute_verdict(
    overall: float,
    *,
    pass_threshold: float = _DEFAULT_PASS_THRESHOLD,
    reroute_threshold: float = _DEFAULT_REROUTE_THRESHOLD,
) -> str:
    """Map overall score to a verdict string."""
    if overall >= pass_threshold:
        return "pass"
    if overall >= reroute_threshold:
        return "reroute"
    return "flag"


def _parse_scores(
    content: str,
    dimensions: list[str],
) -> tuple[dict[str, float], str]:
    """Parse LLM response into a scores dict and reasoning string.

    Falls back to a default score of 3.0 for all dimensions on any parse
    failure, so evaluation never blocks the pipeline.

    Returns:
        (scores_dict, reasoning_str) — reasoning is empty string on parse failure.
    """
    default = dict.fromkeys(dimensions, 3.0)
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start < 0 or end <= start:
            logger.warning("Evaluator: no JSON found in response, using defaults")
            return default, ""
        data = json.loads(content[start:end])
        raw_scores = data.get("scores", {})
        reasoning = str(data.get("reasoning", "")) if data.get("reasoning") else ""
        if not isinstance(raw_scores, dict):
            logger.warning("Evaluator: scores field is not a dict, using defaults")
            return default, reasoning
        scores: dict[str, float] = {}
        for dim in dimensions:
            val = raw_scores.get(dim)
            if isinstance(val, (int, float)):
                scores[dim] = float(max(0.0, min(5.0, val)))
            else:
                scores[dim] = 3.0  # lenient fallback for missing dimension
        return scores, reasoning
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        logger.warning("Evaluator: parse failure, using default scores", exc_info=True)
        return default, ""


async def evaluator_node(state: AgentState) -> dict[str, Any]:
    """Score the agent's response and decide whether to pass, reroute, or flag.

    simple_utility tasks return immediately with a pass verdict (no LLM call).
    For all other task types, calls the evaluator model and parses JSON scores.
    On reroute, injects feedback into messages so the agent can improve.
    Max cycles configurable via eval_config in state (default: 2).

    OV4 changes:
    - Task-type-specific rubric dimensions with anchor examples (ARCH-EV2)
    - Reroute feedback uses role "developer" instead of "user" (ARCH-EV1)
    - Reasoning field returned in state for Langfuse logging (ARCH-EV1)
    - Thresholds read from state["eval_config"] (UX-EV1)
    """
    task_type = state.get("task_type")
    eval_cycle = int(state.get("eval_cycle") or 0)

    # UX-EV1: Read thresholds from eval_config in state (with safe defaults)
    eval_config = state.get("eval_config") or {}
    pass_threshold = float(eval_config.get("pass_threshold") or _DEFAULT_PASS_THRESHOLD)
    reroute_threshold = float(
        eval_config.get("reroute_threshold") or _DEFAULT_REROUTE_THRESHOLD
    )
    max_cycles = int(eval_config.get("max_cycles") or _DEFAULT_MAX_REROUTE_CYCLES)

    # simple_utility skips evaluation entirely (no wasted tokens)
    if task_type == "simple_utility":
        logger.debug("Evaluator: skipping for simple_utility task")
        return {
            "eval_scores": {},
            "eval_verdict": "pass",
            "eval_cycle": eval_cycle,
            "eval_reasoning": "",
        }

    response = state.get("response") or ""
    archetype = state.get("archetype")
    # Get user message for context
    messages = state.get("messages", [])
    user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break

    if not response or not user_message:
        logger.warning("Evaluator: missing response or user_message — passing through")
        return {
            "eval_scores": {},
            "eval_verdict": "pass",
            "eval_cycle": eval_cycle,
            "eval_reasoning": "",
        }

    # Use cheap model from model_config, fallback to gpt-4o-mini
    mc = state.get("model_config") or {}
    model = mc.get("evaluator") or "openai/gpt-4o-mini"

    if model == "none":
        logger.debug("Evaluator: model='none', skipping evaluation")
        return {
            "eval_scores": {},
            "eval_verdict": "pass",
            "eval_cycle": eval_cycle,
            "eval_reasoning": "",
        }

    dimensions = _get_dimensions(task_type)
    dimensions_list_text = _build_dimensions_list(dimensions)

    prompt = _EVALUATOR_PROMPT.format(
        user_message=user_message,
        response=response,
        dimensions_list=dimensions_list_text,
    )

    start_ms = time.monotonic()
    try:
        llm_result = await invoke_llm(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            tools=[],  # Evaluator gets NO tools
            temperature=0.0,
            max_tokens=512,
        )
        elapsed_ms = (time.monotonic() - start_ms) * 1000.0
        scores, reasoning = _parse_scores(llm_result.content, dimensions)
        logger.info(
            "Evaluator: model=%s task_type=%s archetype=%s elapsed_ms=%.0f",
            model,
            task_type,
            archetype,
            elapsed_ms,
        )
    except Exception:  # noqa: BLE001
        elapsed_ms = (time.monotonic() - start_ms) * 1000.0
        logger.warning("Evaluator: LLM call failed, defaulting to pass", exc_info=True)
        return {
            "eval_scores": dict.fromkeys(dimensions, 3.0),
            "eval_verdict": "pass",
            "eval_cycle": eval_cycle,
            "eval_reasoning": "",
        }

    overall = _compute_overall(scores)
    verdict = _compute_verdict(
        overall,
        pass_threshold=pass_threshold,
        reroute_threshold=reroute_threshold,
    )

    logger.info(
        "Evaluator: overall=%.2f verdict=%s cycle=%d reasoning=%s",
        overall,
        verdict,
        eval_cycle,
        reasoning[:120] if reasoning else "",
    )

    # Persist evaluation to DB (best-effort — never blocks the pipeline)
    await _persist_evaluation(
        run_id=state.get("run_id") or "",
        task_type=task_type,
        archetype=archetype,
        scores=scores,
        overall=overall,
        verdict=verdict,
        reroute_cycle=eval_cycle,
        eval_model=model,
        eval_ms=elapsed_ms,
    )

    # Build state update — reasoning included for Langfuse span capture (ARCH-EV1)
    state_update: dict[str, Any] = {
        "eval_scores": scores,
        "eval_verdict": verdict,
        "eval_cycle": eval_cycle,
        "eval_reasoning": reasoning,
    }

    # On reroute: inject feedback into messages for the agent to improve
    # ARCH-EV1: Use role "developer" to avoid impersonating real user messages
    if verdict == "reroute" and eval_cycle < max_cycles:
        # Build a feedback summary from dimension scores
        low_dims = [d for d, s in scores.items() if s < pass_threshold]
        feedback_lines = [
            "Your previous response needs improvement. "
            "Please provide a better answer addressing these issues:"
        ]
        if low_dims:
            feedback_lines.append(
                "Weak areas: " + ", ".join(d.replace("_", " ") for d in low_dims)
            )
        feedback_lines.append(
            f"Overall quality score: {overall:.1f}/5.0"
            f" (minimum required: {pass_threshold})"
        )
        feedback_lines.append(
            "Please revise your response to be more complete and accurate."
        )
        feedback_msg = "\n".join(feedback_lines)

        new_messages = list(messages)
        new_messages.append({
            "role": "developer",
            "content": feedback_msg,
        })
        state_update["messages"] = new_messages
        state_update["eval_cycle"] = eval_cycle + 1
        state_update["response"] = None  # Clear response for re-generation

    return state_update


async def _persist_evaluation(
    *,
    run_id: str,
    task_type: str | None,
    archetype: str | None,
    scores: dict[str, float],
    overall: float,
    verdict: str,
    reroute_cycle: int,
    eval_model: str,
    eval_ms: float,
) -> None:
    """Persist evaluation record to DB (best-effort, never raises)."""
    try:
        from noa.api.app_state import get_session_factory
        from noa.db.models.response_evaluation import ResponseEvaluation

        session_factory = get_session_factory()
        if session_factory is None:
            return

        async with session_factory() as session:
            record = ResponseEvaluation(
                run_id=run_id,
                task_type=task_type,
                archetype=archetype,
                rubric_version=_RUBRIC_VERSION,
                scores=scores,
                overall=overall,
                verdict=verdict,
                reroute_target="agent" if verdict == "reroute" else None,
                reroute_cycle=reroute_cycle,
                eval_model=eval_model,
                eval_ms=eval_ms,
            )
            session.add(record)
            await session.commit()
    except Exception:  # noqa: BLE001
        logger.debug("Evaluator: failed to persist evaluation record", exc_info=True)
