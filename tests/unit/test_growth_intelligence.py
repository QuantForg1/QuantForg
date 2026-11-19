"""Owner-only growth status stays read-only and refuses invented metrics."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import main
from app.application.dto.auth import AuthUserDTO
from app.application.services.growth_intelligence import growth_intelligence_status
from app.domain.identity.designated_owner import DESIGNATED_OWNER_EMAIL
from app.presentation.dependencies.auth import get_current_user
from app.presentation.routers import growth_intelligence as growth_router

pytestmark = pytest.mark.unit


def test_status_document_has_no_numeric_measurements() -> None:
    payload = growth_intelligence_status()
    assert payload["read_only"] is True
    assert payload["places_orders"] is False
    assert payload["ads_kill_switch"] == "stopped"
    assert payload["catalog"]["trial_offered"] is False
    assert payload["catalog"]["plans"]
    for section in payload["sections"]:
        assert section["status"] in {"not_connected", "unavailable", "stopped"}
        for metric in section["metrics"]:
            assert metric["value"] is None
            assert metric["fetched_at"] is None
            assert metric["status"] in {"not_connected", "unavailable", "stopped"}


def test_router_is_get_only_and_owner_gated() -> None:
    methods: set[str] = set()
    for route in growth_router.router.routes:
        methods.update(getattr(route, "methods", set()))
    assert methods <= {"GET", "HEAD"}
    names = [name for name, _path in main._ROUTER_SPECS]
    assert "growth_intelligence" in names
    assert "growth_intelligence" not in main._OPERATOR_ONLY_ROUTER_MODULES


def _client(role: str, email: str) -> TestClient:
    app = FastAPI()
    from app.presentation.middleware.error_handler import register_exception_handlers

    register_exception_handlers(app)
    main._register_routers(
        app,
        SimpleNamespace(api_prefix="/api/v1"),
        specs=(
            ("growth_intelligence", "app.presentation.routers.growth_intelligence"),
        ),
    )
    user = AuthUserDTO(
        id=uuid4(),
        email=email,
        display_name="u",
        role=role,
        status="active",
        auth_user_id=None,
    )
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


def test_trader_and_non_designated_owner_are_forbidden() -> None:
    trader = _client("trader", "trader@example.invalid").get("/api/v1/growth/status")
    assert trader.status_code == 403
    other = _client("owner", "other@example.invalid").get("/api/v1/growth/status")
    assert other.status_code == 403


def test_designated_owner_can_read_status() -> None:
    response = _client("owner", DESIGNATED_OWNER_EMAIL).get("/api/v1/growth/status")
    assert response.status_code == 200
    body = response.json()
    assert body["ads_kill_switch"] == "stopped"
    assert body["sections"][0]["metrics"][0]["value"] is None
