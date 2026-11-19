"""Robot Control Center API: the caller's own accounts only.

GET  /robot-control/accounts          accounts + robot state + recent events
POST /robot-control/accounts/{id}/{action}
     action: pause | resume | stop | start | emergency_stop

The backend state is the source of truth. A control never closes a position
and never changes the global LIVE switch or another user's account.
"""

from __future__ import annotations

import asyncio
import contextlib
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.application.dto.auth import AuthUserDTO
from app.application.services import robot_control_service as rc
from app.application.services.blocking_io_offload import run_broker_read
from app.domain.enums.user import UserRole
from app.presentation.dependencies.auth import CurrentUser, require_roles

router = APIRouter(prefix="/robot-control", tags=["robot-control"])


class ControlBody(BaseModel):
    reason: str = Field(default="", max_length=300)


# Broker evidence must never hold the page hostage: accounts and controls come
# from the database; the gateway/worker read is bounded and optional.
EVIDENCE_TIMEOUT_S = 6.0


def _gateway_account() -> Any:
    from core.di.container import get_container

    return get_container().mt5_adapter.account_info()


def _workers(request: Request) -> list[dict[str, Any]]:
    api = getattr(request.app.state, "mt5_worker_api", None)
    if api is None:
        return []
    return list(api.ops_summary().get("workers") or [])


async def _evidence_async(
    request: Request,
) -> tuple[Any, list[dict[str, Any]], bool]:
    """(gateway_account, workers, complete). Fails soft, never blocks > 6 s."""

    async def gw() -> Any:
        return await asyncio.wait_for(
            run_broker_read(_gateway_account), timeout=EVIDENCE_TIMEOUT_S
        )

    async def wk() -> list[dict[str, Any]]:
        return await asyncio.wait_for(
            asyncio.to_thread(_workers, request), timeout=EVIDENCE_TIMEOUT_S
        )

    gw_res, wk_res = await asyncio.gather(gw(), wk(), return_exceptions=True)
    complete = not isinstance(gw_res, BaseException) and not isinstance(
        wk_res, BaseException
    )
    gateway_account = None if isinstance(gw_res, BaseException) else gw_res
    workers = [] if isinstance(wk_res, BaseException) else wk_res
    return gateway_account, workers, complete


def _evidence(request: Request) -> tuple[Any, list[dict[str, Any]]]:
    gateway_account = None
    with contextlib.suppress(Exception):
        gateway_account = _gateway_account()
    workers: list[dict[str, Any]] = []
    with contextlib.suppress(Exception):
        workers = _workers(request)
    return gateway_account, workers


@router.get("/accounts")
async def my_robot_accounts(user: CurrentUser, request: Request) -> dict[str, Any]:
    uid = UUID(str(user.id))
    (
        accounts,
        events,
        activity,
        entitlement,
        (gateway_account, workers, complete),
    ) = await asyncio.gather(
        asyncio.to_thread(rc.list_accounts, user_id=uid),
        asyncio.to_thread(rc.recent_events, user_id=uid, limit=50),
        _safe_activity(uid),
        _safe_entitlement(uid),
        _evidence_async(request),
    )
    for acct in accounts:
        acct["connection"] = rc.connection_state(
            {
                "id": acct["broker_account_id"],
                "external_account_id": acct.pop("_login", ""),
                "verification": acct.get("verification", ""),
            },
            gateway_account=gateway_account,
            workers=workers,
            evidence_available=complete,
        )
        acct["status"] = rc.robot_status(
            control_state=str(acct.get("robot_state") or ""),
            connection=acct["connection"],
            entitled=entitlement,
            execution_enabled=_execution_enabled(
                source=str(acct["connection"].get("source") or ""),
                environment=str(acct.get("environment") or ""),
            ),
        )
        acct["worker"] = _worker_health(workers, acct["broker_account_id"])
    return {
        "accounts": accounts,
        "events": [_public_event(e) for e in events],
        "activity": activity,
        "strategy": _strategy(),
        "subscription_active": entitlement,
        "broker_evidence": "complete" if complete else "unavailable",
        "states": sorted(rc.STATES),
        "actions": {k: sorted(v[0]) for k, v in rc.TRANSITIONS.items()},
        "positions_closed_by_controls": False,
    }


async def _safe_activity(uid: UUID) -> list[dict[str, Any]]:
    try:
        return await asyncio.to_thread(rc.recent_activity, user_id=uid, limit=20)
    except Exception:
        return []


