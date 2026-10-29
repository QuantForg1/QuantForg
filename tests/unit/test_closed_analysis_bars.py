"""An unfinished bar must not confirm a swing that fills a target slot."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.institutional_trading.ai_scalping.structure_targets import (
    select_owner_structure_tp,
)
from app.domain.market_data.candle import Candle
from app.domain.market_data.closed_bars import closed_analysis_bars
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.engine import MarketStructureEngine
from app.domain.market_structure.structure_analyzer import StructureAnalyzer
from app.domain.market_structure.swing_detector import SwingDetector
from app.domain.market_structure.trend_classifier import TrendClassifier
from tests.unit.market_structure_fakes import InMemoryPriceSeries

_START = datetime(2026, 6, 2, 12, 0, tzinfo=UTC)
# Highs: a closed far swing at 22, a closed near swing at 15.4, and a nearer
# swing at 15.8 that exists only while the last bar is still forming.
_HIGHS = (
    "10",
    "12",
    "22",
    "11",
    "10",
    "15.4",
    "13",
    "12",
    "15.8",
    "14",
    "13",
)


def _series() -> list[Candle]:
    bars: list[Candle] = []
    for index, high in enumerate(_HIGHS):
        opened = _START + timedelta(minutes=5 * index)
        low = str(Decimal(high) - Decimal("1"))
        bars.append(
            Candle.create(
                symbol_code="EURUSD",
                timeframe=Timeframe.M5,
                open_time=opened,
                close_time=opened + Timeframe.M5.duration,
                open=low,
                high=high,
                low=low,
                close=low,
                volume="1",
            )
        )
    return bars


def _highs(swings: object) -> set[Decimal]:
    found: set[Decimal] = set()
    for swing in swings:  # type: ignore[attr-defined]
        kind = str(getattr(getattr(swing, "kind", None), "value", "")).upper()
        if "HIGH" in kind:
            found.add(swing.price.value)
    return found


def _choice(highs: set[Decimal]):
    return select_owner_structure_tp(
        [(price, "swing_M5") for price in highs],
        entry=Decimal("15"),
        stop_distance=Decimal("2"),
        spread=Decimal("0.2"),
    )


@pytest.mark.unit
def test_forming_bar_is_not_swing_confirmation() -> None:
    bars = _series()
    forming = bars[-1]
    as_of = forming.open_time + timedelta(minutes=2)
    assert forming.close_time > as_of
    assert forming.close_time <= as_of + Timeframe.M5.duration

    raw = _highs(SwingDetector().detect(bars, left=2, right=2))
    assert Decimal("15.8") in raw
    assert Decimal("22") in raw

    closed = closed_analysis_bars(bars, as_of=as_of, timeframe=Timeframe.M5)
    assert closed[-1].open_time < forming.open_time
    confirmed = _highs(SwingDetector().detect(closed, left=2, right=2))
    assert Decimal("15.8") not in confirmed
    assert confirmed == {Decimal("15.4"), Decimal("22")}

    blocked = _choice(raw)
    opened = _choice(confirmed)
    assert blocked.price is None
    assert opened.price == Decimal("22")
    assert opened.level == 2
    assert opened.rr_after_spread is not None
    assert opened.rr_after_spread >= Decimal("1.50")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_structure_engine_drops_the_open_bar() -> None:
    bars = _series()
    forming = bars[-1]
    as_of = forming.open_time + timedelta(minutes=2)
    engine = MarketStructureEngine(
        prices=InMemoryPriceSeries(bars),
        swings=SwingDetector(),
        trends=TrendClassifier(),
        analyzer=StructureAnalyzer(),
        swing_left=2,
        swing_right=2,
    )
    result = await engine.analyze("EURUSD", Timeframe.M5, as_of=as_of)
    assert _highs(result.snapshot.swings) == {Decimal("15.4"), Decimal("22")}


@pytest.mark.unit
def test_broker_clock_lead_drops_only_the_newest_bar() -> None:
    bars = _series()
    as_of = bars[-1].close_time - timedelta(hours=2)
    closed = closed_analysis_bars(bars, as_of=as_of, timeframe=Timeframe.M5)
    assert len(closed) == len(bars) - 1
    assert closed[-1].open_time == bars[-2].open_time
    assert Decimal("15.8") not in _highs(
        SwingDetector().detect(closed, left=2, right=2)
    )
