"""Tests for project configuration — Phase F1.

Spec refs: SPEC.md §4.1, §7.1, §20.1
Phase plan: MASTER_PLAN.md Phase F1

These tests define the behavioral contract for project configuration,
Docker Compose structure, and package imports.
"""

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.f1

COMPOSE_PATH = Path(__file__).resolve().parents[2] / "docker-compose.yml"


class TestConfigLoading:
    """Configuration loading from environment variables."""

    def test_database_url_from_env(self, monkeypatch):
        """Config must accept DATABASE_URL from env."""
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://noa:secret@localhost:5432/noa",
        )
        from noa.config import Settings

        settings = Settings()
        assert settings.database_url == (
            "postgresql+asyncpg://noa:secret@localhost:5432/noa"
        )

    def test_defaults_applied_when_env_missing(self):
        """Config provides sensible defaults for all settings."""
        from noa.config import Settings

        settings = Settings()
        assert settings.api_host is not None
        assert settings.api_port is not None
        assert settings.log_level is not None

    def test_invalid_log_level_rejected(self):
        """Config validates values at startup — fail fast."""
        from noa.config import Settings

        with pytest.raises((ValueError, Exception)):
            Settings(log_level="INVALID_LEVEL")

    def test_secret_key_required_in_production(self, monkeypatch):
        """Secrets must not use defaults in production."""
        monkeypatch.setenv("NOA_ENV", "production")
        monkeypatch.delenv("SECRET_KEY", raising=False)
        from noa.config import Settings

        with pytest.raises((ValueError, Exception)):
            Settings()


class TestDockerComposeStructure:
    """Docker Compose structure per SPEC.md §7.1, §20.1."""

    @pytest.fixture()
    def compose_config(self):
        with open(COMPOSE_PATH) as f:
            return yaml.safe_load(f)

    def test_required_services_defined(self, compose_config):
        """Phase 1 requires all four services."""
        services = set(compose_config["services"].keys())
        required = {
            "noa-api", "postgres",
            "private-worker", "external-worker",
        }
        assert required.issubset(services), (
            f"Missing services: {required - services}"
        )

    def test_noa_internal_network_is_internal(self, compose_config):
        """noa-internal must have internal: true."""
        networks = compose_config["networks"]
        assert "noa-internal" in networks
        assert networks["noa-internal"].get("internal") is True

    def test_noa_external_network_exists(self, compose_config):
        """noa-external must exist for external worker."""
        networks = compose_config["networks"]
        assert "noa-external" in networks

    def test_private_worker_only_on_internal(self, compose_config):
        """Private container on noa-internal only."""
        pw = compose_config["services"]["private-worker"]
        nets = pw["networks"]
        if isinstance(nets, list):
            assert nets == ["noa-internal"]
        else:
            assert set(nets.keys()) == {"noa-internal"}

    def test_external_worker_only_on_external(self, compose_config):
        """External container on noa-external only."""
        ew = compose_config["services"]["external-worker"]
        nets = ew["networks"]
        if isinstance(nets, list):
            assert nets == ["noa-external"]
        else:
            assert set(nets.keys()) == {"noa-external"}

    def test_noa_api_bridges_both_networks(self, compose_config):
        """Noa API spans both networks (gateway)."""
        nets = compose_config["services"]["noa-api"]["networks"]
        if isinstance(nets, list):
            assert "noa-internal" in nets
            assert "noa-external" in nets
        else:
            assert "noa-internal" in nets
            assert "noa-external" in nets

    def test_noa_api_binds_to_localhost_only(self, compose_config):
        """API binds to 127.0.0.1, never 0.0.0.0."""
        ports = compose_config["services"]["noa-api"].get("ports", [])
        for port in ports:
            port_str = str(port)
            assert "0.0.0.0" not in port_str, (  # noqa: S104
                f"API must not bind to 0.0.0.0: {port_str}"
            )

    def test_postgres_only_on_internal(self, compose_config):
        """Postgres only accessible from internal network."""
        pg = compose_config["services"]["postgres"]
        nets = pg["networks"]
        if isinstance(nets, list):
            assert nets == ["noa-internal"]
        else:
            assert set(nets.keys()) == {"noa-internal"}


class TestContainerHardening:
    """Container hardening per SPEC.md §8.1 and §8.2."""

    @pytest.fixture()
    def compose_config(self):
        with open(COMPOSE_PATH) as f:
            return yaml.safe_load(f)

    def test_private_worker_read_only_filesystem(self, compose_config):
        """Private container must have read-only root fs."""
        pw = compose_config["services"]["private-worker"]
        assert pw.get("read_only") is True

    def test_private_worker_drops_all_caps(self, compose_config):
        """Private container must drop all capabilities."""
        pw = compose_config["services"]["private-worker"]
        cap_drop = pw.get("cap_drop", [])
        assert "ALL" in cap_drop

    def test_external_worker_read_only_filesystem(self, compose_config):
        """External container must have read-only root fs."""
        ew = compose_config["services"]["external-worker"]
        assert ew.get("read_only") is True


class TestPackageImports:
    """Package structure is importable."""

    def test_noa_package_importable(self):
        """src/noa/ package must be importable."""
        import noa  # noqa: F401

    def test_config_module_importable(self):
        """Config module must be importable."""
        from noa.config import Settings  # noqa: F401
