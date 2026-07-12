"""Ports for the Order Block Engine.

Why these ports exist
---------------------
They isolate market structure, liquidity context, price history, and snapshot
persistence from the orchestrating engine. SQL/REST/MT5 adapters are out of
scope — contracts and in-domain services only.

``PriceHistoryPort`` and ``MarketStructurePort`` are re-exported from the
liquidity interfaces module (identical contracts) so consumers share one
structural type.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.interfaces.liquidity import (
    MarketStructurePort,
    PriceHistoryPort,
)
from app.domain.liquidity.models import LiquiditySnapshot
from app.domain.market_data.timeframe import Timeframe
from app.domain.order_block.models import OrderBlockSnapshot
from app.domain.value_objects.identity import SymbolCode

__all__ = [
    "LiquiditySnapshotPort",
    "MarketStructurePort",
    "OrderBlockRepositoryPort",
    "PriceHistoryPort",
]


class LiquiditySnapshotPort(Protocol):
    """Provides the latest liquidity snapshot for confluence checks.

    Why it exists
    -------------
    Order-block quality may consider nearby liquidity pools/sweeps without
    owning liquidity computation.
    """

    async def get_latest_snapshot(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
    ) -> LiquiditySnapshot | None:
        """Load the newest liquidity snapshot, if any."""
        ...


class OrderBlockRepositoryPort(Protocol):
    """Persists and loads immutable order-block snapshots.

    Why it exists
    -------------
    Snapshot durability is optional. No SQL in this sprint.
    """

    async def save_snapshot(self, snapshot: OrderBlockSnapshot) -> None:
        """Persist an order-block snapshot."""
        ...

    async def get_latest_snapshot(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
    ) -> OrderBlockSnapshot | None:
        """Load the newest snapshot for symbol/timeframe, if any."""
        ...
