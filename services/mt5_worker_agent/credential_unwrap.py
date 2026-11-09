"""Local unwrap of sealed credential envelopes (Windows worker only).

Never logs secret material. Used after an authorized claim from Railway.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("quantforg.mt5_worker_agent.cred")


def unwrap_sealed_envelope(
    *, service_token: str, worker_id: str, sealed_envelope: str
) -> dict[str, str]:
    material = f"qf-mt5-worker-cred-v1|{service_token.strip()}|{worker_id}".encode()
    digest = hashlib.sha256(material).digest()
    fernet = Fernet(base64.urlsafe_b64encode(digest))
    try:
        raw = fernet.decrypt(sealed_envelope.encode("ascii"))
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
    logger.info(
        "sealed_envelope_unwrapped worker_id=%s login=%s server=%s secret_len=%s",
        worker_id,
        login,
        server,
        len(secret),
    )
    return {"login": login, "server": server, "secret": secret}


def claim_result_safe_summary(payload: dict[str, Any]) -> dict[str, Any]:
    """Redact envelope contents for status printing."""
    return {
        "ok": bool(payload.get("ok")),
        "authorized": bool(payload.get("authorized")),
        "sealed": bool(payload.get("sealed")),
        "password_included": bool(payload.get("password_included")),
        "error": payload.get("error"),
        "has_envelope": bool(payload.get("sealed_envelope")),
    }
