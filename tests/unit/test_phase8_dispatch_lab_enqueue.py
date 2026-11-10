"""Phase 8 — staging lab enqueue security + assignment-bound claim regressions."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.services.mt5_worker_api import Mt5WorkerApiFacade
from app.application.services.mt5_worker_control_plane import Mt5WorkerControlPlane
from app.application.services.multi_account_dispatch_queue import (
    reset_durable_dispatch_queue_for_tests,
)
from app.presentation.middleware.error_handler import register_exception_handlers
from app.presentation.routers import mt5_workers as mt5_workers_router
from core.config.settings import AppEnvironment, Settings

pytestmark = [pytest.mark.unit]

TOKEN = "phase8-worker-service-token"


def _fake_settings(*, env: AppEnvironment, lab: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        app_env=env,
        qf_dispatch_lab_enabled=lab,
        multi_account_dispatch_enabled=False,
        multi_account_live_submit_enabled=False,
    )


def _client() -> tuple[TestClient, Mt5WorkerApiFacade]:
    reset_durable_dispatch_queue_for_tests()
    api = Mt5WorkerApiFacade(plane=Mt5WorkerControlPlane(service_token=TOKEN))
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(mt5_workers_router.router, prefix="/api/v1")
    app.state.mt5_worker_api = api
    from app.presentation.dependencies import mt5_workers as deps

    app.dependency_overrides[deps.require_worker_service_token] = lambda: "ok"
    app.dependency_overrides[deps.get_mt5_worker_api] = lambda: api
    return TestClient(app), api


def _register_heartbeat_attest(
    client: TestClient, *, host: str = "h1", slot: str = "demo-a"
) -> str:
    wid = client.post(
        "/api/v1/mt5-workers/register",
        json={"host_code": host, "slot_id": slot},
    ).json()["worker_id"]
    hb = client.post(
        "/api/v1/mt5-workers/heartbeat",
        json={"worker_id": wid, "slot_id": slot, "lifecycle": "provisioning"},
    )
    assert hb.status_code == 200
    assert hb.json()["ok"] is True
    attest = client.post(
        "/api/v1/mt5-workers/lab/attest-assignment",
        json={"worker_id": wid},
    )
    assert attest.status_code == 200
    assert attest.json()["ok"] is True
    return wid


def test_lab_enqueue_forbidden_in_production_returns_403(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        mt5_workers_router,
        "get_settings",
        lambda: _fake_settings(env=AppEnvironment.PRODUCTION, lab=True),
    )
    client, _ = _client()
    wid = client.post(
        "/api/v1/mt5-workers/register",
        json={"host_code": "h1", "slot_id": "demo-a"},
    ).json()["worker_id"]
    resp = client.post(
        "/api/v1/mt5-workers/dispatch/lab-enqueue",
        json={"worker_id": wid},
    )
    assert resp.status_code == 403
    body = resp.json()
    assert body["ok"] is False
    assert body["error"] == "lab_enqueue_disabled"
    assert body["live_submit_allowed"] is False


def test_lab_enqueue_rejects_registration_without_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        mt5_workers_router,
        "get_settings",
        lambda: _fake_settings(env=AppEnvironment.STAGING),
    )
    client, _ = _client()
    wid = client.post(
        "/api/v1/mt5-workers/register",
        json={"host_code": "h1", "slot_id": "demo-a"},
    ).json()["worker_id"]
    # Register only — no heartbeat / attestation.
    resp = client.post(
        "/api/v1/mt5-workers/dispatch/lab-enqueue",
        json={"worker_id": wid},
    )
    assert resp.status_code == 403
    assert resp.json()["error"] == "heartbeat_required"


def test_lab_enqueue_rejects_heartbeat_without_attestation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        mt5_workers_router,
        "get_settings",
        lambda: _fake_settings(env=AppEnvironment.STAGING),
    )
    client, _ = _client()
    wid = client.post(
        "/api/v1/mt5-workers/register",
        json={"host_code": "h1", "slot_id": "demo-a"},
    ).json()["worker_id"]
    client.post(
        "/api/v1/mt5-workers/heartbeat",
        json={"worker_id": wid, "slot_id": "demo-a"},
    )
    resp = client.post(
        "/api/v1/mt5-workers/dispatch/lab-enqueue",
        json={"worker_id": wid},
    )
    assert resp.status_code == 403
    assert resp.json()["error"] == "assignment_unverified"


def test_lab_attest_forbidden_outside_staging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        mt5_workers_router,
        "get_settings",
        lambda: _fake_settings(env=AppEnvironment.DEVELOPMENT, lab=True),
    )
    client, _ = _client()
    wid = client.post(
        "/api/v1/mt5-workers/register",
        json={"host_code": "h1", "slot_id": "demo-a"},
    ).json()["worker_id"]
    client.post(
        "/api/v1/mt5-workers/heartbeat",
        json={"worker_id": wid, "slot_id": "demo-a"},
    )
    resp = client.post(
        "/api/v1/mt5-workers/lab/attest-assignment",
        json={"worker_id": wid},
    )
    assert resp.status_code == 403
    assert resp.json()["error"] == "staging_attestation_required"


def test_lab_enqueue_claim_ack_on_staging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mt5_workers_router,
        "get_settings",
        lambda: _fake_settings(env=AppEnvironment.STAGING),
    )
    client, api = _client()
    wid = _register_heartbeat_attest(client)
    worker = api.require_worker(UUID(wid))
    enq = client.post(
        "/api/v1/mt5-workers/dispatch/lab-enqueue",
        json={"worker_id": wid, "idempotency_key": "phase8-lab-1"},
    )
    assert enq.status_code == 200
    body = enq.json()
    assert body["ok"] is True
    assert body["live_submit_allowed"] is False
    assert body["staging_lab_synthetic_readiness"] is True
    assert body["job_count"] == 1
    assert "password" not in str(body).lower()

    spoof = client.post(
        "/api/v1/mt5-workers/dispatch/claim",
        json={
            "worker_id": wid,
            "user_id": "00000000-0000-0000-0000-000000000099",
            "broker_account_id": "00000000-0000-0000-0000-000000000098",
        },
    ).json()
    assert spoof["ok"] is False
    assert spoof["error"] == "assignment_mismatch"

    claim = client.post(
        "/api/v1/mt5-workers/dispatch/claim",
        json={
            "worker_id": wid,
            "user_id": str(worker.user_id),
            "broker_account_id": str(worker.broker_account_id),
        },
    ).json()
    assert claim["ok"] is True
    assert claim["job"] is not None
    intent_id = claim["job"]["intent_id"]

    ack = client.post(
        "/api/v1/mt5-workers/dispatch/ack",
        json={"worker_id": wid, "intent_id": intent_id, "detail": "ok"},
    ).json()
    assert ack["ok"] is True
    assert ack["job"]["delivery_status"] == "acked"
    assert ack["live_submit_allowed"] is False


def test_settings_default_lab_flag_false() -> None:
    settings = Settings(_env_file=None)
    assert settings.qf_dispatch_lab_enabled is False
    assert settings.multi_account_dispatch_enabled is False
    assert settings.multi_account_live_submit_enabled is False


def test_lab_enqueue_idempotent_recover_and_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        mt5_workers_router,
        "get_settings",
        lambda: _fake_settings(env=AppEnvironment.STAGING),
    )
    client, api = _client()
    wid = _register_heartbeat_attest(client)
    worker = api.require_worker(UUID(wid))
    key = "phase8-lab-idem"
    first = client.post(
        "/api/v1/mt5-workers/dispatch/lab-enqueue",
        json={"worker_id": wid, "idempotency_key": key},
    ).json()
    second = client.post(
        "/api/v1/mt5-workers/dispatch/lab-enqueue",
        json={"worker_id": wid, "idempotency_key": key},
    ).json()
    assert first["ok"] is True and second["ok"] is True
    assert first["jobs"][0]["intent_id"] == second["jobs"][0]["intent_id"]

    claim = client.post(
        "/api/v1/mt5-workers/dispatch/claim",
        json={
            "worker_id": wid,
            "user_id": str(worker.user_id),
            "broker_account_id": str(worker.broker_account_id),
        },
    ).json()
    assert claim["job"] is not None
    intent_id = claim["job"]["intent_id"]

    recovered = client.post("/api/v1/mt5-workers/dispatch/recover", json={}).json()
    assert recovered["ok"] is True
    assert recovered["recovered"] >= 1

    claim2 = client.post(
        "/api/v1/mt5-workers/dispatch/claim",
        json={
            "worker_id": wid,
            "user_id": str(worker.user_id),
            "broker_account_id": str(worker.broker_account_id),
        },
    ).json()
    assert claim2["job"] is not None
    assert claim2["job"]["intent_id"] == intent_id

    fail = client.post(
        "/api/v1/mt5-workers/dispatch/fail",
        json={
            "worker_id": wid,
            "intent_id": intent_id,
            "reason": "phase8_forced_fail",
        },
    ).json()
    assert fail["ok"] is True
    assert fail["job"]["delivery_status"] in {"pending", "dead_letter"}
    assert fail["live_submit_allowed"] is False


def test_ops_summary_explains_execution_workers_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        mt5_workers_router,
        "get_settings",
        lambda: _fake_settings(env=AppEnvironment.STAGING),
    )
    client, _ = _client()
    client.post(
        "/api/v1/mt5-workers/register",
        json={"host_code": "h1", "slot_id": "demo-a"},
    )
    ops = client.get("/api/v1/mt5-workers/ops/summary").json()
    assert ops.get("ok") is True
    assert ops.get("live_submit_enabled") is False
    assert "execution_workers_note" in ops
    assert "control_plane_worker_count" in ops
    assert ops.get("credentials_exposed") is False
    # Notes may mention passwords are never stored; ensure no secret fields leak.
    blob = str(ops).lower()
    assert '"password":' not in blob
    assert "'password':" not in blob
    assert "sealed_envelope" not in blob


def test_harness_heartbeat_helper_rejects_register_fallback() -> None:
    from scripts.staging_phase8_dispatch_demo import _assert_no_secrets, _heartbeat_ok

    assert _heartbeat_ok({"railway": {}}) is False
    assert _heartbeat_ok({"railway": {"demo-a": {"ok": False}}}) is False
    assert _heartbeat_ok({"ok": True}) is False  # registration-shaped payload
    assert _heartbeat_ok({"railway": {"demo-a": {"ok": True}}}) is True
    # Docs notes may mention passwords; only structured secret fields fail.
    assert _assert_no_secrets({"note": "passwords are never stored"}) is True
    assert _assert_no_secrets({"password": "secret-value"}) is False


def test_lab_bound_detection_from_deterministic_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        mt5_workers_router,
        "get_settings",
        lambda: _fake_settings(env=AppEnvironment.STAGING),
    )
    client, api = _client()
    wid = client.post(
        "/api/v1/mt5-workers/register",
        json={"host_code": "h1", "slot_id": "demo-a"},
    ).json()["worker_id"]
    worker = api.require_worker(UUID(wid))
    # Strip lab_binding flag but keep deterministic lab ids / slot map.
    from app.application.services.mt5_worker_api import _with_metadata

    stripped = api.plane.provisioner.save(  # type: ignore[union-attr]
        _with_metadata(worker, {"slot_id": "demo-a", "host_code": "h1"})
    )
    assert stripped.metadata.get("lab_binding") is not True
    assert api._is_lab_bound_assignment(stripped) is True
    client.post(
        "/api/v1/mt5-workers/heartbeat",
        json={"worker_id": wid, "slot_id": "demo-a"},
    )
    attest = client.post(
        "/api/v1/mt5-workers/lab/attest-assignment",
        json={"worker_id": wid},
    )
    assert attest.status_code == 200
    assert attest.json()["ok"] is True
