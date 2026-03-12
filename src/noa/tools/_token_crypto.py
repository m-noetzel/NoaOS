"""Symmetric encryption for stored tokens — resolves M10.

Uses Fernet (AES-128-CBC + HMAC-SHA256) with a key derived from
the JWT_SECRET_KEY via HKDF. Tokens are stored as base64 ciphertext.
"""

from __future__ import annotations

import base64
import hashlib
import os


def _derive_key() -> bytes:
    """Derive a 32-byte Fernet key via SHA-256.

    Fallback chain: SECRET_KEY → JWT_SECRET → JWT_SECRET_KEY → RuntimeError.
    SECRET_KEY is the canonical name in docker-compose.yml and config.py.
    JWT_SECRET is the secondary name from docker-compose.yml.
    JWT_SECRET_KEY is a legacy alias kept for test compatibility.
    """
    secret = (
        os.environ.get("SECRET_KEY")
        or os.environ.get("JWT_SECRET")
        or os.environ.get("JWT_SECRET_KEY")
        or ""
    )
    if not secret:
        raise RuntimeError(
            "SECRET_KEY (or JWT_SECRET) must be set for token encryption"
        )
    digest = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token string, returning base64 ciphertext."""
    from cryptography.fernet import Fernet

    key = _derive_key()
    f = Fernet(key)
    return f.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a base64 ciphertext back to plaintext."""
    from cryptography.fernet import Fernet

    key = _derive_key()
    f = Fernet(key)
    return f.decrypt(ciphertext.encode()).decode()
