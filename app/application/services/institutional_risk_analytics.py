"""Application facade — Institutional Risk Analytics Platform (read-only)."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_risk_analytics import get_irap
from app.domain.institutional_risk_analytics.models import ISOLATION_FLAGS


def build_irap_dashboard() -> dict[str, Any]:
    payload = get_irap().dashboard()
    payload.update(
        {
            "advisory_only": True,
            "mutates_engines": False,
            "influences_trading": False,
            "never_modifies_production": True,
            "never_executes_trades": True,
            "never_modifies_risk_parameters": True,
            "isolation": {**ISOLATION_FLAGS, **(payload.get("isolation") or {})},
        }
    )
    return payload


def irap_list_reports(*, limit: int = 20) -> dict[str, Any]:
    rows = get_irap().store.list_reports(limit=limit)
    return {"reports": rows, "count": len(rows), "isolation": ISOLATION_FLAGS}
