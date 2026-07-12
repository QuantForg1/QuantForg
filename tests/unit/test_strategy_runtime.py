"""Unit tests for Strategy Runtime — never order_send / never enable execution."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.dto.strategy_runtime import (
    ListStrategySignalsCommand,
    StrategyEvaluateCommand,
)
from app.application.services.mt5_market_data import MT5MarketDataService
from app.application.services.risk_engine import RiskEngine
from app.application.services.strategy_runtime import (
    StrategyEvaluateInput,
    StrategyRuntimeService,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.application.use_cases.strategy_runtime import (
    EvaluateStrategyUseCase,
    ListStrategySignalsUseCase,
)
from app.domain.entities.risk_engine import RiskEngineConfig
from app.domain.entities.strategy_runtime import (
    AnalysisContext,
    StrategyRuntimeConfig,
)
from app.domain.enums.strategy import StrategyDecisionType
from app.domain.interfaces.mt5_client import MT5LoginRequest
from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter
from app.infrastructure.persistence.memory_broker import MemoryBrokerUnitOfWorkFactory
from app.infrastructure.persistence.memory_mt5 import MemoryMT5UnitOfWorkFactory
from app.infrastructure.persistence.memory_strategy import (
    MemoryStrategyUnitOfWorkFactory,
)
from core.config.settings import get_settings


def _bullish_analysis() -> AnalysisContext:
    return AnalysisContext(
        market_open=True,
        session="london",
        structure_bias="up",
        liquidity_sweep_bullish=True,
        order_block_bullish=True,
        fvg_bullish=True,
        has_structure=True,
        has_liquidity=True,
        has_order_blocks=True,
        has_fvgs=True,
    )


@pytest.mark.unit
class TestStrategyRuntimeService:
    def test_ready_on_confluence(self) -> None:
        runtime = StrategyRuntimeService(
            config=StrategyRuntimeConfig(consult_risk_engine=False)
        )
        result = runtime.evaluate(
            StrategyEvaluateInput(
                user_id=uuid4(),
                request_id="strat-ready-1",
                symbol="EURUSD",
                timeframe="m15",
                analysis=_bullish_analysis(),
                check_risk=False,
                tick_age_seconds=5.0,
                candle_count=50,
                last_price="1.08500",
                equity=Decimal("10000"),
            )
        )
        assert result.evaluation.decision is StrategyDecisionType.READY
        assert result.signal is not None
        assert result.signal.direction.value == "buy"
        assert 0.0 <= result.signal.confidence <= 1.0
        events = runtime.drain_events()
        assert any(e.event_type == "strategy.evaluated" for e in events)
        assert any(e.event_type == "strategy.signal_generated" for e in events)

    def test_blocked_on_stale_data(self) -> None:
        runtime = StrategyRuntimeService(
            config=StrategyRuntimeConfig(
                max_tick_age_seconds=30.0, consult_risk_engine=False
            )
        )
        result = runtime.evaluate(
            StrategyEvaluateInput(
                user_id=uuid4(),
                request_id="strat-stale-1",
                symbol="EURUSD",
                analysis=_bullish_analysis(),
                check_risk=False,
                tick_age_seconds=500.0,
                candle_count=50,
            )
        )
        assert result.evaluation.decision is StrategyDecisionType.BLOCKED
        events = runtime.drain_events()
        assert any(e.event_type == "strategy.blocked" for e in events)

    def test_blocked_when_market_closed(self) -> None:
        runtime = StrategyRuntimeService(
            config=StrategyRuntimeConfig(consult_risk_engine=False)
        )
        analysis = AnalysisContext(market_open=False, structure_bias="up")
        result = runtime.evaluate(
            StrategyEvaluateInput(
                user_id=uuid4(),
                request_id="strat-closed-1",
                symbol="EURUSD",
                analysis=analysis,
                check_risk=False,
                tick_age_seconds=1.0,
                candle_count=10,
            )
        )
        assert result.evaluation.decision is StrategyDecisionType.BLOCKED

    def test_watch_on_partial_setup(self) -> None:
        runtime = StrategyRuntimeService(
            config=StrategyRuntimeConfig(min_confluence=3, consult_risk_engine=False)
        )
        analysis = AnalysisContext(
            market_open=True,
            structure_bias="up",
            has_structure=True,
            liquidity_sweep_bullish=True,
            has_liquidity=True,
        )
        result = runtime.evaluate(
            StrategyEvaluateInput(
                user_id=uuid4(),
                request_id="strat-watch-1",
                symbol="GBPUSD",
                analysis=analysis,
                check_risk=False,
                tick_age_seconds=2.0,
                candle_count=20,
            )
        )
        assert result.evaluation.decision is StrategyDecisionType.WATCH
        assert result.signal is not None

    def test_no_action_without_setup(self) -> None:
        runtime = StrategyRuntimeService(
            config=StrategyRuntimeConfig(consult_risk_engine=False)
        )
        result = runtime.evaluate(
            StrategyEvaluateInput(
                user_id=uuid4(),
                request_id="strat-none-1",
                symbol="USDJPY",
                analysis=AnalysisContext(market_open=True),
                check_risk=False,
                tick_age_seconds=1.0,
                candle_count=10,
            )
        )
        assert result.evaluation.decision is StrategyDecisionType.NO_ACTION
        assert result.signal is None

    def test_risk_reject_blocks_and_rejects_signal(self) -> None:
        risk = RiskEngine(config=RiskEngineConfig(max_open_positions=0))
        runtime = StrategyRuntimeService(
            risk_engine=risk,
            config=StrategyRuntimeConfig(consult_risk_engine=True),
        )
        from app.domain.entities.mt5_portfolio import AccountSnapshot

        account = AccountSnapshot(
            login=1,
            balance=Decimal("10000"),
            equity=Decimal("10000"),
            margin=Decimal("0"),
            free_margin=Decimal("10000"),
            margin_level=Decimal("0"),
            profit=Decimal("0"),
            leverage=100,
        )
        result = runtime.evaluate(
            StrategyEvaluateInput(
                user_id=uuid4(),
                request_id="strat-risk-1",
                symbol="EURUSD",
                analysis=_bullish_analysis(),
                check_risk=True,
                tick_age_seconds=1.0,
                candle_count=50,
                last_price="1.08500",
                equity=Decimal("10000"),
                requested_lots=Decimal("0.10"),
                stop_loss_distance=Decimal("0.0020"),
            ),
            account=account,
            positions=[],
        )
        assert result.evaluation.decision is StrategyDecisionType.BLOCKED
        assert result.signal is not None
        assert result.signal.rejected is True
        events = runtime.drain_events()
        assert any(e.event_type == "strategy.signal_rejected" for e in events)

    def test_collects_from_mock_mt5(self) -> None:
        client = MockMT5Client()
        client.initialize()
        client.login(MT5LoginRequest(login=1, password="p", server="Demo"))
        adapter = MT5Adapter(client=client, execution_enabled=False)
        market = MT5MarketDataService(adapter=adapter)
        runtime = StrategyRuntimeService(
            market_data=market,
            config=StrategyRuntimeConfig(consult_risk_engine=False),
        )
        result = runtime.evaluate(
            StrategyEvaluateInput(
                user_id=uuid4(),
                request_id="strat-mt5-1",
                symbol="EURUSD",
                analysis=_bullish_analysis(),
                check_risk=False,
            )
        )
        assert result.evaluation.market_state["mt5_connected"] is True
        assert result.evaluation.decision is StrategyDecisionType.READY


@pytest.mark.unit
class TestStrategyUseCases:
    @pytest.mark.asyncio
    async def test_evaluate_persists_and_never_enables_execution(self) -> None:
        settings = get_settings()
        assert settings.execution_enabled is False

        strategy_factory = MemoryStrategyUnitOfWorkFactory()
        mt5_factory = MemoryMT5UnitOfWorkFactory()
        audit = RecordAuditEventUseCase(
            uow_factory=MemoryBrokerUnitOfWorkFactory()  # type: ignore[arg-type]
        )
        runtime = StrategyRuntimeService(
            config=StrategyRuntimeConfig(consult_risk_engine=False)
        )
        user_id = uuid4()
        use_case = EvaluateStrategyUseCase(
            strategy_uow_factory=strategy_factory,
            mt5_uow_factory=mt5_factory,
            runtime=runtime,
            portfolio_sync=None,
            audit=audit,
        )
        dto = await use_case.execute(
            StrategyEvaluateCommand(
                user_id=user_id,
                request_id="api-strat-1",
                symbol="EURUSD",
                structure_bias="up",
                liquidity_sweep_bullish=True,
                order_block_bullish=True,
                fvg_bullish=True,
                has_structure=True,
                has_liquidity=True,
                has_order_blocks=True,
                has_fvgs=True,
                check_risk=False,
                tick_age_seconds=1.0,
                candle_count=50,
                last_price="1.08500",
                equity="10000",
            )
        )
        assert dto.decision == "ready"
        assert dto.signal is not None

        listed = await ListStrategySignalsUseCase(
            strategy_uow_factory=strategy_factory
        ).execute(ListStrategySignalsCommand(user_id=user_id))
        assert listed.count == 1
        assert listed.items[0].direction == "buy"

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
