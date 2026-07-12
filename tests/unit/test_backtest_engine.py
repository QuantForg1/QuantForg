"""Unit tests for Backtesting Engine — never order_send / never live broker."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.dto.backtest import (
    BacktestBarCommand,
    GetBacktestCommand,
    ListBacktestsCommand,
    RunBacktestCommand,
)
from app.application.services.backtest_engine import (
    BacktestBarInput,
    BacktestEngine,
    BacktestRunInput,
)
from app.application.services.backtest_metrics import MetricsEngine
from app.application.services.historical_replay import HistoricalReplayEngine
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.application.services.strategy_runtime import StrategyRuntimeService
from app.application.use_cases.backtest import (
    GetBacktestUseCase,
    ListBacktestsUseCase,
    RunBacktestUseCase,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.entities.backtest import BacktestAssumptions, EquityPoint
from app.domain.entities.execution_gateway import RETCODE_EXECUTION_DISABLED
from app.domain.entities.mt5_order import OrderIntent
from app.domain.entities.strategy_runtime import StrategyRuntimeConfig
from app.domain.enums.backtest import BacktestStatus, ReplayControlState, ReplayMode
from app.domain.enums.order import OrderSide, OrderType
from app.domain.interfaces.mt5_client import MT5LoginRequest
from app.domain.value_objects.mt5_order import LotSize
from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter
from app.infrastructure.persistence.memory_backtest import (
    MemoryBacktestUnitOfWorkFactory,
)
from app.infrastructure.persistence.memory_broker import MemoryBrokerUnitOfWorkFactory
from core.config.settings import get_settings


def _bars(n: int = 30, *, up: bool = True) -> list[BacktestBarInput]:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    price = Decimal("1.08000")
    out: list[BacktestBarInput] = []
    for i in range(n):
        step = Decimal("0.00020") if up else Decimal("-0.00020")
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
class TestHistoricalReplay:
    def test_pause_resume_step_speed(self) -> None:
        engine = HistoricalReplayEngine()
        engine.load_raw_bars(
            [
                {
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "open": "1.0",
                    "high": "1.1",
                    "low": "0.9",
                    "close": "1.05",
                },
                {
                    "timestamp": "2026-01-01T00:15:00+00:00",
                    "open": "1.05",
                    "high": "1.2",
                    "low": "1.0",
                    "close": "1.15",
                },
                {
                    "timestamp": "2026-01-01T00:30:00+00:00",
                    "open": "1.15",
                    "high": "1.3",
                    "low": "1.1",
                    "close": "1.25",
                },
            ]
        )
        engine.start()
        engine.set_speed(2.0)
        assert engine.clock is not None
        assert engine.clock.speed == 2.0

        first = engine.step_forward()
        assert first is not None
        engine.pause()
        assert engine.controller.state is ReplayControlState.PAUSED
        assert engine.step_forward() is None
        engine.resume()
        second = engine.step_forward()
        assert second is not None
        remaining = engine.run_all()
        assert len(remaining) == 1
        assert engine.controller.state is ReplayControlState.COMPLETED


@pytest.mark.unit
class TestMetricsEngine:
    def test_basic_metrics(self) -> None:
        curve = [
            EquityPoint(
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                equity=Decimal("10000"),
                balance=Decimal("10000"),
                drawdown_pct=Decimal("0"),
                bar_index=0,
            ),
            EquityPoint(
                timestamp=datetime(2026, 6, 1, tzinfo=UTC),
                equity=Decimal("11000"),
                balance=Decimal("11000"),
                drawdown_pct=Decimal("5"),
                bar_index=1,
            ),
        ]
        metrics = MetricsEngine().compute(
            trades=[],
            equity_curve=curve,
            initial_balance=Decimal("10000"),
        )
        assert metrics.total_return_pct == Decimal("10.0000")
        assert metrics.max_drawdown_pct == Decimal("5.0000")


@pytest.mark.unit
class TestBacktestEngine:
    def test_run_produces_curves_and_never_enables_execution(self) -> None:
        settings = get_settings()
        assert settings.execution_enabled is False

        engine = BacktestEngine(
            strategy_runtime=StrategyRuntimeService(
                config=StrategyRuntimeConfig(consult_risk_engine=True)
            ),
            metrics_engine=MetricsEngine(),
        )
        result = engine.run(
            BacktestRunInput(
                user_id=uuid4(),
                request_id="bt-1",
                symbol="EURUSD",
                timeframe="m15",
                initial_balance=Decimal("10000"),
                bars=tuple(_bars(40)),
                assumptions=BacktestAssumptions(
                    lot_size=Decimal("0.10"),
                    stop_loss_distance=Decimal("0.0010"),
                    take_profit_distance=Decimal("0.0020"),
                ),
                auto_analysis=True,
                consult_execution_safety=False,
            )
        )
        assert result.run.status is BacktestStatus.COMPLETED
        assert len(result.equity_curve) >= 1
        assert "total_return_pct" in result.run.metrics
        assert "max_drawdown_pct" in result.run.metrics
        events = engine.drain_events()
        assert any(e.event_type == "backtest.started" for e in events)
        assert any(e.event_type == "backtest.finished" for e in events)
        assert any(e.event_type == "backtest.metric_updated" for e in events)

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

    def test_tick_mode_replay(self) -> None:
        engine = BacktestEngine(
            strategy_runtime=StrategyRuntimeService(
                config=StrategyRuntimeConfig(consult_risk_engine=False)
            )
        )
        ticks = tuple(
            {
                "timestamp": (
                    datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=i)
                ).isoformat(),
                "open": str(Decimal("1.08") + Decimal("0.0001") * i),
                "high": str(Decimal("1.08") + Decimal("0.0001") * i),
                "low": str(Decimal("1.08") + Decimal("0.0001") * i),
                "close": str(Decimal("1.08") + Decimal("0.0001") * i),
            }
            for i in range(20)
        )
        result = engine.run(
            BacktestRunInput(
                user_id=uuid4(),
                request_id="bt-tick-1",
                symbol="EURUSD",
                ticks=ticks,
                replay_mode=ReplayMode.TICK,
                auto_analysis=True,
                consult_execution_safety=False,
            )
        )
        assert result.run.status is BacktestStatus.COMPLETED
        assert result.run.replay_mode is ReplayMode.TICK


@pytest.mark.unit
class TestBacktestUseCases:
    @pytest.mark.asyncio
    async def test_run_list_get(self) -> None:
        settings = get_settings()
        assert settings.execution_enabled is False

        factory = MemoryBacktestUnitOfWorkFactory()
        audit = RecordAuditEventUseCase(
            uow_factory=MemoryBrokerUnitOfWorkFactory()  # type: ignore[arg-type]
        )
        engine = BacktestEngine(
            strategy_runtime=StrategyRuntimeService(
                config=StrategyRuntimeConfig(consult_risk_engine=True)
            )
        )
        user_id = uuid4()
        run_uc = RunBacktestUseCase(
            backtest_uow_factory=factory,
            engine=engine,
            audit=audit,
        )
        bars = _bars(25)
        dto = await run_uc.execute(
            RunBacktestCommand(
                user_id=user_id,
                request_id="api-bt-1",
                symbol="EURUSD",
                bars=tuple(
                    BacktestBarCommand(
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
                consult_execution_safety=False,
            )
        )
        assert dto.status == "completed"
        assert dto.bar_count == 25

        listed = await ListBacktestsUseCase(backtest_uow_factory=factory).execute(
            ListBacktestsCommand(user_id=user_id)
        )
        assert listed.count == 1

        got = await GetBacktestUseCase(backtest_uow_factory=factory).execute(
            GetBacktestCommand(user_id=user_id, backtest_id=dto.id)
        )
        assert got.id == dto.id
        assert got.metrics
