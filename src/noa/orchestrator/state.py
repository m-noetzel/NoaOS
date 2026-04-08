"""AgentState schema for the LangGraph orchestrator.

Spec ref: SPEC.md S2.1 -- state carried through every node.
"""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict):
    """Typed state dict flowing through every graph node.

    Fields:
        messages: Conversation history (user + assistant messages).
        privacy_mode: "private" or "external" -- set by router.
        selected_model: Model identifier chosen by router.
        tool_calls: Tool invocations requested by the agent node.
        tool_results: Results returned by the tools node.
        response: Final formatted response string.
        total_cost: Cumulative cost tracker (USD estimate).
        tool_rounds: Number of tool-execution rounds completed (MR9 loop cap).
        max_tool_calls: Max tool calls per agent step (W22-H1).
        max_retries: Max tool-execution rounds (W22-H1).
        timeout_seconds: Orchestrator timeout in seconds (W22-H1).
        approvals_enabled: Whether human-in-the-loop approvals are enforced (W22-H2).
    """

    messages: list[dict[str, Any]]
    privacy_mode: str
    selected_model: str
    user_model_override: str | None
    user_provider_override: str | None
    user_privacy_override: str | None
    requested_tools: list[str] | None
    tool_calls: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    response: str | None
    total_cost: float
    model_config: dict[str, str]
    tool_rounds: int
    llm_usage: list[dict[str, Any]]
    available_tools: list[dict[str, Any]]
    # UX-M4: Agent execution limits (W22-H1)
    max_tool_calls: int
    max_retries: int
    timeout_seconds: int
    # UX-M2: Human-in-the-loop approvals toggle (W22-H2)
    approvals_enabled: bool
    # MVP-H3: Private domain availability flag (passed from health checker)
    private_available: bool
    # User identity for scoped storage (memory, etc.)
    user_id: str | None
    # CQ1: Task-level tool scope (None = all tools allowed)
    tool_scope: str | None
    # DI1: Task type classification
    # Values: "simple_utility" | "execution" | "research" | "decision_intelligence"
    task_type: str | None
    # OI1: Planning node fields
    plan: str | None  # Planner's output (injected as system context)
    archetype: str | None  # e.g. "comparative_selection", "execution", "research"
    thoughts: list[dict[str, Any]]  # ReAct thought steps
    use_react: bool  # Whether to use ReAct mode
    # ST4: Per-run token streaming callback (avoids module-global race).
    # Typed as Any because TypedDict doesn't support Callable directly.
    token_callback: Any
    # Run identity (for evaluation persistence)
    run_id: str | None
    # EV1: Evaluator node fields
    eval_scores: dict[str, float] | None  # {dimension: score}
    eval_verdict: str | None  # "pass" | "reroute" | "flag"
    eval_cycle: int  # Number of reroute cycles completed
    # OV4: UX-EV1 — configurable evaluator thresholds
    eval_config: dict[str, Any] | None
    # OV4: ARCH-EV1 — evaluator reasoning for Langfuse logging
    eval_reasoning: str | None
    # CC1: Context compaction flag — True when context was compacted this turn
    is_compaction_boundary: bool
