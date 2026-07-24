"""Application facade — QuantForg Autonomous Operations Center (read-only)."""

from __future__ import annotations

from typing import Any

from app.domain.quantforg_autonomous_operations import get_aoc
from app.domain.quantforg_autonomous_operations.models import ISOLATION_FLAGS


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "influences_trading": False,
        "never_executes_trades": True,
        "never_modifies_production": True,
        "never_modifies_strategies": True,
        "never_modifies_risk": True,
        "never_modifies_safety": True,
        "never_approves_releases": True,
        "never_allocates_capital": True,
        "never_deploys_strategies": True,
        "never_performs_automatic_remediation": True,
        "human_approval_required_for_recommendations": True,
        "preserves_existing_safety_guarantees": True,
        "isolation": dict(ISOLATION_FLAGS),
    }


def build_aoc_dashboard() -> dict[str, Any]:
    payload = get_aoc().dashboard()
    payload.update(_flags())
    return payload


def aoc_recommendations() -> dict[str, Any]:
    pack = get_aoc().dashboard()
    return {"recommendations": pack.get("recommendations") or [], **_flags()}


def aoc_queue() -> dict[str, Any]:
    pack = get_aoc().dashboard()
    return {"work_queue": pack.get("work_queue") or [], **_flags()}


def aoc_scores() -> dict[str, Any]:
    pack = get_aoc().dashboard()
    return {
        "executive_scores": pack.get("executive_scores"),
        "operational_health": pack.get("operational_health"),
        **_flags(),
    }


def aoc_evidence() -> dict[str, Any]:
    pack = get_aoc().dashboard()
    return {"evidence": pack.get("evidence"), **_flags()}


def aoc_brief() -> dict[str, Any]:
    pack = get_aoc().dashboard()
    return {
        "executive_brief": (pack.get("sections") or {}).get("executive_brief"),
        **_flags(),
    }


def aoc_list_reports(*, limit: int = 20) -> dict[str, Any]:
    rows = get_aoc().store.list_reports(limit=limit)
    return {"reports": rows, "count": len(rows), **_flags()}
