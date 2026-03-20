"""Langfuse observability client with graceful degradation.

One trace per run, one generation span per LLM call, one span per tool call.
All operations silently no-op when:
  - langfuse package is not installed
  - LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY env vars are absent
  - Langfuse server is unreachable

Spec refs: SPEC.md — LF1
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Module-level singleton — lazily initialised once per process.
_langfuse_instance: Any | None = None
_langfuse_checked: bool = False


def get_langfuse() -> Any | None:
    """Return a Langfuse client singleton, or None if unavailable.

    Checks once per process:
    1. Is the ``langfuse`` package installed?
    2. Are LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY set?

    Subsequent calls return the cached result without re-importing.
    """
    global _langfuse_instance, _langfuse_checked  # noqa: PLW0603

    if _langfuse_checked:
        return _langfuse_instance

    _langfuse_checked = True
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "")

    if not public_key or not secret_key:
        logger.debug(
            "Langfuse disabled: LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set",
        )
        return None

    try:
        from langfuse import Langfuse

        host = os.environ.get("LANGFUSE_HOST", "http://langfuse:3000")
        _langfuse_instance = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
        logger.info("Langfuse observability enabled (host=%s)", host)
    except ImportError:
        logger.debug("Langfuse SDK not installed — observability disabled")
    except Exception:  # noqa: BLE001
        logger.warning(
            "Langfuse initialisation failed — observability disabled",
            exc_info=True,
        )

    return _langfuse_instance


def flush() -> None:
    """Flush pending Langfuse events (best-effort, non-blocking)."""
    lf = get_langfuse()
    if lf is None:
        return
    try:
        lf.flush()
    except Exception:  # noqa: BLE001
        logger.debug("Langfuse flush failed", exc_info=True)


class TraceContext:
    """Wraps a single Langfuse trace for one agent run.

    All public methods silently no-op when Langfuse is unavailable.

    Usage::

        ctx = TraceContext(run_id="...", user_id="...", metadata={})
        ctx.generation(
            "agent", model="gpt-4o", input_messages=[...], output="...", usage={}
        )
        ctx.span("tool/web_search", input={"query": "..."}, output={"results": [...]})
        ctx.score("goal_alignment", 4.0)
        ctx.flush()
    """

    def __init__(
        self,
        run_id: str,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._trace: Any | None = None
        self._run_id = run_id

        lf = get_langfuse()
        if lf is None:
            return

        try:
            self._trace = lf.trace(
                id=run_id,
                name=f"run/{run_id}",
                user_id=user_id,
                metadata=metadata or {},
            )
        except Exception:  # noqa: BLE001
            logger.debug(
                "Failed to create Langfuse trace for run %s",
                run_id,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Recording helpers
    # ------------------------------------------------------------------

    def generation(
        self,
        name: str,
        model: str,
        input_messages: list[dict[str, Any]],
        output: str,
        usage: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record an LLM generation span.

        Args:
            name: Span name, e.g. ``"agent"`` or ``"classifier"``.
            model: Model identifier, e.g. ``"gpt-4o"``.
            input_messages: The messages list sent to the LLM.
            output: The raw completion string.
            usage: Optional token usage dict
                (``{"prompt_tokens": N, "completion_tokens": N}``).
            metadata: Optional extra metadata dict.
        """
        if self._trace is None:
            return
        try:
            self._trace.generation(
                name=name,
                model=model,
                input=input_messages,
                output=output,
                usage=usage or {},
                metadata=metadata or {},
            )
        except Exception:  # noqa: BLE001
            logger.debug(
                "Langfuse generation() failed for span %s",
                name,
                exc_info=True,
            )

    def span(
        self,
        name: str,
        input: dict[str, Any] | None = None,  # noqa: A002
        output: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a generic span (tool call, planning step, etc.).

        Args:
            name: Span name, e.g. ``"tool/web_search"``.
            input: Input payload for the span.
            output: Output payload for the span.
            metadata: Optional extra metadata.
        """
        if self._trace is None:
            return
        try:
            self._trace.span(
                name=name,
                input=input or {},
                output=output or {},
                metadata=metadata or {},
            )
        except Exception:  # noqa: BLE001
            logger.debug(
                "Langfuse span() failed for span %s",
                name,
                exc_info=True,
            )

    def score(
        self,
        name: str,
        value: float,
        comment: str | None = None,
    ) -> None:
        """Attach an evaluation score to this trace.

        Args:
            name: Score dimension name, e.g. ``"goal_alignment"``.
            value: Numeric score (e.g. 0–5).
            comment: Optional human-readable comment.
        """
        if self._trace is None:
            return
        try:
            self._trace.score(
                name=name,
                value=value,
                comment=comment,
            )
        except Exception:  # noqa: BLE001
            logger.debug(
                "Langfuse score() failed for %s",
                name,
                exc_info=True,
            )

    def update(self, **kwargs: Any) -> None:
        """Update trace-level fields (e.g. output, metadata).

        Keyword arguments are forwarded directly to ``trace.update()``.
        """
        if self._trace is None:
            return
        try:
            self._trace.update(**kwargs)
        except Exception:  # noqa: BLE001
            logger.debug("Langfuse trace.update() failed", exc_info=True)

    def flush(self) -> None:
        """Flush pending events for this trace (delegates to module-level flush)."""
        flush()
