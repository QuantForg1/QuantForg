"""Phase 8 — sealed credential delivery, redaction, and replay controls."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services.mt5_worker_api import Mt5WorkerApiFacade
from app.application.services.mt5_worker_control_plane import Mt5WorkerControlPlane
from app.application.services.mt5_worker_credential_seal import (
    redact_credential_blob,
    seal_credential_material,
    unwrap_credential_material,
)
from app.domain.exceptions.auth import AuthorizationError

pytestmark = [pytest.mark.unit]

TOKEN = "phase8-sealed-credential-token"


def test_seal_unwrap_round_trip_no_password_field() -> None:
    wid = uuid4()
    sealed = seal_credential_material(
        service_token=TOKEN,
        worker_id=wid,
        login="1001",
        server="Demo-Server",
        password="lab-only-secret",
    )
    assert sealed["sealed"] is True
    assert sealed["credentials_exposed"] is False
    assert "password" not in sealed
    assert sealed["claim_id"]
    plain = unwrap_credential_material(
        service_token=TOKEN,
        worker_id=wid,
        sealed_envelope=sealed["sealed_envelope"],
    )
    assert plain["login"] == "1001"
    assert plain["server"] == "Demo-Server"
    assert plain["secret"] == "lab-only-secret"
    assert plain["claim_id"] == sealed["claim_id"]


def test_unwrap_rejects_wrong_worker() -> None:
    sealed = seal_credential_material(
        service_token=TOKEN,
        worker_id=uuid4(),
        login="1001",
        server="Demo-Server",
        password="lab-only-secret",
    )
    with pytest.raises(ValueError, match="sealed_envelope"):
        unwrap_credential_material(
            service_token=TOKEN,
            worker_id=uuid4(),
            sealed_envelope=sealed["sealed_envelope"],
        )


def test_redact_credential_blob_strips_secrets() -> None:
    blob = redact_credential_blob(
        {
            "ok": True,
            "password": "nope",
            "nested": {"sealed_envelope": "abc", "login": "1001"},
            "items": [{"secret": "x"}],
        }
    )
    assert blob["password"] == "***REDACTED***"
    assert blob["nested"]["sealed_envelope"] == "***REDACTED***"
    assert blob["nested"]["login"] == "1001"
    assert blob["items"][0]["secret"] == "***REDACTED***"


def test_claim_requires_heartbeat_and_rotates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QF_DEMO_LOGIN", "2002")
    monkeypatch.setenv("QF_DEMO_SERVER", "Demo-Server")
    monkeypatch.setenv("QF_DEMO_PASSWORD", "lab-only-secret")
    api = Mt5WorkerApiFacade(plane=Mt5WorkerControlPlane(service_token=TOKEN))
    reg = api.register(host_code="h1", slot_id="demo-a")
    wid = reg["worker_id"]
    from uuid import UUID

    worker_id = UUID(str(wid))
    with pytest.raises(AuthorizationError) as exc:
        api.claim_sealed_credentials(worker_id=worker_id)
    assert getattr(exc.value, "code", None) == "heartbeat_required"

    api.heartbeat(worker_id=worker_id, slot_id="demo-a")
    first = api.claim_sealed_credentials(worker_id=worker_id)
    assert first["sealed"] is True
    assert first["credentials_exposed"] is False
    assert "password" not in first
    second = api.claim_sealed_credentials(worker_id=worker_id)
    assert second["claim_id"] != first["claim_id"]
    assert second["rotated_previous_claim"] is True
    assert second["previous_claim_id"] == first["claim_id"]

    api.revoke(worker_id=worker_id)
    with pytest.raises(AuthorizationError):
        api.claim_sealed_credentials(worker_id=worker_id)
