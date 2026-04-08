"""Tests for OV9: Web Search Artifact Reports.

Verifies that web_search tool results are formatted as Markdown reports,
written to disk as artifacts, and that an artifact_created SSE event is emitted.

Phase: OV9
Spec refs: SPEC.md §22.3
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_run_service(artifact_id: str | None = None) -> MagicMock:
    """Create a mock RunService that stubs artifact creation."""
    svc = MagicMock()
    svc.append_event = AsyncMock()
    svc.update_status = AsyncMock()

    artifact = MagicMock()
    artifact.id = uuid.UUID(artifact_id) if artifact_id else uuid.uuid4()
    svc.create_artifact = AsyncMock(return_value=artifact)
    return svc


def _make_tool_result(
    *,
    tool_name: str = "web_search",
    query: str = "test query",
    results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Construct a tool_result dict as the runner's tools node produces it."""
    if results is None:
        results = [
            {"title": "Result One", "url": "https://example.com/1", "snippet": "Snippet one."},
            {"title": "Result Two", "url": "https://example.com/2", "snippet": "Snippet two."},
        ]
    return {
        "name": tool_name,
        "args": {"query": query},
        "result": {"results": results},
    }


# ---------------------------------------------------------------------------
# 1. Report formatting
# ---------------------------------------------------------------------------

class TestFormatSearchReport:
    """_format_search_report produces correct Markdown."""

    def _fmt(self, query: str, results: list[dict[str, Any]], ts: str) -> str:
        from noa.orchestrator.runner import OrchestratorRunner
        return OrchestratorRunner._format_search_report(query, results, ts)

    def test_header_contains_query(self) -> None:
        md = self._fmt("my query", [], "2026-04-08T12:00:00+00:00")
        assert "**Query:** my query" in md

    def test_header_contains_date(self) -> None:
        ts = "2026-04-08T12:00:00+00:00"
        md = self._fmt("q", [], ts)
        assert f"**Date:** {ts}" in md

    def test_header_contains_result_count(self) -> None:
        results = [{"title": "A", "url": "https://a.com", "snippet": "s"}]
        md = self._fmt("q", results, "ts")
        assert "**Results:** 1" in md

    def test_results_section_numbered(self) -> None:
        results = [
            {"title": "First", "url": "https://first.com", "snippet": "First snippet."},
            {"title": "Second", "url": "https://second.com", "snippet": "Second snippet."},
        ]
        md = self._fmt("q", results, "ts")
        assert "## 1. First" in md
        assert "## 2. Second" in md

    def test_results_include_url_and_snippet(self) -> None:
        results = [
            {"title": "Page", "url": "https://page.com", "snippet": "Page snippet."},
        ]
        md = self._fmt("q", results, "ts")
        assert "**URL:** https://page.com" in md
        assert "Page snippet." in md

    def test_empty_results(self) -> None:
        md = self._fmt("empty search", [], "ts")
        assert "**Results:** 0" in md
        # No numbered section headers beyond the intro
        assert "## 1." not in md

    def test_snippet_fallback_to_content(self) -> None:
        """Results without 'snippet' key fall back to 'content'."""
        results = [{"title": "T", "url": "u", "content": "Content text."}]
        md = self._fmt("q", results, "ts")
        assert "Content text." in md

    def test_missing_url_omitted(self) -> None:
        """Results without URL don't produce empty URL line."""
        results = [{"title": "No URL", "snippet": "s"}]
        md = self._fmt("q", results, "ts")
        assert "**URL:**" not in md


# ---------------------------------------------------------------------------
# 2. Artifact creation (unit — file system mocked)
# ---------------------------------------------------------------------------

