"""Phase 4 — AI Trading Intelligence (advisory product layer).

Assembles existing market/regime/scoring engines into explainable DTOs.
Never calls order_send. Never increases risk. Supervisor defaults MONITOR_ONLY.
"""

from app.domain.ai_trading_intelligence.adaptive import (
    AdaptiveProposal,
    AdaptiveProposalStore,
    get_adaptive_store,
    propose_adaptation,
)
from app.domain.ai_trading_intelligence.market_intelligence import (
    MarketIntelligenceBundle,
    assemble_market_intelligence,
)
from app.domain.ai_trading_intelligence.optimizer import (
    OptimizationResult,
    run_optimization_orchestrator,
)
from app.domain.ai_trading_intelligence.regime import (
    CanonicalRegime,
    RegimeAssessment,
    map_canonical_regime,
)
from app.domain.ai_trading_intelligence.risk_alerts import (
    AiRiskAlert,
    build_ai_risk_alerts,
)
from app.domain.ai_trading_intelligence.signal_quality import (
    SignalQualityScore,
    score_signal_quality,
)
from app.domain.ai_trading_intelligence.supervisor import (
    SupervisorMode,
    SupervisorState,
    get_supervisor,
)

__all__ = [
    "AdaptiveProposal",
    "AdaptiveProposalStore",
    "AiRiskAlert",
    "CanonicalRegime",
    "MarketIntelligenceBundle",
    "OptimizationResult",
    "RegimeAssessment",
    "SignalQualityScore",
    "SupervisorMode",
    "SupervisorState",
    "assemble_market_intelligence",
    "build_ai_risk_alerts",
    "get_adaptive_store",
    "get_supervisor",
    "map_canonical_regime",
    "propose_adaptation",
    "run_optimization_orchestrator",
    "score_signal_quality",
]

MODEL_VERSION = "phase4-ati-1.0.0"
