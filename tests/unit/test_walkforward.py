"""Unit tests for Walk-Forward Validation — never order_send / never live trades."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.dto.walkforward import (
    GetWalkForwardCommand,
    ListWalkForwardCommand,
    RunWalkForwardCommand,
    WalkForwardBarCommand,
)
from app.application.services.backtest_engine import (
    BacktestBarInput,
    BacktestEngine,
)
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.application.services.rolling_windows import RollingWindowScheduler
from app.application.services.strategy_runtime import StrategyRuntimeService
from app.application.services.walkforward_engine import (
    WalkForwardEngine,
    WalkForwardRunInput,
)
from app.application.services.walkforward_robustness import RobustnessEngine
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.application.use_cases.walkforward import (
    GetWalkForwardUseCase,
    ListWalkForwardUseCase,
    RunWalkForwardUseCase,
)
from app.domain.entities.execution_gateway import RETCODE_EXECUTION_DISABLED
from app.domain.entities.mt5_order import OrderIntent
from app.domain.entities.strategy_runtime import StrategyRuntimeConfig
from app.domain.entities.walkforward import WalkForwardWindowConfig
from app.domain.enums.order import OrderSide, OrderType
from app.domain.enums.walkforward import (
    PromotionDecision,
    WalkForwardStatus,
)
from app.domain.interfaces.mt5_client import MT5LoginRequest
from app.domain.value_objects.mt5_order import LotSize
from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter
from app.infrastructure.persistence.memory_broker import MemoryBrokerUnitOfWorkFactory
from app.infrastructure.persistence.memory_walkforward import (
    MemoryWalkForwardUnitOfWorkFactory,
)
from core.config.settings import get_settings


def _bars(n: int = 120, *, up: bool = True) -> list[BacktestBarInput]:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    price = Decimal("1.08000")
    out: list[BacktestBarInput] = []
    for i in range(n):
        # Alternate mild regimes so OOS is not identical
        direction = up if (i // 30) % 2 == 0 else not up
        step = Decimal("0.00015") if direction else Decimal("-0.00010")
        o = price
        c = price + step
        h = max(o, c) + Decimal("0.00005")
        low = min(o, c) - Decimal("0.00005")
        t0 = base + timedelta(minutes=15 * i)
        t1 = t0 + timedelta(minutes=15)
        out.append(
            BacktestBarInput(
                open_time=t0.isoformat(),
                close_time=t1.isoformat(),
                open=str(o),
                high=str(h),
                low=str(low),
                close=str(c),
                volume="1",
            )
        )
        price = c
    return out


@pytest.mark.unit
class TestRollingWindows:
    def test_rolling_and_anchored(self) -> None:
        scheduler = RollingWindowScheduler()
        rolling = scheduler.build(
            bar_count=100,
            config=WalkForwardWindowConfig(
                in_sample_bars=40, out_of_sample_bars=20, step_bars=20
            ),
        )
        assert len(rolling) >= 2
        assert rolling[0].is_start == 0
        assert rolling[0].oos_end == 60

        anchored = scheduler.build(
            bar_count=100,
            config=WalkForwardWindowConfig(
                in_sample_bars=40,
                out_of_sample_bars=20,
                step_bars=20,
                anchored=True,
            ),
        )
        assert all(w.is_start == 0 for w in anchored)
        assert anchored[1].is_end > anchored[0].is_end


@pytest.mark.unit
class TestWalkForwardEngine:
    def test_run_produces_promotion_and_never_order_send(self) -> None:
        settings = get_settings()
        assert settings.execution_enabled is False

        backtest = BacktestEngine(
            strategy_runtime=StrategyRuntimeService(
                config=StrategyRuntimeConfig(consult_risk_engine=True)
            )
        )
        engine = WalkForwardEngine(
            backtest_engine=backtest,
            window_scheduler=RollingWindowScheduler(),
            robustness_engine=RobustnessEngine(),
        )
        result = engine.run(
            WalkForwardRunInput(
                user_id=uuid4(),
                request_id="wf-1",
                symbol="EURUSD",
                bars=tuple(_bars(120)),
                window_config=WalkForwardWindowConfig(
                    in_sample_bars=40,
                    out_of_sample_bars=20,
                    step_bars=20,
                ),
                optimize_params=True,
            )
        )
        assert result.run.status is WalkForwardStatus.COMPLETED
        assert result.run.promotion in {
            PromotionDecision.PROMOTE_TO_PAPER,
            PromotionDecision.NEEDS_REWORK,
            PromotionDecision.REJECT,
        }
        assert result.run.fold_count >= 1
        assert "total_return_pct" in result.run.aggregated_oos
        assert "robustness_score" in result.run.robustness
        assert "is_metrics" in result.run.report
        assert "oos_metrics" in result.run.report
        events = engine.drain_events()
        assert any(e.event_type == "walkforward.started" for e in events)
        assert any(e.event_type == "walkforward.finished" for e in events)

        client = MockMT5Client()
        client.initialize()
        client.login(MT5LoginRequest(login=1, password="p", server="S"))
        adapter = MT5Adapter(client=client, execution_enabled=False)
        req = MT5OrderValidationService(adapter=adapter).build_order_request(
            OrderIntent(
                symbol="EURUSD",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                volume=LotSize.of("0.01"),
            )
        )
        assert adapter.order_send(req).retcode == RETCODE_EXECUTION_DISABLED


@pytest.mark.unit
class TestWalkForwardUseCases:
    @pytest.mark.asyncio
    async def test_run_list_get(self) -> None:
        settings = get_settings()
        assert settings.execution_enabled is False

        backtest = BacktestEngine(
            strategy_runtime=StrategyRuntimeService(
                config=StrategyRuntimeConfig(consult_risk_engine=True)
            )
        )
        engine = WalkForwardEngine(backtest_engine=backtest)
        factory = MemoryWalkForwardUnitOfWorkFactory()
        audit = RecordAuditEventUseCase(
            uow_factory=MemoryBrokerUnitOfWorkFactory()  # type: ignore[arg-type]
        )
        user_id = uuid4()
        bars = _bars(100)
        dto = await RunWalkForwardUseCase(
            walkforward_uow_factory=factory,
            engine=engine,
            audit=audit,
        ).execute(
            RunWalkForwardCommand(
                user_id=user_id,
                request_id="api-wf-1",
                symbol="EURUSD",
                bars=tuple(
                    WalkForwardBarCommand(
                        open_time=b.open_time,
                        open=b.open,
                        high=b.high,
                        low=b.low,
                        close=b.close,
                        volume=b.volume,
                        close_time=b.close_time,
                    )
                    for b in bars
                ),
                in_sample_bars=40,
                out_of_sample_bars=20,
                step_bars=20,
            )
        )
        assert dto.status == "completed"
        assert dto.fold_count >= 1

        listed = await ListWalkForwardUseCase(walkforward_uow_factory=factory).execute(
            ListWalkForwardCommand(user_id=user_id)
        )
        assert listed.count == 1

        got = await GetWalkForwardUseCase(walkforward_uow_factory=factory).execute(
            GetWalkForwardCommand(user_id=user_id, run_id=dto.id)
        )
        assert got.id == dto.id
        assert got.report
