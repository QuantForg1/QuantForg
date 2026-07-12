"""PostgreSQL health-check adapter."""

from __future__ import annotations

from dataclasses import dataclass

from core.database.session import DatabaseManager


@dataclass(frozen=True, slots=True)
class PostgresHealthCheck:
    """Health probe for the PostgreSQL dependency."""

    database: DatabaseManager

    @property
    def name(self) -> str:
        return "postgres"

    async def check(self) -> bool:
        return await self.database.health_check()
