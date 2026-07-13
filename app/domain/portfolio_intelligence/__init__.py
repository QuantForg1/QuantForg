"""Portfolio Intelligence package — deterministic risk laboratory math."""

from __future__ import annotations

from app.domain.portfolio_intelligence.attribution import attribute_returns
from app.domain.portfolio_intelligence.journal import analyze_trades
from app.domain.portfolio_intelligence.optimizer import optimize_allocations
from app.domain.portfolio_intelligence.statistics import (
    cluster_labels,
    correlation_matrix,
    diversification_score,
    expected_shortfall,
    herfindahl,
    historical_var,
)
from app.domain.portfolio_intelligence.stress import (
    MODEL_SCENARIOS,
    PositionShockInput,
    apply_model_scenario,
    historical_from_deals,
)
from app.domain.portfolio_intelligence.taxonomy import (
    classify_currency,
    classify_sector,
)

__all__ = [
    "MODEL_SCENARIOS",
    "PositionShockInput",
    "analyze_trades",
    "apply_model_scenario",
    "attribute_returns",
    "classify_currency",
    "classify_sector",
    "cluster_labels",
    "correlation_matrix",
    "diversification_score",
    "expected_shortfall",
    "herfindahl",
    "historical_from_deals",
    "historical_var",
    "optimize_allocations",
]
