"""Application facade — Institutional Control Plane (read-only)."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_control_plane import get_icp
from app.domain.institutional_control_plane.models import ISOLATION_FLAGS


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "influences_trading": False,
        "never_executes_trades": True,
        "never_modifies_production": True,
        "never_modifies_strategy": True,
        "never_modifies_risk": True,
        "never_modifies_releases": True,
        "never_approves_experiments": True,
        "never_approves_lifecycle_transitions": True,
        "isolation": dict(ISOLATION_FLAGS),
    }


def build_icp_dashboard() -> dict[str, Any]:
    payload = get_icp().dashboard()
    payload.update(_flags())
    return payload


def icp_health() -> dict[str, Any]:
    pack = get_icp().dashboard()
    return {"health": pack.get("health"), **_flags()}


def icp_alerts() -> dict[str, Any]:
    pack = get_icp().dashboard()
    return {"alerts": pack.get("alerts") or [], **_flags()}


def icp_timeline() -> dict[str, Any]:
    pack = get_icp().dashboard()
    return {"timeline": pack.get("timeline") or [], **_flags()}


def icp_dependencies() -> dict[str, Any]:
    pack = get_icp().dashboard()
    return {"dependencies": pack.get("dependencies"), **_flags()}


def icp_evidence() -> dict[str, Any]:
    pack = get_icp().dashboard()
    return {"evidence": pack.get("evidence"), **_flags()}


def icp_list_reports(*, limit: int = 20) -> dict[str, Any]:
    rows = get_icp().store.list_reports(limit=limit)
    return {"reports": rows, "count": len(rows), **_flags()}
