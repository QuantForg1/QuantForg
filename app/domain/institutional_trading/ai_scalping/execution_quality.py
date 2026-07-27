"""Rolling execution quality statistics for live scalping."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class ExecutionQualityStore:
    """Process-scoped rolling window of execution outcomes."""

    window: int = 200
    _events: deque[dict[str, Any]] = field(default_factory=deque, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(
        self,
        *,
        outcome: str,
        latency_ms: float | None = None,
        slippage: float | None = None,
        spread: float | None = None,
        retcode: int | None = None,
        partial_fill: bool = False,
        requote: bool = False,
        rejection_reason: str | None = None,
    ) -> dict[str, Any]:
        ev = {
            "at": datetime.now(UTC).isoformat(),
            "outcome": outcome,  # success | reject | abort | partial
            "latency_ms": latency_ms,
            "slippage": slippage,
            "spread": spread,
            "retcode": retcode,
            "partial_fill": partial_fill,
            "requote": requote,
            "rejection_reason": rejection_reason,
        }
        with self._lock:
            self._events.append(ev)
            while len(self._events) > self.window:
                self._events.popleft()
        return ev

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            rows = list(self._events)
        n = len(rows)
        if n == 0:
            return {
                "samples": 0,
                "fill_rate": None,
                "reject_rate": None,
                "partial_fill_rate": None,
                "requote_rate": None,
                "avg_latency_ms": None,
                "avg_slippage": None,
                "execution_success_rate": None,
            }
        fills = sum(1 for r in rows if r["outcome"] == "success")
        rejects = sum(1 for r in rows if r["outcome"] in {"reject", "abort"})
        partials = sum(1 for r in rows if r.get("partial_fill"))
        requotes = sum(1 for r in rows if r.get("requote"))
        lats = [float(r["latency_ms"]) for r in rows if r.get("latency_ms") is not None]
        slips = [float(r["slippage"]) for r in rows if r.get("slippage") is not None]
        return {
            "samples": n,
            "fill_rate": round(100.0 * fills / n, 2),
            "reject_rate": round(100.0 * rejects / n, 2),
            "partial_fill_rate": round(100.0 * partials / n, 2),
            "requote_rate": round(100.0 * requotes / n, 2),
            "avg_latency_ms": round(sum(lats) / len(lats), 3) if lats else None,
            "avg_slippage": round(sum(slips) / len(slips), 4) if slips else None,
            "execution_success_rate": round(100.0 * fills / n, 2),
            "recent": list(reversed(rows[-20:])),
        }


_STORE: ExecutionQualityStore | None = None
_LOCK = threading.Lock()


def get_execution_quality_store() -> ExecutionQualityStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = ExecutionQualityStore()
        return _STORE
