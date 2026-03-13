"""FastAPI application factory for the private worker.

Spec refs: SPEC.md §8.1, §9.1, §28.5
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from noa.private_worker.handlers import get_handler
from noa.private_worker.rpc import validate_request
from noa.private_worker.schemas import RPCRequest, RPCResponse, RPCResponseResult

logger = logging.getLogger(__name__)

_APP_VERSION = "0.1.0"


def create_private_app() -> FastAPI:
    """Create the private worker FastAPI application."""
    app = FastAPI(
        title="Noa Private Worker",
        description="Private domain worker — Domain A (no internet)",
        version=_APP_VERSION,
        default_response_class=JSONResponse,
    )

    _start_time = time.monotonic()

    @app.get("/health")
    async def health() -> dict[str, Any]:
        """Liveness probe (§28.5)."""
        return {
            "status": "ok",
            "uptime_seconds": round(time.monotonic() - _start_time, 2),
            "version": _APP_VERSION,
        }

    @app.get("/health/ready")
    async def health_ready() -> dict[str, Any]:
        """Readiness probe (§28.5)."""
        return {
            "ready": True,
            "status": "ok",
        }

    @app.post("/rpc")
    async def rpc_dispatch(body: RPCRequest) -> dict[str, Any]:
        """RPC dispatch endpoint per SPEC.md §9.1 (H1)."""
        # Validate the request against §9.1 limits
        raw = body.model_dump()
        validation = validate_request(raw)
        if not validation.is_valid:
            logger.warning("rpc_validation_failed: %s", validation.error)
            return RPCResponse(
                request_id=body.request_id,
                status="error",
                error={"message": validation.error},
            ).model_dump()

        handler = get_handler(body.task_type)
        if handler is None:
            return RPCResponse(
                request_id=body.request_id,
                status="error",
                error={"message": f"Unknown task_type: {body.task_type}"},
            ).model_dump()

        try:
            result_data = await handler(raw.get("payload", {}))
            return RPCResponse(
                request_id=body.request_id,
                status="success",
                result=RPCResponseResult(**result_data),
            ).model_dump()
        except (ValueError, KeyError, TypeError) as exc:
            logger.error(
                "rpc_handler_error: task_type=%s error=%s",
                body.task_type, exc,
            )
            return RPCResponse(
                request_id=body.request_id,
                status="error",
                error={"message": str(exc)},
            ).model_dump()

    return app
