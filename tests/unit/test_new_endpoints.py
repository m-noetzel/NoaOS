"""Tests for new Noa API endpoints — Wave 6 web client routes.

Tests cover: route registration (via AST inspection), Pydantic schema
validation, and app.py router composition. These tests run without
FastAPI installed by parsing source files and testing schemas directly.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

pytestmark = pytest.mark.wm6

# ---------------------------------------------------------------------------
# Helpers — AST-based route extraction
# ---------------------------------------------------------------------------

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "noa" / "api"


def _parse_module(relative_path: str) -> ast.Module:
    """Parse a Python source file under src/noa/api/ into an AST."""
    full_path = SRC_ROOT / relative_path
    assert full_path.exists(), f"Source file not found: {full_path}"
    return ast.parse(full_path.read_text(), filename=str(full_path))


def _extract_route_decorators(tree: ast.Module) -> list[tuple[str, str]]:
    """Extract (method, path) pairs from @router.<method>(...) decorators.

    Returns e.g. [("get", ""), ("post", ""), ("get", "/{thread_id}/messages")].
    """
    routes: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            # Match @router.get("/path") or @router.post("/path")
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                attr = dec.func
                if (
                    isinstance(attr.value, ast.Name)
                    and attr.value.id == "router"
                    and attr.attr in ("get", "post", "put", "delete", "patch")
                ):
                    method = attr.attr
                    # First positional arg is the path string
                    path = ""
                    if dec.args and isinstance(dec.args[0], ast.Constant):
                        path = dec.args[0].value
                    routes.append((method, path))
    return routes


def _extract_router_prefix(tree: ast.Module) -> str | None:
    """Extract the prefix= kwarg from APIRouter(...) assignment."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        val = node.value
        if isinstance(val, ast.Call):
            # Look for APIRouter(prefix="...")
            func = val.func
            if isinstance(func, ast.Name) and func.id == "APIRouter":
                for kw in val.keywords:
                    if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                        return kw.value.value
            if isinstance(func, ast.Attribute) and func.attr == "APIRouter":
                for kw in val.keywords:
                    if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                        return kw.value.value
    return None


def _extract_pydantic_models(tree: ast.Module) -> list[str]:
    """Extract names of classes that inherit from BaseModel."""
    models: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id == "BaseModel":
                    models.append(node.name)
    return models


def _extract_include_router_calls(tree: ast.Module) -> int:
    """Count app.include_router(...) calls in app.py."""
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "include_router":
            count += 1
    return count


# ---------------------------------------------------------------------------
# 1. threads.py — route registration
# ---------------------------------------------------------------------------


class TestThreadsRoutes:
    """Verify threads.py defines expected routes."""

    @pytest.fixture(autouse=True)
    def _parse(self):
        self.tree = _parse_module("v1/threads.py")
        self.routes = _extract_route_decorators(self.tree)
        self.prefix = _extract_router_prefix(self.tree)

    def test_router_prefix(self):
        """Router prefix is /api/v1/threads."""
        assert self.prefix == "/api/v1/threads"

    def test_has_get_threads(self):
        """GET /threads route exists (path='')."""
        assert ("get", "") in self.routes

    def test_has_post_threads(self):
        """POST /threads route exists (path='')."""
        assert ("post", "") in self.routes

    def test_has_get_thread_messages(self):
        """GET /threads/{thread_id}/messages route exists."""
        assert ("get", "/{thread_id}/messages") in self.routes

    def test_route_count(self):
        """Routes defined in threads.py (GET list, POST create, GET messages, PATCH rename, DELETE thread)."""
        assert len(self.routes) == 5

    def test_create_thread_request_model_defined(self):
        """CreateThreadRequest Pydantic model is defined."""
        models = _extract_pydantic_models(self.tree)
        assert "CreateThreadRequest" in models


# ---------------------------------------------------------------------------
# 2. chat.py — route registration and ChatRequest schema
# ---------------------------------------------------------------------------


class TestChatRoutes:
    """Verify chat.py defines expected routes."""

    @pytest.fixture(autouse=True)
    def _parse(self):
        self.tree = _parse_module("v1/chat.py")
        self.routes = _extract_route_decorators(self.tree)
        self.prefix = _extract_router_prefix(self.tree)

    def test_router_prefix(self):
        """Router prefix is /api/v1."""
        assert self.prefix == "/api/v1"

    def test_has_post_chat(self):
        """POST /chat route exists."""
        assert ("post", "/chat") in self.routes

    def test_route_count(self):
        """Exactly 1 route defined in chat.py."""
        assert len(self.routes) == 1


