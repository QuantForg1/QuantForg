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
async def test_refuses_insufficient_bars(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.domain.institutional_trading.ai_scalping.universe_discovery as ud

    monkeypatch.setattr(ud, "_CATALOGUE_CACHE", None)
    adapter = MagicMock()
    adapter.list_symbols.return_value = [
        SimpleNamespace(code="XAUUSD_i", description="Gold", digits=3)
    ]
    adapter.copy_rates_from_pos.return_value = [_rate(Timeframe.M5, 0)] * 10
    ctx = await build_ite_cycle_market_context(adapter)
    assert ctx.ok is False
    assert "Insufficient" in ctx.reason


@pytest.mark.unit
@pytest.mark.asyncio
async def test_refuses_zero_equity(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.domain.institutional_trading.ai_scalping.universe_discovery as ud

    monkeypatch.setattr(ud, "_CATALOGUE_CACHE", None)
    adapter = MagicMock()
    adapter.list_symbols.return_value = [
        SimpleNamespace(code="XAUUSD_i", description="Gold", digits=3)
    ]

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


def _ready_adapter(*, bars=None, tick=True, equity: Decimal = Decimal("10000")):
    adapter = MagicMock()
    adapter.client = SimpleNamespace(is_connected=True, session_mode="attached")
    adapter.list_symbols.return_value = [
        SimpleNamespace(code="XAUUSD_i", description="Gold", digits=3),
        SimpleNamespace(code="EURUSD_i", description="EURUSD", digits=5),
    ]

    def _bars(symbol, tf, start, count):
        if callable(bars):
            return bars(symbol, tf, start, count)
        return [_rate(tf, i) for i in range(count)]

    adapter.copy_rates_from_pos.side_effect = _bars
    if tick is True:
        adapter.latest_tick.return_value = SimpleNamespace(
            bid=Decimal("2300"),
            ask=Decimal("2300.4"),
            mid=Decimal("2300.2"),
            volume=Decimal("1"),
            timestamp=datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
        )
    elif tick is None:
        adapter.latest_tick.return_value = None
    else:
        adapter.latest_tick.return_value = tick
    adapter.account_info.return_value = MT5AccountInfo(
        login=1,
        name="t",
        server="s",
        equity=equity,
        balance=equity,
        free_margin=equity,
    )
    adapter.list_positions.return_value = []
    adapter.history_deals = None
    return adapter


def _patch_analyze(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_analyze(*_a, **_k):
        return SimpleNamespace(
            symbol="XAUUSD_i",
            atr=Decimal("1"),
            spread=Decimal("0.4"),
            session=SimpleNamespace(
                session=SimpleNamespace(value="london"), allowed=True
            ),
        )

    monkeypatch.setattr(
        "app.application.services.ite_cycle_market_context."
        "InstitutionalTradingAnalysisService.analyze_bars",
        _fake_analyze,
    )


@pytest.mark.unit
@pytest.mark.trading_core
@pytest.mark.asyncio
async def test_optional_h4_failure_does_not_block_scalping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.domain.institutional_trading.ai_scalping.universe_discovery as ud

    monkeypatch.setattr(ud, "_CATALOGUE_CACHE", None)
    _patch_analyze(monkeypatch)

    def _bars(symbol, tf, start, count):
        if tf == Timeframe.H4:
            raise RuntimeError("H4 gateway timeout")
        return [_rate(tf, i) for i in range(count)]

    ctx = await build_ite_cycle_market_context(_ready_adapter(bars=_bars))
    assert ctx.ok is True
    assert ctx.diagnostics.get("bars", {}).get("H4", {}).get("required") is False
    assert "H1" in (ctx.diagnostics.get("required_timeframes") or [])
    assert "H4" not in (ctx.diagnostics.get("required_timeframes") or [])


@pytest.mark.unit
@pytest.mark.trading_core
@pytest.mark.asyncio
async def test_missing_tick_is_symbol_context_not_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.domain.institutional_trading.ai_scalping.universe_discovery as ud

    monkeypatch.setattr(ud, "_CATALOGUE_CACHE", None)
    ctx = await build_ite_cycle_market_context(_ready_adapter(tick=None))
    assert ctx.ok is False
    assert "SYMBOL_CONTEXT_NOT_READY:MISSING_TICK" in ctx.reason


@pytest.mark.unit
@pytest.mark.trading_core
@pytest.mark.asyncio
async def test_missing_required_timeframe_is_not_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.domain.institutional_trading.ai_scalping.universe_discovery as ud

    monkeypatch.setattr(ud, "_CATALOGUE_CACHE", None)

    def _bars(symbol, tf, start, count):
        if tf == Timeframe.M15:
            return [_rate(tf, i) for i in range(10)]
        return [_rate(tf, i) for i in range(count)]

    ctx = await build_ite_cycle_market_context(_ready_adapter(bars=_bars))
    assert ctx.ok is False
    assert "SYMBOL_CONTEXT_NOT_READY" in ctx.reason
    assert "M15" in ctx.reason
    assert "Insufficient" in ctx.reason


@pytest.mark.unit
@pytest.mark.trading_core
@pytest.mark.asyncio
async def test_scan_purpose_skips_history_deals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.domain.institutional_trading.ai_scalping.universe_discovery as ud

    monkeypatch.setattr(ud, "_CATALOGUE_CACHE", None)
    _patch_analyze(monkeypatch)
    adapter = _ready_adapter()
    adapter.history_deals = MagicMock(side_effect=AssertionError("scan must not load deals"))
    ctx = await build_ite_cycle_market_context(adapter, purpose="scan")
    assert ctx.ok is True
    adapter.history_deals.assert_not_called()
