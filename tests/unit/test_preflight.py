"""Tests for Noa pre-flight checks — SPEC.md §30, §31.

All tests are self-contained: no Docker or real environment required.
We mock environment variables and subprocess calls.
"""

from __future__ import annotations

import subprocess
from unittest.mock import patch

from scripts.preflight import check_docker, check_env_vars, check_volumes, run_preflight

# ---------------------------------------------------------------------------
# check_env_vars
# ---------------------------------------------------------------------------


class TestCheckEnvVars:
    """Validate required env-var checking."""

    def test_all_required_vars_present(self) -> None:
        env = {
            "DATABASE_URL": "postgresql+asyncpg://noa:noa@postgres:5432/noa",
            "JWT_SECRET": "supersecret",
            "BACKUP_PASSPHRASE": "hunter2",
        }
        with patch.dict("os.environ", env, clear=True):
            errors = check_env_vars()
        assert errors == []

    def test_missing_all_required_vars(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            errors = check_env_vars()
        assert len(errors) == 3
        assert any("DATABASE_URL" in e for e in errors)
        assert any("JWT_SECRET" in e for e in errors)
        assert any("BACKUP_PASSPHRASE" in e for e in errors)

    def test_missing_single_required_var(self) -> None:
        env = {
            "DATABASE_URL": "postgresql+asyncpg://noa:noa@postgres:5432/noa",
            "BACKUP_PASSPHRASE": "hunter2",
        }
        with patch.dict("os.environ", env, clear=True):
            errors = check_env_vars()
        assert len(errors) == 1
        assert "JWT_SECRET" in errors[0]

    def test_optional_vars_not_required(self) -> None:
        """Optional vars (API keys) should produce warnings, not errors."""
        env = {
            "DATABASE_URL": "postgresql+asyncpg://noa:noa@postgres:5432/noa",
            "JWT_SECRET": "supersecret",
            "BACKUP_PASSPHRASE": "hunter2",
        }
        with patch.dict("os.environ", env, clear=True):
            errors = check_env_vars()
        # No errors even without ANTHROPIC_API_KEY etc.
        assert errors == []


# ---------------------------------------------------------------------------
# check_docker
# ---------------------------------------------------------------------------


class TestCheckDocker:
    """Validate Docker prerequisite checks."""

    def test_docker_compose_available(self) -> None:
        """When docker compose version succeeds, no errors."""
        mock_result = subprocess.CompletedProcess(
            args=["docker", "compose", "version"],
            returncode=0,
            stdout="Docker Compose version v2.24.0\n",
            stderr="",
        )
        with patch("subprocess.run", return_value=mock_result):
            errors = check_docker()
        assert errors == []

    def test_docker_compose_not_found(self) -> None:
        """When docker compose version fails, report error."""
        with patch(
            "subprocess.run",
            side_effect=FileNotFoundError("docker not found"),
        ):
            errors = check_docker()
        assert len(errors) >= 1
        assert any("docker" in e.lower() for e in errors)

    def test_docker_compose_returns_error(self) -> None:
        """Non-zero exit from docker compose version is an error."""
        mock_result = subprocess.CompletedProcess(
            args=["docker", "compose", "version"],
            returncode=1,
            stdout="",
            stderr="unknown command",
        )
        with patch("subprocess.run", return_value=mock_result):
            errors = check_docker()
        assert len(errors) >= 1


# ---------------------------------------------------------------------------
# check_volumes
# ---------------------------------------------------------------------------


class TestCheckVolumes:
    """Validate Docker volume checks."""

    def test_all_volumes_exist(self) -> None:
        mock_result = subprocess.CompletedProcess(
            args=["docker", "volume", "ls", "--format", "{{.Name}}"],
            returncode=0,
            stdout="noa_postgres-data\nnoa_private-data\nnoa_backups\n",
            stderr="",
        )
        with patch("subprocess.run", return_value=mock_result):
            errors = check_volumes()
        assert errors == []

    def test_docker_not_available_for_volumes(self) -> None:
        with patch(
            "subprocess.run",
            side_effect=FileNotFoundError("docker not found"),
        ):
            errors = check_volumes()
        assert len(errors) >= 1


# ---------------------------------------------------------------------------
# run_preflight
# ---------------------------------------------------------------------------


class TestRunPreflight:
    """Integration of all preflight checks."""

    def test_all_pass(self) -> None:
        env = {
            "DATABASE_URL": "postgresql+asyncpg://noa:noa@postgres:5432/noa",
            "JWT_SECRET": "supersecret",
            "BACKUP_PASSPHRASE": "hunter2",
        }
        docker_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Docker Compose version v2.24.0\n", stderr=""
        )
        volume_result = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="noa_postgres-data\nnoa_private-data\nnoa_backups\n",
            stderr="",
        )
        with (
            patch.dict("os.environ", env, clear=True),
            patch("subprocess.run", side_effect=[docker_result, volume_result]),
        ):
            ok, errors = run_preflight()
        assert ok is True
        assert errors == []

    def test_env_failure_propagates(self) -> None:
        docker_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Docker Compose version v2.24.0\n", stderr=""
        )
        volume_result = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="noa_postgres-data\nnoa_private-data\nnoa_backups\n",
            stderr="",
        )
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("subprocess.run", side_effect=[docker_result, volume_result]),
        ):
            ok, errors = run_preflight()
        assert ok is False
        assert len(errors) >= 1
