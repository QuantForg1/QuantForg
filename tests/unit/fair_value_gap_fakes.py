"""Helpers and fakes for fair-value-gap unit tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.fair_value_gap.models import FairValueGapSnapshot
from app.domain.market_data.candle import Candle
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.models import StructureSnapshot
from app.domain.order_block.models import OrderBlockSnapshot
from app.domain.value_objects.identity import SymbolCode


def make_candle(
    *,
    index: int,
    open_: str,
    high: str,
    low: str,
    close: str,
    symbol: str = "EURUSD",
    timeframe: Timeframe = Timeframe.M15,
    start: datetime | None = None,
) -> Candle:
    base = start or datetime(2026, 1, 1, tzinfo=UTC)
    open_time = base + timedelta(minutes=15 * index)
    close_time = open_time + timedelta(minutes=15)
    return Candle.create(
        symbol_code=symbol,
        timeframe=timeframe,
        open_time=open_time,
        close_time=close_time,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume="1",
    )


def bullish_fvg_series() -> list[Candle]:
    """Three-candle bullish FVG then partial fill.

    Bars 0–2 form bullish FVG (right.low 11.2 > left.high 10).
    Zone = [10, 11.2]. Bar 3 dips to 10.5 → partial fill.
    """
    rows = [
        ("9.5", "10", "9", "9.8"),
        ("9.8", "12", "9.7", "11.5"),
        ("11.5", "12.5", "11.2", "12"),
        ("12", "12.2", "10.5", "10.8"),
    ]
    return [
        make_candle(index=i, open_=o, high=h, low=low, close=c)
        for i, (o, h, low, c) in enumerate(rows)
    ]


def bullish_fvg_full_fill_series() -> list[Candle]:
    """Bullish FVG then full fill through gap low."""
    base = bullish_fvg_series()[:3]
    return [
        *base,
        make_candle(index=3, open_="12", high="12.1", low="9.5", close="9.8"),
    ]


def bullish_fvg_invalidate_series() -> list[Candle]:
    """Bullish FVG then close below gap low without needing fill path first."""
    base = bullish_fvg_series()[:3]
    return [
        *base,
        make_candle(index=3, open_="11.5", high="11.6", low="9.4", close="9.5"),
    ]


class InMemoryPriceHistory:
    def __init__(self, candles: list[Candle]) -> None:
        self._candles = list(candles)

    async def get_candles(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
        *,
        limit: int = 500,
    ) -> list[Candle]:
        return [
            c
            for c in self._candles
            if c.symbol_code == symbol_code and c.timeframe == timeframe
        ][-limit:]


class NullMarketStructure:
    async def get_latest_snapshot(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
    ) -> StructureSnapshot | None:
        return None


class NullOrderBlockSnapshot:
    async def get_latest_snapshot(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
    ) -> OrderBlockSnapshot | None:
        return None


class InMemoryFairValueGapRepository:
    def __init__(self) -> None:
        self.items: list[FairValueGapSnapshot] = []

    async def save_snapshot(self, snapshot: FairValueGapSnapshot) -> None:
        self.items.append(snapshot)

    async def get_latest_snapshot(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
    ) -> FairValueGapSnapshot | None:
        for snapshot in reversed(self.items):
            if snapshot.symbol_code == symbol_code and snapshot.timeframe == timeframe:
                return snapshot
        return None
