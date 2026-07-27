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
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    DEFAULT_SCALPING_UNIVERSE,
    AdaptiveThresholdBand,
    AiScalpingConfig,
    SetupFamily,
    scalping_ite_config,
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
from app.domain.institutional_trading.ai_scalping.validation import (
    compare_backtest_vs_live,
)

__all__ = [
    "DEFAULT_AI_SCALPING_CONFIG",
    "DEFAULT_SCALPING_UNIVERSE",
    "AdaptiveCooldownDecision",
    "AdaptiveCooldownGate",
    "AdaptiveThresholdBand",
    "AddTradeDecision",
    "AiScalpingConfig",
    "AiScalpingScore",
    "DirectionDecision",
    "ExecutionQualityStore",
    "LearningTradeRecord",
    "LiveHealthMonitor",
    "LotSizingResult",
    "PaConfluenceResult",
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
    "apply_thresholds_to_ite",
    "assess_session",
    "assess_spread",
    "build_regime_execution_profile",
    "calculate_scalping_lots",
    "classify_scalping_regime",
    "classify_volatility_band",
    "compare_backtest_vs_live",
    "compute_post_trade_analytics",
    "compute_structure_targets",
    "decide_scalping_direction",
    "evaluate_pa_confluence",
    "evaluate_quality_gates",
    "get_adaptive_cooldown_gate",
    "get_execution_quality_store",
    "get_live_health_monitor",
    "get_post_trade_journal",
    "get_scalping_diagnostics_store",
    "get_scalping_learning_store",
    "may_add_scalping_trade",
    "measure_slippage",
    "rank_scalping_opportunities",
    "resolve_adaptive_cooldown_seconds",
    "resolve_adaptive_thresholds",
    "scalping_ite_config",
    "scan_setup_families",
    "score_scalping_setup",
]
