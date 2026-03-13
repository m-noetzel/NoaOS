"""DE4: Backup Verification Automation tests.

Covers:
  - GET /health/backup: status ok / failed / never_run / stale
  - All cases return HTTP 200
  - verify_backup.sh: finds most recent .gpg by mtime
  - verify_backup.sh: exits non-zero on pg_restore failure
  - verify_backup.sh: writes verify_status.json with timestamp on success
  - verify_backup.sh: writes status=failed on restore failure
  - Dockerfile cron: 0 3 * * 0 weekly schedule
  - docker-compose: noa-api mounts backups read-only
  - Schema check: verify script checks table presence
  - Health endpoint: backup_age_hours field; >25h triggers stale
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parents[2]
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"
BACKUP_DOCKERFILE = REPO_ROOT / "docker" / "backup" / "Dockerfile"
VERIFY_SCRIPT = REPO_ROOT / "docker" / "backup" / "verify_backup.sh"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def compose() -> dict[str, Any]:
    raw = COMPOSE_PATH.read_text()
    data: dict[str, Any] = yaml.safe_load(raw)
    return data


@pytest.fixture
def client(tmp_path, monkeypatch):
    """FastAPI test client with verify status path overridden."""
    import noa.api.v1.health as health_mod

    monkeypatch.setattr(
        health_mod, "_VERIFY_STATUS_PATH", tmp_path / "verify_status.json"
    )

    from noa.api.app import create_app

    app = create_app()
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Health endpoint tests
# ---------------------------------------------------------------------------


class TestBackupHealthEndpoint:
    def _status_file(self, client) -> Path:
        """Retrieve the path currently used by the test client's health module."""
        import noa.api.v1.health as health_mod

        return health_mod._VERIFY_STATUS_PATH

    def test_never_run_when_file_absent(self, client):
        """Returns status=never_run and HTTP 200 when file does not exist."""
        resp = client.get("/health/backup")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "never_run"
        assert data["last_backup"] is None
        assert data["last_verify"] is None
        assert data["backup_age_hours"] is None

    def test_ok_status_when_verify_passed(self, client):
        """Returns status=ok when verify_status.json reports ok."""
        path = self._status_file(client)
        now = datetime.now(tz=UTC)
        path.write_text(
            json.dumps({
                "status": "ok",
                "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "backup_file": "/backups/noa_2026-03-12.sql.gz.gpg",
                "error": "",
            })
        )
        resp = client.get("/health/backup")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "ok"
        assert data["last_backup"] == "/backups/noa_2026-03-12.sql.gz.gpg"
        assert data["last_verify"] is not None
        assert data["backup_age_hours"] is not None

    def test_failed_status_when_verify_failed(self, client):
        """Returns status=failed when verify_status.json reports failure."""
        path = self._status_file(client)
        now = datetime.now(tz=UTC)
        path.write_text(
            json.dumps({
                "status": "failed",
                "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "backup_file": "/backups/noa_2026-03-12.sql.gz.gpg",
                "error": "pg_restore exited with code 1",
            })
        )
        resp = client.get("/health/backup")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "failed"
        assert "error" in data

    def test_http_200_in_all_cases(self, client):
        """All cases (ok, failed, never_run) return HTTP 200."""
        path = self._status_file(client)

        # never_run
        assert client.get("/health/backup").status_code == 200

        # ok
        path.write_text(json.dumps({
            "status": "ok",
            "timestamp": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "backup_file": "/backups/noa_2026.sql.gz.gpg",
            "error": "",
        }))
        assert client.get("/health/backup").status_code == 200

        # failed
        path.write_text(json.dumps({
            "status": "failed",
            "timestamp": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "backup_file": "",
            "error": "decrypt failed",
        }))
        assert client.get("/health/backup").status_code == 200

    def test_stale_when_backup_age_exceeds_25h(self, client):
        """Returns status=stale when ok but backup verify is older than 25 hours."""
        path = self._status_file(client)
        old_ts = datetime.now(tz=UTC) - timedelta(hours=26)
        path.write_text(
            json.dumps({
                "status": "ok",
                "timestamp": old_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "backup_file": "/backups/noa_old.sql.gz.gpg",
                "error": "",
            })
        )
        resp = client.get("/health/backup")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "stale"
        assert data["backup_age_hours"] is not None
        assert data["backup_age_hours"] > 25.0

    def test_backup_age_hours_present_in_response(self, client):
        """backup_age_hours field is always present in the response data."""
        path = self._status_file(client)
        now = datetime.now(tz=UTC)
        path.write_text(
            json.dumps({
                "status": "ok",
                "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "backup_file": "/backups/noa_2026.sql.gz.gpg",
                "error": "",
            })
        )
        resp = client.get("/health/backup")
        data = resp.json()["data"]
        assert "backup_age_hours" in data
        assert isinstance(data["backup_age_hours"], (int, float))

    def test_corrupted_json_returns_failed(self, client):
        """Returns status=failed when verify_status.json is corrupt."""
        path = self._status_file(client)
        path.write_text("{ invalid json }")
        resp = client.get("/health/backup")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "failed"


