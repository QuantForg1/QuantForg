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

MUTATIONS = [
    "/api/v1/weltrade/connect",
    "/api/v1/weltrade/attach",
    "/api/v1/weltrade/claim",
    "/api/v1/weltrade/disconnect",
    "/api/v1/weltrade/reconnect",
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
