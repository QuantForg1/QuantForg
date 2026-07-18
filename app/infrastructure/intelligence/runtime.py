"""Shared HTTP/runtime helpers for intelligence providers."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, TypeVar

import httpx

from app.domain.intelligence.providers import ProviderMetrics

T = TypeVar("T")


@dataclass
class TtlCache:
    ttl_seconds: float = 30.0
    max_items: int = 256
    _data: OrderedDict[str, tuple[float, Any]] = field(default_factory=OrderedDict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def get(self, key: str) -> Any | None:
        now = time.monotonic()
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires, value = item
            if expires < now:
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = (time.monotonic() + self.ttl_seconds, value)
            self._data.move_to_end(key)
            while len(self._data) > self.max_items:
                self._data.popitem(last=False)


@dataclass
class TokenBucket:
    """Simple per-provider rate limiter."""

    rate_per_minute: float = 60.0
    _tokens: float = field(default=0.0)
    _updated: float = field(default_factory=time.monotonic)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        self._tokens = self.rate_per_minute

    def allow(self) -> bool:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._updated
            self._updated = now
            self._tokens = min(
                self.rate_per_minute,
                self._tokens + elapsed * (self.rate_per_minute / 60.0),
            )
            if self._tokens < 1.0:
                return False
            self._tokens -= 1.0
            return True


@dataclass
class ProviderRuntime:
    metrics: ProviderMetrics = field(default_factory=ProviderMetrics)
    cache: TtlCache = field(default_factory=TtlCache)
    limiter: TokenBucket = field(default_factory=TokenBucket)
    timeout_seconds: float = 8.0

    def cached(self, key: str, factory: Callable[[], T]) -> T:
        hit = self.cache.get(key)
        if hit is not None:
            self.metrics.cache_hits += 1
            return hit  # type: ignore[no-any-return]
        value = factory()
        self.cache.set(key, value)
        return value

    def guarded(self, fn: Callable[[], T]) -> T | None:
        if not self.limiter.allow():
            self.metrics.rate_limited += 1
            self.metrics.last_error = "rate_limited"
            return None
        started = time.monotonic()
        self.metrics.requests += 1
        try:
            value = fn()
            self.metrics.last_latency_ms = (time.monotonic() - started) * 1000.0
            self.metrics.last_success_at = datetime.now(UTC).isoformat()
            self.metrics.last_error = ""
            return value
        except Exception as exc:
            self.metrics.failures += 1
            self.metrics.last_error = str(exc)[:240]
            self.metrics.last_latency_ms = (time.monotonic() - started) * 1000.0
            return None

    def get_json(self, url: str, *, params: dict[str, Any] | None = None) -> Any | None:
        def _call() -> Any:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                return response.json()

        return self.guarded(_call)
