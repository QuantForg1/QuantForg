"""Phase 4 — AI Trading Intelligence API (advisory; never order_send)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.application.services import ai_trading_intelligence_service as ati
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(
    prefix="/ai-trading-intelligence",
    tags=["ai-trading-intelligence"],
)


class MarketIntelBody(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    facts: dict[str, Any] = Field(default_factory=dict)


class RegimeBody(BaseModel):
    source_label: str | None = None
    confidence: float | None = None


class SignalScoreBody(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    direction: str | None = None
    strategy_source: str | None = None
    regime_label: str | None = None
    regime_confidence: float | None = None
    confidence: float | None = None
    quality: float | None = None
    supporting_factors: list[str] = Field(default_factory=list)
    conflicting_factors: list[str] = Field(default_factory=list)
    entry_context: dict[str, Any] | None = None
    sl_tp_context: dict[str, Any] | None = None
    ttl_seconds: int | None = None
    duplicate: bool = False


class AdaptBody(BaseModel):
    strategy_id: str = Field(min_length=1, max_length=128)
    current_params: dict[str, Any] = Field(default_factory=dict)
    proposed_params: dict[str, Any] = Field(default_factory=dict)
    rationale: str = Field(min_length=1, max_length=1024)
    regime: str | None = None


class OptimizeBody(BaseModel):
    strategy_id: str = Field(min_length=1, max_length=128)
    backtest: dict[str, Any] | None = None
    walk_forward: dict[str, Any] | None = None
    out_of_sample: dict[str, Any] | None = None
    robustness: dict[str, Any] | None = None
    owner_promotion_approved: bool = False


class RiskAlertsBody(BaseModel):
    portfolio: dict[str, Any] = Field(default_factory=dict)
    strategy_health: dict[str, Any] = Field(default_factory=dict)
    signal_quality_drift: dict[str, Any] = Field(default_factory=dict)
    execution: dict[str, Any] = Field(default_factory=dict)


class SupervisorModeBody(BaseModel):
    mode: str = Field(min_length=1, max_length=64)
    confirmed: bool = False


class SupervisorActionBody(BaseModel):
    action: str = Field(min_length=1, max_length=64)
    detail: str = ""
    owner_approved: bool = False
    increases_risk: bool = False
    enables_live: bool = False
    disables_safety: bool = False


@router.get("/health")
async def ati_health(user: CurrentUser) -> dict[str, Any]:
    _ = user
    snap = ati.get_supervisor().snapshot()
    return {
        "ok": True,
        "model_version": "phase4-ati-1.0.0",
        "supervisor_mode": snap["mode"],
        "order_send": False,
        "auto_live_deploy": False,
    }


@router.post("/market-intelligence")
async def post_market_intelligence(
    body: MarketIntelBody,
    user: CurrentUser,
) -> dict[str, Any]:
    _ = user
    bundle = ati.assemble_market_intelligence(symbol=body.symbol, facts=body.facts)
    return ati.serialize_market(bundle)


@router.post("/regime")
async def post_regime(body: RegimeBody, user: CurrentUser) -> dict[str, Any]:
    _ = user
    assessment = ati.map_canonical_regime(body.source_label, confidence=body.confidence)
    return ati.serialize_regime(assessment)


@router.get("/regime/validation")
async def regime_validation(user: CurrentUser) -> dict[str, Any]:
    """Honest fixture-level agreement report — never invents accuracy."""
    _ = user
    fixtures = [
        ("strong_trend", 80, "TRENDING"),
        ("ranging", 70, "RANGING"),
        ("breakout", 75, "BREAKOUT"),
        ("unknown", 90, "UNCERTAIN"),
        ("strong_trend", 20, "UNCERTAIN"),  # low confidence
    ]
    correct = 0
    rows = []
    for label, conf, expected in fixtures:
        out = ati.map_canonical_regime(label, confidence=conf)
        ok = out.regime.value == expected
        if ok:
            correct += 1
        rows.append(
            {
                "source_label": label,
                "confidence": conf,
                "expected": expected,
                "got": out.regime.value,
                "match": ok,
            }
        )
    return {
        "fixture_count": len(fixtures),
        "agreement_count": correct,
        "agreement_rate": correct / len(fixtures) if fixtures else None,
        "rows": rows,
        "methodology": {
            "source": "synthetic_label_fixtures_only",
            "not_live_accuracy": True,
            "invented_market_accuracy": False,
        },
    }


@router.post("/signal-quality")
async def post_signal_quality(
    body: SignalScoreBody,
    user: CurrentUser,
) -> dict[str, Any]:
    _ = user
    score = ati.score_signal_quality(
        symbol=body.symbol,
        direction=body.direction,
        strategy_source=body.strategy_source,
        regime_label=body.regime_label,
        regime_confidence=body.regime_confidence,
        confidence=body.confidence,
        quality=body.quality,
        supporting_factors=body.supporting_factors,
        conflicting_factors=body.conflicting_factors,
        entry_context=body.entry_context,
        sl_tp_context=body.sl_tp_context,
        ttl_seconds=body.ttl_seconds,
        duplicate=body.duplicate,
    )
    return ati.serialize_signal(score)


@router.post("/adaptive/propose")
async def post_adaptive_propose(
    body: AdaptBody,
    user: CurrentUser,
) -> dict[str, Any]:
    _ = user
    proposal = ati.propose_adaptation(
        strategy_id=body.strategy_id,
        current_params=body.current_params,
        proposed_params=body.proposed_params,
        rationale=body.rationale,
        regime=body.regime,
    )
    return ati.serialize_proposal(proposal)


@router.post("/adaptive/{proposal_id}/approve")
async def post_adaptive_approve(
    proposal_id: str,
    user: CurrentUser,
) -> dict[str, Any]:
    _ = user
    out = ati.get_adaptive_store().approve(proposal_id)
    if out is None:
        return {"ok": False, "error": "proposal_not_found_or_not_proposed"}
    return {"ok": True, "proposal": ati.serialize_proposal(out)}


@router.post("/adaptive/{strategy_id}/rollback")
async def post_adaptive_rollback(
    strategy_id: str,
    user: CurrentUser,
) -> dict[str, Any]:
    _ = user
    baseline = ati.get_adaptive_store().rollback(strategy_id)
    if baseline is None:
        return {"ok": False, "error": "no_validated_baseline"}
    return {"ok": True, "restored_params": baseline, "live_deployed": False}


@router.get("/adaptive")
async def list_adaptive(
    user: CurrentUser,
    strategy_id: str | None = None,
) -> dict[str, Any]:
    _ = user
    items = ati.get_adaptive_store().list_for(strategy_id)
    return {"items": [ati.serialize_proposal(p) for p in items]}


@router.post("/optimize")
async def post_optimize(body: OptimizeBody, user: CurrentUser) -> dict[str, Any]:
    _ = user
    result = ati.run_optimization_orchestrator(
        strategy_id=body.strategy_id,
        backtest_summary=body.backtest,
        walk_forward_summary=body.walk_forward,
        out_of_sample_summary=body.out_of_sample,
        robustness_summary=body.robustness,
        owner_promotion_approved=body.owner_promotion_approved,
    )
    return ati.serialize_optimization(result)


@router.post("/risk-alerts")
async def post_risk_alerts(
    body: RiskAlertsBody,
    user: CurrentUser,
) -> dict[str, Any]:
    _ = user
    alerts = ati.build_ai_risk_alerts(
        portfolio=body.portfolio,
        strategy_health=body.strategy_health,
        signal_quality_drift=body.signal_quality_drift,
        execution=body.execution,
    )
    return {
        "alerts": [ati.serialize_alert(a) for a in alerts],
        "mutates_risk_center": False,
        "mutates_kill_switch": False,
    }


@router.get("/supervisor")
async def get_supervisor_state(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return ati.get_supervisor().snapshot()


@router.post("/supervisor/mode")
async def set_supervisor_mode(
    body: SupervisorModeBody,
    user: CurrentUser,
) -> dict[str, Any]:
    if not body.confirmed:
        return {"ok": False, "error": "confirmation_required"}
    try:
        mode = ati.SupervisorMode(body.mode)
    except ValueError:
        return {
            "ok": False,
            "error": "invalid_mode",
            "allowed": [m.value for m in ati.SupervisorMode],
        }
    ev = ati.get_supervisor().set_mode(mode, actor=str(user.id))
    return {
        "ok": True,
        "mode": ev.mode.value,
        "event_id": ev.event_id,
        "at": ev.at.isoformat(),
    }


@router.post("/supervisor/action")
async def supervisor_action(
    body: SupervisorActionBody,
    user: CurrentUser,
) -> dict[str, Any]:
    _ = user
    ev = ati.get_supervisor().evaluate_action(
        action=body.action,
        detail=body.detail,
        owner_approved=body.owner_approved,
        increases_risk=body.increases_risk,
        enables_live=body.enables_live,
        disables_safety=body.disables_safety,
    )
    return {
        "applied": ev.applied,
        "reject_reason": ev.reject_reason,
        "mode": ev.mode.value,
        "action": ev.action,
        "event_id": ev.event_id,
        "at": ev.at.isoformat(),
    }
