"""Symmetric encryption for stored tokens — resolves M10.

Uses Fernet (AES-128-CBC + HMAC-SHA256) with a key derived from
the JWT_SECRET_KEY via HKDF. Tokens are stored as base64 ciphertext.
"""

from __future__ import annotations

import base64
import hashlib
import os


def _derive_key() -> bytes:
    """Derive a 32-byte Fernet key from JWT_SECRET_KEY via SHA-256."""
    secret = os.environ.get("JWT_SECRET_KEY", "")
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY must be set for token encryption")
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
