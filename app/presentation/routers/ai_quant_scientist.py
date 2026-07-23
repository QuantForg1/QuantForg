"""AI Quant Scientist API — advisory research only.

Prefix: /aqs
Never modifies production, thresholds, strategy, risk, safety, OMS, or gateway.
Never executes trades or approves promotion.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/aqs", tags=["ai-quant-scientist"])


class StatusBody(BaseModel):
    status: str = Field(..., max_length=32)


class AskBody(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "influences_trading": False,
        "never_modifies_production": True,
        "never_executes_trades": True,
        "never_approves_promotion": True,
        "humans_remain_responsible": True,
    }


@router.get("/dashboard")
def aqs_dashboard(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.ai_quant_scientist import build_aqs_dashboard

    payload = build_aqs_dashboard()
    payload.update(_flags())
    return payload


@router.get("/feed")
def aqs_feed(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.ai_quant_scientist import build_aqs_dashboard

    pack = build_aqs_dashboard()
    return {"feed": pack.get("feed"), **_flags()}


@router.get("/recommendations")
def aqs_recommendations(
    _user: CurrentUser,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=300),
) -> dict[str, Any]:
    from app.application.services.ai_quant_scientist import aqs_list_recommendations

    payload = aqs_list_recommendations(status=status, limit=limit)
    payload.update(_flags())
    return payload


@router.get("/recommendations/{recommendation_id}")
def aqs_recommendation(recommendation_id: str, _user: CurrentUser) -> dict[str, Any]:
    from app.domain.ai_quant_scientist import get_aqs

    row = get_aqs().store.get_recommendation(recommendation_id)
    if not row:
        raise HTTPException(status_code=404, detail="recommendation_not_found")
    return {"recommendation": row, **_flags()}


@router.post("/recommendations/{recommendation_id}/status")
def aqs_recommendation_status(
    recommendation_id: str,
    body: StatusBody,
    _user: CurrentUser,
) -> dict[str, Any]:
    """Human marking only — Accepted never changes production automatically."""
    from app.application.services.ai_quant_scientist import aqs_set_status

    try:
        row = aqs_set_status(recommendation_id, body.status)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_status") from None
    if not row:
        raise HTTPException(status_code=404, detail="recommendation_not_found")
    return {
        "recommendation": row,
        "note": "Status update is AQS-isolated; production engines unchanged",
        **_flags(),
    }


@router.get("/patterns")
def aqs_patterns(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.ai_quant_scientist import build_aqs_dashboard

    pack = build_aqs_dashboard()
    return {"patterns": pack.get("patterns"), **_flags()}


@router.get("/compare")
def aqs_compare(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.ai_quant_scientist import build_aqs_dashboard

    pack = build_aqs_dashboard()
    return {"comparison": pack.get("comparison"), **_flags()}


@router.get("/regimes")
def aqs_regimes(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.ai_quant_scientist import build_aqs_dashboard

    pack = build_aqs_dashboard()
    return {"regimes": pack.get("regimes"), **_flags()}


@router.get("/sensitivity")
def aqs_sensitivity(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.ai_quant_scientist import build_aqs_dashboard

    pack = build_aqs_dashboard()
    return {"sensitivity": pack.get("sensitivity"), **_flags()}


@router.get("/reports")
def aqs_reports(
    _user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    from app.application.services.ai_quant_scientist import aqs_list_reports

    payload = aqs_list_reports(limit=limit)
    payload.update(_flags())
    return payload


@router.get("/ask")
def aqs_ask_get(
    _user: CurrentUser,
    q: str = Query(..., min_length=1, max_length=500),
) -> dict[str, Any]:
    from app.application.services.ai_quant_scientist import aqs_ask

    payload = aqs_ask(q)
    payload.update(_flags())
    return payload


@router.post("/ask")
def aqs_ask_post(body: AskBody, _user: CurrentUser) -> dict[str, Any]:
    from app.application.services.ai_quant_scientist import aqs_ask

    payload = aqs_ask(body.question)
    payload.update(_flags())
    return payload
