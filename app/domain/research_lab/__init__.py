"""Quant Research Lab domain package."""

from __future__ import annotations

from app.domain.research_lab.comparison import (
    compare_strategies,
    pick_dashboard_leaders,
)
from app.domain.research_lab.library import get_strategy, list_strategy_library
from app.domain.research_lab.parameter_lab import (
    PRODUCTION_DEFAULTS,
    sandbox_parameters,
    to_backtest_assumptions,
)
from app.domain.research_lab.regime import classify_regime, strategy_regime_fit
from app.domain.research_lab.reports import build_research_report
from app.domain.research_lab.store import get_research_store

__all__ = [
    "PRODUCTION_DEFAULTS",
    "build_research_report",
    "classify_regime",
    "compare_strategies",
    "get_research_store",
    "get_strategy",
    "list_strategy_library",
    "pick_dashboard_leaders",
    "sandbox_parameters",
    "strategy_regime_fit",
    "to_backtest_assumptions",
]
