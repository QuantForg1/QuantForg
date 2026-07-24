"""Institutional Strategy Lifecycle Manager API.

Prefix: /islm
Governance layer — never executes trades or modifies production.
Lifecycle transitions require explicit human approval (ISLM-isolated only).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/islm", tags=["institutional-strategy-lifecycle"])


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
        "preserves_existing_governance_rules": True,
    }


class LifecycleApprovalBody(BaseModel):
    strategy_id: str = Field(min_length=1, max_length=128)
    to_state: str = Field(min_length=1, max_length=64)
    decision: str = Field(pattern="^(approved|rejected)$")
    comment: str | None = Field(default=None, max_length=2000)
    approver: str | None = Field(default=None, max_length=128)


@router.get("/dashboard")
def islm_dashboard(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_strategy_lifecycle import (
        build_islm_dashboard,
    )

    payload = build_islm_dashboard()
    payload.update(_flags())
    return payload


@router.get("/registry")
def islm_registry(
    _user: CurrentUser,
    limit: int = Query(default=100, ge=1, le=200),
) -> dict[str, Any]:
    from app.application.services.institutional_strategy_lifecycle import islm_registry

    payload = islm_registry(limit=limit)
    payload.update(_flags())
    return payload


@router.get("/strategies/{strategy_id}")
def islm_strategy(strategy_id: str, _user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_strategy_lifecycle import islm_strategy

    payload = islm_strategy(strategy_id)
    payload.update(_flags())
    if not payload.get("found"):
        raise HTTPException(status_code=404, detail="strategy_not_found")
    return payload


@router.get("/timeline")
def islm_timeline(
    _user: CurrentUser,
    strategy_id: str | None = Query(default=None),
) -> dict[str, Any]:
    from app.application.services.institutional_strategy_lifecycle import islm_timeline

    payload = islm_timeline(strategy_id)
    payload.update(_flags())
    return payload


@router.get("/versions")
def islm_versions(
    _user: CurrentUser,
    strategy_id: str | None = Query(default=None),
) -> dict[str, Any]:
    from app.application.services.institutional_strategy_lifecycle import islm_versions

    payload = islm_versions(strategy_id)
    payload.update(_flags())
    return payload


@router.get("/health")
def islm_health(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_strategy_lifecycle import islm_health

    payload = islm_health()
    payload.update(_flags())
    return payload


@router.get("/evidence")
def islm_evidence(
    _user: CurrentUser,
    strategy_id: str | None = Query(default=None),
) -> dict[str, Any]:
    from app.application.services.institutional_strategy_lifecycle import islm_evidence

    payload = islm_evidence(strategy_id)
    payload.update(_flags())
    return payload


@router.get("/alerts")
def islm_alerts(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_strategy_lifecycle import islm_alerts

    payload = islm_alerts()
    payload.update(_flags())
    return payload


@router.get("/reports")
def islm_reports(
    _user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    from app.application.services.institutional_strategy_lifecycle import (
        islm_list_reports,
    )

    payload = islm_list_reports(limit=limit)
    payload.update(_flags())
    return payload


@router.get("/approvals")
def islm_approvals(
    _user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    from app.application.services.institutional_strategy_lifecycle import (
        islm_list_approvals,
    )

    payload = islm_list_approvals(limit=limit)
    payload.update(_flags())
    return payload


@router.post("/lifecycle/approve")
def islm_approve(
    body: LifecycleApprovalBody,
    user: CurrentUser,
) -> dict[str, Any]:
    """Explicit human approval — ISLM isolation only; never production."""
    from app.application.services.institutional_strategy_lifecycle import (
        islm_approve_transition,
    )

    approver = body.approver or getattr(user, "email", None) or getattr(
        user, "sub", None
    ) or "human-operator"
    try:
        payload = islm_approve_transition(
            strategy_id=body.strategy_id,
            to_state=body.to_state,
            approver=str(approver),
            decision=body.decision,
            comment=body.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload.update(_flags())
    return payload
