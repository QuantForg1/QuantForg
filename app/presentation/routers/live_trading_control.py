"""Phase 73 live-trading control API — OWNER/ADMIN only.

Does not enable live trading on GET. Never fabricates broker state.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.application.dto.auth import AuthUserDTO
from app.application.services.live_trading_control_service import (
    arm_live_trading,
    build_live_trading_status,
    confirmation_preview,
    disable_live_trading,
    enable_live_trading,
    evaluate_live_order_request,
    kill_live_trading,
    operator_from_user,
    pause_live_trading,
    reset_killed,
    update_live_risk,
)
from app.domain.enums.user import UserRole
from app.domain.institutional_trading.live_trading_control import (
    BrokerSymbolSpec,
    LiveOrderRequest,
    LiveTradingAuthError,
    LiveTradingTransitionError,
    spec_from_broker,
)
from app.presentation.dependencies.auth import require_roles

router = APIRouter(prefix="/live-trading", tags=["live-trading-control"])

OperatorUser = Annotated[
    AuthUserDTO,
    Depends(require_roles(UserRole.OWNER, UserRole.ADMIN)),
]


def _operator(
    user: AuthUserDTO,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
):
    ip = x_forwarded_for or (request.client.host if request.client else None)
    ua = request.headers.get("user-agent")
    return operator_from_user(user, ip=ip, user_agent=ua)


class ConfirmBody(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    confirmed: bool = False
    confirmation_phrase: str | None = None


class RiskBody(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    risk_per_trade_pct: str | None = None
    max_daily_loss_pct: str | None = None
    max_open_positions: int | None = None
    max_consecutive_losses: int | None = None
    max_margin_utilization_pct: str | None = None
    max_total_exposure_pct: str | None = None
    max_spread: str | None = None
    max_slippage: str | None = None
    close_positions_on_kill: bool | None = None


class EvaluateBody(BaseModel):
    symbol: str
    direction: str
    price: str | None = None
    entry: str | None = None
    stop_loss: str | None = None
    take_profit: str | None = None
    score: str | None = None
    edge: str | None = None
    regime: str | None = None
    spread: str | None = None
    quote_age_seconds: str | None = None
    signal_id: str | None = None
    signal_status: str | None = None
    reward_risk: str | None = None
    evidence: dict[str, Any] | None = None
    spec: dict[str, Any] | None = None
    equity: str | None = None
    balance: str | None = None
    free_margin: str | None = None
    used_margin: str | None = None
    open_positions: int = 0
    daily_loss_pct: str | None = None
    consecutive_losses: int = 0
    slippage: str | None = None
    gateway_online: bool = False
    mt5_connected: bool = False
    ownership_ok: bool = False
    account_available: bool = False
    trading_permitted: bool = False
    symbol_available: bool = False
    symbol_tradeable: bool = False
    quote_fresh: bool = False
    price_valid: bool = False
    market_open: bool = False
    oms_healthy: bool = False
    risk_engine_healthy: bool = False
    audit_healthy: bool = False
    authenticated_authorized: bool = False
    request_id: str | None = None


def _http_exc(exc: Exception) -> HTTPException:
    if isinstance(exc, LiveTradingAuthError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, LiveTradingTransitionError):
        detail = str(exc)
        if "confirmation" in detail:
            return HTTPException(status_code=400, detail=detail)
        return HTTPException(status_code=409, detail=detail)
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/status")
def live_trading_status(user: OperatorUser) -> dict[str, Any]:
    """Read-only. Opening this endpoint never enables live trading."""
    return build_live_trading_status(user=user)


@router.get("/confirmation-preview")
def live_trading_confirmation_preview(user: OperatorUser) -> dict[str, Any]:
    return confirmation_preview(user=user)


@router.post("/arm")
def live_trading_arm(
    body: ConfirmBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    try:
        return arm_live_trading(
            _operator(user, request, x_forwarded_for),
            confirmed=body.confirmed,
            reason=body.reason,
            confirmation_phrase=body.confirmation_phrase,
        )
    except (LiveTradingAuthError, LiveTradingTransitionError) as exc:
        raise _http_exc(exc) from exc


@router.post("/enable")
def live_trading_enable(
    body: ConfirmBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    try:
        return enable_live_trading(
            _operator(user, request, x_forwarded_for),
            confirmed=body.confirmed,
            reason=body.reason,
            confirmation_phrase=body.confirmation_phrase,
        )
    except (LiveTradingAuthError, LiveTradingTransitionError) as exc:
        raise _http_exc(exc) from exc


@router.post("/pause")
def live_trading_pause(
    body: ConfirmBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    try:
        return pause_live_trading(
            _operator(user, request, x_forwarded_for),
            reason=body.reason,
        )
    except (LiveTradingAuthError, LiveTradingTransitionError) as exc:
        raise _http_exc(exc) from exc


@router.post("/disable")
def live_trading_disable(
    body: ConfirmBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    try:
        return disable_live_trading(
            _operator(user, request, x_forwarded_for),
            reason=body.reason,
        )
    except (LiveTradingAuthError, LiveTradingTransitionError) as exc:
        raise _http_exc(exc) from exc


@router.post("/kill")
def live_trading_kill(
    body: ConfirmBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    try:
        return kill_live_trading(
            _operator(user, request, x_forwarded_for),
            confirmed=body.confirmed,
            reason=body.reason,
        )
    except (LiveTradingAuthError, LiveTradingTransitionError) as exc:
        raise _http_exc(exc) from exc


@router.post("/emergency-stop")
def live_trading_emergency_stop(
    body: ConfirmBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    """Alias of kill — ANY state → DISABLED. Does not close positions."""
    try:
        return kill_live_trading(
            _operator(user, request, x_forwarded_for),
            confirmed=body.confirmed,
            reason=body.reason or "emergency_stop",
        )
    except (LiveTradingAuthError, LiveTradingTransitionError) as exc:
        raise _http_exc(exc) from exc


@router.post("/reset-killed")
def live_trading_reset_killed(
    body: ConfirmBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    try:
        return reset_killed(
            _operator(user, request, x_forwarded_for),
            reason=body.reason,
        )
    except (LiveTradingAuthError, LiveTradingTransitionError) as exc:
        raise _http_exc(exc) from exc


@router.post("/risk")
def live_trading_risk(
    body: RiskBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    patch = body.model_dump(exclude_none=True)
    patch.pop("reason", None)
    try:
        return update_live_risk(
            _operator(user, request, x_forwarded_for),
            patch,
            reason=body.reason,
        )
    except (LiveTradingAuthError, LiveTradingTransitionError) as exc:
        raise _http_exc(exc) from exc


@router.post("/evaluate")
def live_trading_evaluate(body: EvaluateBody, _user: OperatorUser) -> dict[str, Any]:
    """Evaluate a candidate against live gates. Does not send an order."""
    spec: BrokerSymbolSpec | None = None
    if body.spec:
        spec = spec_from_broker(body.symbol, body.spec)
    req = LiveOrderRequest(
        symbol=body.symbol,
        direction=body.direction,
        price=_d(body.price),
        entry=_d(body.entry),
        stop_loss=_d(body.stop_loss),
        take_profit=_d(body.take_profit),
        score=_d(body.score),
        edge=_d(body.edge),
        regime=body.regime,
        spread=_d(body.spread),
        quote_age_seconds=_d(body.quote_age_seconds),
        signal_id=body.signal_id,
        signal_status=body.signal_status,
        evidence=body.evidence,
        reward_risk=_d(body.reward_risk),
        spec=spec,
        equity=_d(body.equity),
        balance=_d(body.balance),
        free_margin=_d(body.free_margin),
        used_margin=_d(body.used_margin),
        open_positions=body.open_positions,
        daily_loss_pct=_d(body.daily_loss_pct),
        consecutive_losses=body.consecutive_losses,
        slippage=_d(body.slippage),
        gateway_online=body.gateway_online,
        mt5_connected=body.mt5_connected,
        ownership_ok=body.ownership_ok,
        account_available=body.account_available,
        trading_permitted=body.trading_permitted,
        symbol_available=body.symbol_available,
        symbol_tradeable=body.symbol_tradeable,
        quote_fresh=body.quote_fresh,
        price_valid=body.price_valid,
        market_open=body.market_open,
        oms_healthy=body.oms_healthy,
        risk_engine_healthy=body.risk_engine_healthy,
        audit_healthy=body.audit_healthy,
        authenticated_authorized=body.authenticated_authorized,
        request_id=body.request_id,
    )
    return evaluate_live_order_request(req)


def _d(value: str | None):
    if value is None or value == "":
        return None
    from decimal import Decimal

    try:
        return Decimal(str(value))
    except Exception:
        return None
