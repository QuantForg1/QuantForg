"""PostgreSQL health-check adapter."""

from __future__ import annotations

from dataclasses import dataclass

from core.database.session import DatabaseManager


@dataclass(frozen=True, slots=True)
class PostgresHealthCheck:
    """Health probe for the PostgreSQL dependency.

    Delegates to :meth:`DatabaseManager.health_check`, which runs
    ``SELECT 1`` on the shared SQLAlchemy/asyncpg engine (same
    ``DATABASE_URL`` / :attr:`Settings.database_url` as the application).
    """

    database: DatabaseManager

    @property
    def name(self) -> str:
        return "postgres"

    async def check(self) -> bool:
        return await self.database.health_check()
