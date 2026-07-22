"""Unit tests — ITE cycle market context builder (no fabricated equity)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.application.services.ite_cycle_market_context import (
    build_ite_cycle_market_context,
)
from app.domain.entities.mt5 import MT5AccountInfo
from app.domain.entities.mt5_market import MT5Rate
from app.domain.market_data.timeframe import Timeframe


def _rate(tf: Timeframe, i: int) -> MT5Rate:
    base = Decimal("2300") + Decimal(i)
    return MT5Rate(
        symbol="XAUUSD",
        timeframe=tf,
        open_time=datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
        open=base,
        high=base + Decimal("1"),
        low=base - Decimal("1"),
        close=base + Decimal("0.5"),
        tick_volume=10,
        real_volume=Decimal("1"),
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_refuses_without_adapter() -> None:
    ctx = await build_ite_cycle_market_context(None)
    assert ctx.ok is False
    assert "adapter" in ctx.reason.lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_refuses_insufficient_bars() -> None:
    adapter = MagicMock()
    adapter.copy_rates_from_pos.return_value = [_rate(Timeframe.M5, 0)] * 10
    ctx = await build_ite_cycle_market_context(adapter)
    assert ctx.ok is False
    assert "Insufficient" in ctx.reason


@pytest.mark.unit
@pytest.mark.asyncio
async def test_refuses_zero_equity(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = MagicMock()

    def _bars(symbol, tf, start, count):
        return [_rate(tf, i) for i in range(count)]

    adapter.copy_rates_from_pos.side_effect = _bars
    adapter.latest_tick.return_value = SimpleNamespace(
        bid=Decimal("2300"), ask=Decimal("2300.4"), mid=Decimal("2300.2")
    )
    adapter.account_info.return_value = MT5AccountInfo(
        login=1,
        name="t",
        server="s",
        equity=Decimal("0"),
        free_margin=Decimal("0"),
    )
    adapter.list_positions.return_value = []

    async def _fake_analyze(*_a, **_k):
        return SimpleNamespace(symbol="XAUUSD", atr=Decimal("1"), spread=Decimal("0.4"))

    monkeypatch.setattr(
        "app.application.services.ite_cycle_market_context."
        "InstitutionalTradingAnalysisService.analyze_bars",
        _fake_analyze,
    )
    ctx = await build_ite_cycle_market_context(adapter)
    assert ctx.ok is False
    assert "equity" in ctx.reason.lower()
