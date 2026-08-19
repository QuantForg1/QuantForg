"""Decision Center Risk/Safety handoff — engines must actually run."""

from __future__ import annotations

import inspect

from app.application.services.decision_intelligence import DecisionIntelligenceService
from app.application.services.decision_intelligence_assessment import (
    GoldAssessmentFacts,
    assess_decision_center_engines,
    assess_risk_engine,
    assess_safety_engine,
)
from app.domain.trading.gold_only import CANONICAL_GOLD_BROKER_DISPLAY
from app.domain.trading.xauusd_specs import MAX_LEVERAGE


def _gold_payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "symbol": CANONICAL_GOLD_BROKER_DISPLAY,
        "side": "buy",
        "signal_present": True,
        "strategy_consensus_ok": True,
        "market_regime_ok": True,
        "spread": "0.40",
        "equity": "10000",
        "leverage": str(MAX_LEVERAGE),
        "price": "2400",
        "stop_distance": "5",
        "atr": "4.80",
        "consecutive_losses": 0,
        "daily_drawdown_pct": "0.2",
        "daily_pnl": "0",
        "kill_switch": False,
        "market_open": True,
        "use_live_facts": False,
        "confidence_factors": {
            "signal_strength": "75",
            "structure_align": "70",
            "consensus": "72",
            "regime_fit": "68",
            "execution_quality": "70",
        },
    }
    body.update(overrides)
    return body


def _stage(result: dict[str, object], name: str) -> dict[str, object]:
    rows = result["waterfall"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, dict)
        if row.get("name") == name:
            return row
    raise AssertionError(f"missing waterfall stage {name}")


def test_gold_decision_receives_current_symbol() -> None:
    svc = DecisionIntelligenceService()
    out = svc.evaluate(_gold_payload())
    assert out["symbol"] == CANONICAL_GOLD_BROKER_DISPLAY
    assessment = out["assessment"]
    assert isinstance(assessment, dict)
    assert assessment["symbol"] == CANONICAL_GOLD_BROKER_DISPLAY
    assert str(assessment["evaluated_at"]).endswith("Z")
    assert assessment["order_send"] is False
    assert assessment["execute_now_required"] is False


def test_risk_and_safety_are_actually_assessed_on_gold() -> None:
    svc = DecisionIntelligenceService()
    out = svc.evaluate(_gold_payload())
    risk = _stage(out, "risk_engine")
    safety = _stage(out, "safety_engine")
    assert risk["state"] == "PASS"
    assert safety["state"] == "PASS"
    assessment = out["assessment"]
    assert isinstance(assessment, dict)
    assert assessment["risk"]["source"] == "risk_engine.evaluate"
    assert assessment["safety"]["source"] == "execution_policy.evaluate"
    assert out["decision"] == "APPROVE"
    assert out["allow_execution_path"] is True


def test_not_assessed_only_when_not_runnable() -> None:
    svc = DecisionIntelligenceService()
    out = svc.evaluate(
        _gold_payload(
            equity=None,
            leverage=None,
            price=None,
            spread=None,
            risk_engine_passed=None,
            safety_engine_passed=None,
        )
    )
    risk = _stage(out, "risk_engine")
    safety = _stage(out, "safety_engine")
    assert risk["state"] == "NOT_ASSESSED"
    assert safety["state"] == "NOT_ASSESSED"
    assert out["decision"] == "HOLD"
    assert out["allow_execution_path"] is False
    assessment = out["assessment"]
    assert isinstance(assessment, dict)
    assert "equity" in assessment["risk"]["missing"]
    assert "leverage" in assessment["safety"]["missing"]


def test_risk_pass_and_safety_pass_propagate() -> None:
    facts, risk, safety = assess_decision_center_engines(
        _gold_payload(),
        use_live=False,
    )
    assert facts.symbol == CANONICAL_GOLD_BROKER_DISPLAY
    assert risk.state == "PASS" and risk.passed is True
    assert safety.state == "PASS" and safety.passed is True


def test_risk_fail_is_hard_block() -> None:
    svc = DecisionIntelligenceService()
    out = svc.evaluate(_gold_payload(consecutive_losses=10))
    risk = _stage(out, "risk_engine")
    assert risk["state"] == "FAIL"
    assert out["decision"] == "REJECT"
    assert out["allow_execution_path"] is False


def test_safety_fail_is_hard_block() -> None:
    svc = DecisionIntelligenceService()
    over_lev = str(MAX_LEVERAGE + 1)
    out = svc.evaluate(_gold_payload(leverage=over_lev))
    safety = _stage(out, "safety_engine")
    assert safety["state"] == "FAIL"
    assert "max_leverage" in str(safety["reason"])
    assert out["decision"] == "REJECT"
    assert out["allow_execution_path"] is False


def test_confidence_does_not_bypass_risk_or_safety() -> None:
    svc = DecisionIntelligenceService()
    out = svc.evaluate(
        _gold_payload(consecutive_losses=10, leverage=str(MAX_LEVERAGE + 1))
    )
    conf = out["confidence"]
    assert isinstance(conf, dict)
    assert conf["passed"] is True
    assert float(str(conf["score"])) >= 65
    assert _stage(out, "risk_engine")["state"] == "FAIL"
    assert _stage(out, "safety_engine")["state"] == "FAIL"
    assert out["decision"] == "REJECT"
    assert out["allow_execution_path"] is False


def test_claimed_true_cannot_bypass_engine_fail() -> None:
    svc = DecisionIntelligenceService()
    out = svc.evaluate(
        _gold_payload(
            consecutive_losses=10,
            leverage=str(MAX_LEVERAGE + 1),
            risk_engine_passed=True,
            safety_engine_passed=True,
        )
    )
    assert _stage(out, "risk_engine")["state"] == "FAIL"
    assert _stage(out, "safety_engine")["state"] == "FAIL"
    assert out["decision"] == "REJECT"


def test_force_and_bypass_remain_off() -> None:
    svc = DecisionIntelligenceService()
    out = svc.evaluate(_gold_payload())
    caps = out["capabilities"]
    assert isinstance(caps, dict)
    assert caps["force_execution"] is False
    assert caps["bypass_risk"] is False
    assert caps["bypass_safety"] is False
    assessment = out["assessment"]
    assert isinstance(assessment, dict)
    assert assessment["force_execution"] is False
    assert assessment["bypass_risk"] is False
    assert assessment["bypass_safety"] is False


def test_autonomous_evaluate_does_not_depend_on_execute_now() -> None:
    eval_src = inspect.getsource(DecisionIntelligenceService.evaluate)
    assess_src = inspect.getsource(assess_decision_center_engines)
    for src in (eval_src, assess_src):
        assert "order_send(" not in src
        assert "execute_now(" not in src.lower()
        assert "FORCE_FIRST_TRADE" not in src
        assert "ALLOW_RISK_LOCK_OVERRIDE" not in src


def test_non_gold_decision_is_not_assessed() -> None:
    risk = assess_risk_engine(
        GoldAssessmentFacts(
            symbol="EURUSD",
            equity=None,
            entry_price=None,
            spread=None,
            leverage=None,
        )
    )
    safety = assess_safety_engine(
        GoldAssessmentFacts(symbol="EURUSD", spread=None, leverage=None)
    )
    assert risk.state == "NOT_ASSESSED"
    assert safety.state == "NOT_ASSESSED"
    assert "gold-only" in risk.reason.lower()
