"""Execution safety + gateway FastAPI dependencies."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any

from fastapi import Depends

from app.application.services.execution_audit import ExecutionAuditService
from app.application.services.execution_gateway import ExecutionGateway
from app.application.services.execution_intelligence import ExecutionIntelligenceService
from app.application.services.execution_safety import ExecutionSafetyService
from app.application.services.institutional_execution_engine import (
    InstitutionalExecutionEngine,
)
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.application.use_cases.execution_gateway import (
    CancelExecutionUseCase,
    ManageExecutionUseCase,
    SubmitExecutionUseCase,
)
from app.application.use_cases.execution_safety import CheckExecutionSafetyUseCase
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.entities.execution_safety import ExecutionPolicy
from app.domain.execution_engine.journal import ExecutionJournalStore
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from app.infrastructure.persistence.memory_execution_audit import (
    MemoryExecutionAuditUnitOfWorkFactory,
)
from app.presentation.dependencies.execution_intelligence import (
    get_execution_intelligence,
)
from core.di.container import get_container


def get_mt5_adapter() -> MT5Adapter:
    adapter = getattr(get_container(), "mt5_adapter", None)
    if adapter is None:
        msg = "MT5 adapter is not available"
        raise RuntimeError(msg)
    return adapter  # type: ignore[no-any-return]


def get_mt5_uow_factory() -> Any:
    factory = getattr(get_container(), "mt5_uow_factory", None)
    if factory is None:
        msg = "MT5 Unit of Work factory is not available"
        raise RuntimeError(msg)
    return factory


def get_execution_uow_factory() -> Any:
    factory = getattr(get_container(), "execution_uow_factory", None)
    if factory is None:
        msg = "Execution Unit of Work factory is not available"
        raise RuntimeError(msg)
    return factory


def get_execution_audit_uow_factory() -> Any:
    factory = getattr(get_container(), "execution_audit_uow_factory", None)
    if factory is None:
        return MemoryExecutionAuditUnitOfWorkFactory()
    return factory


def get_execution_audit_service() -> ExecutionAuditService:
    return ExecutionAuditService(uow_factory=get_execution_audit_uow_factory())


def get_execution_safety_service() -> ExecutionSafetyService:
    service = getattr(get_container(), "execution_safety", None)
    if service is not None:
        return service  # type: ignore[no-any-return]
    adapter = get_mt5_adapter()
    order_validation = getattr(get_container(), "mt5_order_validation", None)
    if order_validation is None:
        order_validation = MT5OrderValidationService(adapter=adapter)
    return ExecutionSafetyService(
        adapter=adapter,
        order_validation=order_validation,
        policy=ExecutionPolicy(),
    )


def get_execution_gateway() -> ExecutionGateway:
    gateway = getattr(get_container(), "execution_gateway", None)
    if gateway is not None:
        return gateway  # type: ignore[no-any-return]
    adapter = get_mt5_adapter()
    order_validation = getattr(get_container(), "mt5_order_validation", None)
    if order_validation is None:
        order_validation = MT5OrderValidationService(adapter=adapter)
    return ExecutionGateway(adapter=adapter, order_validation=order_validation)


@lru_cache(maxsize=1)
def get_execution_journal() -> ExecutionJournalStore:
    return ExecutionJournalStore()


def get_institutional_execution_engine() -> InstitutionalExecutionEngine:
    adapter = get_mt5_adapter()
    order_validation = getattr(get_container(), "mt5_order_validation", None)
    if order_validation is None:
        order_validation = MT5OrderValidationService(adapter=adapter)
    intelligence: ExecutionIntelligenceService = get_execution_intelligence()
    return InstitutionalExecutionEngine(
        gateway=get_execution_gateway(),
        safety=get_execution_safety_service(),
        order_validation=order_validation,
        intelligence=intelligence,
        journal=get_execution_journal(),
    )


def get_check_execution_safety() -> CheckExecutionSafetyUseCase:
    broker_uow = getattr(get_container(), "broker_uow_factory", None)
    if broker_uow is None:
        msg = "Broker Unit of Work factory is not available for audit"
        raise RuntimeError(msg)
    return CheckExecutionSafetyUseCase(
        mt5_uow_factory=get_mt5_uow_factory(),
        execution_uow_factory=get_execution_uow_factory(),
        safety_service=get_execution_safety_service(),
        audit=RecordAuditEventUseCase(uow_factory=broker_uow),
        execution_audit=get_execution_audit_service(),
    )


def get_submit_execution() -> SubmitExecutionUseCase:
    broker_uow = getattr(get_container(), "broker_uow_factory", None)
    if broker_uow is None:
        msg = "Broker Unit of Work factory is not available for audit"
        raise RuntimeError(msg)
    return SubmitExecutionUseCase(
        mt5_uow_factory=get_mt5_uow_factory(),
        execution_uow_factory=get_execution_uow_factory(),
        engine=get_institutional_execution_engine(),
        audit=RecordAuditEventUseCase(uow_factory=broker_uow),
        execution_audit=get_execution_audit_service(),
    )


def get_cancel_execution() -> CancelExecutionUseCase:
    broker_uow = getattr(get_container(), "broker_uow_factory", None)
    if broker_uow is None:
        msg = "Broker Unit of Work factory is not available for audit"
        raise RuntimeError(msg)
    return CancelExecutionUseCase(
        mt5_uow_factory=get_mt5_uow_factory(),
        execution_uow_factory=get_execution_uow_factory(),
        engine=get_institutional_execution_engine(),
        audit=RecordAuditEventUseCase(uow_factory=broker_uow),
        execution_audit=get_execution_audit_service(),
    )


def get_manage_execution() -> ManageExecutionUseCase:
    return ManageExecutionUseCase(
        mt5_uow_factory=get_mt5_uow_factory(),
        execution_uow_factory=get_execution_uow_factory(),
        engine=get_institutional_execution_engine(),
        audit=get_submit_execution().audit,
        submit=get_submit_execution(),
        cancel=get_cancel_execution(),
    )


CheckExecutionDep = Annotated[
    CheckExecutionSafetyUseCase, Depends(get_check_execution_safety)
]
SubmitExecutionDep = Annotated[SubmitExecutionUseCase, Depends(get_submit_execution)]
CancelExecutionDep = Annotated[CancelExecutionUseCase, Depends(get_cancel_execution)]
ManageExecutionDep = Annotated[ManageExecutionUseCase, Depends(get_manage_execution)]
EngineDep = Annotated[
    InstitutionalExecutionEngine, Depends(get_institutional_execution_engine)
]
JournalDep = Annotated[ExecutionJournalStore, Depends(get_execution_journal)]
ExecutionAuditDep = Annotated[
    ExecutionAuditService, Depends(get_execution_audit_service)
]
