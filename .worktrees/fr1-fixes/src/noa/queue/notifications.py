"""User notification service — SPEC.md §17.3.

Provides a simple interface for queue state change notifications.
Concrete delivery mechanism (websocket, SSE, push) is deferred to
a later phase. This module defines the contract only.
"""

from __future__ import annotations

import uuid
from typing import Any


class NotificationService:
    """Notify users of queue state changes.

    Integration contract:
    - notify(event, task_id, detail) -> None
    - Events: task_queued, task_started, task_completed, task_failed,
      task_cancelled
    """

    async def notify(
        self,
        event: str,
        task_id: uuid.UUID,
        detail: str = "",
        **kwargs: Any,
    ) -> None:
        """Send a notification about a queue state change.

        Args:
            event: Event type (e.g. 'task_queued', 'task_failed').
            task_id: The UUID of the affected task.
            detail: Human-readable detail string.
            **kwargs: Additional context for the notification.

        Concrete delivery is deferred. This base implementation is a
        no-op that can be subclassed for websocket/SSE/push delivery.
        """
