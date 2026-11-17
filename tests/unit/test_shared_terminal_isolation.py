"""Customers must never change the shared platform MT5 session (17 Nov 2026).

A customer's /weltrade/restore-profile disconnected the owner's LIVE Weltrade
session on the platform terminal and logged it into the customer's account.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.presentation.dependencies.auth import get_current_user

pytestmark = [pytest.mark.unit]

# Shared-platform-terminal mutations only. Customer disconnect/reconnect are
# vault lifecycle paths and must never call the gateway (covered below).
MUTATIONS = [
    "/api/v1/weltrade/attach",
    "/api/v1/weltrade/claim",
    "/api/v1/weltrade/restore-profile",
    "/api/v1/mt5/connect",
    "/api/v1/mt5/disconnect",
    "/api/v1/broker-connections/validate",
]


def _client(role: str) -> TestClient:
    from app.presentation.routers import broker_connections, mt5, weltrade

    app = FastAPI()
    for r in (weltrade.router, mt5.router, broker_connections.router):
        app.include_router(r, prefix="/api/v1")
    user = SimpleNamespace(id=uuid4(), role=role, email="x@example.invalid")
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("path", MUTATIONS)
def test_customer_cannot_change_the_shared_terminal(path: str) -> None:
    r = _client("trader").post(path, json={})
    assert r.status_code == 403, (path, r.status_code)
    assert "SHARED_TERMINAL_OWNER_ONLY" in r.text


@pytest.mark.parametrize("path", MUTATIONS)
def test_owner_passes_the_guard(path: str) -> None:
    r = _client("owner").post(path, json={})
    assert r.status_code != 403 or "SHARED_TERMINAL_OWNER_ONLY" not in r.text


def test_customer_disconnect_and_reconnect_never_touch_the_shared_terminal() -> None:
    from app.presentation.dependencies.weltrade import get_weltrade_service
    from app.presentation.routers import weltrade

    calls: dict[str, int] = {
        "disconnect": 0,
        "reconnect": 0,
        "customer_disconnect": 0,
        "customer_reconnect": 0,
    }

    class _Svc:
        async def disconnect(self, **_: object) -> dict[str, object]:
            calls["disconnect"] += 1
            return {"ok": True}

        async def reconnect(self, **_: object) -> dict[str, object]:
            calls["reconnect"] += 1
            return {"ok": True}

        async def disconnect_customer_account(self, **_: object) -> dict[str, object]:
            calls["customer_disconnect"] += 1
            return {"ok": True, "state": "DISCONNECTED"}

        async def reconnect_customer_account(self, **_: object) -> dict[str, object]:
            calls["customer_reconnect"] += 1
            return {"ok": True, "state": "QUEUED_FOR_TERMINAL"}

    app = FastAPI()
    app.include_router(weltrade.router, prefix="/api/v1")
    user = SimpleNamespace(id=uuid4(), role="trader", email="x@example.invalid")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_weltrade_service] = lambda: _Svc()
    client = TestClient(app)
    d = client.post("/api/v1/weltrade/disconnect", json={})
    r = client.post("/api/v1/weltrade/reconnect", json={})
    assert d.status_code == 200 and d.json()["state"] == "DISCONNECTED"
    assert r.status_code == 200 and r.json()["state"] == "QUEUED_FOR_TERMINAL"
    assert calls == {
        "disconnect": 0,
        "reconnect": 0,
        "customer_disconnect": 1,
        "customer_reconnect": 1,
    }


def test_customer_connect_saves_for_a_worker_terminal_only() -> None:
    from app.presentation.dependencies.weltrade import get_weltrade_service
    from app.presentation.routers import weltrade

    calls: dict[str, int] = {"connect": 0, "register": 0}

    class _Svc:
        async def connect(self, **_: object) -> dict[str, object]:
            calls["connect"] += 1
            return {}

        async def register_customer_account(self, **kw: object) -> dict[str, object]:
            calls["register"] += 1
            assert kw["broker_slug"] == "xm"
            return {"ok": True, "state": "QUEUED_FOR_TERMINAL"}

    app = FastAPI()
    app.include_router(weltrade.router, prefix="/api/v1")
    user = SimpleNamespace(id=uuid4(), role="trader", email="x@example.invalid")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_weltrade_service] = lambda: _Svc()
    r = TestClient(app).post(
        "/api/v1/weltrade/connect",
        json={
            "login": 450397410,
            "password": "pw-not-real",
            "server": "XMGlobal-MT5 20",
            "account_type": "live",
            "broker_slug": "xm",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "QUEUED_FOR_TERMINAL"
    assert calls == {"connect": 0, "register": 1}


def test_register_validates_and_never_touches_the_terminal() -> None:
    import asyncio

    from app.application.services.weltrade_integration import (
        WeltradeIntegrationService,
    )

    saved: list[dict[str, object]] = []

    class _Store:
        async def save_selection(self, **kw: object) -> bool:
            saved.append(kw)
            return True

    from app.application.services import broker_ownership_restore as bor

    bor_orig = bor.login_registered_to_another_user
    bor.login_registered_to_another_user = lambda *_a, **_k: False  # type: ignore[assignment]
    svc = object.__new__(WeltradeIntegrationService)
    svc._secret_store = lambda: _Store()  # type: ignore[method-assign]
    out = asyncio.run(
        svc.register_customer_account(
            user_id=uuid4(),
            login=450397410,
            password="pw-not-real",
            server="XMGlobal-MT5 20",
            account_type="demo",
            broker_slug="xm",
        )
    )
    assert out["state"] == "QUEUED_FOR_TERMINAL"
    bor.login_registered_to_another_user = lambda *_a, **_k: True  # type: ignore[assignment]
    with pytest.raises(ValueError, match="already registered"):
        asyncio.run(
            svc.register_customer_account(
                user_id=uuid4(),
                login=12439799,
                password="x",
                server="Weltrade-Real",
                account_type="live",
                broker_slug="weltrade",
            )
        )
    bor.login_registered_to_another_user = bor_orig  # type: ignore[assignment]
    assert saved[0]["pending_terminal"] is True and saved[0]["broker_slug"] == "xm"
    with pytest.raises(ValueError):
        asyncio.run(
            svc.register_customer_account(
                user_id=uuid4(),
                login=1234567,
                password="x",
                server="Weltrade-Real",
                account_type="live",
                broker_slug="xm",
            )
        )
