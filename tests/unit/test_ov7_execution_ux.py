"""OV7: Tests for Execution Task UX + Google Token Refresh.

Findings resolved: UX-EX1 (Medium), BE-AP3 (Medium), BE-AP1 (High).

Test plan:
- UX-EX1: Execution tasks get execution-specific system prompt guidance
- UX-EX1: Non-execution tasks don't get the execution prompt
- UX-EX1: Execution prompt injected when no system message exists
- BE-AP3: invalid_grant / auth error on refresh returns friendly error dict
- BE-AP3: Token reload from DB is attempted before Gmail API calls
- BE-AP3: Token reload from DB is attempted before Calendar API calls
- BE-AP3: Successful API call works normally (no regression)
- BE-AP1: Run summary is updated after approval resume
- BE-AP1: Summary update failure is swallowed (best-effort)
- Integration: agent_node with execution task has guidance in system message
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest  # noqa: I001

# ---------------------------------------------------------------------------
# UX-EX1: Execution task system prompt injection
# ---------------------------------------------------------------------------


class TestExecutionTaskPrompt:
    """UX-EX1: agent_node injects execution-specific guidance for execution tasks."""

    @pytest.mark.asyncio
    async def test_execution_task_gets_execution_prompt(self) -> None:
        """Execution task state results in execution guidance in system message."""
        from noa.orchestrator.nodes.agent import agent_node

        captured_messages: list[list[dict[str, Any]]] = []

        async def mock_invoke_llm(
            model: str,
            messages: list[dict[str, Any]],
            *,
            privacy_mode: str = "external",
            max_tokens: int = 4096,
            tools: list[dict[str, Any]] | None = None,
            temperature: float | None = None,
        ) -> Any:
            captured_messages.append(messages)
            mock_resp = MagicMock()
            mock_resp.content = "Email sent successfully."
            mock_resp.tool_calls = []
            mock_resp.usage = {}
            mock_resp.provider = ""
            mock_resp.model = ""
            return mock_resp

        state: dict[str, Any] = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Send the email"},
            ],
            "task_type": "execution",
            "selected_model": "openai/gpt-4.1",
            "privacy_mode": "external",
            "available_tools": [],
            "max_tokens": 1024,
            "llm_usage": [],
            "thoughts": [],
            "use_react": False,
            "plan": None,
            "token_callback": None,
        }

        with patch(
            "noa.orchestrator.nodes.agent.invoke_llm", side_effect=mock_invoke_llm
        ):
            result = await agent_node(state)

        assert captured_messages, "LLM was not called"
        system_msgs = [
            m for m in captured_messages[0] if m.get("role") == "system"
        ]
        assert system_msgs, "No system message found"
        system_content = system_msgs[0]["content"]
        assert "execution tasks" in system_content.lower() or "execution" in system_content
        assert "actual result data" in system_content or "show what was done" in system_content
        assert result is not None

    @pytest.mark.asyncio
    async def test_non_execution_task_no_execution_prompt(self) -> None:
        """Non-execution tasks do not get the execution-specific guidance."""
        from noa.orchestrator.nodes.agent import agent_node

        captured_messages: list[list[dict[str, Any]]] = []

        async def mock_invoke_llm(
            model: str,
            messages: list[dict[str, Any]],
            *,
            privacy_mode: str = "external",
            max_tokens: int = 4096,
            tools: list[dict[str, Any]] | None = None,
            temperature: float | None = None,
        ) -> Any:
            captured_messages.append(messages)
            mock_resp = MagicMock()
            mock_resp.content = "The weather is sunny."
            mock_resp.tool_calls = []
            mock_resp.usage = {}
            mock_resp.provider = ""
            mock_resp.model = ""
            return mock_resp

        state: dict[str, Any] = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is the weather?"},
            ],
            "task_type": "informational",
            "selected_model": "openai/gpt-4.1",
            "privacy_mode": "external",
            "available_tools": [],
            "max_tokens": 1024,
            "llm_usage": [],
            "thoughts": [],
            "use_react": False,
            "plan": None,
            "token_callback": None,
        }

        with patch(
            "noa.orchestrator.nodes.agent.invoke_llm", side_effect=mock_invoke_llm
        ):
            await agent_node(state)

        assert captured_messages, "LLM was not called"
        system_msgs = [
            m for m in captured_messages[0] if m.get("role") == "system"
        ]
        # System message content should NOT contain execution-specific guidance
        if system_msgs:
            system_content = system_msgs[0]["content"]
            assert "For execution tasks:" not in system_content

    @pytest.mark.asyncio
    async def test_execution_prompt_injected_without_system_message(self) -> None:
        """Execution prompt is added as a new system message when none exists."""
        from noa.orchestrator.nodes.agent import agent_node

        captured_messages: list[list[dict[str, Any]]] = []

        async def mock_invoke_llm(
            model: str,
            messages: list[dict[str, Any]],
            *,
            privacy_mode: str = "external",
            max_tokens: int = 4096,
            tools: list[dict[str, Any]] | None = None,
            temperature: float | None = None,
        ) -> Any:
            captured_messages.append(messages)
            mock_resp = MagicMock()
            mock_resp.content = "Done."
            mock_resp.tool_calls = []
            mock_resp.usage = {}
            mock_resp.provider = ""
            mock_resp.model = ""
            return mock_resp

        state: dict[str, Any] = {
            "messages": [
                {"role": "user", "content": "Create a calendar event"},
            ],
            "task_type": "execution",
            "selected_model": "openai/gpt-4.1",
            "privacy_mode": "external",
            "available_tools": [],
            "max_tokens": 1024,
            "llm_usage": [],
            "thoughts": [],
            "use_react": False,
            "plan": None,
            "token_callback": None,
        }

        with patch(
            "noa.orchestrator.nodes.agent.invoke_llm", side_effect=mock_invoke_llm
        ):
            await agent_node(state)

        assert captured_messages, "LLM was not called"
        system_msgs = [
            m for m in captured_messages[0] if m.get("role") == "system"
        ]
        assert system_msgs, "No system message was injected for execution task"
        system_content = system_msgs[0]["content"]
        assert "execution" in system_content.lower()


# ---------------------------------------------------------------------------
# BE-AP3: Google token refresh — invalid_grant returns friendly error
# ---------------------------------------------------------------------------


class TestGoogleTokenRefresh:
    """BE-AP3: Google clients return friendly error on auth failure."""

    @pytest.mark.asyncio
    async def test_gmail_client_invalid_grant_returns_friendly_error(self) -> None:
        """GmailClient._safe_request returns reconnect error dict on GoogleAuthError."""
        from noa.tools.google_auth import GoogleAuthClient, GoogleAuthError
        from noa.tools.google_gmail_client import _GOOGLE_RECONNECT_ERROR, GmailClient

        auth = MagicMock(spec=GoogleAuthClient)
        auth.access_token = "tok"
        auth.refresh_access_token = AsyncMock(
            side_effect=GoogleAuthError("Token refresh failed: 400")
        )
        client = GmailClient(auth_client=auth)

        # Simulate 401 response → refresh fails with GoogleAuthError
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient") as mock_http:
            mock_http.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await client._safe_request("get", "https://example.com")

        assert result == _GOOGLE_RECONNECT_ERROR
        assert "error" in result
        assert "re-connect" in result["error"].lower() or "reconnect" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_calendar_client_invalid_grant_returns_friendly_error(self) -> None:
        """GoogleCalendarClient._safe_request returns reconnect error dict on GoogleAuthError."""
        from noa.tools.google_auth import GoogleAuthClient, GoogleAuthError
        from noa.tools.google_calendar_client import (
            _GOOGLE_RECONNECT_ERROR,
            GoogleCalendarClient,
        )

        auth = MagicMock(spec=GoogleAuthClient)
        auth.access_token = "tok"
        auth.refresh_access_token = AsyncMock(
            side_effect=GoogleAuthError("Token refresh failed: 400")
        )
        client = GoogleCalendarClient(auth_client=auth)

        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient") as mock_http:
            mock_http.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await client._safe_request("get", "https://example.com")

        assert result == _GOOGLE_RECONNECT_ERROR
        assert "error" in result

    @pytest.mark.asyncio
    async def test_gmail_client_reloads_tokens_from_db(self) -> None:
        """GmailClient._ensure_fresh_token calls load_tokens_from_db when session_factory available."""
        from noa.tools.google_auth import GoogleAuthClient
        from noa.tools.google_gmail_client import GmailClient

        auth = MagicMock(spec=GoogleAuthClient)
        auth.access_token = "fresh_tok"

        user_id = uuid.uuid4()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_session_factory = MagicMock(return_value=mock_session)

        client = GmailClient(
            auth_client=auth,
            user_id=user_id,
            session_factory=mock_session_factory,
        )

        load_called = False

        async def mock_load(session: Any, uid: Any, ac: Any) -> bool:
            nonlocal load_called
            load_called = True
            return True

        with patch("noa.tools.google_gmail_client.load_tokens_from_db", side_effect=mock_load):
            result = await client._ensure_fresh_token()

        assert result is None
        assert load_called, "load_tokens_from_db was not called"

    @pytest.mark.asyncio
    async def test_calendar_client_reloads_tokens_from_db(self) -> None:
        """GoogleCalendarClient._ensure_fresh_token calls load_tokens_from_db."""
        from noa.tools.google_auth import GoogleAuthClient
        from noa.tools.google_calendar_client import GoogleCalendarClient

        auth = MagicMock(spec=GoogleAuthClient)
        auth.access_token = "fresh_tok"

        user_id = uuid.uuid4()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_factory = MagicMock(return_value=mock_session)

        client = GoogleCalendarClient(
            auth_client=auth,
            user_id=user_id,
            session_factory=mock_session_factory,
        )

        load_called = False

        async def mock_load(session: Any, uid: Any, ac: Any) -> bool:
            nonlocal load_called
            load_called = True
            return True

        with patch(
            "noa.tools.google_calendar_client.load_tokens_from_db",
            side_effect=mock_load,
        ):
            result = await client._ensure_fresh_token()

        assert result is None
        assert load_called, "load_tokens_from_db was not called"

    @pytest.mark.asyncio
    async def test_gmail_client_no_session_factory_skips_reload(self) -> None:
        """GmailClient._ensure_fresh_token skips reload when no session_factory."""
        from noa.tools.google_auth import GoogleAuthClient
        from noa.tools.google_gmail_client import GmailClient

        auth = MagicMock(spec=GoogleAuthClient)
        client = GmailClient(auth_client=auth)  # No user_id / session_factory

        result = await client._ensure_fresh_token()
        assert result is None  # No error, just skips reload

    @pytest.mark.asyncio
    async def test_token_refresh_failure_does_not_crash_tool(self) -> None:
        """GoogleAuthError during token refresh returns error dict, not an exception."""
        from noa.tools.google_auth import GoogleAuthClient, GoogleAuthError
        from noa.tools.google_gmail_client import GmailClient

        auth = MagicMock(spec=GoogleAuthClient)
        auth.access_token = "old_tok"
        auth.refresh_access_token = AsyncMock(
            side_effect=GoogleAuthError("Token refresh failed: 400")
        )
        client = GmailClient(auth_client=auth)

        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient") as mock_http:
            mock_http.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            # Must not raise — must return error dict
            result = await client.read_email(email_id="test123")

        assert isinstance(result, dict)
        assert "error" in result
        # Should be friendly reconnect message, not raw exception text
        assert "Token refresh failed" not in result.get("error", "")


# ---------------------------------------------------------------------------
# BE-AP1: Run summary update after approval resume
# ---------------------------------------------------------------------------


class TestRunSummaryAfterApproval:
    """BE-AP1: runner._update_run_summary updates the run's summary field."""

    @pytest.mark.asyncio
    async def test_update_run_summary_called_with_response(self) -> None:
        """_update_run_summary calls run_service.update_run with non-empty summary."""
        from noa.orchestrator.runner import OrchestratorRunner

        run_service = AsyncMock()
        run_service.update_run = AsyncMock()

        await OrchestratorRunner._update_run_summary(
            run_service,
            "run-123",
            "Email sent to alice@example.com",
            {},
        )

        run_service.update_run.assert_called_once()
        call_kwargs = run_service.update_run.call_args
        assert call_kwargs is not None
        # First arg is run_id
        assert "run-123" in str(call_kwargs)
        # summary kwarg should be non-empty
        summary_arg = call_kwargs.kwargs.get("summary", "")
        assert summary_arg  # not empty
        assert "email" in summary_arg.lower() or "alice" in summary_arg.lower()

    @pytest.mark.asyncio
    async def test_update_run_summary_skips_empty_response(self) -> None:
        """_update_run_summary does not call update_run when response is empty."""
        from noa.orchestrator.runner import OrchestratorRunner

        run_service = AsyncMock()
        run_service.update_run = AsyncMock()

        await OrchestratorRunner._update_run_summary(
            run_service,
            "run-123",
            "",
            {},
        )

        run_service.update_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_run_summary_failure_is_swallowed(self) -> None:
        """_update_run_summary swallows exceptions (best-effort)."""
        from noa.orchestrator.runner import OrchestratorRunner

        run_service = AsyncMock()
        run_service.update_run = AsyncMock(side_effect=RuntimeError("DB gone"))

        # Must not raise
        await OrchestratorRunner._update_run_summary(
            run_service,
            "run-123",
            "Some response",
            {},
        )
        # If we reach here, the exception was properly swallowed

    @pytest.mark.asyncio
    async def test_update_run_summary_includes_tool_names(self) -> None:
        """Summary includes tool names when tool_results are present."""
        from noa.orchestrator.runner import OrchestratorRunner

        run_service = AsyncMock()
        run_service.update_run = AsyncMock()

        tool_results = [{"name": "gmail", "result": {"id": "abc"}}]

        await OrchestratorRunner._update_run_summary(
            run_service,
            "run-456",
            "Email sent successfully.",
            {"tool_results": tool_results},
        )

        run_service.update_run.assert_called_once()
        call_kwargs = run_service.update_run.call_args
        summary_arg = call_kwargs.kwargs.get("summary", "")
        assert "gmail" in summary_arg.lower()

    @pytest.mark.asyncio
    async def test_resume_calls_update_run_summary(self) -> None:
        """resume() calls _update_run_summary after the graph completes."""
        from noa.orchestrator.runner import OrchestratorRunner, _pending_interrupts

        # Build a minimal mock graph that yields a result chunk
        async def mock_astream(command: Any, *, config: Any) -> Any:
            yield {
                "agent": {
                    "response": "Calendar event created: Team Meeting at 10am.",
                    "tool_results": [{"name": "calendar", "result": {"id": "evt1"}}],
                    "llm_usage": [],
                    "messages": [
                        {"role": "assistant", "content": "Calendar event created: Team Meeting at 10am."}
                    ],
                }
            }

        mock_graph = MagicMock()
        mock_graph.astream = mock_astream

        run_service = AsyncMock()
        run_service.update_status = AsyncMock()
        run_service.append_event = AsyncMock()
        run_service.update_run = AsyncMock()

        run_id = "resume-test-run-1"
        _pending_interrupts[run_id] = run_id  # Register as pending

        runner = OrchestratorRunner(graph=mock_graph)

        events = []
        async for event in runner.resume(
            run_id=run_id,
            decision={"decision": "approved"},
            run_service=run_service,
        ):
            events.append(event)

        # run summary update should have been called
        run_service.update_run.assert_called()
        summary_call = run_service.update_run.call_args
        summary_arg = summary_call.kwargs.get("summary", "")
        assert summary_arg  # non-empty
