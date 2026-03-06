"""Health endpoints — SPEC.md §28.5."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Query

from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope

router = APIRouter(tags=["health"])

_start_time: float = time.monotonic()


@router.get("/health")
async def liveness() -> dict[str, Any]:
    """Liveness probe — always returns 200."""
    return success_envelope(
        data={"status": "alive"},
        trace_id=trace_id_ctx.get(""),
    )


@router.get("/health/ready")
async def readiness() -> dict[str, Any]:
    """Readiness probe — checks DB connectivity."""
    from noa.api.app_state import get_engine

    engine = get_engine()
    status = "ready"
    if engine is not None:
        try:
            async with engine.connect() as conn:
                await conn.execute(
                    __import__("sqlalchemy").text("SELECT 1")
                )
        except Exception:  # noqa: BLE001
            status = "degraded"
    else:
        status = "ready"  # No engine configured (e.g. testing)

    return success_envelope(
        data={"status": status},
        trace_id=trace_id_ctx.get(""),
    )


@router.get("/health/metrics")
async def metrics() -> dict[str, Any]:
    """Application metrics including 24h private-worker availability."""
    from noa import __version__
    from noa.api.app_state import get_health_checker

    uptime = time.monotonic() - _start_time
    data: dict[str, Any] = {
        "uptime_seconds": round(uptime, 2),
        "version": __version__,
    }

    checker = get_health_checker()
    if checker is not None:
        data["private_worker"] = checker.stats_24h()

    return success_envelope(data=data, trace_id=trace_id_ctx.get(""))


@router.get("/health/echo")
async def echo(value: str = Query(...)) -> dict[str, Any]:
    """Echo endpoint used for validation error testing."""
    return success_envelope(
        data={"echo": value},
        trace_id=trace_id_ctx.get(""),
    )
