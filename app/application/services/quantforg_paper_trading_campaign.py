"""Application facade — QuantForg Paper Trading Campaign Manager."""

from __future__ import annotations

from typing import Any

from app.domain.quantforg_paper_trading_campaign import get_qptcm
from app.domain.quantforg_paper_trading_campaign.models import ISOLATION_FLAGS


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "influences_trading": False,
        "paper_trading_only": True,
        "never_places_live_trades": True,
        "never_modifies_production": True,
        "never_allocates_capital": True,
        "never_approves_graduation_automatically": True,
        "human_approval_required_for_transitions": True,
        "preserves_existing_safety_guarantees": True,
        "isolation": dict(ISOLATION_FLAGS),
    }


def build_qptcm_dashboard() -> dict[str, Any]:
    payload = get_qptcm().dashboard()
    payload.update(_flags())
    return payload


def qptcm_campaigns() -> dict[str, Any]:
    pack = get_qptcm().dashboard()
    return {"campaigns": pack.get("campaigns") or [], **_flags()}


def qptcm_timeline() -> dict[str, Any]:
    pack = get_qptcm().dashboard()
    return {"daily_timeline": pack.get("daily_timeline") or [], **_flags()}


def qptcm_evidence() -> dict[str, Any]:
    pack = get_qptcm().dashboard()
    return {
        "evidence_center": (pack.get("sections") or {}).get("evidence_center"),
        **_flags(),
    }


def qptcm_graduation() -> dict[str, Any]:
    pack = get_qptcm().dashboard()
    return {
        "graduation_workspace": pack.get("graduation_workspace"),
        **_flags(),
    }


def qptcm_reports(*, limit: int = 20) -> dict[str, Any]:
    rows = get_qptcm().store.list_reports(limit=limit)
    return {"reports": rows, "count": len(rows), **_flags()}


def qptcm_approvals(*, limit: int = 50) -> dict[str, Any]:
    rows = get_qptcm().store.list_approvals(limit=limit)
    pack = get_qptcm().dashboard()
    queue = [
        {
            "campaign_id": c.get("campaign_id"),
            "from_state": c.get("lifecycle"),
            "to_state": c.get("next_lifecycle"),
            "strategy_id": c.get("strategy_id"),
            "strategy_name": c.get("strategy_name"),
            "requires_human_approval": True,
            "never_places_live_trades": True,
        }
        for c in pack.get("campaigns") or []
        if c.get("next_lifecycle")
    ]
    return {"approvals": rows, "queue": queue, **_flags()}


def qptcm_approve_transition(
    *,
    campaign_id: str,
    to_state: str,
    approver: str,
    decision: str,
    comment: str | None = None,
) -> dict[str, Any]:
    payload = get_qptcm().approve_transition(
        campaign_id=campaign_id,
        to_state=to_state,
        approver=approver,
        decision=decision,
        comment=comment,
    )
    payload.update(_flags())
    return payload
