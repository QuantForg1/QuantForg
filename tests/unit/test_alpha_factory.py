"""Unit tests — Alpha Factory."""

from __future__ import annotations

from app.domain.alpha_factory import AlphaFactory, AlphaFactoryConfig, AlphaFactoryInput
from app.domain.trading.gold_only import GOLD_SYMBOL


def test_hard_locks_outside_production() -> None:
    status = AlphaFactory().status()
    assert status["symbol"] == GOLD_SYMBOL
    assert status["allow_order_send"] is False
    assert status["allow_automatic_promotion"] is False
    assert status["allow_modify_live_strategy"] is False
    caps = status["capabilities"]
    assert caps["outside_production"] is True
    assert caps["never_automatic_promotion"] is True
    assert caps["never_modify_execution_pipeline"] is True
    assert len(status["modules"]) == 10


def test_policies_cannot_unlock() -> None:
    cfg = AlphaFactoryConfig().update(
        {
            "allow_order_send": True,
            "allow_automatic_promotion": True,
            "allow_modify_auto_trading": True,
        }
    )
    assert cfg.allow_order_send is False
    assert cfg.allow_automatic_promotion is False
    assert cfg.allow_modify_auto_trading is False


def test_insufficient_alpha_score() -> None:
    out = AlphaFactory().evaluate(
        AlphaFactoryInput(score_inputs={"consistency": 70})
    )
    assert out["modules"]["alpha_score"]["recommendation"] == (
        "Insufficient Data"
    )
    assert out["automatic_promotion"] is False


def test_full_research_cycle() -> None:
    out = AlphaFactory().evaluate(
        AlphaFactoryInput(
            author="qa",
            experiment={
                "author": "qa",
                "version": "0.1.0",
                "status": "active",
                "description": "test",
            },
            strategy={"family": "Breakout", "name": "BO1", "certified": False},
            strategies=[
                {"id": "c1", "family": "SMC", "name": "S1", "certified": True}
            ],
            replay={
                "timeframe": "5m",
                "trades": [{"pnl": 1}] * 22,
                "expectancy": 2.0,
                "drawdown": 1.5,
                "profit_factor": 1.3,
                "equity_curve": [100, 102],
            },
            paper={
                "trades": [{"pnl": 1}] * 12,
                "performance": {"expectancy": 1.1},
                "risk_metrics": {"max_dd": 2},
                "execution_timing": {"avg_latency_ms": 40},
            },
            benchmarks=[
                {
                    "name": "A",
                    "win_rate": 55,
                    "profit_factor": 1.4,
                    "drawdown": 3,
                    "expectancy": 2,
                    "trade_count": 30,
                },
                {
                    "name": "B",
                    "win_rate": 50,
                    "profit_factor": 1.2,
                    "drawdown": 4,
                    "expectancy": 1.5,
                    "trade_count": 25,
                },
            ],
            promotion={
                "stage": "Paper Trading",
                "approvals": {"research": True, "risk": False, "operator": False},
            },
            score_inputs={
                "consistency": 70,
                "risk_discipline": 75,
                "edge_stability": 68,
                "capital_preservation": 72,
                "market_adaptability": 70,
                "execution_quality": 74,
            },
            history_event={"experiment_id": "e1", "comments": "note"},
        )
    )
    assert out["outside_production"] is True
    assert out["modifies_live_strategy"] is False
    assert out["modifies_auto_trading"] is False
    assert out["research_summary"]["active_experiments"] >= 1
    assert out["certified_strategies"]["count"] == 1
    assert out["modules"]["promotion_workflow"]["details"][
        "never_auto_promotes"
    ] is True
    assert out["modules"]["promotion_report"]["details"][
        "never_auto_promotes"
    ] is True
    assert out["modules"]["replay_engine"]["status"] == "available"
    assert out["modules"]["benchmark_engine"]["status"] == "available"


def test_promotion_never_auto() -> None:
    out = AlphaFactory().evaluate(
        AlphaFactoryInput(
            promotion={"stage": "Production", "auto_promote": True}
        )
    )
    promo = out["modules"]["promotion_workflow"]
    assert promo["details"]["automatic_promotion"] is False
    assert promo["details"]["never_auto_promotes"] is True
