"""Lightweight process metrics for Railway→Gateway traffic (hardening)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


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

    def _roll(self) -> None:
        now = time.monotonic()
        if now - self._minute.started >= 60.0:
            self._minute = _Window(started=now)

    def record_request(self, *, latency_ms: float, error: bool = False) -> None:
        with self._lock:
            self._roll()
            for window in (self._lifetime, self._minute):
                window.count += 1
                window.total_latency_ms += max(0.0, latency_ms)
                if error:
                    window.errors += 1

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

            return {
                "last_minute": pack(self._minute),
                "lifetime": pack(self._lifetime),
                "requests_per_minute": self._minute.count,
            }


gateway_metrics = GatewayMetrics()
