"""In-memory market data provider foundation adapter.

Reads from an :class:`InMemoryMarketDataStore` (or any storage port).
Does not connect to MetaTrader or any external venue.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from app.domain.interfaces.market_data import MarketDataStoragePort
from app.domain.interfaces.time import TimeProviderPort
from app.domain.market_data.candle import Candle
from app.domain.market_data.quote import Quote
from app.domain.market_data.snapshot import MarketSnapshot, SymbolMarketView
from app.domain.market_data.spread import Spread
from app.domain.market_data.tick import Tick
from app.domain.market_data.timeframe import Timeframe
from app.domain.value_objects.identity import SymbolCode
from app.infrastructure.market_data.memory_store import InMemoryMarketDataStore
from app.infrastructure.time.providers import UtcTimeProvider


class InMemoryMarketDataProvider:
    """Provider that surfaces observations already held in storage.

    Why it exists
    -------------
    Implements :class:`MarketDataProviderPort` for local/dev/test without a
    live market feed. Production venue adapters will replace this later.
    """

    def __init__(
        self,
        storage: MarketDataStoragePort,
        *,
        time_provider: TimeProviderPort | None = None,
    ) -> None:
        self._storage = storage
        self._time = time_provider or UtcTimeProvider()

    async def list_symbols(self) -> Sequence[SymbolCode]:
        if isinstance(self._storage, InMemoryMarketDataStore):
            return self._storage.known_symbols()
        return []

    async def get_latest_tick(self, symbol_code: SymbolCode) -> Tick | None:
        return await self._storage.get_latest_tick(symbol_code)

    async def get_latest_quote(self, symbol_code: SymbolCode) -> Quote | None:
        return await self._storage.get_latest_quote(symbol_code)

    async def get_latest_spread(self, symbol_code: SymbolCode) -> Spread | None:
        return await self._storage.get_latest_spread(symbol_code)

    async def get_candles(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
        *,
        limit: int = 100,
    ) -> Sequence[Candle]:
        return await self._storage.get_candles(symbol_code, timeframe, limit=limit)

    async def get_snapshot(
        self,
        symbol_codes: Sequence[SymbolCode],
    ) -> MarketSnapshot | None:
        if not symbol_codes:
            return None
        views: list[SymbolMarketView] = []
        for code in symbol_codes:
            tick = await self._storage.get_latest_tick(code)
            quote = await self._storage.get_latest_quote(code)
            spread = await self._storage.get_latest_spread(code)
            candles = await self._storage.get_candles(code, Timeframe.M1, limit=1)
            candle = candles[-1] if candles else None
            if tick is None and quote is None and spread is None and candle is None:
                continue
            views.append(
                SymbolMarketView(
                    symbol_code=code,
                    tick=tick,
                    quote=quote,
                    spread=spread,
                    candle=candle,
                )
            )
        if not views:
            return None
        captured_at: datetime = self._time.now()
        if captured_at.tzinfo is None:
            captured_at = captured_at.replace(tzinfo=UTC)
        return MarketSnapshot.create(views=views, captured_at=captured_at)
