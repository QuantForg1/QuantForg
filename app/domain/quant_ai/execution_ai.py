"""Quant AI — execution quality explanations over real attempts/fills."""

from __future__ import annotations

from typing import Any

from app.domain.execution_intelligence.analytics import compute_execution_analytics


def analyze_execution_ai(
    *,
    attempts: list[dict[str, Any]],
    fills: list[dict[str, Any]],
    broker_latency_ms: float | None = None,
) -> dict[str, Any]:
    base = compute_execution_analytics(attempts=attempts, fills=fills)
    metrics = dict(base.get("metrics") or {})
    reasons: list[str] = []

    fill_rate = metrics.get("fill_rate")
    reject_rate = metrics.get("reject_rate")
    avg_slip = metrics.get("average_slippage")
    latency = metrics.get("order_latency_ms_avg")
    if latency is None and broker_latency_ms is not None:
        latency = broker_latency_ms
        metrics["broker_latency_ms"] = broker_latency_ms
        reasons.append(f"Broker heartbeat latency {broker_latency_ms:.1f} ms")

    score = None
    if fill_rate is not None and reject_rate is not None:
        slip_pen = (
            min(1.0, float(avg_slip or 0.0) * 10.0) if avg_slip is not None else 0.0
        )
        score = round(
            max(
                0.0,
                min(
                    1.0, float(fill_rate) * (1.0 - float(reject_rate)) - slip_pen * 0.1
                ),
            ),
            4,
        )
        reasons.append(
            f"Fill rate {float(fill_rate):.1%}, reject rate {float(reject_rate):.1%}"
        )
    if avg_slip is not None:
        reasons.append(f"Average observed slippage {avg_slip}")
    if latency is not None:
        reasons.append(f"Average execution/broker latency {float(latency):.1f} ms")
    if metrics.get("rejected_orders"):
        reasons.append(f"Rejected orders count {metrics.get('rejected_orders')}")
    if metrics.get("cancelled_orders"):
        reasons.append(f"Cancelled orders count {metrics.get('cancelled_orders')}")
    if not reasons:
        reasons.append(str(base.get("reason") or "No execution attempts available"))

    quality = "unavailable"
    if score is not None:
        if score >= 0.75:
            quality = "strong"
        elif score >= 0.5:
            quality = "acceptable"
        else:
            quality = "weak"

    return {
        "status": base.get("status", "unavailable"),
        "execution_score": score,
        "execution_quality": quality,
        "metrics": {
            **metrics,
            "average_slippage": avg_slip,
            "broker_latency_ms": latency,
            "fill_quality": quality,
            "partial_fills": None,  # never invent — only if field appears later
        },
        "sample_sizes": base.get("sample_sizes") or {},
        "why": {
            "summary": f"Execution quality: {quality}",
            "supporting_factors": reasons,
        },
        "data_source": base.get("data_source") or "execution_attempts",
        "autonomous_trading": False,
        "advisory_only": True,
        "never_submits_orders": True,
    }
