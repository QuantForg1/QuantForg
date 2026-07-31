"""Customer Operations Platform API — additive enterprise ops.

Never modifies Trading Engine, AI, OMS, MT5, Risk, pricing, or licensing rules.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Query, Request

from app.application.dto.auth import AuthUserDTO
from app.application.services.customer_operations_platform import (
    build_customer_operations_platform,
    build_customer_ops_noc_panels,
)
from app.domain.customer_operations.analytics import build_enterprise_analytics
from app.domain.customer_operations.broker_center import build_broker_connection_center
from app.domain.customer_operations.cop_audit import list_cop_audit
from app.domain.customer_operations.customer_fleet import build_customer_fleet
from app.domain.customer_operations.customer_workspace import build_customer_workspace
from app.domain.customer_operations.license_center import (
    add_license_internal_note,
    build_license_center,
    license_manual_action,
)
from app.domain.customer_operations.notifications_center import (
    build_notifications_center,
    publish_notification,
)
from app.domain.customer_operations.support_center import (
    build_support_center,
    create_support_ticket,
    update_support_ticket,
)
from app.domain.enums.user import UserRole
from app.presentation.dependencies.auth import require_roles

router = APIRouter(prefix="/customer-ops", tags=["customer-operations"])

OperatorUser = Annotated[
    AuthUserDTO,
    Depends(require_roles(UserRole.OWNER, UserRole.ADMIN)),
]


def _operator(user: AuthUserDTO) -> str:
    return str(getattr(user, "email", None) or getattr(user, "id", None) or "operator")


def _ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return ""


@router.get("/platform")
async def platform_dashboard(_user: OperatorUser) -> dict[str, Any]:
    return await build_customer_operations_platform()


@router.get("/noc-panels")
async def noc_panels(_user: OperatorUser) -> dict[str, Any]:
    return await build_customer_ops_noc_panels()


@router.get("/fleet")
async def fleet(
    _user: OperatorUser,
    country: str | None = Query(default=None),
    broker: str | None = Query(default=None),
    status: str | None = Query(default=None),
    license: str | None = Query(default=None),
) -> dict[str, Any]:
    return await build_customer_fleet(
        country=country,
        broker=broker,
        status=status,
        license_status=license,
    )


@router.get("/customers/{customer_id}")
async def customer_workspace(
    customer_id: str, _user: OperatorUser
) -> dict[str, Any]:
    return await build_customer_workspace(customer_id)


@router.get("/licenses")
async def licenses(_user: OperatorUser) -> dict[str, Any]:
    return await build_license_center()


@router.post("/licenses/{license_id}/notes")
async def license_notes(
    license_id: str,
    request: Request,
    user: OperatorUser,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    return await add_license_internal_note(
        license_id=license_id,
        note=str(payload.get("note") or ""),
        operator=_operator(user),
        ip=_ip(request),
    )


@router.post("/licenses/{license_id}/action")
async def license_action(
    license_id: str,
    request: Request,
    user: OperatorUser,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    """Manual approval/suspend/revoke — existing License domain methods only."""
    return await license_manual_action(
        license_id=license_id,
        action=str(payload.get("action") or ""),
        operator=_operator(user),
        ip=_ip(request),
        reason=str(payload.get("reason") or ""),
    )


@router.get("/brokers")
async def brokers(_user: OperatorUser) -> dict[str, Any]:
    return await build_broker_connection_center()


@router.get("/support")
async def support(_user: OperatorUser) -> dict[str, Any]:
    return build_support_center()


@router.post("/support/tickets")
async def support_create(
    request: Request,
    user: OperatorUser,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    return create_support_ticket(
        subject=str(payload.get("subject") or ""),
        customer_id=payload.get("customer_id"),
        priority=str(payload.get("priority") or "normal"),
        operator=_operator(user),
        ip=_ip(request),
        body=str(payload.get("body") or ""),
    )


@router.post("/support/tickets/{ticket_id}")
async def support_update(
    ticket_id: str,
    request: Request,
    user: OperatorUser,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    updated = update_support_ticket(
        ticket_id=ticket_id,
        operator=_operator(user),
        ip=_ip(request),
        status=payload.get("status"),
        assigned_staff=payload.get("assigned_staff"),
        priority=payload.get("priority"),
        internal_note=payload.get("internal_note"),
        attachment_name=payload.get("attachment_name"),
    )
    return updated or {"ok": False, "error": "not_found"}


@router.get("/notifications")
async def notifications(
    _user: OperatorUser,
    channel: str | None = Query(default=None),
) -> dict[str, Any]:
    return build_notifications_center(channel=channel)


@router.post("/notifications")
async def notifications_publish(
    request: Request,
    user: OperatorUser,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    return publish_notification(
        channel=str(payload.get("channel") or "operator"),
        title=str(payload.get("title") or ""),
        message=str(payload.get("message") or ""),
        operator=_operator(user),
        customer_id=payload.get("customer_id"),
        ip=_ip(request),
        severity=str(payload.get("severity") or "info"),
    )


@router.get("/analytics")
async def analytics(_user: OperatorUser) -> dict[str, Any]:
    return await build_enterprise_analytics()


@router.get("/audit")
async def audit(
    _user: OperatorUser,
    limit: int = Query(default=200, ge=1, le=2000),
) -> dict[str, Any]:
    return list_cop_audit(limit=limit)
