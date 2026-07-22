"""Unit tests — Adaptive Scalping Intelligence."""

from __future__ import annotations

from decimal import Decimal

from app.domain.adaptive_scalping_intelligence import (
    AdaptiveScalpingIntelligence,
    AsiConfig,
    AsiInput,
)
from app.domain.trading.gold_only import GOLD_SYMBOL


def _hist(n: int = 24) -> list[dict]:
    rows = []
    for i in range(n):
        rows.append(
            {
                "session": "london" if i % 2 == 0 else "new_york",
                "hour_utc": 8 + (i % 10),
                "quality": 55 + (i % 30),
                "outcome_score": 50 + (i % 35),
                "personality": "trending" if i % 3 == 0 else "mean_reverting",
                "regime": "trend" if i % 3 == 0 else "range",
                "pattern_id": "sweep_reclaim" if i % 4 == 0 else "bos_continuation",
                "confidence": 60 + (i % 25),
                "win": i % 3 != 0,
                "opportunity_id": f"opp_{i}",
            }
        )
    return rows


def test_hard_locks_and_xauusd() -> None:
    status = AdaptiveScalpingIntelligence().status()
    assert status["symbol"] == GOLD_SYMBOL
    assert status["allow_order_send"] is False
    assert status["invent_statistics"] is False
    assert status["allow_modify_trading_rules"] is False
    caps = status["capabilities"]
    assert caps["never_order_send"] is True
    assert caps["never_fabricate_statistics"] is True
    assert caps["never_modify_execution_pipeline"] is True
    assert caps["never_modify_auto_trading_loop"] is True
    assert len(status["modules"]) == 10


def test_policies_cannot_unlock() -> None:
    cfg = AsiConfig().update(
        {
            "allow_order_send": True,
            "invent_statistics": True,
            "allow_modify_risk_policies": True,
        }
    )
    assert cfg.allow_order_send is False
    assert cfg.invent_statistics is False
    assert cfg.allow_modify_risk_policies is False


def test_insufficient_history_reported() -> None:
    out = AdaptiveScalpingIntelligence().evaluate(
        AsiInput(session="london", historical_observations=[])
    )
    assert out["never_fabricate_statistics"] is True
    assert out["auto_modifies_trading_rules"] is False
    assert out["insufficient_modules"]
    assert any(
        m["status"] == "insufficient_history"
        for m in out["modules"].values()
    )


def test_full_evaluate_with_history() -> None:
    out = AdaptiveScalpingIntelligence().evaluate(
        AsiInput(
            session="london",
            hour_utc=13,
            regime="trend",
            pattern_id="sweep_reclaim",
            live_confidence=Decimal("72"),
            capital_facts={"max_drawdown_pct": 1.0, "daily_loss_pct": 0.2},
            decision_context={"decision": "APPROVE", "reason": "demo"},
            historical_observations=_hist(24),
            closed_trades=[
                {"win": True, "pnl": 10, "confidence": 70},
                {"win": False, "pnl": -5, "confidence": 65},
            ]
            * 8,
            opportunity_catalog=[{"opportunity_id": "opp_0"}],
        )
    )
    assert out["advisory_only"] is True
    assert out["modifies_execution_pipeline"] is False
    assert "market_personality" in out["modules"]
    assert "weekly_ai_coach" in out["modules"]
    assert "decision_explainability" in out["modules"]
    assert out["modules"]["market_personality"]["source"] in {
        "historical",
        "mixed",
        "live",
    }
    assert out["modules"]["opportunity_heat_map"]["status"] == "available"
    coach = out["modules"]["weekly_ai_coach"]
    assert coach["details"]["auto_modifies_trading_rules"] is False


def test_live_vs_historical_labeled() -> None:
    out = AdaptiveScalpingIntelligence().evaluate(
        AsiInput(
            session="london",
            historical_observations=_hist(24),
        )
    )
    for mod in out["modules"].values():
        assert mod["source"] in {"live", "historical", "mixed", "none"}
        assert mod["invented"] is False
        assert mod["explainable"] is True
