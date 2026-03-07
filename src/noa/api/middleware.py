"""Middleware: request ID, error handling, idempotency — SPEC.md §25.3, §25.4."""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from noa.api.schemas.common import error_envelope

# Context var to carry trace_id through the request lifecycle
trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="")

# Context var for idempotency key — set by middleware, read by endpoints (M1)
idempotency_key_ctx: ContextVar[str | None] = ContextVar(
    "idempotency_key", default=None
)


def extract_idempotency_key(headers: dict[str, str]) -> str | None:
    """Extract Idempotency-Key from request headers per §25.4.

    Case-insensitive lookup per RFC 7230 (HTTP headers are case-insensitive).
    Starlette/FastAPI normalises headers to lowercase, so we check both forms.

    Args:
        headers: Request headers dict.

    Returns:
        The idempotency key string, or None if not present.
    """
    # Fast path: try canonical and lowercase forms first
    value = headers.get("Idempotency-Key") or headers.get("idempotency-key")
    if value is not None:
        return value
    # Fallback: full case-insensitive scan
    for k, v in headers.items():
        if k.lower() == "idempotency-key":
            return v
    return None


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique trace_id to every request."""

    async def dispatch(self, request: Request, call_next: Any) -> Any:  # noqa: ANN401
        rid = str(uuid.uuid4())
        trace_id_ctx.set(rid)
        # M1: Extract idempotency key from request headers
        idem_key = extract_idempotency_key(dict(request.headers))
        idempotency_key_ctx.set(idem_key)
        response = await call_next(request)
        response.headers["X-Trace-ID"] = rid
        return response


def register_error_handlers(app: FastAPI) -> None:
    """Register global exception handlers that return envelope responses."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        rid = trace_id_ctx.get("")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope(
                code=f"HTTP_{exc.status_code}",
                message=str(exc.detail),
                trace_id=rid,
            ),
            headers={"X-Trace-ID": rid},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        rid = trace_id_ctx.get("")
        return JSONResponse(
            status_code=422,
            content=error_envelope(
                code="VALIDATION_ERROR",
                message="Request validation failed",
                trace_id=rid,
                details=list(exc.errors()),
            ),
            headers={"X-Trace-ID": rid},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        rid = trace_id_ctx.get("")
        return JSONResponse(
            status_code=500,
            content=error_envelope(
                code="INTERNAL_ERROR",
                message="An internal error occurred",
                trace_id=rid,
            ),
            headers={"X-Trace-ID": rid},
        )
