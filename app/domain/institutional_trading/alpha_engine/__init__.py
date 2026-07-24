"""Institutional Alpha Engine — public exports."""

from __future__ import annotations

from app.domain.institutional_trading.alpha_engine.analytics import (
    AlphaAnalyticsStore,
    AlphaTradeAnalyticsRow,
    get_alpha_analytics_store,
)
from app.domain.institutional_trading.alpha_engine.config import (
    DEFAULT_ALPHA_CONFIG,
    DEFAULT_ALPHA_UNIVERSE,
    DEFAULT_CORRELATION_GROUPS,
    InstitutionalAlphaConfig,
)
from app.domain.institutional_trading.alpha_engine.correlation import (
    CorrelationDecision,
    correlation_matrix,
    may_open_with_correlation,
)
from app.domain.institutional_trading.alpha_engine.position_ai import (
    AiManageHints,
    plan_ai_position_action,
)
from app.domain.institutional_trading.alpha_engine.ranking import (
    SymbolOpportunity,
    rank_opportunities,
    score_opportunity,
    top_executable,
)
from app.domain.institutional_trading.alpha_engine.risk_allocation import (
    RiskAllocation,
    SmartRecoveryState,
    allocate_risk_pct,
    get_smart_recovery,
    min_score_with_recovery,
)
from app.domain.institutional_trading.alpha_engine.scanner import (
    AlphaScanResult,
    SymbolMarketFacts,
    scan_universe,
)

__all__ = [
    "DEFAULT_ALPHA_CONFIG",
    "DEFAULT_ALPHA_UNIVERSE",
    "DEFAULT_CORRELATION_GROUPS",
    "AiManageHints",
    "AlphaAnalyticsStore",
    "AlphaScanResult",
    "AlphaTradeAnalyticsRow",
    "CorrelationDecision",
    "InstitutionalAlphaConfig",
    "RiskAllocation",
    "SmartRecoveryState",
    "SymbolMarketFacts",
    "SymbolOpportunity",
    "allocate_risk_pct",
    "correlation_matrix",
    "get_alpha_analytics_store",
    "get_smart_recovery",
    "may_open_with_correlation",
    "min_score_with_recovery",
    "plan_ai_position_action",
    "rank_opportunities",
    "scan_universe",
    "score_opportunity",
    "top_executable",
]
