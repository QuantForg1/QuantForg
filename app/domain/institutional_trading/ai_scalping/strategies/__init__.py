"""Multi-strategy scalping pack — production strategies on shared Trading Core."""

from __future__ import annotations

from app.domain.institutional_trading.ai_scalping.strategies.advisory_collaboration import (  # noqa: E501
    AdvisoryVote,
    collect_score_factor_advisory_votes,
    summarize_advisory_agreement,
)
from app.domain.institutional_trading.ai_scalping.strategies.evaluate import (
    evaluate_all_strategies,
    evaluate_strategy,
)
from app.domain.institutional_trading.ai_scalping.strategies.live_eligibility import (
    eligibility_snapshot,
    list_eligibility,
    live_executable_ids,
)
from app.domain.institutional_trading.ai_scalping.strategies.models import (
    StrategyDefinition,
    StrategyEvaluation,
    StrategyId,
)
from app.domain.institutional_trading.ai_scalping.strategies.monitoring import (
    build_strategy_performance_monitor,
)
from app.domain.institutional_trading.ai_scalping.strategies.orchestrator import (
    ORCHESTRATION_VERSION,
    OrchestrationVerdict,
    catalog_participation_policy,
    orchestrate_strategies,
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
    "ORCHESTRATION_VERSION",
    "RANGE_MEAN_REVERSION",
    "SMC_SCALPING",
    "STRATEGY_BY_ID",
    "TREND_CONTINUATION",
    "AdvisoryVote",
    "OrchestrationVerdict",
    "StrategyDefinition",
    "StrategyEvaluation",
    "StrategyId",
    "StrategyStatsBook",
    "attach_strategies_to_scores",
    "best_strategy_for_symbol",
    "build_strategy_performance_monitor",
    "catalog_participation_policy",
    "collect_score_factor_advisory_votes",
    "eligibility_snapshot",
    "evaluate_all_strategies",
    "evaluate_strategy",
    "get_strategy_stats_book",
    "list_eligibility",
    "list_strategy_ids",
    "live_executable_ids",
    "orchestrate_strategies",
    "select_global_best",
    "summarize_advisory_agreement",
]
