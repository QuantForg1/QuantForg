"""Postgres persistence for MT5 connections and order validations."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.domain.entities.mt5 import MT5Connection
from app.domain.entities.mt5_order import TradeValidation
from app.domain.enums.mt5 import MT5ConnectionStatus
from app.infrastructure.persistence.postgres_common import (
    PostgresUnitOfWorkBase,
    as_json,
    json_dict,
    json_list,
    parse_datetime,
    parse_datetime_optional,
    parse_decimal,
    parse_uuid,
)
from core.database.session import DatabaseManager


def _connection_from_row(row: Any) -> MT5Connection:
    return MT5Connection(
        id=parse_uuid(row["id"]),
        user_id=parse_uuid(row["user_id"]),
        login=int(row["login"]),
        server=str(row["server"]),
        status=MT5ConnectionStatus(str(row["status"])),
        session_ref=str(row["session_ref"] or ""),
        terminal_path=str(row["terminal_path"] or ""),
        terminal_build=(
            int(row["terminal_build"]) if row["terminal_build"] is not None else None
        ),
        terminal_version=str(row["terminal_version"] or ""),
        latency_ms=(
            float(row["latency_ms"]) if row["latency_ms"] is not None else None
        ),
        last_heartbeat_at=parse_datetime_optional(row["last_heartbeat_at"]),
        connected=bool(row["connected"]),
        login_status=str(row["login_status"] or "logged_out"),
        last_error=str(row["last_error"] or ""),
        history=[],
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def _validation_from_row(row: Any) -> TradeValidation:
    created = parse_datetime(row["created_at"])
    return TradeValidation(
        id=parse_uuid(row["id"]),
        user_id=parse_uuid(row["user_id"]),
        symbol=str(row["symbol"]),
        side=str(row["side"]),
        order_type=str(row["order_type"] or "market"),
        volume=parse_decimal(row["volume"]),
        valid=bool(row["valid"]),
        retcode=int(row["retcode"] or 0),
        expected_margin=parse_decimal(row["expected_margin"], "0"),
        estimated_profit=parse_decimal(row["estimated_profit"], "0"),
        messages=[str(m) for m in json_list(row["messages"])],
        checks={str(k): bool(v) for k, v in json_dict(row["checks"]).items()},
        request_snapshot=json_dict(row["request_snapshot"]),
        validated_at=parse_datetime(row["validated_at"]),
        created_at=created,
        updated_at=created,
    )


_CONNECTION_UPSERT_SQL = """
INSERT INTO mt5_connections (
    id, user_id, login, server, status, session_ref, terminal_path,
    terminal_build, terminal_version, latency_ms, last_heartbeat_at,
    connected, login_status, last_error, created_at, updated_at
) VALUES (
    :id, :user_id, :login, :server, :status, :session_ref, :terminal_path,
    :terminal_build, :terminal_version, :latency_ms, :last_heartbeat_at,
    :connected, :login_status, :last_error, :created_at, :updated_at
)
ON CONFLICT (id) DO UPDATE SET
    user_id = EXCLUDED.user_id,
    login = EXCLUDED.login,
    server = EXCLUDED.server,
    status = EXCLUDED.status,
    session_ref = EXCLUDED.session_ref,
    terminal_path = EXCLUDED.terminal_path,
    terminal_build = EXCLUDED.terminal_build,
    terminal_version = EXCLUDED.terminal_version,
    latency_ms = EXCLUDED.latency_ms,
    last_heartbeat_at = EXCLUDED.last_heartbeat_at,
    connected = EXCLUDED.connected,
    login_status = EXCLUDED.login_status,
    last_error = EXCLUDED.last_error,
    updated_at = EXCLUDED.updated_at
