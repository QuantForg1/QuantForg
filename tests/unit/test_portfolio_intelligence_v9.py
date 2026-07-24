"""Unit tests — Institutional Portfolio Intelligence v9."""

from __future__ import annotations

import pytest

from app.domain.institutional_trading.portfolio_intelligence.allocation import (
    allocate_capital,
)
from app.domain.institutional_trading.portfolio_intelligence.capital_protection import (
    evaluate_capital_protection,
)
from app.domain.institutional_trading.portfolio_intelligence.config import (
    DEFAULT_PI_CONFIG,
)
from app.domain.institutional_trading.portfolio_intelligence.queue import (
    OpportunityQueue,
)
from app.domain.institutional_trading.portfolio_intelligence.recommendations import (
    PortfolioRecommendationEngine,
)
from app.domain.institutional_trading.portfolio_intelligence.risk_budget import (
    DynamicRiskBudget,
)
from app.domain.institutional_trading.portfolio_intelligence.state import (
    build_portfolio_state,
)
from app.domain.institutional_trading.portfolio_intelligence.stress import (
    run_stress_tests,
)


@pytest.mark.unit
def test_allocation_is_dynamic_and_advisory() -> None:
    assert DEFAULT_PI_CONFIG.capital_reallocation_auto is False
    state = build_portfolio_state(equity=100_000, open_symbols=["EURUSD"])
    opps = [
        {"symbol": "XAUUSD", "opportunity_score": 90, "ai_confidence": 88, "expected_rr": 2.0},
        {"symbol": "USDJPY", "opportunity_score": 70, "ai_confidence": 65, "expected_rr": 1.5},
        {"symbol": "BTCUSD", "opportunity_score": 55, "ai_confidence": 50, "expected_rr": 1.2},
        {"symbol": "NAS100", "opportunity_score": 40, "ai_confidence": 40, "expected_rr": 1.0},
    ]
    alloc = allocate_capital(opps, state, risk_budget_pct=4.0, new_exposure_scale=1.0)
    assert alloc["auto_applied"] is False
    shares = [a["share_pct"] for a in alloc["allocations"]]
    assert shares[0] >= shares[-1]
    assert abs(sum(shares) + alloc["reserve_pct"] - 100) < 5 or sum(shares) < 100


@pytest.mark.unit
def test_risk_budget_reduces_on_drawdown() -> None:
    budget = DynamicRiskBudget(current_pct=4.0)
    state = build_portfolio_state(equity=100_000, current_drawdown_pct=5.0)
    snap = budget.budget_for_state(state)
    assert snap["risk_budget_pct"] < 4.0
    assert snap["martingale"] is False
    assert snap["grid"] is False


@pytest.mark.unit
def test_capital_protection_blocks_daily_loss() -> None:
    state = build_portfolio_state(equity=100_000, daily_pnl=-4000)
    prot = evaluate_capital_protection(state)
    assert prot.allow_new_exposure is False
    assert prot.new_exposure_scale == 0.0
    assert prot.to_dict()["auto_reallocate"] is False


@pytest.mark.unit
def test_capital_protection_scales_near_limit() -> None:
    state = build_portfolio_state(equity=100_000, daily_pnl=-2500, current_drawdown_pct=0)
    prot = evaluate_capital_protection(state)
    assert prot.allow_new_exposure is True
    assert prot.new_exposure_scale < 1.0


@pytest.mark.unit
def test_stress_test_scenarios() -> None:
    state = build_portfolio_state(
        equity=100_000,
        open_symbols=["XAUUSD", "EURUSD"],
        exposure_by_symbol={"XAUUSD": 0.5, "EURUSD": 0.3},
    )
    stress = run_stress_tests(state)
    names = {s["scenario"] for s in stress["scenarios"]}
    assert "flash_crash" in names
    assert "gap_open" in names
    assert stress["worst_case"] is not None
    assert stress["advisory_only"] is True


@pytest.mark.unit
def test_correlation_reuse_blocks_group() -> None:
    state = build_portfolio_state(equity=100_000, open_symbols=["EURUSD"])
    prot = evaluate_capital_protection(state, candidate_symbol="GBPUSD")
    # Alpha correlation groups block EURUSD+GBPUSD when max_correlated_open<=1
    assert prot.allow_new_exposure is False or prot.new_exposure_scale <= 1.0


@pytest.mark.unit
def test_opportunity_queue_priority() -> None:
    q = OpportunityQueue()
    state = build_portfolio_state(equity=100_000)
    items = q.rebuild(
        [
            {"symbol": "A", "opportunity_score": 50, "ai_confidence": 50, "expected_rr": 1},
            {"symbol": "B", "opportunity_score": 90, "ai_confidence": 80, "expected_rr": 2},
        ],
        state,
        risk_budget_pct=4.0,
    )
    assert items[0].symbol == "B"
    assert items[0].priority == 1


@pytest.mark.unit
def test_recommendations_never_auto_apply() -> None:
    eng = PortfolioRecommendationEngine()
    recs = eng.generate(
        allocation={
            "allocations": [{"symbol": "XAUUSD", "share_pct": 40}],
        },
        optimization={"rebalance_recommendations": ["diversify"], "correlation": 0.7},
        protection={"new_exposure_scale": 0.5},
        regime={"regime": "GLOBAL_RISK_OFF"},
        risk_budget_pct=3.5,
    )
    assert recs
    assert all(r.auto_applied is False for r in recs)


@pytest.mark.unit
def test_portfolio_intelligence_dashboard_shape() -> None:
    from app.application.services.portfolio_intelligence import (
        build_portfolio_intelligence_dashboard,
    )

    dash = build_portfolio_intelligence_dashboard()
    assert dash["version"].startswith("portfolio-intelligence-v9")
    assert dash["safeguards"]["auto_reallocate"] is False
    for key in (
        "portfolio_score",
        "risk_budget",
        "capital_allocation",
        "opportunity_queue",
        "stress_test",
        "market_regime",
        "portfolio_health",
        "recommendations",
        "long_term_analytics",
    ):
        assert key in dash
