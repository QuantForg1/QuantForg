"""Unit tests — QuantForg Alpha Engine V1."""

from __future__ import annotations

from decimal import Decimal

from app.application.services.decision_intelligence import (
    DecisionIntelligenceService,
    _merge_alpha_advisory,
)
from app.domain.alpha_engine import AlphaEngine, AlphaEngineInput
from app.domain.alpha_engine.config import AlphaEngineConfig
from app.domain.trading.gold_only import GOLD_SYMBOL


def _rich_input() -> AlphaEngineInput:
    return AlphaEngineInput(
        regime={
            "trend": "up",
            "atr": "15",
            "price": "2300",
            "news_driven": False,
            "structure_label": "bullish",
        },
        liquidity={"spread": "0.35", "liquidity_pools": [{"z": 1}], "sweep_count": 2},
        structure={"bias": "bullish", "bos": True, "choch": False, "swing_count": 4},
        order_flow={"imbalance": "0.4", "delta": "2", "volume_burst": True},
        opportunities=[
            {"id": "a", "score": 80, "label": "sweep"},
            {"id": "b", "score": 55, "label": "fvg"},
        ],
        execution={"spread": "0.35", "session": "london", "timing_score": 70},
        exit_context={"mfe": "5", "mae": "1", "structure_invalidated": False},
        trade_factors={
            "setup_quality": 70,
            "risk_reward": 75,
            "location_quality": 68,
            "timing_quality": 72,
            "management_quality": 65,
        },
        closed_trades=[{"execution_quality": 0.8, "slippage": 0.1}],
        side="buy",
    )


def test_xauusd_only_and_hard_locks() -> None:
    status = AlphaEngine().status()
    assert status["symbol"] == GOLD_SYMBOL
    assert status["allow_order_send"] is False
    assert status["promise_profitability"] is False
    caps = status["capabilities"]
    assert caps["bypass_risk"] is False
    assert caps["bypass_safety"] is False


def test_unavailable_without_facts() -> None:
    result = AlphaEngine().evaluate(AlphaEngineInput())
    assert result.symbol == GOLD_SYMBOL
    assert result.composite_score is None
    assert result.market_quality_band == "unavailable"
    assert result.engines["market_regime"].status == "unavailable"
    assert result.advisory_only is True


def test_evaluate_explainable_scores() -> None:
    result = AlphaEngine().evaluate(_rich_input())
    assert result.composite_score is not None
    assert result.composite_score > Decimal("0")
    assert result.market_quality_ok is not None
    for engine in result.engines.values():
        assert engine.status == "available"
        assert engine.reasons
        assert engine.to_dict()["explainable"] is True
        assert engine.to_dict()["invented"] is False
    assert result.decision_center_inputs["never_sets_risk_or_safety"] is True
    assert "risk_engine_passed" not in result.decision_center_inputs
    assert "safety_engine_passed" not in result.decision_center_inputs


def test_policies_cannot_enable_order_send() -> None:
    cfg = AlphaEngineConfig().update(
        {
            "allow_order_send": True,
            "promise_profitability": True,
            "min_confluence_score": 70,
        }
    )
    assert cfg.allow_order_send is False
    assert cfg.promise_profitability is False
    assert cfg.min_confluence_score == Decimal("70")


def test_history_auditable() -> None:
    engine = AlphaEngine()
    result = engine.evaluate(_rich_input())
    assert result.audit_id.startswith("ae_")
    hist = engine.list_history(limit=5)
    assert hist[0]["audit_id"] == result.audit_id
    replay = engine.replay(result.audit_id)
    assert replay["status"] == "available"


def test_empty_opportunity_candidates() -> None:
    result = AlphaEngine().evaluate(AlphaEngineInput(opportunities=[]))
    assert result.engines["opportunity"].status == "empty"


def test_decision_center_alpha_merge_never_sets_risk_safety() -> None:
    payload = _merge_alpha_advisory(
        {
            "side": "buy",
            "alpha": {
                "market_regime_ok": True,
                "confidence_factors": {"regime_fit": "72", "consensus": "68"},
                "alpha_composite_score": "71",
                "risk_engine_passed": True,
                "safety_engine_passed": True,
            },
        }
    )
    assert payload["market_regime_ok"] is True
    assert payload["confidence_factors"]["regime_fit"] == "72"
    assert payload.get("risk_engine_passed") is None
    assert payload["_alpha_audit"]["never_sets_risk_or_safety"] is True

    # Risk/Safety still required → HOLD
    out = DecisionIntelligenceService().evaluate(
        {
            "side": "buy",
            "signal_present": True,
            "strategy_consensus_ok": True,
            "alpha": {
                "market_regime_ok": True,
                "confidence_factors": {
                    "signal_strength": 75,
                    "structure_align": 70,
                    "consensus": 72,
                    "regime_fit": 68,
                    "execution_quality": 70,
                },
            },
        }
    )
    assert out["decision"] == "HOLD"
    assert out["allow_execution_path"] is False
    assert out["alpha_integration"]["integrated"] is True
