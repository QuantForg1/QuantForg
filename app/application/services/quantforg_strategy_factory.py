"""Application facade — QuantForg Strategy Factory."""

from __future__ import annotations

from typing import Any

from app.domain.quantforg_strategy_factory import get_qsf
from app.domain.quantforg_strategy_factory.models import ISOLATION_FLAGS


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "influences_trading": False,
        "never_executes_trades": True,
        "never_modifies_production": True,
        "never_approves_releases": True,
        "never_deploys_strategies": True,
        "never_allocates_capital": True,
        "human_approval_required_for_transitions": True,
        "preserves_existing_safety_guarantees": True,
        "isolation": dict(ISOLATION_FLAGS),
    }


def build_qsf_dashboard() -> dict[str, Any]:
    payload = get_qsf().dashboard()
    payload.update(_flags())
    return payload


def qsf_pipeline() -> dict[str, Any]:
    pack = get_qsf().dashboard()
    return {"pipeline_board": pack.get("pipeline_board"), **_flags()}


def qsf_work_items() -> dict[str, Any]:
    pack = get_qsf().dashboard()
    return {"work_items": pack.get("work_items") or [], **_flags()}


def qsf_dossiers() -> dict[str, Any]:
    pack = get_qsf().dashboard()
    return {"dossiers": pack.get("dossiers"), **_flags()}


def qsf_approval_queue() -> dict[str, Any]:
    pack = get_qsf().dashboard()
    return {
        "approval_queue": pack.get("approval_queue") or [],
        "approvals": pack.get("approvals") or [],
        **_flags(),
    }


def qsf_evidence() -> dict[str, Any]:
    pack = get_qsf().dashboard()
    return {
        "evidence_center": (pack.get("sections") or {}).get("evidence_center"),
        **_flags(),
    }


def qsf_reports(*, limit: int = 20) -> dict[str, Any]:
    rows = get_qsf().store.list_reports(limit=limit)
    return {"reports": rows, "count": len(rows), **_flags()}


def qsf_approve_transition(
    *,
    strategy_id: str,
    to_stage: str,
    approver: str,
    decision: str,
    comment: str | None = None,
    work_item_id: str | None = None,
) -> dict[str, Any]:
    payload = get_qsf().approve_transition(
        strategy_id=strategy_id,
        to_stage=to_stage,
        approver=approver,
        decision=decision,
        comment=comment,
        work_item_id=work_item_id,
    )
    payload.update(_flags())
    return payload
