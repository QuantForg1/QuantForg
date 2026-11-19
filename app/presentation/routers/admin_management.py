"""Admin portal API: customers, feature access and broker accounts.

Owner/admin only (``require_roles`` also downgrades non-designated owner or
admin roles). Every write is audited and needs a reason. See
``app.application.services.admin_management`` for the safety rules.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.application.dto.auth import AuthUserDTO
from app.application.services import admin_management as am
from app.domain.enums.user import UserRole
from app.presentation.dependencies.auth import require_roles

router = APIRouter(prefix="/admin/manage", tags=["admin-management"])

AdminUser = Annotated[
    AuthUserDTO, Depends(require_roles(UserRole.OWNER, UserRole.ADMIN))
]


class StatusBody(BaseModel):
    action: str = Field(pattern="^(suspend|reactivate|deactivate)$")
    reason: str = Field(min_length=3, max_length=500)


class UpdateBody(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    role: str | None = Field(default=None, max_length=16)
    reason: str = Field(min_length=3, max_length=500)


class AccessBody(BaseModel):
    feature: str = Field(max_length=32)
    allowed: bool
    reason: str = Field(min_length=3, max_length=500)


class BrokerBody(BaseModel):
    action: str = Field(pattern="^(disable|enable|remove)$")
    reason: str = Field(min_length=3, max_length=500)


def _actor(user: AuthUserDTO, request: Request) -> am.Actor:
    ip = request.headers.get("x-forwarded-for") or (
        request.client.host if request.client else ""
    )
    return am.Actor(
        user_id=user.id,
        email=user.email or "",
        ip=(ip or "").split(",")[0].strip(),
        user_agent=request.headers.get("user-agent", ""),
    )


async def _run(fn: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return await asyncio.to_thread(fn, *args, **kwargs)
    except am.AdminActionError as exc:
        raise HTTPException(
            status_code=exc.status, detail={"code": exc.code, "message": exc.message}
        ) from exc


@router.get("/users")
async def admin_users(
    _user: AdminUser,
    q: str = Query(default="", max_length=120),
    status: str = Query(default="", max_length=20),
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, Any]:
    result: dict[str, Any] = await _run(
        am.list_users, query=q, status=status, limit=limit
    )
    return result


@router.get("/users/{user_id}")
async def admin_user(user_id: UUID, _user: AdminUser) -> dict[str, Any]:
    result: dict[str, Any] = await _run(am.user_detail, user_id)
    return result


@router.patch("/users/{user_id}")
async def admin_update_user(
    user_id: UUID, body: UpdateBody, user: AdminUser, request: Request
) -> dict[str, Any]:
    result: dict[str, Any] = await _run(
        am.update_user,
        user_id,
        display_name=body.display_name,
        role=body.role,
        reason=body.reason,
        actor=_actor(user, request),
    )
    return result


@router.post("/users/{user_id}/status")
async def admin_user_status(
    user_id: UUID, body: StatusBody, user: AdminUser, request: Request
) -> dict[str, Any]:
    result: dict[str, Any] = await _run(
        am.set_user_status,
        user_id,
        body.action,
        reason=body.reason,
        actor=_actor(user, request),
    )
    return result


@router.post("/users/{user_id}/access")
async def admin_user_access(
    user_id: UUID, body: AccessBody, user: AdminUser, request: Request
) -> dict[str, Any]:
    result: dict[str, Any] = await _run(
        am.set_access,
        user_id,
        body.feature,
        allowed=body.allowed,
        reason=body.reason,
        actor=_actor(user, request),
    )
    return result


@router.get("/brokers")
async def admin_brokers(
    _user: AdminUser, include_removed: bool = Query(default=False)
) -> dict[str, Any]:
    result: dict[str, Any] = await _run(
        am.list_brokers, include_removed=include_removed
    )
    return result


@router.post("/brokers/{broker_account_id}")
async def admin_broker_action(
    broker_account_id: UUID, body: BrokerBody, user: AdminUser, request: Request
) -> dict[str, Any]:
    result: dict[str, Any] = await _run(
        am.broker_action,
        broker_account_id,
        body.action,
        reason=body.reason,
        actor=_actor(user, request),
    )
    return result


@router.get("/audit")
async def admin_audit(
    _user: AdminUser, limit: int = Query(default=100, ge=1, le=200)
) -> dict[str, Any]:
    items = await _run(am.recent_audit, limit=limit)
    return {"items": items}
