"""In-memory market data storage foundation adapter.

Implements :class:`MarketDataStoragePort` without SQL. Suitable for tests
and local development. Not a production durability guarantee.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from app.domain.market_data.candle import Candle
from app.domain.market_data.quote import Quote
from app.domain.market_data.snapshot import MarketSnapshot
from app.domain.market_data.spread import Spread
from app.domain.market_data.tick import Tick
from app.domain.market_data.timeframe import Timeframe
from app.domain.value_objects.identity import SymbolCode


class InMemoryMarketDataStore:
    """Process-local store for ticks, quotes, spreads, candles, and snapshots.

    Why it exists
    -------------
    Provides a working :class:`MarketDataStoragePort` so the market-data
    foundation is exercisable before SQL repositories exist.
    """

    def __init__(self) -> None:
        self._ticks: dict[str, list[Tick]] = defaultdict(list)
        self._quotes: dict[str, list[Quote]] = defaultdict(list)
        self._spreads: dict[str, list[Spread]] = defaultdict(list)
        self._candles: dict[tuple[str, str], list[Candle]] = defaultdict(list)
        self._snapshots: list[MarketSnapshot] = []

    async def save_tick(self, tick: Tick) -> None:
        self._ticks[tick.symbol_code.value].append(tick)

    async def save_quote(self, quote: Quote) -> None:
        self._quotes[quote.symbol_code.value].append(quote)

    async def save_spread(self, spread: Spread) -> None:
        self._spreads[spread.symbol_code.value].append(spread)

    async def save_candle(self, candle: Candle) -> None:
        key = (candle.symbol_code.value, candle.timeframe.value)
        self._candles[key].append(candle)

    async def save_snapshot(self, snapshot: MarketSnapshot) -> None:
        self._snapshots.append(snapshot)

    async def get_latest_tick(self, symbol_code: SymbolCode) -> Tick | None:
        items = self._ticks.get(symbol_code.value, [])
        return items[-1] if items else None

    async def get_latest_quote(self, symbol_code: SymbolCode) -> Quote | None:
        items = self._quotes.get(symbol_code.value, [])
        return items[-1] if items else None

    async def get_latest_spread(self, symbol_code: SymbolCode) -> Spread | None:
        items = self._spreads.get(symbol_code.value, [])
        return items[-1] if items else None

    async def get_candles(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
        *,
        limit: int = 100,
    ) -> Sequence[Candle]:
        if limit < 1:
            return []
        key = (symbol_code.value, timeframe.value)
        items = self._candles.get(key, [])
        return items[-limit:]

    async def get_latest_snapshot(
        self,
        symbol_codes: Sequence[SymbolCode] | None = None,
    ) -> MarketSnapshot | None:
        if not self._snapshots:
            return None
        if symbol_codes is None:
            return self._snapshots[-1]
        wanted = {code.value for code in symbol_codes}
        for snapshot in reversed(self._snapshots):
            if set(snapshot.symbol_codes) >= wanted:
                return snapshot
        return None

    def known_symbols(self) -> list[SymbolCode]:
        """Return symbol codes that have any stored observation."""
        codes = set(self._ticks) | set(self._quotes) | set(self._spreads)
        codes |= {key[0] for key in self._candles}
        return [SymbolCode(value=code) for code in sorted(codes)]
