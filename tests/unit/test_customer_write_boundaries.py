"""Customer write boundaries found in the 17 Nov 2026 API write-path audit.

- Manual order submit / cancel / manage run on the shared platform terminal
  (the owner's session) and are owner/admin only.
- Household emergency stops: customers act only on their own user or owned
  accounts, never on broker-wide stops, and never disarm a stop the owner
  armed. The read view hides other users' accounts.
- Platform-wide research / strategy / universe writes are owner/admin only.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import main
from app.domain.enums.user import UserRole
from app.domain.portfolio_household import emergency_stops
from app.presentation.dependencies.auth import get_current_user
from app.presentation.routers import household_portfolio

pytestmark = [pytest.mark.unit]

_MODULES = {
    "execution",
    "household_portfolio",
    "research_validation_platform",
    "research_lab",
    "strategy",
    "market_universe",
    "symbol_signals",
}


def _client(role: UserRole, user_id: Any = None) -> tuple[TestClient, Any]:
    app = FastAPI()
    from app.presentation.middleware.error_handler import register_exception_handlers

    register_exception_handlers(app)
    specs = tuple(
        (name, path)
        for name, path in main._ROUTER_SPECS
        if path.rsplit(".", 1)[-1] in _MODULES
    )
    main._register_routers(app, SimpleNamespace(api_prefix="/api/v1"), specs=specs)
    user = SimpleNamespace(
        id=user_id or uuid4(),
        role=role,
        email="u@example.invalid",
        display_name="u",
        status="active",
    )
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False), user


@pytest.fixture(autouse=True)
def _fresh_stop_store(
    monkeypatch: pytest.MonkeyPatch,
) -> emergency_stops.EmergencyStopStore:
    store = emergency_stops.EmergencyStopStore()
    monkeypatch.setattr(emergency_stops, "_STORE", store)
    return store


@pytest.mark.parametrize("path", ["submit", "cancel", "manage"])
def test_customer_cannot_use_shared_terminal_execution(path: str) -> None:
    client, _ = _client(UserRole.TRADER)
    r = client.post(f"/api/v1/execution/{path}", json={})
    assert r.status_code == 403, r.text[:300]
    assert "SHARED_TERMINAL_OWNER_ONLY" in r.text


def test_owner_passes_execution_guard() -> None:
    client, _ = _client(UserRole.OWNER)
    r = client.post("/api/v1/execution/submit", json={})
    assert r.status_code != 403, r.text[:300]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/v1/research-validation/release"),
        ("post", "/api/v1/research-validation/rollback"),
        ("post", "/api/v1/research-validation/policies"),
        ("put", "/api/v1/strategy/portfolio/allocations"),
        ("post", "/api/v1/market-universe/refresh"),
        ("post", "/api/v1/research-lab/parameters"),
        ("post", "/api/v1/research-lab/promotion/criteria"),
        ("post", "/api/v1/signals/research/refresh"),
    ],
)
def test_customer_cannot_change_platform_wide_state(method: str, path: str) -> None:
    client, _ = _client(UserRole.TRADER)
    r = client.request(method.upper(), path, json={})
    assert r.status_code == 403, (path, r.status_code, r.text[:200])


def _stop(scope: str, scope_id: str, *, disarm: bool = False) -> tuple[str, dict]:
    action = "disarm" if disarm else "arm"
    return (
        f"/api/v1/portfolio/household/emergency-stops/{action}",
        {"scope": scope, "scope_id": scope_id, "reason": "test", "confirmed": True},
    )


def test_customer_cannot_arm_or_disarm_broker_stop(
    _fresh_stop_store: emergency_stops.EmergencyStopStore,
) -> None:
    _fresh_stop_store.arm(scope="broker", scope_id="weltrade", reason="owner")
    client, _ = _client(UserRole.TRADER)
    for disarm in (False, True):
        url, body = _stop("broker", "weltrade", disarm=disarm)
        assert client.post(url, json=body).status_code == 403
    assert _fresh_stop_store.is_armed(broker_code="weltrade")


def test_customer_cannot_touch_another_users_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mine, theirs = str(uuid4()), str(uuid4())
    monkeypatch.setattr(household_portfolio, "_owned_account_ids", lambda _u: {mine})
    client, _ = _client(UserRole.TRADER)
    url, body = _stop("account", theirs)
    assert client.post(url, json=body).status_code == 403
    url, body = _stop("account", mine)
    assert client.post(url, json=body).status_code == 200


def test_customer_cannot_disarm_owner_armed_stop_on_own_user(
    _fresh_stop_store: emergency_stops.EmergencyStopStore,
) -> None:
    owner_id = uuid4()
    client, user = _client(UserRole.TRADER)
    _fresh_stop_store.arm(
        scope="user", scope_id=str(user.id), reason="owner hold", actor_user_id=owner_id
    )
    url, body = _stop("user", "ignored", disarm=True)
    r = client.post(url, json=body)
    assert r.status_code == 403
    assert "emergency_stop_armed_by_operator" in r.text
    assert _fresh_stop_store.is_armed(user_id=user.id)


def test_customer_can_arm_and_disarm_own_user_stop(
    _fresh_stop_store: emergency_stops.EmergencyStopStore,
) -> None:
    client, user = _client(UserRole.TRADER)
    url, body = _stop("user", "someone-else")
    assert client.post(url, json=body).status_code == 200
    assert _fresh_stop_store.is_armed(user_id=user.id)
    url, body = _stop("user", "someone-else", disarm=True)
    assert client.post(url, json=body).status_code == 200
    assert not _fresh_stop_store.is_armed(user_id=user.id)


def test_customer_view_hides_other_accounts(
    monkeypatch: pytest.MonkeyPatch,
    _fresh_stop_store: emergency_stops.EmergencyStopStore,
) -> None:
    mine, theirs = str(uuid4()), str(uuid4())
    _fresh_stop_store.arm(scope="account", scope_id=mine, reason="x")
    _fresh_stop_store.arm(scope="account", scope_id=theirs, reason="y")
    monkeypatch.setattr(household_portfolio, "_owned_account_ids", lambda _u: {mine})
    client, _ = _client(UserRole.TRADER)
    data = client.get("/api/v1/portfolio/household/emergency-stops").json()
    assert data["accounts"] == [mine]
    assert all(e["scope_id"] != theirs for e in data["audit_tail"])
    assert all("actor_user_id" not in e for e in data["audit_tail"])


def test_owner_can_manage_broker_stop(
    _fresh_stop_store: emergency_stops.EmergencyStopStore,
) -> None:
    client, _ = _client(UserRole.OWNER)
    url, body = _stop("broker", "weltrade")
    assert client.post(url, json=body).status_code == 200
    url, body = _stop("broker", "weltrade", disarm=True)
    assert client.post(url, json=body).status_code == 200
    assert not _fresh_stop_store.is_armed(broker_code="weltrade")
