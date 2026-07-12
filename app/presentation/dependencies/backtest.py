"""Backtesting Engine FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends

from app.application.services.backtest_engine import BacktestEngine
from app.application.services.backtest_metrics import MetricsEngine
from app.application.services.execution_safety import ExecutionSafetyService
from app.application.services.risk_engine import RiskEngine
from app.application.services.strategy_runtime import StrategyRuntimeService
from app.application.use_cases.backtest import (
    GetBacktestUseCase,
    ListBacktestsUseCase,
    RunBacktestUseCase,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.entities.risk_engine import RiskEngineConfig
from app.domain.entities.strategy_runtime import StrategyRuntimeConfig
from core.di.container import get_container


def get_backtest_uow_factory() -> Any:
    factory = getattr(get_container(), "backtest_uow_factory", None)
    if factory is None:
        msg = "Backtest Unit of Work factory is not available"
        raise RuntimeError(msg)
    return factory


def get_strategy_runtime() -> StrategyRuntimeService:
    runtime = getattr(get_container(), "strategy_runtime", None)
    if runtime is not None:
        return runtime  # type: ignore[no-any-return]
    return StrategyRuntimeService(config=StrategyRuntimeConfig())


def get_risk_engine() -> RiskEngine:
    engine = getattr(get_container(), "risk_engine", None)
    if engine is not None:
        return engine  # type: ignore[no-any-return]
    return RiskEngine(config=RiskEngineConfig())


def get_execution_safety() -> ExecutionSafetyService | None:
    return getattr(get_container(), "execution_safety", None)


def get_backtest_engine() -> BacktestEngine:
    engine = getattr(get_container(), "backtest_engine", None)
    if engine is not None:
        return engine  # type: ignore[no-any-return]
    return BacktestEngine(
        strategy_runtime=get_strategy_runtime(),
        risk_engine=get_risk_engine(),
        execution_safety=get_execution_safety(),
        metrics_engine=MetricsEngine(),
    )


def get_run_backtest() -> RunBacktestUseCase:
    broker_uow = getattr(get_container(), "broker_uow_factory", None)
    if broker_uow is None:
        msg = "Broker Unit of Work factory is not available for audit"
        raise RuntimeError(msg)
    return RunBacktestUseCase(
        backtest_uow_factory=get_backtest_uow_factory(),
        engine=get_backtest_engine(),
        audit=RecordAuditEventUseCase(uow_factory=broker_uow),
    )


def get_list_backtests() -> ListBacktestsUseCase:
    return ListBacktestsUseCase(backtest_uow_factory=get_backtest_uow_factory())


def get_get_backtest() -> GetBacktestUseCase:
    return GetBacktestUseCase(backtest_uow_factory=get_backtest_uow_factory())


RunBacktestDep = Annotated[RunBacktestUseCase, Depends(get_run_backtest)]
ListBacktestsDep = Annotated[ListBacktestsUseCase, Depends(get_list_backtests)]
GetBacktestDep = Annotated[GetBacktestUseCase, Depends(get_get_backtest)]
