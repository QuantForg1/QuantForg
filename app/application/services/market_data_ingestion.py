"""Application service for ingesting market-data observations.

Why it exists
-------------
Coordinates validation (domain factories), persistence
(:class:`MarketDataStoragePort`), and event publication
(:class:`EventPublisherPort`). No REST, SQL, MetaTrader, or trade execution.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.domain.events.market import (
    CandleClosed,
    MarketDataStored,
    MarketSnapshotCaptured,
    QuoteUpdated,
    SpreadObserved,
    TickReceived,
)
from app.domain.interfaces.event_bus import EventPublisherPort
from app.domain.interfaces.market_data import MarketDataStoragePort
from app.domain.interfaces.time import TimeProviderPort
from app.domain.market_data.candle import Candle
from app.domain.market_data.quote import Quote
from app.domain.market_data.snapshot import MarketSnapshot, SymbolMarketView
from app.domain.market_data.tick import Tick
from app.domain.market_data.timeframe import Timeframe
from app.domain.value_objects.identity import SymbolCode
from app.domain.value_objects.market import Price


@dataclass(frozen=True, slots=True)
class MarketDataIngestionService:
    """Ingest ticks, quotes, candles, and snapshots through ports."""

    storage: MarketDataStoragePort
    publisher: EventPublisherPort
    time_provider: TimeProviderPort

    async def record_tick(
        self,
        *,
        symbol_code: str | SymbolCode,
        price: Price | Decimal | int | str,
        timestamp: datetime | None = None,
        volume: Decimal | int | str | None = None,
        symbol_id: UUID | None = None,
    ) -> Tick:
        """Validate, store, and publish a tick observation."""
        tick = Tick.create(
            symbol_code=symbol_code,
            price=price,
            timestamp=timestamp or self.time_provider.now(),
            volume=volume,
            symbol_id=symbol_id,
        )
        await self.storage.save_tick(tick)
        await self.publisher.publish(TickReceived(tick=tick))
        await self.publisher.publish(
            MarketDataStored(
                record_type="tick",
                record_id=tick.id,
                symbol_code=tick.symbol_code.value,
            )
        )
        return tick

    async def record_quote(
        self,
        *,
        symbol_code: str | SymbolCode,
        bid: Price | Decimal | int | str,
        ask: Price | Decimal | int | str,
        timestamp: datetime | None = None,
        symbol_id: UUID | None = None,
        record_spread: bool = True,
    ) -> Quote:
        """Validate, store, and publish a quote (and optional spread)."""
        quote = Quote.create(
            symbol_code=symbol_code,
            bid=bid,
            ask=ask,
            timestamp=timestamp or self.time_provider.now(),
            symbol_id=symbol_id,
        )
        await self.storage.save_quote(quote)
        await self.publisher.publish(QuoteUpdated(quote=quote))
        await self.publisher.publish(
            MarketDataStored(
                record_type="quote",
                record_id=quote.id,
                symbol_code=quote.symbol_code.value,
            )
        )
        if record_spread:
            spread = quote.to_spread()
            await self.storage.save_spread(spread)
            await self.publisher.publish(SpreadObserved(spread=spread))
        return quote

    async def record_candle(
        self,
        *,
        symbol_code: str | SymbolCode,
        timeframe: Timeframe | str,
        open_time: datetime,
        close_time: datetime,
        open: Price | Decimal | int | str,
        high: Price | Decimal | int | str,
        low: Price | Decimal | int | str,
        close: Price | Decimal | int | str,
        volume: Decimal | int | str = 0,
        tick_count: int = 0,
        symbol_id: UUID | None = None,
    ) -> Candle:
        """Validate, store, and publish a closed candle."""
        candle = Candle.create(
            symbol_code=symbol_code,
            timeframe=timeframe,
            open_time=open_time,
            close_time=close_time,
            open=open,
            high=high,
            low=low,
            close=close,
            volume=volume,
            tick_count=tick_count,
            symbol_id=symbol_id,
        )
        await self.storage.save_candle(candle)
        await self.publisher.publish(CandleClosed(candle=candle))
        await self.publisher.publish(
            MarketDataStored(
                record_type="candle",
                record_id=candle.id,
                symbol_code=candle.symbol_code.value,
            )
        )
        return candle

    async def capture_snapshot(
        self,
        *,
        symbol_codes: Sequence[str | SymbolCode],
    ) -> MarketSnapshot:
        """Build a multi-symbol snapshot from latest stored observations."""
        views: list[SymbolMarketView] = []
        for raw in symbol_codes:
            code = raw if isinstance(raw, SymbolCode) else SymbolCode(value=raw)
            tick = await self.storage.get_latest_tick(code)
            quote = await self.storage.get_latest_quote(code)
            spread = await self.storage.get_latest_spread(code)
            views.append(
                SymbolMarketView(
                    symbol_code=code,
                    tick=tick,
                    quote=quote,
                    spread=spread,
                )
            )
        snapshot = MarketSnapshot.create(
            views=views,
            captured_at=self.time_provider.now(),
        )
        await self.storage.save_snapshot(snapshot)
        await self.publisher.publish(MarketSnapshotCaptured(snapshot=snapshot))
        await self.publisher.publish(
            MarketDataStored(
                record_type="snapshot",
                record_id=snapshot.id,
                symbol_code=",".join(snapshot.symbol_codes),
            )
        )
        return snapshot
