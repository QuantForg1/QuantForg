"""Application facade — Continuous Validation Framework (read-only)."""

from __future__ import annotations

from typing import Any

from app.domain.continuous_validation_framework import get_cvf
from app.domain.continuous_validation_framework.models import ISOLATION_FLAGS


def build_cvf_dashboard() -> dict[str, Any]:
    payload = get_cvf().dashboard()
    payload.update(
        {
            "advisory_only": True,
            "mutates_engines": False,
            "influences_trading": False,
            "never_modifies_production": True,
            "never_executes_trades": True,
            "never_approves_promotions": True,
            "humans_remain_responsible": True,
            "isolation": {**ISOLATION_FLAGS, **(payload.get("isolation") or {})},
        }
    )
    return payload


def cvf_list_reports(*, limit: int = 20) -> dict[str, Any]:
    rows = get_cvf().store.list_reports(limit=limit)
    return {"reports": rows, "count": len(rows), "isolation": ISOLATION_FLAGS}