"""


def _connection_params(connection: MT5Connection) -> dict[str, object]:
    return {
        "id": str(connection.id),
        "user_id": str(connection.user_id),
        "login": connection.login,
        "server": connection.server,
        "status": connection.status.value,
        "session_ref": connection.session_ref,
        "terminal_path": connection.terminal_path,
        "terminal_build": connection.terminal_build,
        "terminal_version": connection.terminal_version,
        "latency_ms": connection.latency_ms,
        "last_heartbeat_at": connection.last_heartbeat_at,
        "connected": connection.connected,
        "login_status": connection.login_status,
        "last_error": connection.last_error,
        "created_at": connection.created_at,
        "updated_at": connection.updated_at,
    }


class PostgresMT5ConnectionRepository:
    def __init__(self, uow: PostgresMT5UnitOfWork) -> None:
        self._uow = uow

    async def get_by_id(self, connection_id: UUID) -> MT5Connection | None:
        session = self._uow._require_session()
        result = await session.execute(
            text("SELECT * FROM mt5_connections WHERE id = :id"),
            {"id": str(connection_id)},
        )
        row = result.mappings().first()
        return _connection_from_row(row) if row else None

    async def get_active_for_user(self, user_id: UUID) -> MT5Connection | None:
        session = self._uow._require_session()
        result = await session.execute(
            text("""
                SELECT * FROM mt5_connections
                WHERE user_id = :user_id AND connected = true
                ORDER BY updated_at DESC
                LIMIT 1
                """),
            {"user_id": str(user_id)},
        )
        row = result.mappings().first()
        if row:
            return _connection_from_row(row)
        result = await session.execute(
            text("""
                SELECT * FROM mt5_connections
                WHERE user_id = :user_id
                ORDER BY updated_at DESC
                LIMIT 1
                """),
            {"user_id": str(user_id)},
        )
        row = result.mappings().first()
        return _connection_from_row(row) if row else None

    async def list_for_user(self, user_id: UUID) -> list[MT5Connection]:
        session = self._uow._require_session()
        result = await session.execute(
            text("""
                SELECT * FROM mt5_connections
                WHERE user_id = :user_id
                ORDER BY updated_at DESC
                """),
            {"user_id": str(user_id)},
        )
        return [_connection_from_row(r) for r in result.mappings().all()]

    async def add(self, connection: MT5Connection) -> MT5Connection:
        session = self._uow._require_session()
        await session.execute(
            text(_CONNECTION_UPSERT_SQL),
            _connection_params(connection),
        )
        return connection

    async def update(self, connection: MT5Connection) -> MT5Connection:
        return await self.add(connection)

    async def upsert_for_user(self, connection: MT5Connection) -> MT5Connection:
        session = self._uow._require_session()
        params = _connection_params(connection)
        result = await session.execute(
            text("""
                INSERT INTO mt5_connections (
                    id, user_id, login, server, status, session_ref, terminal_path,
                    terminal_build, terminal_version, latency_ms, last_heartbeat_at,
                    connected, login_status, last_error, created_at, updated_at
                ) VALUES (
                    :id, :user_id, :login, :server, :status, :session_ref,
                    :terminal_path, :terminal_build, :terminal_version, :latency_ms,
                    :last_heartbeat_at, :connected, :login_status, :last_error,
                    :created_at, :updated_at
                )
                ON CONFLICT (user_id, login, server) DO UPDATE SET
                    status = EXCLUDED.status,
                    session_ref = EXCLUDED.session_ref,
                    terminal_path = EXCLUDED.terminal_path,
                    terminal_build = EXCLUDED.terminal_build,
                    terminal_version = EXCLUDED.terminal_version,
                    latency_ms = EXCLUDED.latency_ms,
                    last_heartbeat_at = EXCLUDED.last_heartbeat_at,
                    connected = EXCLUDED.connected,
                    login_status = EXCLUDED.login_status,
                    last_error = EXCLUDED.last_error,
                    updated_at = EXCLUDED.updated_at
                RETURNING id
                """),
            params,
        )
        row = result.mappings().first()
        if row:
            connection.id = parse_uuid(row["id"])
        return connection


class PostgresMT5ValidationRepository:
    def __init__(self, uow: PostgresMT5UnitOfWork) -> None:
        self._uow = uow

    async def add(self, validation: TradeValidation) -> TradeValidation:
        session = self._uow._require_session()
        await session.execute(
            text("""
                INSERT INTO mt5_order_validations (
                    id, user_id, symbol, side, order_type, volume, valid, retcode,
                    expected_margin, estimated_profit, messages, checks,
                    request_snapshot, validated_at, created_at
                ) VALUES (
                    :id, :user_id, :symbol, :side, :order_type, :volume, :valid,
                    :retcode, :expected_margin, :estimated_profit,
                    CAST(:messages AS jsonb), CAST(:checks AS jsonb),
                    CAST(:request_snapshot AS jsonb), :validated_at, :created_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    symbol = EXCLUDED.symbol,
                    side = EXCLUDED.side,
                    order_type = EXCLUDED.order_type,
                    volume = EXCLUDED.volume,
                    valid = EXCLUDED.valid,
                    retcode = EXCLUDED.retcode,
                    expected_margin = EXCLUDED.expected_margin,
                    estimated_profit = EXCLUDED.estimated_profit,
                    messages = EXCLUDED.messages,
                    checks = EXCLUDED.checks,
                    request_snapshot = EXCLUDED.request_snapshot,
                    validated_at = EXCLUDED.validated_at
                """),
            {
                "id": str(validation.id),
                "user_id": str(validation.user_id),
                "symbol": validation.symbol,
                "side": validation.side,
                "order_type": validation.order_type,
                "volume": str(validation.volume),
                "valid": validation.valid,
                "retcode": validation.retcode,
                "expected_margin": str(validation.expected_margin),
                "estimated_profit": str(validation.estimated_profit),
                "messages": as_json(validation.messages),
                "checks": as_json(validation.checks),
                "request_snapshot": as_json(validation.request_snapshot),
                "validated_at": validation.validated_at,
                "created_at": validation.created_at,
            },
        )
        return validation

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 50
    ) -> list[TradeValidation]:
        session = self._uow._require_session()
        result = await session.execute(
            text("""
                SELECT * FROM mt5_order_validations
                WHERE user_id = :user_id
                ORDER BY validated_at DESC
                LIMIT :limit
                """),
            {"user_id": str(user_id), "limit": limit},
        )
        return [_validation_from_row(r) for r in result.mappings().all()]


class PostgresMT5UnitOfWork(PostgresUnitOfWorkBase):
    def __init__(self, database: DatabaseManager) -> None:
        super().__init__(database)
        self.connections = PostgresMT5ConnectionRepository(self)
        self.validations = PostgresMT5ValidationRepository(self)


class PostgresMT5UnitOfWorkFactory:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    def __call__(self) -> PostgresMT5UnitOfWork:
        return PostgresMT5UnitOfWork(self._database)
