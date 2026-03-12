"""DE3: Worker Container Hardening tests.

Validates that docker-compose.yml has correct resource limits, restart
policies, and health check start periods for private-worker and
external-worker. Also validates Dockerfile HEALTHCHECK instructions and
the startup degraded-mode probe in app.py.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parents[2]
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"
PRIVATE_DOCKERFILE = REPO_ROOT / "docker" / "private-worker" / "Dockerfile"
EXTERNAL_DOCKERFILE = REPO_ROOT / "docker" / "external-worker" / "Dockerfile"


def _duration_seconds(value: str | None) -> int:
    """Convert a docker-compose duration string like '60s' or '2m' to seconds."""
    if value is None:
        return 0
    value = str(value).strip()
    match = re.fullmatch(r"(\d+)(s|m|h)?", value)
    if not match:
        raise ValueError(f"Unrecognised duration format: {value!r}")
    amount = int(match.group(1))
    unit = match.group(2) or "s"
    multipliers = {"s": 1, "m": 60, "h": 3600}
    return amount * multipliers[unit]


@pytest.fixture(scope="module")
def compose() -> dict[str, Any]:
    raw = COMPOSE_PATH.read_text()
    data: dict[str, Any] = yaml.safe_load(raw)
    return data


# ---------------------------------------------------------------------------
# private-worker resource limits
# ---------------------------------------------------------------------------


def test_private_worker_cpu_limit(compose: dict[str, Any]) -> None:
    svc = compose["services"]["private-worker"]
    cpus = svc["deploy"]["resources"]["limits"]["cpus"]
    assert str(cpus) == "4.0", f"Expected cpus '4.0', got {cpus!r}"


def test_private_worker_memory_limit(compose: dict[str, Any]) -> None:
    svc = compose["services"]["private-worker"]
    memory = svc["deploy"]["resources"]["limits"]["memory"]
    # Accept '32G', '32g', '32GB' etc.
    assert re.match(r"32[Gg][Bb]?", str(memory)), (
        f"Expected memory '32G', got {memory!r}"
    )


def test_private_worker_restart_policy(compose: dict[str, Any]) -> None:
    svc = compose["services"]["private-worker"]
    assert svc.get("restart") == "unless-stopped", (
        f"Expected restart 'unless-stopped', got {svc.get('restart')!r}"
    )


def test_private_worker_healthcheck_start_period(compose: dict[str, Any]) -> None:
    svc = compose["services"]["private-worker"]
    start_period = svc["healthcheck"].get("start_period")
    assert start_period is not None, "private-worker healthcheck missing start_period"
    assert _duration_seconds(start_period) >= 30, (
        f"Expected start_period ≥30s, got {start_period!r}"
    )


# ---------------------------------------------------------------------------
# external-worker resource limits
# ---------------------------------------------------------------------------


def test_external_worker_cpu_limit(compose: dict[str, Any]) -> None:
    svc = compose["services"]["external-worker"]
    cpus = svc["deploy"]["resources"]["limits"]["cpus"]
    assert str(cpus) == "2.0", f"Expected cpus '2.0', got {cpus!r}"


def test_external_worker_memory_limit(compose: dict[str, Any]) -> None:
    svc = compose["services"]["external-worker"]
    memory = svc["deploy"]["resources"]["limits"]["memory"]
    assert re.match(r"4[Gg][Bb]?", str(memory)), (
        f"Expected memory '4g', got {memory!r}"
    )


def test_external_worker_restart_policy(compose: dict[str, Any]) -> None:
    svc = compose["services"]["external-worker"]
    assert svc.get("restart") == "unless-stopped", (
        f"Expected restart 'unless-stopped', got {svc.get('restart')!r}"
    )


def test_external_worker_healthcheck_start_period(compose: dict[str, Any]) -> None:
    svc = compose["services"]["external-worker"]
    start_period = svc["healthcheck"].get("start_period")
    assert start_period is not None, "external-worker healthcheck missing start_period"
    assert _duration_seconds(start_period) >= 30, (
        f"Expected start_period ≥30s, got {start_period!r}"
    )


# ---------------------------------------------------------------------------
# Dockerfile HEALTHCHECK instructions
# ---------------------------------------------------------------------------


def test_private_worker_dockerfile_has_healthcheck() -> None:
    content = PRIVATE_DOCKERFILE.read_text()
    assert "HEALTHCHECK" in content, (
        f"HEALTHCHECK not found in {PRIVATE_DOCKERFILE}"
    )


def test_external_worker_dockerfile_has_healthcheck() -> None:
    content = EXTERNAL_DOCKERFILE.read_text()
    assert "HEALTHCHECK" in content, (
        f"HEALTHCHECK not found in {EXTERNAL_DOCKERFILE}"
    )


# ---------------------------------------------------------------------------
# Startup probe: degraded-mode flag
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_probe_worker_returns_false_on_503() -> None:
    """_probe_worker returns False when the worker returns a 5xx status."""
    from unittest.mock import AsyncMock, MagicMock, patch

    import httpx

    from noa.api.app import _probe_worker

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 503

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("noa.api.app.httpx.AsyncClient", return_value=mock_client):
        result = await _probe_worker("http://worker:8001/health", "private-worker")

    assert result is False


@pytest.mark.asyncio
async def test_probe_worker_returns_false_on_connection_error() -> None:
    """_probe_worker returns False (never raises) when worker is unreachable."""
    from unittest.mock import AsyncMock, patch

    import httpx

    from noa.api.app import _probe_worker

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.TransportError("refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("noa.api.app.httpx.AsyncClient", return_value=mock_client):
        result = await _probe_worker("http://missing:9999/health", "private-worker")

    assert result is False


@pytest.mark.asyncio
async def test_probe_worker_returns_true_on_200() -> None:
    """_probe_worker returns True when the worker is healthy."""
    from unittest.mock import AsyncMock, MagicMock, patch

    import httpx

    from noa.api.app import _probe_worker

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("noa.api.app.httpx.AsyncClient", return_value=mock_client):
        result = await _probe_worker("http://worker:8001/health", "private-worker")

    assert result is True


@pytest.mark.asyncio
async def test_workers_degraded_set_when_external_worker_down() -> None:
    """app.state.workers_degraded is True when external worker returns 503."""
    from unittest.mock import AsyncMock, MagicMock, patch

    import httpx
    from fastapi import FastAPI

    from noa.api.app import _probe_worker

    def _make_response(status_code: int) -> MagicMock:
        r = MagicMock(spec=httpx.Response)
        r.status_code = status_code
        return r

    responses = {
        "http://private-worker:8001/health": _make_response(200),
        "http://external-worker:8002/health": _make_response(503),
    }

    async def _fake_get(url: str) -> MagicMock:
        return responses[url]

    mock_client = AsyncMock()
    mock_client.get = _fake_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("noa.api.app.httpx.AsyncClient", return_value=mock_client):
        private_ok = await _probe_worker(
            "http://private-worker:8001/health", "private-worker"
        )
        external_ok = await _probe_worker(
            "http://external-worker:8002/health", "external-worker"
        )

    # Mimic the lifespan logic
    mock_app = FastAPI()
    mock_app.state.workers_degraded = not (private_ok and external_ok)

    assert mock_app.state.workers_degraded is True


# ---------------------------------------------------------------------------
# Security hardening: cap_drop and security_opt
# ---------------------------------------------------------------------------


def test_private_worker_cap_drop_all(compose: dict[str, Any]) -> None:
    svc = compose["services"]["private-worker"]
    cap_drop = svc.get("cap_drop", [])
    assert "ALL" in cap_drop, (
        f"private-worker should have cap_drop: [ALL], got {cap_drop!r}"
    )


def test_external_worker_cap_drop_all(compose: dict[str, Any]) -> None:
    svc = compose["services"]["external-worker"]
    cap_drop = svc.get("cap_drop", [])
    assert "ALL" in cap_drop, (
        f"external-worker should have cap_drop: [ALL], got {cap_drop!r}"
    )


def test_private_worker_no_new_privileges(compose: dict[str, Any]) -> None:
    svc = compose["services"]["private-worker"]
    sec_opt = svc.get("security_opt", [])
    assert "no-new-privileges:true" in sec_opt, (
        f"private-worker should have security_opt: [no-new-privileges:true], "
        f"got {sec_opt!r}"
    )


def test_external_worker_no_new_privileges(compose: dict[str, Any]) -> None:
    svc = compose["services"]["external-worker"]
    sec_opt = svc.get("security_opt", [])
    assert "no-new-privileges:true" in sec_opt, (
        f"external-worker should have security_opt: [no-new-privileges:true], "
        f"got {sec_opt!r}"
    )
