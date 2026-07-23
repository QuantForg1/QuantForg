"""Application facade — AI Quant Scientist (read-only toward production)."""

from __future__ import annotations

from typing import Any

from app.domain.ai_quant_scientist import get_aqs
from app.domain.ai_quant_scientist.models import ISOLATION_FLAGS


def build_aqs_dashboard() -> dict[str, Any]:
    payload = get_aqs().dashboard()
    payload.update(
        {
            "advisory_only": True,
            "mutates_engines": False,
            "influences_trading": False,
            "never_modifies_production": True,
            "isolation": {**ISOLATION_FLAGS, **(payload.get("isolation") or {})},
        }
    )
    return payload


def aqs_ask(question: str) -> dict[str, Any]:
    return get_aqs().ask(question)


def aqs_set_status(recommendation_id: str, status: str) -> dict[str, Any] | None:
    return get_aqs().set_recommendation_status(recommendation_id, status)


def aqs_list_recommendations(*, status: str | None = None, limit: int = 100) -> dict[str, Any]:
    rows = get_aqs().store.list_recommendations(status=status, limit=limit)
    return {
        "recommendations": rows,
        "count": len(rows),
        "isolation": ISOLATION_FLAGS,
    }


def aqs_list_reports(*, limit: int = 20) -> dict[str, Any]:
    rows = get_aqs().store.list_reports(limit=limit)
    return {"reports": rows, "count": len(rows), "isolation": ISOLATION_FLAGS}
