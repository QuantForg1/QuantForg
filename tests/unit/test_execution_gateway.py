"""Unit tests for MT5 Adapter Sprint 4 — Execution Gateway."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.dto.execution import ExecutionSubmitCommand
from app.application.dto.mt5 import MT5ConnectCommand
from app.application.services.execution_gateway import ExecutionGateway
from app.application.services.execution_intelligence import ExecutionIntelligenceService
from app.application.services.execution_safety import ExecutionSafetyService
from app.application.services.institutional_execution_engine import (
    InstitutionalExecutionEngine,
)
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.application.use_cases.execution_gateway import SubmitExecutionUseCase
from app.application.use_cases.mt5 import ConnectMT5UseCase
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.entities.execution_gateway import (
    RETCODE_EXECUTION_DISABLED,
    RETCODE_REQUOTE,
    map_retcode_to_outcome,
)
from app.domain.entities.mt5_order import OrderIntent
from app.domain.enums.execution import ExecutionOutcome
from app.domain.enums.order import OrderSide, OrderType
from app.domain.exceptions.auth import AuthorizationError
from app.domain.execution_engine.journal import ExecutionJournalStore
from app.domain.interfaces.mt5_client import MT5LoginRequest
from app.domain.interfaces.mt5_order import RETCODE_DONE, RETCODE_NO_MONEY
from app.domain.value_objects.mt5_order import LotSize
from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter
from app.infrastructure.persistence.memory_broker import MemoryBrokerUnitOfWorkFactory
from app.infrastructure.persistence.memory_execution import (
    MemoryExecutionUnitOfWorkFactory,
)
from app.infrastructure.persistence.memory_mt5 import MemoryMT5UnitOfWorkFactory


def _intent() -> OrderIntent:
    return OrderIntent(
        symbol="EURUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        volume=LotSize.of("0.01"),
    )


def _wire(*, execution_enabled: bool = False) -> tuple[
    MemoryMT5UnitOfWorkFactory,
    MemoryExecutionUnitOfWorkFactory,
    MT5Adapter,
    ExecutionGateway,
    RecordAuditEventUseCase,
    MockMT5Client,
    InstitutionalExecutionEngine,
]:
    client = MockMT5Client()
    adapter = MT5Adapter(client=client, execution_enabled=execution_enabled)
    validation = MT5OrderValidationService(adapter=adapter)
    gateway = ExecutionGateway(adapter=adapter, order_validation=validation)
    safety = ExecutionSafetyService(adapter=adapter, order_validation=validation)
    engine = InstitutionalExecutionEngine(
        gateway=gateway,
        safety=safety,
        order_validation=validation,
        intelligence=ExecutionIntelligenceService(),
        journal=ExecutionJournalStore(),
    )
    mt5_factory = MemoryMT5UnitOfWorkFactory()
    exec_factory = MemoryExecutionUnitOfWorkFactory()
    audit = RecordAuditEventUseCase(
        uow_factory=MemoryBrokerUnitOfWorkFactory()  # type: ignore[arg-type]
    )
    return mt5_factory, exec_factory, adapter, gateway, audit, client, engine


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
            login=6001,
            password="secret",
            server="Demo-Server",
        )
    )


@pytest.mark.unit
class TestRetcodeMapping:
    def test_success_failure_retry_disabled(self) -> None:
        assert map_retcode_to_outcome(RETCODE_DONE)[0] is ExecutionOutcome.SUCCESS
        assert map_retcode_to_outcome(RETCODE_NO_MONEY)[0] is ExecutionOutcome.FAILED
        outcome, retryable, _ = map_retcode_to_outcome(RETCODE_REQUOTE)
        assert outcome is ExecutionOutcome.RETRY
        assert retryable is True
        assert (
            map_retcode_to_outcome(RETCODE_EXECUTION_DISABLED)[0]
            is ExecutionOutcome.DISABLED
        )


@pytest.mark.unit
class TestExecutionGatewayDisabled:
    def test_submit_never_calls_client_when_disabled(self) -> None:
        client = MockMT5Client()
        client.initialize()
        client.login(MT5LoginRequest(login=1, password="p", server="S"))
        adapter = MT5Adapter(client=client, execution_enabled=False)
        validation = MT5OrderValidationService(adapter=adapter)
        gateway = ExecutionGateway(adapter=adapter, order_validation=validation)
        before = len(client.list_positions())
        result = gateway.submit(_intent(), user_id=uuid4(), request_id="dis-1")
        assert result.outcome is ExecutionOutcome.DISABLED
        assert result.retcode == RETCODE_EXECUTION_DISABLED
        assert len(client.list_positions()) == before
        events = gateway.drain_events()
        types = {e.event_type for e in events}
        assert "execution.requested" in types
        assert "execution.disabled" in types

    def test_adapter_order_send_returns_disabled(self) -> None:
        client = MockMT5Client()
        client.initialize()
        client.login(MT5LoginRequest(login=1, password="p", server="S"))
        adapter = MT5Adapter(client=client, execution_enabled=False)
        validation = MT5OrderValidationService(adapter=adapter)
        req = validation.build_order_request(_intent())
        raw = adapter.order_send(req)
        assert raw.retcode == RETCODE_EXECUTION_DISABLED


@pytest.mark.unit
class TestExecutionGatewayEnabled:
    def test_success_mapping(self) -> None:
        client = MockMT5Client()
        client.initialize()
        client.login(MT5LoginRequest(login=1, password="p", server="S"))
        adapter = MT5Adapter(client=client, execution_enabled=True)
        gateway = ExecutionGateway(
            adapter=adapter,
            order_validation=MT5OrderValidationService(adapter=adapter),
        )
        result = gateway.submit(_intent(), user_id=uuid4(), request_id="ok-1")
        assert result.outcome is ExecutionOutcome.SUCCESS
        assert result.order_ticket is not None
        events = {e.event_type for e in gateway.drain_events()}
        assert "execution.submitted" in events

    def test_failure_mapping(self) -> None:
        client = MockMT5Client(force_send_retcode=RETCODE_NO_MONEY)
        client.initialize()
        client.login(MT5LoginRequest(login=1, password="p", server="S"))
        adapter = MT5Adapter(client=client, execution_enabled=True)
        gateway = ExecutionGateway(
            adapter=adapter,
            order_validation=MT5OrderValidationService(adapter=adapter),
        )
        result = gateway.submit(_intent(), user_id=uuid4(), request_id="fail-1")
        assert result.outcome is ExecutionOutcome.FAILED
        assert result.retryable is False
        events = {e.event_type for e in gateway.drain_events()}
        assert "execution.failed" in events

    def test_retry_mapping(self) -> None:
        client = MockMT5Client(force_send_retcode=RETCODE_REQUOTE)
        client.initialize()
        client.login(MT5LoginRequest(login=1, password="p", server="S"))
        adapter = MT5Adapter(client=client, execution_enabled=True)
        gateway = ExecutionGateway(
            adapter=adapter,
            order_validation=MT5OrderValidationService(adapter=adapter),
        )
        result = gateway.submit(_intent(), user_id=uuid4(), request_id="retry-1")
        assert result.outcome is ExecutionOutcome.RETRY
        assert result.retryable is True

    def test_cancel(self) -> None:
        client = MockMT5Client()
        client.initialize()
        client.login(MT5LoginRequest(login=1, password="p", server="S"))
        adapter = MT5Adapter(client=client, execution_enabled=True)
        gateway = ExecutionGateway(
            adapter=adapter,
            order_validation=MT5OrderValidationService(adapter=adapter),
        )
        pending = client.list_orders()
        assert pending
        result = gateway.cancel(
            pending[0].ticket,
            user_id=uuid4(),
            request_id="cancel-1",
            symbol=pending[0].symbol,
        )
        assert result.outcome is ExecutionOutcome.SUCCESS
        assert client.order_by_ticket(pending[0].ticket) is None


@pytest.mark.unit
class TestSubmitExecutionUseCase:
    @pytest.mark.asyncio
    async def test_disabled_raises_403(self) -> None:
        mt5_factory, exec_factory, adapter, _gateway, audit, _, engine = _wire(
            execution_enabled=False
        )
        user_id = uuid4()
        await _connect(mt5_factory, adapter, audit, user_id)
        use_case = SubmitExecutionUseCase(
            mt5_uow_factory=mt5_factory,
            execution_uow_factory=exec_factory,
            engine=engine,
            audit=audit,
        )
        with pytest.raises(AuthorizationError) as exc:
            await use_case.execute(
                ExecutionSubmitCommand(
                    user_id=user_id,
                    request_id="api-dis-1",
                    symbol="EURUSD",
                    side="buy",
                    volume="0.01",
                )
            )
        assert exc.value.code == "execution_disabled"

    @pytest.mark.asyncio
    async def test_idempotency(self) -> None:
        mt5_factory, exec_factory, adapter, _gateway, audit, _, engine = _wire(
            execution_enabled=True
        )
        user_id = uuid4()
        await _connect(mt5_factory, adapter, audit, user_id)
        use_case = SubmitExecutionUseCase(
            mt5_uow_factory=mt5_factory,
            execution_uow_factory=exec_factory,
            engine=engine,
            audit=audit,
        )
        cmd = ExecutionSubmitCommand(
            user_id=user_id,
            request_id="idem-gw-1",
            symbol="EURUSD",
            side="buy",
            volume="0.01",
        )
        first = await use_case.execute(cmd)
        assert first.outcome == "success"
        assert first.stages
        second = await use_case.execute(cmd)
        assert second.idempotent_replay is True
        assert second.id == first.id
        assert second.order_ticket == first.order_ticket
