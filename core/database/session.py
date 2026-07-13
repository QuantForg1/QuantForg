"""SQLAlchemy async engine and session factory.

The :class:`DatabaseManager` encapsulates engine creation, session
provisioning, and graceful shutdown. A single manager is created during
application lifespan and shared via dependency injection.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config.settings import Settings
from core.logging import get_logger

logger = get_logger(__name__)


def _dsn_source(settings: Settings) -> str:
    if (settings.database_url_override or "").strip():
        return "DATABASE_URL"
    if settings.supabase_db_password is not None:
        password = settings.supabase_db_password.get_secret_value().strip()
        if password and settings._supabase_project_ref:
            return "SUPABASE_DB_PASSWORD"
    return "POSTGRES_COMPOSED"


def _sslmode_label(settings: Settings) -> str:
    if settings.asyncpg_connect_args.get("ssl"):
        return "require"
    return "disable"


def _safe_endpoint(settings: Settings) -> dict[str, Any]:
    """Host/port/driver/ssl diagnostics — never includes credentials."""
    raw = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    parsed = urlparse(raw)
    return {
        "database_dsn_source": _dsn_source(settings),
        "database_host": parsed.hostname or "",
        "database_port": parsed.port or 5432,
        "database_sslmode": _sslmode_label(settings),
        "database_driver": "postgresql+asyncpg",
    }


def create_engine(settings: Settings) -> AsyncEngine:
    """Create a configured async SQLAlchemy engine.

    Uses :attr:`Settings.database_url` (honours ``DATABASE_URL`` / pooler
    composition) with the same ``connect_args`` as the rest of the app.
    """
    return create_async_engine(
        settings.database_url,
        pool_size=settings.postgres_pool_size,
        max_overflow=settings.postgres_max_overflow,
        echo=settings.postgres_echo,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_timeout=30,
        connect_args=settings.asyncpg_connect_args,
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
        """Create the engine and session factory from application settings."""
        if self._engine is not None:
            return
        endpoint = _safe_endpoint(self._settings)
        if (
            self._settings.is_production
            and endpoint["database_dsn_source"] == "POSTGRES_COMPOSED"
            and endpoint["database_host"] in {"localhost", "127.0.0.1"}
        ):
            logger.error(
                "database_localhost_fallback_in_production",
                **endpoint,
                hint=(
                    "DATABASE_URL / SUPABASE_DB_URL / SUPABASE_DB_PASSWORD "
                    "not visible to this process; composed DSN uses "
                    "POSTGRES_HOST default localhost"
                ),
            )
        self._engine = create_engine(self._settings)
        # Ground truth from the live engine URL (password never logged).
        engine_url = self._engine.url
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
        logger.info(
            "database_engine_started",
            **endpoint,
            engine_url_host=engine_url.host or "",
            engine_url_port=engine_url.port or 5432,
            engine_url_driver=engine_url.drivername,
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
        """Return True if ``SELECT 1`` succeeds on the application engine.

        Uses the same SQLAlchemy/asyncpg engine created at startup (driven by
        ``DATABASE_URL`` via :attr:`Settings.database_url`) — never a separate
        ``POSTGRES_HOST``/localhost client.
        """
        from sqlalchemy import text

        endpoint = _safe_endpoint(self._settings)
        try:
            engine = self.engine
        except RuntimeError:
            logger.error(
                "database_health_check_failed",
                reason="engine_not_started",
                **endpoint,
            )
            return False

        # Prefer engine URL host (actual pool target) over settings fields.
        engine_host = engine.url.host or endpoint["database_host"]
        engine_port = engine.url.port or endpoint["database_port"]
        try:
            async with engine.connect() as connection:
                result = await connection.execute(text("SELECT 1"))
                result.scalar_one()
            logger.info(
                "database_health_check_ok",
                database_host=engine_host,
                database_port=engine_port,
                database_driver=engine.url.drivername,
                database_sslmode=endpoint["database_sslmode"],
                database_dsn_source=endpoint["database_dsn_source"],
            )
            return True
        except Exception as exc:
            logger.exception(
                "database_health_check_failed",
                database_host=engine_host,
                database_port=engine_port,
                database_driver=engine.url.drivername,
                database_sslmode=endpoint["database_sslmode"],
                database_dsn_source=endpoint["database_dsn_source"],
                error_type=type(exc).__name__,
            )
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
