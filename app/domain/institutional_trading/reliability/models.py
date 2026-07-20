"""Phase G reliability contracts — incidents, traces, recovery, health."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class IncidentSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class IncidentStatus(StrEnum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    MITIGATING = "MITIGATING"
    RESOLVED = "RESOLVED"


class TraceStage(StrEnum):
    DECISION = "decision"
    ELIGIBILITY = "eligibility"
    BRIDGE = "bridge"
    OMS = "oms"
    GATEWAY = "gateway"
    MT5 = "mt5"
    PME = "pme"
    JOURNAL = "journal"


class RecoveryAction(StrEnum):
    GATEWAY_RECONNECT = "gateway_reconnect"
    MT5_RECONNECT = "mt5_reconnect"
    SAFE_READ_RETRY = "safe_read_retry"
    # Explicitly NOT supported: ORDER_SEND_RETRY


class ComponentName(StrEnum):
    GATEWAY = "gateway"
    MT5 = "mt5"
    CLOUDFLARE_TUNNEL = "cloudflare_tunnel"
    RAILWAY_API = "railway_api"
    SUPABASE = "supabase"
    DATABASE = "database"
    OMS = "oms"
    EXECUTION = "execution"
    DECISION = "decision"
    PME = "pme"
    RESEARCH = "research"
    BRIDGE = "bridge"


@dataclass(frozen=True, slots=True)
class Heartbeat:
    component: ComponentName
    at: datetime
    latency_ms: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component.value,
            "at": self.at.isoformat(),
            "latency_ms": self.latency_ms,
            "meta": dict(self.meta),
        }


@dataclass(frozen=True, slots=True)
class TraceSpan:
    stage: TraceStage
    started_at: datetime
    ended_at: datetime | None
    latency_ms: float
    ok: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "latency_ms": round(self.latency_ms, 3),
            "ok": self.ok,
            "detail": self.detail,
        }


@dataclass
class TradeTrace:
    """One trade lifecycle under a single trace_id."""

    trace_id: str
    created_at: datetime
    spans: list[TraceSpan] = field(default_factory=list)
    decision_id: str | None = None
    symbol: str = "XAUUSD"

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "created_at": self.created_at.isoformat(),
            "decision_id": self.decision_id,
            "symbol": self.symbol,
            "spans": [s.to_dict() for s in self.spans],
        }


@dataclass(frozen=True, slots=True)
class Incident:
    severity: IncidentSeverity
    title: str
    detail: str
    source: str
    created_at: datetime
    status: IncidentStatus = IncidentStatus.OPEN
    escalation_level: int = 0
    id: UUID = field(default_factory=uuid4)
    resolved_at: datetime | None = None
    acknowledged_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "severity": self.severity.value,
            "title": self.title,
            "detail": self.detail,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "status": self.status.value,
            "escalation_level": self.escalation_level,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "acknowledged_by": self.acknowledged_by,
        }


@dataclass(frozen=True, slots=True)
class RecoveryEvent:
    action: RecoveryAction
    success: bool
    detail: str
    at: datetime
    id: UUID = field(default_factory=uuid4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "action": self.action.value,
            "success": self.success,
            "detail": self.detail,
            "at": self.at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class ContinuousHealthSnapshot:
    gateway_latency_ms: float
    gateway_available: bool
    mt5_connected: bool
    cloudflare_tunnel_up: bool
    railway_api_up: bool
    supabase_up: bool
    database_latency_ms: float
    oms_latency_ms: float
    execution_latency_ms: float
    decision_latency_ms: float
    pme_latency_ms: float
    health_score: int
    checked_at: datetime
    degraded: bool = False
    chaos_active: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "gateway_latency_ms": self.gateway_latency_ms,
            "gateway_available": self.gateway_available,
            "mt5_connected": self.mt5_connected,
            "cloudflare_tunnel_up": self.cloudflare_tunnel_up,
            "railway_api_up": self.railway_api_up,
            "supabase_up": self.supabase_up,
            "database_latency_ms": self.database_latency_ms,
            "oms_latency_ms": self.oms_latency_ms,
            "execution_latency_ms": self.execution_latency_ms,
            "decision_latency_ms": self.decision_latency_ms,
            "pme_latency_ms": self.pme_latency_ms,
            "health_score": self.health_score,
            "checked_at": self.checked_at.isoformat(),
            "degraded": self.degraded,
            "chaos_active": list(self.chaos_active),
        }


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    timestamp: datetime
    category: str
    action: str
    detail: str
    severity: str = "INFO"
    trace_id: str | None = None
    id: UUID = field(default_factory=uuid4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "timestamp": self.timestamp.isoformat(),
            "category": self.category,
            "action": self.action,
            "detail": self.detail,
            "severity": self.severity,
            "trace_id": self.trace_id,
        }
