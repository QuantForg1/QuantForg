"""AES-256-GCM credential encryption with key-version rotation.

Envelope format
---------------
``v2:<key_version>:<base64url(nonce || ciphertext||tag)>``

Legacy Fernet tokens (no ``v2:`` prefix) remain decryptable for backward
compatibility with Broker Foundation Sprint 1 rows.
"""

from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass, field

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from core.security.crypto import _fernet_from_secret

_V2_PREFIX = "v2:"
_NONCE_BYTES = 12
_CURRENT_SCHEME = 2


def _aes_key(secret: str, *, key_version: int) -> bytes:
    """Derive a 256-bit AES key from an application secret + version."""
    if len(secret) < 32:
        msg = "Encryption secret must be at least 32 characters"
        raise ValueError(msg)
    material = f"quantforg.credentials.v{key_version}:{secret}".encode()
    return hashlib.sha256(material).digest()


def encrypt_aes256_gcm(
    plaintext: str,
    *,
    secret_key: str,
    key_version: int = 1,
) -> str:
    """Encrypt with AES-256-GCM and return a versioned envelope string."""
    if not plaintext:
        msg = "Cannot encrypt an empty secret"
        raise ValueError(msg)
    if key_version < 1:
        msg = "key_version must be >= 1"
        raise ValueError(msg)
    key = _aes_key(secret_key, key_version=key_version)
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    blob = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
    return f"{_V2_PREFIX}{key_version}:{blob}"


def decrypt_aes256_gcm(token: str, *, secret_key: str) -> str:
    """Decrypt a ``v2:`` AES-256-GCM envelope."""
    if not token.startswith(_V2_PREFIX):
        msg = "Not an AES-256-GCM envelope"
        raise ValueError(msg)
    rest = token[len(_V2_PREFIX) :]
    version_str, _, blob = rest.partition(":")
    if not version_str or not blob:
        msg = "Malformed AES-256-GCM envelope"
        raise ValueError(msg)
    try:
        key_version = int(version_str)
    except ValueError as exc:
        msg = "Invalid key_version in envelope"
        raise ValueError(msg) from exc
    raw = base64.urlsafe_b64decode(blob.encode("ascii"))
    if len(raw) <= _NONCE_BYTES:
        msg = "Ciphertext too short"
        raise ValueError(msg)
    nonce, ciphertext = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
    key = _aes_key(secret_key, key_version=key_version)
    try:
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
    except Exception as exc:
        msg = "Failed to decrypt AES-256-GCM payload"
        raise ValueError(msg) from exc
    return plaintext.decode("utf-8")


def is_aes256_envelope(token: str) -> bool:
    return token.startswith(_V2_PREFIX)


@dataclass(frozen=True, slots=True)
class CredentialEncryptionService:
    """Application-facing encryption service for broker credentials.

    Never logs or returns plaintext. Supports key rotation via
    ``key_version`` and optional ``previous_keys``.
    """

    secret_key: str
    key_version: int = 1
    previous_keys: tuple[str, ...] = field(default_factory=tuple)

    def encrypt(self, plaintext: str) -> tuple[str, int]:
        """Return ``(ciphertext, key_version)``. Never returns plaintext."""
        ciphertext = encrypt_aes256_gcm(
            plaintext,
            secret_key=self.secret_key,
            key_version=self.key_version,
        )
        return ciphertext, self.key_version

    def decrypt(self, token: str) -> str:
        """Decrypt AES-256-GCM or legacy Fernet ciphertext."""
        if is_aes256_envelope(token):
            try:
                return decrypt_aes256_gcm(token, secret_key=self.secret_key)
            except ValueError:
                for prev in self.previous_keys:
                    try:
                        return decrypt_aes256_gcm(token, secret_key=prev)
                    except ValueError:
                        continue
                raise
        # Legacy Fernet (Sprint 1)
        try:
            plaintext = _fernet_from_secret(self.secret_key).decrypt(
                token.encode("ascii")
            )
            return plaintext.decode("utf-8")
        except Exception:
            for prev in self.previous_keys:
                try:
                    plaintext = _fernet_from_secret(prev).decrypt(token.encode("ascii"))
                    return plaintext.decode("utf-8")
                except Exception:  # noqa: S112 — try next rotation key
                    continue
            msg = "Failed to decrypt secret payload"
            raise ValueError(msg) from None

    def rotate(self, token: str) -> tuple[str, int]:
        """Decrypt with any known key and re-encrypt with the current version."""
        plaintext = self.decrypt(token)
        return self.encrypt(plaintext)

    def secure_repr(self, token: str) -> str:
        """Safe serialization for logs/diagnostics — never plaintext."""
        if is_aes256_envelope(token):
            rest = token[len(_V2_PREFIX) :]
            version, _, _ = rest.partition(":")
            return f"v2:key={version}:****"
        return "legacy-fernet:****"
