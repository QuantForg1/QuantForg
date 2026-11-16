"""Worker account snapshot: real MT5 values only, nothing invented."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from services.mt5_worker_agent.account_snapshot import build_account_snapshot

pytestmark = [pytest.mark.unit]

NOW = datetime(2026, 10, 22, 10, 0, tzinfo=UTC)


class _FakeMT5:
    def __init__(self, *, trade_mode: int = 0, tick: bool = True) -> None:
        self._mode = trade_mode
        self._tick = tick

    def account_info(self):
        return SimpleNamespace(trade_mode=self._mode, balance=1000.0, equity=990.5)

    def symbol_info_tick(self, _symbol: str):
        return SimpleNamespace(bid=4000.0, ask=4000.2) if self._tick else None

    def symbol_info(self, _symbol: str):
        return SimpleNamespace(trade_contract_size=100.0)

    def positions_get(self):
        return ()

    def history_deals_get(self, _a, _b):
        return (
            SimpleNamespace(
                ticket=7,
                time=1,
                type=0,
                entry=1,
                volume=0.01,
                profit=-2.5,
                commission=0.0,
                swap=0.0,
                fee=0.0,
            ),
        )


def test_snapshot_reads_mode_quote_positions_and_deals() -> None:
    snap = build_account_snapshot(_FakeMT5(), "XAUUSD", now=NOW)
    assert snap["trade_mode"] == "demo"
    assert snap["equity"] == "990.5"
    assert snap["bid"] == "4000.0" and snap["ask"] == "4000.2"
    assert snap["contract_size"] == "100.0"
    assert snap["open_positions"] == 0
    assert snap["deals_today"][0]["profit"] == "-2.5"
    assert "commission_source" not in snap  # never assumed


def test_real_account_is_reported_as_real() -> None:
    assert (
        build_account_snapshot(_FakeMT5(trade_mode=2), "XAUUSD")["trade_mode"] == "real"
    )


def test_missing_quote_is_left_out() -> None:
    snap = build_account_snapshot(_FakeMT5(tick=False), "XAUUSD", now=NOW)
    assert "bid" not in snap and "ask" not in snap


def test_verified_commission_is_labelled() -> None:
    snap = build_account_snapshot(
        _FakeMT5(), "XAUUSD", now=NOW, verified_commission_usd="0.00"
    )
    assert snap["commission_source"] == "verified_account_tariff"
    assert snap["commission_usd"] == "0.00"
