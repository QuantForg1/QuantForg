"""Application facade — Institutional Strategy Lifecycle Manager."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_strategy_lifecycle import get_islm
from app.domain.institutional_strategy_lifecycle.models import ISOLATION_FLAGS


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "influences_trading": False,
        "never_executes_trades": True,
        "never_modifies_production": True,
        "never_changes_strategy_parameters": True,
        "never_approves_promotions_automatically": True,
        "never_retires_strategies_automatically": True,
        "human_approval_required_for_transitions": True,
        "isolation": dict(ISOLATION_FLAGS),
    }


def build_islm_dashboard() -> dict[str, Any]:
    payload = get_islm().dashboard()
    payload.update(_flags())
    return payload


def islm_registry(*, limit: int = 100) -> dict[str, Any]:
    pack = get_islm().dashboard()
    rows = list(pack.get("registry") or [])[:limit]
    return {"registry": rows, "count": len(rows), **_flags()}


def islm_strategy(strategy_id: str) -> dict[str, Any]:
    row = get_islm().get_strategy(strategy_id)
    if not row:
        return {"strategy": None, "found": False, **_flags()}
    return {"strategy": row, "found": True, **_flags()}


def islm_alerts() -> dict[str, Any]:
    pack = get_islm().dashboard()
    return {"alerts": pack.get("alerts") or [], **_flags()}


def islm_health() -> dict[str, Any]:
    pack = get_islm().dashboard()
    return {
        "health_dashboard": (pack.get("sections") or {}).get("health_dashboard"),
        **_flags(),
    }


def islm_evidence(strategy_id: str | None = None) -> dict[str, Any]:
    islm = get_islm()
    if strategy_id:
        row = islm.get_strategy(strategy_id)
        return {
            "strategy_id": strategy_id,
            "evidence": (row or {}).get("evidence"),
            "found": row is not None,
            **_flags(),
        }
    pack = islm.dashboard()
    return {
        "evidence_viewer": (pack.get("sections") or {}).get("evidence_viewer"),
        **_flags(),
    }


def islm_timeline(strategy_id: str | None = None) -> dict[str, Any]:
    islm = get_islm()
    if strategy_id:
        row = islm.get_strategy(strategy_id)
        return {
            "strategy_id": strategy_id,
            "timeline": (row or {}).get("timeline"),
            "found": row is not None,
            **_flags(),
        }
    pack = islm.dashboard()
    return {
        "lifecycle_timeline": (pack.get("sections") or {}).get("lifecycle_timeline"),
        **_flags(),
    }


def islm_versions(strategy_id: str | None = None) -> dict[str, Any]:
    pack = get_islm().dashboard()
    explorer = (pack.get("sections") or {}).get("version_explorer") or []
    if strategy_id:
        match = [r for r in explorer if r.get("strategy_id") == strategy_id]
        return {"versions": match, "strategy_id": strategy_id, **_flags()}
    return {"version_explorer": explorer, **_flags()}


def islm_list_reports(*, limit: int = 20) -> dict[str, Any]:
    rows = get_islm().store.list_reports(limit=limit)
    return {"reports": rows, "count": len(rows), **_flags()}


def islm_list_approvals(*, limit: int = 50) -> dict[str, Any]:
    rows = get_islm().store.list_approvals(limit=limit)
    return {"approvals": rows, "count": len(rows), **_flags()}


def islm_approve_transition(
    *,
    strategy_id: str,
    to_state: str,
    approver: str,
    decision: str,
    comment: str | None = None,
) -> dict[str, Any]:
    payload = get_islm().approve_transition(
        strategy_id=strategy_id,
        to_state=to_state,
        approver=approver,
        decision=decision,
        comment=comment,
    )
    payload.update(_flags())
    return payload
