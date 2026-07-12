"""Market data provider and storage ports.

Why these ports exist
---------------------
They isolate the application from concrete market-data sources and stores.
Adapters (file, memory, future brokers) implement these contracts.
**No MetaTrader, SQL, or trade-execution logic belongs here.**
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.domain.market_data.candle import Candle
from app.domain.market_data.quote import Quote
from app.domain.market_data.snapshot import MarketSnapshot
from app.domain.market_data.spread import Spread
from app.domain.market_data.tick import Tick
from app.domain.market_data.timeframe import Timeframe
from app.domain.value_objects.identity import SymbolCode


class MarketDataProviderPort(Protocol):
    """Inbound port: fetch live or historical market observations.

    Why it exists
    -------------
    Application services request market data through this port. Concrete
    providers (CSV replay, in-memory feed, future venue adapters) plug in
    behind it. This sprint defines the contract only — no venue SDKs.
    """

    async def list_symbols(self) -> Sequence[SymbolCode]:
        """Return symbol codes available from the provider."""
        ...

    async def get_latest_tick(self, symbol_code: SymbolCode) -> Tick | None:
        """Return the most recent tick for ``symbol_code``, if any."""
        ...

    async def get_latest_quote(self, symbol_code: SymbolCode) -> Quote | None:
        """Return the most recent quote for ``symbol_code``, if any."""
        ...

    async def get_latest_spread(self, symbol_code: SymbolCode) -> Spread | None:
        """Return the most recent spread for ``symbol_code``, if any."""
        ...

    async def get_candles(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
        *,
        limit: int = 100,
    ) -> Sequence[Candle]:
        """Return up to ``limit`` most recent candles (newest last)."""
        ...

    async def get_snapshot(
        self,
        symbol_codes: Sequence[SymbolCode],
    ) -> MarketSnapshot | None:
        """Build or fetch a snapshot covering the requested symbols."""
        ...


class MarketDataStoragePort(Protocol):
    """Outbound port: persist and retrieve market-data records.

    Why it exists
    -------------
    Separates durable storage of ticks/quotes/candles from the provider.
    Foundation adapters may be in-memory; SQL adapters arrive in a later
    sprint. This port must not embed SQL.
    """

    async def save_tick(self, tick: Tick) -> None:
        """Persist a tick observation."""
        ...

    async def save_quote(self, quote: Quote) -> None:
        """Persist a quote observation."""
        ...

    async def save_spread(self, spread: Spread) -> None:
        """Persist a spread observation."""
        ...

    async def save_candle(self, candle: Candle) -> None:
        """Persist a closed candle."""
        ...

    async def save_snapshot(self, snapshot: MarketSnapshot) -> None:
        """Persist a market snapshot."""
        ...

    async def get_latest_tick(self, symbol_code: SymbolCode) -> Tick | None:
        """Load the latest stored tick for ``symbol_code``."""
        ...

    async def get_latest_quote(self, symbol_code: SymbolCode) -> Quote | None:
        """Load the latest stored quote for ``symbol_code``."""
        ...

    async def get_latest_spread(self, symbol_code: SymbolCode) -> Spread | None:
        """Load the latest stored spread for ``symbol_code``."""
        ...

    async def get_candles(
        self,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
        *,
        limit: int = 100,
    ) -> Sequence[Candle]:
        """Load up to ``limit`` stored candles (newest last)."""
        ...

    async def get_latest_snapshot(
        self,
        symbol_codes: Sequence[SymbolCode] | None = None,
    ) -> MarketSnapshot | None:
        """Load the most recent snapshot, optionally filtered by symbols."""
        ...
