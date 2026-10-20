"""Router boot lifecycle and readiness semantics."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.presentation.router_boot import (
    CRITICAL_READY_ROUTERS,
    empty_router_boot,
    evaluate_readiness,
    merge_registration_summary,
)
from app.presentation.routers.health import router as health_router
from core.config.environments import production_settings, testing_settings


@pytest.mark.unit
def test_evaluate_readiness_untracked_is_ok() -> None:
    out = evaluate_readiness(None)
    assert out["status"] == "ok"
    assert out["http_ready"] is True


@pytest.mark.unit
def test_evaluate_readiness_pending_not_http_ready() -> None:
    boot = empty_router_boot(
        mode="deferred",
        pending=(("portfolio", "app.presentation.routers.portfolio"),),
    )
    out = evaluate_readiness(boot)
    assert out["status"] == "initializing"
    assert out["http_ready"] is False


@pytest.mark.unit
def test_evaluate_readiness_critical_failure() -> None:
    boot = merge_registration_summary(
        empty_router_boot(mode="eager"),
        {"registered": ["health"], "failed": ["auth"], "first_failure": "auth"},
        remaining_pending=(),
    )
    assert "auth" in CRITICAL_READY_ROUTERS
    out = evaluate_readiness(boot)
    assert out["status"] == "not_ready"
    assert out["http_ready"] is False
    assert "auth" in out["routers"]["critical_failed"]


@pytest.mark.unit
def test_evaluate_readiness_optional_failure_is_degraded() -> None:
    boot = merge_registration_summary(
        empty_router_boot(mode="eager"),
        {
            "registered": ["health", "auth"],
            "failed": ["quant_studio"],
            "first_failure": "quant_studio",
        },
        remaining_pending=(),
    )
    out = evaluate_readiness(boot)
    assert out["status"] == "degraded"
    assert out["http_ready"] is True


@pytest.mark.unit
def test_health_ready_returns_503_while_pending() -> None:
    app = FastAPI()
    app.include_router(health_router)
    app.include_router(health_router, prefix="/api/v1")
    app.state.router_boot = empty_router_boot(
        mode="deferred",
        pending=(("execution", "app.presentation.routers.execution"),),
    )
    client = TestClient(app)
    response = client.get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "initializing"
    assert body["routers"]["pending_count"] == 1


@pytest.mark.unit
def test_health_live_always_200_even_when_not_ready() -> None:
    app = FastAPI()
    app.include_router(health_router)
    app.state.router_boot = merge_registration_summary(
        empty_router_boot(mode="eager"),
        {"registered": [], "failed": ["auth"], "first_failure": "auth"},
        remaining_pending=(),
    )
    client = TestClient(app)
    live = client.get("/health/live")
    assert live.status_code == 200
    assert live.json()["status"] == "ok"
    ready = client.get("/health/ready")
    assert ready.status_code == 503
    assert ready.json()["status"] == "not_ready"


@pytest.mark.unit
def test_docs_disabled_in_production_settings() -> None:
    settings = production_settings(
        secret_key="a-real-production-secret-key-with-enough-entropy-here",
        postgres_password="a-real-production-password-here",
    )
    assert settings.docs_enabled is False


@pytest.mark.unit
def test_create_app_docs_urls_follow_docs_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QF_EAGER_ROUTERS", "false")
    from app.main import create_app

    settings = testing_settings(docs_enabled=False)
    app = create_app(settings=settings)
    assert app.docs_url is None
    assert app.openapi_url is None

    settings_on = testing_settings(docs_enabled=True)
    app_on = create_app(settings=settings_on)
    assert app_on.docs_url == "/docs"
    assert app_on.openapi_url == "/openapi.json"


@pytest.mark.unit
def test_create_app_deferred_leaves_pending_and_registers_core(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QF_EAGER_ROUTERS", "false")
    from app.main import _CORE_ROUTER_NAMES, create_app

    settings = testing_settings()
    app = create_app(settings=settings)
    pending = getattr(app.state, "pending_router_specs", ())
    assert pending
    pending_names = {n for n, _ in pending}
    assert "portfolio" in pending_names
    assert "health" not in pending_names
    registered = set(getattr(app.state, "registered_router_names", ()) or ())
    assert registered & _CORE_ROUTER_NAMES
    boot = app.state.router_boot
    assert boot["status"] == "pending"
    assert boot["mode"] == "deferred"


@pytest.mark.unit
def test_register_routers_skips_duplicates(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.main import _register_routers

    settings = testing_settings()
    app = FastAPI()
    app.state.registered_router_names = frozenset()
    first = _register_routers(
        app,
        settings,
        specs=(("version", "app.presentation.routers.version"),),
        mount_unprefixed_health=False,
    )
    second = _register_routers(
        app,
        settings,
        specs=(("version", "app.presentation.routers.version"),),
        mount_unprefixed_health=False,
    )
    assert first["registered"] == ["version"]
    assert second["registered"] == []
    assert "version" in second["skipped_duplicate"]


@pytest.mark.unit
def test_disabled_router_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QF_DISABLED_COMPONENTS", "version")
    from app.main import _register_routers

    settings = testing_settings()
    app = FastAPI()
    app.state.registered_router_names = frozenset()
    summary = _register_routers(
        app,
        settings,
        specs=(("version", "app.presentation.routers.version"),),
        mount_unprefixed_health=False,
    )
    assert summary["registered"] == []
    assert summary["failed"] == []


@pytest.mark.unit
def test_failed_import_is_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.main import _register_routers

    settings = testing_settings()
    app = FastAPI()
    app.state.registered_router_names = frozenset()
    summary = _register_routers(
        app,
        settings,
        specs=(("broken_router", "app.presentation.routers.__does_not_exist__"),),
        mount_unprefixed_health=False,
    )
    assert summary["failed"] == ["broken_router"]
    assert summary["first_failure"] == "broken_router"
