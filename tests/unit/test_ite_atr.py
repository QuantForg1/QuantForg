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

    def test_coarse_0_0001_quantize_can_false_fail_fx_hard_min(self) -> None:
        """Document the precision trap this change closes. Floor stays 0.03%."""
        mid = Decimal("0.40")
        raw = Decimal("0.00012")  # ATR% = 0.03 exactly
        assert (raw / mid) * Decimal("100") == Decimal("0.03")
        coarse = raw.quantize(Decimal("0.0001"))
        assert coarse == Decimal("0.0001")
        assert (coarse / mid) * Decimal("100") < Decimal("0.03")

    def test_compute_atr_preserves_fx_percent_at_hard_min(self) -> None:
        # TR = 0.00012 on every bar after the first.
        bars = [_candle(0, high="0.40012", low="0.40000", close="0.40012")]
        for i in range(1, 15):
            prev = bars[-1].close.value
            nxt = prev + Decimal("0.00012")
            bars.append(
                _candle(
                    i,
                    high=str(nxt),
                    low=str(prev),
                    close=str(nxt),
                )
            )
        atr = compute_atr(bars, period=14)
        assert atr is not None
        mid = Decimal("0.40")
        atr_pct = (atr / mid) * Decimal("100")
        assert atr_pct >= Decimal("0.03")
        # Gold-style 0.0001 rounding would have collapsed this under the floor.
        assert atr.quantize(Decimal("0.0001")) < atr or atr >= Decimal("0.00012")
        stop = stop_distance_from_atr(atr)
        assert stop == (atr * Decimal("1.5")).quantize(Decimal("0.0001"))

    def test_fx_hard_min_floor_unchanged(self) -> None:
        from app.domain.institutional_trading.ai_scalping.volatility_gate_v2 import (
            resolve_atr_floors_for_symbol,
        )

        hard, _exc, _std = resolve_atr_floors_for_symbol("NZDUSD_I")
        assert hard == Decimal("0.03")
