"""Unit tests for secret encryption helpers."""

from __future__ import annotations

import pytest

from core.security.crypto import (
    credential_hint,
    decrypt_secret,
    encrypt_secret,
    hash_value,
    verify_hash,
)

_KEY = "encryption-test-secret-key-32chars-minimum!!"


@pytest.mark.unit
class TestSecretEncryption:
    def test_round_trip(self) -> None:
        token = encrypt_secret("broker-password", secret_key=_KEY)
        assert token != "broker-password"
        assert decrypt_secret(token, secret_key=_KEY) == "broker-password"

    def test_wrong_key_fails(self) -> None:
        token = encrypt_secret("secret", secret_key=_KEY)
        with pytest.raises(ValueError):
            decrypt_secret(token, secret_key="x" * 40)

    def test_hint_never_includes_secret(self) -> None:
        hint = credential_hint("hunter2")
        assert "hunter2" not in hint
        assert hint.startswith("••••")

    def test_hash_helpers_still_work(self) -> None:
        digest = hash_value("payload", salt="s")
        assert verify_hash("payload", digest, salt="s")
