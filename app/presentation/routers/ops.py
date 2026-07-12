"""Operations & Observability API — monitoring, audit, alerts.

Never enables EXECUTION_ENABLED. Never calls order_send(). Never AI.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.presentation.dependencies.ops import (
    AuditCenterDep,
    MonitoringDashboardDep,
    OpsAlertsDep,
    OpsMetricsDep,
)
from app.presentation.schemas.ops import (
    AlertsResponse,
    AuditCenterResponse,
    MetricsResponse,
    MonitoringDashboardResponse,
)

router = APIRouter(prefix="/ops", tags=["operations"])


@router.get("/dashboard", response_model=MonitoringDashboardResponse)
async def monitoring_dashboard(
    uc: MonitoringDashboardDep,
) -> MonitoringDashboardResponse:
    """Monitoring dashboard: system, broker, MT5, API, DB, queue, jobs."""
    dto = await uc.execute()
    return MonitoringDashboardResponse(**dto.payload)


@router.get("/metrics", response_model=MetricsResponse)
async def ops_metrics(uc: OpsMetricsDep) -> MetricsResponse:
    """Collected operational metrics snapshot."""
    dto = await uc.execute()
    return MetricsResponse(**dto.payload)


@router.get("/alerts", response_model=AlertsResponse)
async def ops_alerts(
    uc: OpsAlertsDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> AlertsResponse:
    """Alert rules and recent alerts (info / warning / critical)."""
    dto = await uc.execute(limit=limit)
    return AlertsResponse(rules=dto.rules, alerts=dto.alerts)


@router.get("/audit", response_model=AuditCenterResponse)
async def audit_center(
    uc: AuditCenterDep,
    limit: int = Query(default=200, ge=1, le=1000),
) -> AuditCenterResponse:
    """Audit Center: auth, broker, strategy, risk, execution, paper events."""
    dto = await uc.execute(limit=limit)
    return AuditCenterResponse(**dto.payload)
