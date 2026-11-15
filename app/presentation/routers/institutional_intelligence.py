"""Phase 6 — Institutional Intelligence API (advisory facade).

Prefix: /institutional-intelligence
Never order_send. Never auto-rebalance LIVE. Approved ≠ LIVE.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.application.services import institutional_intelligence as ii
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(
    prefix="/institutional-intelligence",
    tags=["institutional-intelligence"],
)


class RecommendBody(BaseModel):
    recommendation: str = Field(min_length=1, max_length=2000)
    reasoning_summary: str = Field(min_length=1, max_length=4000)
    supporting_evidence: list[str] = Field(default_factory=list)
    confidence: float | None = None
    expected_benefits: list[str] = Field(default_factory=list)
    risks_and_limitations: list[str] = Field(default_factory=list)
    affected_strategy_or_account: str | None = None
    required_approval: bool = True


class StatusBody(BaseModel):
    status: str = Field(min_length=1, max_length=64)
    note: str = ""


async def _load_attempts(user_id: UUID, limit: int = 100) -> list[dict[str, Any]]:
    try:
        from app.presentation.dependencies.execution import get_execution_uow_factory

        factory = get_execution_uow_factory()
    except Exception:
        return []
    try:
        async with factory() as uow:
            rows = await uow.attempts.list_for_user(user_id, limit=limit)
            return [a.to_dict() for a in rows]
    except Exception:
        return []


@router.get("/health")
async def intel_health(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return ii.health()


@router.get("/summary")
async def intel_summary(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return ii.summary()


@router.get("/market/overview")
async def market_overview(
    user: CurrentUser,
    symbol: str = "XAUUSD",
    regime_label: str | None = None,
    regime_confidence: float | None = None,
) -> dict[str, Any]:
    _ = user
    return ii.market_overview(
        symbol=symbol[:32],
        regime_label=regime_label,
        regime_confidence=regime_confidence,
    )


@router.get("/strategy/overview")
async def strategy_overview(user: CurrentUser) -> dict[str, Any]:
    _ = user
    strategies: list[dict[str, Any]] = []
    try:
        import importlib

        sic = importlib.import_module(
            "app.application.services.strategy_intelligence_center"
        )
        for name in ("build_dashboard", "dashboard", "strategy_summary"):
            fn = getattr(sic, name, None)
            if callable(fn):
                pack = fn()
                if isinstance(pack, dict):
                    rows = (
                        pack.get("strategies")
                        or pack.get("registry")
                        or pack.get("items")
                        or []
                    )
                    if isinstance(rows, list):
                        strategies = [r for r in rows if isinstance(r, dict)]
                break
    except Exception:
        strategies = []
    return ii.strategy_overview(strategies=strategies)


@router.get("/risk/overview")
async def risk_overview(user: CurrentUser) -> dict[str, Any]:
    _ = user
    ati_alerts: list[dict[str, Any]] = []
    try:
        from app.domain.ai_trading_intelligence.risk_alerts import build_ai_risk_alerts

        for a in build_ai_risk_alerts(
            portfolio={},
            strategy_health={},
            signal_quality_drift={},
            execution={},
        ):
            ati_alerts.append(
                {
                    "code": a.code,
                    "severity": a.severity,
                    "title": a.title,
                    "explanation": a.explanation,
                    "recommended_action": a.recommended_action,
                    "advisory_only": True,
                }
            )
    except Exception:
        ati_alerts = []

    phase5_risk: dict[str, Any] = {}
    try:
        from app.application.services import institutional_ops_control as ioc

        phase5_risk = ioc.risk_overview(ati_alerts=ati_alerts)
    except Exception:
        phase5_risk = {}

    irap: dict[str, Any] = {}
    try:
        import importlib

        mod = importlib.import_module(
            "app.application.services.institutional_risk_analytics"
        )
        for name in ("build_dashboard", "dashboard", "build_irap_dashboard"):
            fn = getattr(mod, name, None)
            if callable(fn):
                pack = fn()
                if isinstance(pack, dict):
                    irap = pack
                break
    except Exception:
        irap = {"status": "unavailable"}

    return ii.risk_overview(
        ati_alerts=ati_alerts,
        irap=irap,
        phase5_risk=phase5_risk,
    )


@router.get("/portfolio/overview")
async def portfolio_overview(user: CurrentUser) -> dict[str, Any]:
    _ = user
    qpm: dict[str, Any] = {}
    try:
        import importlib

        mod = importlib.import_module(
            "app.application.services.quantforg_portfolio_manager"
        )
        for name in ("build_dashboard", "dashboard", "recommendations"):
            fn = getattr(mod, name, None)
            if callable(fn):
                pack = fn()
                if isinstance(pack, dict):
                    qpm = pack
                elif isinstance(pack, list):
                    qpm = {"recommendations": pack}
                break
    except Exception:
        qpm = {}
    # Household equity/balance intentionally omitted unless a safe caller supplies —
    # never invent capital in the facade.
    return ii.portfolio_overview(qpm=qpm, household={})


@router.get("/execution/overview")
async def execution_overview(user: CurrentUser) -> dict[str, Any]:
    attempts = await _load_attempts(user.id)
    return ii.execution_overview(attempts=attempts, eqs={})


@router.get("/decision/overview")
async def decision_overview(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return ii.decision_overview()


@router.get("/decision/recommendations")
async def list_recommendations(user: CurrentUser) -> dict[str, Any]:
    _ = user
    pack = ii.decision_overview()
    return {
        "recommendations": pack.get("recommendations") or [],
        "count": pack.get("count") or 0,
        **{
            k: pack[k]
            for k in ("advisory_only", "never_order_send", "model_version")
            if k in pack
        },
        "approved_is_not_live": True,
    }


@router.post("/decision/recommendations")
async def create_recommendation(
    body: RecommendBody,
    user: CurrentUser,
) -> dict[str, Any]:
    _ = user
    row = ii.create_recommendation(
        recommendation=body.recommendation,
        reasoning_summary=body.reasoning_summary,
        supporting_evidence=body.supporting_evidence,
        confidence=body.confidence,
        expected_benefits=body.expected_benefits,
        risks_and_limitations=body.risks_and_limitations,
        affected_strategy_or_account=body.affected_strategy_or_account,
        required_approval=body.required_approval,
    )
    return {**row, "ok": True, "approved_is_not_live": True}


@router.post("/decision/recommendations/{rec_id}/status")
async def set_recommendation_status(
    rec_id: str,
    body: StatusBody,
    user: CurrentUser,
) -> dict[str, Any]:
    _ = user
    out = ii.set_recommendation_status(rec_id, status=body.status, note=body.note)
    if out is None:
        raise HTTPException(status_code=404, detail="recommendation_not_found")
    if out.get("ok") is False:
        raise HTTPException(status_code=400, detail=out)
    return out


@router.get("/reports/overview")
async def reports_overview(user: CurrentUser) -> dict[str, Any]:
    _ = user
    catalogs: list[dict[str, Any]] = [
        {
            "id": "phase5_ops",
            "label": "Phase 5 Operations",
            "path": "/operations",
            "result_class": "actual",
        },
        {
            "id": "ati",
            "label": "AI Trading Intelligence",
            "path": "/ai-trading-intelligence",
            "result_class": "advisory",
        },
        {
            "id": "execution",
            "label": "Execution Intelligence",
            "path": "/execution-intelligence",
            "result_class": "actual",
        },
        {
            "id": "audit",
            "label": "Audit Governance",
            "path": "/audit-governance",
            "result_class": "actual",
        },
    ]
    return ii.reports_overview(catalogs=catalogs)


@router.get("/governance/data-quality")
async def data_quality_overview(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return ii.data_quality_overview(qcdm={}, idw={})
