"""Unit tests — market context fail-closed risk / book facts."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.application.services.ite_cycle_market_context import (
    build_ite_cycle_market_context,
)
from app.application.services.live_account_risk_tracker import (
    reset_live_account_risk_tracker_for_tests,
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


def _ready_adapter(*, history_deals=None, list_positions=None, positions_raise=False):
    import app.domain.institutional_trading.ai_scalping.universe_discovery as ud

    ud._CATALOGUE_CACHE = None
    adapter = MagicMock()
    adapter.client = MagicMock()
    adapter.client.is_connected = True
    adapter.client.session_mode = "attached"
    adapter.list_symbols.return_value = [
        SimpleNamespace(code="XAUUSD_i", description="Gold", digits=3)
    ]

    def _bars(symbol, tf, start, count):
        return [_rate(tf, i) for i in range(count)]

    adapter.copy_rates_from_pos.side_effect = _bars
    adapter.latest_tick.return_value = SimpleNamespace(
        bid=Decimal("2300"),
        ask=Decimal("2300.4"),
        mid=Decimal("2300.2"),
        volume=Decimal("1"),
        timestamp=datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
    )
    adapter.account_info.return_value = MT5AccountInfo(
        login=4242,
        name="demo",
        server="Weltrade-Demo",
        equity=Decimal("10000"),
        balance=Decimal("10000"),
        free_margin=Decimal("9000"),
        margin=Decimal("1000"),
        leverage=100,
        trade_mode="demo",
    )
    if positions_raise:
        adapter.list_positions.side_effect = RuntimeError("book unavailable")
    else:
        adapter.list_positions.return_value = (
            list_positions if list_positions is not None else []
        )
    if history_deals is None:
        # Explicit None — not a MagicMock auto-attr (list(MagicMock()) == []).
        adapter.history_deals = None
        adapter.client.history_deals = None
    else:
        adapter.history_deals = MagicMock(return_value=history_deals)
    return adapter


@pytest.fixture(autouse=True)
def _reset_tracker():
    reset_live_account_risk_tracker_for_tests()
    yield
    reset_live_account_risk_tracker_for_tests()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_history_deals_failure_trips_daily_loss_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _ready_adapter(history_deals=None)

    async def _fake_analyze(*_a, **_k):
        return SimpleNamespace(
            symbol="XAUUSD",
            atr=Decimal("1"),
            spread=Decimal("0.4"),
            session=SimpleNamespace(
                session=SimpleNamespace(value="london"),
                allowed=True,
            ),
        )

    monkeypatch.setattr(
        "app.application.services.ite_cycle_market_context."
        "InstitutionalTradingAnalysisService.analyze_bars",
        _fake_analyze,
    )
    monkeypatch.setattr(
        "app.application.services.mt5_position_truth.force_sync_positions",
        lambda *_a, **_k: SimpleNamespace(
            mt5_positions=0,
            internal_positions=0,
            repaired=False,
            tickets=[],
        ),
    )

    ctx = await build_ite_cycle_market_context(adapter)
    assert ctx.ok is True
    assert ctx.account is not None
    assert ctx.diagnostics.get("daily_pnl_fail_closed") is True
    assert ctx.diagnostics.get("daily_pnl_trusted") is False
    assert ctx.account.daily_pnl == Decimal("0")
    assert ctx.account.daily_pnl != -(ctx.account.equity * Decimal("0.40"))
    assert ctx.diagnostics.get("daily_pnl") is None
    assert ctx.diagnostics.get("daily_loss_source") == "unavailable"
    assert ctx.diagnostics.get("daily_loss_lock") == "UNKNOWN"
    assert ctx.diagnostics.get("lock_changed") is not True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_history_deals_ok_trusts_zero_daily_pnl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _ready_adapter(history_deals=[])

    async def _fake_analyze(*_a, **_k):
        return SimpleNamespace(
            symbol="XAUUSD",
            atr=Decimal("1"),
            spread=Decimal("0.4"),
            session=SimpleNamespace(
                session=SimpleNamespace(value="london"),
                allowed=True,
            ),
        )

    monkeypatch.setattr(
        "app.application.services.ite_cycle_market_context."
        "InstitutionalTradingAnalysisService.analyze_bars",
        _fake_analyze,
    )
    monkeypatch.setattr(
        "app.application.services.mt5_position_truth.force_sync_positions",
        lambda *_a, **_k: SimpleNamespace(
            mt5_positions=0,
            internal_positions=0,
            repaired=False,
            tickets=[],
        ),
    )

    ctx = await build_ite_cycle_market_context(adapter)
    assert ctx.ok is True
    assert ctx.account is not None
    assert ctx.diagnostics.get("daily_pnl_fail_closed") is not True
    assert ctx.diagnostics.get("daily_pnl_trusted") is True
    assert ctx.account.daily_pnl == Decimal("0")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_book_facts_failure_with_open_positions_marks_incomplete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _ready_adapter(history_deals=[], positions_raise=True)

    async def _fake_analyze(*_a, **_k):
        return SimpleNamespace(
            symbol="XAUUSD",
            atr=Decimal("1"),
            spread=Decimal("0.4"),
            session=SimpleNamespace(
                session=SimpleNamespace(value="london"),
                allowed=True,
            ),
        )

    monkeypatch.setattr(
        "app.application.services.ite_cycle_market_context."
        "InstitutionalTradingAnalysisService.analyze_bars",
        _fake_analyze,
    )
    monkeypatch.setattr(
        "app.application.services.mt5_position_truth.force_sync_positions",
        lambda *_a, **_k: SimpleNamespace(
            mt5_positions=2,
            quantforg_positions=2,
            quantforg_tickets=[1, 2],
            internal_positions=2,
            repaired=False,
            tickets=[1, 2],
        ),
    )

    ctx = await build_ite_cycle_market_context(adapter)
    assert ctx.ok is True
    assert ctx.account is not None
    assert ctx.account.open_positions == 2
    assert ctx.diagnostics.get("book_facts_incomplete") is True
    assert ctx.account.open_directions == ()
    assert ctx.account.open_entries == ()