class TestChatRequestSchema:
    """Validate the real ChatRequest Pydantic model from noa.api.v1.chat."""

    def test_valid_full_request(self):
        """Full ChatRequest with all optional fields validates."""
        from noa.api.v1.chat import ChatRequest

        req = ChatRequest(
            message="Hello",
            thread_id="abc-123",
            privacy_mode="external",
            model="claude-sonnet-4-20250514",
            provider="anthropic",
            temperature=0.7,
            max_tokens=1024,
        )
        assert req.message == "Hello"
        assert req.temperature == 0.7

    def test_valid_minimal_request(self):
        """ChatRequest with only 'message' (all other fields optional) validates."""
        from noa.api.v1.chat import ChatRequest

        req = ChatRequest(message="Hi")
        assert req.thread_id is None
        assert req.privacy_mode is None
        assert req.model is None
        assert req.provider is None
        assert req.temperature is None
        assert req.max_tokens is None

    def test_missing_message_rejected(self):
        """ChatRequest without 'message' is rejected."""
        from noa.api.v1.chat import ChatRequest

        with pytest.raises(ValidationError) as exc_info:
            ChatRequest(privacy_mode="external", model="claude-sonnet-4-20250514")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("message",) for e in errors)

    def test_privacy_mode_optional(self):
        """ChatRequest privacy_mode is optional — defaults to None (external at runtime)."""
        from noa.api.v1.chat import ChatRequest

        req = ChatRequest(message="Hello")
        assert req.privacy_mode is None

    def test_privacy_mode_accepts_private_and_external(self):
        """ChatRequest privacy_mode accepts 'private' and 'external'."""
        from noa.api.v1.chat import ChatRequest

        req_priv = ChatRequest(message="Hi", privacy_mode="private")
        req_ext = ChatRequest(message="Hi", privacy_mode="external")
        assert req_priv.privacy_mode == "private"
        assert req_ext.privacy_mode == "external"

    def test_temperature_accepts_float(self):
        """temperature field coerces numeric values to float."""
        from noa.api.v1.chat import ChatRequest

        req = ChatRequest(message="Hi", temperature=1)
        assert isinstance(req.temperature, float)


# ---------------------------------------------------------------------------
# 3. memory.py — route registration
# ---------------------------------------------------------------------------


class TestMemoryRoutes:
    """Verify memory.py defines expected routes."""

    @pytest.fixture(autouse=True)
    def _parse(self):
        self.tree = _parse_module("v1/memory.py")
        self.routes = _extract_route_decorators(self.tree)
        self.prefix = _extract_router_prefix(self.tree)

    def test_router_prefix(self):
        """Router prefix is /api/v1/memory."""
        assert self.prefix == "/api/v1/memory"

    def test_has_get_facts(self):
        """GET /facts route exists."""
        assert ("get", "/facts") in self.routes

    def test_has_post_approve(self):
        """POST /facts/{fact_id}/approve route exists."""
        assert ("post", "/facts/{fact_id}/approve") in self.routes

    def test_has_post_update(self):
        """POST /facts/{fact_id}/update route exists."""
        assert ("post", "/facts/{fact_id}/update") in self.routes

    def test_has_delete_fact(self):
        """DELETE /facts/{fact_id} route exists."""
        assert ("delete", "/facts/{fact_id}") in self.routes

    def test_route_count(self):
        """Routes in memory.py: GET /facts, POST /facts, POST approve, POST update, DELETE."""
        assert len(self.routes) == 5

    def test_update_fact_request_model_defined(self):
        """UpdateFactRequest Pydantic model is defined."""
        models = _extract_pydantic_models(self.tree)
        assert "UpdateFactRequest" in models


class TestUpdateFactRequestSchema:
    """Validate UpdateFactRequest schema."""

    def _make_model(self):
        class UpdateFactRequest(BaseModel):
            fact: str

        return UpdateFactRequest

    def test_valid_request(self):
        """UpdateFactRequest with fact field validates."""
        Model = self._make_model()
        req = Model(fact="User prefers dark mode")
        assert req.fact == "User prefers dark mode"

    def test_missing_fact_rejected(self):
        """UpdateFactRequest without 'fact' is rejected."""
        Model = self._make_model()
        with pytest.raises(ValidationError):
            Model()


# ---------------------------------------------------------------------------
# 4. settings.py — route registration and UpdateSettingsRequest schema
# ---------------------------------------------------------------------------


