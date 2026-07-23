"""AI Quant Copilot API — operational explanations only.

Prefix: /aqc
Never executes trades or modifies strategy, thresholds, risk, safety,
OMS, gateway, scheduler, research, or production data.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/aqc", tags=["ai-quant-copilot"])


class AskBody(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "influences_trading": False,
        "never_modifies_production": True,
        "never_executes_trades": True,
        "humans_make_all_operational_decisions": True,
    }


@router.get("/dashboard")
def aqc_dashboard(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.ai_quant_copilot import build_aqc_dashboard

    payload = build_aqc_dashboard()
    payload.update(_flags())
    return payload


@router.get("/ask")
def aqc_ask_get(
    _user: CurrentUser,
    q: str = Query(..., min_length=1, max_length=500),
) -> dict[str, Any]:
    from app.application.services.ai_quant_copilot import aqc_ask

    payload = aqc_ask(q)
    payload.update(_flags())
    return payload


@router.post("/ask")
def aqc_ask_post(body: AskBody, _user: CurrentUser) -> dict[str, Any]:
    """Advisory Q&A only — may append to AQC-isolated conversation history."""
    from app.application.services.ai_quant_copilot import aqc_ask

    payload = aqc_ask(body.question)
    payload.update(_flags())
    return payload


@router.get("/investigations")
def aqc_investigations(
    _user: CurrentUser,
    limit: int = Query(default=40, ge=1, le=100),
) -> dict[str, Any]:
    from app.application.services.ai_quant_copilot import aqc_list_investigations

    payload = aqc_list_investigations(limit=limit)
    payload.update(_flags())
    return payload


@router.get("/investigations/{investigation_id}")
def aqc_investigation(investigation_id: str, _user: CurrentUser) -> dict[str, Any]:
    from app.domain.ai_quant_copilot import get_aqc

    row = get_aqc().store.get_investigation(investigation_id)
    if not row:
        # rebuild from live snapshot and search
        for inv in get_aqc().list_investigations(limit=100):
            if inv.get("id") == investigation_id:
                return {"investigation": inv, **_flags()}
        raise HTTPException(status_code=404, detail="investigation_not_found")
    return {"investigation": row, **_flags()}


@router.get("/timeline")
def aqc_timeline(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.ai_quant_copilot import build_aqc_dashboard

    pack = build_aqc_dashboard()
    return {"timeline": pack.get("timeline"), **_flags()}


@router.get("/comparison")
def aqc_comparison(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.ai_quant_copilot import build_aqc_dashboard

    pack = build_aqc_dashboard()
    return {"comparison": pack.get("comparison"), **_flags()}


@router.get("/evidence")
def aqc_evidence(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.ai_quant_copilot import build_aqc_dashboard

    pack = build_aqc_dashboard()
    sections = pack.get("sections") or {}
    return {
        "evidence": sections.get("evidence_viewer"),
        "execution_explain": pack.get("execution_explain"),
        **_flags(),
    }


@router.get("/reports")
def aqc_reports(
    _user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    from app.application.services.ai_quant_copilot import aqc_list_reports

    payload = aqc_list_reports(limit=limit)
    payload.update(_flags())
    return payload


@router.get("/recommendations")
def aqc_recommendations(
    _user: CurrentUser,
    status: str | None = None,
    min_confidence: float | None = Query(default=None, ge=0, le=100),
    research_area: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    from app.application.services.ai_quant_copilot import aqc_recommendations as _recs

    payload = _recs(
        status=status,
        min_confidence=min_confidence,
        research_area=research_area,
        limit=limit,
    )
    payload.update(_flags())
    return payload


@router.get("/conversations")
def aqc_conversations(
    _user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    from app.application.services.ai_quant_copilot import aqc_list_conversations

    payload = aqc_list_conversations(limit=limit)
    payload.update(_flags())
    return payload


@router.get("/correlations")
def aqc_correlations(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.ai_quant_copilot import build_aqc_dashboard

    pack = build_aqc_dashboard()
    return {"correlations": pack.get("correlations"), **_flags()}
