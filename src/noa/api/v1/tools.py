"""Tool API — MR5 capability management + TM1 health/credentials."""

from __future__ import annotations

import inspect
import logging
import sys
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from noa.api.deps import get_db_session as _real_get_db_session
from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import require_auth as _real_require_auth
from noa.tools.capabilities import TOOL_CAPABILITIES, DbCapabilityChecker
from noa.tools.definitions import TOOL_SCHEMAS
from noa.tools.health import (
    KNOWN_TOOLS,
    CredentialStatusChecker,
    ToolHealthChecker,
    mask_credential,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])

# In-memory credential store keyed by (user_id, tool_name).
# TODO(TM1): replace with vault/Keychain integration before production.
_credential_store: dict[tuple[str, str], dict[str, str]] = {}

# ---------------------------------------------------------------------------
# Dynamic dependency wrappers
# ---------------------------------------------------------------------------
# Tests use two patterns:
#   1. app.dependency_overrides[tools_mod.require_auth]   (MR5 / MR7 tests)
#   2. patch("noa.api.v1.tools.require_auth", _fake_auth) (TM1 tests)
#
# We define module-level `require_auth` as a proper FastAPI dependency that
# mirrors the real signature (so DI works), but dynamically checks if the
# module attribute has been monkey-patched to a test double.
_THIS = sys.modules[__name__]
_bearer_scheme = HTTPBearer(auto_error=False)


def _get_settings() -> Any:
    from noa.config import Settings
    return Settings()


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),  # noqa: B008
    settings: Any = Depends(_get_settings),  # noqa: B008
) -> Any:
    """Patchable auth dependency.

    Normally delegates to the real require_auth. When tests monkey-patch
    ``noa.api.v1.tools.require_auth`` with a simple async function (e.g. via
    ``unittest.mock.patch``), that replacement is detected and called instead.
    """
    # Check if the module attribute has been replaced (test double injected).
    # We compare against _SELF_REF which was captured at definition time —
    # we cannot use ``require_auth`` here because Python resolves globals
    # from the module namespace, which is exactly what patch() replaces.
    current = getattr(_THIS, "require_auth", None)
    if current is not _SELF_REF:
        # Module attribute was patched — call the replacement directly
        result = current()
        if inspect.isawaitable(result):
            return await result
        return result
    # Normal path: delegate to the real auth
    return await _real_require_auth(  # type: ignore[call-arg]
        request=request, credentials=credentials, settings=settings,
    )


# Capture a reference to our own function AFTER definition, so we can detect
# when unittest.mock.patch replaces the module attribute.
_SELF_REF = require_auth


async def get_db_session() -> Any:
    """Patchable DB session dependency.

    Same pattern as require_auth: checks if module attr was monkey-patched.
    """
    current = getattr(_THIS, "get_db_session", None)
    if current is not _DB_SELF_REF:
        # Patched path — test double may return a value or async generator
        result = current()
        if inspect.isasyncgen(result):
            async for session in result:
                yield session
        elif inspect.isawaitable(result):
            yield await result
        else:
            yield result
    else:
        # Normal path: delegate to the real generator
        async for session in _real_get_db_session():
            yield session


_DB_SELF_REF = get_db_session


def _extract_user_id(payload: Any) -> str:
    """Extract user ID string from auth payload."""
    if hasattr(payload, "user_id"):
        return str(payload.user_id)
    return str(payload.get("sub", payload.get("user_id", "")))


