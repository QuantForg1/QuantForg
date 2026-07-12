"""Application-scoped dependency injection container.

The container is constructed once during FastAPI lifespan startup and
torn down on shutdown. Presentation-layer dependency providers resolve
services from this container rather than constructing them inline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.config.settings import Settings
from core.database.session import DatabaseManager
from core.logging import get_logger

if TYPE_CHECKING:
    from app.infrastructure.cache.redis_client import RedisClient

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
    """

    settings: Settings
    database: DatabaseManager
    redis: RedisClient | None = field(default=None, init=False)

    async def startup(self) -> None:
        """Start all managed infrastructure connections."""
        await self.database.start()

        from app.infrastructure.cache.redis_client import RedisClient

        self.redis = RedisClient(self.settings)
        await self.redis.connect()
        logger.info("container_startup_complete", env=self.settings.app_env.value)

    async def shutdown(self) -> None:
        """Gracefully close all managed infrastructure connections."""
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
