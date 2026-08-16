"""Confidence calibration monitoring — evidence only. No LIVE recalibration."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from threading import RLock
from typing import Any


@dataclass
class CalibrationMonitor:
    # bucket -> list of realized_R and wins
    buckets: dict[str, list[tuple[float, bool]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    min_sample: int = 20
    _lock: RLock = field(default_factory=RLock, repr=False)

    @staticmethod
    def _bucket(confidence: float) -> str:
        c = max(0.0, min(100.0, float(confidence)))
        lo = int(c // 10) * 10
        return f"{lo}-{lo + 10}"

    def record(
        self,
        *,
        confidence: float,
        realized_r: float | None,
        win: bool | None = None,
        expected_r: float | None = None,
    ) -> None:
        if realized_r is None:
            return
        w = bool(win) if win is not None else float(realized_r) > 0
        with self._lock:
            self.buckets[self._bucket(confidence)].append((float(realized_r), w))
            # expected_r reserved for future; not fabricated into metrics
            _ = expected_r

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            rows = []
            for bucket, items in sorted(self.buckets.items()):
                n = len(items)
                if n < self.min_sample:
                    state = "INSUFFICIENT_SAMPLE"
                    win_rate = avg_r = None
                else:
                    wins = sum(1 for _, w in items if w)
                    win_rate = 100.0 * wins / n
                    avg_r = sum(r for r, _ in items) / n
                    # Mid of bucket as predicted confidence proxy
                    lo = int(bucket.split("-")[0])
                    predicted = lo + 5
                    gap = predicted - win_rate
                    if gap >= 15:
                        state = "OVERCONFIDENT"
                    elif gap <= -15:
                        state = "UNDERCONFIDENT"
                    else:
                        state = "WELL_CALIBRATED"
                rows.append(
                    {
                        "confidence_bucket": bucket,
                        "trade_count": n,
                        "win_rate": None if win_rate is None else round(win_rate, 2),
                        "average_R": None if avg_r is None else round(avg_r, 6),
                        "state": state,
                    }
                )
        return {
            "buckets": rows,
            "auto_recalibrate_live": False,
            "mode": "EVIDENCE_ONLY",
        }
