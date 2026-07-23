"""Application facade — AI Quant Copilot (read-only toward production)."""

from __future__ import annotations

from typing import Any

from app.domain.ai_quant_copilot import get_aqc
from app.domain.ai_quant_copilot.analysis import search_aqs_recommendations
from app.domain.ai_quant_copilot.gather import gather_ops_context
from app.domain.ai_quant_copilot.models import ISOLATION_FLAGS


def build_aqc_dashboard() -> dict[str, Any]:
    payload = get_aqc().dashboard()
    payload.update(
        {
            "advisory_only": True,
            "mutates_engines": False,
            "influences_trading": False,
            "never_modifies_production": True,
            "never_executes_trades": True,
            "humans_make_all_operational_decisions": True,
            "isolation": {**ISOLATION_FLAGS, **(payload.get("isolation") or {})},
        }
    )
    return payload


def aqc_ask(question: str) -> dict[str, Any]:
    return get_aqc().ask(question)


def aqc_list_investigations(*, limit: int = 40) -> dict[str, Any]:
    rows = get_aqc().list_investigations(limit=limit)
    return {
        "investigations": rows,
        "count": len(rows),
        "isolation": ISOLATION_FLAGS,
    }


def aqc_list_conversations(*, limit: int = 50) -> dict[str, Any]:
    rows = get_aqc().list_conversations(limit=limit)
    return {
        "conversations": rows,
        "count": len(rows),
        "isolation": ISOLATION_FLAGS,
    }


def aqc_list_reports(*, limit: int = 20) -> dict[str, Any]:
    rows = get_aqc().store.list_reports(limit=limit)
    return {"reports": rows, "count": len(rows), "isolation": ISOLATION_FLAGS}


def aqc_recommendations(
    *,
    status: str | None = None,
    min_confidence: float | None = None,
    research_area: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    ctx = gather_ops_context()
    rows = search_aqs_recommendations(
        ctx,
        status=status,
        min_confidence=min_confidence,
        research_area=research_area,
        limit=limit,
    )
    return {
        "recommendations": rows,
        "count": len(rows),
        "filters": {
            "status": status,
            "min_confidence": min_confidence,
            "research_area": research_area,
        },
        "isolation": ISOLATION_FLAGS,
        "note": "AQS recommendations explored read-only — Accepted never applies production",
    }
