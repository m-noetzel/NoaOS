"""Tests for Phase CM2: macOS Keychain Bootstrap & Env Var Overrides.

Covers: config.py env var API key fields, service env-var-overrides-DB
fallback, keychain_store.sh format, keychain_bootstrap.sh output format.

Spec refs: SPEC.md §11.1, §11.2
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.cm2

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"


# ---------------------------------------------------------------------------
# Config: env var API key fields
# ---------------------------------------------------------------------------

class TestConfigApiKeyEnvVars:
    """Config.py should accept API key env vars."""

    def test_anthropic_key_from_env(self, monkeypatch):
        monkeypatch.setenv("NOA_ENV", "testing")
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///test.db")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-from-env")
        from noa.config import Settings

        s = Settings()
        assert s.anthropic_api_key == "sk-ant-from-env"

    def test_openai_key_from_env(self, monkeypatch):
        monkeypatch.setenv("NOA_ENV", "testing")
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///test.db")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-from-env")
        from noa.config import Settings

        s = Settings()
        assert s.openai_api_key == "sk-openai-from-env"

    def test_all_key_fields_default_none(self, monkeypatch):
        monkeypatch.setenv("NOA_ENV", "testing")
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///test.db")
        # Clear any existing env vars
        for key in (
            "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_CLIENT_ID",
            "GOOGLE_CLIENT_SECRET", "NOTION_TOKEN", "TAVILY_API_KEY",
        ):
            monkeypatch.delenv(key, raising=False)
        from noa.config import Settings

        s = Settings()
        assert s.anthropic_api_key is None
        assert s.openai_api_key is None
        assert s.google_client_id is None
        assert s.google_client_secret is None  # noqa: S105
        assert s.notion_token is None
        assert s.tavily_api_key is None

    def test_ollama_base_url_from_env(self, monkeypatch):
        monkeypatch.setenv("NOA_ENV", "testing")
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///test.db")
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        from noa.config import Settings

        s = Settings()
        assert s.ollama_base_url == "http://localhost:11434"


# ---------------------------------------------------------------------------
# Service: env var overrides DB
# ---------------------------------------------------------------------------

class TestServiceEnvVarOverride:
    """SettingsService.get_effective_key checks env first, then DB."""

    def test_env_overrides_db_value(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-env")
        from noa.settings.service import SettingsService

        result = SettingsService.get_effective_key(
            "anthropic_api_key", db_value="sk-from-db",
        )
        assert result == "sk-from-env"

    def test_missing_env_falls_back_to_db(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from noa.settings.service import SettingsService

        result = SettingsService.get_effective_key(
            "anthropic_api_key", db_value="sk-from-db",
        )
        assert result == "sk-from-db"

    def test_empty_env_falls_back_to_db(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        from noa.settings.service import SettingsService

        result = SettingsService.get_effective_key(
            "anthropic_api_key", db_value="sk-from-db",
        )
        assert result == "sk-from-db"

    def test_no_env_no_db_returns_none(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from noa.settings.service import SettingsService

        result = SettingsService.get_effective_key(
            "anthropic_api_key", db_value=None,
        )
        assert result is None


# ---------------------------------------------------------------------------
# Shell scripts: format validation
# ---------------------------------------------------------------------------

class TestKeychainStoreScript:
    """Validate keychain_store.sh exists and has correct structure."""

    def test_script_exists(self):
        script = TOOLS_DIR / "keychain_store.sh"
        assert script.exists(), "tools/keychain_store.sh must exist"

    def test_script_is_executable(self):
        script = TOOLS_DIR / "keychain_store.sh"
        assert os.access(script, os.X_OK), "keychain_store.sh must be executable"

    def test_script_has_set_get_delete_commands(self):
        script = TOOLS_DIR / "keychain_store.sh"
        content = script.read_text()
        assert "set)" in content or "set\"" in content, "Must support 'set' command"
        assert "get)" in content or "get\"" in content, "Must support 'get' command"
        assert (
            "delete)" in content or "delete\"" in content
        ), "Must support 'delete' command"


class TestKeychainBootstrapScript:
    """Validate keychain_bootstrap.sh exists and generates env file format."""

    def test_script_exists(self):
        script = TOOLS_DIR / "keychain_bootstrap.sh"
        assert script.exists(), "tools/keychain_bootstrap.sh must exist"

    def test_script_is_executable(self):
        script = TOOLS_DIR / "keychain_bootstrap.sh"
        assert os.access(script, os.X_OK), "keychain_bootstrap.sh must be executable"

    def test_script_references_env_secrets_file(self):
        script = TOOLS_DIR / "keychain_bootstrap.sh"
        content = script.read_text()
        assert ".env.secrets" in content, "Must reference .env.secrets output file"


# ---------------------------------------------------------------------------
# Docker compose: env_file wiring
# ---------------------------------------------------------------------------

class TestDockerComposeSecrets:
    """docker-compose.yml should reference .env.secrets."""

    def test_env_file_referenced(self):
        compose = Path(__file__).resolve().parents[2] / "docker-compose.yml"
        content = compose.read_text()
        assert ".env.secrets" in content, (
            "docker-compose.yml must reference .env.secrets"
        )


# ---------------------------------------------------------------------------
# .gitignore: .env.secrets excluded
# ---------------------------------------------------------------------------

class TestGitignoreSecrets:
    """.env.secrets must be in .gitignore."""

    def test_env_secrets_in_gitignore(self):
        gitignore = Path(__file__).resolve().parents[2] / ".gitignore"
        content = gitignore.read_text()
        assert ".env.secrets" in content, (
            ".env.secrets must be listed in .gitignore"
        )
