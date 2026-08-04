"""Multi-strategy scalping pack — production strategies on shared Trading Core."""

from __future__ import annotations

from app.domain.institutional_trading.ai_scalping.strategies.evaluate import (
    evaluate_all_strategies,
    evaluate_strategy,
)
from app.domain.institutional_trading.ai_scalping.strategies.models import (
    StrategyDefinition,
    StrategyEvaluation,
    StrategyId,
)
from app.domain.institutional_trading.ai_scalping.strategies.registry import (
    ALL_STRATEGIES,
    BREAKOUT_SCALPING,
    MOMENTUM_SCALPING,
    RANGE_MEAN_REVERSION,
    SMC_SCALPING,
    STRATEGY_BY_ID,
    TREND_CONTINUATION,
    list_strategy_ids,
)
from app.domain.institutional_trading.ai_scalping.strategies.select import (
    attach_strategies_to_scores,
    best_strategy_for_symbol,
    select_global_best,
)
from app.domain.institutional_trading.ai_scalping.strategies.stats import (
    StrategyStatsBook,
    get_strategy_stats_book,
)

__all__ = [
    "ALL_STRATEGIES",
    "BREAKOUT_SCALPING",
    "MOMENTUM_SCALPING",
    "RANGE_MEAN_REVERSION",
    "SMC_SCALPING",
    "STRATEGY_BY_ID",
    "StrategyDefinition",
    "StrategyEvaluation",
    "StrategyId",
    "StrategyStatsBook",
    "TREND_CONTINUATION",
    "attach_strategies_to_scores",
    "best_strategy_for_symbol",
    "evaluate_all_strategies",
    "evaluate_strategy",
    "get_strategy_stats_book",
    "list_strategy_ids",
    "select_global_best",
]
