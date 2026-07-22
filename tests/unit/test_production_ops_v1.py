"""Production alerts + services health for institutional ops."""

from __future__ import annotations

from decimal import Decimal

from app.domain.institutional_trading.operations.control_plane import (
    OperationsControlPlane,
)
from app.domain.institutional_trading.operations.models import AlertKind
from app.domain.institutional_trading.operations.production_alerts import (
    ProductionAlertInputs,
    evaluate_production_alerts,
)
from app.domain.institutional_trading.operations.runbooks import RUNBOOKS


def test_production_alerts_raise_expected_kinds() -> None:
    plane = OperationsControlPlane()
    raised = evaluate_production_alerts(
        plane,
        ProductionAlertInputs(
            gateway_connected=False,
            mt5_connected=False,
            login_expired=True,
            spread=Decimal("5"),
            max_spread=Decimal("2"),
            ticks_fresh=False,
            gateway_latency_ms=900,
            high_latency_ms=500,
            execution_timeout=True,
            risk_locked=True,
            safety_locked=True,
            drawdown_pct=Decimal("15"),
            max_drawdown_pct=Decimal("10"),
            memory_pct=90,
            disk_pct=95,
            database_ok=False,
            calendar_ok=False,
        ),
    )
    kinds = {a.kind for a in raised}
    assert AlertKind.GATEWAY_OFFLINE in kinds
    assert AlertKind.MT5_DISCONNECTED in kinds
    assert AlertKind.MT5_LOGIN_EXPIRED in kinds
    assert AlertKind.HIGH_SPREAD in kinds
    assert AlertKind.NO_TICKS in kinds
    assert AlertKind.HIGH_LATENCY in kinds
    assert AlertKind.EXECUTION_TIMEOUT in kinds
    assert AlertKind.RISK_LOCK in kinds
    assert AlertKind.SAFETY_LOCK in kinds
    assert AlertKind.HIGH_DRAWDOWN in kinds
    assert AlertKind.MEMORY_USAGE in kinds
    assert AlertKind.DISK_USAGE in kinds
    assert AlertKind.DATABASE_UNAVAILABLE in kinds
    assert AlertKind.CALENDAR_UNAVAILABLE in kinds


def test_alert_dedupe_same_kind() -> None:
    plane = OperationsControlPlane()
    a1 = evaluate_production_alerts(
        plane, ProductionAlertInputs(gateway_connected=False)
    )
    a2 = evaluate_production_alerts(
        plane, ProductionAlertInputs(gateway_connected=False)
    )
    assert len(a1) >= 1
    assert a1[0].id == a2[0].id
    unacked = plane.alerts.list(unacked_only=True)
    gateway = [a for a in unacked if a.kind == AlertKind.GATEWAY_OFFLINE]
    assert len(gateway) == 1


def test_operator_runbooks_cover_production_set() -> None:
    required = {
        "startup",
        "shutdown",
        "restart",
        "recovery",
        "disaster_recovery",
        "incident_response",
        "gateway_restart",
        "broker_failure",
        "emergency_shutdown",
        "mt5_reconnect",
    }
    assert required.issubset(set(RUNBOOKS))
