"""Run/Event Pydantic schemas — SPEC.md §22.1, §22.2, §22.3."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# Valid event types per §22.2
VALID_EVENT_TYPES = frozenset(
    [
        "message_received",
        "classification_done",
        "step_started",
        "token_stream",
        "tool_called",
        "tool_result",
        "approval_requested",
        "approval_received",
        "artifact_created",
        "result_ready",
        "error",
    ]
)

# Valid run statuses per §22.1
VALID_STATUSES = frozenset(
    ["pending", "running", "awaiting_approval", "completed", "failed", "cancelled"]
)

# Valid status transitions (from -> set of allowed targets)
VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset(["running", "cancelled"]),
    "running": frozenset(["awaiting_approval", "completed", "failed", "cancelled"]),
    "awaiting_approval": frozenset(["running", "cancelled"]),
    "completed": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
}


class RunCreate(BaseModel):
    """Input schema for creating a run."""

    thread_id: uuid.UUID
    user_id: uuid.UUID
    risk_tier: str = "low"
    privacy_mode: str = "private"
    summary: str | None = None


class RunRead(BaseModel):
    """Output schema for reading a run."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    thread_id: uuid.UUID
    user_id: uuid.UUID
    status: str
    risk_tier: str
    privacy_mode: str
    summary: str | None
    created_at: datetime
    updated_at: datetime


class EventCreate(BaseModel):
    """Input schema for appending an event."""

    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class EventRead(BaseModel):
    """Output schema for reading an event."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    run_id: uuid.UUID
    event_type: str
    timestamp: datetime
    payload: dict[str, Any]


class ArtifactCreate(BaseModel):
    """Input schema for creating an artifact."""

    artifact_type: str = Field(alias="type")
    name: str
    mime_type: str
    size_bytes: int
    storage_ref: str


class ArtifactRead(BaseModel):
    """Output schema for reading an artifact."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    run_id: uuid.UUID
    type: str
    name: str
    mime_type: str
    size_bytes: int
    storage_ref: str
    created_at: datetime
