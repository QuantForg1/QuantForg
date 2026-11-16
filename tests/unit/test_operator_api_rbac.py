"""Customers cannot change platform-wide state through operator desks (17 Nov).

97 routers had a session check but no role check, so any registered user
could e.g. clear the scalping emergency stop or change the supervisor mode.
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
from app.presentation.dependencies.auth import get_current_user

pytestmark = [pytest.mark.unit]


def _client(role: UserRole) -> TestClient:
    app = FastAPI()
    from app.presentation.middleware.error_handler import register_exception_handlers

    register_exception_handlers(app)
    specs = tuple(
        (name, path)
        for name, path in main._ROUTER_SPECS
        if path.rsplit(".", 1)[-1]
        in {"scalping_ai_v2", "ai_trading_intelligence", "gateway_manager", "risk"}
    )
    main._register_routers(app, SimpleNamespace(api_prefix="/api/v1"), specs=specs)
    user = SimpleNamespace(
        id=uuid4(),
        role=role,
        email="u@example.invalid",
        display_name="u",
        status="active",
    )
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/v1/scalping-ai-v2/emergency-stop/clear"),
        ("post", "/api/v1/scalping-ai-v2/policies"),
        ("get", "/api/v1/gateway-manager/dashboard"),
        ("post", "/api/v1/ai-trading-intelligence/supervisor/mode"),
        ("post", "/api/v1/ai-trading-intelligence/adaptive/x/approve"),
    ],
)
def test_customer_is_forbidden(method: str, path: str) -> None:
    client = _client(UserRole.TRADER)
    r: Any = client.get(path) if method == "get" else client.post(path, json={})
    assert r.status_code == 403, (path, r.status_code, r.text[:200])


def test_owner_passes_the_role_gate() -> None:
    r = _client(UserRole.OWNER).post(
        "/api/v1/ai-trading-intelligence/supervisor/mode", json={"mode": "x"}
    )
    assert r.status_code != 403


def test_customer_read_endpoints_stay_open() -> None:
    r = _client(UserRole.TRADER).get("/api/v1/ai-trading-intelligence/supervisor")
    assert r.status_code != 403


def test_operator_list_covers_known_dangerous_routers() -> None:
    for name in (
        "scalping_ai_v2",
        "autonomous_trading_control",
        "gateway_manager",
        "trading_kernel",
        "quantitative_research_control",
        "mission_control",
    ):
        assert name in main._OPERATOR_ONLY_ROUTER_MODULES
    for customer in ("auth", "risk", "robot_control", "trading_session", "weltrade"):
        assert customer not in main._OPERATOR_ONLY_ROUTER_MODULES
