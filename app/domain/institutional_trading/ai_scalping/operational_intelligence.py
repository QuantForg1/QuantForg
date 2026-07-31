"""Operational Intelligence — warnings only from live EQ / health signals."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def _iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def build_operational_intelligence() -> dict[str, Any]:
    """Detect degradation; raise warnings only — never stop production here."""
    warnings: list[dict[str, Any]] = []

    eq: dict[str, Any] = {}
    try:
        from app.domain.institutional_trading.ai_scalping.execution_quality import (
            get_execution_quality_store,
        )

        eq = get_execution_quality_store().snapshot()
    except Exception:
        eq = {}

    samples = int(eq.get("samples") or 0)
    reject = eq.get("reject_rate")
    slip = eq.get("avg_slippage")
    lat = eq.get("avg_latency_ms")

    if samples >= 8 and reject is not None and float(reject) >= 40:
        warnings.append(
            {
                "code": "high_rejection_rate",
                "severity": "warn",
                "message": f"Reject rate {reject}% over last {samples} samples",
                "value": reject,
            }
        )
    if samples >= 5 and slip is not None and abs(float(slip)) >= 0.25:
        warnings.append(
            {
                "code": "high_slippage",
                "severity": "warn",
                "message": f"Avg slippage {slip} elevated",
                "value": slip,
            }
        )
    if samples >= 5 and lat is not None and float(lat) >= 1500:
        warnings.append(
            {
                "code": "high_latency",
                "severity": "warn",
                "message": f"Avg execution latency {lat}ms elevated",
                "value": lat,
            }
        )

    # Live health / gateway signals
    try:
        from app.domain.institutional_trading.ai_scalping.live_health import (
            get_live_health_monitor,
        )

        health = get_live_health_monitor().snapshot()
        prot = health.get("self_protection") if isinstance(health, dict) else {}
        reasons = list((prot or {}).get("reasons") or [])
        if any("gateway" in str(r).lower() for r in reasons):
            warnings.append(
                {
                    "code": "gateway_instability",
                    "severity": "warn",
                    "message": "Gateway instability signal present",
                    "value": reasons,
                }
            )
        if any("broker" in str(r).lower() or "mt5" in str(r).lower() for r in reasons):
            warnings.append(
                {
                    "code": "broker_instability",
                    "severity": "warn",
                    "message": "Broker/MT5 instability signal present",
                    "value": reasons,
                }
            )
        if any("slippage" in str(r).lower() for r in reasons):
            warnings.append(
                {
                    "code": "execution_degradation",
                    "severity": "warn",
                    "message": "Execution degradation (slippage protection)",
                    "value": reasons,
                }
            )
    except Exception:
        pass

    return {
        "as_of": _iso(),
        "warnings": warnings,
        "warning_count": len(warnings),
        "execution_quality": eq,
        "stops_production": False,
        "note": "Warnings only — existing safety rules remain sole stop authority",
        "fabricated": False,
        "observe_only": True,
    }
