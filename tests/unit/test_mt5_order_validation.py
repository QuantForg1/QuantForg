"""Unit tests for MT5 order validation layer (Sprint 3)."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.dto.mt5 import MT5ConnectCommand, MT5OrderValidateCommand
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.application.use_cases.mt5 import ConnectMT5UseCase
from app.application.use_cases.mt5_order import (
    CalculateMT5OrderUseCase,
    ValidateMT5OrderUseCase,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.entities.mt5_order import OrderIntent
from app.domain.enums.order import OrderSide, OrderType
from app.domain.interfaces.mt5_client import MT5LoginRequest
from app.domain.interfaces.mt5_order import RETCODE_DONE
from app.domain.value_objects.mt5_order import (
    LotSize,
    MagicNumber,
    Slippage,
    StopLoss,
    TakeProfit,
)
from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter
from app.infrastructure.persistence.memory_broker import MemoryBrokerUnitOfWorkFactory
from app.infrastructure.persistence.memory_mt5 import MemoryMT5UnitOfWorkFactory


def _wire() -> tuple[
    MemoryMT5UnitOfWorkFactory,
    MT5Adapter,
    MT5OrderValidationService,
    RecordAuditEventUseCase,
]:
    mt5_factory = MemoryMT5UnitOfWorkFactory()
    broker_factory = MemoryBrokerUnitOfWorkFactory()
    audit = RecordAuditEventUseCase(uow_factory=broker_factory)  # type: ignore[arg-type]
    adapter = MT5Adapter(client=MockMT5Client())
    validation = MT5OrderValidationService(adapter=adapter)
    return mt5_factory, adapter, validation, audit


@pytest.mark.unit
class TestOrderValueObjects:
    def test_lot_size_and_stops(self) -> None:
        assert LotSize.of("0.10").value == Decimal("0.10")
        assert StopLoss.of("1.08000").value > 0
        assert TakeProfit.of("1.09000").value > 0
        assert Slippage.of(15).value == 15
        assert MagicNumber.of(42).value == 42


@pytest.mark.unit
class TestMockOrderCheck:
    def test_order_check_margin_profit_never_send(self) -> None:
        client = MockMT5Client()
        client.initialize()
        client.login(MT5LoginRequest(login=1, password="p", server="Demo"))
        adapter = MT5Adapter(client=client)
        service = MT5OrderValidationService(adapter=adapter)
        intent = OrderIntent(
            symbol="EURUSD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            volume=LotSize.of("0.10"),
            stop_loss=StopLoss.of("1.08000"),
            take_profit=TakeProfit.of("1.09500"),
        )
        request = service.build_order_request(intent)
        check = client.order_check(request)
        assert check.retcode == RETCODE_DONE
        assert check.margin > 0
        margin = client.order_calc_margin(request)
        profit = client.order_calc_profit(request)
        assert margin.margin > 0
        assert isinstance(profit.profit, Decimal)
        # Default adapter keeps execution disabled — never reaches live send path.
        from app.domain.entities.execution_gateway import RETCODE_EXECUTION_DISABLED

        disabled = adapter.order_send(request)
        assert disabled.retcode == RETCODE_EXECUTION_DISABLED


@pytest.mark.unit
class TestOrderValidationService:
    def test_validate_order_pipeline(self) -> None:
        adapter = MT5Adapter(client=MockMT5Client())
        adapter.initialize()
        adapter.login(MT5LoginRequest(login=7, password="p", server="S"))
        service = MT5OrderValidationService(adapter=adapter)
        intent = OrderIntent(
            symbol="EURUSD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            volume=LotSize.of("0.01"),
        )
        result = service.validate_order(intent)
        assert result.valid is True
        assert result.checks.get("symbol") is True
        assert result.checks.get("volume") is True
        assert result.checks.get("order_check") is True
        assert result.expected_margin > 0

    def test_misaligned_volume_is_normalized(self) -> None:
        adapter = MT5Adapter(client=MockMT5Client())
        adapter.initialize()
        adapter.login(MT5LoginRequest(login=7, password="p", server="S"))
        service = MT5OrderValidationService(adapter=adapter)
        intent = OrderIntent(
            symbol="EURUSD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            volume=LotSize.of("0.015"),  # not aligned to 0.01 step
        )
        result = service.validate_order(intent)
        assert result.valid is True
        assert result.volume == LotSize.of("0.01").value
        assert result.checks.get("volume") is True
        assert any("normalized" in m.lower() for m in result.messages)


@pytest.mark.unit
class TestOrderValidationUseCases:
    @pytest.mark.asyncio
    async def test_validate_and_calculate_endpoints(self) -> None:
        factory, adapter, validation, audit = _wire()
        user_id = uuid4()
        await ConnectMT5UseCase(
            uow_factory=factory, adapter=adapter, audit=audit
        ).execute(
            MT5ConnectCommand(
                user_id=user_id,
                login=3003,
                password="secret",
                server="Demo-Server",
            )
        )
        cmd = MT5OrderValidateCommand(
            user_id=user_id,
            symbol="EURUSD",
            side="buy",
            order_type="market",
            volume="0.10",
            stop_loss="1.08000",
            take_profit="1.09500",
        )
        validated = await ValidateMT5OrderUseCase(
            uow_factory=factory, validation_service=validation, audit=audit
        ).execute(cmd)
        assert validated.valid is True
        assert validated.retcode == RETCODE_DONE
        assert validated.expected_margin
        assert validated.messages

        calc = await CalculateMT5OrderUseCase(
            uow_factory=factory, validation_service=validation
        ).execute(cmd)
        assert calc.expected_margin
        assert calc.estimated_profit is not None
        assert "password" not in str(calc.request_snapshot).lower()
