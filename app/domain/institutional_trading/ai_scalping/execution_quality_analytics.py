"""Execution quality analytics — rich per-order records on existing infra."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

_LOCK = threading.Lock()
_STORE: "ExecutionQualityAnalyticsStore | None" = None


def _iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass
class ExecutionQualityAnalyticsStore:
    """Rolling rich fill/reject records (requested vs executed, latency, score)."""

    window: int = 300
    _events: deque[dict[str, Any]] = field(default_factory=deque, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(
        self,
        *,
        symbol: str,
        side: str | None = None,
        requested_price: float | None = None,
        executed_price: float | None = None,
        slippage: float | None = None,
        latency_ms: float | None = None,
        broker_execution_time_ms: float | None = None,
        fill_quality: str | None = None,
        execution_score: int | None = None,
        outcome: str = "success",
        ticket: str | None = None,
        retcode: int | None = None,
        extras: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = {
            "at": _iso(),
            "symbol": str(symbol or "").upper(),
            "side": str(side or "").upper() or None,
            "requested_price": requested_price,
            "executed_price": executed_price,
            "slippage": slippage,
            "latency_ms": latency_ms,
            "broker_execution_time_ms": broker_execution_time_ms,
            "fill_quality": fill_quality,
            "execution_score": execution_score,
            "outcome": outcome,
            "ticket": ticket,
            "retcode": retcode,
            "extras": dict(extras or {}),
            "fabricated": False,
        }
        with self._lock:
            self._events.append(row)
            while len(self._events) > self.window:
                self._events.popleft()
        return row

    def snapshot(self, *, limit: int = 25) -> dict[str, Any]:
        with self._lock:
            rows = list(self._events)
        recent = list(reversed(rows[-limit:]))
        slips = [float(r["slippage"]) for r in rows if r.get("slippage") is not None]
        lats = [
            float(r["latency_ms"]) for r in rows if r.get("latency_ms") is not None
        ]
        scores = [
            int(r["execution_score"])
            for r in rows
            if r.get("execution_score") is not None
        ]
        fills = sum(1 for r in rows if r.get("outcome") == "success")
        n = len(rows)
        return {
            "samples": n,
            "avg_slippage": round(sum(slips) / len(slips), 6) if slips else None,
            "avg_latency_ms": round(sum(lats) / len(lats), 3) if lats else None,
            "avg_execution_score": (
                round(sum(scores) / len(scores), 2) if scores else None
            ),
            "fill_rate": round(100.0 * fills / n, 2) if n else None,
            "recent": recent,
            "fabricated": False,
            "source": "real_execution_records_only",
        }


def get_execution_quality_analytics_store() -> ExecutionQualityAnalyticsStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = ExecutionQualityAnalyticsStore()
        return _STORE


def classify_fill_quality(
    *,
    slippage: float | None,
    latency_ms: float | None,
) -> str:
    slip = abs(float(slippage)) if slippage is not None else None
    lat = float(latency_ms) if latency_ms is not None else None
    if slip is None and lat is None:
        return "unknown"
    bad = (slip is not None and slip > 0.25) or (lat is not None and lat > 2000)
    fair = (slip is not None and slip > 0.10) or (lat is not None and lat > 800)
    if bad:
        return "poor"
    if fair:
        return "fair"
    return "good"
