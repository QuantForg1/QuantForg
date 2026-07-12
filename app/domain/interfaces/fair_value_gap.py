"""Ports for the Fair Value Gap Engine.

Why these ports exist
---------------------
They isolate market structure, order-block context, price history, and
snapshot persistence from the orchestrating engine. SQL/REST/MT5 adapters
are out of scope.

``PriceHistoryPort`` and ``MarketStructurePort`` are re-exported from the
liquidity interfaces module (identical contracts).
"""

from __future__ import annotations

from typing import Protocol

from app.domain.fair_value_gap.models import FairValueGapSnapshot
from app.domain.interfaces.liquidity import (
    MarketStructurePort,
    PriceHistoryPort,
)
from app.domain.market_data.timeframe import Timeframe
from app.domain.order_block.models import OrderBlockSnapshot
from app.domain.value_objects.identity import SymbolCode

__all__ = [
    "FairValueGapRepositoryPort",
    "MarketStructurePort",
    "OrderBlockSnapshotPort",
    "PriceHistoryPort",
]


class OrderBlockSnapshotPort(Protocol):
    """Provides the latest order-block snapshot for confluence checks.

    Why it exists
    -------------
    FVG quality may consider nearby order blocks without owning OB computation.
    """

    async def get_latest_snapshot(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
    ) -> OrderBlockSnapshot | None:
        """Load the newest order-block snapshot, if any."""
        ...


class FairValueGapRepositoryPort(Protocol):
    """Persists and loads immutable FVG snapshots.

    Why it exists
    -------------
    Snapshot durability is optional. No SQL in this sprint.
    """

    async def save_snapshot(self, snapshot: FairValueGapSnapshot) -> None:
        """Persist an FVG snapshot."""
        ...

    async def get_latest_snapshot(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
    ) -> FairValueGapSnapshot | None:
        """Load the newest snapshot for symbol/timeframe, if any."""
        ...
