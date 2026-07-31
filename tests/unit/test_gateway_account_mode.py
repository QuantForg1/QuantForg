"""Unit tests — MT5 account_mode mapping (demo/contest/real)."""

from __future__ import annotations

import pytest

from services.mt5_gateway.account_mode import map_account_trade_mode


@pytest.mark.unit
class TestMapAccountTradeMode:
    def test_int_modes(self) -> None:
        assert map_account_trade_mode(0) == ("demo", 0)
        assert map_account_trade_mode(1) == ("contest", 1)
        assert map_account_trade_mode(2) == ("real", 2)

    def test_string_digits_and_names(self) -> None:
        assert map_account_trade_mode("2") == ("real", 2)
        assert map_account_trade_mode("real") == ("real", 2)
        assert map_account_trade_mode("ACCOUNT_TRADE_MODE_REAL") == ("real", 2)
        assert map_account_trade_mode("demo") == ("demo", 0)

    def test_enum_like_value(self) -> None:
        class _E:
            value = 2

        assert map_account_trade_mode(_E()) == ("real", 2)

    def test_none_and_unmapped(self) -> None:
        assert map_account_trade_mode(None) == ("unknown", None)
        assert map_account_trade_mode(99) == ("unknown", 99)
        assert map_account_trade_mode("") == ("unknown", None)
