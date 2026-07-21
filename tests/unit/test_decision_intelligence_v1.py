"""Unit tests — QuantForg Decision Intelligence Center."""

from __future__ import annotations

from decimal import Decimal

from app.domain.decision_intelligence import (
    DecisionCenterInput,
    DecisionIntelligenceCenter,
)
from app.domain.decision_intelligence.confidence import ConfidenceFactors
from app.domain.decision_intelligence.config import DecisionIntelligenceConfig
from app.domain.decision_intelligence.override import apply_operator_override
from app.domain.decision_intelligence.quality import QualityInput


def _approve_input(**overrides: object) -> DecisionCenterInput:
    base = DecisionCenterInput(
        signal_present=True,
        strategy_consensus_ok=True,
        market_regime_ok=True,
        confidence_factors=ConfidenceFactors(
            signal_strength=Decimal("75"),
            structure_align=Decimal("70"),
            consensus=Decimal("72"),
            regime_fit=Decimal("68"),
            execution_quality=Decimal("70"),
        ),
        spread=Decimal("0.40"),
        daily_drawdown_pct=Decimal("0.2"),
        consecutive_losses=0,
        risk_engine_passed=True,
        safety_engine_passed=True,
        quality=QualityInput(
            approve_precision=Decimal("70"),
            reject_precision=Decimal("75"),
            override_rate=Decimal("5"),
            audit_completeness=Decimal("100"),
        ),
    )
    if not overrides:
        return base
    data = {
        "side": base.side,
        "strategy_id": base.strategy_id,
        "technique": base.technique,
        "signal_present": base.signal_present,
        "strategy_consensus_ok": base.strategy_consensus_ok,
        "market_regime_ok": base.market_regime_ok,
        "confidence_factors": base.confidence_factors,
        "spread": base.spread,
        "daily_drawdown_pct": base.daily_drawdown_pct,
        "consecutive_losses": base.consecutive_losses,
        "risk_engine_passed": base.risk_engine_passed,
        "safety_engine_passed": base.safety_engine_passed,
        "quality": base.quality,
        "operator_action": base.operator_action,
        "operator": base.operator,
        "operator_reason": base.operator_reason,
    }
    data.update(overrides)
    return DecisionCenterInput(**data)  # type: ignore[arg-type]


def test_hold_without_risk_safety() -> None:
    center = DecisionIntelligenceCenter()
    result = center.evaluate(
        _approve_input(risk_engine_passed=None, safety_engine_passed=None)
    )
    assert result.decision == "HOLD"
    assert result.allow_execution_path is False
    assert any(s.name == "risk_engine" and not s.passed for s in result.waterfall)


def test_approve_when_gates_pass() -> None:
    center = DecisionIntelligenceCenter()
    result = center.evaluate(_approve_input())
    assert result.decision == "APPROVE"
    assert result.allow_execution_path is True
    assert result.executive_panel.to_dict()["never_force_execution"] is True
    assert result.capabilities["force_execution"] is False
    assert result.capabilities["bypass_risk"] is False


def test_operator_reject_veto() -> None:
    center = DecisionIntelligenceCenter()
    result = center.evaluate(
        _approve_input(
            operator_action="reject",
            operator="alice",
            operator_reason="desk veto",
        )
    )
    assert result.decision == "REJECT"
    assert result.veto.clear is False


def test_force_approve_blocked() -> None:
    override = apply_operator_override(
        action="force_approve", operator="bob", reason="try"
    )
    assert override.action == "hold"
    assert override.forced_execution is False

    center = DecisionIntelligenceCenter()
    result = center.evaluate(
        _approve_input(operator_action="force_execute", operator="bob")
    )
    assert result.decision == "HOLD"
    assert result.allow_execution_path is False


def test_veto_on_spread_and_losses() -> None:
    center = DecisionIntelligenceCenter()
    result = center.evaluate(
        _approve_input(spread=Decimal("9"), consecutive_losses=5)
    )
    assert result.decision == "REJECT"
    assert result.veto.clear is False


def test_history_and_replay_auditable() -> None:
    center = DecisionIntelligenceCenter()
    first = center.evaluate(_approve_input())
    hist = center.list_history(limit=5)
    assert len(hist) >= 1
    replay = center.replay(first.audit_id)
    assert replay["status"] == "available"
    assert replay["replay"]["audit_id"] == first.audit_id


def test_policies_configurable_hard_locks() -> None:
    center = DecisionIntelligenceCenter()
    updated = center.update_policies({"min_confidence": "70", "max_spread": "1.5"})
    assert updated["min_confidence"] == "70"
    assert updated["allow_force_execution"] is False
    assert updated["allow_bypass_risk"] is False
    assert updated["require_risk_engine"] is True


def test_config_hard_locks() -> None:
    cfg = DecisionIntelligenceConfig(
        allow_force_execution=True,  # type: ignore[arg-type]
        allow_bypass_risk=True,  # type: ignore[arg-type]
        allow_bypass_safety=True,  # type: ignore[arg-type]
        allow_operator_force_approve=True,  # type: ignore[arg-type]
        require_risk_engine=False,  # type: ignore[arg-type]
        require_safety_engine=False,  # type: ignore[arg-type]
    )
    assert cfg.allow_force_execution is False
    assert cfg.allow_bypass_risk is False
    assert cfg.require_risk_engine is True
    assert cfg.require_safety_engine is True


def test_service_roundtrip() -> None:
    from app.application.services.decision_intelligence import (
        DecisionIntelligenceService,
    )

    svc = DecisionIntelligenceService()
    status = svc.status()
    assert "decision-intelligence" in str(status["version"])
    out = svc.evaluate(
        {
            "signal_present": True,
            "strategy_consensus_ok": True,
            "market_regime_ok": True,
            "spread": "0.4",
            "confidence_factors": {
                "signal_strength": "80",
                "structure_align": "75",
                "consensus": "70",
                "regime_fit": "70",
                "execution_quality": "70",
            },
            "risk_engine_passed": True,
            "safety_engine_passed": True,
        }
    )
    assert out["decision"] == "APPROVE"
    assert out["capabilities"]["force_execution"] is False
    assert "summary" in out
    assert "waterfall" in out
