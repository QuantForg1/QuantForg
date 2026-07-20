"""Reliability platform façade — wire health, heartbeat, traces, incidents."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.domain.institutional_trading.reliability.chaos import ChaosHarness
from app.domain.institutional_trading.reliability.health import (
    ContinuousHealthMonitor,
    ProbeInputs,
)
from app.domain.institutional_trading.reliability.heartbeat import HeartbeatRegistry
from app.domain.institutional_trading.reliability.incidents import IncidentManager
from app.domain.institutional_trading.reliability.live_metrics import LiveMetricsRegistry
from app.domain.institutional_trading.reliability.models import (
    ComponentName,
    IncidentSeverity,
    TimelineEvent,
    TraceStage,
)
from app.domain.institutional_trading.reliability.notifications import NotificationBus
from app.domain.institutional_trading.reliability.recovery import RecoveryOrchestrator
from app.domain.institutional_trading.reliability.timeline import AuditTimeline
from app.domain.institutional_trading.reliability.tracing import TradeTraceStore


@dataclass
class ReliabilityPlatform:
    health: ContinuousHealthMonitor = field(default_factory=ContinuousHealthMonitor)
    heartbeats: HeartbeatRegistry = field(default_factory=HeartbeatRegistry)
    traces: TradeTraceStore = field(default_factory=TradeTraceStore)
    incidents: IncidentManager = field(default_factory=IncidentManager)
    recovery: RecoveryOrchestrator = field(default_factory=RecoveryOrchestrator)
    metrics: LiveMetricsRegistry = field(default_factory=LiveMetricsRegistry)
    notifications: NotificationBus = field(default_factory=NotificationBus)
    timeline: AuditTimeline = field(default_factory=AuditTimeline)
    chaos: ChaosHarness = field(default_factory=ChaosHarness)

    def tick(
        self,
        probes: ProbeInputs,
        *,
        now: datetime | None = None,
        required_heartbeats: tuple[ComponentName, ...] | None = None,
    ) -> dict[str, Any]:
        """Continuous monitoring tick — health + missing heartbeats → incidents."""
        moment = now or datetime.now(UTC)
        probed = self.chaos.apply_to_probes(probes)
        snap = self.health.observe(probed, now=moment)
        self.timeline.append(
            TimelineEvent(
                timestamp=moment,
                category="health",
                action="observe",
                detail=f"score={snap.health_score} degraded={snap.degraded}",
                severity="WARNING" if snap.degraded else "INFO",
            )
        )

        missing = self.heartbeats.missing(required_heartbeats, now=moment)
        for comp in missing:
            inc = self.incidents.open(
                severity=IncidentSeverity.ERROR,
                title=f"Heartbeat missing: {comp.value}",
                detail=f"No heartbeat within {self.heartbeats.timeout_seconds}s",
                source="heartbeat",
                now=moment,
            )
            self.notifications.notify(
                subject=inc.title,
                body=inc.detail,
                meta={"incident_id": str(inc.id), "component": comp.value},
            )
            self.timeline.append(
                TimelineEvent(
                    timestamp=moment,
                    category="incident",
                    action="heartbeat_missing",
                    detail=comp.value,
                    severity="ERROR",
                )
            )

        if not snap.gateway_available:
            self.incidents.open(
                severity=IncidentSeverity.CRITICAL,
                title="Gateway unavailable",
                detail="Gateway probe failed",
                source="health",
                now=moment,
            )
        if not snap.mt5_connected:
            self.incidents.open(
                severity=IncidentSeverity.CRITICAL,
                title="MT5 disconnected",
                detail="MT5 probe failed",
                source="health",
                now=moment,
            )

        escalated = self.incidents.apply_escalation(now=moment)
        for inc in escalated:
            self.notifications.notify(
                subject=f"Escalation L{inc.escalation_level}: {inc.title}",
                body=inc.detail,
                meta={"incident_id": str(inc.id)},
            )

        return {
            "health": snap.to_dict(),
            "missing_heartbeats": [c.value for c in missing],
            "open_incidents": self.incidents.open_count(),
            "metrics": self.metrics.snapshot(),
        }

    def record_trade_path(
        self,
        *,
        decision_id: str | None = None,
        latencies: dict[TraceStage, float] | None = None,
        ok: bool = True,
    ) -> str:
        """Create a full Decision→…→Journal trace with one trace_id."""
        trace = self.traces.start(decision_id=decision_id)
        stages = (
            TraceStage.DECISION,
            TraceStage.ELIGIBILITY,
            TraceStage.BRIDGE,
            TraceStage.OMS,
            TraceStage.GATEWAY,
            TraceStage.MT5,
            TraceStage.PME,
            TraceStage.JOURNAL,
        )
        lat = latencies or {}
        for stage in stages:
            self.traces.span(
                trace.trace_id,
                stage,
                latency_ms=float(lat.get(stage, 1.0)),
                ok=ok,
            )
        self.timeline.append(
            TimelineEvent(
                timestamp=datetime.now(UTC),
                category="trace",
                action="trade_path",
                detail=f"trace={trace.trace_id}",
                severity="INFO",
                trace_id=trace.trace_id,
            )
        )
        self.metrics.record_decision()
        return trace.trace_id

    def operational_dashboard(self) -> dict[str, Any]:
        health = self.health.latest()
        series = self.health.series(limit=60)
        return {
            "health": health.to_dict() if health else None,
            "latency_series": [
                {
                    "t": s.checked_at.isoformat(),
                    "gateway": s.gateway_latency_ms,
                    "execution": s.execution_latency_ms,
                    "decision": s.decision_latency_ms,
                    "oms": s.oms_latency_ms,
                    "pme": s.pme_latency_ms,
                    "database": s.database_latency_ms,
                }
                for s in series
            ],
            "errors": {
                "open_incidents": self.incidents.open_count(),
                "oms_failures": self.metrics.snapshot()["oms_failures"],
            },
            "active_incidents": [
                i.to_dict()
                for i in self.incidents.list(limit=20)
                if i.status.value != "RESOLVED"
            ],
            "recovery_events": [e.to_dict() for e in self.recovery.list(limit=20)],
            "metrics": self.metrics.snapshot(),
            "chaos_active": list(self.chaos.active()),
            "heartbeats": self.heartbeats.snapshot(),
        }


_GLOBAL: ReliabilityPlatform | None = None


def get_reliability_platform() -> ReliabilityPlatform:
    global _GLOBAL
    if _GLOBAL is None:
        _GLOBAL = ReliabilityPlatform()
    return _GLOBAL


def reset_reliability_platform_for_tests() -> ReliabilityPlatform:
    global _GLOBAL
    _GLOBAL = ReliabilityPlatform()
    return _GLOBAL
