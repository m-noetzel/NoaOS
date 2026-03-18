"""OrchestratorRunner — executes the LangGraph pipeline and yields SSE events.

Spec refs: SPEC.md §2.1, §22.1, §22.2, §22.4
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


class OrchestratorRunner:
    """Compile and run the orchestrator graph, yielding SSE events.

    Usage::

        runner = OrchestratorRunner(graph=compiled_graph)
        async for event in runner.run(
            message="hello",
            run_service=svc,
            run_id="...",
        ):
            # event is {"event_type": str, "payload": dict, "timestamp": str}
            yield sse_format(event)
    """

    def __init__(self, graph: Any, checkpointer: Any | None = None) -> None:
        self._graph = graph
        self._checkpointer = checkpointer

    async def run(
        self,
        *,
        message: str,
        run_service: Any,
        run_id: str,
        privacy_mode: str = "external",
        model: str | None = None,
        provider: str | None = None,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        user_id: str | None = None,
        trace_id: str | None = None,
        history: list[dict[str, Any]] | None = None,
        max_tool_calls: int = 10,
        max_retries: int = 3,
        timeout_seconds: int = 120,
        approvals_enabled: bool = True,
        private_available: bool = True,
        tool_scope: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Execute the graph and yield structured events.

        Args:
            message: User message text.
            run_service: RunService instance for persisting events.
            run_id: The Run ID to append events to.
            privacy_mode: "external" or "private".
            model: Model identifier.
            provider: Optional provider override.
            user_id: Authenticated user ID for structured logging.
            trace_id: Request trace ID for structured logging.
            max_tool_calls: Max tool calls per agent step (W22-H1).
            max_retries: Max tool-execution rounds (W22-H1).
            timeout_seconds: Orchestrator timeout in seconds (W22-H1).
            approvals_enabled: Whether human approval checks are enforced (W22-H2).

        Yields:
            Event dicts with event_type, payload, timestamp.
        """
        # BE-M4: Structured log context for queryable logs
        log_ctx = {
            "run_id": run_id,
            "user_id": user_id or "unknown",
            "trace_id": trace_id or "unknown",
        }
        logger.info(
            "Run started: run_id=%s user_id=%s trace_id=%s privacy_mode=%s model=%s",
            run_id,
            user_id or "unknown",
            trace_id or "unknown",
            privacy_mode,
            model or "default",
            extra=log_ctx,
        )

        # 1. message_received
        event = self._make_event(
            "message_received",
            {"message": message},
        )
        await self._persist_event(run_service, run_id, event)
        yield event

        # 2. Transition to running
        try:
            await run_service.update_status(run_id, "running")
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to update run status to running: run_id=%s",
                run_id,
                extra=log_ctx,
            )

        # 3. classification_done (pre-graph — we know the privacy_mode)
        event = self._make_event(
            "classification_done",
            {"privacy_mode": privacy_mode, "model": model},
        )
        await self._persist_event(run_service, run_id, event)
        yield event

        # 5. Stream graph node-by-node
        try:
            # Resolve available tools from gateway
            from noa.orchestrator.nodes.tools import get_gateway
            gw = get_gateway()
            avail_tools: list[dict[str, Any]] = []
            if gw is not None:
                avail_tools = [
                    {"name": t} for t in gw.list_tools()
                ]

            messages: list[dict[str, Any]] = []
            # System prompt: use exactly what was passed (from
            # settings → UI → ChatRequest). Tool context is
            # appended as operational metadata.
            sp = system_prompt or ""
            tool_ctx = self._build_tool_context(avail_tools)
            # Inject current date/time so the model knows "now"
            now_str = datetime.now(UTC).strftime("%A, %B %d, %Y at %H:%M UTC")
            time_ctx = f"Current date and time: {now_str}"
            parts = [p for p in (sp, time_ctx, tool_ctx) if p]
            combined = "\n\n".join(parts)
            if combined:
                messages.append({"role": "system", "content": combined})

            # Include conversation history for multi-turn context
            if history:
                for h in history:
                    role = h.get("role", "user")
                    content = h.get("content", "")
                    if role in ("user", "assistant") and content:
                        messages.append({"role": role, "content": content})

            messages.append({"role": "user", "content": message})

            initial_state: dict[str, Any] = {
                "messages": messages,
                "privacy_mode": privacy_mode,
                "user_privacy_override": privacy_mode,
                "selected_model": model or "gpt-4.1",
                "user_model_override": model,
                "user_provider_override": provider or "openai",
                "tool_calls": [],
                "tool_results": [],
                "response": None,
                "total_cost": 0.0,
                "llm_usage": [],
                "model_config": {},
                "tool_rounds": 0,
                "available_tools": avail_tools,
                "temperature": temperature,
                "max_tokens": max_tokens or 4096,
                # W22-H1: User-configured agent limits
                "max_tool_calls": max_tool_calls,
                "max_retries": max_retries,
                "timeout_seconds": timeout_seconds,
                # W22-H2: Human-in-the-loop approvals toggle
                "approvals_enabled": approvals_enabled,
                # MVP-H3: Private domain availability (for router node)
                "private_available": private_available,
                "user_id": user_id,
                # CQ1: Task-level tool scope (None = all tools allowed)
                "tool_scope": tool_scope,
            }

            # A4: Load checkpoint if available (resume support)
            if self._checkpointer is not None:
                saved = await self._checkpointer.load(run_id=run_id)
                if saved is not None:
                    initial_state.update(saved)
                    logger.info("Resumed from checkpoint for run %s", run_id)

            logger.debug(
                "Invoking graph: run_id=%s tools=%d",
                run_id,
                len(avail_tools),
                extra=log_ctx,
            )

            # Stream node-by-node so the frontend sees events in real-time
            # instead of waiting for the entire graph to complete.
            result: dict[str, Any] = dict(initial_state)
            seen_tools: set[str] = set()

            async for chunk in self._graph.astream(initial_state):
                # astream yields {node_name: state_update} per completed node
                for node_name, node_output in chunk.items():
                    if not isinstance(node_output, dict):
                        continue
                    # Merge node output into accumulated result
                    result.update(node_output)

                    # Emit step_started for each node as it completes
                    step_event = self._make_event(
                        "step_started",
                        {"step": node_name},
                    )
                    await self._persist_event(run_service, run_id, step_event)
                    yield step_event

                    # Emit tool events from agent node (tool_calls)
                    if node_name == "agent":
                        for tc in node_output.get("tool_calls", []):
                            tool_name = (
                                tc.get("name")
                                if isinstance(tc, dict)
                                else getattr(tc, "name", "tool")
                            )
                            if tool_name and tool_name not in seen_tools:
                                start_event = self._make_event(
                                    "tool_start",
                                    {"tool_name": tool_name},
                                )
                                await self._persist_event(
                                    run_service, run_id, start_event,
                                )
                                yield start_event

                                tc_event = self._make_event(
                                    "tool_called",
                                    {"tool_call": tc, "tool_name": tool_name},
                                )
                                await self._persist_event(run_service, run_id, tc_event)
                                yield tc_event
                                seen_tools.add(tool_name)

                    # Emit tool results from tools node
                    if node_name == "tools":
                        for tr in node_output.get("tool_results", []):
                            if not isinstance(tr, dict):
                                continue
                            tr_name = tr.get("name", tr.get("tool_name", ""))

                            # Emit tool_end for completed tools
                            end_event = self._make_event(
                                "tool_end",
                                {"tool_name": tr_name, "result": tr},
                            )
                            await self._persist_event(run_service, run_id, end_event)
                            yield end_event

                            # Emit approval_requested for actions needing approval
                            if tr.get("approval_required"):
                                approval_event = self._make_event(
                                    "approval_requested",
                                    {
                                        "tool": tr.get("tool", ""),
                                        "function": tr.get("function", ""),
                                        "args": tr.get("args", {}),
                                        "risk_tier": tr.get("risk_tier", "medium"),
                                    },
                                )
                                await self._persist_event(
                                    run_service, run_id, approval_event,
                                )
                                yield approval_event
                            else:
                                tr_event = self._make_event(
                                    "tool_result",
                                    {"tool_result": tr, "tool_name": tr_name},
                                )
                                await self._persist_event(run_service, run_id, tr_event)
                                yield tr_event

            # A4: Save checkpoint after successful execution
            if self._checkpointer is not None:
                await self._checkpointer.save(run_id=run_id, state=result)

            # 7. result_ready
            response = result.get("response", "")
            event = self._make_event(
                "result_ready",
                {
                    "response": response,
                    "total_cost": result.get("total_cost", 0.0),
                    "llm_usage": result.get("llm_usage", []),
                },
            )
            await self._persist_event(run_service, run_id, event)
            yield event

            # 8. Transition to completed
            logger.info(
                "Run completed: run_id=%s user_id=%s trace_id=%s",
                run_id,
                user_id or "unknown",
                trace_id or "unknown",
                extra=log_ctx,
            )
            try:
                await run_service.update_status(run_id, "completed")
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Failed to update run status to completed: run_id=%s",
                    run_id,
                    extra=log_ctx,
                )

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Run failed: run_id=%s user_id=%s trace_id=%s error=%s",
                run_id,
                user_id or "unknown",
                trace_id or "unknown",
                str(exc),
                exc_info=True,
                extra=log_ctx,
            )
            # Error event — send a generic message to the client (str(exc) may
            # contain internal details like API keys or DB connection strings).
            # The full error is already captured in the server log above.
            error_event = self._make_event(
                "error",
                {
                    "error": "An error occurred processing your request.",
                    "error_type": type(exc).__name__,
                },
            )
            await self._persist_event(run_service, run_id, error_event)
            yield error_event

            # Transition to failed
            try:
                await run_service.update_status(run_id, "failed")
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Failed to update run status to failed: run_id=%s",
                    run_id,
                    extra=log_ctx,
                )

    @staticmethod
    def _build_tool_context(
        avail_tools: list[dict[str, Any]],
    ) -> str:
        """Build tool-availability context appended to the system prompt.

        This is operational metadata — tells the LLM what tools exist
        and how to use them. Personality and behavior instructions come
        from the user's system prompt (prompts/system_prompt.txt → DB
        → UI → ChatRequest). Transparency principle: no hidden prompts.
        """
        tool_names = (
            [t["name"] for t in avail_tools] if avail_tools else []
        )
        if not tool_names:
            return ""

        descs = {
            "web_search": (
                "Search the web for current information"
                " (powered by Tavily)"
            ),
            "calendar": (
                "List, create, and manage"
                " Google Calendar events"
            ),
            "gmail": (
                "Search, read, send, and draft"
                " emails via Gmail"
            ),
            "notion": (
                "Search, read, and create Notion pages"
            ),
            "memory": (
                "Remember facts about the user (remember)"
                " or recall previously stored facts (recall)."
                " Use remember when the user shares preferences,"
                " habits, or important personal information."
                " Use recall to retrieve stored knowledge"
            ),
        }
        lines = []
        for name in tool_names:
            desc = descs.get(name, name)
            lines.append(f"- {name}: {desc}")

        return (
            "You have the following tools available."
            " Use them proactively when a user's question"
            " could benefit from external data or"
            " actions:\n"
            + "\n".join(lines)
            + "\n\nYou can call multiple tools in"
            " sequence across turns. After each tool"
            " returns its result, you will be called"
            " again and can use another tool or"
            " respond with your final answer."
            " For complex tasks, chain tools together:"
            " e.g. search the web first, then use the"
            " results to draft an email or create a"
            " calendar event."
            "\n\nWhen a user asks for current"
            " information (news, weather, facts that"
            " may have changed), USE the web_search"
            " tool rather than relying on your training"
            " data. When a user asks you to use a"
            " specific service (e.g. 'use Tavily',"
            " 'search the web'), call the appropriate"
            " tool."
            "\n\nAfter using tools, ALWAYS provide a"
            " clear summary of what you found or did."
            " Never leave the user without a response."
        )

    @staticmethod
    def _make_event(
        event_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a structured event dict."""
        return {
            "event_type": event_type,
            "payload": payload,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    @staticmethod
    async def _persist_event(
        run_service: Any,
        run_id: str,
        event: dict[str, Any],
    ) -> None:
        """Persist an event via RunService (best-effort)."""
        try:
            await run_service.append_event(
                run_id,
                event["event_type"],
                event["payload"],
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to persist event %s for run %s",
                event["event_type"],
                run_id,
            )