class TestCreateSearchArtifact:
    """_create_search_artifact writes file, calls create_artifact, returns event."""

    def _run(self, coro: Any) -> Any:
        return asyncio.get_event_loop().run_until_complete(coro)

    def _make_runner(self) -> Any:
        from noa.orchestrator.runner import OrchestratorRunner
        return OrchestratorRunner(graph=MagicMock())

    def test_returns_artifact_created_event(self, tmp_path: Path) -> None:
        runner = self._make_runner()
        run_id = str(uuid.uuid4())
        svc = _make_run_service()
        tr = _make_tool_result(query="latest news")

        with patch("noa.orchestrator.runner._ARTIFACTS_BASE", tmp_path):
            event = self._run(
                runner._create_search_artifact(
                    run_service=svc,
                    run_id=run_id,
                    tool_result=tr,
                )
            )

        assert event is not None
        assert event["event_type"] == "artifact_created"
        payload = event["payload"]
        assert payload["name"] == "search_report.md"
        assert payload["mime_type"] == "text/markdown"
        assert payload["size_bytes"] > 0

    def test_file_written_to_disk(self, tmp_path: Path) -> None:
        runner = self._make_runner()
        run_id = str(uuid.uuid4())
        svc = _make_run_service()
        tr = _make_tool_result(query="test disk write")

        with patch("noa.orchestrator.runner._ARTIFACTS_BASE", tmp_path):
            self._run(
                runner._create_search_artifact(
                    run_service=svc,
                    run_id=run_id,
                    tool_result=tr,
                )
            )

        artifact_file = tmp_path / run_id / "search_report.md"
        assert artifact_file.exists()
        content = artifact_file.read_text()
        assert "**Query:** test disk write" in content

    def test_create_artifact_called_with_correct_params(self, tmp_path: Path) -> None:
        runner = self._make_runner()
        run_id = str(uuid.uuid4())
        svc = _make_run_service()
        tr = _make_tool_result(query="param check")

        with patch("noa.orchestrator.runner._ARTIFACTS_BASE", tmp_path):
            self._run(
                runner._create_search_artifact(
                    run_service=svc,
                    run_id=run_id,
                    tool_result=tr,
                )
            )

        svc.create_artifact.assert_called_once()
        call_kwargs = svc.create_artifact.call_args
        # First positional arg is run_uuid
        args, kwargs = call_kwargs
        assert kwargs.get("artifact_type") == "export"
        assert kwargs.get("name") == "search_report.md"
        assert kwargs.get("mime_type") == "text/markdown"
        assert kwargs.get("size_bytes") > 0

    def test_returns_none_on_create_artifact_failure(self, tmp_path: Path) -> None:
        runner = self._make_runner()
        run_id = str(uuid.uuid4())
        svc = _make_run_service()
        svc.create_artifact = AsyncMock(side_effect=RuntimeError("DB error"))
        tr = _make_tool_result()

        with patch("noa.orchestrator.runner._ARTIFACTS_BASE", tmp_path):
            event = self._run(
                runner._create_search_artifact(
                    run_service=svc,
                    run_id=run_id,
                    tool_result=tr,
                )
            )

        assert event is None

    def test_handles_string_result_gracefully(self, tmp_path: Path) -> None:
        """When result is a serialised string, creates empty-result artifact."""
        runner = self._make_runner()
        run_id = str(uuid.uuid4())
        svc = _make_run_service()
        tr = {
            "name": "web_search",
            "args": {"query": "string result"},
            "result": "Some string result",
        }

        with patch("noa.orchestrator.runner._ARTIFACTS_BASE", tmp_path):
            event = self._run(
                runner._create_search_artifact(
                    run_service=svc,
                    run_id=run_id,
                    tool_result=tr,
                )
            )

        # Should still produce an event (just with 0 results in report)
        assert event is not None
        assert event["event_type"] == "artifact_created"


# ---------------------------------------------------------------------------
# 3. SSE event emission — integration with runner
# ---------------------------------------------------------------------------

