"""Shared pytest fixtures for QuantForg tests."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

# Force testing environment before any settings import.
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault(
    "SECRET_KEY",
    "test-secret-key-that-is-long-enough-for-validation-32chars",
)
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("LOG_FORMAT", "console")
os.environ.setdefault("LOG_JSON", "false")
os.environ.setdefault("DEBUG", "true")


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def settings() -> Any:
    """Provide testing settings and clear the settings cache."""
    from core.config.environments import testing_settings
    from core.config.settings import get_settings

    get_settings.cache_clear()
    configured = testing_settings()
    return configured


@pytest.fixture
def app(settings: Any) -> Iterator[FastAPI]:
    """Create a FastAPI app with testing settings.

    Lifespan is not entered for unit tests that do not need infrastructure.
    Integration tests that need live connections should use ``live_app``.
    """
    from core.config.settings import get_settings

    get_settings.cache_clear()

    # Patch get_settings to return testing settings for the factory.
    import core.config.settings as settings_module

    original = settings_module.get_settings
    settings_module.get_settings = lambda: settings  # type: ignore[assignment]

    from app.main import create_app

    application = create_app(settings=settings)
    yield application

    settings_module.get_settings = original
    get_settings.cache_clear()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """Synchronous TestClient without lifespan (no DB/Redis required)."""
    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client


@pytest.fixture
async def async_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Async HTTP client bound to the ASGI app (no lifespan)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