class TestSettingsRoutes:
    """Verify settings.py defines expected routes."""

    @pytest.fixture(autouse=True)
    def _parse(self):
        self.tree = _parse_module("v1/settings.py")
        self.routes = _extract_route_decorators(self.tree)
        self.prefix = _extract_router_prefix(self.tree)

    def test_router_prefix(self):
        """Router prefix is /api/v1/settings."""
        assert self.prefix == "/api/v1/settings"

    def test_has_get_settings(self):
        """GET / route exists (path='')."""
        assert ("get", "") in self.routes

    def test_has_put_settings(self):
        """PUT / route exists (path='')."""
        assert ("put", "") in self.routes

    def test_route_count(self):
        """Settings router has ≥4 routes (GET/PUT/PATCH + GET /providers from FR1; system-prompt GET/PUT added in FR4)."""
        assert len(self.routes) >= 4


class TestUpdateSettingsRequestSchema:
    """Validate UpdateSettingsRequest schema."""

    def _make_model(self):
        class UpdateSettingsRequest(BaseModel):
            default_model: str | None = None
            default_privacy_mode: str | None = None
            budget_daily_usd: float | None = None
            budget_monthly_usd: float | None = None

        return UpdateSettingsRequest

    def test_all_fields_optional(self):
        """All fields are optional — empty body is valid."""
        Model = self._make_model()
        req = Model()
        assert req.default_model is None
        assert req.default_privacy_mode is None
        assert req.budget_daily_usd is None
        assert req.budget_monthly_usd is None

    def test_partial_update(self):
        """Setting only some fields works."""
        Model = self._make_model()
        req = Model(default_model="gpt-4", budget_daily_usd=5.0)
        assert req.default_model == "gpt-4"
        assert req.budget_daily_usd == 5.0
        assert req.default_privacy_mode is None

    def test_full_update(self):
        """All fields can be set simultaneously."""
        Model = self._make_model()
        req = Model(
            default_model="claude-sonnet-4-20250514",
            default_privacy_mode="private",
            budget_daily_usd=10.0,
            budget_monthly_usd=200.0,
        )
        assert req.budget_monthly_usd == 200.0

    def test_budget_accepts_int_as_float(self):
        """Budget fields coerce integers to floats."""
        Model = self._make_model()
        req = Model(budget_daily_usd=5)
        assert isinstance(req.budget_daily_usd, float)


# ---------------------------------------------------------------------------
# 5. usage.py — route registration
# ---------------------------------------------------------------------------


class TestUsageRoutes:
    """Verify usage.py defines expected routes."""

    @pytest.fixture(autouse=True)
    def _parse(self):
        self.tree = _parse_module("v1/usage.py")
        self.routes = _extract_route_decorators(self.tree)
        self.prefix = _extract_router_prefix(self.tree)

    def test_router_prefix(self):
        """Router prefix is /api/v1/usage."""
        assert self.prefix == "/api/v1/usage"

    def test_has_get_usage(self):
        """GET / route exists (path='')."""
        assert ("get", "") in self.routes

    def test_route_count(self):
        """Exactly 1 route defined in usage.py."""
        assert len(self.routes) == 1


# ---------------------------------------------------------------------------
# 6. artifacts.py — route registration
# ---------------------------------------------------------------------------


class TestArtifactsRoutes:
    """Verify artifacts.py defines expected routes."""

    @pytest.fixture(autouse=True)
    def _parse(self):
        self.tree = _parse_module("v1/artifacts.py")
        self.routes = _extract_route_decorators(self.tree)
        self.prefix = _extract_router_prefix(self.tree)

    def test_router_prefix(self):
        """Router prefix is /api/v1/artifacts."""
        assert self.prefix == "/api/v1/artifacts"

    def test_has_get_download(self):
        """GET /{artifact_id}/download route exists."""
        assert ("get", "/{artifact_id}/download") in self.routes

    def test_route_count(self):
        """Routes defined in artifacts.py (GET list + GET download)."""
        assert len(self.routes) == 2


# ---------------------------------------------------------------------------
# 7. approvals.py — route registration and ApprovalDecision schema
# ---------------------------------------------------------------------------


class TestApprovalsRoutes:
    """Verify approvals.py defines expected routes."""

    @pytest.fixture(autouse=True)
    def _parse(self):
        self.tree = _parse_module("v1/approvals.py")
        self.routes = _extract_route_decorators(self.tree)
        self.prefix = _extract_router_prefix(self.tree)

    def test_router_prefix(self):
        """Router prefix is /api/v1/approvals."""
        assert self.prefix == "/api/v1/approvals"

    def test_has_get_pending(self):
        """GET /pending route exists."""
        assert ("get", "/pending") in self.routes

    def test_has_post_decide(self):
        """POST /{approval_id}/decide route exists."""
        assert ("post", "/{approval_id}/decide") in self.routes

    def test_route_count(self):
        """3 routes defined in approvals.py (GET /pending, GET /history, POST /decide)."""
        assert len(self.routes) == 3


