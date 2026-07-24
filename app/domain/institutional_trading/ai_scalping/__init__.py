"""Institutional AI Scalping Engine — extends ITE without replacing OMS/Risk."""

from __future__ import annotations

from app.domain.institutional_trading.ai_scalping.adaptive_thresholds import (
    ResolvedThresholds,
    apply_thresholds_to_ite,
    classify_volatility_band,
    resolve_adaptive_thresholds,
)
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
    AdaptiveThresholdBand,
    scalping_ite_config,
)
from app.domain.institutional_trading.ai_scalping.duplicate_guard import (
    AddTradeDecision,
    may_add_scalping_trade,
)
from app.domain.institutional_trading.ai_scalping.learning import (
    LearningTradeRecord,
    ScalpingLearningStore,
    get_scalping_learning_store,
)
from app.domain.institutional_trading.ai_scalping.regime import (
    RegimeAssessment,
    classify_scalping_regime,
)
from app.domain.institutional_trading.ai_scalping.scoring import (
    AiScalpingScore,
    score_scalping_setup,
)
from app.domain.institutional_trading.ai_scalping.session_intelligence import (
    SessionAssessment,
    assess_session,
)
from app.domain.institutional_trading.ai_scalping.sizing import (
    LotSizingResult,
    calculate_scalping_lots,
)
from app.domain.institutional_trading.ai_scalping.spread_intelligence import (
    SpreadAssessment,
    assess_spread,
)

__all__ = [
    "DEFAULT_AI_SCALPING_CONFIG",
    "AdaptiveThresholdBand",
    "AddTradeDecision",
    "AiScalpingConfig",
    "AiScalpingScore",
    "LearningTradeRecord",
    "LotSizingResult",
    "RegimeAssessment",
    "ResolvedThresholds",
    "ScalpingLearningStore",
    "SessionAssessment",
    "SpreadAssessment",
    "apply_thresholds_to_ite",
    "assess_session",
    "assess_spread",
    "calculate_scalping_lots",
    "classify_scalping_regime",
    "classify_volatility_band",
    "get_scalping_learning_store",
    "may_add_scalping_trade",
    "resolve_adaptive_thresholds",
    "scalping_ite_config",
    "score_scalping_setup",
]
