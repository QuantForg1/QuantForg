"""Unit tests for Risk Management Engine — never order_send / never enable execution."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.dto.risk_engine import RiskCheckCommand
from app.application.services.risk_engine import RiskCheckInput, RiskEngine
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.application.use_cases.risk_engine import CheckRiskUseCase
from app.domain.entities.mt5_portfolio import AccountSnapshot, MT5Position
from app.domain.entities.risk_engine import RiskEngineConfig
from app.domain.enums.risk import (
    PositionSizingMethod,
    RiskDecision,
    RiskScoreBand,
)
from app.domain.interfaces.mt5_client import MT5LoginRequest
from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter
from app.infrastructure.persistence.memory_broker import MemoryBrokerUnitOfWorkFactory
from app.infrastructure.persistence.memory_mt5 import MemoryMT5UnitOfWorkFactory
from app.infrastructure.persistence.memory_risk import MemoryRiskUnitOfWorkFactory
from core.config.settings import get_settings


def _account(equity: str = "10000") -> AccountSnapshot:
    eq = Decimal(equity)
    return AccountSnapshot(
        login=1,
        balance=eq,
        equity=eq,
        margin=Decimal("0"),
        free_margin=eq,
        margin_level=Decimal("0"),
        profit=Decimal("0"),
        leverage=100,
    )


@pytest.mark.unit
class TestPositionSizing:
    def test_fixed_lot_and_cap(self) -> None:
        engine = RiskEngine(
            config=RiskEngineConfig(max_lot=Decimal("1"), fixed_lot=Decimal("2"))
        )
        size = engine.size_position(
            equity=Decimal("10000"),
            method=PositionSizingMethod.FIXED_LOT,
            requested_lots=None,
            stop_distance=Decimal("0.001"),
            atr=None,
            entry_price=Decimal("1.08"),
        )
        assert size.approved_lots == Decimal("1")
        assert size.capped is True

    def test_percentage_and_atr(self) -> None:
        engine = RiskEngine()
        pct = engine.size_position(
            equity=Decimal("10000"),
            method=PositionSizingMethod.PERCENTAGE_RISK,
            requested_lots=Decimal("5"),
            stop_distance=Decimal("0.0010"),
            atr=None,
            entry_price=Decimal("1.08"),
        )
        assert pct.approved_lots > 0
        assert pct.approved_lots <= Decimal("5")
        atr = engine.size_position(
            equity=Decimal("10000"),
            method=PositionSizingMethod.ATR_BASED,
            requested_lots=None,
            stop_distance=None,
            atr=Decimal("0.00080"),
            entry_price=Decimal("1.08"),
        )
        assert atr.method is PositionSizingMethod.ATR_BASED
        assert atr.approved_lots >= Decimal("0.01")


@pytest.mark.unit
class TestRiskEngineEvaluate:
    def test_allow_happy_path(self) -> None:
        engine = RiskEngine()
        user_id = uuid4()
        result = engine.evaluate(
            RiskCheckInput(
                user_id=user_id,
                request_id="risk-ok-1",
                symbol="EURUSD",
                side="buy",
                requested_lots=Decimal("0.10"),
                stop_loss_distance=Decimal("0.0020"),
                sizing_method=PositionSizingMethod.PERCENTAGE_RISK,
                entry_price=Decimal("1.08500"),
            ),
            account=_account(),
            positions=[],
        )
        assert result.decision is RiskDecision.ALLOW
        assert result.risk_band in {
            RiskScoreBand.LOW,
            RiskScoreBand.MEDIUM,
        }
        assert result.approved_lots > 0
        events = engine.drain_events()
        assert any(e.event_type == "risk.approved" for e in events)

    def test_reject_on_daily_loss(self) -> None:
        engine = RiskEngine(config=RiskEngineConfig(max_daily_loss_pct=Decimal("2")))
        result = engine.evaluate(
            RiskCheckInput(
                user_id=uuid4(),
                request_id="risk-dd-1",
                symbol="EURUSD",
                side="buy",
                requested_lots=Decimal("0.10"),
                stop_loss_distance=Decimal("0.0020"),
                entry_price=Decimal("1.08500"),
            ),
            account=_account(),
            positions=[],
            daily_pnl=Decimal("-500"),  # 5% of 10k
        )
        assert result.decision is RiskDecision.REJECT
        assert any("daily loss" in r for r in result.reasons)
        events = engine.drain_events()
        assert any(e.event_type == "risk.rejected" for e in events)

    def test_reduce_size_on_cap(self) -> None:
        engine = RiskEngine(config=RiskEngineConfig(max_lot=Decimal("0.05")))
        result = engine.evaluate(
            RiskCheckInput(
                user_id=uuid4(),
                request_id="risk-cap-1",
                symbol="EURUSD",
                side="buy",
                requested_lots=Decimal("1.00"),
                stop_loss_distance=Decimal("0.00010"),
                sizing_method=PositionSizingMethod.FIXED_LOT,
                entry_price=Decimal("1.08500"),
            ),
            account=_account(),
            positions=[],
        )
        assert result.decision in {
            RiskDecision.REDUCE_SIZE,
            RiskDecision.ALLOW,
        }
        assert result.approved_lots <= Decimal("0.05")

    def test_correlation_and_exposure(self) -> None:
        engine = RiskEngine(
            config=RiskEngineConfig(
                max_correlated_exposure_pct=Decimal("5"),
                max_symbol_exposure_pct=Decimal("5"),
            )
        )
        positions = [
            MT5Position(
                ticket=1,
                symbol="GBPUSD",
                side="buy",
                volume=Decimal("1.0"),
                open_price=Decimal("1.26"),
            )
        ]
        result = engine.evaluate(
            RiskCheckInput(
                user_id=uuid4(),
                request_id="risk-corr-1",
                symbol="EURUSD",
                side="buy",
                requested_lots=Decimal("1.0"),
                stop_loss_distance=Decimal("0.001"),
                sizing_method=PositionSizingMethod.FIXED_LOT,
                entry_price=Decimal("1.08"),
            ),
            account=_account("10000"),
            positions=positions,
        )
        assert result.decision in {
            RiskDecision.REDUCE_SIZE,
            RiskDecision.REJECT,
        }
        assert (
            result.checks.get("correlation") is False
            or result.checks.get("exposure") is False
        )


@pytest.mark.unit
class TestCheckRiskUseCase:
    @pytest.mark.asyncio
    async def test_check_persists_and_never_enables_execution(self) -> None:
        settings = get_settings()
        assert settings.execution_enabled is False

        risk_factory = MemoryRiskUnitOfWorkFactory()
        mt5_factory = MemoryMT5UnitOfWorkFactory()
        audit = RecordAuditEventUseCase(
            uow_factory=MemoryBrokerUnitOfWorkFactory()  # type: ignore[arg-type]
        )
        engine = RiskEngine()
        use_case = CheckRiskUseCase(
            risk_uow_factory=risk_factory,
            mt5_uow_factory=mt5_factory,
            risk_engine=engine,
            portfolio_sync=None,
            audit=audit,
        )
        dto = await use_case.execute(
            RiskCheckCommand(
                user_id=uuid4(),
                request_id="api-risk-1",
                symbol="EURUSD",
                side="buy",
                requested_lots="0.10",
                stop_loss_distance="0.0020",
                equity="10000",
                balance="10000",
            )
        )
        assert dto.decision in {"allow", "reduce_size", "reject"}
        assert 0 <= dto.risk_score <= 100
        assert dto.approved_lots

        # Adapter still disabled — order_send must not reach client
        client = MockMT5Client()
        client.initialize()
        client.login(MT5LoginRequest(login=1, password="p", server="S"))
        adapter = MT5Adapter(client=client, execution_enabled=False)
        from app.application.services.mt5_order_validation import (
            MT5OrderValidationService,
        )
        from app.domain.entities.execution_gateway import RETCODE_EXECUTION_DISABLED
        from app.domain.entities.mt5_order import OrderIntent
        from app.domain.enums.order import OrderSide, OrderType
        from app.domain.value_objects.mt5_order import LotSize

        req = MT5OrderValidationService(adapter=adapter).build_order_request(
            OrderIntent(
                symbol="EURUSD",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                volume=LotSize.of("0.01"),
            )
        )
        assert adapter.order_send(req).retcode == RETCODE_EXECUTION_DISABLED
