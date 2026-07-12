"""Integration test placeholders.

These tests require live PostgreSQL and Redis instances.
They are skipped unless ``RUN_INTEGRATION=1`` is set in the environment.

Run with::

    RUN_INTEGRATION=1 make test-integration
"""

from __future__ import annotations

import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION") != "1",
        reason="Set RUN_INTEGRATION=1 to run integration tests",
    ),
]


@pytest.mark.asyncio
async def test_postgres_health_probe() -> None:
    """Verify the DatabaseManager can reach a live PostgreSQL instance."""
    from core.config.environments import testing_settings
    from core.database.session import DatabaseManager

    settings = testing_settings()
    manager = DatabaseManager(settings)
    await manager.start()
    try:
        assert await manager.health_check() is True
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_redis_health_probe() -> None:
    """Verify the RedisClient can reach a live Redis instance."""
    from app.infrastructure.cache.redis_client import RedisClient
    from core.config.environments import testing_settings

    settings = testing_settings()
    client = RedisClient(settings)
    await client.connect()
    try:
        assert await client.ping() is True
    finally:
        await client.disconnect()
