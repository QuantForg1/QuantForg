"""Portfolio Intelligence Engine — orchestrates portfolio-aware evaluation."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.portfolio_intelligence.allocation import (
    allocate_capital,
)
from app.domain.institutional_trading.portfolio_intelligence.capital_protection import (
    evaluate_capital_protection,
)
from app.domain.institutional_trading.portfolio_intelligence.config import (
    DEFAULT_PI_CONFIG,
)
from app.domain.institutional_trading.portfolio_intelligence.explainability import (
    get_portfolio_explain_store,
)
from app.domain.institutional_trading.portfolio_intelligence.optimizer import (
    optimize_portfolio,
)
from app.domain.institutional_trading.portfolio_intelligence.queue import (
    get_opportunity_queue,
)
from app.domain.institutional_trading.portfolio_intelligence.recommendations import (
    get_portfolio_recommendation_engine,
)
from app.domain.institutional_trading.portfolio_intelligence.regime import (
    detect_global_regime,
)
from app.domain.institutional_trading.portfolio_intelligence.risk_budget import (
    get_dynamic_risk_budget,
)
from app.domain.institutional_trading.portfolio_intelligence.state import (
    PortfolioState,
    build_portfolio_state,
)
from app.domain.institutional_trading.portfolio_intelligence.stress import (
    run_stress_tests,
)
from app.domain.institutional_trading.portfolio_intelligence.analytics import (
    get_long_term_analytics,
)
from core.logging import get_logger

logger = get_logger(__name__)


def evaluate_portfolio(
    *,
    opportunities: list[dict[str, Any]],
    state: PortfolioState | None = None,
    equity: float | None = None,
    free_margin: float | None = None,
    open_symbols: list[str] | None = None,
    exposure_by_symbol: dict[str, float] | None = None,
    daily_pnl: float | None = None,
    weekly_pnl: float | None = None,
    monthly_pnl: float | None = None,
    current_drawdown_pct: float | None = None,
    portfolio_volatility: float | None = None,
    correlation_matrix: dict[str, Any] | None = None,
    session: str | None = None,
    execution_quality_score: float | None = None,
    candidate_symbol: str | None = None,
) -> dict[str, Any]:
    """Full portfolio pass — never evaluates a symbol in isolation."""
    st = state or build_portfolio_state(
        equity=equity,
        free_margin=free_margin,
        open_symbols=open_symbols,
        exposure_by_symbol=exposure_by_symbol,
        daily_pnl=daily_pnl,
        weekly_pnl=weekly_pnl,
        monthly_pnl=monthly_pnl,
        current_drawdown_pct=current_drawdown_pct,
        portfolio_volatility=portfolio_volatility,
        correlation_matrix=correlation_matrix,
        session=session,
    )

    get_long_term_analytics().record_equity(st.equity)

    budget = get_dynamic_risk_budget().budget_for_state(st)
    protection = evaluate_capital_protection(
        st, candidate_symbol=candidate_symbol
    )
    allocation = allocate_capital(
        opportunities,
        st,
        risk_budget_pct=float(budget["risk_budget_pct"]),
        new_exposure_scale=protection.new_exposure_scale,
    )
    optimization = optimize_portfolio(
        state=st,
        allocation=allocation,
        execution_quality_score=execution_quality_score,
    )
    regime = detect_global_regime(
        portfolio_volatility=st.portfolio_volatility,
        daily_pnl=st.daily_pnl,
        equity=st.equity,
    )
    stress = run_stress_tests(st)
    queue = get_opportunity_queue().rebuild(
        opportunities, st, risk_budget_pct=float(budget["risk_budget_pct"])
    )
    explanations = get_portfolio_explain_store().record_allocation(allocation)
    recs = get_portfolio_recommendation_engine().generate(
        allocation=allocation,
        optimization=optimization,
        protection=protection.to_dict(),
        regime=regime.to_dict(),
        risk_budget_pct=float(budget["risk_budget_pct"]),
    )

    health = "healthy"
    if not protection.allow_new_exposure:
        health = "protected"
    elif protection.new_exposure_scale < 0.75:
        health = "caution"
    elif float(optimization.get("correlation") or 0) >= 0.6:
        health = "elevated_correlation"

    logger.info(
        "portfolio_intelligence_evaluated",
        score=optimization.get("portfolio_score"),
        budget=budget.get("risk_budget_pct"),
        health=health,
        auto_reallocate=False,
    )

    return {
        "version": DEFAULT_PI_CONFIG.version,
        "portfolio_state": st.to_dict(),
        "portfolio_score": optimization.get("portfolio_score"),
        "risk_budget": budget,
        "capital_allocation": allocation,
        "expected_return": optimization.get("expected_return"),
        "expected_drawdown": optimization.get("expected_drawdown"),
        "optimization": optimization,
        "capital_protection": protection.to_dict(),
        "opportunity_queue": {
            "count": len(queue),
            "items": [q.to_dict() for q in queue],
        },
        "exposure_map": st.exposure_by_symbol,
        "correlation_matrix": st.correlation_matrix,
        "stress_test": stress,
        "market_regime": regime.to_dict(),
        "portfolio_health": health,
        "explanations": [e.to_dict() for e in explanations],
        "recommendations": [r.to_dict() for r in recs],
        "long_term_analytics": get_long_term_analytics().snapshot(),
        "safeguards": {
            "auto_reallocate": False,
            "recommendations_auto_applied": False,
            "martingale": False,
            "grid": False,
        },
    }
