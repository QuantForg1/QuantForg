"""Application facade — QuantForg Strategy Marketplace & Registry (read-only)."""

from __future__ import annotations

from typing import Any

from app.domain.quantforg_strategy_marketplace import get_qsmr
from app.domain.quantforg_strategy_marketplace.analytics import compare_strategies
from app.domain.quantforg_strategy_marketplace.models import ISOLATION_FLAGS


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "influences_trading": False,
        "never_executes_trades": True,
        "never_modifies_strategies": True,
        "never_modifies_production": True,
        "never_approves_certifications": True,
        "never_deploys_strategies": True,
        "isolation": dict(ISOLATION_FLAGS),
    }


def build_qsmr_dashboard() -> dict[str, Any]:
    payload = get_qsmr().dashboard()
    payload.update(_flags())
    return payload


def qsmr_registry(*, limit: int = 100) -> dict[str, Any]:
    pack = get_qsmr().dashboard()
    rows = list(pack.get("registry") or [])[:limit]
    return {"registry": rows, "count": len(rows), **_flags()}


def qsmr_strategy(strategy_id: str) -> dict[str, Any]:
    row = get_qsmr().get_strategy(strategy_id)
    if not row:
        return {"strategy": None, "found": False, **_flags()}
    return {"strategy": row, "found": True, **_flags()}


def qsmr_search(**kwargs: Any) -> dict[str, Any]:
    payload = get_qsmr().search(**kwargs)
    payload.update(_flags())
    return payload


def qsmr_compare(*, strategy_ids: list[str] | None = None) -> dict[str, Any]:
    registry = get_qsmr().sync_registry()
    payload = compare_strategies(registry, strategy_ids=strategy_ids)
    payload.update(_flags())
    return payload


def qsmr_evidence(strategy_id: str | None = None) -> dict[str, Any]:
    qsmr = get_qsmr()
    if strategy_id:
        row = qsmr.get_strategy(strategy_id)
        if not row:
            return {"found": False, "evidence": None, **_flags()}
        return {
            "found": True,
            "strategy_id": strategy_id,
            "evidence": {
                "research_lineage": row.get("research_lineage"),
                "replay_evidence": row.get("replay_evidence"),
                "simulation_evidence": row.get("simulation_evidence"),
                "validation_evidence": row.get("validation_evidence"),
                "risk_profile": row.get("risk_profile"),
                "deployment_history": row.get("deployment_history"),
                "knowledge_graph_links": row.get("knowledge_graph_links"),
            },
            **_flags(),
        }
    pack = qsmr.dashboard()
    return {
        "evidence_viewer": (pack.get("sections") or {}).get("evidence_viewer"),
        **_flags(),
    }


def qsmr_list_reports(*, limit: int = 20) -> dict[str, Any]:
    rows = get_qsmr().store.list_reports(limit=limit)
    return {"reports": rows, "count": len(rows), **_flags()}
