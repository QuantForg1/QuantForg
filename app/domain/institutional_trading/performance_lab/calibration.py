"""Confidence calibration — predicted confidence vs realized win rate."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from app.domain.institutional_trading.performance_lab.config import DEFAULT_LAB_CONFIG


def _bin_for(confidence: int, bins: tuple[int, ...]) -> int:
    chosen = bins[0]
    for b in bins:
        if confidence >= b:
            chosen = b
    return chosen


@dataclass
class CalibrationStore:
    # bin -> (wins, total)
    _bins: dict[int, list[int]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(self, *, confidence: int, win: bool) -> None:
        b = _bin_for(int(confidence), DEFAULT_LAB_CONFIG.calibration_bins)
        with self._lock:
            row = self._bins.setdefault(b, [0, 0])
            row[1] += 1
            if win:
                row[0] += 1

    def chart(self) -> dict[str, Any]:
        cfg = DEFAULT_LAB_CONFIG
        points: list[dict[str, Any]] = []
        flags: list[str] = []
        with self._lock:
            for b in cfg.calibration_bins:
                wins, total = self._bins.get(b, [0, 0])
                actual = round(100.0 * wins / total, 2) if total else None
                gap = round(float(b) - actual, 2) if actual is not None else None
                status = "insufficient"
                if actual is not None and total >= 5:
                    if gap is not None and gap >= cfg.overconfidence_gap:
                        status = "overconfident"
                        flags.append(f"{b}% predicted → {actual}% actual (over)")
                    elif gap is not None and gap <= cfg.underconfidence_gap:
                        status = "underconfident"
                        flags.append(f"{b}% predicted → {actual}% actual (under)")
                    else:
                        status = "calibrated"
                points.append(
                    {
                        "predicted_confidence": b,
                        "actual_win_rate": actual,
                        "samples": total,
                        "gap": gap,
                        "status": status,
                    }
                )
        return {
            "points": points,
            "flags": flags,
            "overconfidence_gap": cfg.overconfidence_gap,
            "underconfidence_gap": cfg.underconfidence_gap,
        }


_STORE: CalibrationStore | None = None
_LOCK = threading.Lock()


def get_calibration_store() -> CalibrationStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = CalibrationStore()
        return _STORE
