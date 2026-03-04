"""Pydantic schemas for audit log entries — SPEC.md §28.1."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class AuditEntryCreate(BaseModel):
    """Input schema for creating an audit log entry."""

    user_id: uuid.UUID
    session_id: uuid.UUID
    device_id: uuid.UUID
    trace_id: uuid.UUID
    domain: str
    model_provider: str
    model_name: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    tool_result_summary: str | None = None
    side_effects: dict[str, Any] | None = None
    privacy_classification: str
    classification_confidence: float
    classification_reasoning: str | None = None


class AuditEntryRead(BaseModel):
    """Output schema for reading an audit log entry."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    timestamp: datetime
    user_id: uuid.UUID
    session_id: uuid.UUID
    device_id: uuid.UUID
    trace_id: uuid.UUID
    domain: str
    model_provider: str
    model_name: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    tool_result_summary: str | None = None
    side_effects: dict[str, Any] | None = None
    privacy_classification: str
    classification_confidence: float
    classification_reasoning: str | None = None
    previous_entry_hash: str | None = None
