"""Institutional Release & Deployment Platform API.

Prefix: /irdp
Read-only reporting except explicit human approval / governance workflow.
Never executes trades or auto-approves releases.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/irdp", tags=["institutional-release-deployment"])


class CreateReleaseBody(BaseModel):
    version: str = Field(..., min_length=1, max_length=64)
    component: str = Field(default="QuantForg", max_length=128)
    notes: str | None = Field(default=None, max_length=2000)


class AdvanceBody(BaseModel):
    to_stage: str | None = Field(default=None, max_length=64)


class ApproveBody(BaseModel):
    approver: str = Field(..., min_length=1, max_length=128)
    decision: str = Field(..., min_length=1, max_length=32)
    comment: str | None = Field(default=None, max_length=2000)


class RollbackPlanBody(BaseModel):
    requested_by: str = Field(..., min_length=1, max_length=128)
    reason: str | None = Field(default=None, max_length=2000)


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "never_executes_trades": True,
        "never_auto_approves": True,
        "never_rollbacks_automatically": True,
        "human_approval_required": True,
        "preserves_production_safety_guarantees": True,
    }


@router.get("/dashboard")
def irdp_dashboard(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_release_deployment import (
        build_irdp_dashboard,
    )

    payload = build_irdp_dashboard()
    payload.update(_flags())
    return payload


@router.get("/releases")
def irdp_releases(
    _user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    from app.domain.institutional_release_deployment import get_irdp

    rows = get_irdp().store.list_releases(limit=limit)
    return {"releases": rows, "count": len(rows), **_flags()}


@router.get("/releases/{release_id}")
def irdp_release(release_id: str, _user: CurrentUser) -> dict[str, Any]:
    from app.domain.institutional_release_deployment import get_irdp

    row = get_irdp().store.get_release(release_id)
    if not row:
        raise HTTPException(status_code=404, detail="release_not_found")
    return {"release": row, **_flags()}


@router.post("/releases")
def irdp_create(body: CreateReleaseBody, _user: CurrentUser) -> dict[str, Any]:
    """Create a draft release record — does not deploy or approve."""
    from app.application.services.institutional_release_deployment import (
        irdp_create_release,
    )

    row = irdp_create_release(
        version=body.version, component=body.component, notes=body.notes
    )
    return {
        "release": row,
        "note": "Draft only — human approval required before staging/production",
        **_flags(),
    }


@router.post("/releases/{release_id}/advance")
def irdp_advance(
    release_id: str, body: AdvanceBody, _user: CurrentUser
) -> dict[str, Any]:
    """Advance pipeline stage — staging/production blocked without approval."""
    from app.application.services.institutional_release_deployment import irdp_advance as _adv

    row = _adv(release_id, to_stage=body.to_stage)
    if not row:
        raise HTTPException(status_code=404, detail="release_not_found")
    return {"release": row, **_flags()}


@router.post("/releases/{release_id}/approve")
def irdp_approve(
    release_id: str, body: ApproveBody, _user: CurrentUser
) -> dict[str, Any]:
    """Explicit human approval workflow — never automatic."""
    from app.application.services.institutional_release_deployment import (
        irdp_approve as _approve,
    )

    try:
        row = _approve(
            release_id,
            approver=body.approver,
            decision=body.decision,
            comment=body.comment,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_decision") from None
    if not row:
        raise HTTPException(status_code=404, detail="release_not_found")
    return {
        "release": row,
        "note": "Human decision recorded — IRDP never auto-approves",
        **_flags(),
    }


@router.post("/releases/{release_id}/rollback-plan")
def irdp_rollback_plan(
    release_id: str, body: RollbackPlanBody, _user: CurrentUser
) -> dict[str, Any]:
    """Record a controlled rollback plan — never executes rollback."""
    from app.application.services.institutional_release_deployment import (
        irdp_plan_rollback,
    )

    plan = irdp_plan_rollback(
        release_id, requested_by=body.requested_by, reason=body.reason
    )
    if not plan:
        raise HTTPException(status_code=404, detail="release_not_found")
    return {
        "rollback_plan": plan,
        "note": "Plan recorded only — never rollback automatically",
        **_flags(),
    }


@router.get("/checklist")
def irdp_checklist(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_release_deployment import (
        build_irdp_dashboard,
    )

    pack = build_irdp_dashboard()
    return {
        "checklist": pack.get("checklist"),
        "pass_count": pack.get("checklist_pass_count"),
        "total": pack.get("checklist_total"),
        **_flags(),
    }


@router.get("/monitoring")
def irdp_monitoring(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_release_deployment import (
        build_irdp_dashboard,
    )

    pack = build_irdp_dashboard()
    return {"monitoring": pack.get("monitoring"), **_flags()}


@router.get("/approvals")
def irdp_approvals(
    _user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    from app.domain.institutional_release_deployment import get_irdp

    rows = get_irdp().store.list_approvals(limit=limit)
    return {"approvals": rows, "count": len(rows), **_flags()}


@router.get("/rollbacks")
def irdp_rollbacks(
    _user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    from app.domain.institutional_release_deployment import get_irdp

    rows = get_irdp().store.list_rollbacks(limit=limit)
    return {"rollbacks": rows, "count": len(rows), **_flags()}


@router.get("/reports")
def irdp_reports(
    _user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    from app.application.services.institutional_release_deployment import irdp_list_reports

    payload = irdp_list_reports(limit=limit)
    payload.update(_flags())
    return payload


@router.get("/releases/{release_id}/audit")
def irdp_audit(release_id: str, _user: CurrentUser) -> dict[str, Any]:
    from app.domain.institutional_release_deployment import get_irdp

    pack = get_irdp().audit_pack(release_id)
    if not pack:
        raise HTTPException(status_code=404, detail="release_not_found")
    pack.update(_flags())
    return pack
