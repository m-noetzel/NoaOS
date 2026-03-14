"""Tests for MR5: Capability-Based Tool Permissions.

Covers:
- ToolCapability model
- TOOL_CAPABILITIES static dict
- CapabilityChecker protocol + DbCapabilityChecker
- Capability check in dispatch()
- POST /tools/{name}/enable and DELETE /tools/{name} endpoints
"""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

from noa.tools.gateway import ToolGateway, ToolRequest, ToolResponse

# -------------------------------------------------------------------
# Fake adapter for gateway tests
# -------------------------------------------------------------------

class FakeAdapter:
    """Test adapter implementing ToolAdapter protocol."""

    def __init__(
        self,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self._result = result or {"ok": True}
        self._error = error
        self.calls: list[ToolRequest] = []

    async def execute(self, request: ToolRequest) -> ToolResponse:
        self.calls.append(request)
        if self._error:
            return ToolResponse(error=self._error)
        return ToolResponse(result=self._result, provider="fake")


# ===================================================================
# 1. ToolCapability model tests
# ===================================================================


class TestToolCapabilityModel:
    def test_model_instantiation(self) -> None:
        """ToolCapability can be instantiated with required fields."""
        from noa.db.models.tool_capability import ToolCapability

        uid = uuid.uuid4()
        granted_by = uuid.uuid4()
        cap = ToolCapability(
            id=uuid.uuid4(),
            user_id=uid,
            tool_name="web_search",
            capability="search.read",
            granted_at=datetime.now(UTC),
            granted_by=granted_by,
        )
        assert cap.user_id == uid
        assert cap.tool_name == "web_search"
        assert cap.capability == "search.read"
        assert cap.granted_by == granted_by

    def test_model_required_fields(self) -> None:
        """ToolCapability table has expected columns."""
        from noa.db.models.tool_capability import ToolCapability

        mapper = ToolCapability.__table__
        col_names = {c.name for c in mapper.columns}
        assert "id" in col_names
        assert "user_id" in col_names
        assert "tool_name" in col_names
        assert "capability" in col_names
        assert "granted_at" in col_names
        assert "granted_by" in col_names


# ===================================================================
# 2. TOOL_CAPABILITIES dict tests
# ===================================================================


class TestToolCapabilitiesDict:
    def test_all_registered_tools_have_capabilities(self) -> None:
        """Every known tool has an entry in TOOL_CAPABILITIES."""
        from noa.tools.capabilities import TOOL_CAPABILITIES

        known_tools = {"web_search", "calendar", "gmail", "notion"}
        for tool in known_tools:
            assert tool in TOOL_CAPABILITIES, (
                f"Tool '{tool}' missing from TOOL_CAPABILITIES"
            )

    def test_capability_strings_use_dot_notation(self) -> None:
        """All capability strings match pattern word.word."""
        from noa.tools.capabilities import TOOL_CAPABILITIES

        pattern = re.compile(r"^\w+\.\w+$")
        for tool_name, cap in TOOL_CAPABILITIES.items():
            assert pattern.match(cap), (
                f"Capability '{cap}' for tool '{tool_name}' "
                "does not match dot notation"
            )


# ===================================================================
# 3. Capability check in dispatch()
# ===================================================================


class TestDispatchCapabilityCheck:
    def test_dispatch_allowed_when_checker_not_set(self) -> None:
        """Backward compat: no checker means all dispatches proceed."""
        gw = ToolGateway()
        adapter = FakeAdapter()
        gw.register("web_search", adapter)
        # No capability_checker set
        req = ToolRequest(
            tool="web_search", function="search", args={"q": "hi"},
        )
        resp = asyncio.run(gw.dispatch(req))
        assert resp.error is None
        assert len(adapter.calls) == 1

    def test_dispatch_allowed_when_user_id_none(self) -> None:
        """Backward compat: no user_id means dispatch proceeds."""
        from noa.tools.capabilities import CapabilityChecker

        checker = AsyncMock(spec=CapabilityChecker)
        gw = ToolGateway()
        gw.capability_checker = checker
        adapter = FakeAdapter()
        gw.register("web_search", adapter)

        req = ToolRequest(
            tool="web_search", function="search", args={"q": "hi"},
            # user_id not set (defaults to None)
        )
        resp = asyncio.run(gw.dispatch(req))
        assert resp.error is None
        assert len(adapter.calls) == 1
        # Checker should NOT have been called
        checker.has_capability.assert_not_called()

    def test_dispatch_blocked_when_capability_denied(self) -> None:
        """Dispatch returns error when checker denies capability."""
        from noa.tools.capabilities import CapabilityChecker

        checker = AsyncMock(spec=CapabilityChecker)
        checker.has_capability = AsyncMock(return_value=False)

        gw = ToolGateway()
        gw.capability_checker = checker
        adapter = FakeAdapter()
        gw.register("web_search", adapter)

        uid = uuid.uuid4()
        req = ToolRequest(
            tool="web_search", function="search", args={"q": "hi"},
            user_id=uid,
        )
        resp = asyncio.run(gw.dispatch(req))
        assert resp.error is not None
        assert "capability" in resp.error.lower() or "denied" in resp.error.lower()
        assert len(adapter.calls) == 0

    def test_dispatch_allowed_when_capability_granted(self) -> None:
        """Dispatch proceeds when checker grants capability."""
        from noa.tools.capabilities import CapabilityChecker

        checker = AsyncMock(spec=CapabilityChecker)
        checker.has_capability = AsyncMock(return_value=True)

        gw = ToolGateway()
        gw.capability_checker = checker
        adapter = FakeAdapter()
        gw.register("web_search", adapter)

        uid = uuid.uuid4()
        req = ToolRequest(
            tool="web_search", function="search", args={"q": "hi"},
            user_id=uid,
        )
        resp = asyncio.run(gw.dispatch(req))
        assert resp.error is None
        assert len(adapter.calls) == 1

    def test_capability_check_before_dry_run(self) -> None:
        """Capability denial applies even in dry_run mode."""
        from noa.tools.capabilities import CapabilityChecker

        checker = AsyncMock(spec=CapabilityChecker)
        checker.has_capability = AsyncMock(return_value=False)

        gw = ToolGateway()
        gw.capability_checker = checker
        adapter = FakeAdapter()
        gw.register("web_search", adapter)

        uid = uuid.uuid4()
        req = ToolRequest(
            tool="web_search", function="search", args={"q": "hi"},
            user_id=uid,
        )
        resp = asyncio.run(gw.dispatch(req, dry_run=True))
        assert resp.error is not None
        assert "capability" in resp.error.lower() or "denied" in resp.error.lower()


# ===================================================================
# 4. API endpoint tests
# ===================================================================


class TestToolEndpoints:
    def test_enable_endpoint_exists(self) -> None:
        """POST /api/v1/tools/{name}/enable returns non-404."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from noa.api.v1.tools import router
        app = FastAPI()
        app.include_router(router)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/tools/web_search/enable")
        # Should exist (may return 401/422/500 but NOT 404/405)
        assert resp.status_code != 404
        assert resp.status_code != 405

    def test_enable_endpoint_requires_auth(self) -> None:
        """POST /api/v1/tools/{name}/enable needs authentication."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from noa.api.v1.tools import router
        app = FastAPI()
        app.include_router(router)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/tools/web_search/enable")
        # Without auth header, should be 401 or 403
        assert resp.status_code in (401, 403)

    def test_enable_grants_capability(self) -> None:
        """POST /api/v1/tools/{name}/enable returns success on grant."""
        from unittest.mock import MagicMock

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from noa.api.v1 import tools as tools_mod
        from noa.api.v1.tools import router

        app = FastAPI()
        app.include_router(router)

        uid = str(uuid.uuid4())
        payload = {"sub": uid, "type": "access", "sid": str(uuid.uuid4())}

        mock_session = AsyncMock()
        mock_session.add = lambda x: None
        mock_session.commit = AsyncMock()
        # grant() calls execute() to check for existing grant
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_exec_result = MagicMock()
        mock_exec_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_exec_result

        async def fake_db():
            yield mock_session

        app.dependency_overrides[tools_mod.require_auth] = lambda: payload
        app.dependency_overrides[tools_mod.get_db_session] = fake_db

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/tools/web_search/enable")
        assert resp.status_code in (200, 201)

    def test_disable_endpoint_exists(self) -> None:
        """DELETE /api/v1/tools/{name} returns non-404."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from noa.api.v1.tools import router
        app = FastAPI()
        app.include_router(router)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.delete("/api/v1/tools/web_search")
        assert resp.status_code != 404
        assert resp.status_code != 405

    def test_disable_revokes_capability(self) -> None:
        """DELETE /api/v1/tools/{name} returns success on revoke."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from noa.api.v1.tools import router

        app = FastAPI()
        app.include_router(router)

        uid = str(uuid.uuid4())
        payload = {"sub": uid, "type": "access", "sid": str(uuid.uuid4())}

        mock_session = AsyncMock()
        # Mock the delete query result
        mock_result = AsyncMock()
        mock_result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        async def fake_db():
            yield mock_session

        from noa.api.v1 import tools as tools_mod
        app.dependency_overrides[tools_mod.require_auth] = lambda: payload
        app.dependency_overrides[tools_mod.get_db_session] = fake_db

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.delete("/api/v1/tools/web_search")
        assert resp.status_code == 200
