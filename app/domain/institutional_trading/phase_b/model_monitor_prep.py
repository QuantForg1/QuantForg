"""AI / model monitoring preparation — baseline distributions only. No retrain."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from threading import RLock
from typing import Any


@dataclass
class ModelMonitorPrepStore:
    confidence: deque[float] = field(default_factory=lambda: deque(maxlen=500))
    quality: deque[float] = field(default_factory=lambda: deque(maxlen=500))
    signals: deque[str] = field(default_factory=lambda: deque(maxlen=500))
    outcomes: deque[float] = field(default_factory=lambda: deque(maxlen=500))
    _lock: RLock = field(default_factory=RLock, repr=False)

    def observe(
        self,
        *,
        confidence: float | None = None,
        quality: float | None = None,
        signal: str | None = None,
        realized_r: float | None = None,
    ) -> None:
        with self._lock:
            if confidence is not None:
                self.confidence.append(float(confidence))
            if quality is not None:
                self.quality.append(float(quality))
            if signal is not None:
                self.signals.append(str(signal))
            if realized_r is not None:
                self.outcomes.append(float(realized_r))

    def snapshot(self) -> dict[str, Any]:
        def _dist(vals: deque[float]) -> dict[str, Any]:
            rows = list(vals)
            if not rows:
                return {"n": 0, "mean": None, "min": None, "max": None}
            return {
                "n": len(rows),
                "mean": round(sum(rows) / len(rows), 4),
                "min": min(rows),
                "max": max(rows),
            }

        with self._lock:
            sigs = list(self.signals)
            counts: dict[str, int] = {}
            for s in sigs:
                counts[s] = counts.get(s, 0) + 1
            return {
                "phase": "B_BASELINE_FOR_C",
                "retrain_in_phase_b": False,
                "confidence_distribution": _dist(self.confidence),
                "quality_distribution": _dist(self.quality),
                "signal_distribution": counts,
                "realized_outcomes": _dist(self.outcomes),
                "calibration": "PENDING_PHASE_C",
                "strategy_drift": "PENDING_PHASE_C",
            }