# ---------------------------------------------------------------------------
# verify_backup.sh script content tests
# ---------------------------------------------------------------------------


class TestVerifyBackupScript:
    def test_script_exists(self):
        """verify_backup.sh exists in docker/backup/."""
        assert VERIFY_SCRIPT.exists(), f"Script not found: {VERIFY_SCRIPT}"

    def test_script_finds_gpg_by_mtime(self):
        """Script uses ls -1t to find the most recent .gpg file by mtime."""
        content = VERIFY_SCRIPT.read_text()
        # Must sort by mtime (ls -1t) and pick the latest
        assert "ls -1t" in content, "Script must use 'ls -1t' for mtime-based sorting"
        assert ".gpg" in content, "Script must filter for .gpg files"
        assert "head -1" in content, "Script must take the first (most recent) result"

    def test_script_exits_nonzero_on_pg_restore_failure(self):
        """Script exits non-zero (set -e / explicit exit 1) when restore fails."""
        content = VERIFY_SCRIPT.read_text()
        # set -euo pipefail ensures non-zero exit propagates
        assert "set -euo pipefail" in content, "Script must use 'set -euo pipefail'"
        # Also check for explicit exit 1 on errors
        assert "exit 1" in content, "Script must have explicit 'exit 1' on errors"

    def test_script_writes_timestamp_on_success(self):
        """Script writes a timestamp field to verify_status.json on success."""
        content = VERIFY_SCRIPT.read_text()
        assert '"timestamp"' in content, "Script must write 'timestamp' field to JSON"
        assert "verify_status.json" in content, (
            "Script must write to verify_status.json"
        )

    def test_script_writes_failed_status_on_restore_failure(self):
        """Script writes status=failed to verify_status.json on restore failure."""
        content = VERIFY_SCRIPT.read_text()
        assert '"failed"' in content, "Script must write status 'failed'"
        # Ensure the write_status helper is called with "failed"
        assert 'write_status "failed"' in content, (
            "Script must call write_status with 'failed' on error"
        )

    def test_script_includes_schema_table_count_check(self):
        """Script checks expected tables exist (not just pg_restore exit code)."""
        content = VERIFY_SCRIPT.read_text()
        # Must check information_schema.tables or a per-table COUNT
        assert "information_schema" in content or "table_name" in content, (
            "Script must verify table presence via information_schema or explicit check"
        )
        # Must check multiple expected tables
        expected = ["users", "threads", "messages"]
        for table in expected:
            assert table in content, f"Script must check for table '{table}'"

    def test_script_is_executable_bash(self):
        """Script has a bash shebang."""
        content = VERIFY_SCRIPT.read_text()
        first_line = content.splitlines()[0]
        assert "bash" in first_line, f"Script must have bash shebang, got: {first_line}"

    def test_script_writes_backup_file_to_status(self):
        """Script records the verified backup file path in verify_status.json."""
        content = VERIFY_SCRIPT.read_text()
        assert '"backup_file"' in content, (
            "Script must record backup_file in status JSON"
        )


# ---------------------------------------------------------------------------
# Dockerfile cron schedule test
# ---------------------------------------------------------------------------


class TestBackupDockerfile:
    def test_cron_weekly_schedule_present(self):
        """Dockerfile adds weekly verify cron: 0 3 * * 0."""
        content = BACKUP_DOCKERFILE.read_text()
        assert "0 3 * * 0" in content, (
            "Dockerfile must include weekly cron '0 3 * * 0' for verify_backup.sh"
        )

    def test_verify_script_copied_in_dockerfile(self):
        """Dockerfile COPYs verify_backup.sh into the image."""
        content = BACKUP_DOCKERFILE.read_text()
        assert "verify_backup.sh" in content, (
            "Dockerfile must COPY verify_backup.sh"
        )


# ---------------------------------------------------------------------------
# docker-compose.yml tests
# ---------------------------------------------------------------------------


class TestDockerComposeMounts:
    def test_noa_api_mounts_backups_readonly(self, compose):
        """noa-api service mounts the backups volume as read-only."""
        api_service = compose["services"]["noa-api"]
        volumes = api_service.get("volumes", [])
        # Look for the backups mount in any format
        backup_mounts = [v for v in volumes if "backups" in str(v)]
        assert backup_mounts, "noa-api must mount the backups volume"
        # Check it is read-only
        backup_mount_str = str(backup_mounts[0])
        assert ":ro" in backup_mount_str, (
            f"noa-api backups mount must be read-only (:ro), got: {backup_mount_str}"
        )

    def test_backups_volume_defined(self, compose):
        """backups named volume is defined in docker-compose volumes section."""
        volumes = compose.get("volumes", {})
        assert "backups" in volumes, "docker-compose must define 'backups' named volume"

    def test_backup_service_mounts_backups_volume(self, compose):
        """backup service mounts the backups volume (writable)."""
        backup_service = compose["services"]["backup"]
        volumes = backup_service.get("volumes", [])
        backup_mounts = [v for v in volumes if "backups" in str(v)]
        assert backup_mounts, "backup service must mount the backups volume"
