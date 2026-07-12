"""Operations & Observability FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.application.services.alerting_service import AlertingService
from app.application.services.audit_center import AuditCenterService
from app.application.services.metrics_collector import MetricsCollector
from app.application.services.monitoring_dashboard import MonitoringDashboardService
from app.application.use_cases.ops import (
    GetAuditCenterUseCase,
    GetMonitoringDashboardUseCase,
    GetOpsMetricsUseCase,
    ListOpsAlertsUseCase,
)
from app.domain.interfaces.ops_uow import OpsUnitOfWorkFactory
from app.presentation.dependencies.services import get_health_service
from core.di.container import get_container


def get_ops_uow_factory() -> OpsUnitOfWorkFactory:
    factory = getattr(get_container(), "ops_uow_factory", None)
    if factory is None:
        msg = "Ops Unit of Work factory is not available"
        raise RuntimeError(msg)
    return factory  # type: ignore[no-any-return]


def get_metrics_collector() -> MetricsCollector:
    collector = getattr(get_container(), "metrics_collector", None)
    if collector is None:
        msg = "Metrics collector is not available"
        raise RuntimeError(msg)
    return collector  # type: ignore[no-any-return]


def get_monitoring_dashboard() -> MonitoringDashboardService:
    container = get_container()
    return MonitoringDashboardService(
        settings=container.settings,
        metrics=get_metrics_collector(),
        health_service=get_health_service(),
        broker_health_monitor=getattr(container, "broker_health_monitor", None),
        mt5_adapter=getattr(container, "mt5_adapter", None),
    )


def get_alerting_service() -> AlertingService:
    return AlertingService(
        uow_factory=get_ops_uow_factory(),
        metrics=get_metrics_collector(),
    )


def get_audit_center() -> AuditCenterService:
    factory = getattr(get_container(), "platform_uow_factory", None)
    if factory is None:
        msg = "Platform Unit of Work factory is not available"
        raise RuntimeError(msg)
    return AuditCenterService(platform_uow_factory=factory)


def get_monitoring_dashboard_uc() -> GetMonitoringDashboardUseCase:
    return GetMonitoringDashboardUseCase(
        monitoring=get_monitoring_dashboard(),
        alerting=get_alerting_service(),
        ops_uow_factory=get_ops_uow_factory(),
    )


def get_ops_metrics_uc() -> GetOpsMetricsUseCase:
    return GetOpsMetricsUseCase(
        metrics=get_metrics_collector(),
        ops_uow_factory=get_ops_uow_factory(),
    )


def get_ops_alerts_uc() -> ListOpsAlertsUseCase:
    return ListOpsAlertsUseCase(alerting=get_alerting_service())


def get_audit_center_uc() -> GetAuditCenterUseCase:
    return GetAuditCenterUseCase(audit_center=get_audit_center())


MonitoringDashboardDep = Annotated[
    GetMonitoringDashboardUseCase, Depends(get_monitoring_dashboard_uc)
]
OpsMetricsDep = Annotated[GetOpsMetricsUseCase, Depends(get_ops_metrics_uc)]
OpsAlertsDep = Annotated[ListOpsAlertsUseCase, Depends(get_ops_alerts_uc)]
AuditCenterDep = Annotated[GetAuditCenterUseCase, Depends(get_audit_center_uc)]
MetricsCollectorDep = Annotated[MetricsCollector, Depends(get_metrics_collector)]
