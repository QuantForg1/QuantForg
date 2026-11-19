"""Signals are a paid feature: the API refuses unpaid customers with 402."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.application.services import entitlements
from app.application.services.entitlements import Entitlement
from app.presentation.routers import symbol_signals


def _user(role: str) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role=role)


def _run(user):
    return asyncio.run(symbol_signals.require_signals_subscription(user))


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_operators_always_allowed(role, monkeypatch):
    def boom(**_):
        raise AssertionError("billing must not be read for operators")

    monkeypatch.setattr(entitlements, "check_trading_entitlement", boom)
    user = _user(role)
    assert _run(user) is user


def test_paid_customer_allowed(monkeypatch):
    monkeypatch.setattr(
        entitlements,
        "check_trading_entitlement",
        lambda **_: Entitlement(True, "license_active", "license"),
    )
    user = _user("trader")
    assert _run(user) is user


def test_unpaid_customer_gets_402(monkeypatch):
    monkeypatch.setattr(
        entitlements,
        "check_trading_entitlement",
        lambda **_: Entitlement(False, "SUBSCRIPTION_INACTIVE", "none"),
    )
    with pytest.raises(HTTPException) as exc:
        _run(_user("trader"))
    assert exc.value.status_code == 402
    assert exc.value.detail["code"] == "subscription_required"


def test_billing_read_failure_fails_closed(monkeypatch):
    def broken(**_):
        raise RuntimeError("db down")

    monkeypatch.setattr(entitlements, "check_trading_entitlement", broken)
    with pytest.raises(HTTPException) as exc:
        _run(_user("trader"))
    assert exc.value.status_code == 402


def test_signal_read_routes_are_gated():
    gated = {
        "/signals",
        "/signals/{symbol}",
        "/signals/intelligence/overview",
        "/signals/intelligence/history",
        "/signals/intelligence/outcomes",
        "/signals/intelligence/probability",
        "/signals/intelligence/heatmap",
        "/signals/intelligence/analytics",
        "/signals/intelligence/chart-markers/{symbol}",
    }
    seen = set()
    for route in symbol_signals.router.routes:
        if getattr(route, "path", None) in gated and "GET" in route.methods:
            calls = {d.call for d in route.dependant.dependencies}
            assert symbol_signals.require_signals_subscription in calls, route.path
            seen.add(route.path)
    assert seen == gated
