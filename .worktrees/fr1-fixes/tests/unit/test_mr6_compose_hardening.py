"""Tests for MR6: Docker Compose Hardening.

Validates that docker-compose.yml has proper healthchecks, resource limits,
container hardening flags, and dependency configuration per SPEC.md §7.1, §8.1.
"""

from __future__ import annotations

from pathlib import Path

import yaml

COMPOSE_PATH = Path(__file__).resolve().parents[2] / "docker-compose.yml"


def _load_compose() -> dict:
    return yaml.safe_load(COMPOSE_PATH.read_text())


# --- noa-api healthcheck ---


class TestNoaApiHealthcheck:
    def test_noa_api_has_healthcheck(self) -> None:
        compose = _load_compose()
        svc = compose["services"]["noa-api"]
        assert "healthcheck" in svc, "noa-api must define a healthcheck"

    def test_noa_api_healthcheck_uses_curl_health(self) -> None:
        compose = _load_compose()
        hc = compose["services"]["noa-api"]["healthcheck"]
        test_cmd = hc["test"]
        # Accept both string and list forms
        joined = " ".join(test_cmd) if isinstance(test_cmd, list) else test_cmd
        assert "curl" in joined, "healthcheck must use curl"
        assert "/health" in joined, "healthcheck must target /health"
        assert "localhost:8000" in joined, "healthcheck must target localhost:8000"

    def test_noa_api_healthcheck_timing(self) -> None:
        compose = _load_compose()
        hc = compose["services"]["noa-api"]["healthcheck"]
        assert hc.get("interval") == "10s"
        assert hc.get("timeout") == "5s"
        assert hc.get("retries") == 5
        assert hc.get("start_period") == "30s"


# --- private-worker healthcheck ---


class TestPrivateWorkerHealthcheck:
    def test_private_worker_has_healthcheck(self) -> None:
        compose = _load_compose()
        svc = compose["services"]["private-worker"]
        assert "healthcheck" in svc, "private-worker must define a healthcheck"

    def test_private_worker_healthcheck_uses_curl_health(self) -> None:
        compose = _load_compose()
        hc = compose["services"]["private-worker"]["healthcheck"]
        test_cmd = hc["test"]
        joined = " ".join(test_cmd) if isinstance(test_cmd, list) else test_cmd
        assert "curl" in joined
        assert "/health" in joined
        assert "localhost:8001" in joined


# --- Resource limits ---


class TestResourceLimits:
    def test_noa_api_cpu_limit(self) -> None:
        compose = _load_compose()
        deploy = compose["services"]["noa-api"]["deploy"]
        cpus = float(deploy["resources"]["limits"]["cpus"])
        assert cpus == 2.0

    def test_noa_api_memory_limit(self) -> None:
        compose = _load_compose()
        deploy = compose["services"]["noa-api"]["deploy"]
        assert deploy["resources"]["limits"]["memory"] == "2g"

    def test_external_worker_memory_limit(self) -> None:
        compose = _load_compose()
        deploy = compose["services"]["external-worker"]["deploy"]
        assert deploy["resources"]["limits"]["memory"] == "4g"

    def test_external_worker_cpu_limit(self) -> None:
        compose = _load_compose()
        deploy = compose["services"]["external-worker"]["deploy"]
        cpus = float(deploy["resources"]["limits"]["cpus"])
        assert cpus == 2.0

    def test_postgres_has_resource_limits(self) -> None:
        compose = _load_compose()
        deploy = compose["services"]["postgres"]["deploy"]
        limits = deploy["resources"]["limits"]
        assert float(limits["cpus"]) == 1.0
        assert limits["memory"] == "2g"


# --- noa-api hardening ---


class TestNoaApiHardening:
    def test_noa_api_read_only(self) -> None:
        compose = _load_compose()
        svc = compose["services"]["noa-api"]
        assert svc.get("read_only") is True

    def test_noa_api_cap_drop_all(self) -> None:
        compose = _load_compose()
        svc = compose["services"]["noa-api"]
        assert "ALL" in svc.get("cap_drop", [])

    def test_noa_api_security_opt(self) -> None:
        compose = _load_compose()
        svc = compose["services"]["noa-api"]
        assert "no-new-privileges:true" in svc.get("security_opt", [])

    def test_noa_api_tmpfs(self) -> None:
        compose = _load_compose()
        svc = compose["services"]["noa-api"]
        tmpfs = svc.get("tmpfs", [])
        tmpdir = "/tmp"  # noqa: S108
        found = any(tmpdir in entry for entry in tmpfs)
        assert found, "noa-api must have /tmp tmpfs mount"


# --- depends_on ---


class TestDependsOn:
    def test_noa_api_depends_on_private_worker_healthy(self) -> None:
        compose = _load_compose()
        deps = compose["services"]["noa-api"]["depends_on"]
        assert "private-worker" in deps
        assert deps["private-worker"]["condition"] == "service_healthy"
