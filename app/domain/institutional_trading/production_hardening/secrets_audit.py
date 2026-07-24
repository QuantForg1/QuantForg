"""Secrets / env audit — names only, never values."""

from __future__ import annotations

from typing import Any


_SENSITIVE_NAME_TOKENS = (
    "SECRET",
    "PASSWORD",
    "TOKEN",
    "API_KEY",
    "APIKEY",
    "PRIVATE",
    "CREDENTIAL",
    "MT5_LOGIN",
    "MT5_PASSWORD",
    "SUPABASE_SERVICE",
    "DATABASE_URL",
    "POSTGRES_PASSWORD",
)


def audit_secret_exposure() -> dict[str, Any]:
    """Report which sensitive env *names* are configured — never echo values."""
    import os

    present: list[str] = []
    missing: list[str] = []
    for key in sorted(os.environ.keys()):
        upper = key.upper()
        if any(tok in upper for tok in _SENSITIVE_NAME_TOKENS):
            val = os.environ.get(key)
            if val is not None and str(val).strip():
                present.append(key)
            else:
                missing.append(key)

    recommendations = [
        "Never log secret values — only names/status.",
        "Rotate Railway secrets periodically.",
        "Restrict MT5 credentials to gateway service only.",
        "Prefer managed secret stores over plaintext .env in production.",
    ]
    return {
        "sensitive_env_names_present": present,
        "sensitive_env_names_empty": missing,
        "values_exposed": False,
        "recommendations": recommendations,
        "ok": True,
    }
