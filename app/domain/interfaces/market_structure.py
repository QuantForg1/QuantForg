"""Ports for the Market Structure Engine.

Why these ports exist
---------------------
They isolate price-series access, swing detection, trend classification, and
snapshot persistence from the orchestrating engine. SQL/REST/MT5 adapters
are out of scope — this sprint defines contracts and in-domain services only.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.domain.market_data.candle import Candle
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.models import (
    StructureNode,
    StructureSnapshot,
    SwingPoint,
    TrendState,
)
from app.domain.value_objects.identity import SymbolCode


class PriceSeriesPort(Protocol):
    """Provides ordered OHLCV bars for structure analysis.

    Why it exists
    -------------
    Structure algorithms need a price series without knowing whether bars
    come from memory, files, or a future venue adapter.
    """

    async def get_candles(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
        *,
        limit: int = 500,
    ) -> Sequence[Candle]:
        """Return candles oldest→newest, up to ``limit`` bars."""
        ...


class SwingDetectorPort(Protocol):
    """Detects swing highs/lows from a candle series.

    Why it exists
    -------------
    Allows alternate swing algorithms (fractal strength, zigzag, …) behind
    one contract. Implementations must not emit trade signals.
    """

    def detect(
        self,
        candles: Sequence[Candle],
        *,
        left: int = 2,
        right: int = 2,
    ) -> tuple[SwingPoint, ...]:
        """Return confirmed swing points ordered by bar index ascending."""
        ...


class TrendAnalyzerPort(Protocol):
    """Classifies trend direction from structure nodes.

    Why it exists
    -------------
    Separates trend classification policy from structure sequencing so both
    can evolve independently.
    """

    def classify(
        self,
        nodes: Sequence[StructureNode],
        *,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
    ) -> TrendState:
        """Return a :class:`TrendState` for the given structure sequence."""
        ...


class StructureRepositoryPort(Protocol):
    """Persists and loads immutable structure snapshots.

    Why it exists
    -------------
    Snapshot durability is optional for analysis runs. The port defines the
    contract; SQL adapters arrive later. No SQL in this sprint.
    """

    async def save_snapshot(self, snapshot: StructureSnapshot) -> None:
        """Persist a structure snapshot."""
        ...

    async def get_latest_snapshot(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
    ) -> StructureSnapshot | None:
        """Load the newest snapshot for symbol/timeframe, if any."""
        ...
