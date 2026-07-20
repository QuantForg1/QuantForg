"""Postgres persistence for Execution Audit Engine."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.domain.entities.execution_audit import ExecutionAudit
from app.domain.enums.execution import ExecutionAuditStage
from app.infrastructure.persistence.postgres_common import (
    PostgresUnitOfWorkBase,
    as_json,
    json_dict,
    parse_datetime,
    parse_uuid,
)
from core.database.session import DatabaseManager


def _audit_from_row(row: Any) -> ExecutionAudit:
    created = parse_datetime(row["created_at"])
    order_ticket = row["order_ticket"]
    deal_ticket = row["deal_ticket"]
    return ExecutionAudit(
        id=parse_uuid(row["id"]),
        user_id=parse_uuid(row["user_id"]),
        request_id=str(row["request_id"]),
        stage=ExecutionAuditStage(str(row["stage"])),
        symbol=str(row["symbol"] or ""),
        side=str(row["side"] or ""),
        volume=str(row["volume"] or ""),
        outcome=str(row["outcome"] or ""),
        retcode=int(row["retcode"] or 0),
        order_ticket=int(order_ticket) if order_ticket is not None else None,
        deal_ticket=int(deal_ticket) if deal_ticket is not None else None,
        latency_ms=(
            float(row["latency_ms"]) if row["latency_ms"] is not None else None
        ),
        gateway_latency_ms=(
            float(row["gateway_latency_ms"])
            if row["gateway_latency_ms"] is not None
            else None
        ),
        railway_processing_ms=(
            float(row["railway_processing_ms"])
            if row["railway_processing_ms"] is not None
            else None
        ),
        cloudflare_latency_ms=(
            float(row["cloudflare_latency_ms"])
            if row["cloudflare_latency_ms"] is not None
            else None
        ),
        spread=str(row["spread"]) if row["spread"] is not None else None,
        slippage=str(row["slippage"]) if row["slippage"] is not None else None,
        commission=str(row["commission"]) if row["commission"] is not None else None,
        swap=str(row["swap"]) if row["swap"] is not None else None,
        margin_used=(
            str(row["margin_used"]) if row["margin_used"] is not None else None
        ),
        free_margin=(
            str(row["free_margin"]) if row["free_margin"] is not None else None
        ),
        balance=str(row["balance"]) if row["balance"] is not None else None,
        equity=str(row["equity"]) if row["equity"] is not None else None,
        leverage=str(row["leverage"]) if row["leverage"] is not None else None,
        broker_server_time=(
            str(row["broker_server_time"])
            if row["broker_server_time"] is not None
            else None
        ),
        market_session=(
            str(row["market_session"]) if row["market_session"] is not None else None
        ),
        execution_route=str(row["execution_route"] or "mt5_gateway"),
        payload_in=json_dict(row["payload_in"]),
        payload_out=json_dict(row["payload_out"]),
        related_ids=json_dict(row["related_ids"]),
        created_at=created,
        updated_at=created,
    )


class PostgresExecutionAuditRepository:
    def __init__(self, uow: PostgresExecutionAuditUnitOfWork) -> None:
        self._uow = uow

    async def add(self, audit: ExecutionAudit) -> ExecutionAudit:
        session = self._uow._require_session()
        result = await session.execute(
            text("""
                INSERT INTO execution_audits (
                    id, user_id, request_id, stage, symbol, side, volume, outcome,
                    retcode, order_ticket, deal_ticket, latency_ms,
                    gateway_latency_ms, railway_processing_ms, cloudflare_latency_ms,
                    spread, slippage, commission, swap, margin_used, free_margin,
                    balance, equity, leverage, broker_server_time, market_session,
                    execution_route, payload_in, payload_out, related_ids, created_at
                ) VALUES (
                    :id, :user_id, :request_id, :stage, :symbol, :side, :volume,
                    :outcome, :retcode, :order_ticket, :deal_ticket, :latency_ms,
                    :gateway_latency_ms, :railway_processing_ms,
                    :cloudflare_latency_ms, :spread, :slippage, :commission, :swap,
                    :margin_used, :free_margin, :balance, :equity, :leverage,
                    :broker_server_time, :market_session, :execution_route,
                    CAST(:payload_in AS jsonb), CAST(:payload_out AS jsonb),
                    CAST(:related_ids AS jsonb), :created_at
                )
                ON CONFLICT (user_id, request_id, stage) DO NOTHING
                RETURNING *
                """),
            {
                "id": str(audit.id),
                "user_id": str(audit.user_id),
                "request_id": audit.request_id,
                "stage": audit.stage.value,
                "symbol": audit.symbol,
                "side": audit.side,
                "volume": audit.volume,
                "outcome": audit.outcome,
                "retcode": audit.retcode,
                "order_ticket": audit.order_ticket,
                "deal_ticket": audit.deal_ticket,
                "latency_ms": audit.latency_ms,
                "gateway_latency_ms": audit.gateway_latency_ms,
                "railway_processing_ms": audit.railway_processing_ms,
                "cloudflare_latency_ms": audit.cloudflare_latency_ms,
                "spread": audit.spread,
                "slippage": audit.slippage,
                "commission": audit.commission,
                "swap": audit.swap,
                "margin_used": audit.margin_used,
                "free_margin": audit.free_margin,
                "balance": audit.balance,
                "equity": audit.equity,
                "leverage": audit.leverage,
                "broker_server_time": audit.broker_server_time,
                "market_session": audit.market_session,
                "execution_route": audit.execution_route,
                "payload_in": as_json(audit.payload_in),
                "payload_out": as_json(audit.payload_out),
                "related_ids": as_json(audit.related_ids),
                "created_at": audit.created_at,
            },
        )
        row = result.mappings().first()
        if row is not None:
            return _audit_from_row(row)
        existing = await session.execute(
            text("""
                SELECT * FROM execution_audits
                WHERE user_id = :user_id
                  AND request_id = :request_id
                  AND stage = :stage
                LIMIT 1
                """),
            {
                "user_id": str(audit.user_id),
                "request_id": audit.request_id,
                "stage": audit.stage.value,
            },
        )
        existing_row = existing.mappings().first()
        if existing_row is not None:
            return _audit_from_row(existing_row)
        return audit

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 50
    ) -> list[ExecutionAudit]:
        session = self._uow._require_session()
        result = await session.execute(
            text("""
                SELECT * FROM execution_audits
                WHERE user_id = :user_id
                ORDER BY created_at DESC
                LIMIT :limit
                """),
            {"user_id": str(user_id), "limit": max(1, min(limit, 500))},
        )
        return [_audit_from_row(r) for r in result.mappings().all()]

    async def list_by_request_id(
        self, user_id: UUID, request_id: str
    ) -> list[ExecutionAudit]:
        session = self._uow._require_session()
        result = await session.execute(
            text("""
                SELECT * FROM execution_audits
                WHERE user_id = :user_id AND request_id = :request_id
                ORDER BY created_at ASC
                """),
            {"user_id": str(user_id), "request_id": request_id.strip()},
        )
        return [_audit_from_row(r) for r in result.mappings().all()]

    async def list_recent(self, *, limit: int = 500) -> list[ExecutionAudit]:
        session = self._uow._require_session()
        result = await session.execute(
            text("""
                SELECT * FROM execution_audits
                ORDER BY created_at DESC
                LIMIT :limit
                """),
            {"limit": max(1, min(limit, 2000))},
        )
        return [_audit_from_row(r) for r in result.mappings().all()]


class PostgresExecutionAuditUnitOfWork(PostgresUnitOfWorkBase):
    def __init__(self, database: DatabaseManager) -> None:
        super().__init__(database)
        self.audits = PostgresExecutionAuditRepository(self)


class PostgresExecutionAuditUnitOfWorkFactory:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    def __call__(self) -> PostgresExecutionAuditUnitOfWork:
        return PostgresExecutionAuditUnitOfWork(self._database)
