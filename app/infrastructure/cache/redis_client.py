"""Redis client wrapper.

Provides connection lifecycle management and basic key-value operations.
Domain caching policies belong in the application layer; this module is a
thin infrastructure adapter.
"""

from __future__ import annotations

from typing import Any, cast

import redis.asyncio as aioredis

from core.config.settings import Settings
from core.logging import get_logger

logger = get_logger(__name__)


class RedisClient:
    """Async Redis client with managed connection pool.

    Parameters
    ----------
    settings:
        Application settings providing Redis connection parameters.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Any | None = None

    @property
    def client(self) -> Any:
        if self._client is None:
            msg = "RedisClient is not connected; call connect() first"
            raise RuntimeError(msg)
        return self._client

    async def connect(self) -> None:
        """Open the Redis connection pool."""
        if self._client is not None:
            return
        self._client = cast(
            Any,
            aioredis.from_url(
                self._settings.redis_url,
                max_connections=self._settings.redis_pool_size,
                decode_responses=True,
            ),
        )
        logger.info(
            "redis_connected",
            host=self._settings.redis_host,
            db=self._settings.redis_db,
        )

    async def disconnect(self) -> None:
        """Close the Redis connection pool."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("redis_disconnected")

    async def get(self, key: str) -> str | None:
        """Get a string value by key."""
        value = await self.client.get(key)
        return cast(str | None, value)

    async def set(
        self,
        key: str,
        value: str,
        *,
        ex: int | None = None,
    ) -> bool:
        """Set a string value with optional expiry seconds."""
        result = await self.client.set(key, value, ex=ex)
        return bool(result)

    async def delete(self, *keys: str) -> int:
        """Delete one or more keys; return count deleted."""
        if not keys:
            return 0
        return int(await self.client.delete(*keys))

    async def ping(self) -> bool:
        """Return True when Redis responds to PING."""
        try:
            return bool(await self.client.ping())
        except Exception:
            return False
