"""Unit tests — gateway session adopt + market context diagnostics."""

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
from app.infrastructure.brokers.mt5.gateway_client import GatewayMT5Client


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
def test_require_connected_adopts_existing_session() -> None:
    client = GatewayMT5Client(
        base_url="https://gateway.example",
        token="test-token",
    )
    assert client.is_connected is False
    client.adopt_existing_session = MagicMock(return_value=True)  # type: ignore[method-assign]
    client._require_connected()
    assert client.adopt_existing_session.called


@pytest.mark.unit
def test_require_connected_raises_when_adopt_fails() -> None:
    client = GatewayMT5Client(
        base_url="https://gateway.example",
        token="test-token",
    )
    client.adopt_existing_session = MagicMock(return_value=False)  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="not connected"):
        client._require_connected()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_market_context_adopts_then_loads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gw = MagicMock()
    gw.is_connected = False
    gw.session_mode = "none"

    def _adopt() -> bool:
        gw.is_connected = True
        gw.session_mode = "attached"
        return True

    gw.adopt_existing_session.side_effect = _adopt
    adapter = MagicMock()
    adapter.client = gw

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
        login=42,
        name="demo",
        server="Weltrade-Demo",
        equity=Decimal("10000"),
        balance=Decimal("10000"),
        free_margin=Decimal("9000"),
        margin=Decimal("1000"),
        leverage=100,
        trade_mode="demo",
    )
    adapter.list_positions.return_value = []

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

    ctx = await build_ite_cycle_market_context(adapter)
    assert ctx.ok is True
    assert ctx.diagnostics.get("connection") == "ADOPTED"
    assert ctx.diagnostics.get("ticks") == "LIVE"
    assert ctx.diagnostics.get("snapshot") == "OK"
    assert ctx.diagnostics.get("account") == "OK"
    assert ctx.bars_loaded and ctx.bars_loaded.get("M5", 0) >= 50
