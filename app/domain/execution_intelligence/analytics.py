"""Execution analytics from real attempt / fill rows only."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def _f(raw: Any, default: float = 0.0) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _parse_ts(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def compute_execution_analytics(
    *,
    attempts: list[dict[str, Any]],
    fills: list[dict[str, Any]],
) -> dict[str, Any]:
    """Latency / fill / reject / slippage from supplied records only."""
    if not attempts and not fills:
        return {
            "status": "unavailable",
            "reason": "No execution attempts or fills available",
            "data_source": "execution_attempts|paper_trades",
            "metrics": {},
        }

    total = len(attempts)
    successes = [
        a
        for a in attempts
        if str(a.get("outcome", "")).lower() in {"success", "filled", "prepared"}
    ]
    rejects = [
        a
        for a in attempts
        if str(a.get("outcome", "")).lower()
        in {"failed", "rejected", "disabled", "cancelled"}
    ]
    # Prefer explicit latency fields when present
    latencies = [
        _f(a.get("latency_ms") or a.get("broker_latency_ms"))
        for a in attempts
        if a.get("latency_ms") is not None or a.get("broker_latency_ms") is not None
    ]
    # Order duration from submitted → filled timestamps when both exist
    durations: list[float] = []
    for a in attempts:
        start = _parse_ts(a.get("submitted_at") or a.get("created_at"))
        end = _parse_ts(a.get("filled_at") or a.get("completed_at"))
        if start and end and end >= start:
            durations.append((end - start).total_seconds() * 1000.0)

    slips: list[float] = []
    for f in fills:
        if f.get("slippage") is not None:
            slips.append(abs(_f(f.get("slippage"))))
        elif f.get("requested_price") is not None and f.get("fill_price") is not None:
            slips.append(abs(_f(f["fill_price"]) - _f(f["requested_price"])))

    fill_rate = (len(successes) / total) if total else None
    reject_rate = (len(rejects) / total) if total else None
    avg_latency = sum(latencies) / len(latencies) if latencies else None
    avg_broker = avg_latency  # same source unless separate field present
    avg_slip = sum(slips) / len(slips) if slips else None
    avg_duration = sum(durations) / len(durations) if durations else None

    # Execution quality score: higher fill, lower reject/slip (only when data exists)
    quality = None
    if fill_rate is not None and reject_rate is not None:
        slip_pen = min(1.0, (avg_slip or 0.0) * 10.0) if slips else 0.0
        quality = round(
            max(0.0, min(1.0, fill_rate * (1.0 - reject_rate) - slip_pen * 0.1)),
            4,
        )

    return {
        "status": "available",
        "data_source": "execution_attempts|paper_trades",
        "sample_sizes": {
            "attempts": total,
            "fills": len(fills),
            "latency_samples": len(latencies),
            "slippage_samples": len(slips),
            "duration_samples": len(durations),
        },
        "metrics": {
            "order_latency_ms_avg": (
                round(avg_latency, 4) if avg_latency is not None else None
            ),
            "order_latency_status": (
                "available" if latencies else "unavailable"
            ),
            "order_latency_reason": (
                None
                if latencies
                else "No latency_ms on attempts — not invented"
            ),
            "broker_response_time_ms_avg": (
                round(avg_broker, 4) if avg_broker is not None else None
            ),
            "fill_rate": round(fill_rate, 4) if fill_rate is not None else None,
            "reject_rate": round(reject_rate, 4) if reject_rate is not None else None,
            "rejected_orders": len(rejects),
            "cancelled_orders": sum(
                1
                for a in attempts
                if str(a.get("outcome", "")).lower() == "cancelled"
            ),
            "success_rate": round(fill_rate, 4) if fill_rate is not None else None,
            "average_slippage": round(avg_slip, 6) if avg_slip is not None else None,
            "average_slippage_status": "available" if slips else "unavailable",
            "average_slippage_reason": (
                None if slips else "No slippage/fill price pairs available"
            ),
            "execution_quality": quality,
            "order_duration_ms_avg": (
                round(avg_duration, 4) if avg_duration is not None else None
            ),
            "execution_time_ms_avg": (
                round(avg_duration, 4)
                if avg_duration is not None
                else (round(avg_latency, 4) if avg_latency is not None else None)
            ),
            "order_duration_status": (
                "available" if durations else "unavailable"
            ),
        },
    }
