"""Health endpoints — SPEC.md §28.5."""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Query

from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope

logger = logging.getLogger(__name__)
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

    # Pool statistics (OP4)
    from noa.api.app_state import get_engine

    engine = get_engine()
    if engine is not None:
        try:
            pool = engine.pool
            data["pool_size"] = pool.size()
            data["pool_checkedin"] = pool.checkedin()
            data["pool_checkedout"] = pool.checkedout()
            data["pool_overflow"] = pool.overflow()
        except Exception:  # noqa: BLE001
            logger.debug("Failed to collect pool stats")

    return success_envelope(data=data, trace_id=trace_id_ctx.get(""))


@router.get("/health/echo")
async def echo(value: str = Query(...)) -> dict[str, Any]:
    """Echo endpoint used for validation error testing."""
    return success_envelope(
        data={"echo": value},
        trace_id=trace_id_ctx.get(""),
    )


def _get_gateway() -> Any | None:
    """Retrieve the ToolGateway from app state (test-patchable)."""
    from noa.api.app_state import get_gateway

    return get_gateway()


def _percentile(data: list[float], pct: float) -> float:
    """Compute a percentile value from sorted data."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (pct / 100.0)
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[f]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


@router.get("/health/tools")
async def tool_stats() -> dict[str, Any]:
    """Per-tool statistics (last 24h) — call count, error rate, latency percentiles."""
    gateway = _get_gateway()
    tools: dict[str, Any] = {}

    if gateway is not None:
        for entry in gateway.telemetry:
            tool_name = entry["tool"]
            if tool_name not in tools:
                tools[tool_name] = {
                    "call_count": 0,
                    "error_count": 0,
                    "latencies": [],
                }
            tools[tool_name]["call_count"] += 1
            if entry["status"] == "error":
                tools[tool_name]["error_count"] += 1
            tools[tool_name]["latencies"].append(entry["latency_ms"])

    # Compute derived stats
    result: dict[str, Any] = {}
    for tool_name, stats in tools.items():
        count = stats["call_count"]
        latencies = stats["latencies"]
        result[tool_name] = {
            "call_count": count,
            "error_rate": stats["error_count"] / count if count > 0 else 0.0,
            "p50_latency_ms": round(_percentile(latencies, 50), 3),
            "p95_latency_ms": round(_percentile(latencies, 95), 3),
        }

    return success_envelope(
        data={"tools": result},
        trace_id=trace_id_ctx.get(""),
    )
