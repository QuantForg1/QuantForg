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
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.application.services import robot_control_service as rc
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/robot-control", tags=["robot-control"])


class ControlBody(BaseModel):
    reason: str = Field(default="", max_length=300)


@router.get("/accounts")
async def my_robot_accounts(user: CurrentUser) -> dict[str, Any]:
    uid = UUID(str(user.id))
    accounts = await asyncio.to_thread(rc.list_accounts, user_id=uid)
    events = await asyncio.to_thread(rc.recent_events, user_id=uid, limit=50)
    return {
        "accounts": accounts,
        "events": events,
        "states": sorted(rc.STATES),
        "actions": {k: sorted(v[0]) for k, v in rc.TRANSITIONS.items()},
        "positions_closed_by_controls": False,
    }


def _readiness_probe(request: Request) -> Any:
    gateway_account = None
    with contextlib.suppress(Exception):
        from core.di.container import get_container

        gateway_account = get_container().mt5_adapter.account_info()
    workers: list[dict[str, Any]] = []
    api = getattr(request.app.state, "mt5_worker_api", None)
    if api is not None:
        with contextlib.suppress(Exception):
            workers = list(api.ops_summary().get("workers") or [])

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
        probe = await asyncio.to_thread(_readiness_probe, request)
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
