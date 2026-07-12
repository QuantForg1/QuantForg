"""Unit tests for Execution Safety Layer — never order_send."""

from __future__ import annotations

from datetime import UTC, datetime, time
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.dto.execution import ExecutionCheckCommand
from app.application.dto.mt5 import MT5ConnectCommand
from app.application.services.execution_safety import ExecutionSafetyService
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.application.use_cases.execution_safety import CheckExecutionSafetyUseCase
from app.application.use_cases.mt5 import ConnectMT5UseCase
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.entities.execution_safety import ExecutionPolicy
from app.domain.entities.mt5_order import OrderIntent
from app.domain.enums.execution import ExecutionDecision
from app.domain.enums.order import OrderSide, OrderType
from app.domain.value_objects.mt5_order import LotSize, Slippage
from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter
from app.infrastructure.persistence.memory_broker import MemoryBrokerUnitOfWorkFactory
from app.infrastructure.persistence.memory_execution import (
    MemoryExecutionUnitOfWorkFactory,
)
from app.infrastructure.persistence.memory_mt5 import MemoryMT5UnitOfWorkFactory


def _wire(*, policy: ExecutionPolicy | None = None) -> tuple[
    MemoryMT5UnitOfWorkFactory,
    MemoryExecutionUnitOfWorkFactory,
    MT5Adapter,
    ExecutionSafetyService,
    RecordAuditEventUseCase,
]:
    mt5_factory = MemoryMT5UnitOfWorkFactory()
    exec_factory = MemoryExecutionUnitOfWorkFactory()
    broker_factory = MemoryBrokerUnitOfWorkFactory()
    audit = RecordAuditEventUseCase(uow_factory=broker_factory)  # type: ignore[arg-type]
    adapter = MT5Adapter(client=MockMT5Client())
    validation = MT5OrderValidationService(adapter=adapter)
    safety = ExecutionSafetyService(
        adapter=adapter,
        order_validation=validation,
        policy=policy or ExecutionPolicy(),
    )
    return mt5_factory, exec_factory, adapter, safety, audit


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
            login=4001,
            password="secret",
            server="Demo-Server",
        )
    )


@pytest.mark.unit
class TestExecutionPolicy:
    def test_policy_validation_fields(self) -> None:
        policy = ExecutionPolicy(
            max_spread=Decimal("0.00030"),
            max_slippage=10,
            trading_hours_start=time(8, 0),
            trading_hours_end=time(17, 0),
            symbol_whitelist=frozenset({"EURUSD"}),
            account_whitelist=frozenset({4001}),
            max_leverage=Decimal("200"),
            max_lot=Decimal("1"),
            min_lot=Decimal("0.01"),
        )
        assert policy.allows_symbol("eurusd")
        assert not policy.allows_symbol("AUDUSD")
        assert policy.allows_account(4001)
        assert not policy.allows_account(9999)
        noon = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)
        night = datetime(2026, 7, 12, 22, 0, tzinfo=UTC)
        assert policy.within_trading_hours(noon)
        assert not policy.within_trading_hours(night)


