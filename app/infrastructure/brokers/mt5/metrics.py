"""Lightweight process metrics for Railway→Gateway traffic (hardening)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from app.infrastructure.brokers.mt5.gateway_budget import (
    MUTATION_LIMIT,
    OBS_READ_LIMIT,
    TRADING_READ_LIMIT,
    UI_READ_LIMIT,
    resource_pressure_state,
)

_PATH_WINDOW = 200
_LATENCY_WINDOW = 400


def _percentile(samples: list[float], pct: float) -> float:
    if not samples:
        return 0.0
    xs = sorted(samples)
    if len(xs) == 1:
        return round(xs[0], 3)
    k = (len(xs) - 1) * (max(0.0, min(100.0, pct)) / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    frac = k - lo
    return round(xs[lo] * (1.0 - frac) + xs[hi] * frac, 3)


@dataclass
class _Window:
    started: float = field(default_factory=time.monotonic)
    count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    errors: int = 0
    total_latency_ms: float = 0.0
    errno11: int = 0
    timeouts: int = 0
    retries: int = 0
    retry_exhausted: int = 0
    calc_failures: int = 0
    coalesce_hits: int = 0
    pool_replaces: int = 0
    reused_connections: int = 0


class GatewayMetrics:
    """In-process counters — no secrets; suitable for /ops or smoke reports."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._lifetime = _Window()
        self._minute = _Window()
        self._by_path: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=_PATH_WINDOW)
        )
        self._latencies: deque[float] = deque(maxlen=_LATENCY_WINDOW)
        self._active = 0
        self._read_only_inflight = 0
        self._mutations_inflight = 0
        self._calc_inflight = 0
        self._pool_max = 20
        self._pool_keepalive = 10
        self._clients_built = 0

    def _roll(self) -> None:
        now = time.monotonic()
        if now - self._minute.started >= 60.0:
            self._minute = _Window(started=now)

    def record_request(
        self, *, latency_ms: float, error: bool = False, path: str = ""
    ) -> None:
        with self._lock:
            self._roll()
            for window in (self._lifetime, self._minute):
                window.count += 1
                window.total_latency_ms += max(0.0, latency_ms)
                if error:
                    window.errors += 1
            key = (path or "").split("?", 1)[0].strip() or "unknown"
            sample = max(0.0, float(latency_ms))
            self._by_path[key].append(sample)
            self._latencies.append(sample)
            if error and key in {
                "/trade/order_calc_profit",
                "/trade/order_calc_margin",
            }:
                self._lifetime.calc_failures += 1
                self._minute.calc_failures += 1

    def record_cache(self, *, hit: bool) -> None:
        with self._lock:
            self._roll()
            for window in (self._lifetime, self._minute):
                if hit:
                    window.cache_hits += 1
                else:
                    window.cache_misses += 1

    def record_retry(
        self,
        *,
        exhausted: bool = False,
        errno11: bool = False,
        timeout: bool = False,
    ) -> None:
        with self._lock:
            self._roll()
            for window in (self._lifetime, self._minute):
                window.retries += 1
                if exhausted:
                    window.retry_exhausted += 1
                if errno11:
                    window.errno11 += 1
                if timeout:
                    window.timeouts += 1

    def record_coalesce(self, *, hit: bool) -> None:
        with self._lock:
            self._roll()
            if hit:
                self._lifetime.coalesce_hits += 1
                self._minute.coalesce_hits += 1
                self._lifetime.cache_hits += 1
                self._minute.cache_hits += 1
            else:
                self._lifetime.cache_misses += 1
                self._minute.cache_misses += 1

    def record_pool_replace(self) -> None:
        with self._lock:
            self._roll()
            self._lifetime.pool_replaces += 1
            self._minute.pool_replaces += 1
            self._clients_built += 1

    def record_client_built(self) -> None:
        with self._lock:
            self._clients_built += 1

    def record_connection_reuse(self) -> None:
        with self._lock:
            self._roll()
            self._lifetime.reused_connections += 1
            self._minute.reused_connections += 1

    def begin_inflight(self, *, mutation: bool, calc: bool = False) -> None:
        with self._lock:
            self._active += 1
            if mutation:
                self._mutations_inflight += 1
            else:
                self._read_only_inflight += 1
            if calc:
                self._calc_inflight += 1

    def end_inflight(self, *, mutation: bool, calc: bool = False) -> None:
        with self._lock:
            self._active = max(0, self._active - 1)
            if mutation:
                self._mutations_inflight = max(0, self._mutations_inflight - 1)
            else:
                self._read_only_inflight = max(0, self._read_only_inflight - 1)
            if calc:
                self._calc_inflight = max(0, self._calc_inflight - 1)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            self._roll()
            lat = list(self._latencies)

            def pack(w: _Window) -> dict[str, Any]:
                avg = (w.total_latency_ms / w.count) if w.count else 0.0
                looked = w.cache_hits + w.cache_misses
                hit_ratio = (w.cache_hits / looked) if looked else None
                reuse_den = max(1, w.count)
                return {
                    "requests": w.count,
                    "errors": w.errors,
                    "avg_latency_ms": round(avg, 3),
                    "cache_hits": w.cache_hits,
                    "cache_misses": w.cache_misses,
                    "cache_hit_ratio": (
                        round(hit_ratio, 4) if hit_ratio is not None else None
                    ),
                    "window_seconds": round(time.monotonic() - w.started, 1),
                    "errno_11_count": w.errno11,
                    "timeout_count": w.timeouts,
                    "retry_count": w.retries,
                    "retry_exhausted_count": w.retry_exhausted,
                    "order_calc_profit_failures": w.calc_failures,
                    "connection_reuse_rate": round(w.reused_connections / reuse_den, 4),
                }

            by_endpoint: dict[str, Any] = {}
            slowest_endpoint = None
            slowest_latency_ms = 0.0
            for path, samples in self._by_path.items():
                rows = list(samples)
                if not rows:
                    continue
                mx = round(max(rows), 3)
                pack_path = {
                    "count": len(rows),
                    "p50": _percentile(rows, 50),
                    "p95": _percentile(rows, 95),
                    "p99": _percentile(rows, 99),
                    "max": mx,
                }
                by_endpoint[path] = pack_path
                if mx >= slowest_latency_ms:
                    slowest_latency_ms = mx
                    slowest_endpoint = path
            budget = (
                TRADING_READ_LIMIT
                + UI_READ_LIMIT
                + OBS_READ_LIMIT
                + MUTATION_LIMIT
            )
            pressure = resource_pressure_state(
                errno11_count=self._minute.errno11,
                retry_exhausted_count=self._minute.retry_exhausted,
                timeout_count=self._minute.timeouts,
                active_requests=self._active,
                budget=budget,
                calc_failures=self._minute.calc_failures,
            )
            pool_available = max(0, self._pool_max - self._active)
            return {
                "last_minute": pack(self._minute),
                "lifetime": pack(self._lifetime),
                "requests_per_minute": self._minute.count,
                "by_endpoint": by_endpoint,
                "slowest_endpoint": slowest_endpoint,
                "slowest_latency_ms": slowest_latency_ms,
                "gateway_active_requests": self._active,
                "gateway_read_only_inflight": self._read_only_inflight,
                "gateway_mutations_inflight": self._mutations_inflight,
                "gateway_connection_pool_size": self._pool_max,
                "gateway_connection_pool_available": pool_available,
                "order_calc_profit_inflight": self._calc_inflight,
                "order_calc_profit_failures": self._lifetime.calc_failures,
                "errno_11_count": self._lifetime.errno11,
                "timeout_count": self._lifetime.timeouts,
                "retry_count": self._lifetime.retries,
                "retry_exhausted_count": self._lifetime.retry_exhausted,
                "connection_reuse_rate": pack(self._lifetime)["connection_reuse_rate"],
                "average_gateway_latency": pack(self._lifetime)["avg_latency_ms"],
                "p95_gateway_latency": _percentile(lat, 95),
                "p99_gateway_latency": _percentile(lat, 99),
                "resource_pressure_state": pressure,
                "clients_built": self._clients_built,
                "concurrency_budget": {
                    "trading_read": TRADING_READ_LIMIT,
                    "ui_read": UI_READ_LIMIT,
                    "observability_read": OBS_READ_LIMIT,
                    "mutation": MUTATION_LIMIT,
                },
            }


gateway_metrics = GatewayMetrics()
