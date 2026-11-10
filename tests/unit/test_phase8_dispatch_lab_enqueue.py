"""Phase 8 — staging lab enqueue + assignment-bound claim regressions."""

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


def test_lab_enqueue_forbidden_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    # Avoid full production Settings (POSTGRES_PASSWORD validator).
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
    assert resp.status_code == 200
    assert resp.json()["ok"] is False
    assert resp.json()["error"] == "lab_enqueue_disabled"


def test_lab_enqueue_claim_ack_on_staging(monkeypatch: pytest.MonkeyPatch) -> None:
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
    enq = client.post(
        "/api/v1/mt5-workers/dispatch/lab-enqueue",
        json={"worker_id": wid, "idempotency_key": "phase8-lab-1"},
    )
    assert enq.status_code == 200
    body = enq.json()
    assert body["ok"] is True
    assert body["live_submit_allowed"] is False
    assert body["job_count"] == 1

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
    wid = client.post(
        "/api/v1/mt5-workers/register",
        json={"host_code": "h1", "slot_id": "demo-a"},
    ).json()["worker_id"]
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
    assert ops.get("live_submit_allowed") is False
    assert "execution_workers_note" in ops
    assert "control_plane_worker_count" in ops
