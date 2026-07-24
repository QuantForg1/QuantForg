"""Execution quality analyzer — stage latencies and bottlenecks."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


STAGES = (
    "signal_generation",
    "ai_decision",
    "oms",
    "gateway",
    "mt5",
    "broker",
)


@dataclass
class ExecutionQualityMonitor:
    _sums: dict[str, float] = field(default_factory=lambda: {s: 0.0 for s in STAGES})
    _counts: dict[str, int] = field(default_factory=lambda: {s: 0 for s in STAGES})
    _last: dict[str, float] = field(default_factory=dict)
    _totals: list[float] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(self, latencies: dict[str, float]) -> None:
        with self._lock:
            total = 0.0
            for stage in STAGES:
                if stage not in latencies:
                    continue
                ms = float(latencies[stage])
                self._sums[stage] = self._sums.get(stage, 0.0) + ms
                self._counts[stage] = self._counts.get(stage, 0) + 1
                self._last[stage] = ms
                total += ms
            if "total" in latencies:
                total = float(latencies["total"])
            self._totals.append(total)
            if len(self._totals) > 2_000:
                self._totals = self._totals[-2_000:]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            avgs: dict[str, float | None] = {}
            for stage in STAGES:
                c = self._counts.get(stage, 0)
                avgs[stage] = (
                    round(self._sums[stage] / c, 3) if c else None
                )
            avg_total = (
                round(sum(self._totals) / len(self._totals), 3) if self._totals else None
            )
            # Bottleneck = highest average among stages with data
            bottleneck = None
            bottleneck_ms = -1.0
            for stage, avg in avgs.items():
                if avg is not None and avg > bottleneck_ms:
                    bottleneck_ms = avg
                    bottleneck = stage
            return {
                "avg_ms_by_stage": avgs,
                "last_ms_by_stage": dict(self._last),
                "avg_total_execution_ms": avg_total,
                "bottleneck": bottleneck,
                "bottleneck_ms": round(bottleneck_ms, 3) if bottleneck else None,
                "samples": len(self._totals),
            }


_MON: ExecutionQualityMonitor | None = None
_LOCK = threading.Lock()


def get_execution_quality_monitor() -> ExecutionQualityMonitor:
    global _MON
    with _LOCK:
        if _MON is None:
            _MON = ExecutionQualityMonitor()
        return _MON
