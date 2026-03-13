"""Approval event batcher — iOS1.

Spec refs: SPEC.md §23.2 (Approval Batching)
Groups approval events within a configurable time window into single
notifications, with strict domain isolation (private vs external).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class ApprovalBatch:
    """A batch of approval events for a single domain."""

    request_ids: list[uuid.UUID] = field(default_factory=list)
    risk_tier: str = "low"
    domain: str = "external"
    started_at: float = field(default_factory=time.monotonic)


class ApprovalBatcher:
    """Batches approval events within a time window.

    Parameters
    ----------
    window_seconds : int | float
        Maximum time (in seconds) to hold events before flushing.
        Events arriving after this window start a new batch.
    """

    def __init__(self, window_seconds: int | float = 30) -> None:
        self._window_seconds = window_seconds
        # user_id -> domain -> list of batches
        self._pending: dict[uuid.UUID, dict[str, list[ApprovalBatch]]] = {}

    def add_event(
        self,
        *,
        user_id: uuid.UUID,
        request_id: uuid.UUID,
        risk_tier: str,
        domain: str,
    ) -> None:
        """Add an approval event to the batcher.

        Events are grouped by user and domain. Within a domain, events
        that arrive within ``window_seconds`` of the current batch's start
        are appended to that batch; otherwise a new batch is created.
        """
        now = time.monotonic()

        if user_id not in self._pending:
            self._pending[user_id] = {}

        domain_batches = self._pending[user_id]

        if domain not in domain_batches:
            domain_batches[domain] = []

        batches = domain_batches[domain]

        # Try to append to the most recent batch if within window
        if batches:
            latest = batches[-1]
            elapsed = now - latest.started_at
            if elapsed <= self._window_seconds:
                latest.request_ids.append(request_id)
                # Escalate risk tier if higher
                if _risk_rank(risk_tier) > _risk_rank(latest.risk_tier):
                    latest.risk_tier = risk_tier
                return

        # Start a new batch
        batch = ApprovalBatch(
            request_ids=[request_id],
            risk_tier=risk_tier,
            domain=domain,
            started_at=now,
        )
        batches.append(batch)

    def flush(self, user_id: uuid.UUID) -> list[ApprovalBatch]:
        """Flush and return all pending batches for the given user.

        Returns a list of ``ApprovalBatch`` objects, one per
        domain-window combination.
        """
        domain_batches = self._pending.pop(user_id, {})
        result: list[ApprovalBatch] = []
        for batches in domain_batches.values():
            result.extend(batches)
        return result


_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _risk_rank(tier: str) -> int:
    return _RISK_ORDER.get(tier, 0)