@pytest.mark.unit
class TestExecutionSafetyService:
    def test_allow_happy_path(self) -> None:
        adapter = MT5Adapter(client=MockMT5Client())
        adapter.initialize()
        from app.domain.interfaces.mt5_client import MT5LoginRequest

        adapter.login(MT5LoginRequest(login=7, password="p", server="S"))
        validation = MT5OrderValidationService(adapter=adapter)
        safety = ExecutionSafetyService(adapter=adapter, order_validation=validation)
        intent = OrderIntent(
            symbol="EURUSD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            volume=LotSize.of("0.10"),
        )
        record = safety.decide(
            user_id=uuid4(),
            request_id="req-allow-1",
            intent=intent,
            connected=True,
            login=7,
            recent=[],
        )
        assert record.decision is ExecutionDecision.ALLOW
        assert record.rejection_reasons == []
        assert "expected_margin" in record.calculated_risk
        events = safety.drain_events()
        assert any(e.event_type == "execution.approved" for e in events)

    def test_policy_symbol_rejection(self) -> None:
        adapter = MT5Adapter(client=MockMT5Client())
        adapter.initialize()
        from app.domain.interfaces.mt5_client import MT5LoginRequest

        adapter.login(MT5LoginRequest(login=7, password="p", server="S"))
        validation = MT5OrderValidationService(adapter=adapter)
        safety = ExecutionSafetyService(
            adapter=adapter,
            order_validation=validation,
            policy=ExecutionPolicy(symbol_whitelist=frozenset({"EURUSD"})),
        )
        intent = OrderIntent(
            symbol="GBPUSD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            volume=LotSize.of("0.01"),
        )
        record = safety.decide(
            user_id=uuid4(),
            request_id="req-reject-symbol",
            intent=intent,
            connected=True,
            login=7,
            recent=[],
        )
        assert record.decision is ExecutionDecision.REJECT
        assert any("whitelist" in r for r in record.rejection_reasons)
        events = safety.drain_events()
        assert any(e.event_type == "execution.rejected" for e in events)

    def test_risk_volume_rejection(self) -> None:
        adapter = MT5Adapter(client=MockMT5Client())
        adapter.initialize()
        from app.domain.interfaces.mt5_client import MT5LoginRequest

        adapter.login(MT5LoginRequest(login=7, password="p", server="S"))
        validation = MT5OrderValidationService(adapter=adapter)
        safety = ExecutionSafetyService(adapter=adapter, order_validation=validation)
        intent = OrderIntent(
            symbol="EURUSD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            volume=LotSize.of("0.015"),
        )
        record = safety.decide(
            user_id=uuid4(),
            request_id="req-reject-vol",
            intent=intent,
            connected=True,
            login=7,
            recent=[],
        )
        assert record.decision is ExecutionDecision.REJECT
        assert record.checks.get("volume_limits") is False

    def test_duplicate_and_rapid_submit(self) -> None:
        adapter = MT5Adapter(client=MockMT5Client())
        adapter.initialize()
        from app.domain.interfaces.mt5_client import MT5LoginRequest

        adapter.login(MT5LoginRequest(login=7, password="p", server="S"))
        validation = MT5OrderValidationService(adapter=adapter)
        safety = ExecutionSafetyService(
            adapter=adapter,
            order_validation=validation,
            policy=ExecutionPolicy(rapid_submit_limit=2),
        )
        user_id = uuid4()
        intent = OrderIntent(
            symbol="EURUSD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            volume=LotSize.of("0.01"),
            slippage=Slippage.of(5),
        )
        first = safety.decide(
            user_id=user_id,
            request_id="dup-1",
            intent=intent,
            connected=True,
            login=7,
            recent=[],
        )
        assert first.decision is ExecutionDecision.ALLOW
        second = safety.decide(
            user_id=user_id,
            request_id="dup-2",
            intent=intent,
            connected=True,
            login=7,
            recent=[first],
        )
        assert second.decision is ExecutionDecision.RETRY
        events = safety.drain_events()
        assert any(e.event_type == "execution.retry_requested" for e in events)
        third = safety.decide(
            user_id=user_id,
            request_id="dup-3",
            intent=intent,
            connected=True,
            login=7,
            recent=[first, second],
        )
        assert third.decision is ExecutionDecision.REJECT
        assert any("rapid" in r for r in third.rejection_reasons)

    def test_never_order_send(self) -> None:
        client = MockMT5Client()
        client.initialize()
        from app.domain.entities.execution_gateway import RETCODE_EXECUTION_DISABLED
        from app.domain.interfaces.mt5_client import MT5LoginRequest

        client.login(MT5LoginRequest(login=1, password="p", server="Demo"))
        adapter = MT5Adapter(client=client, execution_enabled=False)
        validation = MT5OrderValidationService(adapter=adapter)
        intent = OrderIntent(
            symbol="EURUSD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            volume=LotSize.of("0.01"),
        )
        request = validation.build_order_request(intent)
        result = adapter.order_send(request)
        assert result.retcode == RETCODE_EXECUTION_DISABLED


@pytest.mark.unit
class TestExecutionSafetyUseCase:
    @pytest.mark.asyncio
    async def test_check_allow_and_idempotency(self) -> None:
        mt5_factory, exec_factory, adapter, safety, audit = _wire()
        user_id = uuid4()
        await _connect(mt5_factory, adapter, audit, user_id)
        use_case = CheckExecutionSafetyUseCase(
            mt5_uow_factory=mt5_factory,
            execution_uow_factory=exec_factory,
            safety_service=safety,
            audit=audit,
        )
        cmd = ExecutionCheckCommand(
            user_id=user_id,
            request_id="idem-100",
            symbol="EURUSD",
            side="buy",
            order_type="market",
            volume="0.10",
        )
        first = await use_case.execute(cmd)
        assert first.decision == "allow"
        assert first.idempotent_replay is False
        second = await use_case.execute(cmd)
        assert second.decision == "allow"
        assert second.idempotent_replay is True
        assert second.id == first.id
        assert "password" not in str(first.calculated_risk)

    @pytest.mark.asyncio
    async def test_retry_on_duplicate_fingerprint(self) -> None:
        mt5_factory, exec_factory, adapter, safety, audit = _wire(
            policy=ExecutionPolicy(rapid_submit_limit=5)
        )
        user_id = uuid4()
        await _connect(mt5_factory, adapter, audit, user_id)
        use_case = CheckExecutionSafetyUseCase(
            mt5_uow_factory=mt5_factory,
            execution_uow_factory=exec_factory,
            safety_service=safety,
            audit=audit,
        )
        base = {
            "user_id": user_id,
            "symbol": "EURUSD",
            "side": "buy",
            "order_type": "market",
            "volume": "0.01",
        }
        a = await use_case.execute(
            ExecutionCheckCommand(request_id="r1", **base)  # type: ignore[arg-type]
        )
        b = await use_case.execute(
            ExecutionCheckCommand(request_id="r2", **base)  # type: ignore[arg-type]
        )
        assert a.decision == "allow"
        assert b.decision == "retry"
