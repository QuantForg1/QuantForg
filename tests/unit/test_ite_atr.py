"""Unit tests — ITE ATR helper and snapshot wiring."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.domain.institutional_trading.atr import (
    compute_atr,
    stop_distance_from_atr,
)
from app.domain.market_data.candle import Candle
from app.domain.market_data.timeframe import Timeframe


def _candle(i: int, *, high: str, low: str, close: str) -> Candle:
    from datetime import timedelta

    t0 = datetime(2026, 7, 23, 12, 0, tzinfo=UTC) + timedelta(minutes=15 * i)
    return Candle.create(
        symbol_code="XAUUSD",
        timeframe=Timeframe.M15,
        open_time=t0,
        close_time=t0 + timedelta(minutes=15),
        open=close,
        high=high,
        low=low,
        close=close,
        volume="1",
    )


@pytest.mark.unit
class TestComputeAtr:
    def test_insufficient_bars(self) -> None:
        assert compute_atr([]) is None
        assert compute_atr([_candle(0, high="10", low="9", close="9.5")]) is None

    def test_simple_window(self) -> None:
        # Flat TR=1 for each bar after first → ATR ≈ 1
        bars = [
            _candle(0, high="10", low="9", close="9.5"),
            _candle(1, high="10.5", low="9.5", close="10"),
            _candle(2, high="11", low="10", close="10.5"),
        ]
        atr = compute_atr(bars, period=14)
        assert atr is not None
        assert atr > 0
        stop = stop_distance_from_atr(atr)
        assert stop == (atr * Decimal("1.5")).quantize(Decimal("0.0001"))

    def test_stop_none_when_atr_missing(self) -> None:
        assert stop_distance_from_atr(None) is None
        assert stop_distance_from_atr(Decimal("0")) is None
