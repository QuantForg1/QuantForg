"""Phase 7 — Autonomous Trading Control API.

Prefix: /autonomous-trading-control
Never order_send. Default OBSERVE_ONLY. AUTHORIZED ≠ LIVE submit.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.application.services import autonomous_trading_control as atc
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(
    prefix="/autonomous-trading-control",
    tags=["autonomous-trading-control"],
)


class DecisionBody(BaseModel):
    symbol: str = "XAUUSD"
    direction: str | None = None
    strategy: str | None = None
    market_regime: str | None = None
    signal_timestamp: str | None = None
    entry_conditions: list[str] = Field(default_factory=list)
    proposed_stop_loss: float | None = None
    proposed_take_profit: float | None = None
    risk_reward_estimate: float | None = None
    confidence: float | None = None
    supporting_evidence: list[str] = Field(default_factory=list)
    risk_assessment: str | None = None
    market_data_stale: bool = False
    market_data_missing: bool = False
    strategy_approved: bool | None = None
    require_approval: bool = True


class ModeBody(BaseModel):
    mode: str = Field(min_length=1, max_length=64)
    note: str = ""


class ApprovalCreateBody(BaseModel):
    decision_id: str = Field(min_length=1, max_length=64)
    bound_params: dict[str, Any] = Field(default_factory=dict)
    expires_in_minutes: int = 30


class ApprovalActionBody(BaseModel):
    action: str = Field(min_length=1, max_length=64)
    note: str = ""
    current_params: dict[str, Any] | None = None


@router.get("/health")
async def health(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return atc.health()


@router.get("/summary")
async def summary(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return atc.summary()


@router.get("/decisions")
async def list_decisions(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return atc.list_decisions()


@router.post("/decisions")
async def create_decision(body: DecisionBody, user: CurrentUser) -> dict[str, Any]:
    _ = user
    return atc.create_decision(**body.model_dump())


@router.get("/decisions/{decision_id}")
async def get_decision(decision_id: str, user: CurrentUser) -> dict[str, Any]:
    _ = user
    row = atc.get_decision(decision_id)
    if row is None:
        raise HTTPException(status_code=404, detail="decision_not_found")
    return row


@router.get("/strategy/selection")
async def strategy_selection(user: CurrentUser) -> dict[str, Any]:
    _ = user
    candidates: list[dict[str, Any]] = []
    try:
        import importlib

        sic = importlib.import_module(
            "app.application.services.strategy_intelligence_center"
        )
        for name in ("build_dashboard", "dashboard", "strategy_summary"):
            fn = getattr(sic, name, None)
            if callable(fn):
                pack = fn()
                if isinstance(pack, dict):
                    rows = (
                        pack.get("strategies")
                        or pack.get("registry")
                        or pack.get("items")
                        or []
                    )
                    if isinstance(rows, list):
                        candidates = [r for r in rows if isinstance(r, dict)]
                    break
    except Exception:
        candidates = []
    return atc.strategy_selection(candidates=candidates)


@router.post("/signals/validate")
async def signals_validate(
    body: dict[str, Any],
    user: CurrentUser,
) -> dict[str, Any]:
    _ = user
    return atc.signal_validate(body if isinstance(body, dict) else {})


@router.post("/sizing/propose")
async def sizing_propose(body: dict[str, Any], user: CurrentUser) -> dict[str, Any]:
    _ = user
    return atc.sizing_propose(body if isinstance(body, dict) else {})


@router.post("/execution/authorize")
async def execution_authorize(
    body: dict[str, Any],
    user: CurrentUser,
) -> dict[str, Any]:
    payload = dict(body) if isinstance(body, dict) else {}
    payload.setdefault("authenticated", True)
    payload.setdefault("actor_user_id", str(getattr(user, "id", "") or ""))
    return atc.execution_authorize(payload)


@router.get("/modes")
async def get_modes(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return atc.get_modes()


@router.post("/modes")
async def set_mode(body: ModeBody, user: CurrentUser) -> dict[str, Any]:
    actor = str(getattr(user, "email", None) or getattr(user, "id", "") or "user")
    out = atc.set_mode(mode=body.mode, actor=actor, note=body.note)
    if not out.get("ok"):
        raise HTTPException(status_code=400, detail=out)
    return out


@router.get("/approvals")
async def list_approvals(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return atc.list_approvals()


@router.post("/approvals")
async def create_approval(
    body: ApprovalCreateBody,
    user: CurrentUser,
) -> dict[str, Any]:
    actor = str(getattr(user, "email", None) or getattr(user, "id", "") or "user")
    return atc.create_approval(
        decision_id=body.decision_id,
        bound_params=body.bound_params,
        actor=actor,
        expires_in_minutes=body.expires_in_minutes,
    )


@router.post("/approvals/{approval_id}/action")
async def approval_action(
    approval_id: str,
    body: ApprovalActionBody,
    user: CurrentUser,
) -> dict[str, Any]:
    actor = str(getattr(user, "email", None) or getattr(user, "id", "") or "user")
    out = atc.approval_action(
        approval_id,
        action=body.action,
        actor=actor,
        note=body.note,
        current_params=body.current_params,
    )
    if out is None:
        raise HTTPException(status_code=404, detail="approval_not_found")
    if out.get("ok") is False:
        raise HTTPException(status_code=400, detail=out)
    return out


@router.get("/orders/lifecycle")
async def orders_lifecycle(user: CurrentUser) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    try:
        from app.presentation.dependencies.execution import get_execution_uow_factory

        factory = get_execution_uow_factory()
        uid = getattr(user, "id", None)
        if uid is not None:
            async with factory() as uow:
                rows = await uow.attempts.list_for_user(
                    uid if isinstance(uid, UUID) else UUID(str(uid)),
                    limit=50,
                )
                attempts = [a.to_dict() for a in rows]
    except Exception:
        attempts = []
    return atc.orders_lifecycle(attempts=attempts)


@router.get("/trade-intelligence/overview")
async def trade_intelligence(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return atc.trade_intelligence(trades=[])


@router.get("/feedback/overview")
async def feedback_overview(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return atc.feedback_overview()


@router.get("/ops/overview")
async def ops_overview(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return atc.ops_overview()


@router.get("/governance/audit")
async def governance_audit(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return atc.audit_log()
