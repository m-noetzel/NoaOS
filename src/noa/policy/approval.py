"""Approval service — SPEC.md §29.6, §23.2."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from noa.db.models.approval import Approval


class ApprovalService:
    """Manages approval requests, decisions, batching, and expiry."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def request_approval(
        self,
        run_id: uuid.UUID,
        user_id: uuid.UUID,
        risk_tier: str,
        preview_text: str | None = None,
        domain: str = "private",
    ) -> Approval:
        """Create a pending approval request per §29.6."""
        approval = Approval(
            id=uuid.uuid4(),
            run_id=run_id,
            user_id=user_id,
            risk_tier=risk_tier,
            preview_text=preview_text,
            decision="pending",
            domain=domain,
        )
        self._session.add(approval)
        self._session.flush()
        return approval

    def decide(
        self,
        approval_id: uuid.UUID,
        decision: str,
        decided_by: uuid.UUID,
    ) -> Approval:
        """Record an approval decision (approved/denied) per §29.6."""
        approval = (
            self._session.query(Approval)
            .filter(Approval.id == approval_id)
            .one()
        )
        if approval.decision != "pending":
            msg = f"Approval {approval_id} already decided: {approval.decision}"
            raise ValueError(msg)
        approval.decision = decision
        approval.decided_at = datetime.now(UTC)
        approval.decided_by_user_id = decided_by
        self._session.flush()
        return approval

    def list_pending(
        self,
        user_id: uuid.UUID | None = None,
        domain: str | None = None,
    ) -> list[Approval]:
        """List pending approvals, optionally filtered by user and domain."""
        q = self._session.query(Approval).filter(
            Approval.decision == "pending",
        )
        if user_id is not None:
            q = q.filter(Approval.user_id == user_id)
        if domain is not None:
            q = q.filter(Approval.domain == domain)
        return q.order_by(Approval.requested_at.asc()).all()

    def expire_stale(self, timeout_minutes: int = 5) -> list[Approval]:
        """Mark approvals older than timeout as expired per §23.2."""
        cutoff = datetime.now(UTC) - timedelta(minutes=timeout_minutes)
        stale = (
            self._session.query(Approval)
            .filter(
                Approval.decision == "pending",
                Approval.requested_at < cutoff,
            )
            .all()
        )
        for approval in stale:
            approval.decision = "expired"
            approval.decided_at = datetime.now(UTC)
        self._session.flush()
        return stale
