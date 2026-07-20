"""Phase F operations contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class OpsExecutionMode(StrEnum):
    """Operator-facing modes (map CANARY → Phase C CANARY_LIVE at the edge)."""

    SHADOW = "SHADOW"
    CANARY = "CANARY"
    LIVE = "LIVE"


# Exact allowed transitions per Phase F spec
ALLOWED_MODE_TRANSITIONS: dict[OpsExecutionMode, frozenset[OpsExecutionMode]] = {
    OpsExecutionMode.SHADOW: frozenset({OpsExecutionMode.CANARY}),
    OpsExecutionMode.CANARY: frozenset({OpsExecutionMode.LIVE}),
    OpsExecutionMode.LIVE: frozenset({OpsExecutionMode.SHADOW}),
}


class OpsPermission(StrEnum):
    ENABLE_LIVE = "enable_live"
    DISABLE_KILL_SWITCH = "disable_kill_switch"
    PROMOTE_STRATEGY = "promote_strategy"
    ROLLBACK = "rollback"
    CHANGE_RISK_CONFIG = "change_risk_config"
    CHANGE_MODE = "change_mode"
    ACK_ALERT = "ack_alert"
    RUN_RUNBOOK = "run_runbook"
    VIEW = "view"


# OWNER / ADMIN roles (existing enum values)
OPERATOR_ROLES = frozenset({"owner", "admin"})

PERMISSIONS_BY_ROLE: dict[str, frozenset[OpsPermission]] = {
    "owner": frozenset(OpsPermission),
    "admin": frozenset(OpsPermission),
}


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertKind(StrEnum):
    GATEWAY_OFFLINE = "gateway_offline"
    MT5_DISCONNECTED = "mt5_disconnected"
    EXECUTION_FAILURES = "execution_failures"
    MT5_REJECTIONS = "mt5_rejections"
    HIGH_LATENCY = "high_latency"
    KILL_SWITCH = "kill_switch_activated"
    DAILY_LOSS = "daily_loss_exceeded"
    CANARY_FAILURE = "canary_failure"


@dataclass(frozen=True, slots=True)
class OperatorIdentity:
    user_id: UUID
    role: str
    display_name: str = ""
    ip: str | None = None
    user_agent: str | None = None

    def has(self, permission: OpsPermission) -> bool:
        if self.role not in OPERATOR_ROLES:
            return False
        allowed = PERMISSIONS_BY_ROLE.get(self.role, frozenset())
        return permission in allowed


@dataclass(frozen=True, slots=True)
class AuditEntry:
    timestamp: datetime
    operator: str
    operator_id: str
    action: str
    old_value: str
    new_value: str
    reason: str
    ip: str | None = None
    user_agent: str | None = None
    id: UUID = field(default_factory=uuid4)
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "schema_version": self.schema_version,
            "timestamp": self.timestamp.isoformat(),
            "operator": self.operator,
            "operator_id": self.operator_id,
            "action": self.action,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "reason": self.reason,
            "ip": self.ip,
            "user_agent": self.user_agent,
        }


@dataclass(frozen=True, slots=True)
class ConfigVersionRecord:
    """Append-only promoted configuration — never overwritten."""

    config_version: str
    strategy_version: str
    promoted_at: datetime
    operator: str
    reason: str
    rollback_target: str | None
    risk_per_trade_pct: Decimal
    max_daily_loss_pct: Decimal
    max_open_trades: int
    execution_mode: OpsExecutionMode
    payload: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "config_version": self.config_version,
            "strategy_version": self.strategy_version,
            "promoted_at": self.promoted_at.isoformat(),
            "operator": self.operator,
            "reason": self.reason,
            "rollback_target": self.rollback_target,
            "risk_per_trade_pct": str(self.risk_per_trade_pct),
            "max_daily_loss_pct": str(self.max_daily_loss_pct),
            "max_open_trades": self.max_open_trades,
            "execution_mode": self.execution_mode.value,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True, slots=True)
class OpsAlert:
    kind: AlertKind
    severity: AlertSeverity
    message: str
    created_at: datetime
    acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "kind": self.kind.value,
            "severity": self.severity.value,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
            "acknowledged": self.acknowledged,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": (
                self.acknowledged_at.isoformat() if self.acknowledged_at else None
            ),
        }


@dataclass(frozen=True, slots=True)
class HealthSnapshot:
    gateway_latency_ms: float
    gateway_available: bool
    mt5_connected: bool
    cloudflare_tunnel_up: bool
    order_latency_ms: float
    journal_latency_ms: float
    research_queue_depth: int
    simulation_queue_depth: int
    oms_queue_depth: int
    decision_throughput_per_min: float
    health_score: int  # 0–100
    checked_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "gateway_latency_ms": self.gateway_latency_ms,
            "gateway_available": self.gateway_available,
            "mt5_connected": self.mt5_connected,
            "cloudflare_tunnel_up": self.cloudflare_tunnel_up,
            "order_latency_ms": self.order_latency_ms,
            "journal_latency_ms": self.journal_latency_ms,
            "research_queue_depth": self.research_queue_depth,
            "simulation_queue_depth": self.simulation_queue_depth,
            "oms_queue_depth": self.oms_queue_depth,
            "decision_throughput_per_min": self.decision_throughput_per_min,
            "health_score": self.health_score,
            "checked_at": self.checked_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class ModeTransitionResult:
    ok: bool
    from_mode: OpsExecutionMode
    to_mode: OpsExecutionMode
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "from_mode": self.from_mode.value,
            "to_mode": self.to_mode.value,
            "message": self.message,
        }
