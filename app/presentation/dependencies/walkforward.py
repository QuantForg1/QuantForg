"""Walk-Forward Validation FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends

from app.application.services.backtest_engine import BacktestEngine
from app.application.services.rolling_windows import RollingWindowScheduler
from app.application.services.walkforward_engine import WalkForwardEngine
from app.application.services.walkforward_robustness import RobustnessEngine
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.application.use_cases.walkforward import (
    GetWalkForwardUseCase,
    ListWalkForwardUseCase,
    RunWalkForwardUseCase,
)
from core.di.container import get_container


def get_walkforward_uow_factory() -> Any:
    factory = getattr(get_container(), "walkforward_uow_factory", None)
    if factory is None:
        msg = "Walk-Forward Unit of Work factory is not available"
        raise RuntimeError(msg)
    return factory


def get_backtest_engine() -> BacktestEngine:
    engine = getattr(get_container(), "backtest_engine", None)
    if engine is None:
        msg = "Backtest engine is not available for walk-forward"
        raise RuntimeError(msg)
    return engine  # type: ignore[no-any-return]


def get_walkforward_engine() -> WalkForwardEngine:
    engine = getattr(get_container(), "walkforward_engine", None)
    if engine is not None:
        return engine  # type: ignore[no-any-return]
    return WalkForwardEngine(
        backtest_engine=get_backtest_engine(),
        window_scheduler=RollingWindowScheduler(),
        robustness_engine=RobustnessEngine(),
    )


def get_run_walkforward() -> RunWalkForwardUseCase:
    broker_uow = getattr(get_container(), "broker_uow_factory", None)
    if broker_uow is None:
        msg = "Broker Unit of Work factory is not available for audit"
        raise RuntimeError(msg)
    return RunWalkForwardUseCase(
        walkforward_uow_factory=get_walkforward_uow_factory(),
        engine=get_walkforward_engine(),
        audit=RecordAuditEventUseCase(uow_factory=broker_uow),
    )


def get_list_walkforward() -> ListWalkForwardUseCase:
    return ListWalkForwardUseCase(walkforward_uow_factory=get_walkforward_uow_factory())


def get_get_walkforward() -> GetWalkForwardUseCase:
    return GetWalkForwardUseCase(walkforward_uow_factory=get_walkforward_uow_factory())


RunWalkForwardDep = Annotated[RunWalkForwardUseCase, Depends(get_run_walkforward)]
ListWalkForwardDep = Annotated[ListWalkForwardUseCase, Depends(get_list_walkforward)]
GetWalkForwardDep = Annotated[GetWalkForwardUseCase, Depends(get_get_walkforward)]
