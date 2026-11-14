"""Phase 3 — household portfolio intelligence API (read + risk evaluate)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.application.services.household_portfolio_service import (
    build_household_from_sources,
    build_household_performance,
    closed_trades_from_deals,
    export_performance_csv,
    household_exposure,
    household_risk_check,
    serialize_exposure,
    serialize_household,
    serialize_performance,
    serialize_risk,
)
from app.domain.portfolio_household.emergency_stops import get_emergency_stop_store
from app.presentation.dependencies.auth import CurrentUser
from app.presentation.dependencies.broker import BrokerSvc
from app.presentation.dependencies.portfolio import PortfolioDep

router = APIRouter(prefix="/portfolio/household", tags=["portfolio-household"])


class HouseholdRiskCheckBody(BaseModel):
    proposed_symbol: str | None = None
    proposed_risk_pct: str | None = Field(default=None, max_length=32)
    broker_account_id: UUID | None = None
    broker_code: str | None = Field(default=None, max_length=64)


class EmergencyStopBody(BaseModel):
    scope: str = Field(pattern="^(user|account|broker)$")
    scope_id: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=512)
    confirmed: bool = False


async def _build(
    user: CurrentUser,
    brokers: BrokerSvc,
    portfolio: PortfolioDep,
) -> Any:
    accounts = await brokers.list_accounts.execute(user_id=user.id)
    live = None
    try:
        live = await portfolio.execute(user_id=user.id)
    except Exception:
        live = None
    return build_household_from_sources(
        user_id=user.id,
        registry_accounts=list(accounts),
        live=live,
    )


@router.get("")
async def get_household_portfolio(
    user: CurrentUser,
    brokers: BrokerSvc,
    portfolio: PortfolioDep,
) -> dict[str, Any]:
    hh = await _build(user, brokers, portfolio)
    return serialize_household(hh)


@router.get("/accounts")
async def get_household_accounts(
    user: CurrentUser,
    brokers: BrokerSvc,
    portfolio: PortfolioDep,
) -> dict[str, Any]:
    hh = await _build(user, brokers, portfolio)
    payload = serialize_household(hh)
    return {
        "as_of": payload["as_of"],
        "accounts": payload["accounts"],
        "methodology": payload["methodology"],
    }


@router.get("/exposure")
async def get_household_exposure(
    user: CurrentUser,
    brokers: BrokerSvc,
    portfolio: PortfolioDep,
) -> dict[str, Any]:
    hh = await _build(user, brokers, portfolio)
    return serialize_exposure(household_exposure(hh))


@router.post("/risk-check")
async def post_household_risk_check(
    body: HouseholdRiskCheckBody,
    user: CurrentUser,
    brokers: BrokerSvc,
    portfolio: PortfolioDep,
) -> dict[str, Any]:
    hh = await _build(user, brokers, portfolio)
    effective = None
    try:
        from app.application.services.user_risk_preferences_service import (
            get_user_risk_preferences,
        )

        prefs = get_user_risk_preferences(user.id)
        effective = prefs.get("effective") if isinstance(prefs, dict) else None
    except Exception:
        effective = None
    proposed = None
    if body.proposed_risk_pct:
        try:
            proposed = Decimal(body.proposed_risk_pct)
        except Exception:
            proposed = None
    check = household_risk_check(
        hh,
        effective=effective if isinstance(effective, dict) else None,
        user_id=user.id,
        proposed_symbol=body.proposed_symbol,
        proposed_risk_pct=proposed,
    )
    return serialize_risk(check)


@router.get("/performance")
async def get_household_performance(
    user: CurrentUser,
    brokers: BrokerSvc,
    portfolio: PortfolioDep,
    broker: str | None = Query(default=None),
    strategy: str | None = Query(default=None),
) -> dict[str, Any]:
    hh = await _build(user, brokers, portfolio)
    deals: list[dict[str, Any]] = []
    try:
        live = await portfolio.execute(user_id=user.id)
        for d in live.history_deals:
            deals.append(
                {
                    "ticket": d.ticket,
                    "symbol": d.symbol,
                    "profit": d.profit,
                    "commission": getattr(d, "commission", None),
                    "swap": getattr(d, "swap", None),
                    "side": getattr(d, "side", None) or getattr(d, "type", None),
                    "time": getattr(d, "time", None),
                    "confirmed": True,
                }
            )
    except Exception:
        deals = []
    trades = closed_trades_from_deals(deals, account_key="active")
    if broker:
        trades = [t for t in trades if (t.broker_code or "") == broker]
    if strategy:
        trades = [t for t in trades if (t.strategy or "") == strategy]
    # Attach broker codes from household when single live account matched
    report = build_household_performance(trades)
    _ = hh  # household available for future multi-account deal merge
    return serialize_performance(report)


@router.get("/attribution")
async def get_household_attribution(
    user: CurrentUser,
    brokers: BrokerSvc,
    portfolio: PortfolioDep,
) -> dict[str, Any]:
    perf = await get_household_performance(user, brokers, portfolio)
    return {
        "attribution": perf.get("attribution", []),
        "methodology": perf.get("methodology", {}),
        "trades_considered": perf.get("trades_considered"),
        "trades_excluded_unconfirmed": perf.get("trades_excluded_unconfirmed"),
    }


@router.get("/reports/export.csv")
async def export_household_report_csv(
    user: CurrentUser,
    portfolio: PortfolioDep,
) -> PlainTextResponse:
    deals: list[dict[str, Any]] = []
    try:
        live = await portfolio.execute(user_id=user.id)
        for d in live.history_deals:
            deals.append(
                {
                    "ticket": d.ticket,
                    "symbol": d.symbol,
                    "profit": d.profit,
                    "confirmed": True,
                }
            )
    except Exception:
        deals = []
    trades = closed_trades_from_deals(deals)
    report = build_household_performance(trades)
    csv_text = export_performance_csv(report)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=household-attribution.csv"
        },
    )


@router.get("/emergency-stops")
async def get_emergency_stops(user: CurrentUser) -> dict[str, Any]:
    snap = get_emergency_stop_store().snapshot()
    # Tenant filter: only show this user's stop + global broker stops
    return {
        "user_armed": str(user.id) in snap["users"],
        "accounts": list(snap["accounts"]),
        "brokers": snap["brokers"],
        "audit_tail": [
            e
            for e in snap["audit_tail"]
            if e.get("scope") != "user" or e.get("scope_id") == str(user.id)
        ],
    }


@router.post("/emergency-stops/arm")
async def arm_emergency_stop(
    body: EmergencyStopBody,
    user: CurrentUser,
) -> dict[str, Any]:
    if not body.confirmed:
        return {"ok": False, "error": "confirmation_required"}
    scope_id = body.scope_id
    if body.scope == "user":
        scope_id = str(user.id)
    ev = get_emergency_stop_store().arm(
        scope=body.scope,
        scope_id=scope_id,
        reason=body.reason,
        actor_user_id=user.id,
    )
    return {
        "ok": True,
        "armed": True,
        "scope": ev.scope,
        "scope_id": ev.scope_id,
        "reason": ev.reason,
        "at": ev.at.isoformat(),
        "auto_close": False,
    }


@router.post("/emergency-stops/disarm")
async def disarm_emergency_stop(
    body: EmergencyStopBody,
    user: CurrentUser,
) -> dict[str, Any]:
    if not body.confirmed:
        return {"ok": False, "error": "confirmation_required"}
    scope_id = body.scope_id
    if body.scope == "user":
        scope_id = str(user.id)
    ev = get_emergency_stop_store().disarm(
        scope=body.scope,
        scope_id=scope_id,
        reason=body.reason,
        actor_user_id=user.id,
    )
    return {
        "ok": True,
        "armed": False,
        "scope": ev.scope,
        "scope_id": ev.scope_id,
        "reason": ev.reason,
        "at": ev.at.isoformat(),
        "auto_close": False,
    }
