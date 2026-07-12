"""Cryptographic utility functions.

These helpers wrap the Python standard library and Fernet so call sites stay
consistent and easy to audit. They do not implement authentication flows.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from cryptography.fernet import Fernet, InvalidToken


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


def _fernet_from_secret(secret: str) -> Fernet:
    """Derive a Fernet key from an application secret (e.g. SECRET_KEY)."""
    if len(secret) < 32:
        msg = "Encryption secret must be at least 32 characters"
        raise ValueError(msg)
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str, *, secret_key: str) -> str:
    """Encrypt ``plaintext`` for at-rest storage. Returns a URL-safe token."""
    if not plaintext:
        msg = "Cannot encrypt an empty secret"
        raise ValueError(msg)
    token = _fernet_from_secret(secret_key).encrypt(plaintext.encode("utf-8"))
    return token.decode("ascii")


def decrypt_secret(token: str, *, secret_key: str) -> str:
    """Decrypt a token produced by :func:`encrypt_secret`."""
    if not token:
        msg = "Cannot decrypt an empty token"
        raise ValueError(msg)
    try:
        plaintext = _fernet_from_secret(secret_key).decrypt(token.encode("ascii"))
    except InvalidToken as exc:
        msg = "Failed to decrypt secret payload"
        raise ValueError(msg) from exc
    return plaintext.decode("utf-8")


def credential_hint(secret: str, *, visible: int = 0) -> str:
    """Return a non-reversible hint for UI display (never the secret itself)."""
    cleaned = secret.strip()
    if not cleaned:
        return ""
    if visible <= 0:
        return f"••••{len(cleaned)}"
    suffix = cleaned[-visible:] if len(cleaned) >= visible else cleaned
    return f"••••{suffix}"
