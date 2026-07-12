"""Alerting service — warning / critical / info rules (operational only)."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.services.metrics_collector import MetricsCollector
from app.domain.entities.ops import AlertRule, MonitoringDashboard, SystemAlert
from app.domain.enums.ops import AlertSeverity, ComponentHealthStatus, ComponentKind
from app.domain.events.ops import AlertTriggered
from app.domain.interfaces.ops_uow import OpsUnitOfWorkFactory

DEFAULT_ALERT_RULES: tuple[AlertRule, ...] = (
    AlertRule(
        code="mt5_disconnected",
        name="MT5 disconnected",
        severity=AlertSeverity.CRITICAL,
        component=ComponentKind.MT5,
        description="MetaTrader 5 client is not connected.",
    ),
    AlertRule(
        code="broker_unhealthy",
        name="Broker unhealthy",
        severity=AlertSeverity.CRITICAL,
        component=ComponentKind.BROKER,
        description="One or more broker connections report unhealthy.",
    ),
    AlertRule(
        code="risk_engine_failures",
        name="Risk engine failures",
        severity=AlertSeverity.CRITICAL,
        component=ComponentKind.SYSTEM,
        description="Risk engine reported operational failures.",
    ),
    AlertRule(
        code="strategy_failures",
        name="Strategy failures",
        severity=AlertSeverity.WARNING,
        component=ComponentKind.SYSTEM,
        description="Strategy runtime reported failures.",
    ),
    AlertRule(
        code="migration_failures",
        name="Migration failures",
        severity=AlertSeverity.CRITICAL,
        component=ComponentKind.DATABASE,
        description="Database migration pipeline reported failures.",
    ),
)


@dataclass
class AlertingService:
    """Evaluate alert rules against monitoring state and persist open alerts."""

    uow_factory: OpsUnitOfWorkFactory
    metrics: MetricsCollector
    rules: tuple[AlertRule, ...] = field(default_factory=lambda: DEFAULT_ALERT_RULES)

    def list_rules(self) -> list[dict[str, object]]:
        return [r.to_dict() for r in self.rules]

    def _triggered(
        self, rule: AlertRule, dashboard: MonitoringDashboard
    ) -> tuple[bool, str]:
        by_kind = {c.kind: c for c in dashboard.components}
        if rule.code == "mt5_disconnected":
            mt5 = by_kind.get(ComponentKind.MT5)
            if mt5 is not None and mt5.status is ComponentHealthStatus.UNHEALTHY:
                return True, mt5.detail or "MT5 disconnected"
            return False, ""
        if rule.code == "broker_unhealthy":
            broker = by_kind.get(ComponentKind.BROKER)
            if broker is not None and broker.status is ComponentHealthStatus.UNHEALTHY:
                return True, broker.detail or "broker unhealthy"
            return False, ""
        if rule.code == "risk_engine_failures":
            if self.metrics.failure_active("risk_engine_failures"):
                return True, "risk engine failure signal active"
            return False, ""
        if rule.code == "strategy_failures":
            if self.metrics.failure_active("strategy_failures"):
                return True, "strategy failure signal active"
            return False, ""
        if rule.code == "migration_failures":
            if self.metrics.failure_active("migration_failures"):
                return True, "migration failure signal active"
            return False, ""
        return False, ""

    async def evaluate(self, dashboard: MonitoringDashboard) -> list[SystemAlert]:
        created: list[SystemAlert] = []
        events: list[AlertTriggered] = []
        async with self.uow_factory() as uow:
            for rule in self.rules:
                active, message = self._triggered(rule, dashboard)
                if not active:
                    continue
                existing = await uow.alerts.find_open_by_code(rule.code)
                if existing is not None:
                    continue
                alert = SystemAlert.open_alert(
                    code=rule.code,
                    name=rule.name,
                    severity=rule.severity,
                    component=rule.component,
                    message=message or rule.description,
                    details={"rule": rule.to_dict()},
                )
                await uow.alerts.add(alert)
                created.append(alert)
                events.append(
                    AlertTriggered(
                        alert_id=alert.id,
                        code=alert.code,
                        severity=alert.severity.value,
                        component=alert.component.value,
                    )
                )
            await uow.commit()
        _ = events
        return created

    async def list_alerts(self, *, limit: int = 100) -> list[SystemAlert]:
        async with self.uow_factory() as uow:
            return await uow.alerts.list_recent(limit=limit)