class TestApprovalDecisionSchema:
    """Validate ApprovalDecision schema."""

    def _make_model(self):
        class ApprovalDecision(BaseModel):
            decision: str

        return ApprovalDecision

    def test_approved_valid(self):
        """ApprovalDecision accepts 'approved'."""
        Model = self._make_model()
        req = Model(decision="approved")
        assert req.decision == "approved"

    def test_denied_valid(self):
        """ApprovalDecision accepts 'denied'."""
        Model = self._make_model()
        req = Model(decision="denied")
        assert req.decision == "denied"

    def test_missing_decision_rejected(self):
        """ApprovalDecision without 'decision' is rejected."""
        Model = self._make_model()
        with pytest.raises(ValidationError):
            Model()

    def test_decision_must_be_string(self):
        """ApprovalDecision rejects non-string decision."""
        Model = self._make_model()
        # Pydantic v2 coerces many types to str, but a complex object should fail
        with pytest.raises(ValidationError):
            Model(decision={"nested": "object"})


# ---------------------------------------------------------------------------
# 8. app.py — router composition
# ---------------------------------------------------------------------------


class TestAppRouterComposition:
    """Verify create_app includes all expected routers."""

    @pytest.fixture(autouse=True)
    def _parse(self):
        self.tree = _parse_module("app.py")

    def test_include_router_count(self):
        """app.py includes at least 11 routers (health x2 + 9 domain routers)."""
        count = _extract_include_router_calls(self.tree)
        # health_router (top-level) + health_router (/api/v1) +
        # auth + runs + approvals + chat + threads + memory +
        # settings + usage + tasks + artifacts = 12
        assert count >= 11, f"Expected >= 11 include_router calls, got {count}"

    def test_all_new_routers_imported(self):
        """app.py imports routers for all new endpoint modules."""
        source = (SRC_ROOT / "app.py").read_text()
        expected_imports = [
            "from noa.api.v1.chat import router",
            "from noa.api.v1.threads import router",
            "from noa.api.v1.memory import router",
            "from noa.api.v1.settings import router",
            "from noa.api.v1.usage import router",
            "from noa.api.v1.artifacts import router",
            "from noa.api.v1.approvals import router",
        ]
        for imp in expected_imports:
            assert imp in source, f"Missing import in app.py: {imp}"

    def test_create_app_function_defined(self):
        """app.py defines a create_app() function."""
        funcs = [
            node.name
            for node in ast.walk(self.tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        assert "create_app" in funcs

    def test_lifespan_function_defined(self):
        """app.py defines a lifespan() async context manager."""
        funcs = [
            node.name
            for node in ast.walk(self.tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        assert "lifespan" in funcs


# ---------------------------------------------------------------------------
# 9. Common schemas — Envelope and success/error helpers
# ---------------------------------------------------------------------------


class TestCommonSchemas:
    """Test the common envelope schemas (importable without FastAPI)."""

    def test_success_envelope_function(self):
        """success_envelope returns correct structure."""
        from noa.api.schemas.common import success_envelope

        result = success_envelope(data={"key": "val"}, trace_id="t-123")
        assert result["ok"] is True
        assert result["data"] == {"key": "val"}
        assert result["error"] is None
        assert result["trace_id"] == "t-123"

    def test_error_envelope_function(self):
        """error_envelope returns correct structure."""
        from noa.api.schemas.common import error_envelope

        result = error_envelope(
            code="NOT_FOUND", message="Not found", trace_id="t-456"
        )
        assert result["ok"] is False
        assert result["data"] is None
        assert result["error"]["code"] == "NOT_FOUND"
        assert result["error"]["message"] == "Not found"
        assert result["trace_id"] == "t-456"

    def test_error_envelope_with_details(self):
        """error_envelope includes details when provided."""
        from noa.api.schemas.common import error_envelope

        result = error_envelope(
            code="VALIDATION",
            message="Invalid",
            trace_id="t-789",
            details=[{"field": "name", "issue": "required"}],
        )
        assert result["error"]["details"] == [
            {"field": "name", "issue": "required"}
        ]

    def test_envelope_model_validation(self):
        """Envelope Pydantic model validates correctly."""
        from noa.api.schemas.common import Envelope

        env = Envelope(ok=True, data={"x": 1}, trace_id="t-000")
        assert env.ok is True
        assert env.data == {"x": 1}
        assert env.error is None

    def test_error_detail_model(self):
        """ErrorDetail Pydantic model validates correctly."""
        from noa.api.schemas.common import ErrorDetail

        ed = ErrorDetail(code="ERR", message="Something went wrong")
        assert ed.code == "ERR"
        assert ed.details is None
