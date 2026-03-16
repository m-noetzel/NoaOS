"""Run/Event CRUD service — SPEC.md §22.1, §22.2, §22.3, §22.5."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select

from noa.db.models.artifact import Artifact
from noa.db.models.run import Run, RunEvent
from noa.runs.schemas import VALID_EVENT_TYPES, VALID_TRANSITIONS
from noa.types import PrivacyMode, RiskTier

logger = logging.getLogger(__name__)

# Run statuses that trigger push notifications (§29.5)
_PUSH_STATUSES = {"completed": "run_completed", "failed": "run_failed"}


class RunService:
    """Service layer for Run, RunEvent, and Artifact operations."""

    def __init__(self, session: Any = None) -> None:
        self._session = session

    # -- Run CRUD ------------------------------------------------------------

    async def create_run(
        self,
        user_id: uuid.UUID,
        thread_id: uuid.UUID,
        *,
        risk_tier: str = RiskTier.LOW,
        privacy_mode: str = PrivacyMode.PRIVATE,
        summary: str | None = None,
    ) -> Run:
        """Create a new run with status='pending'."""
        run = Run(
            id=uuid.uuid4(),
            user_id=user_id,
            thread_id=thread_id,
            status="pending",
            risk_tier=risk_tier,
            privacy_mode=privacy_mode,
            summary=summary,
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def get_run(self, run_id: uuid.UUID) -> Run | None:
        """Get a run by ID, or None if not found."""
        result = await self._session.execute(
            select(Run).where(Run.id == run_id)
        )
        return cast(Run | None, result.scalar_one_or_none())

    async def list_runs(
        self,
        *,
        thread_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[Run]:
        """List runs with optional filters."""
        stmt = select(Run)
        if thread_id is not None:
            stmt = stmt.where(Run.thread_id == thread_id)
        if user_id is not None:
            stmt = stmt.where(Run.user_id == user_id)
        if status is not None:
            stmt = stmt.where(Run.status == status)
        stmt = stmt.order_by(Run.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(self, run_id: uuid.UUID, new_status: str) -> Run:
        """Transition a run to a new status, enforcing valid transitions.

        Triggers push notification for completed/failed runs (§29.5).
        """
        result = await self._session.execute(
            select(Run).where(Run.id == run_id)
        )
        run = cast(Run, result.scalar_one())
        allowed = VALID_TRANSITIONS.get(run.status, frozenset())
        if new_status not in allowed:
            msg = f"Invalid status transition: {run.status} -> {new_status}"
            raise ValueError(msg)
        run.status = new_status
        run.updated_at = datetime.now(UTC)
        await self._session.flush()

        # Push notification hook (§29.5)
        if new_status in _PUSH_STATUSES:
            self._notify_push(run, _PUSH_STATUSES[new_status])

        return run

    def _notify_push(self, run: Run, notification_type: str) -> None:
        """Schedule a push notification for run status changes."""
        import asyncio

        try:
            from noa.api.app_state import get_apns_service

            apns = get_apns_service()
            if apns is None:
                return
            risk_tier = getattr(run, "risk_tier", RiskTier.LOW)
            if not apns.should_notify(
                event_type=notification_type,
                risk_tier=risk_tier,
            ):
                return

            from noa.push.tasks import send_push_to_user

            asyncio.create_task(
                send_push_to_user(
                    user_id=run.user_id,
                    notification_type=notification_type,
                    request_id=run.id,
                    risk_tier=risk_tier,
                )
            )
            logger.info(
                "Push notification scheduled: type=%s run=%s user=%s",
                notification_type,
                run.id,
                run.user_id,
            )
        except RuntimeError:
            # No running event loop (e.g. sync test context) — skip push
            logger.debug("No event loop for push notification, skipping")
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to schedule push notification", exc_info=True
            )

    async def update_run(self, run_id: uuid.UUID, **kwargs: object) -> Run:
        """Update arbitrary run fields (e.g. summary)."""
        result = await self._session.execute(
            select(Run).where(Run.id == run_id)
        )
        run = cast(Run, result.scalar_one())
        for key, value in kwargs.items():
            setattr(run, key, value)
        run.updated_at = datetime.now(UTC)
        await self._session.flush()
        return run

    # -- Event operations ----------------------------------------------------

    async def append_event(
        self,
        run_id: uuid.UUID,
        event_type: str,
        payload: dict[str, object],
    ) -> RunEvent:
        """Append an event to a run (append-only)."""
        if event_type not in VALID_EVENT_TYPES:
            msg = f"Invalid event type: {event_type}"
            raise ValueError(msg)
        event = RunEvent(
            id=uuid.uuid4(),
            run_id=run_id,
            event_type=event_type,
            payload=payload,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def list_events(self, run_id: uuid.UUID) -> list[RunEvent]:
        """List events for a run, ordered by timestamp."""
        result = await self._session.execute(
            select(RunEvent)
            .where(RunEvent.run_id == run_id)
            .order_by(RunEvent.timestamp.asc())
        )
        return list(result.scalars().all())

    # -- Artifact operations -------------------------------------------------

    async def create_artifact(
        self,
        run_id: uuid.UUID,
        artifact_type: str,
        name: str,
        mime_type: str,
        size_bytes: int,
        storage_ref: str,
    ) -> Artifact:
        """Create artifact metadata linked to a run."""
        artifact = Artifact(
            id=uuid.uuid4(),
            run_id=run_id,
            type=artifact_type,
            name=name,
            mime_type=mime_type,
            size_bytes=size_bytes,
            storage_ref=storage_ref,
        )
        self._session.add(artifact)
        await self._session.flush()
        return artifact

    async def list_artifacts(self, run_id: uuid.UUID) -> list[Artifact]:
        """List artifacts for a run."""
        result = await self._session.execute(
            select(Artifact)
            .where(Artifact.run_id == run_id)
            .order_by(Artifact.created_at.asc())
        )
        return list(result.scalars().all())
