"""ITE Operations Control Plane API — Phase F."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.application.dto.auth import AuthUserDTO
from app.domain.enums.user import UserRole
from app.domain.institutional_trading.auto_trading import AutoTradeLiveFacts
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
from core.config.settings import get_settings

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


class AutoTradeControlsBody(ConfirmBody):
    enabled: bool | None = None
    max_open_positions: int | None = None
    risk_per_trade_pct: str | None = None
    max_daily_loss_pct: str | None = None
    allowed_sessions: list[str] | None = None
    allowed_symbols: list[str] | None = None
    max_spread: str | None = None
    news_filter_enabled: bool | None = None


class AutoTradeEvaluateBody(BaseModel):
    gateway_connected: bool = False
    broker_connected: bool = False
    market_data_live: bool = False
    risk_engine_pass: bool = False
    risk_engine_reasons: list[str] = Field(default_factory=list)
    account_trading_enabled: bool = False
    mt5_autotrading_enabled: bool = False
    symbol: str = "XAUUSD"
    symbol_tradable: bool = False
    margin_available: bool = False
    no_broker_restrictions: bool = False
    open_positions: int = 0
    session: str = "off_hours"
    spread: str | None = None
    news_blocked: bool = False
    news_reason: str = ""
    daily_loss_exceeded: bool = False


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


@router.get("/auto-trading")
def get_auto_trading(_user: OperatorUser) -> dict[str, Any]:
    """Auto Trading status + controls. Fail-closed evaluation without live facts."""
    plane = get_control_plane()
    settings = get_settings()
    health = plane.health.latest()
    facts = AutoTradeLiveFacts(
        gateway_connected=bool(health and health.gateway_available),
        broker_connected=bool(health and health.mt5_connected),
        market_data_live=False,
        risk_engine_pass=False,
        account_trading_enabled=False,
        mt5_autotrading_enabled=False,
        symbol_tradable=False,
        margin_available=False,
        no_broker_restrictions=False,
        emergency_stop=plane.kill_switch_armed,
        ops_mode=plane.mode.value,
        execution_enabled=bool(getattr(settings, "execution_enabled", False)),
    )
    safety = plane.evaluate_auto_trading(facts)
    return {
        "status": safety.status,
        "allowed": safety.allowed,
        "failed_reasons": list(safety.failed_reasons),
        "conditions": [c.to_dict() for c in safety.conditions],
        "policy": plane.auto_trade_policy().to_dict(),
        "emergency_stop": plane.kill_switch_armed,
        "execution_enabled": bool(getattr(settings, "execution_enabled", False)),
        "ops_mode": plane.mode.value,
    }


@router.post("/auto-trading")
def update_auto_trading(
    body: AutoTradeControlsBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    if not body.confirmed:
        raise HTTPException(status_code=400, detail="confirmation required")
    plane = get_control_plane()
    op = _operator(user, request, x_forwarded_for)
    try:
        policy = plane.update_auto_trade_controls(
            op,
            enabled=body.enabled,
            max_open_positions=body.max_open_positions,
            risk_per_trade_pct=(
                Decimal(body.risk_per_trade_pct)
                if body.risk_per_trade_pct is not None
                else None
            ),
            max_daily_loss_pct=(
                Decimal(body.max_daily_loss_pct)
                if body.max_daily_loss_pct is not None
                else None
            ),
            allowed_sessions=(
                tuple(body.allowed_sessions)
                if body.allowed_sessions is not None
                else None
            ),
            allowed_symbols=(
                tuple(body.allowed_symbols)
                if body.allowed_symbols is not None
                else None
            ),
            max_spread=(
                Decimal(body.max_spread) if body.max_spread is not None else None
            ),
            news_filter_enabled=body.news_filter_enabled,
            reason=body.reason,
        )
    except PermissionDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"policy": policy.to_dict()}


@router.post("/auto-trading/evaluate")
def evaluate_auto_trading(
    body: AutoTradeEvaluateBody,
    _user: OperatorUser,
) -> dict[str, Any]:
    """Evaluate live safety conditions and return exact failure reasons."""
    plane = get_control_plane()
    settings = get_settings()
    safety = plane.evaluate_auto_trading(
        AutoTradeLiveFacts(
            gateway_connected=body.gateway_connected,
            broker_connected=body.broker_connected,
            market_data_live=body.market_data_live,
            risk_engine_pass=body.risk_engine_pass,
            risk_engine_reasons=tuple(body.risk_engine_reasons),
            account_trading_enabled=body.account_trading_enabled,
            mt5_autotrading_enabled=body.mt5_autotrading_enabled,
            symbol=body.symbol,
            symbol_tradable=body.symbol_tradable,
            margin_available=body.margin_available,
            no_broker_restrictions=body.no_broker_restrictions,
            open_positions=body.open_positions,
            session=body.session,
            spread=Decimal(body.spread) if body.spread is not None else None,
            news_blocked=body.news_blocked,
            news_reason=body.news_reason,
            daily_loss_exceeded=body.daily_loss_exceeded,
            emergency_stop=plane.kill_switch_armed,
            ops_mode=plane.mode.value,
            execution_enabled=bool(getattr(settings, "execution_enabled", False)),
        )
    )
    return safety.to_dict()


@router.post("/auto-trading/emergency-stop")
def emergency_stop_auto_trading(
    body: ConfirmBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    plane = get_control_plane()
    op = _operator(user, request, x_forwarded_for)
    try:
        plane.emergency_stop(op, reason=body.reason, confirmed=body.confirmed)
    except (PermissionDenied, ValueError) as exc:
        raise HTTPException(
            status_code=403 if isinstance(exc, PermissionDenied) else 400,
            detail=str(exc),
        ) from exc
    return {
        "emergency_stop": True,
        "auto_trading_enabled": False,
        "kill_switch": True,
    }


@router.get("/auto-trading/live-certification")
def live_certification_probe(_user: OperatorUser) -> dict[str, Any]:
    """Step 1 probe — STOP with exact reasons when live conditions fail.

    Never sends orders. Never fabricates broker fills.
    """
    from app.application.services.live_auto_trade_certification import (
        get_live_cert_service,
    )

    svc = get_live_cert_service()
    payload = svc.probe_local_environment()
    last = svc.last_report()
    payload["last_report"] = last.to_dict() if last is not None else None
    return payload


class LiveCertAttemptBody(BaseModel):
    reason: str = Field(min_length=1)
    confirmed: bool = False
    # Live facts — caller must supply measured values; defaults fail-closed
    gateway_connected: bool = False
    broker_connected: bool = False
    market_data_live: bool = False
    risk_engine_pass: bool = False
    risk_engine_reasons: list[str] = Field(default_factory=list)
    account_trading_enabled: bool = False
    mt5_autotrading_enabled: bool = False
    symbol: str = "XAUUSD"
    symbol_tradable: bool = False
    margin_available: bool = False
    no_broker_restrictions: bool = False
    open_positions: int = 0
    session: str = "off_hours"
    spread: str | None = None
    news_blocked: bool = False
    news_reason: str = ""
    daily_loss_exceeded: bool = False
    mt5_logged_in: bool = False
    exposure_pass: bool = False
    drawdown_pass: bool = False
    account_is_demo: bool = False
    # Optional real trade evidence (omit unless broker returned real tickets)
    trade: dict[str, Any] | None = None
    stages_completed: dict[str, bool] = Field(default_factory=dict)


@router.post("/auto-trading/live-certification/attempt")
def live_certification_attempt(
    body: LiveCertAttemptBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    """Attempt Demo certification. Refuses without real trade evidence.

    Never auto-switches SHADOW→LIVE. On failure disables Auto Trading.
    """
    if not body.confirmed:
        raise HTTPException(status_code=400, detail="confirmation required")

    from app.application.services.live_auto_trade_certification import (
        get_live_cert_service,
    )
    from app.domain.institutional_trading.live_certification import LiveTradeEvidence

    plane = get_control_plane()
    op = _operator(user, request, x_forwarded_for)
    settings = get_settings()
    facts = AutoTradeLiveFacts(
        gateway_connected=body.gateway_connected,
        broker_connected=body.broker_connected,
        market_data_live=body.market_data_live,
        risk_engine_pass=body.risk_engine_pass,
        risk_engine_reasons=tuple(body.risk_engine_reasons),
        account_trading_enabled=body.account_trading_enabled,
        mt5_autotrading_enabled=body.mt5_autotrading_enabled,
        symbol=body.symbol,
        symbol_tradable=body.symbol_tradable,
        margin_available=body.margin_available,
        no_broker_restrictions=body.no_broker_restrictions,
        open_positions=body.open_positions,
        session=body.session,
        spread=Decimal(body.spread) if body.spread is not None else None,
        news_blocked=body.news_blocked,
        news_reason=body.news_reason,
        daily_loss_exceeded=body.daily_loss_exceeded,
        emergency_stop=plane.kill_switch_armed,
        ops_mode=plane.mode.value,
        execution_enabled=bool(getattr(settings, "execution_enabled", False)),
    )

    trade: LiveTradeEvidence | None = None
    if body.trade is not None:
        t = body.trade
        try:
            trade = LiveTradeEvidence(
                broker=str(t.get("broker") or ""),
                account_type=str(t.get("account_type") or ""),
                symbol=str(t.get("symbol") or "XAUUSD"),
                volume=Decimal(str(t.get("volume") or "0")),
                ticket=int(t.get("ticket") or 0),
                deal=int(t.get("deal") or 0),
                entry=Decimal(str(t.get("entry") or "0")),
                exit=(
                    Decimal(str(t["exit"]))
                    if t.get("exit") is not None
                    else None
                ),
                profit_loss=(
                    Decimal(str(t["profit_loss"]))
                    if t.get("profit_loss") is not None
                    else None
                ),
                execution_latency_ms=float(t.get("execution_latency_ms") or 0),
                margin_used=(
                    Decimal(str(t["margin_used"]))
                    if t.get("margin_used") is not None
                    else None
                ),
                risk_pct=Decimal(str(t.get("risk_pct") or "0")),
                audit_id=str(t.get("audit_id") or ""),
                position_closed=bool(t.get("position_closed")),
                history_recorded=bool(t.get("history_recorded")),
                analytics_recorded=bool(t.get("analytics_recorded")),
            )
        except Exception as exc:
            raise HTTPException(
                status_code=400, detail=f"invalid trade evidence: {exc}"
            ) from exc

    report = get_live_cert_service().run_certification_attempt(
        op,
        facts=facts,
        mt5_logged_in=body.mt5_logged_in,
        exposure_pass=body.exposure_pass,
        drawdown_pass=body.drawdown_pass,
        account_is_demo=body.account_is_demo,
        trade=trade,
        stage_completed=body.stages_completed,
        reason=body.reason,
    )
    return report.to_dict()


@router.get("/auto-trading/live-certification/report")
def live_certification_report(_user: OperatorUser) -> dict[str, Any]:
    from app.application.services.live_auto_trade_certification import (
        get_live_cert_service,
    )

    last = get_live_cert_service().last_report()
    if last is None:
        raise HTTPException(status_code=404, detail="no live certification report yet")
    return last.to_dict()
