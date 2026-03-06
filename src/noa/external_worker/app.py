"""FastAPI application factory for the external worker.

Spec refs: SPEC.md Section 8.2, §28.5
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

_APP_VERSION = "0.1.0"


def create_external_app() -> FastAPI:
    """Create the external worker FastAPI application."""
    app = FastAPI(
        title="Noa External Worker",
        description="External domain worker -- Domain B",
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

    return app