async def _safe_entitlement(uid: UUID) -> bool | None:
    """True/False from billing; None when it could not be read."""
    try:
        from app.application.services.entitlements import check_trading_entitlement

        ent = await asyncio.to_thread(check_trading_entitlement, user_id=uid)
        return bool(ent.allowed)
    except Exception:
        return None


def _worker_health(
    workers: list[dict[str, Any]], broker_account_id: str
) -> dict[str, Any] | None:
    for w in workers:
        if str(w.get("broker_account_id")) == str(broker_account_id):
            return {
                "assigned": True,
                "connected": bool(w.get("connected")),
                "heartbeat_at": w.get("last_heartbeat_at") or w.get("heartbeat_at"),
            }
    return None


def _public_event(e: dict[str, Any]) -> dict[str, Any]:
    """Control history without internal readiness details."""
    readiness = e.get("readiness") or {}
    return {
        "broker_account_id": e.get("broker_account_id"),
        "action": e.get("action"),
        "state_before": e.get("state_before"),
        "state_after": e.get("state_after"),
        "reason": e.get("reason"),
        "verified": bool(readiness.get("ready")) if readiness else None,
        "at": e.get("at"),
    }


def _execution_enabled(*, source: str, environment: str) -> bool | None:
    """Can the path that serves this account submit orders right now?"""
    try:
        if source == "gateway":
            from app.domain.institutional_trading.live_trading_control import (
                get_live_trading_controller,
            )

            return bool(get_live_trading_controller().research_can_execute())
        if source == "worker":
            from core.config.settings import get_settings

            cfg = get_settings()
            if not bool(getattr(cfg, "multi_account_dispatch_enabled", False)):
                return False
            if environment.upper() == "LIVE":
                return bool(getattr(cfg, "multi_account_live_submit_enabled", False))
            return True
    except Exception:
        return None
    return None


def _strategy() -> dict[str, Any]:
    """The platform strategy every customer robot runs (no parameters)."""
    try:
        from core.config.settings import get_settings

        gold_only = bool(getattr(get_settings(), "gold_only_mode", True))
    except Exception:
        gold_only = True
    return {
        "name": "QuantForg Gold Intraday",
        "instruments": ["XAUUSD"] if gold_only else ["XAUUSD", "multi-asset"],
        "style": "Intraday · every trade has a stop-loss and a target",
        "assigned_by": "platform",
    }


def _readiness_probe(request: Request) -> Any:
    gateway_account, workers = _evidence(request)

    def probe(account: dict[str, Any]) -> rc.Readiness:
        return rc.account_readiness(
            account, gateway_account=gateway_account, workers=workers
        )

    return probe


@router.post("/accounts/{broker_account_id}/{action}")
async def control_robot(
    broker_account_id: UUID,
    action: str,
    body: ControlBody,
    user: CurrentUser,
    request: Request,
) -> dict[str, Any]:
    uid = UUID(str(user.id))
    probe = None
    if action in {"resume", "start"}:
        # Resume/Start must re-verify readiness; if evidence cannot be read the
        # probe sees no account and refuses (fail closed).
        probe = await run_broker_read(_readiness_probe, request)
    try:
        return await asyncio.to_thread(
            rc.apply_action,
            user_id=uid,
            broker_account_id=broker_account_id,
            action=action,
            reason=body.reason,
            readiness_probe=probe,
        )
    except rc.RobotControlError as exc:
        raise HTTPException(
            status_code=exc.status, detail={"code": exc.code, "message": str(exc)}
        ) from exc


class VerifiedCommissionBody(BaseModel):
    usd_per_order: Decimal = Field(ge=0, le=100)
    source: str
    evidence: str = Field(min_length=10, max_length=500)


@router.post("/admin/accounts/{broker_account_id}/verified-commission")
async def set_verified_commission(
    broker_account_id: UUID,
    body: VerifiedCommissionBody,
    owner: Annotated[AuthUserDTO, Depends(require_roles(UserRole.OWNER))],
) -> dict[str, Any]:
    """Owner records the broker-verified per-order commission for an account."""
    from app.application.services.account_commission import (
        record_verified_commission,
    )

    try:
        recorded = await asyncio.to_thread(
            record_verified_commission,
            broker_account_id=broker_account_id,
            usd_per_order=body.usd_per_order,
            source=body.source,
            evidence=body.evidence,
            actor_id=UUID(str(owner.id)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "verified_commission": recorded}
