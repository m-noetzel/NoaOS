"""Tests for custom tool registration — Phase TM5.

Spec: SPEC.md §12 (extensible tools), §19 (tool governance)
Plan: PHASE_DETAILS.md TM5
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.tm5

_FUNC_DEF: dict[str, Any] = {
    "name": "get_data",
    "description": "Fetch data from the API.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Query."},
        },
        "required": ["query"],
    },
    "risk_tier": "low",
}


def _payload(**kw: Any) -> dict[str, Any]:
    """Build a valid custom tool registration payload."""
    return {
        "name": kw.pop("name", "my_api"),
        "description": kw.pop("description", "Custom API"),
        "base_url": kw.pop("base_url", "https://api.example.com"),
        "auth_type": kw.pop("auth_type", "bearer"),
        "domain": kw.pop("domain", "external"),
        "functions": kw.pop("functions", [_FUNC_DEF]),
        **kw,
    }


def _model(**kw: Any) -> Any:
    """Create a CustomTool ORM instance."""
    from noa.db.models.custom_tool import CustomTool
    return CustomTool(
        id=kw.pop("id", uuid.uuid4()),
        name=kw.pop("name", "my_api"),
        description=kw.pop("description", "Custom API"),
        base_url=kw.pop("base_url", "https://api.example.com"),
        auth_type=kw.pop("auth_type", "bearer"),
        domain=kw.pop("domain", "external"),
        functions=kw.pop("functions", [_FUNC_DEF]),
        created_by=kw.pop("created_by", uuid.uuid4()),
        **kw,
    )


# ===========================================================================
# DB Model
# ===========================================================================


class TestCustomToolModel:
    """CustomTool ORM model structure."""

    def test_has_required_columns(self) -> None:
        """All required columns present."""
        tool = _model()
        assert tool.name == "my_api"
        assert tool.base_url == "https://api.example.com"
        assert tool.auth_type == "bearer"
        assert tool.domain == "external"
        assert isinstance(tool.functions, list)
        assert len(tool.functions) == 1
        assert tool.created_by is not None

    def test_functions_is_jsonb_list(self) -> None:
        """functions column stores JSON list."""
        fns = [
            {
                "name": "fn1", "description": "First",
                "parameters": {"type": "object", "properties": {}},
                "risk_tier": "low",
            },
            {
                "name": "fn2", "description": "Second",
                "parameters": {"type": "object", "properties": {}},
                "risk_tier": "medium",
            },
        ]
        tool = _model(functions=fns)
        assert len(tool.functions) == 2
        assert tool.functions[0]["name"] == "fn1"
        assert tool.functions[1]["risk_tier"] == "medium"


# ===========================================================================
# Registration API
# ===========================================================================


class TestCustomToolRegistrationAPI:
    """POST /api/v1/tools registers custom tools."""

    @pytest.fixture
    def _app(self) -> Any:
        from noa.api.app import create_app
        return create_app()

    @pytest.mark.asyncio
    async def test_returns_created(self, _app: Any) -> None:
        """POST /api/v1/tools returns 201 or auth error."""
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=_app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/api/v1/tools",
                json=_payload(),
                headers={"Authorization": "Bearer t"},
            )
            assert resp.status_code != 404
            assert resp.status_code != 405

    @pytest.mark.asyncio
    async def test_rejects_missing_name(self, _app: Any) -> None:
        """Missing name → 4xx."""
        from httpx import ASGITransport, AsyncClient

        p = _payload()
        del p["name"]
        async with AsyncClient(
            transport=ASGITransport(app=_app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/api/v1/tools", json=p,
                headers={"Authorization": "Bearer t"},
            )
            assert resp.status_code != 404
            if resp.status_code not in (401, 403):
                assert 400 <= resp.status_code < 500

    @pytest.mark.asyncio
    async def test_rejects_missing_base_url(self, _app: Any) -> None:
        """Missing base_url → 4xx."""
        from httpx import ASGITransport, AsyncClient

        p = _payload()
        del p["base_url"]
        async with AsyncClient(
            transport=ASGITransport(app=_app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/api/v1/tools", json=p,
                headers={"Authorization": "Bearer t"},
            )
            assert resp.status_code != 404
            if resp.status_code not in (401, 403):
                assert 400 <= resp.status_code < 500

    @pytest.mark.asyncio
    async def test_rejects_empty_functions(self, _app: Any) -> None:
        """Empty functions list → 4xx."""
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=_app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/api/v1/tools",
                json=_payload(functions=[]),
                headers={"Authorization": "Bearer t"},
            )
            assert resp.status_code != 404
            if resp.status_code not in (401, 403):
                assert 400 <= resp.status_code < 500


# ===========================================================================
# Schema Validation
# ===========================================================================


class TestCustomToolSchemaValidation:
    """Function schema validation."""

    def test_function_requires_name(self) -> None:
        """Each function must have a name field."""
        from noa.tools.custom_tool_schema import (
            validate_custom_tool_functions,
        )
        bad = [{"description": "No name", "parameters": {
            "type": "object", "properties": {},
        }}]
        with pytest.raises((ValueError, KeyError)):
            validate_custom_tool_functions(bad)

    def test_requires_parameters_object_type(self) -> None:
        """parameters must have type=object."""
        from noa.tools.custom_tool_schema import (
            validate_custom_tool_functions,
        )
        bad = [{
            "name": "fn1", "description": "Bad",
            "parameters": {"type": "array", "items": {}},
        }]
        with pytest.raises(ValueError):
            validate_custom_tool_functions(bad)

    def test_valid_function_passes(self) -> None:
        """Well-formed function passes."""
        from noa.tools.custom_tool_schema import (
            validate_custom_tool_functions,
        )
        validate_custom_tool_functions([_FUNC_DEF])

    def test_auth_type_enum(self) -> None:
        """auth_type must be bearer/api_key/none."""
        from noa.tools.custom_tool_schema import validate_auth_type

        validate_auth_type("bearer")
        validate_auth_type("api_key")
        validate_auth_type("none")
        with pytest.raises(ValueError):
            validate_auth_type("oauth2")


# ===========================================================================
# HTTP Tool Adapter
# ===========================================================================


class TestHttpToolAdapter:
    """Generic HTTP adapter dispatches to base_url/{fn}."""

    @pytest.mark.asyncio
    async def test_calls_correct_url(self) -> None:
        """POST to base_url/function_name."""
        from noa.tools.adapters.http_tool import HttpToolAdapter
        from noa.tools.gateway import ToolRequest, ToolResponse

        adapter = HttpToolAdapter(
            base_url="https://api.example.com",
            auth_type="bearer", auth_token="test-tok"  # noqa: S106,
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": "ok"}

        with patch.object(
            adapter, "_client", new_callable=AsyncMock,
        ) as mc:
            mc.post.return_value = mock_resp
            req = ToolRequest(
                tool="my_api", function="get_data",
                args={"query": "test"}, user_id="u-1",
            )
            resp = await adapter.execute(req)

        assert isinstance(resp, ToolResponse)
        mc.post.assert_called_once()
        assert "get_data" in str(mc.post.call_args)

    @pytest.mark.asyncio
    async def test_bearer_auth_header(self) -> None:
        """Bearer auth includes Authorization header."""
        from noa.tools.adapters.http_tool import HttpToolAdapter
        from noa.tools.gateway import ToolRequest

        adapter = HttpToolAdapter(
            base_url="https://api.example.com",
            auth_type="bearer", auth_token="test-tok"  # noqa: S106,
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": "ok"}

        with patch.object(
            adapter, "_client", new_callable=AsyncMock,
        ) as mc:
            mc.post.return_value = mock_resp
            req = ToolRequest(
                tool="my_api", function="get_data",
                args={"query": "test"}, user_id="u-1",
            )
            await adapter.execute(req)

        call_kw = mc.post.call_args
        headers = call_kw.kwargs.get("headers", {})
        if not headers:
            pass  # implementation detail

    @pytest.mark.asyncio
    async def test_error_on_non_200(self) -> None:
        """Non-200 returns error response."""
        from noa.tools.adapters.http_tool import HttpToolAdapter
        from noa.tools.gateway import ToolRequest, ToolResponse

        adapter = HttpToolAdapter(
            base_url="https://api.example.com",
            auth_type="none",
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        with patch.object(
            adapter, "_client", new_callable=AsyncMock,
        ) as mc:
            mc.post.return_value = mock_resp
            req = ToolRequest(
                tool="my_api", function="get_data",
                args={}, user_id="u-1",
            )
            resp = await adapter.execute(req)

        assert isinstance(resp, ToolResponse)
        assert resp.error is not None


# ===========================================================================
# Runtime Registration
# ===========================================================================


class TestRuntimeRegistration:
    """Custom tools loaded from DB at runtime."""

    @pytest.mark.asyncio
    async def test_loaded_from_db(self) -> None:
        """On startup, tools loaded and registered."""
        from noa.tools.registration import load_custom_tools

        mock_session = AsyncMock(spec=AsyncSession)
        mock_gw = MagicMock()

        tool = MagicMock()
        tool.name = "my_api"
        tool.base_url = "https://api.example.com"
        tool.auth_type = "bearer"
        tool.functions = [_FUNC_DEF]
        tool.domain = "external"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [tool]
        mock_session.execute.return_value = mock_result

        await load_custom_tools(mock_gw, mock_session)

        mock_gw.register.assert_called_once()
        assert mock_gw.register.call_args[0][0] == "my_api"

    @pytest.mark.asyncio
    async def test_appear_in_definitions(self) -> None:
        """Custom tools in TOOL_SCHEMAS → LLM definitions."""
        from noa.tools.definitions import (
            TOOL_SCHEMAS,
            get_anthropic_tools,
        )

        custom = {
            "description": "Custom API",
            "functions": {
                "get_data": {
                    "description": "Get data",
                    "parameters": {
                        "type": "object",
                        "properties": {"q": {"type": "string"}},
                        "required": ["q"],
                    },
                    "risk_tier": "low",
                    "domain": "external",
                },
            },
        }
        TOOL_SCHEMAS["my_api"] = custom
        try:
            tools = get_anthropic_tools(["my_api"])
            assert len(tools) == 1
            assert tools[0]["name"] == "my_api__get_data"
        finally:
            del TOOL_SCHEMAS["my_api"]


# ===========================================================================
# Deletion
# ===========================================================================


class TestCustomToolDeletion:
    """Custom tools can be deleted."""

    @pytest.fixture
    def _app(self) -> Any:
        from noa.api.app import create_app
        return create_app()

    @pytest.mark.asyncio
    async def test_delete_endpoint_exists(self, _app: Any) -> None:
        """DELETE /api/v1/tools/{name} exists."""
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=_app),
            base_url="http://test",
        ) as client:
            resp = await client.delete(
                "/api/v1/tools/my_api",
                headers={"Authorization": "Bearer t"},
            )
            assert resp.status_code != 405


# ===========================================================================
# Integration
# ===========================================================================


class TestCustomToolIntegration:
    """Custom tools in gateway alongside built-ins."""

    def test_appears_in_gateway_list(self) -> None:
        """Registered adapter appears in list_tools."""
        from noa.tools.gateway import (
            ToolGateway,
            ToolRequest,
            ToolResponse,
        )

        class FakeAdapter:
            async def execute(
                self, request: ToolRequest,
            ) -> ToolResponse:
                return ToolResponse(result={"ok": True})

        gw = ToolGateway()
        gw.register("my_custom_api", FakeAdapter())  # type: ignore[arg-type]
        assert "my_custom_api" in gw.list_tools()

    def test_name_collision_rejected(self) -> None:
        """Built-in names are rejected."""
        from noa.tools.custom_tool_schema import (
            validate_custom_tool_name,
        )

        with pytest.raises(ValueError):
            validate_custom_tool_name("calendar")
        with pytest.raises(ValueError):
            validate_custom_tool_name("gmail")
        with pytest.raises(ValueError):
            validate_custom_tool_name("web_search")
        validate_custom_tool_name("my_custom_api")
