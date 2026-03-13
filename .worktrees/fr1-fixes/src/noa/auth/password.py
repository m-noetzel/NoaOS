"""Password hashing with bcrypt — SPEC.md SS5.1.

Uses passlib's bcrypt backend for password hashing and verification.
"""

from __future__ import annotations

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Return a bcrypt hash of *password*."""
    result: str = _pwd_context.hash(password)
    return result


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if *plain_password* matches *hashed_password*."""
    result: bool = _pwd_context.verify(plain_password, hashed_password)
    return result
