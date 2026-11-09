"""Phase 1C — Railway MT5 worker control-plane API tests (mocked MT5).

These tests exercise authenticated HTTP routes and process-durable state.
They do NOT prove real MetaTrader login or concurrent LIVE trading.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.services.mt5_worker_api import Mt5WorkerApiFacade, lab_ids_for_slot
from app.application.services.mt5_worker_control_plane import Mt5WorkerControlPlane
from app.domain.exceptions.auth import AuthorizationError
from app.domain.multi_account.feature_gates import multi_account_live_submit_allowed
from app.presentation.middleware.error_handler import register_exception_handlers
from app.presentation.routers import mt5_workers as mt5_workers_router
from core.config.settings import Settings

pytestmark = [pytest.mark.unit]

TOKEN = "phase1c-worker-service-token"


def _facade() -> Mt5WorkerApiFacade:
    return Mt5WorkerApiFacade(
        plane=Mt5WorkerControlPlane(service_token=TOKEN),
        stale_after=timedelta(seconds=45),
    )


def _client(
    facade: Mt5WorkerApiFacade | None = None,
) -> tuple[TestClient, Mt5WorkerApiFacade]:
    api = facade or _facade()
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(mt5_workers_router.router, prefix="/api/v1")
    app.state.mt5_worker_api = api

    def _auth() -> str:
        return "authenticated"

    def _api() -> Mt5WorkerApiFacade:
        return api

    app.dependency_overrides[mt5_workers_router.WorkerAuth] = _auth  # type: ignore[attr-defined]
    # WorkerAuth is Annotated — override the underlying callable.
    from app.presentation.dependencies import mt5_workers as deps

    app.dependency_overrides[deps.require_worker_service_token] = _auth
    app.dependency_overrides[deps.get_mt5_worker_api] = _api
    return TestClient(app), api


def test_live_flags_still_false() -> None:
    settings = Settings(_env_file=None)
    assert settings.multi_account_dispatch_enabled is False
    assert settings.multi_account_live_submit_enabled is False
    assert multi_account_live_submit_allowed(settings) is False


def test_register_heartbeat_assignment_idempotent() -> None:
    client, _api = _client()
    r1 = client.post(
        "/api/v1/mt5-workers/register",
        json={"host_code": "local-windows-1", "slot_id": "demo-a"},
    )
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["ok"] is True
    assert body1["credentials_exposed"] is False
    wid = body1["worker_id"]

    r2 = client.post(
        "/api/v1/mt5-workers/register",
        json={"host_code": "local-windows-1", "slot_id": "demo-a"},
    )
    assert r2.status_code == 200
    assert r2.json()["worker_id"] == wid
    assert r2.json()["idempotent"] is True

    hb = client.post(
        "/api/v1/mt5-workers/heartbeat",
        json={
            "worker_id": wid,
            "slot_id": "demo-a",
            "lifecycle": "starting",
            "ready": False,
        },
    )
    assert hb.status_code == 200
    assert hb.json()["ok"] is True
    assert hb.json()["last_heartbeat_at"] is not None

    assign = client.get(f"/api/v1/mt5-workers/assignments/{wid}")
    assert assign.status_code == 200
    payload = assign.json()
    assert payload["ok"] is True
    assert payload["credentials"]["credentials_exposed"] is False
    blob = str(payload).lower()
    assert "password" not in blob
    assert "secret" not in blob


def test_abc_workers_independent_and_isolated() -> None:
    client, api = _client()
    ids = []
    for slot in ("demo-a", "demo-b", "demo-c"):
        resp = client.post(
            "/api/v1/mt5-workers/register",
            json={"host_code": "local-windows-1", "slot_id": slot},
        )
        assert resp.status_code == 200
        ids.append(UUID(resp.json()["worker_id"]))
    assert len(set(ids)) == 3

    # Fail / revoke A only.
    revoked = client.post("/api/v1/mt5-workers/revoke", json={"worker_id": str(ids[0])})
    assert revoked.status_code == 200
    assert revoked.json()["revoked"] is True or revoked.json()["lifecycle"] == "revoked"

    # B and C still heartbeating.
    for wid in ids[1:]:
        hb = client.post(
            "/api/v1/mt5-workers/heartbeat",
            json={"worker_id": str(wid), "ready": False},
        )
        assert hb.status_code == 200
        assert hb.json()["ok"] is True

    # A denied after revoke.
    denied = client.post(
        "/api/v1/mt5-workers/heartbeat",
        json={"worker_id": str(ids[0]), "ready": False},
    )
    assert denied.status_code in {401, 403}

    # Cross-slot mismatch denied.
    with pytest.raises(AuthorizationError):
        api.heartbeat(worker_id=ids[1], slot_id="demo-a")


def test_stale_detection_and_reconnect() -> None:
    api = _facade()
    reg = api.register(host_code="h1", slot_id="demo-a")
    wid = UUID(reg["worker_id"])
    reg_b = api.register(host_code="h1", slot_id="demo-b")
    wid_b = UUID(reg_b["worker_id"])
    start = datetime.now(UTC)
    api.heartbeat(worker_id=wid, now=start)
    future = start + timedelta(seconds=120)
    api.heartbeat(worker_id=wid_b, now=future)
    stale = api.scan_stale(now=future)
    stale_ids = {UUID(w["worker_id"]) for w in stale["workers"]}
    assert wid in stale_ids
    assert wid_b not in stale_ids
    recon = api.reconnect(worker_id=wid)
    assert recon["lifecycle"] == "reconnecting"
    assert recon["reconnect_backoff_seconds"] >= 2.0


def test_credentials_authorize_never_returns_password() -> None:
    client, _ = _client()
    reg = client.post(
        "/api/v1/mt5-workers/register",
        json={"host_code": "h1", "slot_id": "demo-a"},
    ).json()
    authz = client.post(
        "/api/v1/mt5-workers/credentials/authorize",
        json={"worker_id": reg["worker_id"]},
    )
    assert authz.status_code == 200
    body = authz.json()
    assert body["authorized"] is True
    assert body["credentials_exposed"] is False
    assert "password" not in body or body.get("password") in (None, False)


def test_unauthenticated_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKER_SERVICE_TOKEN", TOKEN)
    from core.config.settings import get_settings

    get_settings.cache_clear()
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(mt5_workers_router.router, prefix="/api/v1")
    app.state.mt5_worker_api = _facade()
    # No dependency overrides — real token check.
    client = TestClient(app, raise_server_exceptions=False)
    missing = client.post(
        "/api/v1/mt5-workers/register",
        json={"host_code": "h1", "slot_id": "demo-a"},
    )
    assert missing.status_code in {401, 403}
    bad = client.post(
        "/api/v1/mt5-workers/register",
        headers={"Authorization": "Bearer wrong-token-xxxxxxxxxx"},
        json={"host_code": "h1", "slot_id": "demo-a"},
    )
    assert bad.status_code in {401, 403}
    get_settings.cache_clear()


def test_lab_ids_stable_per_slot() -> None:
    a1, b1 = lab_ids_for_slot(host_code="local-windows-1", slot_id="demo-a")
    a2, b2 = lab_ids_for_slot(host_code="local-windows-1", slot_id="demo-a")
    c1, _ = lab_ids_for_slot(host_code="local-windows-1", slot_id="demo-b")
    assert a1 == a2 and b1 == b2
    assert a1 != c1


def test_health_and_release() -> None:
    client, _ = _client()
    wid = client.post(
        "/api/v1/mt5-workers/register",
        json={"host_code": "h1", "slot_id": "demo-a"},
    ).json()["worker_id"]
    health = client.post(
        "/api/v1/mt5-workers/health",
        json={
            "worker_id": wid,
            "cpu_percent": 12.5,
            "ram_percent": 40.0,
            "disk_percent": 70.0,
            "healthy": True,
            "details": {"note": "idle", "password": "must-be-stripped"},
        },
    )
    assert health.status_code == 200
    assert "password" not in health.json().get("details_keys", [])
    released = client.post("/api/v1/mt5-workers/release", json={"worker_id": wid})
    assert released.status_code == 200
    assert released.json()["lifecycle"] == "stopped"
