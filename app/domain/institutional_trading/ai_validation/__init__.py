"""AI Validation & Performance Optimization v7."""

from __future__ import annotations

from app.domain.institutional_trading.ai_validation.alerts import get_validation_alerter
from app.domain.institutional_trading.ai_validation.benchmarks import (
    estimate_buy_hold_return,
    estimate_sma_crossover_return,
    get_benchmark_store,
)
from app.domain.institutional_trading.ai_validation.config import (
    DEFAULT_AI_VALIDATION_CONFIG,
    AiValidationConfig,
)
from app.domain.institutional_trading.ai_validation.execution_quality import (
    get_execution_quality_monitor,
)
from app.domain.institutional_trading.ai_validation.opportunity_history import (
    get_opportunity_history_store,
)
from app.domain.institutional_trading.ai_validation.portfolio import (
    get_portfolio_analytics_store,
)
from app.domain.institutional_trading.ai_validation.shadow_ai import (
    compare_primary_shadow,
    evaluate_shadow,
    get_shadow_store,
    run_shadow_validation,
)
from app.domain.institutional_trading.ai_validation.slippage import (
    compute_entry_slippage,
    get_slippage_store,
)
from app.domain.institutional_trading.ai_validation.strategy_performance import (
    get_strategy_performance_store,
)
from app.domain.institutional_trading.ai_validation.weight_optimizer import (
    get_weight_optimizer,
)

__all__ = [
    "AiValidationConfig",
    "DEFAULT_AI_VALIDATION_CONFIG",
    "compare_primary_shadow",
    "compute_entry_slippage",
    "estimate_buy_hold_return",
    "estimate_sma_crossover_return",
    "evaluate_shadow",
    "get_benchmark_store",
    "get_execution_quality_monitor",
    "get_opportunity_history_store",
    "get_portfolio_analytics_store",
    "get_shadow_store",
    "get_slippage_store",
    "get_strategy_performance_store",
    "get_validation_alerter",
    "get_weight_optimizer",
    "run_shadow_validation",
]
