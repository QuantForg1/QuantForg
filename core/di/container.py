"""Application-scoped dependency injection container.

The container is constructed once during FastAPI lifespan startup and
torn down on shutdown. Presentation-layer dependency providers resolve
services from this container rather than constructing them inline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from core.config.settings import Settings
from core.database.session import DatabaseManager
from core.logging import get_logger

if TYPE_CHECKING:
    from app.infrastructure.cache.redis_client import RedisClient
    from app.infrastructure.supabase.client import SupabaseClient

logger = get_logger(__name__)


@dataclass
class Container:
    """Holds shared application dependencies for the process lifetime.

    Attributes
    ----------
    settings:
        Validated application configuration.
    database:
        Async database manager (engine + session factory).
    redis:
        Redis client wrapper, initialised during ``startup``.
    supabase:
        Supabase client wrapper, initialised during ``startup`` when configured.
    uow_factory:
        Unit of Work factory for identity profile persistence.
    """

    settings: Settings
    database: DatabaseManager
    redis: RedisClient | None = field(default=None, init=False)
    supabase: SupabaseClient | None = field(default=None, init=False)
    uow_factory: Any = field(default=None, init=False)
    platform_uow_factory: Any = field(default=None, init=False)
    broker_uow_factory: Any = field(default=None, init=False)
    broker_registry: Any = field(default=None, init=False)

    async def startup(self) -> None:
        """Start all managed infrastructure connections."""
        await self.database.start()

        from app.infrastructure.brokers.placeholders import (
            register_placeholder_adapters,
        )
        from app.infrastructure.brokers.registry import BrokerRegistry
        from app.infrastructure.cache.redis_client import RedisClient
        from app.infrastructure.persistence.memory_broker import (
            MemoryBrokerUnitOfWorkFactory,
        )
        from app.infrastructure.persistence.memory_platform import (
            MemoryPlatformUnitOfWorkFactory,
        )

        self.redis = RedisClient(self.settings)
        await self.redis.connect()
        self.platform_uow_factory = MemoryPlatformUnitOfWorkFactory()
        self.broker_uow_factory = MemoryBrokerUnitOfWorkFactory()
        self.broker_registry = BrokerRegistry()
        register_placeholder_adapters(self.broker_registry)

        if self.settings.supabase_configured:
            from app.infrastructure.persistence.supabase_identity import (
                SupabaseIdentityUnitOfWorkFactory,
            )
            from app.infrastructure.supabase.client import SupabaseClient

            self.supabase = SupabaseClient(self.settings)
            self.supabase.connect()
            self.uow_factory = SupabaseIdentityUnitOfWorkFactory(supabase=self.supabase)
        logger.info("container_startup_complete", env=self.settings.app_env.value)

    async def shutdown(self) -> None:
        """Gracefully close all managed infrastructure connections."""
        self.uow_factory = None
        self.platform_uow_factory = None
        self.broker_uow_factory = None
        self.broker_registry = None
        if self.supabase is not None:
            self.supabase.disconnect()
            self.supabase = None
        if self.redis is not None:
            await self.redis.disconnect()
            self.redis = None
        await self.database.stop()
        logger.info("container_shutdown_complete")

    def require_redis(self) -> RedisClient:
        """Return the Redis client or raise if not connected."""
        if self.redis is None:
            msg = "Redis client is not available"
            raise RuntimeError(msg)
        return self.redis

    def require_supabase(self) -> SupabaseClient:
        """Return the Supabase client or raise if not connected."""
        if self.supabase is None:
            msg = "Supabase client is not available"
            raise RuntimeError(msg)
        return self.supabase


_container: Container | None = None


def get_container() -> Container:
    """Return the process-wide DI container.

    Raises
    ------
    RuntimeError
        If the container has not been initialised.
    """
    if _container is None:
        msg = "DI container has not been initialised"
        raise RuntimeError(msg)
    return _container


def set_container(container: Container) -> None:
    """Register the process-wide DI container (called during lifespan)."""
    global _container
    _container = container
