"""Standard response envelope and error schemas — SPEC.md §25.3."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Error detail included in envelope when ok=False."""

    code: str
    message: str
    details: list[Any] | None = None


class Envelope(BaseModel):
    """Standard response envelope per §25.3.

    All API responses are wrapped in this structure.
    """

    ok: bool
    data: dict[str, Any] | list[Any] | None = None
    error: ErrorDetail | None = None
    trace_id: str = Field(default="")


def success_envelope(
    data: dict[str, Any] | list[Any], trace_id: str
) -> dict[str, Any]:
    """Build a success envelope dict."""
    return {
        "ok": True,
        "data": data,
        "error": None,
        "trace_id": trace_id,
    }


def error_envelope(
    code: str, message: str, trace_id: str, details: list[Any] | None = None
) -> dict[str, Any]:
    """Build an error envelope dict."""
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {
        "ok": False,
        "data": None,
        "error": error,
        "trace_id": trace_id,
    }
