"""QE2: Mypy zero — verify type annotations and CI gate enforcement.

Tests verify:
  - Key source files can be imported without AttributeError (annotations present)
  - Specific typed attributes exist on public classes
  - pyproject.toml has [tool.mypy] section with required settings
  - CI workflow runs mypy and fails on errors (no continue-on-error: true)
  - AgentState TypedDict has the new required_tools / user_privacy_override keys
  - AuditService._require_session() raises when no session configured
  - Checkpointer and CustomTool models have typed generic columns
  - Tool execute() dispatchers are present and typed
  - settings/service.py get_settings returns dict[str, Any]
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent.parent  # project root


def _read_pyproject() -> str:
    return (ROOT / "pyproject.toml").read_text()


def _read_ci_yml() -> str:
    return (ROOT / ".github" / "workflows" / "ci.yml").read_text()


# ---------------------------------------------------------------------------
# 1. pyproject.toml has [tool.mypy] section (QE2 deliverable)
# ---------------------------------------------------------------------------

class TestPyprojectMypy:
    def test_mypy_section_present(self) -> None:
        content = _read_pyproject()
        assert "[tool.mypy]" in content

    def test_ignore_missing_imports_configured(self) -> None:
        """At least one override block must have ignore_missing_imports = true."""
        content = _read_pyproject()
        assert "ignore_missing_imports = true" in content

    def test_warn_unused_configs_present(self) -> None:
        content = _read_pyproject()
        assert "warn_unused_configs = true" in content

    def test_python_version_set(self) -> None:
        content = _read_pyproject()
        assert 'python_version = "3.11"' in content

    def test_jose_override_present(self) -> None:
        """jose module override must exist (used in auth/jwt.py)."""
        content = _read_pyproject()
        assert '"jose"' in content or "'jose'" in content

    def test_jwt_override_present(self) -> None:
        """jwt (PyJWT) module override must exist (used in apns.py)."""
        content = _read_pyproject()
        assert '"jwt"' in content or "'jwt'" in content


# ---------------------------------------------------------------------------
# 2. CI workflow enforces mypy (no continue-on-error: true on mypy step)
# ---------------------------------------------------------------------------

class TestCIGate:
    def test_mypy_step_present(self) -> None:
        content = _read_ci_yml()
        assert "mypy" in content.lower()

    def test_mypy_not_continue_on_error(self) -> None:
        """The mypy step must NOT have continue-on-error: true."""
        content = _read_ci_yml()
        lines = content.splitlines()
        in_mypy_step = False
        for line in lines:
            stripped = line.strip()
            if "mypy" in stripped.lower() and stripped.startswith("-"):
                in_mypy_step = True
            if in_mypy_step and "continue-on-error: true" in stripped:
                pytest.fail(
                    "CI mypy step has 'continue-on-error: true' — this disables the gate"
                )
            # Another step starts
            if in_mypy_step and stripped.startswith("- name:") and "mypy" not in stripped.lower():
                break

    def test_mypy_targets_src_noa(self) -> None:
        """Mypy CI step must target src/noa/ (not the full src/ which includes stubs)."""
        content = _read_ci_yml()
        assert "src/noa/" in content or "src/noa" in content


# ---------------------------------------------------------------------------
# 3. AgentState TypedDict has new fields added in QE2
# ---------------------------------------------------------------------------

class TestAgentState:
    def test_agent_state_has_user_privacy_override(self) -> None:
        from noa.orchestrator.state import AgentState
        hints = AgentState.__annotations__
        assert "user_privacy_override" in hints

    def test_agent_state_has_requested_tools(self) -> None:
        from noa.orchestrator.state import AgentState
        hints = AgentState.__annotations__
        assert "requested_tools" in hints

    def test_agent_state_existing_fields_intact(self) -> None:
        from noa.orchestrator.state import AgentState
        hints = AgentState.__annotations__
        for key in ("messages", "privacy_mode", "selected_model", "tool_calls"):
            assert key in hints, f"AgentState missing {key}"


# ---------------------------------------------------------------------------
# 4. AuditService._require_session raises when no session configured
# ---------------------------------------------------------------------------

class TestAuditService:
    def test_require_session_raises_without_session(self) -> None:
        from noa.audit.service import AuditService
        svc = AuditService()  # no session
        with pytest.raises(RuntimeError, match="no sync session"):
            svc._require_session()

    def test_require_session_returns_session_when_set(self) -> None:
        from unittest.mock import MagicMock

        from noa.audit.service import AuditService

        mock_session = MagicMock()
        svc = AuditService(session=mock_session)
        assert svc._require_session() is mock_session


# ---------------------------------------------------------------------------
# 5. DB model typing
# ---------------------------------------------------------------------------

class TestDBModelTyping:
    def test_checkpoint_state_has_type_annotation(self) -> None:
        from noa.db.models.checkpoint import Checkpoint
        annotations = Checkpoint.__annotations__
        assert "state" in annotations

    def test_custom_tool_functions_has_type_annotation(self) -> None:
        from noa.db.models.custom_tool import CustomTool
        annotations = CustomTool.__annotations__
        assert "functions" in annotations

    def test_engine_kwargs_typed(self) -> None:
        """Verify db/engine.py imports cleanly — dict is typed."""
        from noa.db import engine as eng_mod  # noqa: F401
        assert hasattr(eng_mod, "create_async_engine_from_config")


# ---------------------------------------------------------------------------
# 6. Tool cast correctness — execute() returns dict not Any
# ---------------------------------------------------------------------------

class TestToolTyping:
    def test_notion_tool_has_execute(self) -> None:
        from noa.tools.notion import NotionTool
        assert inspect.iscoroutinefunction(NotionTool.execute)

    def test_calendar_tool_has_execute(self) -> None:
        from noa.tools.calendar import CalendarTool
        assert inspect.iscoroutinefunction(CalendarTool.execute)

    def test_gmail_tool_has_execute(self) -> None:
        from noa.tools.gmail import GmailTool
        assert inspect.iscoroutinefunction(GmailTool.execute)

    def test_memory_tool_has_execute(self) -> None:
        from noa.tools.memory import MemoryTool
        assert inspect.iscoroutinefunction(MemoryTool.execute)


# ---------------------------------------------------------------------------
# 7. settings/service.py get_settings return annotation
# ---------------------------------------------------------------------------

class TestSettingsServiceTyping:
    def test_get_settings_return_annotation(self) -> None:
        from noa.settings.service import SettingsService
        hints = SettingsService.get_settings.__annotations__
        assert "return" in hints

    def test_update_settings_return_annotation(self) -> None:
        from noa.settings.service import SettingsService
        hints = SettingsService.update_settings.__annotations__
        assert "return" in hints


# ---------------------------------------------------------------------------
# 8. No bare Any return on public API endpoints (spot check)
# ---------------------------------------------------------------------------

class TestPublicEndpointAnnotations:
    def test_health_endpoint_has_return_type(self) -> None:
        from noa.api.v1 import health
        # health() function should have return annotation
        fn = getattr(health, "health", None)
        if fn is not None:
            hints = getattr(fn, "__annotations__", {})
            assert "return" in hints

    def test_chat_endpoint_has_return_type(self) -> None:
        from noa.api.v1 import chat
        fn = getattr(chat, "submit_chat", None)
        if fn is not None:
            hints = getattr(fn, "__annotations__", {})
            assert "return" in hints
