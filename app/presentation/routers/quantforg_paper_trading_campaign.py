"""QuantForg Paper Trading Campaign Manager API.

Prefix: /qptcm
Never places live trades, modifies production, or allocates capital.
Lifecycle transitions require explicit human approval (QPTCM-isolated).
Graduation is never automatic.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/qptcm", tags=["quantforg-paper-trading-campaign"])


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
        "read_only_except_human_approvals": True,
    }


class CampaignApprovalBody(BaseModel):
    campaign_id: str = Field(min_length=1, max_length=128)
    to_state: str = Field(min_length=1, max_length=64)
    decision: str = Field(pattern="^(approved|rejected)$")
    comment: str | None = Field(default=None, max_length=2000)
    approver: str | None = Field(default=None, max_length=128)


@router.get("/dashboard")
def qptcm_dashboard(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_paper_trading_campaign import (
        build_qptcm_dashboard,
    )

    payload = build_qptcm_dashboard()
    payload.update(_flags())
    return payload


@router.get("/campaigns")
def qptcm_campaigns(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_paper_trading_campaign import (
        qptcm_campaigns as svc,
    )

    payload = svc()
    payload.update(_flags())
    return payload


@router.get("/timeline")
def qptcm_timeline(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_paper_trading_campaign import (
        qptcm_timeline as svc,
    )

    payload = svc()
    payload.update(_flags())
    return payload


@router.get("/evidence")
def qptcm_evidence(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_paper_trading_campaign import (
        qptcm_evidence as svc,
    )

    payload = svc()
    payload.update(_flags())
    return payload


@router.get("/graduation")
def qptcm_graduation(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_paper_trading_campaign import (
        qptcm_graduation as svc,
    )

    payload = svc()
    payload.update(_flags())
    return payload


@router.get("/reports")
def qptcm_reports(
    _user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    from app.application.services.quantforg_paper_trading_campaign import (
        qptcm_reports as svc,
    )

    payload = svc(limit=limit)
    payload.update(_flags())
    return payload


@router.get("/approvals")
def qptcm_approvals(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_paper_trading_campaign import (
        qptcm_approvals as svc,
    )

    payload = svc()
    payload.update(_flags())
    return payload


@router.post("/lifecycle/approve")
def qptcm_approve(body: CampaignApprovalBody, user: CurrentUser) -> dict[str, Any]:
    """Explicit human approval — QPTCM isolation; never live trades or auto-grad."""
    from app.application.services.quantforg_paper_trading_campaign import (
        qptcm_approve_transition,
    )

    approver = (
        body.approver
        or getattr(user, "email", None)
        or getattr(user, "sub", None)
        or "human-operator"
    )
    try:
        payload = qptcm_approve_transition(
            campaign_id=body.campaign_id,
            to_state=body.to_state,
            approver=str(approver),
            decision=body.decision,
            comment=body.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload.update(_flags())
    return payload
