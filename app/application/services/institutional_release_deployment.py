"""Application facade — Institutional Release & Deployment Platform."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_release_deployment import get_irdp
from app.domain.institutional_release_deployment.models import ISOLATION_FLAGS


def build_irdp_dashboard() -> dict[str, Any]:
    payload = get_irdp().dashboard()
    payload.update(
        {
            "advisory_only": True,
            "mutates_engines": False,
            "influences_trading": False,
            "never_executes_trades": True,
            "never_auto_approves": True,
            "never_rollbacks_automatically": True,
            "preserves_production_safety_guarantees": True,
            "isolation": {**ISOLATION_FLAGS, **(payload.get("isolation") or {})},
        }
    )
    return payload


def irdp_create_release(
    *, version: str, component: str = "QuantForg", notes: str | None = None
) -> dict[str, Any]:
    return get_irdp().create_release(version=version, component=component, notes=notes)


def irdp_advance(release_id: str, *, to_stage: str | None = None) -> dict[str, Any] | None:
    return get_irdp().advance(release_id, to_stage=to_stage)


def irdp_approve(
    release_id: str,
    *,
    approver: str,
    decision: str,
    comment: str | None = None,
) -> dict[str, Any] | None:
    return get_irdp().approve(
        release_id, approver=approver, decision=decision, comment=comment
    )


def irdp_plan_rollback(
    release_id: str, *, requested_by: str, reason: str | None = None
) -> dict[str, Any] | None:
    return get_irdp().plan_rollback(
        release_id, requested_by=requested_by, reason=reason
    )


def irdp_list_reports(*, limit: int = 20) -> dict[str, Any]:
    rows = get_irdp().store.list_reports(limit=limit)
    return {"reports": rows, "count": len(rows), "isolation": ISOLATION_FLAGS}
