"""Strategy Runtime FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends

from app.application.services.mt5_market_data import MT5MarketDataService
from app.application.services.portfolio_sync import PortfolioSyncService
from app.application.services.risk_engine import RiskEngine
from app.application.services.strategy_runtime import StrategyRuntimeService
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.application.use_cases.strategy_runtime import (
    EvaluateStrategyUseCase,
    ListStrategySignalsUseCase,
)
from app.domain.entities.risk_engine import RiskEngineConfig
from app.domain.entities.strategy_runtime import StrategyRuntimeConfig
from core.di.container import get_container


def get_mt5_uow_factory() -> Any:
    factory = getattr(get_container(), "mt5_uow_factory", None)
    if factory is None:
        msg = "MT5 Unit of Work factory is not available"
        raise RuntimeError(msg)
    return factory


def get_strategy_uow_factory() -> Any:
    factory = getattr(get_container(), "strategy_uow_factory", None)
    if factory is None:
        msg = "Strategy Unit of Work factory is not available"
        raise RuntimeError(msg)
    return factory


def get_portfolio_sync() -> PortfolioSyncService | None:
    return getattr(get_container(), "portfolio_sync", None)


def get_market_data() -> MT5MarketDataService | None:
    return getattr(get_container(), "mt5_market_data", None)


def get_risk_engine() -> RiskEngine:
    engine = getattr(get_container(), "risk_engine", None)
    if engine is not None:
        return engine  # type: ignore[no-any-return]
    return RiskEngine(config=RiskEngineConfig())


def get_strategy_runtime() -> StrategyRuntimeService:
    runtime = getattr(get_container(), "strategy_runtime", None)
    if runtime is not None:
        return runtime  # type: ignore[no-any-return]
    return StrategyRuntimeService(
        market_data=get_market_data(),
        portfolio_sync=get_portfolio_sync(),
        risk_engine=get_risk_engine(),
        config=StrategyRuntimeConfig(),
    )


def get_evaluate_strategy() -> EvaluateStrategyUseCase:
    broker_uow = getattr(get_container(), "broker_uow_factory", None)
    if broker_uow is None:
        msg = "Broker Unit of Work factory is not available for audit"
        raise RuntimeError(msg)
    return EvaluateStrategyUseCase(
        strategy_uow_factory=get_strategy_uow_factory(),
        mt5_uow_factory=get_mt5_uow_factory(),
        runtime=get_strategy_runtime(),
        portfolio_sync=get_portfolio_sync(),
        audit=RecordAuditEventUseCase(uow_factory=broker_uow),
    )


def get_list_strategy_signals() -> ListStrategySignalsUseCase:
    return ListStrategySignalsUseCase(
        strategy_uow_factory=get_strategy_uow_factory(),
    )


EvaluateStrategyDep = Annotated[EvaluateStrategyUseCase, Depends(get_evaluate_strategy)]
ListStrategySignalsDep = Annotated[
    ListStrategySignalsUseCase, Depends(get_list_strategy_signals)
]
