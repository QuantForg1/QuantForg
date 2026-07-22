"""Unit tests — Production Readiness Certification."""

from __future__ import annotations

from app.domain.production_readiness_certification import (
    PrcConfig,
    PrcInput,
    ProductionReadinessCertification,
)
from app.domain.production_readiness_certification.modules import (
    INSUFFICIENT,
    VERDICT_PASS,
)
from app.domain.trading.gold_only import GOLD_SYMBOL


def _full_pass() -> PrcInput:
    return PrcInput(
        reliability={
            "service_uptime_pct": 99.5,
            "recovery_success_rate_pct": 98,
            "restart_recovery_ok": True,
            "watchdog_health_ok": True,
            "mt5_synchronization_ok": True,
            "incident_rate_per_day": 0.1,
            "duplicate_protection_ok": True,
        },
        risk={
            "risk_policy_compliance_pct": 99,
            "maximum_drawdown_pct": 3,
            "position_sizing_consistency_ok": True,
            "daily_loss_compliance_ok": True,
            "exposure_discipline_ok": True,
        },
        execution={
            "fill_reliability_pct": 99,
            "execution_latency_ms_p95": 100,
            "broker_acknowledgement_ok": True,
            "slippage_observations_ok": True,
            "retry_behavior_ok": True,
        },
        decision={
            "decision_explainability_ok": True,
            "decision_consistency_pct": 95,
            "confidence_calibration_ok": True,
            "no_trade_discipline_ok": True,
        },
        data={
            "market_data_integrity_ok": True,
            "missing_data_handling_ok": True,
            "feed_coverage_pct": 98,
            "timestamp_consistency_ok": True,
            "historical_completeness_pct": 95,
        },
        research={
            "replay_evidence_ok": True,
            "paper_trading_evidence_ok": True,
            "ivp_evidence_ok": True,
            "llp_evidence_ok": True,
            "alpha_factory_evidence_ok": True,
        },
        operations={
            "health_ok": True,
            "monitoring_ok": True,
            "alerts_ok": True,
            "audit_ok": True,
            "logging_ok": True,
            "recovery_ok": True,
            "operator_workflow_ok": True,
        },
    )


def test_hard_locks_certifies_only() -> None:
    status = ProductionReadinessCertification().status()
    assert status["symbol"] == GOLD_SYMBOL
    assert status["allow_order_send"] is False
    assert status["allow_change_configuration_automatically"] is False
    caps = status["capabilities"]
    assert caps["certifies_only"] is True
    assert caps["human_approval_required"] is True
    assert caps["never_modify_auto_trading"] is True
    assert len(status["modules"]) == 10


def test_policies_cannot_unlock() -> None:
    cfg = PrcConfig().update(
        {
            "allow_order_send": True,
            "allow_modify_risk_engine": True,
            "allow_change_configuration_automatically": True,
        }
    )
    assert cfg.allow_order_send is False
    assert cfg.allow_modify_risk_engine is False
    assert cfg.allow_change_configuration_automatically is False


def test_insufficient_without_evidence() -> None:
    out = ProductionReadinessCertification().evaluate(PrcInput())
    assert (
        out["modules"]["reliability_certification"]["recommendation"]
        == INSUFFICIENT
    )
    assert out["human_approval_required"] is True
    assert out["changes_configuration_automatically"] is False


def test_full_certification_pass() -> None:
    prc = ProductionReadinessCertification()
    out = prc.evaluate(_full_pass())
    assert out["certifies_only"] is True
    assert out["modifies_auto_trading"] is False
    report = out["certification_report"]
    assert report["human_approval_required"] is True
    assert report["certification_status"] == VERDICT_PASS
    assert float(report["overall_readiness_score"]) >= 80
    assert out["modules"]["human_signoff_package"]["details"][
        "human_approval_required"
    ] is True
    assert out["modules"]["human_signoff_package"]["details"][
        "auto_deploy"
    ] is False


def test_status_change_notifies_only() -> None:
    prc = ProductionReadinessCertification()
    prc.evaluate(_full_pass())
    # Degrade reliability → status should change and notify
    degraded = _full_pass()
    out = prc.evaluate(
        PrcInput(
            reliability={
                "service_uptime_pct": 80,
                "recovery_success_rate_pct": 50,
                "restart_recovery_ok": False,
                "watchdog_health_ok": False,
                "mt5_synchronization_ok": False,
                "incident_rate_per_day": 5,
                "duplicate_protection_ok": False,
            },
            risk=degraded.risk,
            execution=degraded.execution,
            decision=degraded.decision,
            data=degraded.data,
            research=degraded.research,
            operations=degraded.operations,
        )
    )
    cont = out["modules"]["continuous_certification"]["details"]
    assert cont["changes_production"] is False
    assert cont["auto_configure"] is False
    assert cont["notify_operators"] is True or cont["status_changed"] is True
    assert len(prc.history) >= 2
