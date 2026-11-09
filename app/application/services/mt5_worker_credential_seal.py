"""Sealed credential delivery for authorized MT5 workers (Phase 1E).

Plaintext passwords are never placed in API JSON fields named ``password``.
The worker unwraps an opaque sealed envelope locally using the shared
WORKER_SERVICE_TOKEN material. Revoked workers must not receive envelopes.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken


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
) -> dict[str, Any]:
    """Build an opaque sealed envelope. Never includes plaintext password keys."""
    if not password.strip():
        return {
            "authorized": False,
            "password_included": False,
            "sealed": False,
            "error": "credential_unavailable",
        }
    f = _fernet_for_worker(service_token=service_token, worker_id=worker_id)
    payload = json.dumps(
        {
            "login": str(login),
            "server": str(server),
            "secret": password,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    token = f.encrypt(payload).decode("ascii")
    return {
        "authorized": True,
        "password_included": False,
        "sealed": True,
        "envelope_version": 1,
        "worker_id": str(worker_id),
        "sealed_envelope": token,
        "note": (
            "Opaque sealed envelope for the assigned Windows worker only. "
            "Unwrap locally; never log the envelope contents."
        ),
    }


def unwrap_credential_material(
    *,
    service_token: str,
    worker_id: UUID | str,
    sealed_envelope: str,
) -> dict[str, str]:
    """Worker-side unwrap. Returns login/server/secret; caller must not log secret."""
    f = _fernet_for_worker(service_token=service_token, worker_id=worker_id)
    try:
        raw = f.decrypt(sealed_envelope.encode("ascii"))
    except InvalidToken as exc:
        raise ValueError("sealed_envelope_invalid") from exc
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("sealed_envelope_invalid_payload")
    login = str(data.get("login") or "")
    server = str(data.get("server") or "")
    secret = str(data.get("secret") or "")
    if not login or not server or not secret:
        raise ValueError("sealed_envelope_incomplete")
    return {"login": login, "server": server, "secret": secret}
