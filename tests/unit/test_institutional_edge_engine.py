"""Unit tests — Institutional Edge Engine."""

from __future__ import annotations

from decimal import Decimal

from app.domain.institutional_edge_engine import (
    IeeConfig,
    IeeInput,
    InstitutionalEdgeEngine,
)
from app.domain.trading.gold_only import GOLD_SYMBOL


def _trades(n: int = 40) -> list[dict]:
    rows = []
    for i in range(n):
        rows.append(
            {
                "win": i % 3 != 0,
                "pnl": 12 + (i % 5) if i % 3 != 0 else -(8 + (i % 4)),
                "rr": 1.2 if i % 3 != 0 else 0.6,
                "regime": "trend" if i % 2 == 0 else "range",
                "volatility": "high" if i % 4 == 0 else "low",
                "session": ["london", "new_york", "asia"][i % 3],
                "news": i % 11 == 0,
                "entry_timing": "late" if i % 7 == 0 else "ok",
                "exit_timing": "premature" if i % 9 == 0 else "ok",
                "mae": 0.5,
                "mfe": 1.2,
                "holding_time_sec": 90 + i,
                "exit_efficiency": 60,
                "risk_pct": 0.5,
            }
        )
    return rows


def test_hard_locks() -> None:
    status = InstitutionalEdgeEngine().status()
    assert status["symbol"] == GOLD_SYMBOL
    assert status["allow_order_send"] is False
    assert status["allow_disable_trading"] is False
    assert status["invent_metrics"] is False
    caps = status["capabilities"]
    assert caps["never_disables_trading"] is True
    assert caps["never_modify_asi"] is True
    assert caps["never_modify_execution_pipeline"] is True
    assert len(status["modules"]) == 10


def test_policies_locked() -> None:
    cfg = IeeConfig().update(
        {
            "allow_disable_trading": True,
            "invent_metrics": True,
            "allow_modify_strategy_rules": True,
        }
    )
    assert cfg.allow_disable_trading is False
    assert cfg.invent_metrics is False
    assert cfg.allow_modify_strategy_rules is False


def test_insufficient_data() -> None:
    out = InstitutionalEdgeEngine().evaluate(IeeInput(completed_trades=[]))
    assert out["edge_report_summary"]["edge_recommendation"] == (
        "Insufficient Data"
    )
    assert out["never_disables_trading"] is True
    assert out["modifies_asi"] is False


def test_full_edge_evaluation() -> None:
    out = InstitutionalEdgeEngine().evaluate(
        IeeInput(
            completed_trades=_trades(40),
            discipline_facts={
                "rule_compliance_pct": 88,
                "risk_consistency_pct": 80,
                "position_sizing_consistency_pct": 78,
                "drawdown_control_pct": 82,
                "capital_preservation_pct": 85,
            },
            prior_edge_score=Decimal("70"),
            research_month="2026-07",
        )
    )
    assert out["advisory_only"] is True
    assert out["edge_report_summary"]["edge_score"] is not None
    assert out["institutional_score"]["overall_grade"] in {"A", "B", "C", "D"}
    assert out["modules"]["edge_decay"]["details"]["never_disables_trading"]
    assert out["modules"]["monthly_research_package"]["details"][
        "auto_modifies_strategy_rules"
    ] is False
    assert out["modules"]["explainable_edge_report"]["details"][
        "speculation"
    ] is False


def test_edge_warning_on_low_score() -> None:
    # Force many losses → low edge → warning
    losses = [
        {
            "win": False,
            "pnl": -10,
            "rr": 0.5,
            "regime": "range",
            "session": "asia",
            "volatility": "high",
        }
        for _ in range(25)
    ]
    out = InstitutionalEdgeEngine().evaluate(
        IeeInput(completed_trades=losses, prior_edge_score=Decimal("80"))
    )
    assert out["modules"]["edge_scoring"]["status"] == "available"
    decay = out["modules"]["edge_decay"]
    assert decay["details"]["edge_warning"] is True
    assert "EDGE WARNING" in decay["recommendation"]
    assert decay["details"]["never_disables_trading"] is True
