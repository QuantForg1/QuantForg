"""Live Market Chat — sanitize, channel, rate limit (no network)."""

from __future__ import annotations

import pytest

from app.application.services.market_chat import (
    _enforce_rate_limit,
    _post_buckets,
    normalize_channel,
    sanitize_body,
    sanitize_display_name,
)
from app.domain.exceptions.base import ValidationError


def test_normalize_channel_default_and_valid() -> None:
    assert normalize_channel(None) == "xauusd"
    assert normalize_channel("XAUUSD") == "xauusd"


def test_normalize_channel_rejects_junk() -> None:
    with pytest.raises(ValidationError):
        normalize_channel("../admin")


def test_sanitize_body_trims_and_limits() -> None:
    assert sanitize_body("  hello   world  ") == "hello world"
    with pytest.raises(ValidationError):
        sanitize_body("   ")
    with pytest.raises(ValidationError):
        sanitize_body("x" * 501)


def test_sanitize_display_name_fallback() -> None:
    assert sanitize_display_name("", "trader") == "trader"
    assert sanitize_display_name("  Gold Desk  ", "x") == "Gold Desk"


def test_rate_limit_blocks_burst() -> None:
    _post_buckets.clear()
    uid = "rate-limit-user"
    for _ in range(8):
        _enforce_rate_limit(uid)
    with pytest.raises(ValidationError) as exc:
        _enforce_rate_limit(uid)
    assert exc.value.code == "rate_limited"
