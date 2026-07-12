"""Unit tests for Paper Trading Engine — never order_send / never live execution."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.dto.paper import (
    ListPaperPositionsCommand,
    PaperHistoryCommand,
    PaperPerformanceCommand,
    PlacePaperOrderCommand,
)
from app.application.services.mt5_market_data import MT5MarketDataService
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.application.services.paper_market_listener import PaperMarketListener
from app.application.services.paper_trading import (
    PaperTradingEngine,
    PlacePaperOrderInput,
)
from app.application.services.virtual_broker import VirtualBroker
from app.application.use_cases.paper import (
    GetPaperHistoryUseCase,
    GetPaperPerformanceUseCase,
    ListPaperPositionsUseCase,
    PlacePaperOrderUseCase,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.entities.execution_gateway import RETCODE_EXECUTION_DISABLED
from app.domain.entities.mt5_order import OrderIntent
from app.domain.entities.paper import PaperBrokerAssumptions
from app.domain.enums.order import OrderSide, OrderType
from app.domain.enums.paper import PaperOrderStatus, PaperPositionStatus
from app.domain.interfaces.mt5_client import MT5LoginRequest
from app.domain.value_objects.mt5_order import LotSize
from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter
from app.infrastructure.persistence.memory_broker import MemoryBrokerUnitOfWorkFactory
from app.infrastructure.persistence.memory_mt5 import MemoryMT5UnitOfWorkFactory
from app.infrastructure.persistence.memory_paper import MemoryPaperUnitOfWorkFactory
from core.config.settings import get_settings


def _wire_engine() -> tuple[PaperTradingEngine, MT5Adapter]:
    client = MockMT5Client()
    client.initialize()
    client.login(MT5LoginRequest(login=1, password="p", server="Paper"))
    adapter = MT5Adapter(client=client, execution_enabled=False)
    market = MT5MarketDataService(adapter=adapter)
    engine = PaperTradingEngine(
        market_listener=PaperMarketListener(market_data=market),
        broker=VirtualBroker(assumptions=PaperBrokerAssumptions()),
    )
    return engine, adapter


@pytest.mark.unit
class TestVirtualBrokerAndEngine:
    def test_market_order_fills_and_never_order_send(self) -> None:
        settings = get_settings()
        assert settings.execution_enabled is False

        engine, adapter = _wire_engine()
        user_id = uuid4()
        result = engine.place_order(
            PlacePaperOrderInput(
                user_id=user_id,
                symbol="EURUSD",
                side="buy",
                order_type="market",
                volume=Decimal("0.10"),
            )
        )
        assert result.order.status is PaperOrderStatus.FILLED
        assert result.position is not None
        assert result.position.status is PaperPositionStatus.OPENED
        assert result.order.fill_price is not None
        events = engine.drain_events()
        assert any(e.event_type == "paper.order_filled" for e in events)
        assert any(e.event_type == "paper.trade_opened" for e in events)

        req = MT5OrderValidationService(adapter=adapter).build_order_request(
            OrderIntent(
                symbol="EURUSD",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                volume=LotSize.of("0.01"),
            )
        )
        assert adapter.order_send(req).retcode == RETCODE_EXECUTION_DISABLED

    def test_limit_accepted_pending_when_not_triggered(self) -> None:
        engine, _adapter = _wire_engine()
        # Far away limit buy — should stay accepted
        result = engine.place_order(
            PlacePaperOrderInput(
                user_id=uuid4(),
                symbol="EURUSD",
                side="buy",
                order_type="limit",
                volume=Decimal("0.10"),
                price=Decimal("0.50000"),
            )
        )
        assert result.order.status is PaperOrderStatus.ACCEPTED
        assert result.position is None

    def test_reject_oversized_lot(self) -> None:
        engine, _ = _wire_engine()
        result = engine.place_order(
            PlacePaperOrderInput(
                user_id=uuid4(),
                symbol="EURUSD",
                side="buy",
                volume=Decimal("100"),
            )
        )
        assert result.order.status is PaperOrderStatus.REJECTED
        events = engine.drain_events()
        assert any(e.event_type == "paper.order_rejected" for e in events)

    def test_reduce_position_closes_and_records_trade(self) -> None:
        engine, _ = _wire_engine()
        user_id = uuid4()
        opened = engine.place_order(
            PlacePaperOrderInput(
                user_id=user_id,
                symbol="EURUSD",
                side="buy",
                volume=Decimal("0.10"),
            )
        )
        assert opened.position is not None
        closed = engine.place_order(
            PlacePaperOrderInput(
                user_id=user_id,
                symbol="EURUSD",
                side="sell",
                volume=Decimal("0.10"),
                reduce_position_id=opened.position.id,
            ),
            portfolio=opened.portfolio,
            positions=[opened.position],
        )
        assert closed.order.status is PaperOrderStatus.FILLED
        assert closed.trade is not None
        assert closed.position is not None
        assert closed.position.status is PaperPositionStatus.CLOSED
        events = engine.drain_events()
        assert any(e.event_type == "paper.trade_closed" for e in events)


@pytest.mark.unit
class TestPaperUseCases:
    @pytest.mark.asyncio
    async def test_place_list_history_performance(self) -> None:
        settings = get_settings()
        assert settings.execution_enabled is False

        engine, adapter = _wire_engine()
        paper_factory = MemoryPaperUnitOfWorkFactory()
        mt5_factory = MemoryMT5UnitOfWorkFactory()
        audit = RecordAuditEventUseCase(
            uow_factory=MemoryBrokerUnitOfWorkFactory()  # type: ignore[arg-type]
        )
        user_id = uuid4()
        place = PlacePaperOrderUseCase(
            paper_uow_factory=paper_factory,
            mt5_uow_factory=mt5_factory,
            engine=engine,
            mt5_adapter=adapter,
            audit=audit,
        )
        dto = await place.execute(
            PlacePaperOrderCommand(
                user_id=user_id,
                symbol="EURUSD",
                side="buy",
                volume="0.10",
            )
        )
        assert dto.order.status == "filled"
        assert dto.position is not None

        positions = await ListPaperPositionsUseCase(
            paper_uow_factory=paper_factory,
            engine=engine,
            mt5_adapter=adapter,
        ).execute(ListPaperPositionsCommand(user_id=user_id))
        assert positions.count == 1

        history = await GetPaperHistoryUseCase(paper_uow_factory=paper_factory).execute(
            PaperHistoryCommand(user_id=user_id)
        )
        assert len(history.orders) == 1

        perf = await GetPaperPerformanceUseCase(
            paper_uow_factory=paper_factory,
            engine=engine,
            mt5_adapter=adapter,
        ).execute(PaperPerformanceCommand(user_id=user_id))
        assert "equity" in perf.performance
        assert "balance" in perf.portfolio
