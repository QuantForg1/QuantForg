"""Phase 1E — sealed credentials + persistence helpers (no real DB required)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services.mt5_worker_api import Mt5WorkerApiFacade
from app.application.services.mt5_worker_control_plane import Mt5WorkerControlPlane
from app.application.services.mt5_worker_credential_seal import (
    seal_credential_material,
    unwrap_credential_material,
)
from services.mt5_worker_agent.credential_unwrap import unwrap_sealed_envelope

pytestmark = [pytest.mark.unit]

TOKEN = "phase1e-worker-service-token"


def test_seal_unwrap_roundtrip_no_password_field() -> None:
    wid = uuid4()
    sealed = seal_credential_material(
        service_token=TOKEN,
        worker_id=wid,
        login="12345",
        server="Demo-Server",
        password="demo-secret",
    )
    assert sealed["authorized"] is True
    assert sealed["password_included"] is False
    assert "password" not in sealed
    assert "demo-secret" not in str(sealed)
    opened = unwrap_credential_material(
        service_token=TOKEN,
        worker_id=wid,
        sealed_envelope=str(sealed["sealed_envelope"]),
    )
    assert opened["login"] == "12345"
    assert opened["server"] == "Demo-Server"
    assert opened["secret"] == "demo-secret"
    agent = unwrap_sealed_envelope(
        service_token=TOKEN,
        worker_id=str(wid),
        sealed_envelope=str(sealed["sealed_envelope"]),
    )
    assert agent["secret"] == "demo-secret"


def test_claim_without_demo_env_does_not_invent_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QF_DEMO_LOGIN", raising=False)
    monkeypatch.delenv("QF_DEMO_PASSWORD", raising=False)
    monkeypatch.delenv("QF_DEMO_SERVER", raising=False)
    api = Mt5WorkerApiFacade(plane=Mt5WorkerControlPlane(service_token=TOKEN))
    reg = api.register(host_code="local-windows-1", slot_id="demo-a")
    claim = api.claim_sealed_credentials(
        worker_id=__import__("uuid").UUID(reg["worker_id"])
    )
    assert claim["ok"] is True
    assert claim["sealed"] is False
    assert claim["password_included"] is False
    assert claim["error"] == "credential_material_unavailable"


def test_claim_with_lab_env_issues_sealed_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QF_DEMO_LOGIN", "99901")
    monkeypatch.setenv("QF_DEMO_SERVER", "Weltrade-Demo")
    monkeypatch.setenv("QF_DEMO_PASSWORD", "lab-only-secret")
    api = Mt5WorkerApiFacade(plane=Mt5WorkerControlPlane(service_token=TOKEN))
    reg = api.register(host_code="local-windows-1", slot_id="demo-b")
    wid = __import__("uuid").UUID(reg["worker_id"])
    claim = api.claim_sealed_credentials(worker_id=wid)
    assert claim["sealed"] is True
    assert claim["password_included"] is False
    assert "lab-only-secret" not in str(claim)
    opened = unwrap_credential_material(
        service_token=TOKEN,
        worker_id=wid,
        sealed_envelope=str(claim["sealed_envelope"]),
    )
    assert opened["login"] == "99901"
    assert opened["secret"] == "lab-only-secret"


def test_revoked_worker_cannot_claim(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QF_DEMO_LOGIN", "1")
    monkeypatch.setenv("QF_DEMO_SERVER", "S")
    monkeypatch.setenv("QF_DEMO_PASSWORD", "x")
    api = Mt5WorkerApiFacade(plane=Mt5WorkerControlPlane(service_token=TOKEN))
    reg = api.register(host_code="h1", slot_id="demo-a")
    wid = __import__("uuid").UUID(reg["worker_id"])
    api.revoke(worker_id=wid)
    with pytest.raises(Exception):
        api.claim_sealed_credentials(worker_id=wid)
