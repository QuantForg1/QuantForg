"""Cryptographic utility functions.

These helpers wrap the Python standard library so call sites stay
consistent and easy to audit. They do not implement authentication flows.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets


def generate_secret(length: int = 64) -> str:
    """Generate a URL-safe random secret of the given byte length.

    Parameters
    ----------
    length:
        Number of random bytes before URL-safe encoding. Must be >= 32.
    """
    if length < 32:
        msg = "Secret length must be at least 32 bytes"
        raise ValueError(msg)
    return secrets.token_urlsafe(length)


def hash_value(value: str, *, salt: str | None = None) -> str:
    """Return a hex-encoded SHA-256 digest of ``value``.

    When ``salt`` is provided it is prepended before hashing. Prefer
    dedicated password-hashing libraries (e.g. argon2) for credentials;
    this helper is for non-credential integrity checks only.
    """
    payload = f"{salt}{value}" if salt is not None else value
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_hash(value: str, expected_digest: str, *, salt: str | None = None) -> bool:
    """Constant-time comparison of ``hash_value(value)`` against ``expected_digest``."""
    actual = hash_value(value, salt=salt)
    return hmac.compare_digest(actual, expected_digest)
