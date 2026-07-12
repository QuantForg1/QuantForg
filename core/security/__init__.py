"""Security primitives for QuantForg.

Provides cryptographic helpers and header-based request identity utilities.
Authentication and authorization business rules belong in the application
layer; this package only supplies low-level building blocks.
"""

from core.security.crypto import (
    credential_hint,
    decrypt_secret,
    encrypt_secret,
    generate_secret,
    hash_value,
    verify_hash,
)
from core.security.headers import SecurityHeaders

__all__ = [
    "SecurityHeaders",
    "credential_hint",
    "decrypt_secret",
    "encrypt_secret",
    "generate_secret",
    "hash_value",
    "verify_hash",
]
