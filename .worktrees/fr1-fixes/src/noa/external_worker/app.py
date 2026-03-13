"""FastAPI application factory for the external worker.

Spec refs: SPEC.md Section 8.2, §28.5
"""

from __future__ import annotations

import logging
import time
from typing import Any, cast

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from noa.llm.exceptions import ProviderError

logger = logging.getLogger(__name__)


class CompleteRequest(BaseModel):
    """Request body for POST /v1/complete."""

    messages: list[dict[str, Any]]
    model: str | None = None
    provider: str | None = None
    max_tokens: int = 1024
    privacy_mode: str = "external"
    temperature: float | None = None


class CompleteResponse(BaseModel):
    """Response body for POST /v1/complete."""

    content: str = ""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)
    provider: str = ""
    model: str = ""

_APP_VERSION = "0.1.0"


def create_external_app(settings: Any = None) -> FastAPI:
    """Create the external worker FastAPI application.

    Args:
        settings: Optional settings object with provider API keys.
            When provided, a ProviderRouter is created at startup
            using from_settings() for real LLM dispatch.
    """
    app = FastAPI(
        title="Noa External Worker",
        description="External domain worker -- Domain B",
        version=_APP_VERSION,
        default_response_class=JSONResponse,
    )

    _start_time = time.monotonic()

    # Build a ProviderRouter at startup if settings are available
    if settings is not None:
        from noa.external_worker.llm.router import ProviderRouter

        app.state.router = ProviderRouter.from_settings(settings)

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

    @app.post("/v1/complete", response_model=None)
    async def complete(body: CompleteRequest) -> dict[str, Any] | JSONResponse:
        """LLM completion endpoint using ProviderRouter (§8.2, H1)."""
        router = getattr(app.state, "router", None)
        if router is None:
            return JSONResponse(
                status_code=503,
                content={"error": "ProviderRouter not configured"},
            )

        try:
            result = await router.complete(
                messages=body.messages,
                max_tokens=body.max_tokens,
                privacy_mode=body.privacy_mode,
                provider=body.provider,
                model=body.model,
            )
        except (httpx.HTTPError, ValueError, KeyError, ProviderError) as exc:
            logger.error("complete_endpoint_error: %s", exc)
            return JSONResponse(
                status_code=502,
                content={"error": str(exc)},
            )
        return cast(dict[str, Any], result)

    return app
