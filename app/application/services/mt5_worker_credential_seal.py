"""Sealed credential delivery for authorized MT5 workers (Phase 1E / Phase 8).

Plaintext passwords are never placed in API JSON fields named ``password``.
The worker unwraps an opaque sealed envelope locally using the shared
WORKER_SERVICE_TOKEN material. Revoked workers must not receive envelopes.

Replay controls:
- Each seal includes a unique ``claim_id``.
- Fernet timestamps enable TTL expiry on unwrap.
- Callers must track claim_ids for rotation / revocation.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any
from uuid import UUID, uuid4

from cryptography.fernet import Fernet, InvalidToken

DEFAULT_SEAL_TTL_SECONDS = 300


def _fernet_for_worker(*, service_token: str, worker_id: UUID | str) -> Fernet:
    material = f"qf-mt5-worker-cred-v1|{service_token.strip()}|{worker_id}".encode()
    digest = hashlib.sha256(material).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def seal_credential_material(
    *,
    service_token: str,
    worker_id: UUID | str,
    login: str,
    server: str,
    password: str,
    claim_id: str | None = None,
) -> dict[str, Any]:
    """Build an opaque sealed envelope. Never includes plaintext password keys."""
    if not password.strip():
        return {
            "authorized": False,
            "credentials_exposed": False,
            "sealed": False,
            "error": "credential_unavailable",
        }
    cid = (claim_id or "").strip() or str(uuid4())
    f = _fernet_for_worker(service_token=service_token, worker_id=worker_id)
    payload = json.dumps(
        {
            "login": str(login),
            "server": str(server),
            "secret": password,
            "claim_id": cid,
            "worker_id": str(worker_id),
        },
        separators=(",", ":"),
    ).encode("utf-8")
    token = f.encrypt(payload).decode("ascii")
    return {
        "authorized": True,
        "credentials_exposed": False,
        "sealed": True,
        "envelope_version": 2,
        "worker_id": str(worker_id),
        "claim_id": cid,
        "ttl_seconds": DEFAULT_SEAL_TTL_SECONDS,
        "sealed_envelope": token,
        "note": (
            "Opaque sealed envelope for the assigned Windows worker only. "
            "Unwrap locally within ttl_seconds; never log the envelope contents."
        ),
    }


def unwrap_credential_material(
    *,
    service_token: str,
    worker_id: UUID | str,
    sealed_envelope: str,
    ttl_seconds: int = DEFAULT_SEAL_TTL_SECONDS,
) -> dict[str, str]:
    """Worker-side unwrap. Returns login/server/secret; caller must not log secret."""
    f = _fernet_for_worker(service_token=service_token, worker_id=worker_id)
    try:
        raw = f.decrypt(
            sealed_envelope.encode("ascii"),
            ttl=max(1, int(ttl_seconds)),
        )
    except InvalidToken as exc:
        raise ValueError("sealed_envelope_invalid") from exc
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("sealed_envelope_invalid_payload")
    bound = str(data.get("worker_id") or "")
    if bound and bound != str(worker_id):
        raise ValueError("sealed_envelope_worker_mismatch")
    login = str(data.get("login") or "")
    server = str(data.get("server") or "")
    secret = str(data.get("secret") or "")
    claim_id = str(data.get("claim_id") or "")
    if not login or not server or not secret:
        raise ValueError("sealed_envelope_incomplete")
    return {
        "login": login,
        "server": server,
        "secret": secret,
        "claim_id": claim_id,
    }


def redact_credential_blob(value: Any) -> Any:
    """Recursively redact secret-bearing keys from diagnostic structures."""
    secret_keys = {
        "password",
        "secret",
        "passwd",
        "sealed_envelope",
        "investor_password",
        "qf_demo_password",
        "worker_service_token",
    }
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in secret_keys:
                out[str(key)] = "***REDACTED***"
            else:
                out[str(key)] = redact_credential_blob(item)
        return out
    if isinstance(value, list):
        return [redact_credential_blob(item) for item in value]
    return value
