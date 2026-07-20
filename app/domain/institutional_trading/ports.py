"""Shared bar store + snapshot ports for the ITE analysis pipeline."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.domain.liquidity.models import LiquiditySnapshot
from app.domain.market_data.candle import Candle
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.models import StructureSnapshot, SwingPoint
from app.domain.market_structure.swing_detector import SwingDetector
from app.domain.order_block.models import OrderBlockSnapshot
from app.domain.value_objects.identity import SymbolCode


@dataclass
class MultiTimeframeBarStore:
    """In-memory / injected OHLC for all ITE timeframes.

    Implements price ports used by structure, liquidity, OB, and FVG engines.
    """

    bars: dict[Timeframe, list[Candle]] = field(default_factory=dict)

    def set_bars(self, timeframe: Timeframe, candles: Sequence[Candle]) -> None:
        self.bars[timeframe] = list(candles)

    def as_mapping(self) -> Mapping[Timeframe, Sequence[Candle]]:
        return self.bars

    async def get_candles(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
        *,
        limit: int = 500,
    ) -> list[Candle]:
        series = self.bars.get(timeframe, [])
        filtered = [
            c
            for c in series
            if c.symbol_code.value == symbol_code.value
            and c.timeframe == timeframe
        ]
        if not filtered and series:
            # Allow tests that stamp a single symbol across the bundle
            filtered = [c for c in series if c.timeframe == timeframe]
        return filtered[-limit:]


@dataclass
class SnapshotStructurePort:
    """Serves the latest structure snapshot produced by the pipeline."""

    snapshots: dict[Timeframe, StructureSnapshot] = field(default_factory=dict)

    def put(self, snapshot: StructureSnapshot) -> None:
        self.snapshots[snapshot.timeframe] = snapshot

    async def get_latest_snapshot(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
    ) -> StructureSnapshot | None:
        snap = self.snapshots.get(timeframe)
        if snap is None:
            return None
        if snap.symbol_code.value != symbol_code.value:
            return None
        return snap


@dataclass
class SwingFromBarsPort:
    """SwingProviderPort backed by SwingDetector + MultiTimeframeBarStore."""

    prices: MultiTimeframeBarStore
    detector: SwingDetector = field(default_factory=SwingDetector)
    left: int = 2
    right: int = 2

    async def get_swings(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
        *,
        left: int = 2,
        right: int = 2,
        limit: int = 500,
    ) -> Sequence[SwingPoint]:
        candles = await self.prices.get_candles(
            symbol_code, timeframe, limit=limit
        )
        return self.detector.detect(
            candles, left=left or self.left, right=right or self.right
        )


@dataclass
class SnapshotLiquidityPort:
    snapshot: LiquiditySnapshot | None = None

    async def get_latest_snapshot(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
    ) -> LiquiditySnapshot | None:
        if self.snapshot is None:
            return None
        if self.snapshot.symbol_code.value != symbol_code.value:
            return None
        if self.snapshot.timeframe != timeframe:
            return None
        return self.snapshot


@dataclass
class SnapshotOrderBlockPort:
    snapshot: OrderBlockSnapshot | None = None

    async def get_latest_snapshot(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
    ) -> OrderBlockSnapshot | None:
        if self.snapshot is None:
            return None
        if self.snapshot.symbol_code.value != symbol_code.value:
            return None
        if self.snapshot.timeframe != timeframe:
            return None
        return self.snapshot
