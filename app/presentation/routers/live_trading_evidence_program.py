"""Institutional Live Trading Readiness & Evidence API.

Additive observe-only. Never forces trades, lowers thresholds, or changes
trading / AI / OMS / MT5 behaviour.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.application.dto.auth import AuthUserDTO
from app.domain.enums.user import UserRole
from app.domain.live_trading_evidence.evidence_dashboard import (
    build_evidence_dashboard,
)
from app.domain.live_trading_evidence.investigation import investigate_trade
from app.domain.live_trading_evidence.platform import (
    build_live_trading_evidence_noc_panels,
    build_live_trading_evidence_program,
)
from app.domain.live_trading_evidence.rejected_repository import (
    sync_and_list_rejections,
)
from app.domain.live_trading_evidence.trade_repository import (
    get_trade,
    sync_and_list_trades,
)
from app.presentation.dependencies.auth import require_roles

router = APIRouter(
    prefix="/live-trading-evidence",
    tags=["live-trading-evidence"],
)

OperatorUser = Annotated[
    AuthUserDTO,
    Depends(require_roles(UserRole.OWNER, UserRole.ADMIN)),
]


@router.get("/program")
async def program(_user: OperatorUser) -> dict[str, Any]:
    return await build_live_trading_evidence_program()


@router.get("/trades")
async def trades(
    _user: OperatorUser,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    return sync_and_list_trades(limit=limit)


@router.get("/trades/{trade_id}")
async def trade_detail(trade_id: str, _user: OperatorUser) -> dict[str, Any]:
    row = get_trade(trade_id)
    if not row:
        return {"ok": False, "error": "not_found", "fabricated": False}
    return {"ok": True, "trade": row, "fabricated": False}


@router.get("/investigate/{trade_id}")
async def investigate(trade_id: str, _user: OperatorUser) -> dict[str, Any]:
    return investigate_trade(trade_id)


@router.get("/rejections")
async def rejections(
    _user: OperatorUser,
    limit: int = Query(default=150, ge=1, le=500),
) -> dict[str, Any]:
    return sync_and_list_rejections(limit=limit)


@router.get("/dashboard")
async def dashboard(_user: OperatorUser) -> dict[str, Any]:
    return build_evidence_dashboard()


@router.get("/readiness")
async def readiness(_user: OperatorUser) -> dict[str, Any]:
    pack = await build_live_trading_evidence_program()
    return pack.get("production_readiness") or {}


@router.get("/noc-panels")
async def noc_panels(_user: OperatorUser) -> dict[str, Any]:
    return await build_live_trading_evidence_noc_panels()
