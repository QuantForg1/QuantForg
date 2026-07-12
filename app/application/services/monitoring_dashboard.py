"""Monitoring dashboard — aggregates component health (operational only)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.application.services.metrics_collector import MetricsCollector
from app.domain.entities.ops import ComponentHealth, MonitoringDashboard
from app.domain.enums.ops import ComponentHealthStatus, ComponentKind
from core.config.settings import Settings


@dataclass(frozen=True, slots=True)
class MonitoringDashboardService:
    """Build a MonitoringDashboard from live operational signals."""

    settings: Settings
    metrics: MetricsCollector
    health_service: Any | None = None
    broker_health_monitor: Any | None = None
    mt5_adapter: Any | None = None

    async def collect(self) -> MonitoringDashboard:
        components: list[ComponentHealth] = [
            ComponentHealth(
                kind=ComponentKind.SYSTEM,
                status=ComponentHealthStatus.HEALTHY,
                detail="process alive",
            ),
            await self._database_health(),
            self._broker_health(),
            self._mt5_health(),
            self._api_health(),
            ComponentHealth(
                kind=ComponentKind.QUEUE,
                status=ComponentHealthStatus.HEALTHY,
                detail="no dedicated job queue configured",
            ),
            ComponentHealth(
                kind=ComponentKind.BACKGROUND_JOBS,
                status=ComponentHealthStatus.HEALTHY,
                detail="no background workers configured",
            ),
        ]
        overall = self._aggregate(components)
        return MonitoringDashboard(
            overall=overall,
            components=tuple(components),
            collected_at=datetime.now(UTC),
            execution_enabled=bool(self.settings.execution_enabled),
        )

    async def _database_health(self) -> ComponentHealth:
        if self.health_service is None:
            return ComponentHealth(
                kind=ComponentKind.DATABASE,
                status=ComponentHealthStatus.UNKNOWN,
                detail="health service unavailable",
            )
        report = await self.health_service.check()
        postgres = next(
            (d for d in report.dependencies if d.name == "postgres"),
            None,
        )
        if postgres is None:
            return ComponentHealth(
                kind=ComponentKind.DATABASE,
                status=ComponentHealthStatus.UNKNOWN,
                detail="postgres probe missing",
            )
        status = (
            ComponentHealthStatus.HEALTHY
            if postgres.status.value == "healthy"
            else ComponentHealthStatus.UNHEALTHY
        )
        return ComponentHealth(
            kind=ComponentKind.DATABASE,
            status=status,
            detail=f"postgres {postgres.status.value}",
            latency_ms=postgres.latency_ms,
        )

    def _broker_health(self) -> ComponentHealth:
        monitor = self.broker_health_monitor
        if monitor is None:
            return ComponentHealth(
                kind=ComponentKind.BROKER,
                status=ComponentHealthStatus.UNKNOWN,
                detail="broker health monitor unavailable",
            )
        records = list(getattr(monitor, "_by_connection", {}).values())
        if not records:
            return ComponentHealth(
                kind=ComponentKind.BROKER,
                status=ComponentHealthStatus.HEALTHY,
                detail="no active broker connections",
            )
        statuses = [getattr(r, "status", None) for r in records]
        values = [s.value if s is not None else "unknown" for s in statuses]
        if any(v == "unhealthy" for v in values):
            return ComponentHealth(
                kind=ComponentKind.BROKER,
                status=ComponentHealthStatus.UNHEALTHY,
                detail="one or more broker connections unhealthy",
            )
        if any(v == "degraded" for v in values):
            return ComponentHealth(
                kind=ComponentKind.BROKER,
                status=ComponentHealthStatus.DEGRADED,
                detail="one or more broker connections degraded",
            )
        return ComponentHealth(
            kind=ComponentKind.BROKER,
            status=ComponentHealthStatus.HEALTHY,
            detail=f"{len(records)} connection(s) monitored",
        )

    def _mt5_health(self) -> ComponentHealth:
        adapter = self.mt5_adapter
        if adapter is None:
            return ComponentHealth(
                kind=ComponentKind.MT5,
                status=ComponentHealthStatus.UNKNOWN,
                detail="mt5 adapter unavailable",
            )
        client = getattr(adapter, "client", None)
        connected = False
        if client is not None and hasattr(client, "is_connected"):
            flag = client.is_connected
            connected = bool(flag() if callable(flag) else flag)
        if connected:
            return ComponentHealth(
                kind=ComponentKind.MT5,
                status=ComponentHealthStatus.HEALTHY,
                detail="mt5 client connected",
            )
        return ComponentHealth(
            kind=ComponentKind.MT5,
            status=ComponentHealthStatus.UNHEALTHY,
            detail="mt5 disconnected",
        )

    def _api_health(self) -> ComponentHealth:
        snap = self.metrics.snapshot()
        if snap.error_rate >= 0.25 and snap.request_count >= 20:
            return ComponentHealth(
                kind=ComponentKind.API,
                status=ComponentHealthStatus.UNHEALTHY,
                detail=f"error_rate={snap.error_rate:.3f}",
                latency_ms=snap.avg_latency_ms,
            )
        if snap.avg_latency_ms >= 2000.0 and snap.request_count >= 5:
            return ComponentHealth(
                kind=ComponentKind.API,
                status=ComponentHealthStatus.DEGRADED,
                detail=f"avg_latency_ms={snap.avg_latency_ms:.1f}",
                latency_ms=snap.avg_latency_ms,
            )
        return ComponentHealth(
            kind=ComponentKind.API,
            status=ComponentHealthStatus.HEALTHY,
            detail="api responding",
            latency_ms=snap.avg_latency_ms,
        )

    @staticmethod
    def _aggregate(
        components: list[ComponentHealth],
    ) -> ComponentHealthStatus:
        statuses = {c.status for c in components}
        if ComponentHealthStatus.UNHEALTHY in statuses:
            return ComponentHealthStatus.UNHEALTHY
        if ComponentHealthStatus.DEGRADED in statuses:
            return ComponentHealthStatus.DEGRADED
        if statuses == {ComponentHealthStatus.UNKNOWN}:
            return ComponentHealthStatus.UNKNOWN
        return ComponentHealthStatus.HEALTHY
