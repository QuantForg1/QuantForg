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


def percentile(values: list[float], p: float) -> float | None:
    """Inclusive nearest-rank percentile. Never invents values."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 4)
    rank = (len(ordered) - 1) * (p / 100.0)
    lo = int(rank)
    hi = min(lo + 1, len(ordered) - 1)
    frac = rank - lo
    return round(ordered[lo] * (1.0 - frac) + ordered[hi] * frac, 4)


def _trade_timeline(row: dict[str, Any]) -> dict[str, Any]:
    snap = (
        row.get("request_snapshot")
        if isinstance(row.get("request_snapshot"), dict)
        else {}
    )
    decision_at = (
        row.get("decision_at")
        or snap.get("decision_at")
        or row.get("created_at")
    )
    submitted_at = row.get("submitted_at") or snap.get("submitted_at")
    ack_at = (
        row.get("broker_ack_at")
        or row.get("acknowledged_at")
        or snap.get("broker_ack_at")
    )
    filled_at = row.get("filled_at") or row.get("completed_at")
    start = _parse_ts(submitted_at or decision_at)
    end = _parse_ts(filled_at)
    total_ms = None
    if start and end and end >= start:
        total_ms = round((end - start).total_seconds() * 1000.0, 4)
    elif row.get("latency_ms") is not None:
        total_ms = round(_f(row.get("latency_ms")), 4)
    spread_entry = row.get("spread_at_entry") or row.get("spread") or snap.get("spread")
    spread_exit = row.get("spread_at_exit") or snap.get("spread_at_exit")
    slip = row.get("slippage")
    if slip is None and row.get("price") is not None and snap.get("price") is not None:
        slip = abs(_f(row.get("price")) - _f(snap.get("price")))
    return {
        "request_id": row.get("request_id"),
        "decision_at": decision_at,
        "submitted_at": submitted_at,
        "broker_ack_at": ack_at,
        "filled_at": filled_at,
        "total_execution_latency_ms": total_ms,
        "slippage": round(_f(slip), 6) if slip is not None else None,
        "spread_at_entry": str(spread_entry) if spread_entry is not None else None,
        "spread_at_exit": str(spread_exit) if spread_exit is not None else None,
        "outcome": row.get("outcome"),
    }


def _abnormal(
    *,
    latency_ms: float | None,
    p95: float | None,
    slippage: float | None,
    slip_p95: float | None,
    outcome: str,
) -> list[str]:
    flags: list[str] = []
    out = outcome.lower()
    if out in {"failed", "rejected", "disabled"}:
        flags.append("reject")
    if latency_ms is not None and p95 is not None and latency_ms > p95 * 1.5:
        flags.append("latency_outlier")
    if slippage is not None and slip_p95 is not None and slippage > slip_p95 * 1.5:
        flags.append("slippage_outlier")
    return flags


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
            "trades": [],
            "abnormal_executions": [],
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
    latencies = [
        _f(a.get("latency_ms") or a.get("broker_latency_ms"))
        for a in attempts
        if a.get("latency_ms") is not None or a.get("broker_latency_ms") is not None
    ]
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
    avg_broker = avg_latency
    avg_slip = sum(slips) / len(slips) if slips else None
    avg_duration = sum(durations) / len(durations) if durations else None

    lat_p50 = percentile(latencies, 50)
    lat_p90 = percentile(latencies, 90)
    lat_p95 = percentile(latencies, 95)
    lat_p99 = percentile(latencies, 99)
    slip_p50 = percentile(slips, 50)
    slip_p90 = percentile(slips, 90)
    slip_p95 = percentile(slips, 95)
    slip_p99 = percentile(slips, 99)

    quality = None
    if fill_rate is not None and reject_rate is not None:
        slip_pen = min(1.0, (avg_slip or 0.0) * 10.0) if slips else 0.0
        quality = round(
            max(0.0, min(1.0, fill_rate * (1.0 - reject_rate) - slip_pen * 0.1)),
            4,
        )

    trades = [_trade_timeline(a) for a in attempts]
    abnormal: list[dict[str, Any]] = []
    for t in trades:
        flags = _abnormal(
            latency_ms=t.get("total_execution_latency_ms"),
            p95=lat_p95,
            slippage=t.get("slippage"),
            slip_p95=slip_p95,
            outcome=str(t.get("outcome") or ""),
        )
        if flags:
            abnormal.append({**t, "flags": flags})

    return {
        "status": "available",
        "data_source": "execution_attempts|paper_trades",
        "sample_sizes": {
            "attempts": total,
            "fills": len(fills),
            "latency_samples": len(latencies),
            "slippage_samples": len(slips),
            "duration_samples": len(durations),
            "abnormal": len(abnormal),
        },
        "metrics": {
            "order_latency_ms_avg": (
                round(avg_latency, 4) if avg_latency is not None else None
            ),
            "order_latency_ms_p50": lat_p50,
            "order_latency_ms_p90": lat_p90,
            "order_latency_ms_p95": lat_p95,
            "order_latency_ms_p99": lat_p99,
            "order_latency_status": ("available" if latencies else "unavailable"),
            "order_latency_reason": (
                None if latencies else "No latency_ms on attempts — not invented"
            ),
            "broker_response_time_ms_avg": (
                round(avg_broker, 4) if avg_broker is not None else None
            ),
            "fill_rate": round(fill_rate, 4) if fill_rate is not None else None,
            "reject_rate": round(reject_rate, 4) if reject_rate is not None else None,
            "rejected_orders": len(rejects),
            "cancelled_orders": sum(
                1 for a in attempts if str(a.get("outcome", "")).lower() == "cancelled"
            ),
            "success_rate": round(fill_rate, 4) if fill_rate is not None else None,
            "average_slippage": round(avg_slip, 6) if avg_slip is not None else None,
            "slippage_p50": slip_p50,
            "slippage_p90": slip_p90,
            "slippage_p95": slip_p95,
            "slippage_p99": slip_p99,
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
            "order_duration_status": ("available" if durations else "unavailable"),
            "abnormal_execution_count": len(abnormal),
        },
        "trades": trades,
        "abnormal_executions": abnormal,
    }
