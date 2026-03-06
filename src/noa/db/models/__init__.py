"""SQLAlchemy ORM models for Noa control plane.

All models share a common declarative Base.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all Noa models."""


# Import all models so Base.metadata knows about them.
from noa.db.models.approval import Approval  # noqa: E402, F401
from noa.db.models.artifact import Artifact  # noqa: E402, F401
from noa.db.models.audit import AuditLog  # noqa: E402, F401
from noa.db.models.conversation import Conversation, Message  # noqa: E402, F401
from noa.db.models.run import Run, RunEvent  # noqa: E402, F401
from noa.db.models.session import AuthSession  # noqa: E402, F401
from noa.db.models.task_queue import TaskQueue  # noqa: E402, F401
from noa.db.models.usage import UsageStats  # noqa: E402, F401
from noa.db.models.tool_call_log import ToolCallLog  # noqa: E402, F401
from noa.db.models.user import User  # noqa: E402, F401
