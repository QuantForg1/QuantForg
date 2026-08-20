"""Trade-starvation observability for the Probability Center selector.

Records per-cycle opportunity scores and 30-minute window statistics.
Never lowers the threshold. Never forces a trade. Never calls OMS.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from datetime import UTC, datetime
from typing import Any

WINDOW_SECONDS = 30 * 60
_MAX_SAMPLES = 4000

_LOCK = threading.RLock()
_SAMPLES: deque[dict[str, Any]] = deque(maxlen=_MAX_SAMPLES)


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def reset_opportunity_starvation() -> None:
    with _LOCK:
        _SAMPLES.clear()


def record_opportunity_cycle(
    *,
    opportunity_score: int | None,
    threshold: int,
    score_breakdown: dict[str, int] | None = None,
    direction: str | None = None,
    first_blocking_gate: str | None = None,
    fault_code: str | None = None,
    fault_reason: str | None = None,
    eligible: bool = False,
    hard_block: bool = False,
    execution_ready: bool = False,
    time_in_candidate_ms: float | None = None,
    time_in_execution_ready_ms: float | None = None,
    time_to_oms_ms: float | None = None,
    time_to_gateway_ms: float | None = None,
    time_to_order_send_ms: float | None = None,
    time_to_fill_ms: float | None = None,
    now_mono: float | None = None,
) -> dict[str, Any]:
    sample = {
        "as_of": _utc_now(),
        "mono": float(now_mono if now_mono is not None else time.monotonic()),
        "opportunity_score": (
            int(opportunity_score) if opportunity_score is not None else None
        ),
        "threshold": int(threshold),
        "score_breakdown": dict(score_breakdown or {}),
        "direction": str(direction or "NONE"),
        "first_blocking_gate": first_blocking_gate,
        "fault_code": fault_code,
        "fault_reason": fault_reason,
        "eligible": bool(eligible),
        "hard_block": bool(hard_block),
        "execution_ready": bool(execution_ready),
        "time_in_candidate_ms": time_in_candidate_ms,
        "time_in_execution_ready_ms": time_in_execution_ready_ms,
        "time_to_oms_ms": time_to_oms_ms,
        "time_to_gateway_ms": time_to_gateway_ms,
        "time_to_order_send_ms": time_to_order_send_ms,
        "time_to_fill_ms": time_to_fill_ms,
        "forces_trades": False,
        "adaptive_threshold_enabled": False,
    }
    with _LOCK:
        _SAMPLES.append(sample)
    return dict(sample)


def opportunity_starvation_snapshot(
    *,
    now_mono: float | None = None,
    window_seconds: int = WINDOW_SECONDS,
) -> dict[str, Any]:
    ts = float(now_mono if now_mono is not None else time.monotonic())
    cutoff = ts - float(window_seconds)
    with _LOCK:
        rows = [dict(s) for s in _SAMPLES if float(s.get("mono") or 0) >= cutoff]

    scores = [
        int(s["opportunity_score"])
        for s in rows
        if s.get("opportunity_score") is not None
    ]
    threshold = int(rows[-1]["threshold"]) if rows else 70
    above = [s for s in rows if (s.get("opportunity_score") or 0) >= threshold]
    candidates = [s for s in rows if s.get("eligible")]
    hard = [s for s in rows if s.get("hard_block")]
    soft = [
        s
        for s in rows
        if not s.get("hard_block") and not s.get("eligible")
    ]
    ready = [s for s in rows if s.get("execution_ready")]
    first_hard = None
    for sample in rows:
        if sample.get("hard_block"):
            first_hard = sample.get("fault_code") or sample.get("first_blocking_gate")
            break
    return {
        "window_seconds": window_seconds,
        "sample_count": len(rows),
        "best_score": max(scores) if scores else None,
        "average_score": (
            round(sum(scores) / len(scores), 2) if scores else None
        ),
        "max_score": max(scores) if scores else None,
        "time_above_70": len(above),
        "candidate_count": len(candidates),
        "hard_block_count": len(hard),
        "soft_wait_count": len(soft),
        "first_hard_blocker": first_hard,
        "execution_ready_count": len(ready),
        "threshold": threshold,
        "adaptive_threshold_enabled": False,
        "forces_trades": False,
        "latest": rows[-1] if rows else None,
    }
