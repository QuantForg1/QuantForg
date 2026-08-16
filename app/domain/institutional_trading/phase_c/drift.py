"""Live model drift monitoring — OBSERVE / WARN / ALERT only. No auto-disable."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Sequence


DRIFT_KINDS = (
    "DATA_DRIFT",
    "FEATURE_DRIFT",
    "SIGNAL_DRIFT",
    "CONFIDENCE_DRIFT",
    "QUALITY_DRIFT",
    "CALIBRATION_DRIFT",
    "PERFORMANCE_DRIFT",
    "EXECUTION_DRIFT",
    "REGIME_DRIFT",
)


def _mean(xs: Sequence[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def classify_drift(
    *,
    baseline: Sequence[float],
    live: Sequence[float],
    min_sample: int = 20,
    mild: float = 0.15,
    significant: float = 0.35,
) -> dict[str, Any]:
    if len(baseline) < min_sample or len(live) < min_sample:
        return {
            "state": "INSUFFICIENT_SAMPLE",
            "response": "OBSERVE",
            "baseline_n": len(baseline),
            "live_n": len(live),
            "auto_disable": False,
            "auto_retrain": False,
            "auto_resize": False,
            "future_degraded_to_shadow": False,
            "future_critical_block_new_entries": False,
        }
    b = _mean(baseline)
    l = _mean(live)
    assert b is not None and l is not None
    denom = abs(b) if abs(b) > 1e-9 else 1.0
    rel = abs(l - b) / denom
    if rel >= significant:
        state, response = "ALERT", "ALERT"
    elif rel >= mild:
        state, response = "WARN", "WARN"
    else:
        state, response = "STABLE", "OBSERVE"
    return {
        "state": state,
        "response": response,  # OBSERVE | WARN | ALERT only in Phase C
        "baseline_mean": round(b, 6),
        "live_mean": round(l, 6),
        "relative_delta": round(rel, 6),
        "auto_disable": False,
        "auto_retrain": False,
        "auto_resize": False,
        "future_degraded_to_shadow": False,
        "future_critical_block_new_entries": False,
    }


@dataclass
class DriftMonitorStore:
    baselines: dict[str, deque[float]] = field(default_factory=dict)
    live: dict[str, deque[float]] = field(default_factory=dict)
    min_sample: int = 20
    _lock: RLock = field(default_factory=RLock, repr=False)

    def observe_baseline(self, kind: str, value: float) -> None:
        key = str(kind).upper()
        with self._lock:
            self.baselines.setdefault(key, deque(maxlen=500)).append(float(value))

    def observe_live(self, kind: str, value: float) -> None:
        key = str(kind).upper()
        with self._lock:
            self.live.setdefault(key, deque(maxlen=500)).append(float(value))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            keys = sorted(set(self.baselines) | set(self.live) | set(DRIFT_KINDS))
            rows = []
            for k in keys:
                b = list(self.baselines.get(k, ()))
                l = list(self.live.get(k, ()))
                # Rolling windows where sample permits
                windows = {}
                for w in (20, 50, 100):
                    if len(l) >= w and len(b) >= min(w, self.min_sample):
                        windows[str(w)] = classify_drift(
                            baseline=b[-w:], live=l[-w:], min_sample=min(w, self.min_sample)
                        )
                    else:
                        windows[str(w)] = {
                            "state": "INSUFFICIENT_SAMPLE",
                            "response": "OBSERVE",
                        }
                rows.append(
                    {
                        "kind": k,
                        "windows": windows,
                        "latest": classify_drift(
                            baseline=b, live=l, min_sample=self.min_sample
                        ),
                    }
                )
        return {
            "kinds": rows,
            "auto_disable": False,
            "auto_retrain": False,
            "phase_d_policies_enabled": False,
        }


def regime_specific_drift(
    *,
    strategy: str,
    symbol: str,
    session: str,
    regime: str,
    direction: str,
    baseline_r: Sequence[float],
    live_r: Sequence[float],
    min_sample: int = 20,
) -> dict[str, Any]:
    cell = {
        "strategy": strategy,
        "symbol": symbol,
        "session": session,
        "regime": regime,
        "direction": direction,
    }
    result = classify_drift(
        baseline=baseline_r, live=live_r, min_sample=min_sample
    )
    result["cell"] = cell
    return result
