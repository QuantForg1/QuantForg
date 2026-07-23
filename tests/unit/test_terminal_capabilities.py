"""Unit tests — terminal capability flags from MetaTrader5.terminal_info()."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.mt5_gateway.runtime import (
    _empty_capability_fields,
    _terminal_capability_fields,
)


@pytest.mark.unit
class TestTerminalCapabilities:
    def test_extracts_trade_allowed_and_dlls(self) -> None:
        term = SimpleNamespace(build=5000, trade_allowed=True, dlls_allowed=False)
        caps = _terminal_capability_fields(term)
        assert caps["mt5_autotrading_enabled"] is True
        assert caps["terminal_trade_allowed"] is True
        assert caps["dlls_allowed"] is False
        assert caps["capability_support"]["autotrading"] == "SUPPORTED"
        assert caps["capability_support"]["dll"] == "SUPPORTED"

    def test_missing_attributes_not_supported(self) -> None:
        term = SimpleNamespace(build=5000)
        caps = _terminal_capability_fields(term)
        assert caps["mt5_autotrading_enabled"] is None
        assert caps["dlls_allowed"] is None
        assert caps["capability_support"]["autotrading"] == "NOT_SUPPORTED"
        assert caps["capability_support"]["dll"] == "NOT_SUPPORTED"

    def test_none_terminal(self) -> None:
        caps = _terminal_capability_fields(None)
        assert caps["capability_support"]["autotrading"] == "NOT_SUPPORTED"
        empty = _empty_capability_fields(reason="test")
        assert empty["mt5_autotrading_enabled"] is None
        assert empty["dlls_allowed"] is None
