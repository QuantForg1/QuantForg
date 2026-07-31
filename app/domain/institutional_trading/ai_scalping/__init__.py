"""Institutional AI Scalping Engine — extends ITE without replacing OMS/Risk."""

from __future__ import annotations

from app.domain.institutional_trading.ai_scalping.adaptive_cooldown import (
    AdaptiveCooldownDecision,
    AdaptiveCooldownGate,
    get_adaptive_cooldown_gate,
    resolve_adaptive_cooldown_seconds,
)
from app.domain.institutional_trading.ai_scalping.adaptive_thresholds import (
    ResolvedThresholds,
    apply_thresholds_to_ite,
    classify_volatility_band,
    resolve_adaptive_thresholds,
)
from app.domain.institutional_trading.ai_scalping.broker_profile_store import (
    BrokerProfileStore,
    BrokerRuntimeProfile,
    get_broker_profile_store,
)
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    DEFAULT_SCALPING_UNIVERSE,
    AdaptiveThresholdBand,
    AiScalpingConfig,
    SetupFamily,
    scalping_ite_config,
)
from app.domain.institutional_trading.ai_scalping.continuous_operation import (
    ContinuousOperationController,
    ContinuousOpSnapshot,
    NewEntryPauseDecision,
    get_continuous_operation_controller,
)
from app.domain.institutional_trading.ai_scalping.correlation_book import (
    PORTFOLIO_CORRELATION_GROUPS,
    correlation_group_members,
    correlation_group_name,
    currency_for,
    normalize_book_symbol,
    sector_for,
)
from app.domain.institutional_trading.ai_scalping.diagnostics import (
    get_scalping_diagnostics_store,
)
from app.domain.institutional_trading.ai_scalping.direction import (
    DirectionDecision,
    decide_scalping_direction,
)
from app.domain.institutional_trading.ai_scalping.duplicate_guard import (
    AddTradeDecision,
    may_add_scalping_trade,
)
from app.domain.institutional_trading.ai_scalping.dynamic_sizing_v2 import (
    DynamicSizingDecision,
    EquityTierPreference,
    calculate_dynamic_lots_v2,
    check_portfolio_sizing_limits,
    classify_quality_band,
    interpolate_equity_tier,
)
from app.domain.institutional_trading.ai_scalping.execution_quality import (
    ExecutionQualityStore,
    get_execution_quality_store,
)
from app.domain.institutional_trading.ai_scalping.learning import (
    LearningTradeRecord,
    ScalpingLearningStore,
    get_scalping_learning_store,
)
from app.domain.institutional_trading.ai_scalping.live_health import (
    LiveHealthMonitor,
    get_live_health_monitor,
)
from app.domain.institutional_trading.ai_scalping.multi_symbol import (
    rank_scalping_opportunities,
)
from app.domain.institutional_trading.ai_scalping.pa_confluence import (
    PaConfluenceResult,
    evaluate_pa_confluence,
)
from app.domain.institutional_trading.ai_scalping.portfolio_risk import (
    PortfolioRiskSnapshot,
    aggregate_portfolio_risk,
    portfolio_daily_loss_pct,
    portfolio_exposure_pct,
)
from app.domain.institutional_trading.ai_scalping.portfolio_risk_engine_v2 import (
    BrokerComplianceSpec,
    PortfolioAllocationDecision,
    PortfolioBookSnapshot,
    build_portfolio_book,
    evaluate_portfolio_allocation,
)
from app.domain.institutional_trading.ai_scalping.portfolio_scanner import (
    PortfolioScanResult,
    check_portfolio_limits,
    scan_multi_asset_portfolio,
)
from app.domain.institutional_trading.ai_scalping.portfolio_scheduler import (
    MultiAssetScanScheduler,
    get_multi_asset_scheduler,
)
from app.domain.institutional_trading.ai_scalping.post_trade_analytics import (
    PostTradeAnalytics,
    PostTradeJournal,
    compute_post_trade_analytics,
    get_post_trade_journal,
)
from app.domain.institutional_trading.ai_scalping.quality_gates import (
    QualityGateResult,
    evaluate_quality_gates,
)
from app.domain.institutional_trading.ai_scalping.regime import (
    RegimeAssessment,
    classify_scalping_regime,
)
from app.domain.institutional_trading.ai_scalping.regime_execution import (
    RegimeExecutionProfile,
    build_regime_execution_profile,
)
from app.domain.institutional_trading.ai_scalping.scoring import (
    AiScalpingScore,
    score_scalping_setup,
)
from app.domain.institutional_trading.ai_scalping.session_intelligence import (
    SessionAssessment,
    assess_session,
)
from app.domain.institutional_trading.ai_scalping.setup_scanner import (
    SetupCandidate,
    SetupScanResult,
    scan_setup_families,
)
from app.domain.institutional_trading.ai_scalping.sizing import (
    LotSizingResult,
    calculate_scalping_lots,
)
from app.domain.institutional_trading.ai_scalping.volatility_gate_v2 import (
    VolatilityDecision,
    evaluate_volatility_gate_v1_compat,
    evaluate_volatility_gate_v2,
)
from app.domain.institutional_trading.ai_scalping.slippage_protection import (
    SlippageAssessment,
    measure_slippage,
)
from app.domain.institutional_trading.ai_scalping.spread_intelligence import (
    SpreadAssessment,
    assess_spread,
)
from app.domain.institutional_trading.ai_scalping.structure_targets import (
    StructureTargets,
    compute_structure_targets,
)
from app.domain.institutional_trading.ai_scalping.symbol_state import (
    SymbolExecutionState,
    SymbolStateBook,
    get_symbol_state_book,
)
from app.domain.institutional_trading.ai_scalping.validation import (
    compare_backtest_vs_live,
)

