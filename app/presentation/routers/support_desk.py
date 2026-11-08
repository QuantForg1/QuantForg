"""Client Support Desk API — authenticated customers only.

FAQ AI chat and ticket workflow. Never modifies trading, risk, or MT5.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Request

from app.application.dto.auth import AuthUserDTO
from app.domain.customer_operations.support_center import (
    SUPPORT_CATEGORIES,
    answer_support_faq,
    append_ticket_message,
    create_support_ticket,
    get_ticket_for_user,
    list_tickets_for_user,
    request_human_on_ticket,
)
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/support-desk", tags=["support-desk"])


def _ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return ""


def _user_id(user: AuthUserDTO) -> str:
    return str(user.id)


def _author(user: AuthUserDTO) -> str:
    return str(user.email or user.id)


@router.get("/tickets")
async def list_my_tickets(user: CurrentUser) -> dict[str, Any]:
    uid = _user_id(user)
    tickets = list_tickets_for_user(uid)
    return {
        "tickets": tickets,
        "count": len(tickets),
        "fabricated": False,
        "modifies_trading": False,
    }


@router.post("/tickets")
async def create_ticket(
    request: Request,
    user: CurrentUser,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    uid = _user_id(user)
    category = str(payload.get("category") or "general").lower()
    if category not in SUPPORT_CATEGORIES:
        category = "general"
    created = create_support_ticket(
        subject=str(payload.get("subject") or ""),
        customer_id=uid,
        user_id=uid,
        category=category,
        priority=str(payload.get("priority") or "normal"),
        operator=_author(user),
        ip=_ip(request),
        body=str(payload.get("body") or payload.get("message") or ""),
        ai_session_id=payload.get("ai_session_id"),
    )
    from app.domain.customer_operations.support_center import customer_ticket_view

    return customer_ticket_view(created)


@router.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: str, user: CurrentUser) -> dict[str, Any]:
    ticket = get_ticket_for_user(ticket_id, _user_id(user))
    if ticket is None:
        return {"ok": False, "error": "not_found"}
    return ticket


@router.post("/tickets/{ticket_id}/messages")
async def post_ticket_message(
    ticket_id: str,
    request: Request,
    user: CurrentUser,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    uid = _user_id(user)
    updated = append_ticket_message(
        ticket_id=ticket_id,
        body=str(payload.get("body") or payload.get("message") or ""),
        role="customer",
        author=_author(user),
        operator=_author(user),
        ip=_ip(request),
        customer_user_id=uid,
    )
    if updated is None:
        return {"ok": False, "error": "not_found"}
    from app.domain.customer_operations.support_center import customer_ticket_view

    return customer_ticket_view(updated)


@router.post("/tickets/{ticket_id}/request-human")
async def post_request_human(
    ticket_id: str,
    request: Request,
    user: CurrentUser,
) -> dict[str, Any]:
    updated = request_human_on_ticket(
        ticket_id=ticket_id,
        user_id=_user_id(user),
        operator=_author(user),
        ip=_ip(request),
    )
    if updated is None:
        return {"ok": False, "error": "not_found"}
    return updated


@router.post("/ai/chat")
async def ai_chat(
    _user: CurrentUser,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    return answer_support_faq(
        message=str(payload.get("message") or ""),
        session_id=payload.get("ai_session_id"),
    )


@router.get("/faq")
async def faq_catalog(_user: CurrentUser) -> dict[str, Any]:
    from app.domain.customer_operations.support_center import PLATFORM_HELP_FAQ

    items = [{"question": q, "answer": a} for q, a in PLATFORM_HELP_FAQ]
    return {
        "items": items,
        "suggested_questions": [q for q, _ in PLATFORM_HELP_FAQ[:5]],
        "fabricated": False,
    }
