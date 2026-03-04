"""Run/Event CRUD service — SPEC.md §22.1, §22.2, §22.3, §22.5."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from noa.db.models.artifact import Artifact
from noa.db.models.run import Run, RunEvent
from noa.runs.schemas import VALID_EVENT_TYPES, VALID_TRANSITIONS


class RunService:
    """Service layer for Run, RunEvent, and Artifact operations."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # -- Run CRUD ------------------------------------------------------------

    def create_run(
        self,
        user_id: uuid.UUID,
        thread_id: uuid.UUID,
        *,
        risk_tier: str = "low",
        privacy_mode: str = "private",
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
        self._session.flush()
        return run

    def get_run(self, run_id: uuid.UUID) -> Run | None:
        """Get a run by ID, or None if not found."""
        return self._session.query(Run).filter(Run.id == run_id).first()

    def list_runs(
        self,
        *,
        thread_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[Run]:
        """List runs with optional filters."""
        q = self._session.query(Run)
        if thread_id is not None:
            q = q.filter(Run.thread_id == thread_id)
        if user_id is not None:
            q = q.filter(Run.user_id == user_id)
        if status is not None:
            q = q.filter(Run.status == status)
        return q.order_by(Run.created_at.desc()).all()

    def update_status(self, run_id: uuid.UUID, new_status: str) -> Run:
        """Transition a run to a new status, enforcing valid transitions."""
        run = self._session.query(Run).filter(Run.id == run_id).one()
        allowed = VALID_TRANSITIONS.get(run.status, frozenset())
        if new_status not in allowed:
            msg = f"Invalid status transition: {run.status} -> {new_status}"
            raise ValueError(msg)
        run.status = new_status
        run.updated_at = datetime.now(UTC)
        self._session.flush()
        return run

    def update_run(self, run_id: uuid.UUID, **kwargs: object) -> Run:
        """Update arbitrary run fields (e.g. summary)."""
        run = self._session.query(Run).filter(Run.id == run_id).one()
        for key, value in kwargs.items():
            setattr(run, key, value)
        run.updated_at = datetime.now(UTC)
        self._session.flush()
        return run

    # -- Event operations ----------------------------------------------------

    def append_event(
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
        self._session.flush()
        return event

    def list_events(self, run_id: uuid.UUID) -> list[RunEvent]:
        """List events for a run, ordered by timestamp."""
        return (
            self._session.query(RunEvent)
            .filter(RunEvent.run_id == run_id)
            .order_by(RunEvent.timestamp.asc())
            .all()
        )

    # -- Artifact operations -------------------------------------------------

    def create_artifact(
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
        self._session.flush()
        return artifact

    def list_artifacts(self, run_id: uuid.UUID) -> list[Artifact]:
        """List artifacts for a run."""
        return (
            self._session.query(Artifact)
            .filter(Artifact.run_id == run_id)
            .order_by(Artifact.created_at.asc())
            .all()
        )
