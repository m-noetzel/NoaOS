"""Capability-based tool permissions.

Maps tool names to required capability strings and provides
a checker protocol + DB-backed implementation.
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from noa.db.models.tool_capability import ToolCapability

# Static mapping: tool_name -> required capability string (dot notation).
TOOL_CAPABILITIES: dict[str, str] = {
    "web_search": "search.read",
    "calendar": "calendar.write",
    "gmail": "gmail.send",
    "notion": "notion.read",
}


@runtime_checkable
class CapabilityChecker(Protocol):
    """Protocol for checking tool capabilities."""

    async def has_capability(
        self, user_id: uuid.UUID, tool_name: str,
    ) -> bool: ...

    async def grant(
        self,
        user_id: uuid.UUID,
        tool_name: str,
        granted_by: uuid.UUID | None = None,
    ) -> None: ...

    async def revoke(
        self, user_id: uuid.UUID, tool_name: str,
    ) -> int: ...


class DbCapabilityChecker:
    """DB-backed capability checker using SQLAlchemy async sessions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def has_capability(
        self, user_id: uuid.UUID, tool_name: str,
    ) -> bool:
        cap_str = TOOL_CAPABILITIES.get(tool_name)
        if cap_str is None:
            # Tool not in capabilities map — deny by default (H7)
            return False
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
    ) -> None:
        cap_str = TOOL_CAPABILITIES.get(tool_name, tool_name)
        record = ToolCapability(
            user_id=user_id,
            tool_name=tool_name,
            capability=cap_str,
            granted_by=granted_by,
        )
        self._session.add(record)
        await self._session.commit()

    async def revoke(
        self, user_id: uuid.UUID, tool_name: str,
    ) -> int:
        stmt = delete(ToolCapability).where(
            ToolCapability.user_id == user_id,
            ToolCapability.tool_name == tool_name,
        )
        cursor_result = await self._session.execute(stmt)
        await self._session.commit()
        rc: int = getattr(cursor_result, "rowcount", 0)
        return rc
