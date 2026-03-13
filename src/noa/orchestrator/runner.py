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

        # 4. step_started
        event = self._make_event(
            "step_started",
            {"step": "agent"},
        )
        await self._persist_event(run_service, run_id, event)
        yield event

        # 5. Invoke graph
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
            # Build system prompt: user-provided or default
            sp = system_prompt or self._build_system_prompt(
                avail_tools,
            )
            if sp:
                messages.append({"role": "system", "content": sp})

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
                "selected_model": model,
                "user_model_override": model,
                "user_provider_override": provider,
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
            result = await self._graph.ainvoke(initial_state)

            # A4: Save checkpoint after successful execution
            if self._checkpointer is not None:
                await self._checkpointer.save(run_id=run_id, state=result)

            # 6. Emit tool events if any
            # UX-H10: pair each tool_called with tool_start/tool_end so the
            # frontend ActivityStream shows per-tool execution progress.
            tool_calls = result.get("tool_calls", [])
            tool_results = result.get("tool_results", [])

            # Build a mapping from tool name → result for pairing start/end
            result_by_name: dict[str, Any] = {}
            for tr in tool_results:
                if isinstance(tr, dict):
                    name = tr.get("name", tr.get("tool_name", ""))
                    if name:
                        result_by_name[name] = tr

            for tc in tool_calls:
                tool_name = (
                    tc.get("name")
                    if isinstance(tc, dict)
                    else getattr(tc, "name", "tool")
                )

                # tool_start — signals the frontend that execution is beginning
                start_event = self._make_event(
                    "tool_start",
                    {"tool_name": tool_name},
                )
                await self._persist_event(run_service, run_id, start_event)
                yield start_event

                # tool_called — full call details (inputs)
                tc_event = self._make_event(
                    "tool_called",
                    {"tool_call": tc, "tool_name": tool_name},
                )
                await self._persist_event(run_service, run_id, tc_event)
                yield tc_event

                # tool_end — signals completion; include result if available
                paired_result = result_by_name.get(tool_name, {})
                end_event = self._make_event(
                    "tool_end",
                    {"tool_name": tool_name, "result": paired_result},
                )
                await self._persist_event(run_service, run_id, end_event)
                yield end_event

            for tr in tool_results:
                # Emit approval_requested event for actions needing approval
                if isinstance(tr, dict) and tr.get("approval_required"):
                    approval_event = self._make_event(
                        "approval_requested",
                        {
                            "tool": tr.get("tool", ""),
                            "function": tr.get("function", ""),
                            "args": tr.get("args", {}),
                            "risk_tier": tr.get("risk_tier", "medium"),
                        },
                    )
                    await self._persist_event(run_service, run_id, approval_event)
                    yield approval_event
                else:
                    tr_name = tr.get("name", "") if isinstance(tr, dict) else ""
                    tr_event = self._make_event(
                        "tool_result",
                        {"tool_result": tr, "tool_name": tr_name},
                    )
                    await self._persist_event(run_service, run_id, tr_event)
                    yield tr_event

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
    def _build_system_prompt(
        avail_tools: list[dict[str, Any]],
    ) -> str:
        """Build default system prompt with tool info."""
        tool_names = (
            [t["name"] for t in avail_tools] if avail_tools else []
        )
        tools_section = ""
        if tool_names:
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
            tools_section = (
                "\n\nYou have the following tools available."
                " Use them proactively when a user's question"
                " could benefit from external data or"
                " actions:\n"
                + "\n".join(lines)
                + "\n\nWhen a user asks for current"
                " information (news, weather, facts that"
                " may have changed), USE the web_search"
                " tool rather than relying on your training"
                " data. When a user asks you to use a"
                " specific service (e.g. 'use Tavily',"
                " 'search the web'), call the appropriate"
                " tool."
            )

        return (
            "You are Noa, a personal AI assistant."
            " You are helpful, precise, and concise."
            " Answer in the same language the user"
            " writes in."
            + tools_section
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
