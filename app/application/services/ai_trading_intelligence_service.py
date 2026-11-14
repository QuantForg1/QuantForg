"""Phase 4 AI Trading Intelligence orchestration + serialization."""

from __future__ import annotations

from typing import Any

from app.domain.ai_trading_intelligence.adaptive import (
    AdaptiveProposal,
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
    get_supervisor,
)


def serialize_regime(r: RegimeAssessment) -> dict[str, Any]:
    return {
        "regime": r.regime.value,
        "confidence": str(r.confidence),
        "source_label": r.source_label,
        "mapped_from": r.mapped_from,
        "rationale": r.rationale,
        "methodology": r.methodology,
    }


def serialize_market(b: MarketIntelligenceBundle) -> dict[str, Any]:
    return {
        "symbol": b.symbol,
        "as_of": b.as_of.isoformat(),
        "regime": serialize_regime(b.regime),
        "structure": b.structure,
        "trend": b.trend,
        "momentum": b.momentum,
        "volatility": b.volatility,
        "support_resistance": b.support_resistance,
        "liquidity": b.liquidity,
        "price_action": b.price_action,
        "session": b.session,
        "multi_timeframe": b.multi_timeframe,
        "confidence": str(b.confidence),
        "data_sources": list(b.data_sources),
        "model_version": b.model_version,
        "notes": list(b.notes),
        "methodology": b.methodology,
    }


def serialize_signal(s: SignalQualityScore) -> dict[str, Any]:
    return {
        "symbol": s.symbol,
        "direction": s.direction,
        "strategy_source": s.strategy_source,
        "regime": s.regime.value,
        "confidence": str(s.confidence),
        "quality": str(s.quality),
        "risk_assessment": s.risk_assessment,
        "entry_context": s.entry_context,
        "sl_tp_context": s.sl_tp_context,
        "supporting_factors": list(s.supporting_factors),
        "conflicting_factors": list(s.conflicting_factors),
        "valid_until": s.valid_until.isoformat() if s.valid_until else None,
        "stale": s.stale,
        "actionable": s.actionable,
        "explanation": s.explanation,
        "disclaimer": s.disclaimer,
        "methodology": s.methodology,
    }


def serialize_proposal(p: AdaptiveProposal) -> dict[str, Any]:
    return {
        "proposal_id": p.proposal_id,
        "strategy_id": p.strategy_id,
        "created_at": p.created_at.isoformat(),
        "rationale": p.rationale,
        "current_params": p.current_params,
        "proposed_params": p.proposed_params,
        "accepted": p.accepted,
        "reject_reason": p.reject_reason,
        "status": p.status,
        "regime": p.regime,
    }


def serialize_optimization(o: OptimizationResult) -> dict[str, Any]:
    return {
        "strategy_id": o.strategy_id,
        "as_of": o.as_of.isoformat(),
        "backtest": o.backtest,
        "walk_forward": o.walk_forward,
        "out_of_sample": o.out_of_sample,
        "robustness": o.robustness,
        "metrics": o.metrics,
        "live_deploy_allowed": o.live_deploy_allowed,
        "live_deploy_reason": o.live_deploy_reason,
        "methodology": o.methodology,
    }


def serialize_alert(a: AiRiskAlert) -> dict[str, Any]:
    return {
        "code": a.code,
        "severity": a.severity,
        "title": a.title,
        "explanation": a.explanation,
        "recommended_action": a.recommended_action,
        "evidence": a.evidence,
    }


# Re-export helpers for router
__all__ = [
    "SupervisorMode",
    "assemble_market_intelligence",
    "build_ai_risk_alerts",
    "get_adaptive_store",
    "get_supervisor",
    "map_canonical_regime",
    "propose_adaptation",
    "run_optimization_orchestrator",
    "score_signal_quality",
    "serialize_alert",
    "serialize_market",
    "serialize_optimization",
    "serialize_proposal",
    "serialize_regime",
    "serialize_signal",
]
