"""Unit tests — QuantForg Production Readiness Program."""

from __future__ import annotations

from app.domain.production_readiness import (
    HealthPolicies,
    ProductionReadinessCenter,
    ReadinessFeeds,
)


def test_status_hard_locks() -> None:
    status = ProductionReadinessCenter().status()
    assert status["never_bypasses_risk"] is True
    assert status["never_bypasses_safety"] is True
    assert status["never_changes_execution_architecture"] is True
    caps = status["capabilities"]
    assert caps["bypass_risk"] is False
    assert caps["bypass_safety"] is False
    assert caps["order_send"] is False
    assert caps["recovery_never_retries_orders"] is True


def test_policies_cannot_bypass_risk_safety() -> None:
    policies = HealthPolicies()
    updated = policies.update(
        {
            "allow_bypass_risk": True,
            "allow_bypass_safety": True,
            "never_retry_order_send": False,
            "min_health_score": 90,
        }
    )
    assert updated.allow_bypass_risk is False
    assert updated.allow_bypass_safety is False
    assert updated.never_retry_order_send is True
    assert updated.min_health_score == 90.0


def test_unavailable_without_feeds() -> None:
    dash = ProductionReadinessCenter().build_dashboard(ReadinessFeeds())
    panels = dash["panels"]
    assert panels["pre_trade_validation"]["status"] == "unavailable"
    assert panels["circuit_breakers"]["status"] == "unavailable"
    assert panels["incident_manager"]["status"] == "unavailable"
    assert dash["never_bypasses_risk"] is True


def test_pre_trade_requires_risk_safety() -> None:
    dash = ProductionReadinessCenter().build_dashboard(
        ReadinessFeeds(
            pre_trade_facts={
                "broker_connected": True,
                "market_open": True,
                "risk_passed": True,
                "margin_sufficient": True,
                "strategy_signal_valid": True,
                "execution_enabled": False,
                "risk_engine_passed": False,
                "safety_engine_passed": True,
            }
        )
    )
    pre = dash["panels"]["pre_trade_validation"]
    assert pre["status"] == "available"
    assert pre["data"]["blocked"] is True
    assert pre["data"]["never_bypasses_risk"] is True


def test_circuit_breakers_and_health_policies() -> None:
    center = ProductionReadinessCenter()
    dash = center.build_dashboard(
        ReadinessFeeds(
            control_center={
                "kill_switch": False,
                "oms_orders_allowed": True,
                "execution_mode": "SHADOW",
                "system_status": "operational",
                "risk": {"daily_loss_exceeded": False},
                "auto_trading": {"status": "off"},
                "health": {
                    "health_score": 95,
                    "gateway_available": True,
                    "mt5_connected": True,
                    "gateway_latency_ms": 40,
                },
            }
        )
    )
    assert dash["panels"]["circuit_breakers"]["data"]["kill_switch"] is False
    health = dash["panels"]["platform_health_policies"]
    assert health["status"] == "available"
    assert health["data"]["evaluation"]["passed"] is True


def test_recovery_and_failure_auditable() -> None:
    center = ProductionReadinessCenter()
    center.log_recovery(
        action="gateway", ok=True, detail="reconnect ok", operator="alice"
    )
    center.log_failure(action="probe", detail="gateway timeout", operator="alice")
    audit = center.list_audit()
    assert audit["status"] == "available"
    assert len(audit["events"]) == 2
    assert audit["events"][0]["ok"] is False


def test_playbooks_and_dr() -> None:
    dash = ProductionReadinessCenter().build_dashboard(
        ReadinessFeeds(
            runbooks=[
                {"id": "emergency_shutdown", "title": "Emergency shutdown"},
                {"id": "gateway_restart", "title": "Gateway restart"},
            ],
            recovery_events=[{"action": "GATEWAY_RECONNECT", "ok": True}],
            ops_audit=[{"action": "kill_switch.arm"}],
        )
    )
    assert dash["panels"]["operator_playbooks"]["status"] == "available"
    dr = dash["panels"]["disaster_recovery"]
    assert dr["status"] == "available"
    assert dr["data"]["never_retries_order_send"] is True


def test_post_trade_empty() -> None:
    dash = ProductionReadinessCenter().build_dashboard(
        ReadinessFeeds(post_trade_rows=[])
    )
    assert dash["panels"]["post_trade_validation"]["status"] == "empty"
