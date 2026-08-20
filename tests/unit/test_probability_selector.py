"""Probability Center is the Gold opportunity selector - no safety bypass."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.domain.institutional_trading.operations.fast_decision_path import (
    CandidateAction,
    DecisionState,
    FaultClass,
    build_current_scan_decision,
    reset_fast_decision_path,
)
from app.domain.institutional_trading.operations.gold_execution_contract import (
    GoldExecutionFacts,
    evaluate_gold_execution_contract,
)
from app.domain.institutional_trading.operations.opportunity_starvation import (
    opportunity_starvation_snapshot,
    record_opportunity_cycle,
    reset_opportunity_starvation,
)
from app.domain.institutional_trading.operations.probability_selector import (
    ADAPTIVE_THRESHOLD_ENABLED,
    OPPORTUNITY_SCORE_THRESHOLD,
    STRONG_CANDIDATE_THRESHOLD,
    evaluate_opportunity,
    weighted_opportunity_score,
)
from app.domain.trading.xauusd_specs import MAX_LEVERAGE

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

ROOT = Path(__file__).resolve().parents[2]


def _ready(**overrides: object) -> GoldExecutionFacts:
    base: dict[str, object] = {
        "symbol": "XAUUSD_I",
        "direction": "BUY",
        "action": "BUY",
        "market_open": True,
        "tradable": True,
        "candles_ok": True,
        "bid": Decimal("2400.10"),
        "ask": Decimal("2400.30"),
        "quote_age_seconds": 1.0,
        "spread": Decimal("0.20"),
        "structure_score": 70,
        "momentum_score": 65,
        "quality": 80,
        "confidence": 75,
        "pa_confluence": 55,
        "risk_reward": Decimal("1.20"),
        "market_regime": "TREND",
        "volatility_ok": True,
        "session_quality_ok": True,
        "safety_allowed": True,
        "kill_switch": False,
        "execution_enabled": True,
        "auto_running": True,
        "account_leverage": Decimal("2000"),
        "risk_eligible": True,
        "approved_lots": Decimal("0.01"),
        "min_lot_infeasible": False,
        "portfolio_allow": True,
        "optimizer_state": "EXECUTE_NOW",
        "oms_orders_allowed": True,
        "gateway_connected": True,
        "broker_connected": True,
        "force_shadow": False,
        "gold_only": True,
        "opportunity_score": 80,
        "opportunity_threshold": 70,
    }
    base.update(overrides)
    return GoldExecutionFacts(**base)  # type: ignore[arg-type]


def test_score_69_is_not_a_candidate() -> None:
    v = evaluate_opportunity(
        direction="BUY",
        structure=60,
        momentum=60,
        quality=60,
        confidence=60,
        regime="range",
        price_action=60,
        liquidity=60,
        volatility=60,
        execution_quality=60,
        mtf_alignment=60,
        risk_reward=1.2,
    )
    # Force the exact 69 band via provided components that sum below 70,
    # then the contract path with an explicit score.
    out = evaluate_gold_execution_contract(_ready(opportunity_score=69))
    assert out.may_submit_oms is False
    assert out.fault_code == "OPPORTUNITY_SCORE_BELOW_THRESHOLD"
    assert out.score_band == "SETUP_NOT_READY"
    assert v.threshold == 70


def test_score_70_is_candidate() -> None:
    out = evaluate_gold_execution_contract(_ready(opportunity_score=70))
    assert out.may_submit_oms is True
    assert out.score_band == "PROBABILITY_CANDIDATE"
    assert out.opportunity_score == 70


def test_score_74_is_candidate() -> None:
    out = evaluate_gold_execution_contract(_ready(opportunity_score=74))
    assert out.may_submit_oms is True
    assert out.score_band == "PROBABILITY_CANDIDATE"


def test_score_85_is_strong_candidate() -> None:
    out = evaluate_gold_execution_contract(_ready(opportunity_score=85))
    assert out.may_submit_oms is True
    assert out.score_band == "STRONG_CANDIDATE"
    assert STRONG_CANDIDATE_THRESHOLD == 85


def test_direction_none_score_90_is_no_trade() -> None:
    out = evaluate_gold_execution_contract(
        _ready(direction="NONE", action="NO_TRADE", opportunity_score=90)
    )
    assert out.may_submit_oms is False
    assert out.fault_code == "DIRECTION_NONE"
    assert out.opportunity_score == 90


def test_score_80_risk_fail_is_hard_block() -> None:
    out = evaluate_gold_execution_contract(
        _ready(risk_eligible=False, risk_reasons=("daily loss limit exceeded",))
    )
    assert out.may_submit_oms is False
    assert out.fault_code == "RISK_REJECTED"
    assert out.fault_class == FaultClass.HARD_BLOCK.value


def test_score_80_safety_fail_is_hard_block() -> None:
    out = evaluate_gold_execution_contract(
        _ready(safety_allowed=False, safety_reasons=("kill switch armed",))
    )
    assert out.may_submit_oms is False
    assert out.fault_code == "SAFETY_BLOCKED"


def test_score_80_stale_quote_is_hard_block() -> None:
    out = evaluate_gold_execution_contract(_ready(quote_age_seconds=200.0))
    assert out.may_submit_oms is False
    assert out.fault_code == "STALE_QUOTE"
    assert out.fault_class == FaultClass.HARD_BLOCK.value


def test_score_80_leverage_2000_passes_leverage_gate() -> None:
    out = evaluate_gold_execution_contract(_ready(account_leverage=Decimal("2000")))
    assert Decimal("2000") == MAX_LEVERAGE
    assert out.may_submit_oms is True


def test_score_80_leverage_2001_is_hard_block() -> None:
    out = evaluate_gold_execution_contract(_ready(account_leverage=Decimal("2001")))
    assert out.may_submit_oms is False
    assert out.fault_code == "LEVERAGE_POLICY_EXCEEDED"
    assert out.fault_class == FaultClass.HARD_BLOCK.value


def test_score_80_all_hard_gates_pass_is_execution_ready() -> None:
    out = evaluate_gold_execution_contract(_ready(opportunity_score=80))
    assert out.decision_state == DecisionState.EXECUTION_READY.value
    assert out.may_submit_oms is True
    assert out.execute_now_required is False


def test_score_cannot_bypass_portfolio() -> None:
    out = evaluate_gold_execution_contract(
        _ready(opportunity_score=92, portfolio_allow=False, portfolio_reasons=("cap",))
    )
    assert out.may_submit_oms is False
    assert out.fault_code == "PORTFOLIO_REJECTED"


def test_score_cannot_bypass_oms() -> None:
    out = evaluate_gold_execution_contract(
        _ready(opportunity_score=92, oms_orders_allowed=False)
    )
    assert out.may_submit_oms is False
    assert out.fault_code == "OMS_NOT_READY"


def test_score_cannot_bypass_reconciliation_unknown() -> None:
    from app.domain.institutional_trading.operations.fast_decision_path import (
        classify_candidate_outcome,
    )

    unknown = classify_candidate_outcome(abort_reason="ORDER_UNKNOWN")
    assert unknown["decision_state"] == DecisionState.ORDER_UNKNOWN.value
    assert unknown["next_action"] == CandidateAction.RECONCILE.value
    shadowed = evaluate_gold_execution_contract(_ready(force_shadow=True))
    assert shadowed.may_submit_oms is False


def test_current_scan_exposes_score_breakdown() -> None:
    reset_fast_decision_path()
    decision = build_current_scan_decision(
        {
            "as_of": "2026-08-20T02:00:00Z",
            "best_symbol": "XAUUSD_I",
            "eligible_symbols": ["XAUUSD_I"],
            "cycle_id": "cycle-test",
            "snapshot_id": "scan-1",
            "opportunity_ranked": [
                {
                    "symbol": "XAUUSD_I",
                    "direction": "BUY",
                    "opportunity_score": 74,
                    "opportunity_threshold": 70,
                    "opportunity_eligible": True,
                    "eligible": True,
                    "score_band": "PROBABILITY_CANDIDATE",
                    "score_breakdown": {"structure": 70, "momentum": 68},
                }
            ],
        }
    )
    assert decision["opportunity_score"] == 74
    assert decision["opportunity_threshold"] == 70
    assert decision["score_band"] == "PROBABILITY_CANDIDATE"
    assert decision["score_breakdown"]["structure"] == 70
    assert decision["direction"] == "BUY"
    assert decision["eligible"] is True
    assert decision["logical_symbol"]
    assert decision["canonical_symbol"]
    assert decision["next_action"] == CandidateAction.RISK_ASSESSMENT.value


def test_current_scan_below_threshold_waits() -> None:
    decision = build_current_scan_decision(
        {
            "as_of": "2026-08-20T02:00:00Z",
            "best_symbol": "XAUUSD_I",
            "eligible_symbols": ["XAUUSD_I"],
            "opportunity_ranked": [
                {
                    "symbol": "XAUUSD_I",
                    "direction": "SELL",
                    "opportunity_score": 63,
                    "opportunity_threshold": 70,
                    "opportunity_eligible": False,
                    "eligible": False,
                    "score_breakdown": {"structure": 55},
                }
            ],
        }
    )
    assert decision["eligible"] is False
    assert decision["blocking_stage"] == "PROBABILITY"
    assert decision["fault_code"] == "OPPORTUNITY_SCORE_BELOW_THRESHOLD"
    assert decision["next_action"] == CandidateAction.WAIT.value
    assert decision["direction"] == "SELL"


def test_decision_center_consumes_same_cycle_snapshot() -> None:
    from app.application.services.decision_intelligence import (
        DecisionIntelligenceService,
    )
    from app.domain.institutional_trading.operations.system_coherence import (
        Plane,
        get_coherence_store,
    )

    store = get_coherence_store()
    store.new_cycle()
    published = store.publish(
        Plane.CURRENT_SCAN.value,
        {
            "symbol": "XAUUSD_i",
            "direction": "BUY",
            "opportunity_score": 74,
            "score_band": "PROBABILITY_CANDIDATE",
            "score_breakdown": {"structure": 70},
        },
        source="test",
        event_type="CURRENT_SCAN",
    )
    result = DecisionIntelligenceService().evaluate(
        {
            "side": "buy",
            "symbol": "XAUUSD_i",
            "cycle_id": published["cycle_id"],
            "snapshot_id": published["snapshot_id"],
            "use_live_facts": False,
            "signal_present": True,
            "strategy_consensus_ok": True,
            "market_regime_ok": True,
            "equity": "10000",
            "price": "2400",
            "spread": "0.40",
            "leverage": "2000",
            "stop_distance": "5",
            "atr": "4.80",
            "kill_switch": False,
            "market_open": True,
        }
    )
    assert result["cycle_id"] == published["cycle_id"]
    assert result["snapshot_id"] == published["snapshot_id"]
    assert result["opportunity_score"] == 74
    assert result["autonomous_execution_authoritative"] is True
    assert result["decision_center_advisory"] is True


def test_no_hidden_structure_momentum_quality_confidence_pa_floors() -> None:
    contract = (
        ROOT / "app/domain/institutional_trading/operations/gold_execution_contract.py"
    ).read_text(encoding="utf-8")
    assert "Weak structure score" not in contract
    assert "facts.momentum_score < floors" not in contract
    assert "facts.quality < floors" not in contract
    assert "facts.confidence < floors" not in contract
    assert "facts.pa_confluence < floors" not in contract
    gates = (
        ROOT / "app/domain/institutional_trading/ai_scalping/quality_gates.py"
    ).read_text(encoding="utf-8")
    assert "soft_rejects.append" in gates
    assert "hard_rejects.append" in gates
    assert "Probability Center is the opportunity selector" in gates
    evaluate = (
        ROOT / "app/domain/institutional_trading/ai_scalping/strategies/evaluate.py"
    ).read_text(encoding="utf-8")
    assert "filters[\"structure_floor\"] = True" in evaluate
    assert "filters[\"momentum_floor\"] = True" in evaluate


def test_mixed_evidence_can_still_clear_threshold() -> None:
    v = evaluate_opportunity(
        direction="BUY",
        structure=55,
        momentum=72,
        regime="strong_trend",
        price_action=60,
        liquidity=85,
        execution_quality=78,
    )
    assert v.opportunity_score >= OPPORTUNITY_SCORE_THRESHOLD
    assert v.eligible is True
    assert v.direction == "BUY"


def test_deterministic_score_for_same_inputs() -> None:
    kwargs = {
        "direction": "SELL",
        "structure": 70,
        "momentum": 68,
        "quality": 75,
        "confidence": 75,
        "regime": "trend",
        "price_action": 65,
        "liquidity": 80,
        "volatility": 74,
        "execution_quality": 70,
        "mtf_alignment": 72,
        "risk_reward": 1.4,
    }
    a = evaluate_opportunity(**kwargs)
    b = evaluate_opportunity(**kwargs)
    assert a.opportunity_score == b.opportunity_score
    assert a.score_breakdown == b.score_breakdown
    again = weighted_opportunity_score(a.score_breakdown)
    assert again[0] == a.opportunity_score


def test_adaptive_threshold_disabled() -> None:
    assert ADAPTIVE_THRESHOLD_ENABLED is False
    assert OPPORTUNITY_SCORE_THRESHOLD == 70


def test_execute_now_is_not_required() -> None:
    out = evaluate_gold_execution_contract(_ready())
    assert out.execute_now_required is False
    runtime = (
        ROOT / "app/application/services/institutional_ite_runtime.py"
    ).read_text(encoding="utf-8")
    assert "evaluate_gold_execution_contract" in runtime


def test_no_duplicate_order_path_and_no_live_order_in_tests() -> None:
    runtime = (
        ROOT / "app/application/services/institutional_ite_runtime.py"
    ).read_text(encoding="utf-8")
    assert "evaluate_gold_execution_contract" in runtime
    assert "self.execution.bridge.handle" in runtime
    selector = (
        ROOT / "app/domain/institutional_trading/operations/probability_selector.py"
    ).read_text(encoding="utf-8")
    contract = (
        ROOT / "app/domain/institutional_trading/operations/gold_execution_contract.py"
    ).read_text(encoding="utf-8")
    for src in (selector, contract):
        assert "order_send(" not in src
        assert "MetaTrader5" not in src


def test_starvation_window_records_scores() -> None:
    reset_opportunity_starvation()
    record_opportunity_cycle(
        opportunity_score=63,
        threshold=70,
        direction="BUY",
        eligible=False,
        fault_code="OPPORTUNITY_SCORE_BELOW_THRESHOLD",
    )
    record_opportunity_cycle(
        opportunity_score=74,
        threshold=70,
        direction="SELL",
        eligible=True,
        execution_ready=True,
    )
    record_opportunity_cycle(
        opportunity_score=80,
        threshold=70,
        direction="BUY",
        eligible=True,
        hard_block=True,
        fault_code="RISK_REJECTED",
    )
    snap = opportunity_starvation_snapshot()
    assert snap["best_score"] == 80
    assert snap["max_score"] == 80
    assert snap["candidate_count"] == 2
    assert snap["hard_block_count"] == 1
    assert snap["soft_wait_count"] == 1
    assert snap["execution_ready_count"] == 1
    assert snap["time_above_70"] == 2
    assert snap["first_hard_blocker"] == "RISK_REJECTED"
    assert snap["adaptive_threshold_enabled"] is False
    assert snap["forces_trades"] is False
