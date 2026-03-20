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

# Verdict thresholds
_PASS_THRESHOLD = 3.0
_REROUTE_THRESHOLD = 2.0
_MAX_REROUTE_CYCLES = 2

# Rubric dimensions by task type
_BASE_DIMENSIONS = [
    "goal_alignment",
    "completeness",
    "grounding",
    "confidence_honesty",
    "actionability",
]
_DECISION_DIMENSIONS = ["option_coverage", "tradeoff_clarity"]
_RESEARCH_DIMENSIONS = ["source_quality", "recency"]

_RUBRIC_VERSION = "v1"

_EVALUATOR_PROMPT = """\
You are a quality evaluator for an AI assistant. Score the following response \
against the rubric dimensions below. Each dimension is scored 0-5.

User message: {user_message}

Agent response: {response}

Rubric dimensions to score:
{dimensions_list}

Score each dimension 0-5:
  5 = Excellent
  4 = Good
  3 = Adequate
  2 = Poor
  1 = Very poor
  0 = Completely absent/wrong

Respond with ONLY a JSON object:
{{"scores": {{"dimension_name": score, ...}}, "reasoning": "brief reason"}}
"""


def _get_dimensions(task_type: str | None) -> list[str]:
    """Return the rubric dimensions for the given task type."""
    dims = list(_BASE_DIMENSIONS)
    if task_type == "decision_intelligence":
        dims.extend(_DECISION_DIMENSIONS)
    elif task_type == "research":
        dims.extend(_RESEARCH_DIMENSIONS)
    return dims


def _compute_overall(scores: dict[str, float]) -> float:
    """Compute the mean score across all dimensions."""
    if not scores:
        return 0.0
    return sum(scores.values()) / len(scores)


def _compute_verdict(overall: float) -> str:
    """Map overall score to a verdict string."""
    if overall >= _PASS_THRESHOLD:
        return "pass"
    if overall >= _REROUTE_THRESHOLD:
        return "reroute"
    return "flag"


def _parse_scores(
    content: str,
    dimensions: list[str],
) -> dict[str, float]:
    """Parse LLM response into a scores dict.

    Falls back to a default score of 3.0 for all dimensions on any parse
    failure, so evaluation never blocks the pipeline.
    """
    default = dict.fromkeys(dimensions, 3.0)
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start < 0 or end <= start:
            logger.warning("Evaluator: no JSON found in response, using defaults")
            return default
        data = json.loads(content[start:end])
        raw_scores = data.get("scores", {})
        if not isinstance(raw_scores, dict):
            logger.warning("Evaluator: scores field is not a dict, using defaults")
            return default
        scores: dict[str, float] = {}
        for dim in dimensions:
            val = raw_scores.get(dim)
            if isinstance(val, (int, float)):
                scores[dim] = float(max(0.0, min(5.0, val)))
            else:
                scores[dim] = 3.0  # lenient fallback for missing dimension
        return scores
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        logger.warning("Evaluator: parse failure, using default scores", exc_info=True)
        return default


async def evaluator_node(state: AgentState) -> dict[str, Any]:
    """Score the agent's response and decide whether to pass, reroute, or flag.

    simple_utility tasks return immediately with a pass verdict (no LLM call).
    For all other task types, calls the evaluator model and parses JSON scores.
    On reroute, injects feedback into messages so the agent can improve.
    Max 2 reroute cycles — third time always terminates.
    """
    task_type = state.get("task_type")
    eval_cycle = int(state.get("eval_cycle") or 0)

    # simple_utility skips evaluation entirely (no wasted tokens)
    if task_type == "simple_utility":
        logger.debug("Evaluator: skipping for simple_utility task")
        return {
            "eval_scores": {},
            "eval_verdict": "pass",
            "eval_cycle": eval_cycle,
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
        }

    dimensions = _get_dimensions(task_type)
    dimensions_list = "\n".join(f"- {d}" for d in dimensions)

    prompt = _EVALUATOR_PROMPT.format(
        user_message=user_message,
        response=response,
        dimensions_list=dimensions_list,
    )

    start_ms = time.monotonic()
    try:
        llm_result = await invoke_llm(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            tools=[],  # Evaluator gets NO tools
            temperature=0.0,
            max_tokens=256,
        )
        elapsed_ms = (time.monotonic() - start_ms) * 1000.0
        scores = _parse_scores(llm_result.content, dimensions)
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
        }

    overall = _compute_overall(scores)
    verdict = _compute_verdict(overall)

    logger.info(
        "Evaluator: overall=%.2f verdict=%s cycle=%d",
        overall,
        verdict,
        eval_cycle,
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

    # Build state update
    state_update: dict[str, Any] = {
        "eval_scores": scores,
        "eval_verdict": verdict,
        "eval_cycle": eval_cycle,
    }

    # On reroute: inject feedback into messages for the agent to improve
    if verdict == "reroute" and eval_cycle < _MAX_REROUTE_CYCLES:
        # Build a feedback summary from dimension scores
        low_dims = [d for d, s in scores.items() if s < _PASS_THRESHOLD]
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
            f" (minimum required: {_PASS_THRESHOLD})"
        )
        feedback_lines.append(
            "Please revise your response to be more complete and accurate."
        )
        feedback_msg = "\n".join(feedback_lines)

        new_messages = list(messages)
        new_messages.append({
            "role": "user",
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
