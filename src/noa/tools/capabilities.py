"""Capability-based tool permissions.

Maps tool names to required capability strings and provides
a checker protocol + DB-backed implementation.

TM2: Function-level capability keys (tool__function) for granular grants.
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from noa.db.models.tool_capability import ToolCapability
from noa.tools.definitions import TOOL_SCHEMAS

# Static mapping: tool_name -> required capability string (dot notation).
# Tool-level keys are preserved for backward compatibility.
TOOL_CAPABILITIES: dict[str, str] = {
    "web_search": "search.read",
    "calendar": "calendar.write",
    "gmail": "gmail.send",
    "notion": "notion.read",
}

# TM2: Add function-level capability keys (tool__function -> capability).
# These coexist with tool-level keys for backward compatibility.
for _tool_name, _tool_def in TOOL_SCHEMAS.items():
    _tool_cap = TOOL_CAPABILITIES.get(_tool_name, _tool_name)
    for _func_name in _tool_def["functions"]:
        _key = f"{_tool_name}__{_func_name}"
        if _key not in TOOL_CAPABILITIES:
            TOOL_CAPABILITIES[_key] = _tool_cap


@runtime_checkable
class CapabilityChecker(Protocol):
    """Protocol for checking tool capabilities."""

    async def has_capability(
        self, user_id: uuid.UUID, tool_name: str,
        function_name: str | None = None,
    ) -> bool: ...

    async def grant(
        self,
        user_id: uuid.UUID,
        tool_name: str,
        granted_by: uuid.UUID | None = None,
        function_name: str | None = None,
    ) -> None: ...

    async def revoke(
        self, user_id: uuid.UUID, tool_name: str,
        function_name: str | None = None,
    ) -> int: ...


class DbCapabilityChecker:
    """DB-backed capability checker using SQLAlchemy async sessions.

    TM2: Supports function-level grants via function_name column.
    - function_name=None in a DB row acts as a wildcard (grants all functions).
    - When checking, a match on either a wildcard row or a specific function row
      is sufficient.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def has_capability(
        self,
        user_id: uuid.UUID,
        tool_name: str,
        function_name: str | None = None,
    ) -> bool:
        """Check if user has capability for tool (optionally specific function).

        A wildcard grant (function_name=NULL) covers all functions.
        A function-specific grant covers only that function.
        """
        cap_str = TOOL_CAPABILITIES.get(tool_name)
        if cap_str is None:
            # Tool not in capabilities map -- deny by default (H7)
            return False

        if function_name is not None:
            # Check for wildcard OR specific function match
            stmt = select(ToolCapability).where(
                ToolCapability.user_id == user_id,
                ToolCapability.tool_name == tool_name,
                ToolCapability.capability == cap_str,
                or_(
                    ToolCapability.function_name.is_(None),
                    ToolCapability.function_name == function_name,
                ),
            )
        else:
            # Legacy: check tool-level (any grant for this tool)
            stmt = select(ToolCapability).where(
                ToolCapability.user_id == user_id,
                ToolCapability.tool_name == tool_name,
                ToolCapability.capability == cap_str,
            )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def grant(
        self,
        user_id: uuid.UUID,
        tool_name: str,
        granted_by: uuid.UUID | None = None,
        function_name: str | None = None,
    ) -> None:
        cap_str = TOOL_CAPABILITIES.get(tool_name, tool_name)
        record = ToolCapability(
            user_id=user_id,
            tool_name=tool_name,
            capability=cap_str,
            granted_by=granted_by,
            function_name=function_name,
        )
        self._session.add(record)
        await self._session.commit()

    async def revoke(
        self,
        user_id: uuid.UUID,
        tool_name: str,
        function_name: str | None = None,
    ) -> int:
        """Revoke grants. If function_name is given, only revoke that specific grant."""
        conditions = [
            ToolCapability.user_id == user_id,
            ToolCapability.tool_name == tool_name,
        ]
        if function_name is not None:
            conditions.append(ToolCapability.function_name == function_name)
        stmt = delete(ToolCapability).where(*conditions)
        cursor_result = await self._session.execute(stmt)
        await self._session.commit()
        rc: int = getattr(cursor_result, "rowcount", 0)
        return rc
