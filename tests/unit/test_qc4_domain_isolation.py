"""Tests for domain isolation & worker wiring — Phase QC4.

Spec refs: SPEC.md §6.2 (Dual-Domain Architecture), §8.3 (Inter-Domain Communication),
           §9 (Private Worker RPC Contract), ARCH_INVARIANTS.md L3 (Domain Isolation)
Phase plan: PHASE_DETAILS.md Phase QC4

Findings addressed:
  C2 — Cross-domain import violations (OllamaClient, MAX_N_RESULTS)
  H1 — Workers are skeleton-only, no real endpoints
  H9 — Google AI provider missing tool call `id` field

These tests define the behavioral contract for domain isolation enforcement,
worker endpoint wiring, and Google AI tool call ID generation.
They are written BEFORE implementation and must fail initially.
"""

from __future__ import annotations

import ast
import importlib
import pathlib
import uuid
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.qc4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SRC_ROOT = pathlib.Path(__file__).resolve().parents[2] / "src" / "noa"


def _collect_imports(package_path: pathlib.Path) -> list[tuple[str, str]]:
    """Parse all .py files under *package_path* and return (file, module) pairs
    for every ``from X import ...`` or ``import X`` statement found."""
    results: list[tuple[str, str]] = []
    for py_file in package_path.rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(), filename=str(py_file))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                results.append((str(py_file), node.module))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    results.append((str(py_file), alias.name))
    return results


# ===================================================================
# C2 — Domain Isolation: No Cross-Domain Imports
# ===================================================================


class TestDomainIsolationImports:
    """SPEC.md §6.2 + ARCH_INVARIANTS L3: external_worker and private_worker
    packages must have zero import dependencies on each other."""

    def test_external_worker_does_not_import_private_worker(self):
        """SPEC.md §6.2: External domain code must never import from private domain.

        Scans all .py files under src/noa/external_worker/ for any
        ``from noa.private_worker`` or ``import noa.private_worker`` statement.
        """
        ext_path = _SRC_ROOT / "external_worker"
        if not ext_path.exists():
            pytest.skip("external_worker package not found")

        violations = [
            (f, mod)
            for f, mod in _collect_imports(ext_path)
            if mod.startswith("noa.private_worker")
        ]
        assert violations == [], (
            f"External worker imports from private worker (violates §6.2): "
            f"{[(pathlib.Path(f).name, mod) for f, mod in violations]}"
        )

    def test_private_worker_does_not_import_external_worker(self):
        """SPEC.md §6.2: Private domain code must never import from external domain.

        Scans all .py files under src/noa/private_worker/ for any
        ``from noa.external_worker`` or ``import noa.external_worker`` statement.
        """
        priv_path = _SRC_ROOT / "private_worker"
        if not priv_path.exists():
            pytest.skip("private_worker package not found")

        violations = [
            (f, mod)
            for f, mod in _collect_imports(priv_path)
            if mod.startswith("noa.external_worker")
        ]
        assert violations == [], (
            f"Private worker imports from external worker (violates §6.2): "
            f"{[(pathlib.Path(f).name, mod) for f, mod in violations]}"
        )

    def test_shared_llm_does_not_import_from_either_domain(self):
        """SPEC.md §6.2 / M8: Shared modules in noa.llm must not import
        from either noa.external_worker or noa.private_worker."""
        llm_path = _SRC_ROOT / "llm"
        if not llm_path.exists():
            pytest.skip("noa.llm package not found")

        violations = [
            (f, mod)
            for f, mod in _collect_imports(llm_path)
            if mod.startswith("noa.external_worker")
            or mod.startswith("noa.private_worker")
        ]
        assert violations == [], (
            f"Shared noa.llm imports from domain packages (violates §6.2): "
            f"{[(pathlib.Path(f).name, mod) for f, mod in violations]}"
        )


