"""Live Market Chat API — public read, authenticated post."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.application.services.market_chat import (
    MarketChatService,
    require_authenticated_user_id,
)
from app.presentation.dependencies.auth import CurrentUser
from core.di.container import get_container

router = APIRouter(tags=["market-chat"])


def _service() -> MarketChatService:
    return MarketChatService(database=get_container().database)


class PostMarketChatBody(BaseModel):
    body: str = Field(min_length=1, max_length=500)
    channel: str = Field(default="xauusd", max_length=32)
    parent_id: str | None = None
    display_name: str | None = Field(default=None, max_length=64)


class ReportMarketChatBody(BaseModel):
    reason: str = Field(default="spam", max_length=32)
    note: str = Field(default="", max_length=500)


@router.get("/public/market/chat")
async def list_public_market_chat(
    service: Annotated[MarketChatService, Depends(_service)],
    channel: str = Query(default="xauusd"),
    limit: int = Query(default=80, ge=1, le=200),
) -> dict[str, Any]:
    """Public read of Live Market discussion — no authentication required."""
    return await service.list_messages(channel=channel, limit=limit)


@router.post("/market/chat")
async def post_market_chat(
    body: PostMarketChatBody,
    user: CurrentUser,
    service: Annotated[MarketChatService, Depends(_service)],
) -> dict[str, Any]:
    """Authenticated post — user_id always taken from the session, never the body."""
    uid = require_authenticated_user_id(user)
    email = getattr(user, "email", None)
    return await service.post_message(
        user_id=uid,
        display_name=body.display_name,
        email_fallback=str(email) if email else None,
        body=body.body,
        channel=body.channel,
        parent_id=body.parent_id,
    )


@router.post("/market/chat/{message_id}/report")
async def report_market_chat(
    message_id: str,
    body: ReportMarketChatBody,
    user: CurrentUser,
    service: Annotated[MarketChatService, Depends(_service)],
) -> dict[str, Any]:
    uid = require_authenticated_user_id(user)
    return await service.report_message(
        user_id=uid,
        message_id=message_id,
        reason=body.reason,
        note=body.note,
    )
