"""Helpers and fakes for order-block unit tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.liquidity.enums import LiquidityStateKind
from app.domain.liquidity.models import LiquiditySnapshot, LiquidityState
from app.domain.market_data.candle import Candle
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.enums import SwingKind, TrendDirection
from app.domain.market_structure.models import (
    BreakOfStructure,
    StructureSnapshot,
    SwingPoint,
    TrendState,
)
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


def bullish_ob_series() -> list[Candle]:
    """Series with down-close OB then bullish displacement / BOS.

    Bar 3: down-close (order block candidate)
    Bar 5-6: impulse up
    Bar 6 close breaks prior swing high -> BOS context
    Later bars can mitigate or break.
    """
    rows = [
        # i, open, high, low, close
        ("10", "10.5", "9.5", "10.2"),
        ("10.2", "11", "10", "10.8"),  # swing high ~11
        ("10.8", "11", "10.2", "10.4"),
        ("10.4", "10.5", "9.8", "9.9"),  # down-close OB @3
        ("9.9", "10.2", "9.7", "10.1"),
        ("10.1", "11.2", "10", "11.1"),  # displacement
        ("11.1", "12", "11", "11.8"),  # BOS through 11
        ("11.8", "12.1", "11.5", "11.7"),
        ("11.7", "11.9", "10.2", "10.4"),  # mitigates into OB zone
    ]
    return [
        make_candle(index=i, open_=o, high=h, low=low, close=c)
        for i, (o, h, low, c) in enumerate(rows)
    ]


def bullish_ob_then_breaker_series() -> list[Candle]:
    """Bullish OB then close below zone → breaker."""
    base = bullish_ob_series()[:7]
    # Replace mitigation with invalidation close below OB low 9.8
    extra = [
        make_candle(index=7, open_="11.5", high="11.6", low="9.5", close="9.6"),
    ]
    return base + extra


def structure_with_bullish_bos(candles: list[Candle]) -> StructureSnapshot:
    """Build a minimal StructureSnapshot with one UP BOS at bar 6."""
    symbol = candles[0].symbol_code
    tf = candles[0].timeframe
    swing_high = SwingPoint.create(
        symbol_code=symbol,
        timeframe=tf,
        kind=SwingKind.HIGH,
        price=candles[1].high,
        bar_index=1,
        timestamp=candles[1].close_time,
    )
    bos = BreakOfStructure(
        symbol_code=symbol,
        timeframe=tf,
        broken_swing=swing_high,
        break_price=candles[6].close,
        broken_at=candles[6].close_time,
        trend_direction=TrendDirection.UP,
    )
    trend = TrendState(
        symbol_code=symbol,
        timeframe=tf,
        direction=TrendDirection.UP,
        as_of=candles[6].close_time,
        swing_count=1,
    )
    return StructureSnapshot(
        symbol_code=symbol,
        timeframe=tf,
        as_of=candles[6].close_time,
        swings=(swing_high,),
        nodes=(),
        trend=trend,
        breaks_of_structure=(bos,),
        changes_of_character=(),
    )


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


class InMemoryMarketStructure:
    def __init__(self, snapshot: StructureSnapshot | None) -> None:
        self._snapshot = snapshot

    async def get_latest_snapshot(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
    ) -> StructureSnapshot | None:
        if self._snapshot is None:
            return None
        if (
            self._snapshot.symbol_code == symbol_code
            and self._snapshot.timeframe == timeframe
        ):
            return self._snapshot
        return None


class NullLiquiditySnapshot:
    async def get_latest_snapshot(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
    ) -> LiquiditySnapshot | None:
        return None


class EmptyLiquiditySnapshot:
    """Liquidity snapshot with no pools (confluence false)."""

    def __init__(self, symbol: str = "EURUSD") -> None:
        code = SymbolCode.of(symbol)
        self._snap = LiquiditySnapshot(
            symbol_code=code,
            timeframe=Timeframe.M15,
            as_of=datetime(2026, 1, 1, tzinfo=UTC),
            equal_highs=(),
            equal_lows=(),
            pools=(),
            zones=(),
            sweeps=(),
            state=LiquidityState(
                symbol_code=code,
                timeframe=Timeframe.M15,
                kind=LiquidityStateKind.UNKNOWN,
                as_of=datetime(2026, 1, 1, tzinfo=UTC),
            ),
        )

    async def get_latest_snapshot(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
    ) -> LiquiditySnapshot | None:
        return self._snap


class InMemoryOrderBlockRepository:
    def __init__(self) -> None:
        self.items: list[OrderBlockSnapshot] = []

    async def save_snapshot(self, snapshot: OrderBlockSnapshot) -> None:
        self.items.append(snapshot)

    async def get_latest_snapshot(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
    ) -> OrderBlockSnapshot | None:
        for snapshot in reversed(self.items):
            if snapshot.symbol_code == symbol_code and snapshot.timeframe == timeframe:
                return snapshot
        return None
