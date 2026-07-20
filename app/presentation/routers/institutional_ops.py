"""ITE Operations Control Plane API — Phase F."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.application.dto.auth import AuthUserDTO
from app.domain.enums.user import UserRole
from app.domain.institutional_trading.operations.control_plane import (
    PermissionDenied,
    get_control_plane,
)
from app.domain.institutional_trading.operations.health import HealthInputs
from app.domain.institutional_trading.operations.models import (
    OperatorIdentity,
    OpsExecutionMode,
)
from app.presentation.dependencies.auth import require_roles

router = APIRouter(prefix="/ite/ops", tags=["ite-operations"])

OperatorUser = Annotated[
    AuthUserDTO,
    Depends(require_roles(UserRole.OWNER, UserRole.ADMIN)),
]


def _operator(
    user: AuthUserDTO,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> OperatorIdentity:
    ip = x_forwarded_for or (request.client.host if request.client else None)
    ua = request.headers.get("user-agent")
    return OperatorIdentity(
        user_id=user.id,
        role=str(user.role).lower(),
        display_name=user.display_name or user.email or str(user.id),
        ip=ip,
        user_agent=ua,
    )


class ConfirmBody(BaseModel):
    reason: str = Field(min_length=1)
    confirmed: bool = False


class ModeBody(ConfirmBody):
    target: str


class PromoteBody(ConfirmBody):
    config_version: str
    strategy_version: str
    risk_per_trade_pct: str | None = None
    max_daily_loss_pct: str | None = None
    max_open_trades: int | None = None


class RollbackBody(ConfirmBody):
    target_config_version: str


class RiskBody(ConfirmBody):
    risk_per_trade_pct: str
    max_daily_loss_pct: str
    max_open_trades: int


class HealthBody(BaseModel):
    gateway_latency_ms: float = 0
    gateway_available: bool = True
    mt5_connected: bool = True
    cloudflare_tunnel_up: bool = True
    order_latency_ms: float = 0
    journal_latency_ms: float = 0
    research_queue_depth: int = 0
    simulation_queue_depth: int = 0
    oms_queue_depth: int = 0
    decision_throughput_per_min: float = 0


class AckBody(BaseModel):
    alert_id: str


@router.get("/control-center")
def control_center(_user: OperatorUser) -> dict[str, Any]:
    return get_control_plane().control_center()


@router.get("/readiness")
def readiness(_user: OperatorUser) -> dict[str, Any]:
    return get_control_plane().readiness_dashboard()


@router.post("/mode")
def set_mode(
    body: ModeBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    plane = get_control_plane()
    op = _operator(user, request, x_forwarded_for)
    try:
        target = OpsExecutionMode(body.target.upper())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid mode") from exc
    try:
        result = plane.transition_mode(
            op, target, reason=body.reason, confirmed=body.confirmed
        )
    except PermissionDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.message)
    return result.to_dict()


@router.post("/kill-switch/arm")
def arm_kill(
    body: ConfirmBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    plane = get_control_plane()
    op = _operator(user, request, x_forwarded_for)
    try:
        plane.arm_kill_switch(op, reason=body.reason, confirmed=body.confirmed)
    except (PermissionDenied, ValueError) as exc:
        raise HTTPException(
            status_code=403 if isinstance(exc, PermissionDenied) else 400,
            detail=str(exc),
        ) from exc
    return {"kill_switch": True}


@router.post("/kill-switch/disarm")
def disarm_kill(
    body: ConfirmBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    plane = get_control_plane()
    op = _operator(user, request, x_forwarded_for)
    try:
        plane.disarm_kill_switch(op, reason=body.reason, confirmed=body.confirmed)
    except (PermissionDenied, ValueError) as exc:
        raise HTTPException(
            status_code=403 if isinstance(exc, PermissionDenied) else 400,
            detail=str(exc),
        ) from exc
    return {"kill_switch": False}


@router.post("/config/promote")
def promote(
    body: PromoteBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    if not body.confirmed:
        raise HTTPException(status_code=400, detail="confirmation required")
    plane = get_control_plane()
    op = _operator(user, request, x_forwarded_for)
    try:
        rec = plane.promote_config(
            op,
            config_version=body.config_version,
            strategy_version=body.strategy_version,
            reason=body.reason,
            risk_per_trade_pct=(
                Decimal(body.risk_per_trade_pct) if body.risk_per_trade_pct else None
            ),
            max_daily_loss_pct=(
                Decimal(body.max_daily_loss_pct) if body.max_daily_loss_pct else None
            ),
            max_open_trades=body.max_open_trades,
        )
    except PermissionDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return rec.to_dict()


@router.post("/rollback")
def rollback(
    body: RollbackBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    plane = get_control_plane()
    op = _operator(user, request, x_forwarded_for)
    try:
        rec = plane.rollback(
            op,
            target_config_version=body.target_config_version,
            reason=body.reason,
            confirmed=body.confirmed,
        )
    except (PermissionDenied, ValueError) as exc:
        raise HTTPException(
            status_code=403 if isinstance(exc, PermissionDenied) else 400,
            detail=str(exc),
        ) from exc
    return rec.to_dict()


@router.post("/risk")
def update_risk(
    body: RiskBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    if not body.confirmed:
        raise HTTPException(status_code=400, detail="confirmation required")
    plane = get_control_plane()
    op = _operator(user, request, x_forwarded_for)
    try:
        plane.update_risk(
            op,
            risk_per_trade_pct=Decimal(body.risk_per_trade_pct),
            max_daily_loss_pct=Decimal(body.max_daily_loss_pct),
            max_open_trades=body.max_open_trades,
            reason=body.reason,
        )
    except PermissionDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return cast("dict[str, Any]", plane.control_center()["risk"])


@router.post("/health")
def post_health(body: HealthBody, _user: OperatorUser) -> dict[str, Any]:
    plane = get_control_plane()
    plane.update_health(
        HealthInputs(
            gateway_latency_ms=body.gateway_latency_ms,
            gateway_available=body.gateway_available,
            mt5_connected=body.mt5_connected,
            cloudflare_tunnel_up=body.cloudflare_tunnel_up,
            order_latency_ms=body.order_latency_ms,
            journal_latency_ms=body.journal_latency_ms,
            research_queue_depth=body.research_queue_depth,
            simulation_queue_depth=body.simulation_queue_depth,
            oms_queue_depth=body.oms_queue_depth,
            decision_throughput_per_min=body.decision_throughput_per_min,
        )
    )
    snap = plane.health.latest()
    return snap.to_dict() if snap else {}


@router.get("/alerts")
def list_alerts(
    _user: OperatorUser,
    unacked_only: bool = False,
) -> dict[str, Any]:
    rows = get_control_plane().alerts.list(unacked_only=unacked_only)
    return {"alerts": [a.to_dict() for a in rows]}


@router.post("/alerts/ack")
def ack_alert(
    body: AckBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    plane = get_control_plane()
    op = _operator(user, request, x_forwarded_for)
    try:
        plane.acknowledge_alert(op, UUID(body.alert_id))
    except (PermissionDenied, ValueError) as exc:
        raise HTTPException(
            status_code=403 if isinstance(exc, PermissionDenied) else 400,
            detail=str(exc),
        ) from exc
    return {"ok": True}


@router.get("/audit")
def audit_log(_user: OperatorUser, limit: int = 200) -> dict[str, Any]:
    rows = get_control_plane().audit.list(limit=limit)
    return {
        "entries": [e.to_dict() for e in rows],
        "count": get_control_plane().audit.count(),
    }


@router.get("/configs")
def list_configs(_user: OperatorUser) -> dict[str, Any]:
    plane = get_control_plane()
    return {
        "active": (
            active.to_dict() if (active := plane.configs.active()) is not None else None
        ),
        "versions": [c.to_dict() for c in plane.configs.list()],
    }


@router.get("/runbooks")
def list_runbooks(_user: OperatorUser) -> dict[str, Any]:
    return {"runbooks": get_control_plane().runbooks.list()}


@router.post("/runbooks/{runbook_id}/execute")
def execute_runbook(
    runbook_id: str,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    plane = get_control_plane()
    op = _operator(user, request, x_forwarded_for)
    try:
        return plane.execute_runbook(op, runbook_id)
    except PermissionDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
