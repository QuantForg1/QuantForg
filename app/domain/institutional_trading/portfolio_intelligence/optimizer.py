"""Portfolio optimizer — continuous rebalance *recommendations* only."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.portfolio_intelligence.state import PortfolioState


def optimize_portfolio(
    *,
    state: PortfolioState,
    allocation: dict[str, Any],
    execution_quality_score: float | None = None,
) -> dict[str, Any]:
    """Score expected return vs risk/correlation/drawdown/margin/execution."""
    allocs = allocation.get("allocations") or []
    if not allocs:
        expected_return = 0.0
    else:
        expected_return = sum(
            float(a.get("share_pct") or 0)
            / 100.0
            * float(a.get("expected_rr") or 0)
            * (float(a.get("opportunity_score") or 0) / 100.0)
            for a in allocs
        )

    corr_heat = 0.0
    for a in allocs:
        corr_heat = max(corr_heat, float(a.get("correlation_penalty") or 0))

    margin_usage = 0.0
    if state.equity > 0:
        margin_usage = state.used_margin / state.equity

    exec_q = float(execution_quality_score) if execution_quality_score is not None else 0.7
    # Higher is better composite 0–100
    score = (
        25 * min(1.0, expected_return / 2.0)
        + 20 * (1.0 - min(1.0, state.current_drawdown_pct / 10.0))
        + 20 * (1.0 - corr_heat)
        + 15 * (1.0 - min(1.0, margin_usage))
        + 10 * min(1.0, max(0.0, exec_q))
        + 10 * (1.0 - min(1.0, state.portfolio_volatility / 5.0))
    )
    recommendations: list[str] = []
    if corr_heat >= 0.6:
        recommendations.append("Current portfolio correlation is high — diversify.")
    if state.current_drawdown_pct >= 3:
        recommendations.append("Reduce risk until drawdown recovers.")
    if margin_usage >= 0.5:
        recommendations.append("Margin usage elevated — prefer fewer concurrent legs.")
    if expected_return < 0.3:
        recommendations.append("Expected return weak relative to risk — wait for higher-quality queue.")

    return {
        "portfolio_score": round(score, 2),
        "expected_return": round(expected_return, 4),
        "expected_drawdown": round(max(state.current_drawdown_pct, corr_heat * 5), 3),
        "risk": round(state.current_drawdown_pct + state.portfolio_volatility, 3),
        "correlation": round(corr_heat, 3),
        "drawdown": state.current_drawdown_pct,
        "margin_usage": round(margin_usage, 4),
        "execution_quality": exec_q,
        "rebalance_recommendations": recommendations,
        "auto_applied": False,
    }
