"""Unit tests for market-data storage, provider, and ingestion service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.application.services.market_data_ingestion import MarketDataIngestionService
from app.domain.events.base import DomainEvent
from app.domain.events.market import (
    CandleClosed,
    MarketSnapshotCaptured,
    QuoteUpdated,
    TickReceived,
)
from app.domain.market_data.timeframe import Timeframe
from app.domain.value_objects.identity import SymbolCode
from app.infrastructure.events.bus import InProcessEventBus
from app.infrastructure.events.subscriber import BaseEventSubscriber
from app.infrastructure.market_data.memory_provider import InMemoryMarketDataProvider
from app.infrastructure.market_data.memory_store import InMemoryMarketDataStore
from app.infrastructure.time.providers import FixedTimeProvider


class _Collector(BaseEventSubscriber):
    def __init__(self) -> None:
        super().__init__(
            name="collector",
            subscribed_types=frozenset(
                {
                    TickReceived,
                    QuoteUpdated,
                    CandleClosed,
                    MarketSnapshotCaptured,
                    DomainEvent,
                }
            ),
        )
        self.types: list[str] = []

    async def handle(self, event: DomainEvent) -> None:
        self.types.append(event.event_type)


@pytest.mark.unit
class TestInMemoryMarketDataStoreAndProvider:
    @pytest.mark.asyncio
    async def test_store_and_provider_roundtrip(self) -> None:
        store = InMemoryMarketDataStore()
        provider = InMemoryMarketDataProvider(store)
        bus = InProcessEventBus()
        fixed = FixedTimeProvider(datetime(2026, 7, 12, 10, 0, tzinfo=UTC))
        ingestion = MarketDataIngestionService(
            storage=store,
            publisher=bus,
            time_provider=fixed,
        )

        await ingestion.record_tick(symbol_code="EURUSD", price="1.1000")
        await ingestion.record_quote(
            symbol_code="EURUSD",
            bid="1.0998",
            ask="1.1002",
        )
        start = fixed.now()
        await ingestion.record_candle(
            symbol_code="EURUSD",
            timeframe=Timeframe.M1,
            open_time=start,
            close_time=start + timedelta(minutes=1),
            open="1.0999",
            high="1.1005",
            low="1.0995",
            close="1.1001",
            volume="12",
        )

        code = SymbolCode.of("EURUSD")
        assert await provider.get_latest_tick(code) is not None
        assert await provider.get_latest_quote(code) is not None
        assert await provider.get_latest_spread(code) is not None
        candles = await provider.get_candles(code, Timeframe.M1, limit=10)
        assert len(candles) == 1
        assert "EURUSD" in [c.value for c in await provider.list_symbols()]

        snapshot = await provider.get_snapshot([code])
        assert snapshot is not None
        assert snapshot.symbol_codes == ("EURUSD",)

    @pytest.mark.asyncio
    async def test_ingestion_publishes_events_for_multiple_symbols(self) -> None:
        store = InMemoryMarketDataStore()
        bus = InProcessEventBus()
        collector = _Collector()
        bus.subscribe(collector)
        ingestion = MarketDataIngestionService(
            storage=store,
            publisher=bus,
            time_provider=FixedTimeProvider(datetime(2026, 7, 12, tzinfo=UTC)),
        )

        await ingestion.record_tick(symbol_code="EURUSD", price="1.1")
        await ingestion.record_tick(symbol_code="GBPUSD", price="1.25")
        await ingestion.record_quote(symbol_code="EURUSD", bid="1.1", ask="1.2")
        snapshot = await ingestion.capture_snapshot(symbol_codes=["EURUSD", "GBPUSD"])

        assert snapshot.symbol_codes == ("EURUSD", "GBPUSD")
        assert "market.tick_received" in collector.types
        assert "market.quote_updated" in collector.types
        assert "market.snapshot_captured" in collector.types
        assert (
            await store.get_latest_snapshot(
                [SymbolCode.of("EURUSD"), SymbolCode.of("GBPUSD")]
            )
            is not None
        )
