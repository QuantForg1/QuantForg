"""Unit tests for MT5 market-data layer (Sprint 2)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.application.dto.mt5 import MT5ConnectCommand
from app.application.services.mt5_market_data import MT5MarketDataService
from app.application.use_cases.mt5 import (
    ConnectMT5UseCase,
    GetMT5CandlesUseCase,
    GetMT5SymbolUseCase,
    GetMT5TickUseCase,
    ListMT5SymbolsUseCase,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.events.mt5 import CandleReceived, MarketDataUpdated, TickReceived
from app.domain.market_data.timeframe import Timeframe
from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter
from app.infrastructure.persistence.memory_broker import MemoryBrokerUnitOfWorkFactory
from app.infrastructure.persistence.memory_mt5 import MemoryMT5UnitOfWorkFactory


def _connected() -> (
    tuple[MemoryMT5UnitOfWorkFactory, MT5Adapter, MT5MarketDataService, object]
):
    mt5_factory = MemoryMT5UnitOfWorkFactory()
    broker_factory = MemoryBrokerUnitOfWorkFactory()
    audit = RecordAuditEventUseCase(uow_factory=broker_factory)  # type: ignore[arg-type]
    adapter = MT5Adapter(client=MockMT5Client())
    market = MT5MarketDataService(adapter=adapter)
    return mt5_factory, adapter, market, audit


@pytest.mark.unit
class TestMockMarketData:
    def test_symbol_management_and_tick(self) -> None:
        client = MockMT5Client()
        client.initialize()
        from app.domain.interfaces.mt5_client import MT5LoginRequest

        assert client.login(MT5LoginRequest(login=1, password="p", server="Demo"))
        symbols = client.list_symbols()
        assert any(s.code == "EURUSD" for s in symbols)
        info = client.symbol_info("EURUSD")
        assert info.digits == 5
        assert client.symbol_select("XAUUSD", enable=True) is True
        assert client.symbol_info("XAUUSD").selected is True
        tick = client.latest_tick("EURUSD")
        assert tick.ask >= tick.bid
        assert tick.spread == tick.ask - tick.bid

    def test_copy_rates_variants(self) -> None:
        client = MockMT5Client()
        client.initialize()
        from app.domain.interfaces.mt5_client import MT5LoginRequest

        client.login(MT5LoginRequest(login=1, password="p", server="Demo"))
        now = datetime.now(UTC)
        from_rates = client.copy_rates_from(
            "EURUSD", Timeframe.H1, now - timedelta(hours=10), 10
        )
        assert len(from_rates) == 10
        assert from_rates[0].timeframe is Timeframe.H1

        ranged = client.copy_rates_range(
            "EURUSD",
            Timeframe.M15,
            now - timedelta(hours=2),
            now,
        )
        assert len(ranged) >= 1

        pos = client.copy_rates_from_pos("EURUSD", Timeframe.M5, 0, 5)
        assert len(pos) == 5

        for tf in Timeframe:
            bars = client.copy_rates_from_pos("GBPUSD", tf, 0, 3)
            assert len(bars) == 3
            assert bars[0].timeframe is tf


@pytest.mark.unit
class TestMT5MarketDataService:
    def test_historical_latest_and_events(self) -> None:
        adapter = MT5Adapter(client=MockMT5Client())
        from app.domain.interfaces.mt5_client import MT5LoginRequest

        adapter.initialize()
        adapter.login(MT5LoginRequest(login=9, password="p", server="S"))
        service = MT5MarketDataService(adapter=adapter)
        service.clear_events()

        tick = service.latest_tick("EURUSD")
        assert tick.symbol == "EURUSD"
        candle = service.latest_candle("EURUSD", Timeframe.H1)
        assert candle is not None
        hist = service.historical_candles("EURUSD", Timeframe.M1, count=20)
        assert len(hist) == 20

        types = {type(e) for e in service.last_events}
        assert TickReceived in types
        assert CandleReceived in types
        assert MarketDataUpdated in types


@pytest.mark.unit
class TestMT5MarketDataUseCases:
    @pytest.mark.asyncio
    async def test_symbol_tick_candles_api_flow(self) -> None:
        factory, adapter, market, audit = _connected()
        user_id = uuid4()
        await ConnectMT5UseCase(
            uow_factory=factory, adapter=adapter, audit=audit
        ).execute(
            MT5ConnectCommand(
                user_id=user_id,
                login=2002,
                password="secret",
                server="Demo-Server",
            )
        )

        symbols = await ListMT5SymbolsUseCase(
            uow_factory=factory, adapter=adapter
        ).execute(user_id=user_id, include_quotes=True)
        assert any(s.code == "XAUUSD" and s.bid is not None for s in symbols.items)

        detail = await GetMT5SymbolUseCase(
            uow_factory=factory, market_data=market
        ).execute(user_id=user_id, symbol="xauusd")
        assert detail.code == "XAUUSD"

        tick = await GetMT5TickUseCase(uow_factory=factory, market_data=market).execute(
            user_id=user_id, symbol="XAUUSD"
        )
        assert tick.spread
        assert tick.bid
        assert tick.ask

        candles = await GetMT5CandlesUseCase(
            uow_factory=factory, market_data=market
        ).execute(
            user_id=user_id,
            symbol="XAUUSD",
            timeframe="H1",
            count=12,
        )
        assert len(candles) == 12
        assert candles[0].timeframe == "H1"
