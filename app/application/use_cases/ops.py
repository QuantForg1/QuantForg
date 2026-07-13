"""Operations & Observability use cases — operational only."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dto.ops import (
    OpsAlertsDTO,
    OpsAuditCenterDTO,
    OpsDashboardDTO,
    OpsMetricsDTO,
)
from app.application.services.alerting_service import AlertingService
from app.application.services.audit_center import AuditCenterService
from app.application.services.metrics_collector import MetricsCollector
from app.application.services.monitoring_dashboard import MonitoringDashboardService
from app.domain.entities.ops import HealthHistoryEntry, SystemMetricRecord
from app.domain.events.ops import HealthSnapshotRecorded
from app.domain.interfaces.ops_uow import OpsUnitOfWorkFactory
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GetMonitoringDashboardUseCase:
    monitoring: MonitoringDashboardService
    alerting: AlertingService
    ops_uow_factory: OpsUnitOfWorkFactory
    persist_history: bool = True

    async def execute(self) -> OpsDashboardDTO:
        dashboard = await self.monitoring.collect()
        await self.alerting.evaluate(dashboard)
        if self.persist_history:
            try:
                async with self.ops_uow_factory() as uow:
                    await uow.health_history.add(
                        HealthHistoryEntry(
                            overall=dashboard.overall,
                            payload=dashboard.to_dict(),
                        )
                    )
                    await uow.commit()
                _ = HealthSnapshotRecorded(overall=dashboard.overall.value)
            except Exception as exc:
                logger.warning(
                    "ops_dashboard_persist_failed",
                    error=str(exc),
                )
        return OpsDashboardDTO(payload=dashboard.to_dict())


@dataclass(frozen=True, slots=True)
class GetOpsMetricsUseCase:
    metrics: MetricsCollector
    ops_uow_factory: OpsUnitOfWorkFactory

    async def execute(self, *, persist: bool = True) -> OpsMetricsDTO:
        snap = self.metrics.snapshot()
        payload = snap.to_dict()
        if persist:
            try:
                async with self.ops_uow_factory() as uow:
                    await uow.metrics.add(SystemMetricRecord(payload=payload))
                    await uow.commit()
            except Exception as exc:
                logger.warning("ops_metrics_persist_failed", error=str(exc))
        return OpsMetricsDTO(payload=payload)


@dataclass(frozen=True, slots=True)
class ListOpsAlertsUseCase:
    alerting: AlertingService

    async def execute(self, *, limit: int = 100) -> OpsAlertsDTO:
        alerts = await self.alerting.list_alerts(limit=limit)
        return OpsAlertsDTO(
            rules=self.alerting.list_rules(),
            alerts=[a.to_dict() for a in alerts],
        )


@dataclass(frozen=True, slots=True)
class GetAuditCenterUseCase:
    audit_center: AuditCenterService

    async def execute(self, *, limit: int = 200) -> OpsAuditCenterDTO:
        payload = await self.audit_center.collect(limit=limit)
        return OpsAuditCenterDTO(payload=payload)
