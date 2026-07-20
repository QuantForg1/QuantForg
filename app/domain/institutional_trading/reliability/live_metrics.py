"""Live operational metrics — latency, throughput, fills, rejects."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock


@dataclass
class LiveMetricsRegistry:
    execution_latency_ms_sum: float = 0.0
    execution_latency_samples: int = 0
    gateway_latency_ms_sum: float = 0.0
    gateway_latency_samples: int = 0
    decisions: int = 0
    fills: int = 0
    rejects: int = 0
    oms_failures: int = 0
    duplicates_prevented: int = 0
    risk_rejects: int = 0
    _lock: Lock = field(default_factory=Lock, repr=False)

    def record_execution_latency(self, ms: float) -> None:
        with self._lock:
            self.execution_latency_ms_sum += ms
            self.execution_latency_samples += 1

    def record_gateway_latency(self, ms: float) -> None:
        with self._lock:
            self.gateway_latency_ms_sum += ms
            self.gateway_latency_samples += 1

    def record_decision(self) -> None:
        with self._lock:
            self.decisions += 1

    def record_fill(self) -> None:
        with self._lock:
            self.fills += 1

    def record_reject(self) -> None:
        with self._lock:
            self.rejects += 1

    def record_oms_failure(self) -> None:
        with self._lock:
            self.oms_failures += 1

    def record_duplicate_prevented(self) -> None:
        with self._lock:
            self.duplicates_prevented += 1

    def record_risk_reject(self) -> None:
        with self._lock:
            self.risk_rejects += 1

    def snapshot(self) -> dict[str, float | int]:
        with self._lock:
            exec_avg = (
                self.execution_latency_ms_sum / self.execution_latency_samples
                if self.execution_latency_samples
                else 0.0
            )
            gw_avg = (
                self.gateway_latency_ms_sum / self.gateway_latency_samples
                if self.gateway_latency_samples
                else 0.0
            )
            attempts = self.fills + self.rejects
            fill_rate = (self.fills / attempts * 100.0) if attempts else 0.0
            reject_rate = (self.rejects / attempts * 100.0) if attempts else 0.0
            return {
                "execution_latency_ms": round(exec_avg, 3),
                "gateway_latency_ms": round(gw_avg, 3),
                "decision_throughput": self.decisions,
                "fill_rate_pct": round(fill_rate, 3),
                "reject_rate_pct": round(reject_rate, 3),
                "oms_failures": self.oms_failures,
                "duplicates_prevented": self.duplicates_prevented,
                "risk_rejects": self.risk_rejects,
                "fills": self.fills,
                "rejects": self.rejects,
            }
