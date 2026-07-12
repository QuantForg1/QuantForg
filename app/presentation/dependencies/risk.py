"""Risk Management Engine FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends

from app.application.services.portfolio_sync import PortfolioSyncService
from app.application.services.risk_engine import RiskEngine
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.application.use_cases.risk_engine import CheckRiskUseCase
from app.domain.entities.risk_engine import RiskEngineConfig
from core.di.container import get_container


def get_mt5_uow_factory() -> Any:
    factory = getattr(get_container(), "mt5_uow_factory", None)
    if factory is None:
        msg = "MT5 Unit of Work factory is not available"
        raise RuntimeError(msg)
    return factory


def get_risk_uow_factory() -> Any:
    factory = getattr(get_container(), "risk_uow_factory", None)
    if factory is None:
        msg = "Risk Unit of Work factory is not available"
        raise RuntimeError(msg)
    return factory


def get_risk_engine() -> RiskEngine:
    engine = getattr(get_container(), "risk_engine", None)
    if engine is not None:
        return engine  # type: ignore[no-any-return]
    return RiskEngine(config=RiskEngineConfig())


def get_portfolio_sync() -> PortfolioSyncService | None:
    return getattr(get_container(), "portfolio_sync", None)


def get_check_risk() -> CheckRiskUseCase:
    broker_uow = getattr(get_container(), "broker_uow_factory", None)
    if broker_uow is None:
        msg = "Broker Unit of Work factory is not available for audit"
        raise RuntimeError(msg)
    return CheckRiskUseCase(
        risk_uow_factory=get_risk_uow_factory(),
        mt5_uow_factory=get_mt5_uow_factory(),
        risk_engine=get_risk_engine(),
        portfolio_sync=get_portfolio_sync(),
        audit=RecordAuditEventUseCase(uow_factory=broker_uow),
    )


CheckRiskDep = Annotated[CheckRiskUseCase, Depends(get_check_risk)]
