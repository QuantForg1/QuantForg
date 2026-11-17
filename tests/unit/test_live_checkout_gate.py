"""Real-money checkout stays closed until the owner opens it (17 Nov 2026)."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.presentation.dependencies.auth import get_current_user

pytestmark = [pytest.mark.unit]


class _Svc:
    def __init__(self, open_: bool) -> None:
        self.settings = SimpleNamespace(billing_live_checkout_enabled=open_)
        self.calls = 0

    async def create_checkout(self, **_: object) -> dict[str, object]:
        self.calls += 1
        return {"ok": True}


def _client(role: str, svc: _Svc) -> TestClient:
    from app.presentation.routers import billing

    app = FastAPI()
    app.include_router(billing.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=uuid4(), role=role, email="c@example.invalid"
    )
    app.dependency_overrides[billing.get_billing_service] = lambda: svc
    return TestClient(app, raise_server_exceptions=False)


BODY = {"plan_id": "starter", "pay_currency": "usdttrc20"}


def test_customer_checkout_closed_by_default() -> None:
    svc = _Svc(False)
    r = _client("trader", svc).post("/api/v1/billing/checkout", json=BODY)
    assert r.status_code == 503 and "PAYMENTS_NOT_OPEN" in r.text
    assert svc.calls == 0


def test_customer_checkout_open_when_enabled() -> None:
    svc = _Svc(True)
    r = _client("trader", svc).post("/api/v1/billing/checkout", json=BODY)
    assert r.status_code == 201 and svc.calls == 1


def test_owner_can_test_checkout_while_closed() -> None:
    svc = _Svc(False)
    r = _client("owner", svc).post("/api/v1/billing/checkout", json=BODY)
    assert r.status_code == 201


def test_default_setting_is_closed() -> None:
    from core.config.settings import Settings

    assert Settings.model_fields["billing_live_checkout_enabled"].default is False
