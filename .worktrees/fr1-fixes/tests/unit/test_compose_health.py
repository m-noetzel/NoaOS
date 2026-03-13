"""Tests for docker-compose health checks and resource limits (OP3).

Validates:
- docker-compose.yml is valid YAML with expected services
- All services have healthcheck defined
- All services have resource limits (deploy.resources.limits)
- External worker health endpoint returns proper status with detail

Spec refs: §28.5, §30, §31
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

COMPOSE_PATH = Path(__file__).resolve().parents[2] / "docker-compose.yml"
EXPECTED_SERVICES = {"noa-api", "postgres", "private-worker", "external-worker"}


@pytest.fixture(scope="module")
def compose_config() -> dict[str, Any]:
    """Load docker-compose.yml as parsed YAML."""
    text = COMPOSE_PATH.read_text()
    data = yaml.safe_load(text)
    assert isinstance(data, dict), "docker-compose.yml must be a valid YAML mapping"
    return data


class TestComposeStructure:
    """docker-compose.yml structural validation."""

    def test_has_services_key(self, compose_config: dict[str, Any]) -> None:
        assert "services" in compose_config, "Missing top-level 'services' key"

    def test_expected_service_names(self, compose_config: dict[str, Any]) -> None:
        services = set(compose_config["services"].keys())
        assert EXPECTED_SERVICES.issubset(services), (
            f"Missing services: {EXPECTED_SERVICES - services}"
        )


class TestHealthChecks:
    """Every service must have a healthcheck (§31)."""

    @pytest.mark.parametrize("service_name", sorted(EXPECTED_SERVICES))
    def test_service_has_healthcheck(
        self, compose_config: dict[str, Any], service_name: str
    ) -> None:
        svc = compose_config["services"][service_name]
        assert "healthcheck" in svc, f"Service '{service_name}' missing healthcheck"
        hc = svc["healthcheck"]
        assert "test" in hc, f"Service '{service_name}' healthcheck missing 'test'"
        assert "interval" in hc or "retries" in hc, (
            f"Service '{service_name}' healthcheck should have interval or retries"
        )


class TestResourceLimits:
    """Every service must declare deploy.resources.limits (§30)."""

    @pytest.mark.parametrize("service_name", sorted(EXPECTED_SERVICES))
    def test_service_has_resource_limits(
        self, compose_config: dict[str, Any], service_name: str
    ) -> None:
        svc = compose_config["services"][service_name]
        deploy = svc.get("deploy", {})
        resources = deploy.get("resources", {})
        limits = resources.get("limits", {})
        assert "cpus" in limits, (
            f"Service '{service_name}' missing deploy.resources.limits.cpus"
        )
        assert "memory" in limits, (
            f"Service '{service_name}' missing deploy.resources.limits.memory"
        )

    def test_private_worker_limits(self, compose_config: dict[str, Any]) -> None:
        """private-worker gets remaining CPU (4) and up to 32 GB RAM (§30)."""
        limits = (
            compose_config["services"]["private-worker"]["deploy"]["resources"]["limits"]
        )
        cpus = float(limits["cpus"])
        assert cpus >= 4.0, f"private-worker cpus should be >= 4.0, got {cpus}"
        mem = str(limits["memory"]).upper().replace("B", "").replace("I", "")
        # Accept 32G, 32g, 32GB, etc.
        assert "32" in mem, (
            f"private-worker memory should be 32G, got {limits['memory']}"
        )


class TestExternalWorkerHealthEndpoint:
    """External worker /health must return enriched status (§28.5)."""

    @pytest.fixture()
    def client(self):  # noqa: ANN201
        from fastapi.testclient import TestClient

        from noa.external_worker.app import create_external_app

        app = create_external_app()
        return TestClient(app)

    def test_health_returns_status(self, client) -> None:  # noqa: ANN001
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] in ("ok", "degraded")

    def test_health_returns_uptime(self, client) -> None:  # noqa: ANN001
        resp = client.get("/health")
        body = resp.json()
        assert "uptime_seconds" in body
        assert isinstance(body["uptime_seconds"], (int, float))
        assert body["uptime_seconds"] >= 0

    def test_health_returns_version(self, client) -> None:  # noqa: ANN001
        resp = client.get("/health")
        body = resp.json()
        assert "version" in body
        assert body["version"] == "0.1.0"

    def test_health_ready_endpoint(self, client) -> None:  # noqa: ANN001
        resp = client.get("/health/ready")
        assert resp.status_code == 200
        body = resp.json()
        assert "ready" in body
        assert isinstance(body["ready"], bool)
