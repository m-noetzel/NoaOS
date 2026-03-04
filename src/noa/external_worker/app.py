"""FastAPI application factory for the external worker.

Spec refs: SPEC.md Section 8.2
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse


def create_external_app() -> FastAPI:
    """Create the external worker FastAPI application."""
    app = FastAPI(
        title="Noa External Worker",
        description="External domain worker -- Domain B",
        version="0.1.0",
        default_response_class=JSONResponse,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
