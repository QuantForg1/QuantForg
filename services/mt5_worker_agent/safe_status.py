"""Redact secrets from worker status / diagnostic JSON payloads.

Status and health outputs must never contain password, token, or secret
values — including nested keys and accidental exception text.
"""

from __future__ import annotations

from typing import Any

_FORBIDDEN_KEY_TOKENS = (
    "password",
    "passwd",
    "secret",
    "token",
    "credential",
    "api_key",
    "apikey",
    "authorization",
    "bearer",
)


def _key_forbidden(key: str) -> bool:
    low = str(key).lower()
    return any(tok in low for tok in _FORBIDDEN_KEY_TOKENS)


def redact_secrets(value: Any) -> Any:
    """Deep-copy payload without forbidden keys or secret-like strings."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if _key_forbidden(str(key)):
                continue
            out[str(key)] = redact_secrets(item)
        return out
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    if isinstance(value, str):
        low = value.lower()
        # Drop accidental secret-bearing diagnostic phrases.
        if any(tok in low for tok in ("password=", "password:", "bearer ", "secret=")):
            return "[redacted]"
        return value
    return value


def public_status_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Sanitize operator status payload for CLI / health printing."""
    cleaned = redact_secrets(dict(payload))
    # Explicit safe flag — never use a key containing the substring "password".
    cleaned["credentials_exposed"] = False
    return cleaned
