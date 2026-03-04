"""RPC request/response Pydantic models per SPEC.md §9.1-§9.2."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class RPCRequestPayload(BaseModel):
    """Payload section of an RPC request."""

    query: str = ""
    fact: str | None = None
    n_results: int = 5
    document_id: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)

    # Allow extra fields (they get validated at the total-size level)
    model_config = {"extra": "allow"}


class RPCRequest(BaseModel):
    """RPC request model per §9.1."""

    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    idempotency_key: str
    task_type: str
    payload: RPCRequestPayload
    timeout_ms: int = 30000

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RPCRequest:
        """Parse a dict into an RPCRequest, applying defaults."""
        return cls(**data)


class RPCResponseResult(BaseModel):
    """Result section of an RPC response."""

    answer: str = ""
    facts: list[Any] = Field(default_factory=list)
    doc_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class RPCResponse(BaseModel):
    """RPC response model per §9.2."""

    request_id: str
    status: str = "success"
    result: RPCResponseResult = Field(default_factory=RPCResponseResult)
    sensitivity_label: str = "none"
    error: dict[str, Any] | None = None
