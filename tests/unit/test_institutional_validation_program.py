"""Unit tests — Institutional Validation Program."""

from __future__ import annotations

from app.domain.institutional_validation_program import (
    InstitutionalValidationProgram,
    IvpConfig,
    IvpInput,
)
from app.domain.trading.gold_only import GOLD_SYMBOL


def _trades(n: int, *, regime_cycle: bool = False) -> list[dict]:
    regimes = [
        "trend",
        "range",
        "high_volatility",
        "low_volatility",
        "london",
        "new_york",
        "asia",
        "news",
    ]
    rows = []
    for i in range(n):
        row: dict = {
            "pnl": -12 if i % 3 == 0 else 18,
            "rr": -1 if i % 3 == 0 else 1.4,
            "hold_minutes": 10 + (i % 15),
        }
        if regime_cycle:
            row["regime"] = regimes[i % 8]
        rows.append(row)
    return rows


def test_hard_locks_read_only() -> None:
    status = InstitutionalValidationProgram().status()
    assert status["symbol"] == GOLD_SYMBOL
    assert status["allow_order_send"] is False
    assert status["allow_place_trades"] is False
    assert status["allow_auto_promote_research"] is False
    caps = status["capabilities"]
    assert caps["read_only"] is True
    assert caps["never_modify_risk_engine"] is True
    assert caps["never_modify_decision_engine"] is True
    assert len(status["modules"]) == 10


def test_policies_cannot_unlock() -> None:
    cfg = IvpConfig().update(
        {
            "allow_order_send": True,
            "allow_place_trades": True,
            "allow_modify_risk_engine": True,
            "allow_auto_promote_research": True,
        }
    )
    assert cfg.allow_order_send is False
    assert cfg.allow_place_trades is False
    assert cfg.allow_modify_risk_engine is False
    assert cfg.allow_auto_promote_research is False


def test_insufficient_evidence() -> None:
    out = InstitutionalValidationProgram().evaluate(
        IvpInput(completed_trades=_trades(5))
    )
    assert (
        out["modules"]["statistical_validation"]["recommendation"]
        == "INSUFFICIENT EVIDENCE"
    )
    assert out["never_order_send"] is True
    assert out["auto_promote_research"] is False


def test_full_validation_cycle() -> None:
    ivp = InstitutionalValidationProgram()
    out = ivp.evaluate(
        IvpInput(
            strategy_id="s1",
            configuration_id="c1",
            completed_trades=_trades(80, regime_cycle=True),
            configurations=[
                {"id": "c1", "trades": _trades(40)},
                {"id": "c2", "trades": _trades(35)},
            ],
            risk_facts={
                "capital_preservation": {"ok": True},
                "drawdown_behavior": {"max_dd": 3},
                "position_sizing_consistency": {"var": 0.1},
                "risk_rule_compliance": {"violations": 0},
            },
            replay_results={
                "expectancy": 4,
                "win_rate": 55,
                "profit_factor": 1.4,
                "drawdown": 3,
                "trade_count": 60,
            },
            paper_results={
                "expectancy": 2.5,
                "win_rate": 52,
                "profit_factor": 1.2,
                "drawdown": 4,
                "trade_count": 48,
            },
            history_event={"comments": "first run"},
        )
    )
    assert out["read_only"] is True
    assert out["modifies_risk_engine"] is False
    assert out["modules"]["statistical_validation"]["status"] == "available"
    assert out["modules"]["confidence_analysis"]["status"] == "available"
    assert out["modules"]["regime_validation"]["status"] == "available"
    assert out["modules"]["configuration_comparison"]["details"][
        "auto_selected_winner"
    ] is None
    assert out["modules"]["configuration_comparison"]["details"][
        "never_auto_selects_winner"
    ] is True
    assert out["modules"]["evidence_dashboard"]["status"] == "available"
    assert out["modules"]["human_decision_package"]["details"][
        "auto_deploy"
    ] is False
    assert out["modules"]["validation_history"]["details"][
        "append_only"
    ] is True
    assert len(ivp.history) == 1

    # Append-only: second eval grows history; first entry preserved
    first_id = ivp.history[0]["id"]
    ivp.evaluate(IvpInput(completed_trades=_trades(40), history_event={}))
    assert len(ivp.history) == 2
    assert any(h["id"] == first_id for h in ivp.history)


def test_no_deployment_without_evidence() -> None:
    out = InstitutionalValidationProgram().evaluate(IvpInput())
    hdp = out["modules"]["human_decision_package"]
    assert "NONE" in hdp["details"]["deployment_recommendation"]
    assert hdp["details"]["auto_deploy"] is False
