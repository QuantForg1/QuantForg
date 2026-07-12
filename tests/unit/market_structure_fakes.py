"""Helpers and fakes for market-structure unit tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.market_data.candle import Candle
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.models import StructureSnapshot
from app.domain.value_objects.identity import SymbolCode


def make_candle(
    *,
    index: int,
    high: str,
    low: str,
    close: str | None = None,
    open_: str | None = None,
    symbol: str = "EURUSD",
    timeframe: Timeframe = Timeframe.M15,
    start: datetime | None = None,
) -> Candle:
    base = start or datetime(2026, 1, 1, tzinfo=UTC)
    open_time = base + timedelta(minutes=15 * index)
    close_time = open_time + timedelta(minutes=15)
    o = open_ if open_ is not None else low
    c = close if close is not None else high
    return Candle.create(
        symbol_code=symbol,
        timeframe=timeframe,
        open_time=open_time,
        close_time=close_time,
        open=o,
        high=high,
        low=low,
        close=c,
        volume="1",
    )


def uptrend_series() -> list[Candle]:
    """Synthetic series with clear swing highs/lows and a late BOS.

    Pattern (left=right=1):
    - swing high @1 (12)
    - swing low @3 (7)
    - swing high @5 (13) HH
    - swing low @7 (8.5) HL
    - closes above 13 at bar 8 → BOS in uptrend
    """
    rows = [
        ("10", "8", "9"),
        ("12", "9", "11.5"),  # swing high
        ("11", "8.5", "10"),
        ("9", "7", "7.5"),  # swing low
        ("10", "8", "9.5"),
        ("13", "9", "12.5"),  # HH
        ("12", "10", "11"),
        ("11", "8.5", "9"),  # HL
        ("14", "10", "13.5"),  # breaks prior high 13
    ]
    return [
        make_candle(index=i, high=h, low=low, close=c, open_=low)
        for i, (h, low, c) in enumerate(rows)
    ]


class InMemoryPriceSeries:
    def __init__(self, candles: list[Candle]) -> None:
        self._candles = list(candles)

    async def get_candles(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
        *,
        limit: int = 500,
    ) -> list[Candle]:
        filtered = [
            c
            for c in self._candles
            if c.symbol_code == symbol_code and c.timeframe == timeframe
        ]
        return filtered[-limit:]


class InMemoryStructureRepository:
    def __init__(self) -> None:
        self.items: list[StructureSnapshot] = []

    async def save_snapshot(self, snapshot: StructureSnapshot) -> None:
        self.items.append(snapshot)

    async def get_latest_snapshot(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
    ) -> StructureSnapshot | None:
        for snapshot in reversed(self.items):
            if snapshot.symbol_code == symbol_code and snapshot.timeframe == timeframe:
                return snapshot
        return None
