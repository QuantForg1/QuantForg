"""Unit tests for AES-256-GCM credential encryption and rotation."""

from __future__ import annotations

import pytest

from core.security.credential_encryption import (
    CredentialEncryptionService,
    decrypt_aes256_gcm,
    encrypt_aes256_gcm,
    is_aes256_envelope,
)
from core.security.crypto import _fernet_from_secret, decrypt_secret, encrypt_secret

_KEY = "encryption-test-secret-key-32chars-minimum!!"
_PREV = "previous-test-secret-key-32chars-minimum!!!"


@pytest.mark.unit
class TestAes256GcmEncryption:
    def test_round_trip_envelope(self) -> None:
        token = encrypt_aes256_gcm("broker-password", secret_key=_KEY, key_version=2)
        assert is_aes256_envelope(token)
        assert token.startswith("v2:2:")
        assert decrypt_aes256_gcm(token, secret_key=_KEY) == "broker-password"

    def test_encrypt_secret_uses_aes(self) -> None:
        token = encrypt_secret("secret", secret_key=_KEY, key_version=1)
        assert is_aes256_envelope(token)
        assert decrypt_secret(token, secret_key=_KEY) == "secret"

    def test_service_never_exposes_plaintext_in_repr(self) -> None:
        service = CredentialEncryptionService(secret_key=_KEY, key_version=3)
        ciphertext, version = service.encrypt("super-secret")
        assert version == 3
        assert "super-secret" not in service.secure_repr(ciphertext)
        assert service.decrypt(ciphertext) == "super-secret"

    def test_key_rotation_reencrypts_with_new_version(self) -> None:
        old = CredentialEncryptionService(secret_key=_KEY, key_version=1)
        ciphertext, _ = old.encrypt("rotate-me")
        rotated = CredentialEncryptionService(secret_key=_KEY, key_version=5)
        new_token, new_version = rotated.rotate(ciphertext)
        assert new_version == 5
        assert new_token.startswith("v2:5:")
        assert rotated.decrypt(new_token) == "rotate-me"

    def test_previous_keys_decrypt(self) -> None:
        legacy = CredentialEncryptionService(secret_key=_PREV, key_version=1)
        token, _ = legacy.encrypt("legacy-secret")
        current = CredentialEncryptionService(
            secret_key=_KEY,
            key_version=2,
            previous_keys=(_PREV,),
        )
        assert current.decrypt(token) == "legacy-secret"

    def test_legacy_fernet_still_decrypts(self) -> None:
        fernet = _fernet_from_secret(_KEY)
        legacy = fernet.encrypt(b"old-sprint1-secret").decode("ascii")
        assert not is_aes256_envelope(legacy)
        service = CredentialEncryptionService(secret_key=_KEY)
        assert service.decrypt(legacy) == "old-sprint1-secret"
        with pytest.raises(ValueError):
            service.decrypt("not-a-valid-token")
