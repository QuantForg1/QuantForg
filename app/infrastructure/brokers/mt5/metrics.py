"""Lightweight process metrics for Railway→Gateway traffic (hardening)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

_PATH_WINDOW = 200


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


class GatewayMetrics:
    """In-process counters — no secrets; suitable for /ops or smoke reports."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._lifetime = _Window()
        self._minute = _Window()
        self._by_path: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=_PATH_WINDOW)
        )

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
            self._by_path[key].append(max(0.0, float(latency_ms)))

    def record_cache(self, *, hit: bool) -> None:
        with self._lock:
            self._roll()
            for window in (self._lifetime, self._minute):
                if hit:
                    window.cache_hits += 1
                else:
                    window.cache_misses += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            self._roll()

            def pack(w: _Window) -> dict[str, Any]:
                avg = (w.total_latency_ms / w.count) if w.count else 0.0
                looked = w.cache_hits + w.cache_misses
                hit_ratio = (w.cache_hits / looked) if looked else None
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
            return {
                "last_minute": pack(self._minute),
                "lifetime": pack(self._lifetime),
                "requests_per_minute": self._minute.count,
                "by_endpoint": by_endpoint,
                "slowest_endpoint": slowest_endpoint,
                "slowest_latency_ms": slowest_latency_ms,
            }


gateway_metrics = GatewayMetrics()
