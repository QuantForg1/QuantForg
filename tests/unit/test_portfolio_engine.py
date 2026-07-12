"""Unit tests for Portfolio & Position Engine — read-only, MockMT5 only."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.dto.mt5 import MT5ConnectCommand
from app.application.services.portfolio_sync import PortfolioSyncService
from app.application.use_cases.mt5 import ConnectMT5UseCase
from app.application.use_cases.portfolio import (
    GetHistoryUseCase,
    GetPortfolioUseCase,
    ListOrdersUseCase,
    ListPositionsUseCase,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.interfaces.mt5_client import MT5LoginRequest
from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter
from app.infrastructure.persistence.memory_broker import MemoryBrokerUnitOfWorkFactory
from app.infrastructure.persistence.memory_mt5 import MemoryMT5UnitOfWorkFactory
from app.infrastructure.persistence.memory_portfolio import (
    MemoryPortfolioUnitOfWorkFactory,
)


def _wire() -> tuple[
    MemoryMT5UnitOfWorkFactory,
    MemoryPortfolioUnitOfWorkFactory,
    MT5Adapter,
    PortfolioSyncService,
    RecordAuditEventUseCase,
]:
    mt5_factory = MemoryMT5UnitOfWorkFactory()
    portfolio_factory = MemoryPortfolioUnitOfWorkFactory()
    broker_factory = MemoryBrokerUnitOfWorkFactory()
    audit = RecordAuditEventUseCase(uow_factory=broker_factory)  # type: ignore[arg-type]
    adapter = MT5Adapter(client=MockMT5Client())
    sync = PortfolioSyncService(adapter=adapter)
    return mt5_factory, portfolio_factory, adapter, sync, audit


async def _connect(
    mt5_factory: MemoryMT5UnitOfWorkFactory,
    adapter: MT5Adapter,
    audit: RecordAuditEventUseCase,
    user_id: object,
) -> None:
    await ConnectMT5UseCase(
        uow_factory=mt5_factory, adapter=adapter, audit=audit
    ).execute(
        MT5ConnectCommand(
            user_id=user_id,  # type: ignore[arg-type]
            login=5001,
            password="secret",
            server="Demo-Server",
        )
    )


@pytest.mark.unit
class TestMockPortfolioReads:
    def test_positions_orders_history_account(self) -> None:
        client = MockMT5Client()
        client.initialize()
        client.login(MT5LoginRequest(login=1, password="p", server="Demo"))
        positions = client.list_positions()
        assert len(positions) == 2
        assert client.position_by_ticket(100001) is not None
        assert len(client.position_by_symbol("EURUSD")) == 1
        orders = client.list_orders()
        assert len(orders) == 1
        assert client.order_by_ticket(200001) is not None
        assert len(client.history_orders()) >= 1
        assert len(client.history_deals()) >= 1
        snap = client.account_snapshot()
        assert snap.balance > 0
        assert snap.equity > 0
        assert snap.leverage == 100
        assert snap.margin >= 0
        assert snap.free_margin >= 0
        from app.application.services.mt5_order_validation import (
            MT5OrderValidationService,
        )
        from app.domain.entities.execution_gateway import RETCODE_EXECUTION_DISABLED
        from app.domain.entities.mt5_order import OrderIntent
        from app.domain.enums.order import OrderSide, OrderType
        from app.domain.value_objects.mt5_order import LotSize

        adapter = MT5Adapter(client=client, execution_enabled=False)
        intent = OrderIntent(
            symbol="EURUSD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            volume=LotSize.of("0.01"),
        )
        req = MT5OrderValidationService(adapter=adapter).build_order_request(intent)
        assert adapter.order_send(req).retcode == RETCODE_EXECUTION_DISABLED


@pytest.mark.unit
class TestPortfolioSyncService:
    def test_synchronize_emits_events(self) -> None:
        adapter = MT5Adapter(client=MockMT5Client())
        adapter.initialize()
        adapter.login(MT5LoginRequest(login=9, password="p", server="S"))
        sync = PortfolioSyncService(adapter=adapter)
        user_id = uuid4()
        record = sync.synchronize(user_id=user_id)
        assert record.position_count == 2
        assert record.pending_order_count == 1
        assert record.login == 9
        events = sync.drain_events()
        types = {e.event_type for e in events}
        assert "portfolio.synchronized" in types
        assert "portfolio.position_opened_detected" in types
        assert "portfolio.pending_order_detected" in types
        assert "portfolio.account_updated" in types

        # Second sync — no new opens; still portfolio.synchronized
        record2 = sync.synchronize(user_id=user_id)
        assert record2.position_count == 2
        events2 = sync.drain_events()
        assert any(e.event_type == "portfolio.synchronized" for e in events2)
        assert not any(
            e.event_type == "portfolio.position_opened_detected" for e in events2
        )


@pytest.mark.unit
class TestPortfolioUseCases:
    @pytest.mark.asyncio
    async def test_portfolio_positions_orders_history(self) -> None:
        mt5_factory, portfolio_factory, adapter, sync, audit = _wire()
        user_id = uuid4()
        await _connect(mt5_factory, adapter, audit, user_id)

        portfolio = await GetPortfolioUseCase(
            mt5_uow_factory=mt5_factory,
            portfolio_uow_factory=portfolio_factory,
            sync_service=sync,
        ).execute(user_id=user_id)
        assert portfolio.position_count == 2
        assert portfolio.pending_order_count == 1
        assert portfolio.account.equity
        assert "password" not in str(portfolio.account)

        positions = await ListPositionsUseCase(
            mt5_uow_factory=mt5_factory, sync_service=sync
        ).execute(user_id=user_id, symbol="EURUSD")
        assert len(positions) == 1
        assert positions[0].symbol == "EURUSD"

        orders = await ListOrdersUseCase(
            mt5_uow_factory=mt5_factory, sync_service=sync
        ).execute(user_id=user_id)
        assert len(orders) == 1

        history = await GetHistoryUseCase(
            mt5_uow_factory=mt5_factory, sync_service=sync
        ).execute(user_id=user_id)
        assert len(history.orders) >= 1
        assert len(history.deals) >= 1
