"""Postgres persistence for public Live Market Chat."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text

from app.infrastructure.persistence.postgres_common import (
    PostgresUnitOfWorkBase,
    parse_datetime,
    parse_uuid,
    parse_uuid_optional,
)
from core.database.session import DatabaseManager


class PostgresMarketChatUnitOfWork(PostgresUnitOfWorkBase):
    def __init__(self, database: DatabaseManager) -> None:
        super().__init__(database)


def _row_to_message(row: Any) -> dict[str, Any]:
    created = parse_datetime(row["created_at"])
    return {
        "id": str(parse_uuid(row["id"])),
        "channel": str(row["channel"]),
        "user_id": str(parse_uuid(row["user_id"])),
        "display_name": str(row["display_name"] or "Trader"),
        "body": str(row["body"]),
        "parent_id": (
            str(parse_uuid_optional(row["parent_id"]))
            if row["parent_id"] is not None
            else None
        ),
        "status": str(row["status"]),
        "created_at": created.astimezone(UTC).replace(microsecond=0).isoformat(),
    }


class PostgresMarketChatRepository:
    def __init__(self, uow: PostgresMarketChatUnitOfWork) -> None:
        self._uow = uow

    async def list_visible(
        self,
        *,
        channel: str,
        limit: int = 80,
        before: datetime | None = None,
    ) -> list[dict[str, Any]]:
        session = self._uow._require_session()
        if before is None:
            result = await session.execute(
                text("""
                    SELECT id, channel, user_id, display_name, body, parent_id,
                           status, created_at
                    FROM live_market_chat_messages
                    WHERE channel = :channel AND status = 'visible'
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """),
                {"channel": channel, "limit": limit},
            )
        else:
            result = await session.execute(
                text("""
                    SELECT id, channel, user_id, display_name, body, parent_id,
                           status, created_at
                    FROM live_market_chat_messages
                    WHERE channel = :channel
                      AND status = 'visible'
                      AND created_at < :before
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """),
                {"channel": channel, "limit": limit, "before": before},
            )
        rows = [_row_to_message(r) for r in result.mappings().all()]
        rows.reverse()
        return rows

    async def insert(
        self,
        *,
        channel: str,
        user_id: UUID,
        display_name: str,
        body: str,
        parent_id: UUID | None,
    ) -> dict[str, Any]:
        session = self._uow._require_session()
        msg_id = uuid4()
        now = datetime.now(UTC)
        await session.execute(
            text("""
                INSERT INTO live_market_chat_messages (
                    id, channel, user_id, display_name, body, parent_id,
                    status, created_at, updated_at
                ) VALUES (
                    :id, :channel, :user_id, :display_name, :body, :parent_id,
                    'visible', :created_at, :updated_at
                )
                """),
            {
                "id": msg_id,
                "channel": channel,
                "user_id": user_id,
                "display_name": display_name,
                "body": body,
                "parent_id": parent_id,
                "created_at": now,
                "updated_at": now,
            },
        )
        return {
            "id": str(msg_id),
            "channel": channel,
            "user_id": str(user_id),
            "display_name": display_name,
            "body": body,
            "parent_id": str(parent_id) if parent_id else None,
            "status": "visible",
            "created_at": now.replace(microsecond=0).isoformat(),
        }

    async def add_report(
        self,
        *,
        message_id: UUID,
        reporter_id: UUID,
        reason: str,
        note: str,
    ) -> None:
        session = self._uow._require_session()
        await session.execute(
            text("""
                INSERT INTO live_market_chat_reports (
                    id, message_id, reporter_id, reason, note, created_at
                ) VALUES (
                    :id, :message_id, :reporter_id, :reason, :note, :created_at
                )
                ON CONFLICT (message_id, reporter_id) DO NOTHING
                """),
            {
                "id": uuid4(),
                "message_id": message_id,
                "reporter_id": reporter_id,
                "reason": reason,
                "note": note,
                "created_at": datetime.now(UTC),
            },
        )