class TestRunnerSearchArtifactEmission:
    """Runner emits artifact_created event after web_search tool_result."""

    def _collect(self, runner: Any, **kwargs: Any) -> list[dict[str, Any]]:
        async def _run() -> list[dict[str, Any]]:
            events: list[dict[str, Any]] = []
            async for ev in runner.run(**kwargs):
                events.append(ev)
            return events

        return asyncio.get_event_loop().run_until_complete(_run())

    def test_artifact_created_event_emitted_after_web_search(
        self, tmp_path: Path,
    ) -> None:
        from noa.orchestrator.runner import OrchestratorRunner

        search_results = [
            {"title": "Top Result", "url": "https://top.com", "snippet": "Top snippet."},
        ]
        tool_result_entry = {
            "name": "web_search",
            "args": {"query": "latest news"},
            "result": {"results": search_results},
        }

        async def _fake_astream(state: Any, **_kwargs: Any):
            yield {
                "agent": {
                    "messages": [],
                    "tool_calls": [],
                    "tool_results": [],
                    "response": None,
                    "llm_usage": [],
                    "total_cost": 0.0,
                },
            }
            yield {
                "tools": {
                    "messages": [],
                    "tool_calls": [],
                    "tool_results": [tool_result_entry],
                    "response": None,
                    "llm_usage": [],
                    "total_cost": 0.0,
                },
            }

        mock_graph = MagicMock()
        mock_graph.astream = _fake_astream
        runner = OrchestratorRunner(graph=mock_graph)

        svc = _make_run_service()
        run_id = str(uuid.uuid4())

        with patch("noa.orchestrator.runner._ARTIFACTS_BASE", tmp_path):
            events = self._collect(
                runner,
                message="search news",
                run_service=svc,
                run_id=run_id,
            )

        event_types = [e["event_type"] for e in events]
        assert "artifact_created" in event_types

        artifact_ev = next(e for e in events if e["event_type"] == "artifact_created")
        assert artifact_ev["payload"]["name"] == "search_report.md"
        assert artifact_ev["payload"]["mime_type"] == "text/markdown"

    def test_no_artifact_for_non_search_tool(self, tmp_path: Path) -> None:
        """Non-web_search tool results do NOT trigger artifact creation."""
        from noa.orchestrator.runner import OrchestratorRunner

        tool_result_entry = {
            "name": "calendar",
            "args": {},
            "result": {"events": []},
        }

        async def _fake_astream(state: Any, **_kwargs: Any):
            yield {
                "tools": {
                    "messages": [],
                    "tool_calls": [],
                    "tool_results": [tool_result_entry],
                    "response": None,
                    "llm_usage": [],
                    "total_cost": 0.0,
                },
            }

        mock_graph = MagicMock()
        mock_graph.astream = _fake_astream
        runner = OrchestratorRunner(graph=mock_graph)

        svc = _make_run_service()
        run_id = str(uuid.uuid4())

        with patch("noa.orchestrator.runner._ARTIFACTS_BASE", tmp_path):
            events = self._collect(
                runner,
                message="show calendar",
                run_service=svc,
                run_id=run_id,
            )

        event_types = [e["event_type"] for e in events]
        assert "artifact_created" not in event_types

    def test_artifact_created_is_in_valid_event_types(self) -> None:
        from noa.orchestrator.sse_types import VALID_SSE_EVENT_TYPES
        assert "artifact_created" in VALID_SSE_EVENT_TYPES

    def test_tool_result_emitted_before_artifact_created(
        self, tmp_path: Path,
    ) -> None:
        """tool_result event precedes artifact_created in the event stream."""
        from noa.orchestrator.runner import OrchestratorRunner

        tool_result_entry = {
            "name": "web_search",
            "args": {"query": "order check"},
            "result": {"results": [{"title": "T", "url": "u", "snippet": "s"}]},
        }

        async def _fake_astream(state: Any, **_kwargs: Any):
            yield {
                "tools": {
                    "messages": [],
                    "tool_calls": [],
                    "tool_results": [tool_result_entry],
                    "response": None,
                    "llm_usage": [],
                    "total_cost": 0.0,
                },
            }

        mock_graph = MagicMock()
        mock_graph.astream = _fake_astream
        runner = OrchestratorRunner(graph=mock_graph)

        svc = _make_run_service()
        run_id = str(uuid.uuid4())

        with patch("noa.orchestrator.runner._ARTIFACTS_BASE", tmp_path):
            events = self._collect(
                runner,
                message="search stuff",
                run_service=svc,
                run_id=run_id,
            )

        event_types = [e["event_type"] for e in events]
        tr_idx = next(i for i, t in enumerate(event_types) if t == "tool_result")
        ac_idx = next(i for i, t in enumerate(event_types) if t == "artifact_created")
        assert tr_idx < ac_idx, "tool_result must precede artifact_created"
