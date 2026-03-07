"""Settings repository — async CRUD for UserSettings."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from noa.settings.models import UserSettings


class SettingsRepository:
    """Async CRUD operations for user settings."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: uuid.UUID) -> UserSettings | None:
        """Fetch settings for a user, or None if not configured."""
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self, user_id: uuid.UUID, fields: dict[str, Any],
    ) -> UserSettings:
        """Create or update settings for a user.

        Only fields present in *fields* are updated; missing keys are
        left unchanged on an existing row.
        """
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()

        if row is None:
            row = UserSettings(user_id=user_id, **fields)
            self._session.add(row)
        else:
            for key, value in fields.items():
                setattr(row, key, value)
            row.updated_at = datetime.now(UTC)

        await self._session.flush()
        await self._session.commit()
        return row
