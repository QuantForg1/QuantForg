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
    accounts, events, (gateway_account, workers, complete) = await asyncio.gather(
        asyncio.to_thread(rc.list_accounts, user_id=uid),
        asyncio.to_thread(rc.recent_events, user_id=uid, limit=50),
        _evidence_async(request),
    )
    for acct in accounts:
        acct["connection"] = rc.connection_state(
            {
                "id": acct["broker_account_id"],
                "external_account_id": acct.pop("_login", ""),
            },
            gateway_account=gateway_account,
            workers=workers,
            evidence_available=complete,
        )
    return {
        "accounts": accounts,
        "events": events,
        "broker_evidence": "complete" if complete else "unavailable",
        "states": sorted(rc.STATES),
        "actions": {k: sorted(v[0]) for k, v in rc.TRANSITIONS.items()},
        "positions_closed_by_controls": False,
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
