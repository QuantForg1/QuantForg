"""Owner-only growth status stays read-only and refuses invented metrics."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import main
from app.application.dto.auth import AuthUserDTO
from app.application.services.growth_automation import reset_growth_automation_state
from app.application.services.growth_intelligence import growth_intelligence_status
from app.domain.billing.plans import plans_public
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


def test_router_writes_are_owner_checks_only() -> None:
    methods: set[str] = set()
    post_paths: list[str] = []
    for route in growth_router.router.routes:
        route_methods = getattr(route, "methods", set())
        methods.update(route_methods)
        if "POST" in route_methods:
            post_paths.append(getattr(route, "path", ""))
    assert methods <= {"GET", "HEAD", "POST"}
    assert sorted(post_paths) == [
        "/growth/automation/emergency-stop",
        "/growth/automation/run",
        "/growth/content/drafts",
        "/growth/content/publish",
    ]
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
    assert body["automation"]["emergency_stop"] is True
    assert body["automation"]["scheduler_attachment"] == "not_registered"
    assert body["automation"]["places_orders"] is False
    assert body["automation"]["ads_can_be_enabled"] is False
    assert body["automation"]["clock"]["attached"] is False
    assert body["automation"]["permissions"]["ads"] == "prohibited"
    assert body["automation"]["permissions"]["publish"] == "approval_required_not_implemented"


def test_emergency_stop_blocks_then_allows_one_check() -> None:
    reset_growth_automation_state()
    client = _client("owner", DESIGNATED_OWNER_EMAIL)
    blocked = client.post("/api/v1/growth/automation/run", json={"job_id": "catalog_prices"})
    assert blocked.status_code == 200
    assert blocked.json()["executed"] is False
    assert blocked.json()["status"] == "stopped"

    released = client.post(
        "/api/v1/growth/automation/emergency-stop",
        json={"engaged": False},
    )
    assert released.status_code == 200
    assert released.json()["ads_can_be_enabled"] is False
    assert released.json()["places_orders"] is False

    ran = client.post("/api/v1/growth/automation/run", json={"job_id": "catalog_prices"})
    assert ran.status_code == 200
    body = ran.json()
    assert body["executed"] is True
    assert body["result"]["subscriber_count"] is None
    assert body["result"]["prices_usd"] == [plan["monthly_price_usd"] for plan in plans_public()]

    replay = client.post("/api/v1/growth/automation/run", json={"job_id": "catalog_prices"})
    assert replay.json()["idempotent_replay"] is True
    assert replay.json()["id"] == body["id"]

    seo = client.post("/api/v1/growth/automation/run", json={"job_id": "seo_contract"})
    assert seo.json()["result"]["indexed_page_count"] is None
    assert seo.json()["result"]["search_volume"] is None

    unknown = client.post("/api/v1/growth/automation/run", json={"job_id": "enable_ads"})
    assert unknown.status_code == 422

    draft = client.post(
        "/api/v1/growth/content/drafts",
        json={"title": "Internal note", "body": "Not for publication."},
    )
    assert draft.status_code == 200
    assert draft.json()["published"] is False
    draft_id = draft.json()["draft"]["id"]
    publish = client.post("/api/v1/growth/content/publish", json={"draft_id": draft_id})
    assert publish.status_code == 200
    assert publish.json()["published"] is False
    assert publish.json()["status"] == "approval_required"

    client.post("/api/v1/growth/automation/emergency-stop", json={"engaged": True})
    stopped_draft = client.post(
        "/api/v1/growth/content/drafts",
        json={"title": "Blocked", "body": "Should not save."},
    )
    assert stopped_draft.json()["executed"] is False
    assert stopped_draft.json()["status"] == "stopped"
    reset_growth_automation_state()


def test_trader_cannot_run_growth_checks() -> None:
    client = _client("trader", "trader@example.invalid")
    assert client.post(
        "/api/v1/growth/automation/run",
        json={"job_id": "catalog_prices"},
    ).status_code == 403
    assert client.post(
        "/api/v1/growth/content/publish",
        json={"draft_id": "x"},
    ).status_code == 403
