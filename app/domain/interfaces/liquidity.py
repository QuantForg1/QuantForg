"""Ports for the Liquidity Engine.

Why these ports exist
---------------------
They isolate price history, swing access, market-structure context, and
snapshot persistence from the orchestrating engine. SQL/REST/MT5 adapters
are out of scope — this sprint defines contracts and in-domain services only.

Distinct from market_context ``LiquidityProfilePort`` (session regime).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.domain.liquidity.models import LiquiditySnapshot
from app.domain.market_data.candle import Candle
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.models import StructureSnapshot, SwingPoint
from app.domain.value_objects.identity import SymbolCode


class PriceHistoryPort(Protocol):
    """Provides ordered OHLCV history for liquidity analysis.

    Why it exists
    -------------
    Liquidity detection needs bars without knowing the upstream store.
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


class SwingProviderPort(Protocol):
    """Supplies swing points for equal-high / equal-low detection.

    Why it exists
    -------------
    Decouples liquidity analysis from a specific swing algorithm. Typical
    adapters wrap Sprint 6 ``SwingDetector`` or a structure repository.
    """

    async def get_swings(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
        *,
        left: int = 2,
        right: int = 2,
        limit: int = 500,
    ) -> Sequence[SwingPoint]:
        """Return swings oldest→newest for the series."""
        ...


class MarketStructurePort(Protocol):
    """Optional market-structure context for liquidity analysis.

    Why it exists
    -------------
    Lets the liquidity engine read the latest structure snapshot (trend,
    swings) without owning structure computation.
    """

    async def get_latest_snapshot(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
    ) -> StructureSnapshot | None:
        """Load the newest structure snapshot, if any."""
        ...


class LiquidityRepositoryPort(Protocol):
    """Persists and loads immutable liquidity snapshots.

    Why it exists
    -------------
    Snapshot durability is optional. The port defines the contract; SQL
    adapters arrive later. No SQL in this sprint.
    """

    async def save_snapshot(self, snapshot: LiquiditySnapshot) -> None:
        """Persist a liquidity snapshot."""
        ...

    async def get_latest_snapshot(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
    ) -> LiquiditySnapshot | None:
        """Load the newest snapshot for symbol/timeframe, if any."""
        ...
