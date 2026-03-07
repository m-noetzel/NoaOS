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
        model: str = "anthropic/claude-haiku",
        provider: str | None = None,
        system_prompt: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Execute the graph and yield structured events.

        Args:
            message: User message text.
            run_service: RunService instance for persisting events.
            run_id: The Run ID to append events to.
            privacy_mode: "external" or "private".
            model: Model identifier.
            provider: Optional provider override.

        Yields:
            Event dicts with event_type, payload, timestamp.
        """
        # 1. message_received
        event = self._make_event(
            "message_received",
            {"message": message},
        )
        self._persist_event(run_service, run_id, event)
        yield event

        # 2. Transition to running
        try:
            run_service.update_status(run_id, "running")
        except Exception:  # noqa: BLE001
            logger.warning("Failed to update run status to running")

        # 3. classification_done (pre-graph — we know the privacy_mode)
        event = self._make_event(
            "classification_done",
            {"privacy_mode": privacy_mode, "model": model},
        )
        self._persist_event(run_service, run_id, event)
        yield event

        # 4. step_started
        event = self._make_event(
            "step_started",
            {"step": "agent"},
        )
        self._persist_event(run_service, run_id, event)
        yield event

        # 5. Invoke graph
        try:
            messages: list[dict[str, Any]] = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": message})

            initial_state: dict[str, Any] = {
                "messages": messages,
                "privacy_mode": privacy_mode,
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
            }

            result = await self._graph.ainvoke(initial_state)

            # 6. Emit tool events if any
            tool_calls = result.get("tool_calls", [])
            for tc in tool_calls:
                tc_event = self._make_event(
                    "tool_called",
                    {"tool_call": tc},
                )
                self._persist_event(run_service, run_id, tc_event)
                yield tc_event

            tool_results = result.get("tool_results", [])
            for tr in tool_results:
                tr_event = self._make_event(
                    "tool_result",
                    {"tool_result": tr},
                )
                self._persist_event(run_service, run_id, tr_event)
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
            self._persist_event(run_service, run_id, event)
            yield event

            # 8. Transition to completed
            try:
                run_service.update_status(run_id, "completed")
            except Exception:  # noqa: BLE001
                logger.warning("Failed to update run status to completed")

        except Exception as exc:
            # Error event
            error_event = self._make_event(
                "error",
                {"error": str(exc), "error_type": type(exc).__name__},
            )
            self._persist_event(run_service, run_id, error_event)
            yield error_event

            # Transition to failed
            try:
                run_service.update_status(run_id, "failed")
            except Exception:  # noqa: BLE001
                logger.warning("Failed to update run status to failed")

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
    def _persist_event(
        run_service: Any,
        run_id: str,
        event: dict[str, Any],
    ) -> None:
        """Persist an event via RunService (best-effort)."""
        try:
            run_service.append_event(
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
