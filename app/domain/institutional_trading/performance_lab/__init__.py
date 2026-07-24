"""Live Performance Lab v8."""

from __future__ import annotations

from app.domain.institutional_trading.performance_lab.calibration import (
    get_calibration_store,
)
from app.domain.institutional_trading.performance_lab.champion_challenger import (
    evaluate_challenger,
    get_duel_store,
    run_champion_challenger,
)
from app.domain.institutional_trading.performance_lab.config import (
    DEFAULT_LAB_CONFIG,
    PerformanceLabConfig,
)
from app.domain.institutional_trading.performance_lab.heatmap import (
    get_portfolio_heatmap_store,
)
from app.domain.institutional_trading.performance_lab.lab_explain import (
    store_lab_explanation,
)
from app.domain.institutional_trading.performance_lab.opportunity_db import (
    get_opportunity_outcome_store,
)
from app.domain.institutional_trading.performance_lab.recommendations import (
    get_recommendation_engine,
)
from app.domain.institutional_trading.performance_lab.strategy_compare import (
    compare_strategies,
)
from app.domain.institutional_trading.performance_lab.symbol_intelligence import (
    build_symbol_rankings,
)
from app.domain.institutional_trading.performance_lab.trade_replay import (
    build_replay_from_decision,
    get_trade_replay_store,
)

__all__ = [
    "DEFAULT_LAB_CONFIG",
    "PerformanceLabConfig",
    "build_replay_from_decision",
    "build_symbol_rankings",
    "compare_strategies",
    "evaluate_challenger",
    "get_calibration_store",
    "get_duel_store",
    "get_opportunity_outcome_store",
    "get_portfolio_heatmap_store",
    "get_recommendation_engine",
    "get_trade_replay_store",
    "run_champion_challenger",
    "store_lab_explanation",
]
