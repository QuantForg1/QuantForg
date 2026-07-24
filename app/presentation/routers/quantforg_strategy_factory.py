"""QuantForg Strategy Factory API — governed workflow.

Prefix: /qsf
Never executes trades, modifies production, approves releases, deploys, or allocates.
Pipeline transitions require explicit human approval (QSF-isolated only).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/qsf", tags=["quantforg-strategy-factory"])


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
        "read_only_except_human_approvals": True,
    }


class PipelineApprovalBody(BaseModel):
    strategy_id: str = Field(min_length=1, max_length=128)
    to_stage: str = Field(min_length=1, max_length=64)
    decision: str = Field(pattern="^(approved|rejected)$")
    comment: str | None = Field(default=None, max_length=2000)
    approver: str | None = Field(default=None, max_length=128)
    work_item_id: str | None = Field(default=None, max_length=128)


@router.get("/dashboard")
def qsf_dashboard(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_strategy_factory import build_qsf_dashboard

    payload = build_qsf_dashboard()
    payload.update(_flags())
    return payload


@router.get("/pipeline")
def qsf_pipeline(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_strategy_factory import qsf_pipeline as svc

    payload = svc()
    payload.update(_flags())
    return payload


@router.get("/work-items")
def qsf_work_items(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_strategy_factory import qsf_work_items as svc

    payload = svc()
    payload.update(_flags())
    return payload


@router.get("/dossiers")
def qsf_dossiers(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_strategy_factory import qsf_dossiers as svc

    payload = svc()
    payload.update(_flags())
    return payload


@router.get("/evidence")
def qsf_evidence(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_strategy_factory import qsf_evidence as svc

    payload = svc()
    payload.update(_flags())
    return payload


@router.get("/approvals")
def qsf_approvals(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_strategy_factory import (
        qsf_approval_queue as svc,
    )

    payload = svc()
    payload.update(_flags())
    return payload


@router.get("/reports")
def qsf_reports(
    _user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    from app.application.services.quantforg_strategy_factory import qsf_reports as svc

    payload = svc(limit=limit)
    payload.update(_flags())
    return payload


@router.post("/pipeline/approve")
def qsf_approve(body: PipelineApprovalBody, user: CurrentUser) -> dict[str, Any]:
    """Explicit human approval — QSF isolation only; never production/deploy."""
    from app.application.services.quantforg_strategy_factory import (
        qsf_approve_transition,
    )

    approver = (
        body.approver
        or getattr(user, "email", None)
        or getattr(user, "sub", None)
        or "human-operator"
    )
    try:
        payload = qsf_approve_transition(
            strategy_id=body.strategy_id,
            to_stage=body.to_stage,
            approver=str(approver),
            decision=body.decision,
            comment=body.comment,
            work_item_id=body.work_item_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload.update(_flags())
    return payload
