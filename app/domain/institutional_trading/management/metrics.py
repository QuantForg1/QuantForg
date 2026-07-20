"""PME metrics — hold time, RR, BE/trail/partial success, exit reasons."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from threading import Lock


@dataclass
class PositionManageMetrics:
    evaluations: int = 0
    be_attempts: int = 0
    be_success: int = 0
    trail_attempts: int = 0
    trail_success: int = 0
    partial_attempts: int = 0
    partial_success: int = 0
    exits: int = 0
    duplicates: int = 0
    oms_failures: int = 0
    hold_seconds_sum: float = 0.0
    hold_samples: int = 0
    exit_r_sum: Decimal = Decimal("0")
    exit_r_samples: int = 0
    exit_reasons: Counter[str] = field(default_factory=Counter)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def record_evaluation(self) -> None:
        with self._lock:
            self.evaluations += 1

    def record_be(self, *, success: bool) -> None:
        with self._lock:
            self.be_attempts += 1
            if success:
                self.be_success += 1

    def record_trail(self, *, success: bool) -> None:
        with self._lock:
            self.trail_attempts += 1
            if success:
                self.trail_success += 1

    def record_partial(self, *, success: bool) -> None:
        with self._lock:
            self.partial_attempts += 1
            if success:
                self.partial_success += 1

    def record_exit(
        self,
        *,
        reason: str,
        hold_seconds: float,
        exit_r: Decimal,
    ) -> None:
        with self._lock:
            self.exits += 1
            self.exit_reasons[reason] += 1
            self.hold_seconds_sum += hold_seconds
            self.hold_samples += 1
            self.exit_r_sum += exit_r
            self.exit_r_samples += 1

    def record_duplicate(self) -> None:
        with self._lock:
            self.duplicates += 1

    def record_oms_failure(self) -> None:
        with self._lock:
            self.oms_failures += 1

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            avg_hold = (
                self.hold_seconds_sum / self.hold_samples if self.hold_samples else 0.0
            )
            avg_rr = (
                float(self.exit_r_sum / self.exit_r_samples)
                if self.exit_r_samples
                else 0.0
            )
            return {
                "evaluations": self.evaluations,
                "average_hold_seconds": avg_hold,
                "average_rr": avg_rr,
                "be_success": self.be_success,
                "be_attempts": self.be_attempts,
                "trailing_success": self.trail_success,
                "trailing_attempts": self.trail_attempts,
                "partial_success": self.partial_success,
                "partial_attempts": self.partial_attempts,
                "exits": self.exits,
                "exit_reasons": dict(self.exit_reasons),
                "duplicates": self.duplicates,
                "oms_failures": self.oms_failures,
            }
