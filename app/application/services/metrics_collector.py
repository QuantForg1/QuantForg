"""Metrics collector — request latency, errors, throughput, cache, jobs.

Operational only. Does not touch trading or execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock

from app.domain.entities.ops import MetricsSnapshot


@dataclass
class MetricsCollector:
    """Process-wide in-memory metrics accumulator."""

    _lock: Lock = field(default_factory=Lock, init=False, repr=False)
    _request_count: int = field(default=0, init=False)
    _error_count: int = field(default=0, init=False)
    _total_latency_ms: float = field(default=0.0, init=False)
    _cache_hits: int = field(default=0, init=False)
    _cache_misses: int = field(default=0, init=False)
    _job_count: int = field(default=0, init=False)
    _total_job_duration_ms: float = field(default=0.0, init=False)
    _window_started_at: datetime = field(
        default_factory=lambda: datetime.now(UTC), init=False
    )
    _failure_signals: dict[str, bool] = field(default_factory=dict, init=False)

    def record_request(self, *, latency_ms: float, success: bool = True) -> None:
        with self._lock:
            self._request_count += 1
            self._total_latency_ms += max(0.0, latency_ms)
            if not success:
                self._error_count += 1

    def record_cache(self, *, hit: bool) -> None:
        with self._lock:
            if hit:
                self._cache_hits += 1
            else:
                self._cache_misses += 1

    def record_job(self, *, name: str, duration_ms: float) -> None:
        _ = name
        with self._lock:
            self._job_count += 1
            self._total_job_duration_ms += max(0.0, duration_ms)

    def set_failure(self, code: str, *, active: bool = True) -> None:
        """Mark operational failure signals used by alert rules."""
        with self._lock:
            self._failure_signals[code.strip().lower()] = active

    def failure_active(self, code: str) -> bool:
        with self._lock:
            return bool(self._failure_signals.get(code.strip().lower(), False))

    def snapshot(self) -> MetricsSnapshot:
        with self._lock:
            now = datetime.now(UTC)
            elapsed_min = max(
                (now - self._window_started_at).total_seconds() / 60.0, 1e-9
            )
            avg_latency = (
                self._total_latency_ms / self._request_count
                if self._request_count
                else 0.0
            )
            error_rate = (
                self._error_count / self._request_count if self._request_count else 0.0
            )
            cache_total = self._cache_hits + self._cache_misses
            hit_ratio = self._cache_hits / cache_total if cache_total else 0.0
            avg_job = (
                self._total_job_duration_ms / self._job_count
                if self._job_count
                else 0.0
            )
            return MetricsSnapshot(
                request_count=self._request_count,
                error_count=self._error_count,
                total_latency_ms=self._total_latency_ms,
                avg_latency_ms=avg_latency,
                error_rate=error_rate,
                throughput_per_minute=self._request_count / elapsed_min,
                cache_hits=self._cache_hits,
                cache_misses=self._cache_misses,
                cache_hit_ratio=hit_ratio,
                job_count=self._job_count,
                avg_job_duration_ms=avg_job,
                collected_at=now,
            )

    def reset(self) -> None:
        with self._lock:
            self._request_count = 0
            self._error_count = 0
            self._total_latency_ms = 0.0
            self._cache_hits = 0
            self._cache_misses = 0
            self._job_count = 0
            self._total_job_duration_ms = 0.0
            self._window_started_at = datetime.now(UTC)
            self._failure_signals.clear()
