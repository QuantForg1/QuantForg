"""SQLAlchemy async engine and session factory.

The :class:`DatabaseManager` encapsulates engine creation, session
provisioning, and graceful shutdown. A single manager is created during
application lifespan and shared via dependency injection.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config.settings import Settings
from core.logging import get_logger

logger = get_logger(__name__)

# Reused compiled statement — avoids per-request text() construction noise.
_HEALTH_SQL = text("SELECT 1")


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

    Pool tuning favours connection reuse across Railway ↔ Supabase RTTs:
    - no ``pool_pre_ping`` (extra RTT per checkout; recycle + warm instead)
    - no reset-on-return ROLLBACK (extra RTT; sessions already commit/rollback)
    - LIFO so the hottest connection is reused first
    """
    return create_async_engine(
        settings.database_url,
        pool_size=settings.postgres_pool_size,
        max_overflow=settings.postgres_max_overflow,
        echo=settings.postgres_echo,
        pool_pre_ping=False,
        pool_recycle=1800,
        pool_timeout=10,
        pool_reset_on_return=None,
        pool_use_lifo=True,
        connect_args=settings.asyncpg_connect_args,
    )


class DatabaseManager:
    """Manages the async engine and session factory lifecycle."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        # Dedicated AUTOCOMMIT connection for health — avoids pool checkout
        # pre-ping/reset RTTs and SSL setup on every /health probe.
        self._health_conn: AsyncConnection | None = None
        self._health_lock = asyncio.Lock()

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
        """Create the engine, warm the pool, and prepare the health connection."""
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
            pool_pre_ping=False,
            pool_reset_on_return=None,
            statement_cache_size=self._settings.asyncpg_connect_args.get(
                "statement_cache_size", "default"
            ),
        )
        await self._warm_pool(endpoint)
        await self._ensure_health_connection()

    async def _warm_pool(self, endpoint: dict[str, Any]) -> None:
        """Open and release connections so the first requests skip TLS setup."""
        warm_count = max(1, min(2, self._settings.postgres_pool_size))
        started = time.perf_counter()
        connections: list[AsyncConnection] = []
        try:
            for _ in range(warm_count):
                connection = await self.engine.connect()
                await connection.execute(_HEALTH_SQL)
                await connection.commit()
                connections.append(connection)
            warm_ms = round((time.perf_counter() - started) * 1000.0, 2)
            logger.info(
                "database_pool_warmed",
                warm_connections=warm_count,
                warm_ms=warm_ms,
                **endpoint,
            )
        except Exception:
            logger.exception("database_pool_warm_failed", **endpoint)
        finally:
            for connection in connections:
                with suppress(Exception):
                    await connection.close()

    async def _close_health_connection(self) -> None:
        conn = self._health_conn
        self._health_conn = None
        if conn is not None:
            with suppress(Exception):
                await conn.close()

    async def _ensure_health_connection(self) -> AsyncConnection:
        """Return a live AUTOCOMMIT connection dedicated to health probes."""
        conn = self._health_conn
        if conn is not None and not conn.closed:
            return conn
        await self._close_health_connection()
        started = time.perf_counter()
        raw = await self.engine.connect()
        conn = await raw.execution_options(isolation_level="AUTOCOMMIT")
        self._health_conn = conn
        connect_ms = round((time.perf_counter() - started) * 1000.0, 2)
        logger.info(
            "database_health_connection_ready",
            connection_ms=connect_ms,
            database_host=self.engine.url.host or "",
            database_port=self.engine.url.port or 5432,
        )
        return conn

    async def stop(self) -> None:
        """Dispose the engine and release all pooled connections."""
        await self._close_health_connection()
        if self._engine is not None:
            await self._engine.dispose()
            logger.info("database_engine_stopped")
        self._engine = None
        self._session_factory = None

    async def health_check(self) -> bool:
        """Return True if ``SELECT 1`` succeeds on a reused health connection.

        Uses the shared SQLAlchemy/asyncpg engine — never creates a new engine
        or pool per request.
        """
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

        engine_host = engine.url.host or endpoint["database_host"]
        engine_port = engine.url.port or endpoint["database_port"]
        total_started = time.perf_counter()

        async with self._health_lock:
            try:
                acquire_started = time.perf_counter()
                connection = await self._ensure_health_connection()
                acquire_ms = round((time.perf_counter() - acquire_started) * 1000.0, 2)

                query_started = time.perf_counter()
                result = await connection.execute(_HEALTH_SQL)
                result.scalar_one()
                query_ms = round((time.perf_counter() - query_started) * 1000.0, 2)
                total_ms = round((time.perf_counter() - total_started) * 1000.0, 2)

                logger.info(
                    "database_health_check_ok",
                    database_host=engine_host,
                    database_port=engine_port,
                    database_driver=engine.url.drivername,
                    database_sslmode=endpoint["database_sslmode"],
                    database_dsn_source=endpoint["database_dsn_source"],
                    pool_acquisition_ms=acquire_ms,
                    connection_ms=0.0,
                    query_execution_ms=query_ms,
                    total_health_ms=total_ms,
                )
                return True
            except Exception as exc:
                # Drop the sticky connection and retry once on a fresh checkout.
                await self._close_health_connection()
                try:
                    retry_acquire = time.perf_counter()
                    connection = await self._ensure_health_connection()
                    acquire_ms = round(
                        (time.perf_counter() - retry_acquire) * 1000.0, 2
                    )
                    query_started = time.perf_counter()
                    result = await connection.execute(_HEALTH_SQL)
                    result.scalar_one()
                    query_ms = round((time.perf_counter() - query_started) * 1000.0, 2)
                    total_ms = round((time.perf_counter() - total_started) * 1000.0, 2)
                    logger.info(
                        "database_health_check_ok",
                        database_host=engine_host,
                        database_port=engine_port,
                        database_driver=engine.url.drivername,
                        database_sslmode=endpoint["database_sslmode"],
                        database_dsn_source=endpoint["database_dsn_source"],
                        pool_acquisition_ms=acquire_ms,
                        connection_ms=acquire_ms,
                        query_execution_ms=query_ms,
                        total_health_ms=total_ms,
                        recovered_from=type(exc).__name__,
                    )
                    return True
                except Exception as retry_exc:
                    total_ms = round((time.perf_counter() - total_started) * 1000.0, 2)
                    logger.exception(
                        "database_health_check_failed",
                        database_host=engine_host,
                        database_port=engine_port,
                        database_driver=engine.url.drivername,
                        database_sslmode=endpoint["database_sslmode"],
                        database_dsn_source=endpoint["database_dsn_source"],
                        error_type=type(retry_exc).__name__,
                        total_health_ms=total_ms,
                    )
                    await self._close_health_connection()
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
