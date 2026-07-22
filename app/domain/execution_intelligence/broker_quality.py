"""Broker quality score from real execution + connection facts only."""

from __future__ import annotations

from typing import Any


def compute_broker_quality(
    *,
    fill_rate: float | None = None,
    reject_rate: float | None = None,
    avg_slippage: float | None = None,
    latency_p95_ms: float | None = None,
    reconnect_count: int | None = None,
    connected: bool | None = None,
    requote_count: int | None = None,
    attempt_count: int = 0,
) -> dict[str, Any]:
    """0-100 score when enough facts exist; never invents missing inputs."""
    if attempt_count <= 0 and fill_rate is None and connected is None:
        return {
            "status": "unavailable",
            "score": None,
            "reason": "No broker/execution facts supplied",
            "components": {},
        }

    components: dict[str, float | None] = {
        "fill_success": None,
        "rejects": None,
        "slippage": None,
        "latency": None,
        "connection_stability": None,
        "requotes": None,
    }
    weights: dict[str, float] = {}

    if fill_rate is not None:
        components["fill_success"] = max(0.0, min(100.0, fill_rate * 100.0))
        weights["fill_success"] = 0.3
    if reject_rate is not None:
        components["rejects"] = max(0.0, min(100.0, (1.0 - reject_rate) * 100.0))
        weights["rejects"] = 0.2
    if avg_slippage is not None:
        # Lower slippage → higher score (penalize above 0.5 price units hard)
        components["slippage"] = max(
            0.0, min(100.0, 100.0 - min(100.0, abs(avg_slippage) * 200.0))
        )
        weights["slippage"] = 0.2
    if latency_p95_ms is not None:
        components["latency"] = max(
            0.0, min(100.0, 100.0 - min(100.0, latency_p95_ms / 10.0))
        )
        weights["latency"] = 0.15
    if reconnect_count is not None or connected is not None:
        base = 100.0 if connected is not False else 20.0
        recon = float(reconnect_count or 0)
        components["connection_stability"] = max(0.0, base - min(80.0, recon * 10.0))
        weights["connection_stability"] = 0.1
    if requote_count is not None and attempt_count > 0:
        rq_rate = requote_count / max(1, attempt_count)
        components["requotes"] = max(0.0, min(100.0, (1.0 - rq_rate) * 100.0))
        weights["requotes"] = 0.05

    if not weights:
        return {
            "status": "unavailable",
            "score": None,
            "reason": "Insufficient components for broker quality score",
            "components": components,
        }

    total_w = sum(weights.values())
    score = sum((components[k] or 0.0) * (w / total_w) for k, w in weights.items())
    return {
        "status": "available",
        "score": round(score, 2),
        "components": {
            k: (round(v, 2) if v is not None else None)
            for k, v in components.items()
        },
        "weights_used": {k: round(w / total_w, 3) for k, w in weights.items()},
        "note": "Composite from supplied facts only — never invents fills",
    }
