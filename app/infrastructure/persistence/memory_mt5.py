"""In-memory MT5 connection persistence (tests + local runtime)."""

from __future__ import annotations

from typing import Self
from uuid import UUID

from app.domain.entities.mt5 import MT5Connection
from app.domain.entities.mt5_order import TradeValidation


class InMemoryMT5ConnectionRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, MT5Connection] = {}

    async def get_by_id(self, connection_id: UUID) -> MT5Connection | None:
        return self.items.get(connection_id)

    async def get_active_for_user(self, user_id: UUID) -> MT5Connection | None:
        for conn in self.items.values():
            if conn.user_id == user_id and conn.connected:
                return conn
        # Prefer most recently updated for user
        candidates = [c for c in self.items.values() if c.user_id == user_id]
        if not candidates:
            return None
        return max(candidates, key=lambda c: c.updated_at)

    async def list_for_user(self, user_id: UUID) -> list[MT5Connection]:
        return [c for c in self.items.values() if c.user_id == user_id]

    async def add(self, connection: MT5Connection) -> MT5Connection:
        self.items[connection.id] = connection
        return connection

    async def update(self, connection: MT5Connection) -> MT5Connection:
        self.items[connection.id] = connection
        return connection

    async def upsert_for_user(self, connection: MT5Connection) -> MT5Connection:
        existing = await self.get_active_for_user(connection.user_id)
        # Also match same login+server disconnected row
        if existing is None:
            for conn in self.items.values():
                if (
                    conn.user_id == connection.user_id
                    and conn.login == connection.login
                    and conn.server == connection.server
                ):
                    existing = conn
                    break
        if existing is None:
            return await self.add(connection)
        connection.id = existing.id
        self.items[existing.id] = connection
        return connection


class InMemoryMT5ValidationRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, TradeValidation] = {}

    async def add(self, validation: TradeValidation) -> TradeValidation:
        self.items[validation.id] = validation
        return validation

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 50
    ) -> list[TradeValidation]:
        rows = [v for v in self.items.values() if v.user_id == user_id]
        rows.sort(key=lambda v: v.validated_at, reverse=True)
        return rows[:limit]


class InMemoryMT5UnitOfWork:
    def __init__(self) -> None:
        self.connections = InMemoryMT5ConnectionRepository()
        self.validations = InMemoryMT5ValidationRepository()
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        if exc_type is not None and not self.committed:
            await self.rollback()

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class MemoryMT5UnitOfWorkFactory:
    def __init__(self, uow: InMemoryMT5UnitOfWork | None = None) -> None:
        self.uow = uow or InMemoryMT5UnitOfWork()

    def __call__(self) -> InMemoryMT5UnitOfWork:
        self.uow.committed = False
        self.uow.rolled_back = False
        return self.uow
