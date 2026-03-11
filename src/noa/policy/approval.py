"""Approval service — SPEC.md §29.6, §23.2."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from noa.db.models.approval import Approval

logger = logging.getLogger(__name__)


@dataclass
class ApprovalRule:
    """A policy rule governing approval behaviour for a risk tier.

    Optionally carries an ``allowed_tools`` list that restricts which
    tools the orchestrator may expose to the LLM when this rule applies.
    ``None`` means no restriction (all user-enabled tools allowed).
    An empty list means no tools are permitted.
    """

    risk_tier: str
    allowed_tools: list[str] | None = field(default=None)


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
        """Create a pending approval request per §29.6.

        Also queues a push notification via APNs if the service is
        available (§29.5).
        """
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

        # Push notification hook (§29.5)
        self._notify_push(
            user_id=user_id,
            notification_type="approval_required",
            request_id=approval.id,
            risk_tier=risk_tier,
            domain=domain,
        )

        return approval

    def _notify_push(
        self,
        *,
        user_id: uuid.UUID,
        notification_type: str,
        request_id: uuid.UUID,
        risk_tier: str,
        domain: str,
    ) -> None:
        """Schedule a push notification via APNs as a fire-and-forget task."""
        import asyncio

        try:
            from noa.api.app_state import get_apns_service

            apns = get_apns_service()
            if apns is None:
                return
            if not apns.should_notify(
                event_type=notification_type, risk_tier=risk_tier
            ):
                return

            from noa.push.tasks import send_push_to_user

            asyncio.create_task(
                send_push_to_user(
                    user_id=user_id,
                    notification_type=notification_type,
                    request_id=request_id,
                    risk_tier=risk_tier,
                )
            )
            logger.info(
                "Push notification scheduled: type=%s user=%s request=%s",
                notification_type,
                user_id,
                request_id,
            )
        except RuntimeError:
            # No running event loop (e.g. sync test context) — skip push
            logger.debug("No event loop for push notification, skipping")
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to schedule push notification", exc_info=True
            )

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
