"""Async PostgreSQL checkpointer setup for LangGraph.

Spec ref: SPEC.md S10.1 — persistent state backed by Postgres.
Placeholder for Phase OC1; real wiring in a later phase.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class NoOpCheckpointer:
    """Placeholder checkpointer that raises NotImplementedError.

    Logs a warning at construction time to make it obvious that
    checkpointing is not yet implemented.  Phase QC8 / A4.
    """

    def __init__(self) -> None:
        logger.warning(
            "NoOpCheckpointer in use — checkpointer is a no-op stub. "
            "Persistent state checkpointing is not yet implemented."
        )

    async def save(self, *, run_id: str, state: dict[str, Any]) -> None:
        """Save checkpoint — not implemented."""
        raise NotImplementedError(
            "Checkpointer.save() is not implemented. "
            "See SPEC.md S10.1 for the planned implementation."
        )

    async def load(self, *, run_id: str) -> dict[str, Any] | None:
        """Load checkpoint — not implemented."""
        raise NotImplementedError(
            "Checkpointer.load() is not implemented. "
            "See SPEC.md S10.1 for the planned implementation."
        )
