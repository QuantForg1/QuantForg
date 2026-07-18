"""Classify live MT5 probe failures — never invents causes."""

from __future__ import annotations

from typing import Any

from app.domain.broker_connectivity.certification_states import (
    CertificationDiagnostic,
)


def classify_diagnostic(
    *,
    reason: str = "",
    capability: str = "",
    status: str = "",
) -> CertificationDiagnostic:
    """Map structured probe text to a diagnostic code (best-effort)."""
    text = f"{status} {capability} {reason}".lower()
    if not reason and status in {"", "ok", "compatible"}:
        return CertificationDiagnostic.NONE

    if any(
        t in text
        for t in (
            "wrong server",
            "server mismatch",
            "does not match",
            "unknown server",
        )
    ):
        return CertificationDiagnostic.WRONG_SERVER

    if any(
        t in text
        for t in (
            "invalid password",
            "invalid credentials",
            "authorization failed",
            "auth failed",
            "login failed",
            "unauthorized",
        )
    ):
        return CertificationDiagnostic.INVALID_CREDENTIALS

    if any(t in text for t in ("timeout", "timed out", "deadline")):
        return CertificationDiagnostic.TIMEOUT

    if any(
        t in text
        for t in (
            "market closed",
            "market is closed",
            "trade disabled",
            "session closed",
        )
    ):
        return CertificationDiagnostic.MARKET_CLOSED

    if any(
        t in text
        for t in (
            "symbol not found",
            "unknown symbol",
            "symbol unavailable",
            "select symbol",
        )
    ):
        return CertificationDiagnostic.SYMBOL_UNAVAILABLE

    if any(
        t in text
        for t in (
            "permission denied",
            "not allowed",
            "trade is disabled",
            "no permission",
        )
    ):
        return CertificationDiagnostic.PERMISSION_DENIED

    if any(
        t in text
        for t in (
            "not connected",
            "mt5 not connected",
            "unavailable",
            "no session",
        )
    ):
        return CertificationDiagnostic.NOT_CONNECTED

    if status in {"error", "failed"} or reason:
        return CertificationDiagnostic.PROBE_ERROR

    return CertificationDiagnostic.NONE


def diagnostics_from_probes(
    probes: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    """Collect non-none diagnostics from probe result maps."""
    out: list[dict[str, str]] = []
    for capability, result in probes.items():
        status = str(result.get("status") or "")
        reason = str(result.get("reason") or "")
        code = classify_diagnostic(reason=reason, capability=capability, status=status)
        if code is CertificationDiagnostic.NONE:
            continue
        if status in {"ok", "compatible"}:
            continue
        out.append(
            {
                "capability": capability,
                "diagnostic": code.value,
                "reason": reason or status,
            }
        )
    return out
