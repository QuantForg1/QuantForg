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
os.environ.setdefault("GOLD_ONLY_MODE", "false")
os.environ.setdefault("MULTI_SYMBOL_ENABLED", "true")
# Generated reports/validation/execution evidence go to a temp dir, never into
# the tracked docs/production tree (see core.production_docs).
if not os.environ.get("QUANTFORG_PRODUCTION_DOCS_DIR"):
    import tempfile

    os.environ["QUANTFORG_PRODUCTION_DOCS_DIR"] = tempfile.mkdtemp(
        prefix="quantforg-production-docs-"
    )


@pytest.fixture(autouse=True)
def _reset_phase_a_plane() -> Iterator[None]:
    """Phase A halt is a process singleton — a kill in one test must not leak."""
    from app.domain.institutional_trading.phase_a.plane import (
        reset_phase_a_plane_for_tests,
    )

    reset_phase_a_plane_for_tests()
    yield
    reset_phase_a_plane_for_tests()


@pytest.fixture(autouse=True)
def _owner_session_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the owner clock to 10:00 UTC on a weekday.

    Day-boundary helpers read this clock. The session gate itself is the full
    UTC day; broker availability is tested with explicit broker facts.
    """
    from datetime import UTC, datetime, time, timedelta

    from app.domain.institutional_trading import owner_live_limits as ol

    day = datetime.now(UTC).date()
    while day.weekday() >= 5:  # keep day-boundary tests on a weekday
        day -= timedelta(days=1)
    fixed = datetime.combine(day, time(10, 0), tzinfo=UTC)
    monkeypatch.setattr(ol, "_now", lambda: fixed)


@pytest.fixture(autouse=True)
def _reset_auto_trading_status_cache() -> Iterator[None]:
    """The 2s status snapshot cache is process-wide — never share it across tests."""
    from app.application.services.auto_trading_status import (
        reset_auto_trading_status_cache,
    )

    reset_auto_trading_status_cache()
    yield
    reset_auto_trading_status_cache()


@pytest.fixture(autouse=True)
def _reset_execution_account_binding() -> Iterator[None]:
    """Singleton gateway binding must not leak across tests."""
    from app.application.services.account_execution_gate import (
        reset_execution_binding_for_tests,
    )

    reset_execution_binding_for_tests()
    yield
    reset_execution_binding_for_tests()


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


def pytest_collection_modifyitems(config: Any, items: list[Any]) -> None:
    """Apply the tracked known-failure list as strict xfails (tests/known_failures.py)."""
    from tests.known_failures import GROUP_ISSUES, KNOWN_FAILURES

    for item in items:
        nodeid = item.nodeid.replace("\\", "/")
        entry = KNOWN_FAILURES.get(nodeid)
        if entry is None:
            continue
        group, reason = entry
        item.add_marker(
            pytest.mark.xfail(
                strict=True,
                reason=f"[known:{group}] {reason} — {GROUP_ISSUES.get(group, '')}",
            )
        )
