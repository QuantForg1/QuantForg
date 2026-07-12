"""Unit tests for Operations & Observability Platform.

Never enables EXECUTION_ENABLED. Never calls order_send(). Never AI.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.dto.health import DependencyStatus, HealthReport, HealthStatus
from app.application.services.alerting_service import AlertingService
from app.application.services.audit_center import (
    AuditCenterService,
    categorize_audit_event,
)
from app.application.services.metrics_collector import MetricsCollector
from app.application.services.monitoring_dashboard import MonitoringDashboardService
from app.application.use_cases.ops import (
    GetAuditCenterUseCase,
    GetMonitoringDashboardUseCase,
    GetOpsMetricsUseCase,
    ListOpsAlertsUseCase,
)
from app.domain.entities.audit_log import AuditLog
from app.domain.entities.ops import SystemAlert
from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.enums.ops import (
    AlertSeverity,
    AlertStatus,
    ComponentHealthStatus,
    ComponentKind,
)
from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter
from app.infrastructure.persistence.memory_ops import MemoryOpsUnitOfWorkFactory
from app.infrastructure.persistence.memory_platform import (
    MemoryPlatformUnitOfWorkFactory,
)
from core.config.settings import get_settings


class _FakeHealthService:
    async def check(self) -> HealthReport:
        return HealthReport(
            status=HealthStatus.HEALTHY,
            version="0.1.0",
            environment="testing",
            dependencies=[
                DependencyStatus(
                    name="postgres",
                    status=HealthStatus.HEALTHY,
                    latency_ms=1.0,
                ),
                DependencyStatus(
                    name="redis",
                    status=HealthStatus.HEALTHY,
                    latency_ms=0.5,
                ),
            ],
        )


@pytest.mark.unit
class TestMetricsCollector:
    def test_records_latency_errors_cache_jobs(self) -> None:
        m = MetricsCollector()
        m.record_request(latency_ms=10.0, success=True)
        m.record_request(latency_ms=20.0, success=False)
        m.record_cache(hit=True)
        m.record_cache(hit=False)
        m.record_job(name="cleanup", duration_ms=50.0)
        snap = m.snapshot()
        assert snap.request_count == 2
        assert snap.error_count == 1
        assert snap.error_rate == 0.5
        assert snap.avg_latency_ms == 15.0
        assert snap.cache_hit_ratio == 0.5
        assert snap.job_count == 1
        assert snap.avg_job_duration_ms == 50.0
        assert snap.throughput_per_minute > 0


@pytest.mark.unit
class TestMonitoringAndAlerts:
    @pytest.mark.asyncio
    async def test_dashboard_and_mt5_disconnected_alert(self) -> None:
        settings = get_settings()
        assert settings.execution_enabled is False
        metrics = MetricsCollector()
        ops_uow = MemoryOpsUnitOfWorkFactory()
        adapter = MT5Adapter(client=MockMT5Client(), execution_enabled=False)
        monitoring = MonitoringDashboardService(
            settings=settings,
            metrics=metrics,
            health_service=_FakeHealthService(),
            broker_health_monitor=None,
            mt5_adapter=adapter,
        )
        alerting = AlertingService(uow_factory=ops_uow, metrics=metrics)
        dashboard = await monitoring.collect()
        assert dashboard.execution_enabled is False
        kinds = {c.kind for c in dashboard.components}
        assert ComponentKind.SYSTEM in kinds
        assert ComponentKind.MT5 in kinds
        assert ComponentKind.DATABASE in kinds
        assert ComponentKind.QUEUE in kinds
        assert ComponentKind.BACKGROUND_JOBS in kinds
        mt5 = next(c for c in dashboard.components if c.kind is ComponentKind.MT5)
        assert mt5.status is ComponentHealthStatus.UNHEALTHY

        created = await alerting.evaluate(dashboard)
        assert any(a.code == "mt5_disconnected" for a in created)
        assert any(a.severity is AlertSeverity.CRITICAL for a in created)

        # Idempotent — open alert not duplicated
        again = await alerting.evaluate(dashboard)
        assert again == []

    @pytest.mark.asyncio
    async def test_failure_signal_rules(self) -> None:
        settings = get_settings()
        metrics = MetricsCollector()
        metrics.set_failure("risk_engine_failures")
        metrics.set_failure("strategy_failures")
        metrics.set_failure("migration_failures")
        ops_uow = MemoryOpsUnitOfWorkFactory()
        adapter = MT5Adapter(client=MockMT5Client(), execution_enabled=False)
        # Connect mock so MT5 does not also fire
        client = adapter.client
        assert client.initialize()
        from app.domain.interfaces.mt5_client import MT5LoginRequest

        assert client.login(MT5LoginRequest(login=1, password="x", server="Mock-Demo"))
        monitoring = MonitoringDashboardService(
            settings=settings,
            metrics=metrics,
            health_service=_FakeHealthService(),
            mt5_adapter=adapter,
        )
        alerting = AlertingService(uow_factory=ops_uow, metrics=metrics)
        dashboard = await monitoring.collect()
        created = await alerting.evaluate(dashboard)
        codes = {a.code for a in created}
        assert "risk_engine_failures" in codes
        assert "strategy_failures" in codes
        assert "migration_failures" in codes

    def test_alert_ack_resolve(self) -> None:
        alert = SystemAlert.open_alert(
            code="info_probe",
            name="Info",
            severity=AlertSeverity.INFO,
            component=ComponentKind.SYSTEM,
            message="hello",
        )
        assert alert.status is AlertStatus.OPEN
        alert.acknowledge()
        assert alert.status is AlertStatus.ACKNOWLEDGED
        alert.resolve()
        assert alert.status is AlertStatus.RESOLVED


@pytest.mark.unit
class TestAuditCenter:
    def test_categorize(self) -> None:
        assert (
            categorize_audit_event(action="login", resource_type="auth")
            == "authentication"
        )
        assert (
            categorize_audit_event(action="create", resource_type="broker_account")
            == "broker"
        )
        assert (
            categorize_audit_event(action="system", resource_type="strategy_evaluation")
            == "strategy"
        )
        assert (
            categorize_audit_event(action="system", resource_type="risk_assessment")
            == "risk"
        )
        assert (
            categorize_audit_event(action="system", resource_type="execution_decision")
            == "execution"
        )
        assert (
            categorize_audit_event(action="create", resource_type="paper_order")
            == "paper"
        )

    @pytest.mark.asyncio
    async def test_collect_buckets(self) -> None:
        platform = MemoryPlatformUnitOfWorkFactory()
        async with platform() as uow:
            await uow.audit_logs.add(
                AuditLog.record(
                    action=AuditAction.LOGIN,
                    outcome=AuditOutcome.SUCCESS,
                    resource_type="auth",
                    actor_user_id=uuid4(),
                    message="login ok",
                )
            )
            await uow.audit_logs.add(
                AuditLog.record(
                    action=AuditAction.SYSTEM,
                    outcome=AuditOutcome.SUCCESS,
                    resource_type="paper_order",
                    message="paper fill",
                )
            )
            await uow.commit()
        center = AuditCenterService(platform_uow_factory=platform)
        payload = await center.collect()
        assert payload["counts"]["authentication"] >= 1
        assert payload["counts"]["paper"] >= 1


@pytest.mark.unit
class TestOpsUseCases:
    @pytest.mark.asyncio
    async def test_metrics_and_dashboard_use_cases(self) -> None:
        settings = get_settings()
        assert settings.execution_enabled is False
        metrics = MetricsCollector()
        metrics.record_request(latency_ms=5.0, success=True)
        ops_uow = MemoryOpsUnitOfWorkFactory()
        adapter = MT5Adapter(client=MockMT5Client(), execution_enabled=False)
        monitoring = MonitoringDashboardService(
            settings=settings,
            metrics=metrics,
            health_service=_FakeHealthService(),
            mt5_adapter=adapter,
        )
        alerting = AlertingService(uow_factory=ops_uow, metrics=metrics)
        dash_uc = GetMonitoringDashboardUseCase(
            monitoring=monitoring,
            alerting=alerting,
            ops_uow_factory=ops_uow,
        )
        metrics_uc = GetOpsMetricsUseCase(metrics=metrics, ops_uow_factory=ops_uow)
        alerts_uc = ListOpsAlertsUseCase(alerting=alerting)

        dash = await dash_uc.execute()
        assert dash.payload["execution_enabled"] is False
        assert "overall" in dash.payload

        m = await metrics_uc.execute()
        assert m.payload["request_count"] >= 1

        m2 = await metrics_uc.execute(persist=False)
        assert "error_rate" in m2.payload

        alerts = await alerts_uc.execute()
        assert len(alerts.rules) >= 5
        assert any(r["code"] == "mt5_disconnected" for r in alerts.rules)

        platform = MemoryPlatformUnitOfWorkFactory()
        audit_uc = GetAuditCenterUseCase(
            audit_center=AuditCenterService(platform_uow_factory=platform)
        )
        audit = await audit_uc.execute()
        assert "authentication" in audit.payload["categories"]
