"""Health endpoints — SPEC.md §28.5."""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Query

if TYPE_CHECKING:
    from noa.tools.gateway import ToolGateway

from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])

_start_time: float = time.monotonic()

# Path to backup verify status JSON (written by verify_backup.sh).
# Overridable in tests via the _VERIFY_STATUS_PATH module-level variable.
_VERIFY_STATUS_PATH: Path = Path("/backups/verify_status.json")


@router.get("/health")
async def liveness() -> dict[str, Any]:
    """Liveness probe — always returns 200."""
    return success_envelope(
        data={"status": "alive"},
        trace_id=trace_id_ctx.get(""),
    )


@router.get("/health/ready")
async def readiness() -> dict[str, Any]:
    """Readiness probe — checks DB connectivity and worker health."""
    from noa.api.app_state import get_app, get_engine

    engine = get_engine()
    status = "ready"
    degraded_reasons: list[str] = []

    if engine is not None:
        try:
            async with engine.connect() as conn:
                await conn.execute(
                    __import__("sqlalchemy").text("SELECT 1")
                )
        except Exception:  # noqa: BLE001
            status = "degraded"
            degraded_reasons.append("database")
    # else: no engine configured (e.g. testing) — skip DB check

    # W20-MED-3: Reflect worker probe results from startup
    app = get_app()
    if app is not None and getattr(app.state, "workers_degraded", False):
        status = "degraded"
        degraded_reasons.append("workers")

    data: dict[str, Any] = {"status": status}
    if degraded_reasons:
        data["degraded_components"] = degraded_reasons

    return success_envelope(
        data=data,
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
            pool: Any = engine.pool
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


def _get_gateway() -> ToolGateway | None:
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


# Stale threshold: more than 25 hours since the last backup was verified
_STALE_HOURS = 25.0


@router.get("/health/backup")
async def backup_health() -> dict[str, Any]:
    """Backup integrity status — reads verify_status.json written by verify_backup.sh.

    Returns HTTP 200 in all cases; callers inspect the `status` field:
      - "ok"         — last verify passed
      - "stale"      — last verify passed but backup is older than 25 hours
      - "failed"     — last verify failed (details in `error`)
      - "never_run"  — verify_status.json does not exist yet
    """
    status_path = _VERIFY_STATUS_PATH
    now = datetime.now(tz=UTC)

    if not status_path.exists():
        return success_envelope(
            data={
                "status": "never_run",
                "last_backup": None,
                "last_verify": None,
                "backup_age_hours": None,
            },
            trace_id=trace_id_ctx.get(""),
        )

    try:
        raw = status_path.read_text()
        verify: dict[str, Any] = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read verify_status.json: %s", exc)
        return success_envelope(
            data={
                "status": "failed",
                "last_backup": None,
                "last_verify": None,
                "backup_age_hours": None,
                "error": f"Could not read verify_status.json: {exc}",
            },
            trace_id=trace_id_ctx.get(""),
        )

    last_verify_str: str | None = verify.get("timestamp")
    backup_file: str | None = verify.get("backup_file")
    reported_status: str = verify.get("status", "failed")
    error_msg: str | None = verify.get("error") or None

    # Compute backup age in hours from the backup filename timestamp or
    # fall back to the verify timestamp itself.
    backup_age_hours: float | None = None
    if last_verify_str:
        try:
            last_verify_dt = datetime.fromisoformat(
                last_verify_str.replace("Z", "+00:00")
            )
            backup_age_hours = round(
                (now - last_verify_dt).total_seconds() / 3600.0, 2
            )
        except ValueError:
            logger.debug("Could not parse verify timestamp: %s", last_verify_str)

    # Determine final status
    if reported_status == "ok":
        if backup_age_hours is not None and backup_age_hours > _STALE_HOURS:
            final_status = "stale"
        else:
            final_status = "ok"
    else:
        final_status = reported_status

    data: dict[str, Any] = {
        "status": final_status,
        "last_backup": backup_file,
        "last_verify": last_verify_str,
        "backup_age_hours": backup_age_hours,
    }
    if error_msg:
        data["error"] = error_msg

    return success_envelope(data=data, trace_id=trace_id_ctx.get(""))
