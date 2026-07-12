"""Helpers and fakes for liquidity unit tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.liquidity.models import LiquiditySnapshot
from app.domain.market_data.candle import Candle
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.models import StructureSnapshot, SwingPoint
from app.domain.market_structure.swing_detector import SwingDetector
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


def equal_highs_sweep_series() -> list[Candle]:
    """Series with equal highs at 10 and a later high-sweep reclaim.

    Pattern (left=right=1):
    - swing high @1 (10)
    - swing low @3
    - swing high @5 (10) — equal highs
    - bar @8: high 10.5, close 9.0 → sweeps sell-side pool
    """
    rows = [
        ("9", "7", "8"),
        ("10", "8", "9.5"),  # swing high
        ("9.5", "8", "8.5"),
        ("9", "7", "7.5"),  # swing low
        ("9.5", "8", "9"),
        ("10", "8.5", "9.5"),  # equal high
        ("9.8", "8.8", "9.2"),
        ("9.5", "8.2", "8.5"),  # swing low
        ("10.5", "8.5", "9.0"),  # sweep highs
    ]
    return [
        make_candle(index=i, high=h, low=low, close=c, open_=low)
        for i, (h, low, c) in enumerate(rows)
    ]


def equal_lows_sweep_series() -> list[Candle]:
    """Series with equal lows at 7 and a later low-sweep reclaim."""
    rows = [
        ("9", "7.5", "8"),
        ("10", "8", "9.5"),  # swing high
        ("9", "7", "7.5"),  # swing low 7
        ("9.5", "8", "9"),
        ("10", "8.5", "9.5"),  # swing high
        ("9", "7", "7.8"),  # equal low 7
        ("9.2", "8", "8.5"),
        ("9.5", "8.2", "9"),  # swing high
        ("8.5", "6.5", "7.5"),  # sweep lows (low 6.5, close 7.5 > 7)
    ]
    return [
        make_candle(index=i, high=h, low=low, close=c, open_=low)
        for i, (h, low, c) in enumerate(rows)
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
        filtered = [
            c
            for c in self._candles
            if c.symbol_code == symbol_code and c.timeframe == timeframe
        ]
        return filtered[-limit:]


class InMemorySwingProvider:
    """SwingProviderPort fake wrapping SwingDetector over in-memory candles."""

    def __init__(self, candles: list[Candle]) -> None:
        self._candles = list(candles)
        self._detector = SwingDetector()

    async def get_swings(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
        *,
        left: int = 2,
        right: int = 2,
        limit: int = 500,
    ) -> tuple[SwingPoint, ...]:
        filtered = [
            c
            for c in self._candles
            if c.symbol_code == symbol_code and c.timeframe == timeframe
        ][-limit:]
        return self._detector.detect(filtered, left=left, right=right)


class NullMarketStructure:
    async def get_latest_snapshot(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
    ) -> StructureSnapshot | None:
        return None


class InMemoryLiquidityRepository:
    def __init__(self) -> None:
        self.items: list[LiquiditySnapshot] = []

    async def save_snapshot(self, snapshot: LiquiditySnapshot) -> None:
        self.items.append(snapshot)

    async def get_latest_snapshot(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
    ) -> LiquiditySnapshot | None:
        for snapshot in reversed(self.items):
            if snapshot.symbol_code == symbol_code and snapshot.timeframe == timeframe:
                return snapshot
        return None
