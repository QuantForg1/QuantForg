"""SQLAlchemy async engine and session factory.

The :class:`DatabaseManager` encapsulates engine creation, session
provisioning, and graceful shutdown. A single manager is created during
application lifespan and shared via dependency injection.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config.settings import Settings
from core.logging import get_logger

logger = get_logger(__name__)


def create_engine(settings: Settings) -> AsyncEngine:
    """Create a configured async SQLAlchemy engine.

    Parameters
    ----------
    settings:
        Application settings providing the database URL and pool options.
    """
    return create_async_engine(
        settings.database_url,
        pool_size=settings.postgres_pool_size,
        max_overflow=settings.postgres_max_overflow,
        echo=settings.postgres_echo,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


class DatabaseManager:
    """Manages the async engine and session factory lifecycle."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            msg = "DatabaseManager is not started; call start() first"
            raise RuntimeError(msg)
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            msg = "DatabaseManager is not started; call start() first"
            raise RuntimeError(msg)
        return self._session_factory

    async def start(self) -> None:
        """Create the engine and session factory."""
        if self._engine is not None:
            return
        self._engine = create_engine(self._settings)
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
        logger.info(
            "database_engine_started",
            host=self._settings.postgres_host,
            database=self._settings.postgres_db,
            pool_size=self._settings.postgres_pool_size,
        )

    async def stop(self) -> None:
        """Dispose the engine and release all pooled connections."""
        if self._engine is not None:
            await self._engine.dispose()
            logger.info("database_engine_stopped")
        self._engine = None
        self._session_factory = None

    async def health_check(self) -> bool:
        """Return True if a trivial query against PostgreSQL succeeds."""
        from sqlalchemy import text

        try:
            async with self.session_factory() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception:
            logger.exception("database_health_check_failed")
            return False

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield a transactional session that commits on success.

        On exception the transaction is rolled back and the error
        re-raised. Callers must not commit or rollback manually.
        """
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise


_database_manager: DatabaseManager | None = None


def get_database_manager() -> DatabaseManager:
    """Return the process-wide DatabaseManager.

    Raises
    ------
    RuntimeError
        If the manager has not been initialised during application startup.
    """
    if _database_manager is None:
        msg = "DatabaseManager has not been initialised"
        raise RuntimeError(msg)
    return _database_manager


def set_database_manager(manager: DatabaseManager) -> None:
    """Register the process-wide DatabaseManager (called during lifespan)."""
    global _database_manager
    _database_manager = manager
