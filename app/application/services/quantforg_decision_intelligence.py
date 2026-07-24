"""Application facade — QuantForg Decision Intelligence Engine (advisory)."""

from __future__ import annotations

from typing import Any

from app.domain.quantforg_decision_intelligence import get_qdie
from app.domain.quantforg_decision_intelligence.models import ISOLATION_FLAGS


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "influences_trading": False,
        "never_executes_trades": True,
        "never_modifies_production": True,
        "never_modifies_strategies": True,
        "never_modifies_risk": True,
        "never_approves_releases": True,
        "never_allocates_capital": True,
        "never_performs_automatic_actions": True,
        "human_approval_required": True,
        "isolation": dict(ISOLATION_FLAGS),
    }


def build_qdie_dashboard() -> dict[str, Any]:
    payload = get_qdie().dashboard()
    payload.update(_flags())
    return payload


def qdie_recommendations() -> dict[str, Any]:
    pack = get_qdie().dashboard()
    return {"recommendations": pack.get("recommendations") or [], **_flags()}


def qdie_scores() -> dict[str, Any]:
    pack = get_qdie().dashboard()
    return {"scores": pack.get("scores"), **_flags()}


def qdie_evidence() -> dict[str, Any]:
    pack = get_qdie().dashboard()
    return {"evidence_graph": pack.get("evidence_graph"), **_flags()}


def qdie_tradeoffs() -> dict[str, Any]:
    pack = get_qdie().dashboard()
    return {"tradeoffs": pack.get("tradeoffs") or [], **_flags()}


def qdie_brief() -> dict[str, Any]:
    pack = get_qdie().dashboard()
    return {
        "executive_decision_brief": (pack.get("reports") or {}).get(
            "executive_decision_brief"
        ),
        **_flags(),
    }


def qdie_reports(*, limit: int = 20) -> dict[str, Any]:
    rows = get_qdie().store.list_reports(limit=limit)
    return {"reports": rows, "count": len(rows), **_flags()}


def qdie_history(*, limit: int = 50) -> dict[str, Any]:
    rows = get_qdie().store.list_history(limit=limit)
    return {"history": rows, "count": len(rows), **_flags()}
