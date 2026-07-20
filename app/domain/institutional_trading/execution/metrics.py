"""Phase C bridge metrics — decisions, eligible, executed, rejected, duplicates."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock


@dataclass
class ExecutionBridgeMetrics:
    """In-process counters for the Execution Bridge."""

    decisions_seen: int = 0
    actionable: int = 0  # BUY/SELL received
    eligible_passed: int = 0
    executed: int = 0  # OMS success or shadow commit
    rejected: int = 0  # aborted / OMS reject
    duplicates: int = 0
    total_latency_ms: float = 0.0
    latency_samples: int = 0
    confidence_sum: int = 0
    confidence_samples: int = 0
    _lock: Lock = field(default_factory=Lock, repr=False)

    def record_decision(self, *, confidence: int, actionable: bool) -> None:
        with self._lock:
            self.decisions_seen += 1
            self.confidence_sum += confidence
            self.confidence_samples += 1
            if actionable:
                self.actionable += 1

    def record_eligible(self) -> None:
        with self._lock:
            self.eligible_passed += 1

    def record_executed(self, latency_ms: float) -> None:
        with self._lock:
            self.executed += 1
            self.total_latency_ms += latency_ms
            self.latency_samples += 1

    def record_rejected(self, latency_ms: float = 0.0) -> None:
        with self._lock:
            self.rejected += 1
            if latency_ms > 0:
                self.total_latency_ms += latency_ms
                self.latency_samples += 1

    def record_duplicate(self) -> None:
        with self._lock:
            self.duplicates += 1

    @property
    def average_latency_ms(self) -> float:
        with self._lock:
            if self.latency_samples == 0:
                return 0.0
            return self.total_latency_ms / self.latency_samples

    @property
    def average_confidence(self) -> float:
        with self._lock:
            if self.confidence_samples == 0:
                return 0.0
            return self.confidence_sum / self.confidence_samples

    def snapshot(self) -> dict[str, float | int]:
        with self._lock:
            return {
                "decisions": self.decisions_seen,
                "actionable": self.actionable,
                "eligible": self.eligible_passed,
                "executed": self.executed,
                "rejected": self.rejected,
                "duplicates": self.duplicates,
                "average_latency_ms": (
                    self.total_latency_ms / self.latency_samples
                    if self.latency_samples
                    else 0.0
                ),
                "average_confidence": (
                    self.confidence_sum / self.confidence_samples
                    if self.confidence_samples
                    else 0.0
                ),
                # Win rate deferred to Phase E analytics
                "win_rate": 0.0,
            }
