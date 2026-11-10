"""Public Live Market Chat — read without login; post when authenticated."""

from __future__ import annotations

import re
import time
from collections import defaultdict
from typing import Any
from uuid import UUID

from app.domain.exceptions.auth import AuthorizationError
from app.domain.exceptions.base import ValidationError
from app.infrastructure.persistence.postgres_market_chat import (
    PostgresMarketChatRepository,
    PostgresMarketChatUnitOfWork,
)
from core.database.session import DatabaseManager
from core.logging import get_logger

logger = get_logger(__name__)

_CHANNEL_RE = re.compile(r"^[a-z0-9_-]{2,32}$")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_DEFAULT_CHANNEL = "xauusd"
_POST_WINDOW_SEC = 60.0
_POST_LIMIT = 8

_post_buckets: dict[str, list[float]] = defaultdict(list)


def normalize_channel(raw: str | None) -> str:
    channel = (raw or _DEFAULT_CHANNEL).strip().lower()
    if not _CHANNEL_RE.match(channel):
        raise ValidationError(
            "Invalid market chat channel",
            details={"channel": channel},
        )
    return channel


def sanitize_body(raw: str) -> str:
    body = _CONTROL_RE.sub("", (raw or "")).strip()
    body = re.sub(r"\s+", " ", body)
    if not body:
        raise ValidationError("Message cannot be empty")
    if len(body) > 500:
        raise ValidationError(
            "Message too long (max 500 characters)",
            details={"length": len(body)},
        )
    return body


def sanitize_display_name(raw: str | None, fallback: str) -> str:
    name = _CONTROL_RE.sub("", (raw or "").strip())
    name = re.sub(r"\s+", " ", name)
    if not name:
        name = (fallback or "Trader").strip() or "Trader"
    return name[:64]


def _enforce_rate_limit(user_id: str) -> None:
    now = time.monotonic()
    bucket = _post_buckets[user_id]
    _post_buckets[user_id] = [t for t in bucket if now - t < _POST_WINDOW_SEC]
    if len(_post_buckets[user_id]) >= _POST_LIMIT:
        raise ValidationError(
            "Too many chat messages. Please wait a moment.",
            code="rate_limited",
            details={"window_seconds": int(_POST_WINDOW_SEC), "limit": _POST_LIMIT},
        )
    _post_buckets[user_id].append(now)


class MarketChatService:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    async def list_messages(
        self,
        *,
        channel: str = _DEFAULT_CHANNEL,
        limit: int = 80,
    ) -> dict[str, Any]:
        channel = normalize_channel(channel)
        limit = max(1, min(int(limit), 200))
        async with PostgresMarketChatUnitOfWork(self._database) as uow:
            repo = PostgresMarketChatRepository(uow)
            messages = await repo.list_visible(channel=channel, limit=limit)
            await uow.commit()
        return {
            "ok": True,
            "channel": channel,
            "auth_required_to_post": True,
            "messages": messages,
            "count": len(messages),
        }

    async def post_message(
        self,
        *,
        user_id: UUID,
        display_name: str | None,
        email_fallback: str | None,
        body: str,
        channel: str = _DEFAULT_CHANNEL,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        channel = normalize_channel(channel)
        clean = sanitize_body(body)
        name = sanitize_display_name(
            display_name,
            (email_fallback or "Trader").split("@", 1)[0],
        )
        _enforce_rate_limit(str(user_id))
        parent_uuid: UUID | None = None
        if parent_id:
            try:
                parent_uuid = UUID(str(parent_id))
            except ValueError as exc:
                raise ValidationError("Invalid parent_id") from exc

        async with PostgresMarketChatUnitOfWork(self._database) as uow:
            repo = PostgresMarketChatRepository(uow)
            message = await repo.insert(
                channel=channel,
                user_id=user_id,
                display_name=name,
                body=clean,
                parent_id=parent_uuid,
            )
            await uow.commit()
        logger.info(
            "market_chat_posted channel=%s user_id=%s",
            channel,
            str(user_id),
        )
        return {"ok": True, "message": message}

    async def report_message(
        self,
        *,
        user_id: UUID,
        message_id: str,
        reason: str = "spam",
        note: str = "",
    ) -> dict[str, Any]:
        try:
            mid = UUID(str(message_id))
        except ValueError as exc:
            raise ValidationError("Invalid message_id") from exc
        reason_clean = (reason or "spam").strip().lower()
        if reason_clean not in {"spam", "abuse", "off_topic", "other"}:
            raise ValidationError("Invalid report reason")
        note_clean = sanitize_body(note) if note.strip() else ""
        if note_clean and len(note_clean) > 500:
            raise ValidationError("Report note too long")
        async with PostgresMarketChatUnitOfWork(self._database) as uow:
            repo = PostgresMarketChatRepository(uow)
            await repo.add_report(
                message_id=mid,
                reporter_id=user_id,
                reason=reason_clean,
                note=note_clean,
            )
            await uow.commit()
        return {"ok": True}


def require_authenticated_user_id(user: Any) -> UUID:
    uid = getattr(user, "id", None)
    if uid is None:
        raise AuthorizationError("Authentication required to post")
    return uid if isinstance(uid, UUID) else UUID(str(uid))
