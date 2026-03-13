"""Policy/approval Pydantic schemas — SPEC.md §21, §29.6."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ApprovalRequest(BaseModel):
    """Input schema for requesting approval."""

    run_id: uuid.UUID
    user_id: uuid.UUID
    risk_tier: str
    preview_text: str | None = None
    domain: str = "private"


class ApprovalDecision(BaseModel):
    """Input schema for deciding an approval."""

    decision: str  # "approved" or "denied"


class ApprovalRead(BaseModel):
    """Output schema for reading an approval."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    run_id: uuid.UUID
    user_id: uuid.UUID
    risk_tier: str
    preview_text: str | None
    decision: str
    domain: str
    requested_at: datetime
    decided_at: datetime | None
    decided_by_user_id: uuid.UUID | None
