"""Unit tests for security primitives and utilities."""

from __future__ import annotations

import pytest

from core.security.crypto import generate_secret, hash_value, verify_hash
from core.utils.identifiers import new_request_id, new_uuid
from core.utils.timing import Timer


@pytest.mark.unit
class TestCrypto:
    def test_generate_secret_length(self) -> None:
        secret = generate_secret(32)
        assert isinstance(secret, str)
        assert len(secret) > 32

    def test_generate_secret_rejects_short(self) -> None:
        with pytest.raises(ValueError):
            generate_secret(16)

    def test_hash_and_verify(self) -> None:
        digest = hash_value("hello", salt="s")
        assert verify_hash("hello", digest, salt="s")
        assert not verify_hash("world", digest, salt="s")


@pytest.mark.unit
class TestIdentifiers:
    def test_new_uuid_format(self) -> None:
        value = new_uuid()
        assert len(value) == 36
        assert value.count("-") == 4

    def test_request_id_prefix(self) -> None:
        rid = new_request_id()
        assert rid.startswith("req_")
        assert len(rid) == 36  # req_ + 32 hex chars


@pytest.mark.unit
class TestTimer:
    def test_elapsed_positive(self) -> None:
        with Timer() as timer:
            pass
        assert timer.elapsed_ms >= 0.0
