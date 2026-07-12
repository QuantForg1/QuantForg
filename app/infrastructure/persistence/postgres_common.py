"""Shared helpers for SQLAlchemy-async Postgres Unit of Work adapters."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Self
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.database.session import DatabaseManager


def parse_uuid(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def parse_uuid_optional(value: object) -> UUID | None:
    if value is None or value == "":
        return None
    return parse_uuid(value)


def parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def parse_datetime_optional(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    return parse_datetime(value)


def parse_decimal(value: object, default: str = "0") -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    return Decimal(str(value))


def parse_decimal_optional(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


def as_json(value: object) -> str:
    """Serialize a Python object for CAST(... AS jsonb) bind params."""
    return json.dumps(value, default=str)


def row_mapping(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def json_col(value: object) -> Any:
    """Normalize a jsonb column that may arrive as dict/list or JSON string."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        return json.loads(value.decode())
    if isinstance(value, str):
        return json.loads(value)
    return value


def json_dict(value: object) -> dict[str, object]:
    raw = json_col(value)
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def json_list(value: object) -> list[object]:
    raw = json_col(value)
    if isinstance(raw, list):
        return list(raw)
    return []


class PostgresUnitOfWorkBase:
    """Opens an AsyncSession from DatabaseManager; commit/rollback on exit."""

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database
        self.session: AsyncSession | None = None
        self.committed = False
        self.rolled_back = False

    def _require_session(self) -> AsyncSession:
        if self.session is None:
            msg = "Unit of Work session is not active"
            raise RuntimeError(msg)
        return self.session

    async def __aenter__(self) -> Self:
        self.session = self._database.session_factory()
        self.committed = False
        self.rolled_back = False
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object,
    ) -> None:
        if self.session is None:
            return
        try:
            if exc_type is not None and not self.rolled_back:
                await self.rollback()
        finally:
            await self.session.close()
            self.session = None

    async def commit(self) -> None:
        session = self._require_session()
        await session.commit()
        self.committed = True

    async def rollback(self) -> None:
        session = self._require_session()
        await session.rollback()
        self.rolled_back = True
