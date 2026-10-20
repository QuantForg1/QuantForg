"""Gold Unified Brain — coordination, conflicts, stale data, inventory."""

from __future__ import annotations

from decimal import Decimal

from app.application.services.gold_unified_brain_service import (
    activation_workflow_document,
    decide_from_score,
    evidence_status,
    micro_account_xauusd_feasibility,
)
from app.domain.trading.gold_unified_brain import (
    decide_gold,
    inventory_strategies,
)


def _base_score(**overrides: object) -> dict:
    score = {
        "symbol": "XAUUSD",
        "reject": False,
        "direction": "BUY",
        "trade_quality": 80,
        "ai_confidence": 78,
        "structure_score": 72,
        "momentum": 70,
        "liquidity": 70,
        "mtf_alignment": 75,
        "spread_score": 70,
        "market_regime": "strong_trend",
        "setup_family": "bos_continuation",
        "quote_age_seconds": 5.0,
        "thresholds": {"quality": 74, "confidence": 71, "band": "normal"},
        "factors": {
            "bos": 85,
            "choch": 20,
            "order_block": 80,
            "fvg": 70,
            "momentum": 70,
            "volume": 75,
            "volatility": 70,
            "atr_expansion": 70,
            "ema": 70,
            "trend_strength": 75,
            "pa_confluence": 60,
            "liquidity_sweep": 70,
            "mtf": 75,
            "spread": 70,
        },
    }
    score.update(overrides)
    return score


def test_inventory_lists_five_live_profiles_and_catalog_only() -> None:
    inv = inventory_strategies()
    ids = {p["id"] for p in inv["live_eligible_profiles"]}
    assert ids == {
        "smc_scalping",
        "trend_continuation",
        "breakout_scalping",
        "range_mean_reversion",
        "momentum_scalping",
    }
    catalog_ids = {m["id"] for m in inv["catalog_only_not_live_profiles"]}
    assert "rsi" in catalog_ids
    assert "macd" in catalog_ids
    assert inv["duplicate_engines"] is False


def test_stale_quote_returns_no_trade() -> None:
    d = decide_gold(_base_score(quote_age_seconds=120.0))
    assert d.decision == "NO_TRADE"
    assert d.stale_data is True
    assert d.authorizes_trade is False


def test_no_passers_returns_no_trade() -> None:
    d = decide_gold(
        _base_score(
            reject=True,
            quality_score=10,
            confidence=10,
            structure_score=10,
            momentum_score=10,
        )
    )
    assert d.decision == "NO_TRADE"
    assert d.selected_strategy_id is None


def test_decision_never_authorizes_trade() -> None:
    out = decide_from_score(_base_score())
    assert out["authorizes_trade"] is False
    assert out["profitability_claimed"] is False
    assert out["live_controller_bypass"] is False


def test_activation_workflow_documents_phrase_and_never_auto() -> None:
    doc = activation_workflow_document()
    assert doc["confirmation_phrase"] == "I UNDERSTAND THIS USES REAL MONEY"
    assert "Deploy / restart never ENABLE" in doc["never_auto"]
    assert doc["authorizes_trade_on_read"] is False


def test_evidence_does_not_claim_profitability() -> None:
    ev = evidence_status()
    assert ev["out_of_sample_profitability_claimed"] is False
    assert ev["walk_forward_executed_this_release"] is False


def test_micro_50_usd_not_tradable_or_conditional() -> None:
    payload = micro_account_xauusd_feasibility(Decimal("50"))
    trad = payload["feasibility"]["tradability"]
    assert trad in {"not_tradable", "conditional"}
    assert "volume_min" in payload["symbol_specs"]


def test_conflicting_directions_force_no_trade(monkeypatch) -> None:
    from app.domain.institutional_trading.ai_scalping.strategies.models import (
        StrategyEvaluation,
    )
    import app.domain.trading.gold_unified_brain as brain

    buy = StrategyEvaluation(
        strategy_id="smc_scalping",
        name="SMC",
        symbol="XAUUSD",
        direction="BUY",
        passed=True,
        quality=80,
        confidence=70,
        explanation="buy",
        reject_reason=None,
        filters={},
        score_components={},
    )
    sell = StrategyEvaluation(
        strategy_id="momentum_scalping",
        name="Mom",
        symbol="XAUUSD",
        direction="SELL",
        passed=True,
        quality=75,
        confidence=70,
        explanation="sell",
        reject_reason=None,
        filters={},
        score_components={},
    )
    monkeypatch.setattr(
        brain,
        "evaluate_all_strategies",
        lambda *a, **k: (buy, sell),
    )
    d = decide_gold(_base_score())
    assert d.decision == "NO_TRADE"
    assert d.conflicting is True
