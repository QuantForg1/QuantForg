"""Regression: gateway JSON retcode 0 must not become 10013."""

from __future__ import annotations

from app.domain.interfaces.mt5_order import RETCODE_INVALID
from app.infrastructure.brokers.mt5.gateway_client import _mt5_retcode


def test_mt5_retcode_preserves_zero_success() -> None:
    assert _mt5_retcode({"retcode": 0}) == 0
    assert _mt5_retcode({"retcode": 10009}) == 10009
    assert _mt5_retcode({}) == RETCODE_INVALID
    assert _mt5_retcode({"retcode": None}) == RETCODE_INVALID