__all__ = [
    "DEFAULT_AI_SCALPING_CONFIG",
    "DEFAULT_SCALPING_UNIVERSE",
    "PORTFOLIO_CORRELATION_GROUPS",
    "AdaptiveCooldownDecision",
    "AdaptiveCooldownGate",
    "AdaptiveThresholdBand",
    "AddTradeDecision",
    "AiScalpingConfig",
    "AiScalpingScore",
    "BrokerComplianceSpec",
    "BrokerProfileStore",
    "BrokerRuntimeProfile",
    "ContinuousOpSnapshot",
    "ContinuousOperationController",
    "DirectionDecision",
    "DynamicSizingDecision",
    "EquityTierPreference",
    "ExecutionQualityStore",
    "LearningTradeRecord",
    "LiveHealthMonitor",
    "LotSizingResult",
    "MultiAssetScanScheduler",
    "NewEntryPauseDecision",
    "PaConfluenceResult",
    "PortfolioAllocationDecision",
    "PortfolioBookSnapshot",
    "PortfolioRiskSnapshot",
    "PortfolioScanResult",
    "PostTradeAnalytics",
    "PostTradeJournal",
    "QualityGateResult",
    "RegimeAssessment",
    "RegimeExecutionProfile",
    "ResolvedThresholds",
    "ScalpingLearningStore",
    "SessionAssessment",
    "SetupCandidate",
    "SetupFamily",
    "SetupScanResult",
    "SlippageAssessment",
    "SpreadAssessment",
    "StructureTargets",
    "SymbolExecutionState",
    "SymbolStateBook",
    "VolatilityDecision",
    "aggregate_portfolio_risk",
    "apply_thresholds_to_ite",
    "assess_session",
    "assess_spread",
    "build_portfolio_book",
    "build_regime_execution_profile",
    "calculate_dynamic_lots_v2",
    "calculate_scalping_lots",
    "check_portfolio_limits",
    "check_portfolio_sizing_limits",
    "classify_quality_band",
    "classify_scalping_regime",
    "classify_volatility_band",
    "compare_backtest_vs_live",
    "compute_post_trade_analytics",
    "compute_structure_targets",
    "correlation_group_members",
    "correlation_group_name",
    "currency_for",
    "decide_scalping_direction",
    "evaluate_pa_confluence",
    "evaluate_portfolio_allocation",
    "evaluate_quality_gates",
    "evaluate_volatility_gate_v1_compat",
    "evaluate_volatility_gate_v2",
    "get_adaptive_cooldown_gate",
    "get_broker_profile_store",
    "get_continuous_operation_controller",
    "get_execution_quality_store",
    "get_live_health_monitor",
    "get_multi_asset_scheduler",
    "get_post_trade_journal",
    "get_scalping_diagnostics_store",
    "get_scalping_learning_store",
    "get_symbol_state_book",
    "interpolate_equity_tier",
    "may_add_scalping_trade",
    "measure_slippage",
    "normalize_book_symbol",
    "portfolio_daily_loss_pct",
    "portfolio_exposure_pct",
    "rank_scalping_opportunities",
    "resolve_adaptive_cooldown_seconds",
    "resolve_adaptive_thresholds",
    "scalping_ite_config",
    "scan_multi_asset_portfolio",
    "scan_setup_families",
    "score_scalping_setup",
    "sector_for",
]
