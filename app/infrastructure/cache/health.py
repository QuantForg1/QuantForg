"""Redis health-check adapter."""

from __future__ import annotations

from dataclasses import dataclass

from app.infrastructure.cache.redis_client import RedisClient


@dataclass(frozen=True, slots=True)
class RedisHealthCheck:
    """Health probe for the Redis dependency."""

    redis: RedisClient

    @property
    def name(self) -> str:
        return "redis"

    async def check(self) -> bool:
        return await self.redis.ping()
