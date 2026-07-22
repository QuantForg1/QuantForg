"""Evaluate production alert conditions against live probe + ops facts.

Extends the existing AlertService — does not invent a parallel alerting stack.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.operations.control_plane import (
    OperationsControlPlane,
)
from app.domain.institutional_trading.operations.models import (
    AlertKind,
    AlertSeverity,
    OpsAlert,
)
from app.domain.institutional_trading.reliability.health import ProbeInputs


@dataclass(frozen=True, slots=True)
class ProductionAlertInputs:
    """Facts for production alert evaluation (caller supplies; never invent)."""

    gateway_connected: bool = False
    mt5_connected: bool = False
    login_expired: bool = False
    spread: Decimal | None = None
    max_spread: Decimal = Decimal("2.00")
    ticks_fresh: bool = True
    gateway_latency_ms: float = 0.0
    high_latency_ms: float = 500.0
    execution_timeout: bool = False
    risk_locked: bool = False
    safety_locked: bool = False
    drawdown_pct: Decimal | None = None
    max_drawdown_pct: Decimal = Decimal("10")
    memory_pct: float | None = None
    memory_warn_pct: float = 85.0
    disk_pct: float | None = None
    disk_warn_pct: float = 90.0
    database_ok: bool = True
    calendar_ok: bool = True


def evaluate_production_alerts(
    plane: OperationsControlPlane,
    inputs: ProductionAlertInputs,
) -> list[OpsAlert]:
    """Raise alerts for degraded conditions; return newly raised alerts."""
    raised: list[OpsAlert] = []

    def _raise(kind: AlertKind, severity: AlertSeverity, message: str) -> None:
        raised.append(
            plane.alerts.raise_alert(kind=kind, severity=severity, message=message)
        )

    if not inputs.gateway_connected:
        _raise(
            AlertKind.GATEWAY_OFFLINE,
            AlertSeverity.CRITICAL,
            "Gateway disconnected",
        )
    if not inputs.mt5_connected:
        _raise(
            AlertKind.MT5_DISCONNECTED,
            AlertSeverity.CRITICAL,
            "MT5 disconnected",
        )
    if inputs.login_expired:
        _raise(
            AlertKind.MT5_LOGIN_EXPIRED,
            AlertSeverity.CRITICAL,
            "MT5 login expired",
        )
    if inputs.spread is not None and inputs.spread > inputs.max_spread:
        _raise(
            AlertKind.HIGH_SPREAD,
            AlertSeverity.WARNING,
            f"High spread {inputs.spread} > max {inputs.max_spread}",
        )
    if not inputs.ticks_fresh:
        _raise(
            AlertKind.NO_TICKS,
            AlertSeverity.WARNING,
            "No ticks / stale market data",
        )
    if inputs.gateway_latency_ms > inputs.high_latency_ms:
        _raise(
            AlertKind.HIGH_LATENCY,
            AlertSeverity.WARNING,
            f"High latency {inputs.gateway_latency_ms:.0f}ms",
        )
    if inputs.execution_timeout:
        _raise(
            AlertKind.EXECUTION_TIMEOUT,
            AlertSeverity.CRITICAL,
            "Execution timeout",
        )
    if inputs.risk_locked or plane.daily_loss_exceeded:
        _raise(AlertKind.RISK_LOCK, AlertSeverity.CRITICAL, "Risk lock active")
    if inputs.safety_locked or plane.kill_switch_armed:
        _raise(
            AlertKind.SAFETY_LOCK,
            AlertSeverity.CRITICAL,
            "Safety / kill switch lock",
        )
    if (
        inputs.drawdown_pct is not None
        and inputs.drawdown_pct > inputs.max_drawdown_pct
    ):
        _raise(
            AlertKind.HIGH_DRAWDOWN,
            AlertSeverity.CRITICAL,
            f"High drawdown {inputs.drawdown_pct}%",
        )
    if inputs.memory_pct is not None and inputs.memory_pct >= inputs.memory_warn_pct:
        _raise(
            AlertKind.MEMORY_USAGE,
            AlertSeverity.WARNING,
            f"Memory usage {inputs.memory_pct:.0f}%",
        )
    if inputs.disk_pct is not None and inputs.disk_pct >= inputs.disk_warn_pct:
        _raise(
            AlertKind.DISK_USAGE,
            AlertSeverity.WARNING,
            f"Disk usage {inputs.disk_pct:.0f}%",
        )
    if not inputs.database_ok:
        _raise(
            AlertKind.DATABASE_UNAVAILABLE,
            AlertSeverity.CRITICAL,
            "Database unavailable",
        )
    if not inputs.calendar_ok:
        _raise(
            AlertKind.CALENDAR_UNAVAILABLE,
            AlertSeverity.WARNING,
            "Economic calendar unavailable",
        )
    return raised


def disk_usage_pct(path: str = ".") -> float | None:
    try:
        usage = shutil.disk_usage(path)
        if usage.total <= 0:
            return None
        return (usage.used / usage.total) * 100.0
    except OSError:
        return None


def inputs_from_probes(
    probes: ProbeInputs,
    *,
    plane: OperationsControlPlane | None = None,
    extra: dict[str, Any] | None = None,
) -> ProductionAlertInputs:
    _ = plane  # reserved for future plane-derived facts
    extra = extra or {}
    return ProductionAlertInputs(
        gateway_connected=bool(probes.gateway_available),
        mt5_connected=bool(probes.mt5_connected),
        login_expired=bool(extra.get("login_expired", False)),
        spread=extra.get("spread"),
        ticks_fresh=bool(extra.get("ticks_fresh", probes.mt5_connected)),
        gateway_latency_ms=float(probes.gateway_latency_ms or 0.0),
        execution_timeout=bool(extra.get("execution_timeout", False)),
        risk_locked=bool(extra.get("risk_locked", False)),
        safety_locked=bool(extra.get("safety_locked", False)),
        drawdown_pct=extra.get("drawdown_pct"),
        memory_pct=extra.get("memory_pct"),
        disk_pct=disk_usage_pct(),
        database_ok=bool(extra.get("database_ok", True)),
        calendar_ok=bool(extra.get("calendar_ok", True)),
    )