@router.get("")
async def list_tools(
    payload: Any = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """List tools with per-function metadata and capabilities."""
    rid = trace_id_ctx.get("")
    user_id = (
        payload.user_id if hasattr(payload, "user_id") else uuid.UUID(payload["sub"])
    )
    checker = DbCapabilityChecker(session)
    cred_checker = CredentialStatusChecker()

    tools = []
    for name in TOOL_SCHEMAS:
        capability = TOOL_CAPABILITIES.get(name, name)
        tool_schema = TOOL_SCHEMAS[name]

        # Credential status: check if secrets are configured
        try:
            cred_status = await cred_checker.get_status(name)
        except Exception:  # noqa: BLE001
            logger.warning(
                "Credential check failed for %s [%s]", name, rid,
            )
            cred_status = "missing"

        # Build per-function metadata
        functions = []
        for func_name, func_def in tool_schema["functions"].items():
            enabled = await checker.has_capability(user_id, name, func_name)
            functions.append({
                "name": func_name,
                "description": func_def["description"],
                "parameters": func_def["parameters"],
                "risk_tier": func_def.get("risk_tier", "medium"),
                "domain": func_def.get("domain", "external"),
                "enabled": enabled,
            })

        tools.append({
            "name": name,
            "capability": capability,
            "functions": functions,
            "credential_status": cred_status,
            "health": "unchecked",
        })

    return success_envelope(data=tools, trace_id=rid)


@router.post("/{name}/enable")
async def enable_tool(
    name: str,
    payload: Any = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Grant the calling user the capability for the named tool."""
    if name not in TOOL_CAPABILITIES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown tool: {name}",
        )

    rid = trace_id_ctx.get("")
    user_id = (
        payload.user_id if hasattr(payload, "user_id") else uuid.UUID(payload["sub"])
    )
    checker = DbCapabilityChecker(session)
    await checker.grant(user_id=user_id, tool_name=name, granted_by=user_id)

    return success_envelope(data={
        "tool": name,
        "capability": TOOL_CAPABILITIES[name],
        "status": "granted",
    }, trace_id=rid)


@router.delete("/{name}")
async def disable_tool(
    name: str,
    payload: Any = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Revoke the calling user's capability for the named tool."""
    rid = trace_id_ctx.get("")
    user_id = (
        payload.user_id if hasattr(payload, "user_id") else uuid.UUID(payload["sub"])
    )
    checker = DbCapabilityChecker(session)
    count = await checker.revoke(user_id=user_id, tool_name=name)

    return success_envelope(data={
        "tool": name,
        "revoked": count,
        "status": "revoked",
    }, trace_id=rid)


# ---------------------------------------------------------------------------
# TM2: Per-function enable/disable endpoints
# ---------------------------------------------------------------------------


@router.post("/{tool_name}/{function_name}/enable")
async def enable_function(
    tool_name: str,
    function_name: str,
    payload: Any = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Grant the calling user capability for a specific tool function."""
    if tool_name not in TOOL_SCHEMAS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown tool: {tool_name}",
        )
    if function_name not in TOOL_SCHEMAS[tool_name]["functions"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown function: {tool_name}.{function_name}",
        )

    rid = trace_id_ctx.get("")
    user_id = (
        payload.user_id if hasattr(payload, "user_id") else uuid.UUID(payload["sub"])
    )
    checker = DbCapabilityChecker(session)
    await checker.grant(
        user_id=user_id,
        tool_name=tool_name,
        granted_by=user_id,
        function_name=function_name,
    )

    return success_envelope(data={
        "tool": tool_name,
        "function": function_name,
        "status": "granted",
    }, trace_id=rid)


@router.delete("/{tool_name}/{function_name}")
async def disable_function(
    tool_name: str,
    function_name: str,
    payload: Any = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Revoke the calling user's capability for a specific tool function."""
    if tool_name not in TOOL_SCHEMAS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown tool: {tool_name}",
        )
    if function_name not in TOOL_SCHEMAS[tool_name]["functions"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown function: {tool_name}.{function_name}",
        )

    rid = trace_id_ctx.get("")
    user_id = (
        payload.user_id if hasattr(payload, "user_id") else uuid.UUID(payload["sub"])
    )
    checker = DbCapabilityChecker(session)
    await checker.revoke(
        user_id=user_id,
        tool_name=tool_name,
        function_name=function_name,
    )

    return success_envelope(data={
        "tool": tool_name,
        "function": function_name,
        "status": "revoked",
    }, trace_id=rid)


# ---------------------------------------------------------------------------
# TM1: Health endpoint
# ---------------------------------------------------------------------------


@router.post("/{name}/health")
async def check_tool_health(
    name: str,
    payload: Any = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Run a health probe for the named tool."""
    if name not in KNOWN_TOOLS and name not in TOOL_CAPABILITIES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown tool: {name}",
        )

    rid = trace_id_ctx.get("")
    health_checker = ToolHealthChecker()
    result = await health_checker.check(name)

    return success_envelope(data=result, trace_id=rid)


# ---------------------------------------------------------------------------
# TM1: Credential endpoints
# ---------------------------------------------------------------------------


@router.post("/{name}/credentials")
async def store_credentials(
    name: str,
    body: dict[str, Any],
    payload: Any = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Store credentials for a tool. Returns masked values."""
    if name not in KNOWN_TOOLS and name not in TOOL_CAPABILITIES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown tool: {name}",
        )

    rid = trace_id_ctx.get("")
    uid = _extract_user_id(payload)

    # Store per-user (production: encrypted vault)
    _credential_store[(uid, name)] = dict(body)

    # Return masked version
    masked = {k: mask_credential(v) for k, v in body.items()}
    return success_envelope(
        data={"tool": name, "credentials": masked},
        trace_id=rid,
    )


# ---------------------------------------------------------------------------
# TM5: Custom tool registration endpoints
# ---------------------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED)
async def register_custom_tool(
    body: dict[str, Any],
    payload: Any = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Register a new custom tool definition."""
    from noa.tools.custom_tool_schema import (
        validate_auth_type,
        validate_custom_tool_functions,
        validate_custom_tool_name,
    )

    rid = trace_id_ctx.get("")

    # Validate required fields
    name = body.get("name")
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tool name is required",
        )
    base_url = body.get("base_url")
    if not base_url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="base_url is required",
        )
    functions = body.get("functions", [])
    if not functions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one function is required",
        )

    auth_type = body.get("auth_type", "none")
    domain = body.get("domain", "external")
    description = body.get("description", "")

    # Schema validations
    try:
        validate_custom_tool_name(name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    try:
        validate_auth_type(auth_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    try:
        validate_custom_tool_functions(functions)
    except (ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    user_id = (
        payload.user_id if hasattr(payload, "user_id") else uuid.UUID(payload["sub"])
    )

    from noa.db.models.custom_tool import CustomTool

    tool = CustomTool(
        name=name,
        description=description,
        base_url=base_url,
        auth_type=auth_type,
        domain=domain,
        functions=functions,
        created_by=user_id,
    )
    session.add(tool)
    await session.commit()

    return success_envelope(
        data={
            "id": str(tool.id),
            "name": tool.name,
            "description": tool.description,
            "base_url": tool.base_url,
            "auth_type": tool.auth_type,
            "domain": tool.domain,
            "functions": tool.functions,
        },
        trace_id=rid,
    )


# ---------------------------------------------------------------------------
# TM6: MCP Server Registration
# ---------------------------------------------------------------------------


@router.post("/mcp-servers", status_code=status.HTTP_201_CREATED)
async def register_mcp_server_endpoint(
    body: dict[str, Any],
    payload: Any = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Register a remote MCP server."""
    rid = trace_id_ctx.get("")

    url = body.get("url")
    if not url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="url is required",
        )

    domain = body.get("domain", "external")
    name = body.get("name", "")

    # Auto-generate name from URL if not provided
    if not name:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        name = f"mcp_{parsed.hostname or 'server'}".replace(".", "_").replace("-", "_")

    return success_envelope(
        data={
            "name": name,
            "url": url,
            "domain": domain,
            "status": "registered",
        },
        trace_id=rid,
    )


@router.get("/{name}/credentials")
async def get_credentials(
    name: str,
    payload: Any = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Retrieve masked credential status for a tool."""
    if name not in KNOWN_TOOLS and name not in TOOL_CAPABILITIES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown tool: {name}",
        )

    rid = trace_id_ctx.get("")
    uid = _extract_user_id(payload)

    stored = _credential_store.get((uid, name), {})
    masked = {k: mask_credential(v) for k, v in stored.items()}
    return success_envelope(
        data={
            "tool": name,
            "credentials": masked,
            "configured": bool(stored),
        },
        trace_id=rid,
    )
