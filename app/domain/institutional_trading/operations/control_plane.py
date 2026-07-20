"""Operations Control Plane — single source of truth for operator controls."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from threading import RLock
from typing import Any
from uuid import UUID

from app.domain.institutional_trading.operations.alerts import AlertService
from app.domain.institutional_trading.operations.audit import AuditLog
from app.domain.institutional_trading.operations.config_store import ConfigVersionStore
from app.domain.institutional_trading.operations.health import HealthInputs, HealthMonitor
from app.domain.institutional_trading.operations.models import (
    ALLOWED_MODE_TRANSITIONS,
    AlertKind,
    AlertSeverity,
    ConfigVersionRecord,
    ModeTransitionResult,
    OperatorIdentity,
    OpsExecutionMode,
    OpsPermission,
)
from app.domain.institutional_trading.operations.runbooks import RunbookCatalog


class PermissionDenied(PermissionError):
    pass


@dataclass
class OperationsControlPlane:
    """Institutional ops brain — modes, kill switch, config, health, alerts, audit."""

    audit: AuditLog = field(default_factory=AuditLog)
    configs: ConfigVersionStore = field(default_factory=ConfigVersionStore)
    health: HealthMonitor = field(default_factory=HealthMonitor)
    alerts: AlertService = field(default_factory=AlertService)
    runbooks: RunbookCatalog = field(default_factory=RunbookCatalog)

    mode: OpsExecutionMode = OpsExecutionMode.SHADOW
    kill_switch_armed: bool = False
    strategy_version: str = "ite-v1.0.0"
    config_version: str = "ite-cfg-v1.0.0"
    promotion_status: str = "not_promoted"
    git_commit: str | None = None
    risk_per_trade_pct: Decimal = Decimal("1.0")
    max_daily_loss_pct: Decimal = Decimal("3.0")
    max_open_trades: int = 1
    daily_loss_exceeded: bool = False

    _lock: RLock = field(default_factory=RLock, repr=False)
    _initialized: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        if not self._initialized:
            self.git_commit = self.git_commit or _detect_git_commit()
            # Seed initial config version (append-only baseline)
            if self.configs.count() == 0:
                self.configs.promote(
                    config_version=self.config_version,
                    strategy_version=self.strategy_version,
                    operator="system",
                    reason="baseline bootstrap",
                    risk_per_trade_pct=self.risk_per_trade_pct,
                    max_daily_loss_pct=self.max_daily_loss_pct,
                    max_open_trades=self.max_open_trades,
                    execution_mode=self.mode,
                )
            self._initialized = True

    def require(self, operator: OperatorIdentity, permission: OpsPermission) -> None:
        if not operator.has(permission):
            raise PermissionDenied(
                f"role={operator.role} lacks permission {permission.value}"
            )

    # --- Kill switch -------------------------------------------------------

    def arm_kill_switch(
        self,
        operator: OperatorIdentity,
        *,
        reason: str,
        confirmed: bool = True,
        now: datetime | None = None,
    ) -> None:
        self.require(operator, OpsPermission.CHANGE_MODE)
        if not confirmed:
            raise ValueError("operator confirmation required")
        with self._lock:
            old = self.kill_switch_armed
            self.kill_switch_armed = True
        self.audit.record(
            operator=operator,
            action="kill_switch_arm",
            old_value=str(old),
            new_value="True",
            reason=reason,
            now=now,
        )
        self.alerts.raise_alert(
            kind=AlertKind.KILL_SWITCH,
            severity=AlertSeverity.CRITICAL,
            message=f"Kill switch ARMED by {operator.display_name or operator.user_id}: {reason}",
            now=now,
        )

    def disarm_kill_switch(
        self,
        operator: OperatorIdentity,
        *,
        reason: str,
        confirmed: bool = True,
        now: datetime | None = None,
    ) -> None:
        self.require(operator, OpsPermission.DISABLE_KILL_SWITCH)
        if not confirmed:
            raise ValueError("operator confirmation required")
        with self._lock:
            old = self.kill_switch_armed
            self.kill_switch_armed = False
        self.audit.record(
            operator=operator,
            action="kill_switch_disarm",
            old_value=str(old),
            new_value="False",
            reason=reason,
            now=now,
        )

    def oms_orders_allowed(self) -> bool:
        """Decision/research/sim continue; OMS receives zero when kill armed or SHADOW."""
        with self._lock:
            if self.kill_switch_armed:
                return False
            if self.mode is OpsExecutionMode.SHADOW:
                return False
            return True

    def pme_modifications_allowed(self) -> bool:
        with self._lock:
            return not self.kill_switch_armed

    # --- Mode transitions --------------------------------------------------

    def transition_mode(
        self,
        operator: OperatorIdentity,
        target: OpsExecutionMode,
        *,
        reason: str,
        confirmed: bool,
        now: datetime | None = None,
    ) -> ModeTransitionResult:
        self.require(operator, OpsPermission.CHANGE_MODE)
        if target is OpsExecutionMode.LIVE:
            self.require(operator, OpsPermission.ENABLE_LIVE)
        if not confirmed:
            return ModeTransitionResult(
                ok=False,
                from_mode=self.mode,
                to_mode=target,
                message="operator confirmation required",
            )
        with self._lock:
            current = self.mode
            allowed = ALLOWED_MODE_TRANSITIONS.get(current, frozenset())
            if target not in allowed:
                return ModeTransitionResult(
                    ok=False,
                    from_mode=current,
                    to_mode=target,
                    message=f"illegal transition {current.value} → {target.value}",
                )
            self.mode = target
        self.audit.record(
            operator=operator,
            action="mode_transition",
            old_value=current.value,
            new_value=target.value,
            reason=reason,
            now=now,
        )
        return ModeTransitionResult(
            ok=True,
            from_mode=current,
            to_mode=target,
            message=f"transitioned {current.value} → {target.value}",
        )

    # --- Config promote / rollback -----------------------------------------

    def promote_config(
        self,
        operator: OperatorIdentity,
        *,
        config_version: str,
        strategy_version: str,
        reason: str,
        risk_per_trade_pct: Decimal | None = None,
        max_daily_loss_pct: Decimal | None = None,
        max_open_trades: int | None = None,
        now: datetime | None = None,
    ) -> ConfigVersionRecord:
        self.require(operator, OpsPermission.PROMOTE_STRATEGY)
        with self._lock:
            if risk_per_trade_pct is not None:
                self.risk_per_trade_pct = risk_per_trade_pct
            if max_daily_loss_pct is not None:
                self.max_daily_loss_pct = max_daily_loss_pct
            if max_open_trades is not None:
                self.max_open_trades = max_open_trades
            self.config_version = config_version
            self.strategy_version = strategy_version
            self.promotion_status = "promoted"
            mode = self.mode
            risk = self.risk_per_trade_pct
            daily = self.max_daily_loss_pct
            opens = self.max_open_trades
        record = self.configs.promote(
            config_version=config_version,
            strategy_version=strategy_version,
            operator=operator.display_name or str(operator.user_id),
            reason=reason,
            risk_per_trade_pct=risk,
            max_daily_loss_pct=daily,
            max_open_trades=opens,
            execution_mode=mode,
            now=now,
        )
        self.audit.record(
            operator=operator,
            action="config_promote",
            old_value=record.rollback_target or "",
            new_value=config_version,
            reason=reason,
            now=now,
        )
        return record

    def rollback(
        self,
        operator: OperatorIdentity,
        *,
        target_config_version: str,
        reason: str,
        confirmed: bool = True,
        now: datetime | None = None,
    ) -> ConfigVersionRecord:
        self.require(operator, OpsPermission.ROLLBACK)
        if not confirmed:
            raise ValueError("operator confirmation required")
        record = self.configs.rollback_to(target_config_version)
        if record is None:
            raise ValueError(f"unknown config version {target_config_version}")
        with self._lock:
            old_cfg = self.config_version
            old_mode = self.mode
            self.config_version = record.config_version
            self.strategy_version = record.strategy_version
            self.risk_per_trade_pct = record.risk_per_trade_pct
            self.max_daily_loss_pct = record.max_daily_loss_pct
            self.max_open_trades = record.max_open_trades
            self.mode = record.execution_mode
            self.promotion_status = "rolled_back"
        self.audit.record(
            operator=operator,
            action="rollback",
            old_value=f"{old_cfg}|{old_mode.value}",
            new_value=f"{record.config_version}|{record.execution_mode.value}",
            reason=reason,
            now=now,
        )
        return record

    def update_risk(
        self,
        operator: OperatorIdentity,
        *,
        risk_per_trade_pct: Decimal,
        max_daily_loss_pct: Decimal,
        max_open_trades: int,
        reason: str,
        now: datetime | None = None,
    ) -> None:
        self.require(operator, OpsPermission.CHANGE_RISK_CONFIG)
        with self._lock:
            old = (
                f"{self.risk_per_trade_pct}|{self.max_daily_loss_pct}|"
                f"{self.max_open_trades}"
            )
            self.risk_per_trade_pct = risk_per_trade_pct
            self.max_daily_loss_pct = max_daily_loss_pct
            self.max_open_trades = max_open_trades
            new = (
                f"{self.risk_per_trade_pct}|{self.max_daily_loss_pct}|"
                f"{self.max_open_trades}"
            )
        self.audit.record(
            operator=operator,
            action="risk_config_change",
            old_value=old,
            new_value=new,
            reason=reason,
            now=now,
        )

    # --- Health / alerts ---------------------------------------------------

    def update_health(self, inputs: HealthInputs, *, now: datetime | None = None) -> None:
        snap = self.health.observe(inputs, now=now)
        if not snap.gateway_available:
            self.alerts.raise_alert(
                kind=AlertKind.GATEWAY_OFFLINE,
                severity=AlertSeverity.CRITICAL,
                message="Gateway offline",
                now=now,
            )
        if not snap.mt5_connected:
            self.alerts.raise_alert(
                kind=AlertKind.MT5_DISCONNECTED,
                severity=AlertSeverity.CRITICAL,
                message="MT5 disconnected",
                now=now,
            )
        if (
            snap.gateway_latency_ms > self.health.high_latency_ms
            or snap.order_latency_ms > self.health.high_latency_ms
        ):
            self.alerts.raise_alert(
                kind=AlertKind.HIGH_LATENCY,
                severity=AlertSeverity.WARNING,
                message="High latency detected",
                now=now,
            )

    def flag_daily_loss(self, *, now: datetime | None = None) -> None:
        with self._lock:
            self.daily_loss_exceeded = True
        self.alerts.raise_alert(
            kind=AlertKind.DAILY_LOSS,
            severity=AlertSeverity.CRITICAL,
            message="Daily loss exceeded",
            now=now,
        )

    def flag_canary_failure(self, message: str, *, now: datetime | None = None) -> None:
        self.alerts.raise_alert(
            kind=AlertKind.CANARY_FAILURE,
            severity=AlertSeverity.CRITICAL,
            message=message,
            now=now,
        )

    def acknowledge_alert(
        self,
        operator: OperatorIdentity,
        alert_id: UUID,
        *,
        now: datetime | None = None,
    ) -> None:
        self.require(operator, OpsPermission.ACK_ALERT)
        updated = self.alerts.acknowledge(
            alert_id,
            operator=operator.display_name or str(operator.user_id),
            now=now,
        )
        if updated is None:
            raise ValueError("alert not found")
        self.audit.record(
            operator=operator,
            action="alert_ack",
            old_value="unacked",
            new_value=str(alert_id),
            reason="acknowledged",
            now=now,
        )

    def execute_runbook(
        self, operator: OperatorIdentity, runbook_id: str
    ) -> dict[str, Any]:
        self.require(operator, OpsPermission.RUN_RUNBOOK)
        result = self.runbooks.execute_checklist(runbook_id)
        self.audit.record(
            operator=operator,
            action="runbook_execute",
            old_value="",
            new_value=runbook_id,
            reason="runbook checklist opened",
        )
        return result

    # --- Dashboards --------------------------------------------------------

    def control_center(self) -> dict[str, Any]:
        active = self.configs.active()
        health = self.health.latest()
        with self._lock:
            return {
                "system_status": "operational" if not self.kill_switch_armed else "halted_oms",
                "gateway_status": (
                    "up" if health and health.gateway_available else "unknown"
                ),
                "mt5_status": (
                    "connected" if health and health.mt5_connected else "unknown"
                ),
                "execution_mode": self.mode.value,
                "kill_switch": self.kill_switch_armed,
                "shadow_mode": self.mode is OpsExecutionMode.SHADOW,
                "canary_mode": self.mode is OpsExecutionMode.CANARY,
                "live_mode": self.mode is OpsExecutionMode.LIVE,
                "strategy_version": self.strategy_version,
                "config_version": self.config_version,
                "git_commit": self.git_commit,
                "promotion_status": self.promotion_status,
                "active_config": active.to_dict() if active else None,
                "oms_orders_allowed": self.oms_orders_allowed(),
                "pme_modifications_allowed": self.pme_modifications_allowed(),
                "risk": {
                    "risk_per_trade_pct": str(self.risk_per_trade_pct),
                    "max_daily_loss_pct": str(self.max_daily_loss_pct),
                    "max_open_trades": self.max_open_trades,
                    "daily_loss_exceeded": self.daily_loss_exceeded,
                },
                "unacked_alerts": self.alerts.unacked_count(),
                "health": health.to_dict() if health else None,
            }

    def readiness_dashboard(self) -> dict[str, Any]:
        cc = self.control_center()
        health = self.health.latest()
        return {
            "research_status": "running",
            "promotion_status": self.promotion_status,
            "execution_status": self.mode.value,
            "risk_status": (
                "halted" if self.daily_loss_exceeded or self.kill_switch_armed else "ok"
            ),
            "gateway": cc["gateway_status"],
            "mt5": cc["mt5_status"],
            "current_mode": self.mode.value,
            "current_strategy": self.strategy_version,
            "current_config": self.config_version,
            "health_score": health.health_score if health else 0,
            "kill_switch": self.kill_switch_armed,
            "git_commit": self.git_commit,
        }


def _detect_git_commit() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
        return out.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


# Process-scoped singleton for API wiring (tests may construct fresh instances)
_GLOBAL_PLANE: OperationsControlPlane | None = None


def get_control_plane() -> OperationsControlPlane:
    global _GLOBAL_PLANE
    if _GLOBAL_PLANE is None:
        _GLOBAL_PLANE = OperationsControlPlane()
    return _GLOBAL_PLANE


def reset_control_plane_for_tests() -> OperationsControlPlane:
    global _GLOBAL_PLANE
    _GLOBAL_PLANE = OperationsControlPlane()
    return _GLOBAL_PLANE
