"""Postgres persistence for Portfolio sync snapshots."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.domain.entities.mt5_portfolio import PortfolioSyncRecord
from app.infrastructure.persistence.postgres_common import (
    PostgresUnitOfWorkBase,
    as_json,
    json_dict,
    parse_datetime,
    parse_decimal,
    parse_uuid,
)
from core.database.session import DatabaseManager


def _sync_from_row(row: Any) -> PortfolioSyncRecord:
    created = parse_datetime(row["created_at"])
    return PortfolioSyncRecord(
        id=parse_uuid(row["id"]),
        user_id=parse_uuid(row["user_id"]),
        login=int(row["login"]),
        balance=parse_decimal(row["balance"]),
        equity=parse_decimal(row["equity"]),
        margin=parse_decimal(row["margin"]),
        free_margin=parse_decimal(row["free_margin"]),
        margin_level=parse_decimal(row["margin_level"]),
        profit=parse_decimal(row["profit"]),
        leverage=int(row["leverage"]),
        position_count=int(row["position_count"] or 0),
        pending_order_count=int(row["pending_order_count"] or 0),
        history_order_count=int(row["history_order_count"] or 0),
        history_deal_count=int(row["history_deal_count"] or 0),
        snapshot=json_dict(row["snapshot"]),
        synced_at=parse_datetime(row["synced_at"]),
        created_at=created,
        updated_at=created,
    )


class PostgresPortfolioSyncRepository:
    def __init__(self, uow: PostgresPortfolioUnitOfWork) -> None:
        self._uow = uow

    async def add(self, record: PortfolioSyncRecord) -> PortfolioSyncRecord:
        session = self._uow._require_session()
        await session.execute(
            text("""
                INSERT INTO portfolio_syncs (
                    id, user_id, login, balance, equity, margin, free_margin,
                    margin_level, profit, leverage, position_count,
                    pending_order_count, history_order_count, history_deal_count,
                    snapshot, synced_at, created_at
                ) VALUES (
                    :id, :user_id, :login, :balance, :equity, :margin, :free_margin,
                    :margin_level, :profit, :leverage, :position_count,
                    :pending_order_count, :history_order_count, :history_deal_count,
                    CAST(:snapshot AS jsonb), :synced_at, :created_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    login = EXCLUDED.login,
                    balance = EXCLUDED.balance,
                    equity = EXCLUDED.equity,
                    margin = EXCLUDED.margin,
                    free_margin = EXCLUDED.free_margin,
                    margin_level = EXCLUDED.margin_level,
                    profit = EXCLUDED.profit,
                    leverage = EXCLUDED.leverage,
                    position_count = EXCLUDED.position_count,
                    pending_order_count = EXCLUDED.pending_order_count,
                    history_order_count = EXCLUDED.history_order_count,
                    history_deal_count = EXCLUDED.history_deal_count,
                    snapshot = EXCLUDED.snapshot,
                    synced_at = EXCLUDED.synced_at
                """),
            {
                "id": str(record.id),
                "user_id": str(record.user_id),
                "login": record.login,
                "balance": str(record.balance),
                "equity": str(record.equity),
                "margin": str(record.margin),
                "free_margin": str(record.free_margin),
                "margin_level": str(record.margin_level),
                "profit": str(record.profit),
                "leverage": record.leverage,
                "position_count": record.position_count,
                "pending_order_count": record.pending_order_count,
                "history_order_count": record.history_order_count,
                "history_deal_count": record.history_deal_count,
                "snapshot": as_json(record.snapshot),
                "synced_at": record.synced_at,
                "created_at": record.created_at,
            },
        )
        return record

    async def get_latest_for_user(self, user_id: UUID) -> PortfolioSyncRecord | None:
        session = self._uow._require_session()
        result = await session.execute(
            text("""
                SELECT * FROM portfolio_syncs
                WHERE user_id = :user_id
                ORDER BY synced_at DESC
                LIMIT 1
                """),
            {"user_id": str(user_id)},
        )
        row = result.mappings().first()
        return _sync_from_row(row) if row else None

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 20
    ) -> list[PortfolioSyncRecord]:
        session = self._uow._require_session()
        result = await session.execute(
            text("""
                SELECT * FROM portfolio_syncs
                WHERE user_id = :user_id
                ORDER BY synced_at DESC
                LIMIT :limit
                """),
            {"user_id": str(user_id), "limit": limit},
        )
        return [_sync_from_row(r) for r in result.mappings().all()]


class PostgresPortfolioUnitOfWork(PostgresUnitOfWorkBase):
    def __init__(self, database: DatabaseManager) -> None:
        super().__init__(database)
        self.syncs = PostgresPortfolioSyncRepository(self)


class PostgresPortfolioUnitOfWorkFactory:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    def __call__(self) -> PostgresPortfolioUnitOfWork:
        return PostgresPortfolioUnitOfWork(self._database)
