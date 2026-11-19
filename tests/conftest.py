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
def _reset_runtime_trading_policy() -> Iterator[None]:
    """A saved policy must not leak into the next test.

    The approved baseline now carries a verified commission. A leaked document
    would turn an unknown commission into that known zero.
    """
    from app.domain.institutional_trading.runtime_policy import (
        reset_runtime_policy,
        use_runtime_policy,
    )

    # Since 2026-11-18 every user has an own risk profile whose defaults are
    # 15/20/30%, lot 0.50, 5 positions, spread 1.00, 24/5. The pre-existing
    # suite was written against the former shared baseline; it keeps testing
    # the same mechanisms under that explicit profile (installed here as a
    # user profile, without a commission block so an unknown commission stays
    # unknown). New-default behaviour is covered by test_user_risk_profiles,
    # which installs its own profiles.
    token = use_runtime_policy(dict(LEGACY_TEST_RISK_PROFILE))
    yield
    reset_runtime_policy(token)


# The former shared owner baseline (policy v17, 2026-11-16), as a profile.
LEGACY_TEST_RISK_PROFILE: dict[str, Any] = {
    "max_planned_risk_pct": "9.0",
    "max_aggregate_open_risk_pct": "9.0",
    "daily_loss_pct": "25.0",
    "weekly_loss_pct": "0",
    "monthly_loss_pct": "0",
    "max_drawdown_pct": "0",
    "min_reward_risk": "1.50",
    "preferred_reward_risk": "1.50",
    "max_spread": "0.45",
    "max_lot": "0.01",
    "max_concurrent_positions": 1,
    "min_trade_quality": 75,
    "trading_days": [0, 1, 2, 3, 4],
    "trading_hours_utc": "07:00-17:00",
    "risk_profile_version": 0,
    "risk_profile_user": None,
}

# The same former baseline in risk-profile field names.
LEGACY_TEST_PROFILE_SETTINGS: dict[str, Any] = {
    "planned_risk_pct": "9.0",
    "aggregate_open_risk_pct": "9.0",
    "daily_loss_pct": "25.0",
    "max_spread": "0.45",
    "max_lot": "0.01",
    "max_open_positions": 1,
    "trading_hours_utc": "07:00-17:00",
}


@pytest.fixture(autouse=True)
def _legacy_profile_for_unsaved_users(monkeypatch: pytest.MonkeyPatch) -> None:
    """A user with no saved profile resolves to the former baseline in tests.

    Production resolves such users to the approved defaults; the pre-existing
    suite exercises engine paths (``install_cycle_policy``) under the former
    baseline. ``test_user_risk_profiles`` restores the real resolver.
    """
    from app.application.services import user_risk_profile_store as store
    from app.domain.institutional_trading.risk_profile import resolve_profile

    original = store.effective_profile

    def _effective(user_id: Any, *, use_cache: bool = True) -> Any:
        settings, version, _updated = store.load_settings(user_id, use_cache=use_cache)
        if not settings:
            return resolve_profile(LEGACY_TEST_PROFILE_SETTINGS, version=version)
        return original(user_id, use_cache=use_cache)

    monkeypatch.setattr(store, "effective_profile", _effective)
    monkeypatch.setattr(store, "REAL_EFFECTIVE_PROFILE", original, raising=False)
    store.reset_for_tests()


@pytest.fixture(autouse=True)
def _known_broker_clock() -> Iterator[None]:
    """Test gateways report deal times in UTC: offset known and zero.

    Production learns the MT5 server offset from live ticks; with no offset
    the engine fails closed on daily P/L (covered by test_broker_clock).
    """
    from datetime import timedelta

    from app.domain.institutional_trading import broker_clock

    broker_clock.set_for_tests(timedelta(0))
    yield
    broker_clock.reset_for_tests()


@pytest.fixture(autouse=True)
def _reset_gateway_circuit() -> Iterator[None]:
    from app.infrastructure.brokers.mt5 import gateway_circuit

    gateway_circuit.reset_for_tests()
    yield
    gateway_circuit.reset_for_tests()


@pytest.fixture(autouse=True)
def _registered_login_default(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unit tests have no broker_accounts table: model the login as the
    user's own registered account unless a test opts out."""
    if request.node.get_closest_marker("real_login_registration"):
        return
    from app.application.services import broker_ownership_restore as bor

    monkeypatch.setattr(bor, "login_registered_to_user", lambda *_a, **_k: True)


@pytest.fixture(autouse=True)
def _clear_auth_user_cache() -> Iterator[None]:
    from app.presentation.dependencies.auth import clear_user_cache

    clear_user_cache()
    yield
    clear_user_cache()


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

    Day-boundary helpers and the owner Mon-Fri 07:00-17:00 UTC entry window
    read this clock, so tests that do not pass ``now`` sit inside the window.
    Tests of the window itself pass an explicit ``now``.
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
    (
        """Apply the tracked known-failure list as strict xfails """
        """(tests/known_failures.py)."""
    )
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


@pytest.fixture(autouse=True)
def _clear_candle_tail_cache():
    """Incremental candle cache is process-wide; isolate every test."""
    from app.application.services.candle_tail_cache import shared_rates_cache

    shared_rates_cache().clear()
    yield
    shared_rates_cache().clear()


@pytest.fixture(autouse=True)
def _clear_public_tick_cache():
    from app.presentation.routers import public_market

    public_market._TICK_CACHE.clear()
    yield
    public_market._TICK_CACHE.clear()
