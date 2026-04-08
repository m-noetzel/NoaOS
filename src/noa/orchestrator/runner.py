"""OrchestratorRunner — executes the LangGraph pipeline and yields SSE events.

Spec refs: SPEC.md §2.1, §22.1, §22.2, §22.4
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from noa.observability.langfuse_client import TraceContext

logger = logging.getLogger(__name__)

# OV9: Artifacts base directory — mirrors the artifacts endpoint setting.
_ARTIFACTS_BASE = Path(
    os.environ.get("ARTIFACTS_DIR", "/data/artifacts")
).resolve()

# OV2: Registry mapping run_id -> thread_id for interrupted runs awaiting
# an approval decision.  Keyed by run_id (str); value is the LangGraph
# thread_id (same as run_id for this implementation).
_pending_interrupts: dict[str, str] = {}


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
        node_models: dict[str, str] | None = None,
        eval_config: dict[str, Any] | None = None,
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
            node_models: MC1 per-node model overrides
                (keys: classifier, planner, agent, evaluator).
            eval_config: OV4 / UX-EV1 evaluator quality thresholds
                (keys: pass_threshold, reroute_threshold, max_cycles).

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

        # LF1: Create Langfuse trace for this run (no-ops when Langfuse unavailable)
        lf_trace = TraceContext(
            run_id=run_id,
            user_id=user_id,
            metadata={
                "privacy_mode": privacy_mode,
                "model": model or "default",
                "provider": provider or "default",
            },
        )
        # Set user message as trace input
        lf_trace.update(input=message)

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
            # Inject current date/time in the user's local timezone so
            # the model generates timezone-aware ISO strings for tools.
            local_now = datetime.now().astimezone()
            tz_offset = local_now.strftime("%z")  # e.g. "+0100"
            tz_fmt = f"{tz_offset[:3]}:{tz_offset[3:]}"  # "+01:00"
            tz_name = local_now.strftime("%Z")
            now_str = local_now.strftime(
                f"%A, %B %d, %Y at %H:%M ({tz_name}, UTC{tz_fmt})"
            )
            ex = f"2026-03-18T20:00:00{tz_fmt}"
            time_ctx = (
                f"Current date and time: {now_str}\n"
                f"User timezone: UTC{tz_fmt} — always include this offset "
                f"in ISO datetime strings for calendar tools (e.g. {ex})."
            )
            parts = [p for p in (sp, time_ctx, tool_ctx) if p]
            combined = "\n\n".join(parts)
            if combined:
                messages.append({"role": "system", "content": combined})

            # Include conversation history for multi-turn context.
            # ST2: Pass through tool-role messages and assistant tool_calls so
            # the LLM retains full tool context on follow-up turns (CHAT-H1).
            if history:
                for h in history:
                    role = h.get("role", "user")
                    if role == "tool":
                        messages.append({
                            "role": "tool",
                            "tool_call_id": h.get("tool_call_id", ""),
                            "name": h.get("name", ""),
                            "content": h.get("content", ""),
                        })
                    elif role == "assistant":
                        msg: dict[str, Any] = {
                            "role": "assistant",
                            "content": h.get("content", ""),
                        }
                        if h.get("tool_calls"):
                            msg["tool_calls"] = h["tool_calls"]
                        messages.append(msg)
                    elif role == "user" and h.get("content"):
                        messages.append({"role": "user", "content": h["content"]})

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
                # MC1: Seed model_config with user-configured node models.
                # The router node will merge its computed config on top,
                # but user preferences for non-agent nodes are preserved.
                "model_config": node_models or {},
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
                "run_id": run_id,
                # ST4: Per-run token callback — set after token_queue init below
                "token_callback": None,
                # CQ1: Task-level tool scope (None = all tools allowed)
                "tool_scope": tool_scope,
                # DI1: Task type (populated by classifier node)
                "task_type": None,
                # OI1: Planning node fields
                "plan": None,
                "archetype": None,
                "thoughts": [],
                "use_react": False,
                # EV1: Evaluator node fields
                "eval_scores": None,
                "eval_verdict": None,
                "eval_cycle": 0,
                # OV4: Configurable evaluator thresholds (UX-EV1)
                "eval_config": eval_config or {},
                # OV4: Evaluator reasoning for Langfuse logging (ARCH-EV1)
                "eval_reasoning": None,
                # CC1: Context compaction boundary flag
                "is_compaction_boundary": False,
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

            # LS1/ST4: Per-run token queue + callback injected into state
            # so concurrent runs never share a module-global callback.
            token_queue: asyncio.Queue[str] = asyncio.Queue()

            async def _token_cb(token: str) -> None:
                await token_queue.put(token)

            initial_state["token_callback"] = _token_cb

            # Stream node-by-node so the frontend sees events in real-time
            # instead of waiting for the entire graph to complete.
            result: dict[str, Any] = dict(initial_state)
            seen_tools: set[str] = set()

            # LS2: Timeout watchdog — track wall-clock time and break after
            # each node completes if the budget has been exceeded.
            _run_start = time.monotonic()
            _timed_out = False

            # OV2: Use run_id as LangGraph thread_id for MemorySaver checkpointing.
            _lg_config: dict[str, Any] = {"configurable": {"thread_id": run_id}}
            _interrupted = False

            # OV2: Pass config for interrupt/resume support.
            # Detect whether the graph's astream accepts 'config' to remain
            # compatible with stub graphs in tests.
            import inspect as _inspect
            try:
                _sig = _inspect.signature(self._graph.astream)
                _has_config = "config" in _sig.parameters
            except (ValueError, TypeError):
                _has_config = False
            if _has_config:
                _stream = self._graph.astream(initial_state, config=_lg_config)
            else:
                _stream = self._graph.astream(initial_state)

            async for chunk in _stream:
                # OV2: LangGraph signals an interrupt via "__interrupt__" key.
                if "__interrupt__" in chunk:
                    interrupt_data = chunk["__interrupt__"]
                    if interrupt_data:
                        try:
                            iv = interrupt_data[0].value
                        except (AttributeError, IndexError, TypeError):
                            iv = {}
                    else:
                        iv = {}

                    _pending_interrupts[run_id] = run_id
                    approval_payload_interrupt: dict[str, Any] = {
                        "tool": iv.get("tool", ""),
                        "function": iv.get("function", ""),
                        "args": iv.get("args", {}),
                        "risk_tier": iv.get("risk_tier", "medium"),
                    }
                    if iv.get("cross_domain"):
                        approval_payload_interrupt["cross_domain"] = True
                        approval_payload_interrupt["reason"] = iv.get("reason", "")

                    approval_event_interrupt = self._make_event(
                        "approval_requested",
                        approval_payload_interrupt,
                    )
                    await self._persist_event(
                        run_service, run_id, approval_event_interrupt,
                    )
                    yield approval_event_interrupt
                    _interrupted = True
                    break

                # astream yields {node_name: state_update} per completed node
                for node_name, node_output in chunk.items():
                    if not isinstance(node_output, dict):
                        continue
                    # Merge node output into accumulated result
                    result.update(node_output)

                    # LS1: Drain token queue — the agent node accumulated
                    # tokens via the callback while it was running.
                    # We drain here (after the node completes) and yield
                    # token_stream SSE events before step_started so tokens
                    # appear to stream before the step completion notice.
                    while not token_queue.empty():
                        try:
                            token = token_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break
                        token_event = self._make_event(
                            "token_stream",
                            {"token": token, "run_id": run_id},
                        )
                        yield token_event

                    # LF1: Record a span for each graph node
                    lf_trace.span(
                        name=f"node/{node_name}",
                        input={
                            k: v
                            for k, v in node_output.items()
                            if k in ("messages", "plan", "task_type",
                                     "archetype", "selected_model",
                                     "privacy_mode", "tool_calls")
                        },
                        output={
                            k: v
                            for k, v in node_output.items()
                            if k in ("response", "selected_model",
                                     "privacy_mode", "plan", "task_type",
                                     "archetype", "eval_scores",
                                     "eval_verdict", "tool_results")
                        },
                        metadata={"node": node_name},
                    )

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

                            # LF1: Record tool span
                            lf_trace.span(
                                name=f"tool/{tr_name}" if tr_name else "tool",
                                input=tr.get("args", {}),
                                output={
                                    "result": tr.get("result", tr.get("output", "")),
                                },
                                metadata={"tool_name": tr_name},
                            )

                            # Emit tool_end for completed tools
                            end_event = self._make_event(
                                "tool_end",
                                {"tool_name": tr_name, "result": tr},
                            )
                            await self._persist_event(run_service, run_id, end_event)
                            yield end_event

                            # OV2: approval_required is now handled by interrupt()
                            # in tool_node before routing reaches here.
                            # Emit tool_result for all completed tool calls.
                            tr_event = self._make_event(
                                "tool_result",
                                {"tool_result": tr, "tool_name": tr_name},
                            )
                            await self._persist_event(run_service, run_id, tr_event)
                            yield tr_event

                            # OV9: Web search artifact — format results as
                            # a Markdown report and save as an artifact.
                            if tr_name == "web_search":
                                artifact_event = await self._create_search_artifact(
                                    run_service=run_service,
                                    run_id=run_id,
                                    tool_result=tr,
                                )
                                if artifact_event is not None:
                                    await self._persist_event(
                                        run_service, run_id, artifact_event,
                                    )
                                    yield artifact_event

                # LS2: Timeout watchdog — check after each chunk (node)
                elapsed = time.monotonic() - _run_start
                if elapsed > timeout_seconds:
                    logger.warning(
                        "Orchestrator timeout: run_id=%s elapsed=%.1fs limit=%ds",
                        run_id,
                        elapsed,
                        timeout_seconds,
                        extra=log_ctx,
                    )
                    timeout_event = self._make_event(
                        "error",
                        {
                            "message": (
                                f"Orchestrator timeout after {timeout_seconds}s"
                            ),
                            "code": "TIMEOUT",
                        },
                    )
                    await self._persist_event(run_service, run_id, timeout_event)
                    yield timeout_event
                    _timed_out = True
                    break

            # LS2: Mark run as failed if timed out
            if _timed_out:
                try:
                    await run_service.update_status(run_id, "failed")
                except Exception:  # noqa: BLE001
                    logger.warning(
                        "Failed to update run status to failed (timeout): run_id=%s",
                        run_id,
                        extra=log_ctx,
                    )
                # ST4: No cleanup needed — callback is scoped to this run's state
                return

            # OV2: Mark run as awaiting_approval if graph was interrupted.
            if _interrupted:
                try:
                    await run_service.update_status(run_id, "awaiting_approval")
                except Exception:  # noqa: BLE001
                    logger.warning(
                        "Failed to update run status to awaiting_approval: run_id=%s",
                        run_id,
                        extra=log_ctx,
                    )
                logger.info(
                    "Run interrupted for approval: run_id=%s",
                    run_id,
                    extra=log_ctx,
                )
                return

            # CC1: Context window compaction — check if accumulated messages
            # exceed the threshold and compact if needed.  Compaction runs
            # after graph execution so it doesn't interrupt the LangGraph
            # node loop; the compacted messages are then checkpointed so
            # the next turn starts from a shorter history.
            result["is_compaction_boundary"] = False
            _current_messages: list[dict[str, Any]] = result.get("messages", [])
            _compaction_model = result.get("selected_model") or model or "gpt-4.1"
            from noa.orchestrator.token_budget import needs_compaction
            if needs_compaction(_current_messages, _compaction_model):
                from noa.orchestrator.nodes.agent import invoke_llm
                from noa.orchestrator.nodes.compactor import (
                    COMPACTION_MODEL,
                    compact_messages,
                )
                _compacted, _did_compact = await compact_messages(
                    _current_messages,
                    invoke_llm,
                    model=COMPACTION_MODEL,
                )
                if _did_compact:
                    result["messages"] = _compacted
                    result["is_compaction_boundary"] = True
                    compaction_event = self._make_event(
                        "compaction",
                        {
                            "messages_before": len(_current_messages),
                            "messages_after": len(_compacted),
                            "model": _compaction_model,
                        },
                    )
                    await self._persist_event(
                        run_service, run_id, compaction_event,
                    )
                    yield compaction_event
                    logger.info(
                        "Context compacted: run_id=%s before=%d after=%d",
                        run_id,
                        len(_current_messages),
                        len(_compacted),
                        extra=log_ctx,
                    )

            # A4: Save checkpoint after successful execution
            if self._checkpointer is not None:
                await self._checkpointer.save(run_id=run_id, state=result)

            # LF1: Record one generation span per LLM call from llm_usage
            llm_usage: list[dict[str, Any]] = result.get("llm_usage", [])
            for usage_entry in llm_usage:
                if not isinstance(usage_entry, dict):
                    continue
                lf_trace.generation(
                    name=usage_entry.get("node", "agent"),
                    model=usage_entry.get("model", model or "unknown"),
                    input_messages=[],  # messages not re-captured at this point
                    output="",
                    usage={
                        "prompt_tokens": usage_entry.get("prompt_tokens", 0),
                        "completion_tokens": usage_entry.get("completion_tokens", 0),
                    },
                    metadata={
                        "cost": usage_entry.get("cost", 0.0),
                        "provider": usage_entry.get("provider", ""),
                    },
                )

            # EV1: Attach evaluation scores to Langfuse trace
            eval_scores: dict[str, float] = result.get("eval_scores") or {}
            eval_verdict = result.get("eval_verdict") or "pass"
            if eval_scores:
                for dim_name, dim_score in eval_scores.items():
                    lf_trace.score(dim_name, dim_score)
                overall_score = (
                    sum(eval_scores.values()) / len(eval_scores)
                    if eval_scores
                    else 0.0
                )
                lf_trace.score("overall", overall_score)
                lf_trace.score(
                    "verdict",
                    1.0 if eval_verdict == "pass" else 0.0,
                )

            # OV3: Extract response with fallback (responder logic moved here).
            response = self._extract_response(result)
            result["response"] = response

            # OV3: Compute total_cost from accumulated llm_usage records
            # (previously done in responder_node, now done in runner after graph).
            llm_usage_final: list[dict[str, Any]] = result.get("llm_usage", [])
            total_cost = sum(
                entry.get("cost_usd", 0.0)
                for entry in llm_usage_final
                if isinstance(entry, dict)
            )
            result["total_cost"] = total_cost

            # LF1: Update trace with final output + flush
            lf_trace.update(
                output=response,
                metadata={
                    "total_cost": total_cost,
                    "privacy_mode": privacy_mode,
                    "model": model or "default",
                    "eval_verdict": eval_verdict,
                },
            )
            lf_trace.flush()

            # 7. result_ready
            event = self._make_event(
                "result_ready",
                {
                    "response": response,
                    "total_cost": total_cost,
                    "llm_usage": llm_usage_final,
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
            # ST4: No global cleanup needed — callback is scoped to this run's state

            # LF1: Update trace with error info + flush
            lf_trace.update(
                metadata={
                    "error": type(exc).__name__,
                    "privacy_mode": privacy_mode,
                },
            )
            lf_trace.flush()

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
                "Remember facts about the user (remember),"
                " recall previously stored facts (recall),"
                " or proactively extract facts alongside"
                " your response (auto_extract)."
                " Use remember when the user explicitly asks."
                " Use auto_extract when the user incidentally"
                " shares preferences, habits, or personal info."
                " Use recall to retrieve stored knowledge."
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

    # OV9: Search artifact helpers -------------------------------------------

    @staticmethod
    def _format_search_report(
        query: str,
        results: list[dict[str, Any]],
        timestamp: str,
    ) -> str:
        """Format web search results as a Markdown report."""
        lines: list[str] = [
            "# Web Search Report",
            "",
            f"**Query:** {query}",
            f"**Date:** {timestamp}",
            f"**Results:** {len(results)}",
            "",
            "---",
            "",
        ]
        for idx, result in enumerate(results, start=1):
            title = result.get("title", "(no title)")
            url = result.get("url", "")
            snippet = result.get("snippet", result.get("content", ""))
            lines.append(f"## {idx}. {title}")
            if url:
                lines.append(f"**URL:** {url}")
            if snippet:
                lines.append(snippet)
            lines.append("")
        return "\n".join(lines)

    async def _create_search_artifact(
        self,
        *,
        run_service: Any,
        run_id: str,
        tool_result: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Write a search report to disk and create an artifact DB record.

        Returns an ``artifact_created`` event dict, or None on failure.
        Best-effort — errors are logged but do not propagate.
        """
        try:
            args: dict[str, Any] = tool_result.get("args", {})
            query: str = args.get("query", "")
            result_data = tool_result.get("result", tool_result.get("output", {}))
            if isinstance(result_data, str):
                results: list[dict[str, Any]] = []
            elif isinstance(result_data, dict):
                results = result_data.get("results", [])
            elif isinstance(result_data, list):
                results = result_data
            else:
                results = []

            timestamp = datetime.now(UTC).isoformat()
            report_md = self._format_search_report(query, results, timestamp)
            report_bytes = report_md.encode("utf-8")

            artifact_dir = _ARTIFACTS_BASE / run_id
            artifact_dir.mkdir(parents=True, exist_ok=True)
            artifact_path = artifact_dir / "search_report.md"
            artifact_path.write_bytes(report_bytes)

            storage_ref = str(artifact_path)

            run_uuid = uuid.UUID(run_id) if isinstance(run_id, str) else run_id
            artifact = await run_service.create_artifact(
                run_uuid,
                artifact_type="export",
                name="search_report.md",
                mime_type="text/markdown",
                size_bytes=len(report_bytes),
                storage_ref=storage_ref,
            )

            artifact_id = str(artifact.id) if hasattr(artifact, "id") else ""
            return self._make_event(
                "artifact_created",
                {
                    "artifact_id": artifact_id,
                    "name": "search_report.md",
                    "mime_type": "text/markdown",
                    "size_bytes": len(report_bytes),
                    "storage_ref": storage_ref,
                },
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to create search artifact for run %s",
                run_id,
                exc_info=True,
            )
            return None

    # -------------------------------------------------------------------------

    async def resume(
        self,
        run_id: str,
        decision: dict[str, Any],
        *,
        run_service: Any,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Resume an interrupted graph with the user's approval decision.

        OV2: Called by the approvals endpoint when the user decides.
        Uses Command(resume=decision) to continue the graph from the
        interrupt point in tool_node.

        Args:
            run_id: The run_id (also used as LangGraph thread_id).
            decision: Dict with "decision" key: "approved" or "denied".
            run_service: RunService for status updates and event persistence.

        Yields:
            SSE event dicts (same format as run()).
        """
        from langgraph.types import Command

        thread_id = _pending_interrupts.pop(run_id, run_id)
        lg_config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}

        logger.info(
            "Resuming graph for run_id=%s with decision=%s",
            run_id,
            decision.get("decision"),
        )

        try:
            await run_service.update_status(run_id, "running")
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to update run status to running on resume: run_id=%s", run_id
            )

        try:
            # OV3: Accumulate result so we can compute response/cost after graph.
            resume_result: dict[str, Any] = {}
            _interrupted_resume = False

            async for chunk in self._graph.astream(
                Command(resume=decision), config=lg_config,
            ):
                if "__interrupt__" in chunk:
                    interrupt_data = chunk["__interrupt__"]
                    if interrupt_data:
                        try:
                            iv = interrupt_data[0].value
                        except (AttributeError, IndexError, TypeError):
                            iv = {}
                    else:
                        iv = {}

                    _pending_interrupts[run_id] = thread_id
                    ap_payload: dict[str, Any] = {
                        "tool": iv.get("tool", ""),
                        "function": iv.get("function", ""),
                        "args": iv.get("args", {}),
                        "risk_tier": iv.get("risk_tier", "medium"),
                    }
                    if iv.get("cross_domain"):
                        ap_payload["cross_domain"] = True
                        ap_payload["reason"] = iv.get("reason", "")

                    ap_event = self._make_event("approval_requested", ap_payload)
                    await self._persist_event(run_service, run_id, ap_event)
                    yield ap_event

                    try:
                        await run_service.update_status(run_id, "awaiting_approval")
                    except Exception:  # noqa: BLE001
                        logger.warning(
                            "Failed to update status to awaiting_approval: run_id=%s",
                            run_id,
                        )
                    _interrupted_resume = True
                    return

                for node_name, node_output in chunk.items():
                    if not isinstance(node_output, dict):
                        continue

                    # Merge node output into accumulated result.
                    resume_result.update(node_output)

                    step_event = self._make_event("step_started", {"step": node_name})
                    await self._persist_event(run_service, run_id, step_event)
                    yield step_event

                    if node_name == "tools":
                        for tr in node_output.get("tool_results", []):
                            if not isinstance(tr, dict):
                                continue
                            tr_name = tr.get("name", tr.get("tool_name", ""))
                            tr_event = self._make_event(
                                "tool_result",
                                {"tool_result": tr, "tool_name": tr_name},
                            )
                            await self._persist_event(run_service, run_id, tr_event)
                            yield tr_event

            # OV3: Emit result_ready after graph loop completes (was: responder node).
            if not _interrupted_resume:
                resume_response = self._extract_response(resume_result)
                resume_llm_usage: list[dict[str, Any]] = resume_result.get(
                    "llm_usage", [],
                )
                resume_cost = sum(
                    entry.get("cost_usd", 0.0)
                    for entry in resume_llm_usage
                    if isinstance(entry, dict)
                )
                result_ready_event = self._make_event(
                    "result_ready",
                    {
                        "response": resume_response,
                        "total_cost": resume_cost,
                        "llm_usage": resume_llm_usage,
                    },
                )
                await self._persist_event(run_service, run_id, result_ready_event)
                yield result_ready_event

            try:
                await run_service.update_status(run_id, "completed")
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Failed to update run status to completed after resume: run_id=%s",
                    run_id,
                )

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Resume failed: run_id=%s error=%s",
                run_id,
                str(exc),
                exc_info=True,
            )
            error_event = self._make_event(
                "error",
                {
                    "error": "An error occurred processing your request.",
                    "error_type": type(exc).__name__,
                },
            )
            await self._persist_event(run_service, run_id, error_event)
            yield error_event

            try:
                await run_service.update_status(run_id, "failed")
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Failed to update run status to failed after resume"
                    " error: run_id=%s",
                    run_id,
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
    def _extract_response(result: dict[str, Any]) -> str:
        """Extract the response text from graph result with fallback chain.

        OV3: This logic was previously in responder_node. Moved here so the
        runner computes it after the graph loop, eliminating the responder node.

        Fallback order:
        1. result["response"] if non-empty.
        2. Last non-empty assistant message content in result["messages"].
        3. "I'm sorry, I couldn't generate a response." (last resort).

        Note: The tool-result synthesized message from the old responder_node
        ("I completed the requested actions using {tool_names}...") is
        intentionally removed — it was identified as false/misleading (ARCH-RS1).
        """
        response = str(result.get("response") or "")
        if response:
            return response

        # Try the last non-empty assistant message.
        messages = result.get("messages", [])
        for msg in reversed(messages):
            if not isinstance(msg, dict):
                continue
            if msg.get("role") == "assistant":
                candidate = str(msg.get("content", "") or "")
                if candidate:
                    return candidate

        # Last resort.
        return "I'm sorry, I couldn't generate a response."

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
