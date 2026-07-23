"""Application facade — Execution Quality Suite (read-only)."""

from __future__ import annotations

from typing import Any

from app.domain.execution_quality_suite import get_eqs
from app.domain.execution_quality_suite.models import ISOLATION_FLAGS


def build_eqs_dashboard() -> dict[str, Any]:
    payload = get_eqs().dashboard()
    payload.update(
        {
            "advisory_only": True,
            "mutates_engines": False,
            "influences_trading": False,
            "never_modifies_production": True,
            "never_executes_trades": True,
            "isolation": {**ISOLATION_FLAGS, **(payload.get("isolation") or {})},
        }
    )
    return payload


def eqs_list_reports(*, limit: int = 20) -> dict[str, Any]:
    rows = get_eqs().store.list_reports(limit=limit)
    return {"reports": rows, "count": len(rows), "isolation": ISOLATION_FLAGS}