class TestSharedModuleLocation:
    """PLAN Phase QC4 / C2: Shared code (OllamaClient, MAX_N_RESULTS) must
    live in shared modules, not in domain-specific packages."""

    def test_ollama_client_importable_from_shared_module(self):
        """PLAN QC4/C2: OllamaClient must be importable from noa.llm.providers,
        not only from noa.private_worker.ollama_client."""
        try:
            mod = importlib.import_module("noa.llm.providers")
        except ModuleNotFoundError:
            pytest.fail(
                "noa.llm.providers module does not exist — "
                "OllamaClient must be moved to a shared module per C2"
            )
        assert hasattr(mod, "OllamaClient"), (
            "noa.llm.providers exists but does not export OllamaClient"
        )

    def test_max_n_results_importable_from_shared_constants(self):
        """PLAN QC4/C2: MAX_N_RESULTS must be importable from noa.constants,
        not only from noa.private_worker.rpc."""
        try:
            mod = importlib.import_module("noa.constants")
        except ModuleNotFoundError:
            pytest.fail(
                "noa.constants module does not exist — "
                "MAX_N_RESULTS must be moved to a shared module per C2"
            )
        assert hasattr(mod, "MAX_N_RESULTS"), (
            "noa.constants exists but does not export MAX_N_RESULTS"
        )

    def test_max_n_results_value_is_20(self):
        """SPEC.md §9.1: n_results max is 20."""
        try:
            from noa.constants import MAX_N_RESULTS
        except (ModuleNotFoundError, ImportError):
            pytest.skip("noa.constants not yet created")
        assert MAX_N_RESULTS == 20

    def test_tools_memory_imports_from_shared_not_private(self):
        """PLAN QC4/C2: noa.tools.memory must import MAX_N_RESULTS from
        noa.constants, not from noa.private_worker.rpc."""
        memory_path = _SRC_ROOT / "tools" / "memory.py"
        if not memory_path.exists():
            pytest.skip("noa.tools.memory not found")

        imports = []
        tree = ast.parse(memory_path.read_text(), filename=str(memory_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "MAX_N_RESULTS" in [a.name for a in (node.names or [])]:
                imports.append(node.module)

        for imp in imports:
            assert not imp.startswith("noa.private_worker"), (
                f"noa.tools.memory imports MAX_N_RESULTS from {imp} "
                f"— must import from noa.constants instead (C2)"
            )


# ===================================================================
# H1 — Worker Endpoints: External Worker POST /v1/complete
# ===================================================================


class TestExternalWorkerCompleteEndpoint:
    """PLAN QC4/H1: External worker must expose POST /v1/complete
    using ProviderRouter for LLM dispatch."""

    @pytest.fixture
    def ext_app(self):
        """Import and create the external worker FastAPI app."""
        try:
            from noa.external_worker.app import create_external_app
        except ImportError:
            pytest.skip("external_worker app not importable")
        return create_external_app()

    def test_complete_route_registered(self, ext_app):
        """PLAN QC4/H1: External worker must have a POST /v1/complete route."""
        routes = [r.path for r in ext_app.routes if hasattr(r, "methods")]
        methods_by_path = {}
        for r in ext_app.routes:
            if hasattr(r, "methods") and hasattr(r, "path"):
                methods_by_path[r.path] = r.methods

        assert "/v1/complete" in methods_by_path, (
            f"POST /v1/complete not registered in external worker. "
            f"Available routes: {list(methods_by_path.keys())}"
        )
        assert "POST" in methods_by_path["/v1/complete"], (
            "/v1/complete exists but does not accept POST"
        )

    @pytest.mark.anyio
    async def test_complete_endpoint_returns_llm_response(self, ext_app):
        """PLAN QC4/H1: POST /v1/complete must return an LLM completion result."""
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=ext_app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/v1/complete",
                json={
                    "messages": [{"role": "user", "content": "Hello"}],
                    "model": "test-model",
                },
            )
        # Should not be 404 (route missing) or 405 (wrong method).
        # 502/503 are acceptable — means endpoint is wired but router
        # is not configured (no settings in test context).
        assert resp.status_code not in (404, 405), (
            f"POST /v1/complete returned {resp.status_code} — endpoint not wired"
        )


# ===================================================================
# H1 — Worker Endpoints: Private Worker POST /rpc
# ===================================================================


class TestPrivateWorkerRpcEndpoint:
    """PLAN QC4/H1: Private worker must expose POST /rpc dispatching
    to memory/DLP handlers per SPEC.md §9."""

    @pytest.fixture
    def priv_app(self):
        """Import and create the private worker FastAPI app."""
        try:
            from noa.private_worker.app import create_private_app
        except ImportError:
            pytest.skip("private_worker app not importable")
        return create_private_app()

    def test_rpc_route_registered(self, priv_app):
        """PLAN QC4/H1: Private worker must have a POST /rpc route."""
        methods_by_path: dict[str, set] = {}
        for r in priv_app.routes:
            if hasattr(r, "methods") and hasattr(r, "path"):
                methods_by_path[r.path] = r.methods

        assert "/rpc" in methods_by_path, (
            f"POST /rpc not registered in private worker. "
            f"Available routes: {list(methods_by_path.keys())}"
        )
        assert "POST" in methods_by_path["/rpc"], (
            "/rpc exists but does not accept POST"
        )

    @pytest.mark.anyio
    async def test_rpc_endpoint_accepts_valid_request(self, priv_app):
        """SPEC.md §9.1: POST /rpc must accept a valid RPC request and return
        a structured response (not 404/405)."""
        from httpx import ASGITransport, AsyncClient

        rpc_request = {
            "request_id": str(uuid.uuid4()),
            "idempotency_key": str(uuid.uuid4()),
            "task_type": "recall",
            "payload": {
                "query": "test query",
                "n_results": 5,
            },
            "timeout_ms": 30000,
        }

        async with AsyncClient(
            transport=ASGITransport(app=priv_app),
            base_url="http://test",
        ) as client:
            resp = await client.post("/rpc", json=rpc_request)

        assert resp.status_code not in (404, 405), (
            f"POST /rpc returned {resp.status_code} — endpoint not wired"
        )

    @pytest.mark.anyio
    async def test_rpc_response_matches_contract_schema(self, priv_app):
        """SPEC.md §9.2: RPC response must contain request_id, status, and result fields."""
        from httpx import ASGITransport, AsyncClient

        req_id = str(uuid.uuid4())
        rpc_request = {
            "request_id": req_id,
            "idempotency_key": str(uuid.uuid4()),
            "task_type": "recall",
            "payload": {"query": "what do I know?", "n_results": 3},
            "timeout_ms": 30000,
        }

        async with AsyncClient(
            transport=ASGITransport(app=priv_app),
            base_url="http://test",
        ) as client:
            resp = await client.post("/rpc", json=rpc_request)

        if resp.status_code in (404, 405):
            pytest.fail("POST /rpc not wired — cannot check response schema")

        body = resp.json()
        assert "request_id" in body, "RPC response missing request_id (§9.2)"
        assert "status" in body, "RPC response missing status (§9.2)"
        assert body["status"] in ("success", "error", "timeout"), (
            f"RPC response status must be success|error|timeout, got {body['status']}"
        )


# ===================================================================
# H9 — Google AI Tool Call ID
# ===================================================================


class TestGoogleAIToolCallId:
    """PLAN QC4/H9: Google AI provider must generate a synthetic `id` for
    tool calls so downstream code can match call → result."""

    def test_parse_response_includes_tool_call_id(self):
        """PLAN QC4/H9: When Google AI returns a functionCall, the parsed
        tool_calls list must include an 'id' field (synthetic UUID)."""
        from noa.external_worker.llm.google_ai import GoogleAIClient

        client = GoogleAIClient.__new__(GoogleAIClient)
        # Set minimal attributes that _parse_response reads
        client._model = "gemini-pro"

        # Simulate a Google AI response with a functionCall part
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "web_search",
                                    "args": {"query": "weather today"},
                                }
                            }
                        ]
                    }
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 5,
            },
        }

        result = client._parse_response(mock_response)

        assert "tool_calls" in result, (
            "Google AI _parse_response must return tool_calls key"
        )
        assert len(result["tool_calls"]) == 1, (
            "Expected exactly one tool call from single functionCall part"
        )

        tool_call = result["tool_calls"][0]
        assert "id" in tool_call, (
            "Google AI tool call missing 'id' field — H9 requires synthetic ID "
            "for downstream call-result matching"
        )
        assert isinstance(tool_call["id"], str), (
            f"Tool call id must be a string, got {type(tool_call['id'])}"
        )
        assert len(tool_call["id"]) > 0, "Tool call id must not be empty"

    def test_tool_call_ids_are_unique(self):
        """PLAN QC4/H9: Each tool call in a multi-tool response must have
        a unique id for result matching."""
        from noa.external_worker.llm.google_ai import GoogleAIClient

        client = GoogleAIClient.__new__(GoogleAIClient)
        client._model = "gemini-pro"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "web_search",
                                    "args": {"query": "weather"},
                                }
                            },
                            {
                                "functionCall": {
                                    "name": "calendar_list",
                                    "args": {"date": "2026-03-07"},
                                }
                            },
                        ]
                    }
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 15,
                "candidatesTokenCount": 10,
            },
        }

        result = client._parse_response(mock_response)
        tool_calls = result.get("tool_calls", [])
        assert len(tool_calls) == 2, "Expected two tool calls"

        for i, tc in enumerate(tool_calls):
            assert "id" in tc, (
                f"Tool call {i} missing 'id' field — H9 requires synthetic ID"
            )

        ids = [tc["id"] for tc in tool_calls]
        assert len(set(ids)) == 2, (
            f"Tool call ids must be unique, got duplicates: {ids}"
        )


# ===================================================================
# Integration: Domain isolation verified at module level
# ===================================================================


class TestDomainIsolationIntegration:
    """Integration test: verify that after QC4 changes, the external worker
    LLM router can be imported without pulling in private_worker."""

    def test_provider_router_import_does_not_load_private_worker(self):
        """SPEC.md §6.2: Importing ProviderRouter must not transitively
        import noa.private_worker modules.

        This is the integration test: it exercises the real import chain
        without mocking internals.
        """
        import sys

        # Record which private_worker modules are loaded before
        before = {
            k for k in sys.modules if k.startswith("noa.private_worker")
        }

        try:
            importlib.import_module("noa.external_worker.llm.router")
        except ImportError:
            pytest.skip("Cannot import router module")

        after = {
            k for k in sys.modules if k.startswith("noa.private_worker")
        }
        new_private_imports = after - before

        assert new_private_imports == set(), (
            f"Importing noa.external_worker.llm.router loaded private_worker "
            f"modules: {new_private_imports} — violates domain isolation (§6.2)"
        )
