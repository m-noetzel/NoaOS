"""Declarative base for all Noa ORM models.

Separated into its own module to avoid circular imports when models
outside the ``noa.db.models`` package (e.g. ``noa.settings.models``)
need to reference ``Base``.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all Noa models."""
