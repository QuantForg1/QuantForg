"""Incremental candle fetching for the ITE cycle.

Every robot cycle needs ~1,700 bars across five timeframes, but closed bars
never change: only the forming bar (and, at a rollover, one new bar) moves.
Re-downloading every bar each cycle overloaded the Windows MT5 gateway
(Cloudflare 502 "origin overloaded", 19 Nov). This cache keeps the series per
(adapter, symbol, timeframe) and fetches only a small tail each cycle,
merging by bar open time. A full refetch happens on first use, periodically,
when a larger count is requested, or whenever the tail does not overlap the
cached series (gap) — so the merged series is always contiguous and current.

Disable with ``QF_CANDLE_TAIL_CACHE=0``.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Any

TAIL_BARS = 5
FULL_REFRESH_SECONDS = 300.0


def tail_cache_enabled() -> bool:
    return os.environ.get("QF_CANDLE_TAIL_CACHE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


@dataclass
class _Entry:
    rates: list[Any]
    count: int
    full_at: float


class RatesTailCache:
    def __init__(
        self,
        *,
        tail: int = TAIL_BARS,
        full_refresh_seconds: float = FULL_REFRESH_SECONDS,
        clock: Any = time.monotonic,
    ) -> None:
        self.tail = tail
        self.full_refresh_seconds = full_refresh_seconds
        self._clock = clock
        self._entries: dict[tuple[Any, ...], _Entry] = {}
        self._lock = threading.Lock()

    def plan(self, key: tuple[Any, ...], count: int) -> int:
        """How many bars to request now (``count`` = full, else the tail)."""
        with self._lock:
            entry = self._entries.get(key)
        if (
            entry is None
            or entry.count < count
            or len(entry.rates) < min(count, entry.count)
            or self._clock() - entry.full_at >= self.full_refresh_seconds
        ):
            return count
        return min(self.tail, count)

    def merge(
        self,
        key: tuple[Any, ...],
        count: int,
        fetched: list[Any],
        *,
        full: bool,
    ) -> list[Any] | None:
        """Store/merge a fetch. Returns the series, or ``None`` when a tail
        fetch cannot be merged safely (caller must refetch in full)."""
        rows = sorted(fetched or [], key=lambda r: r.open_time)
        if full:
            if rows:
                with self._lock:
                    self._entries[key] = _Entry(rows[-count:], count, self._clock())
            return rows[-count:]
        with self._lock:
            entry = self._entries.get(key)
        if entry is None or not rows or not entry.rates:
            return None
        first_new = rows[0].open_time
        if first_new > entry.rates[-1].open_time:
            return None  # gap between cache and tail: refetch in full
        if rows[-1].open_time < entry.rates[-1].open_time:
            return None  # tail older than cache: something is off
        kept = [r for r in entry.rates if r.open_time < first_new]
        merged = (kept + rows)[-count:]
        with self._lock:
            self._entries[key] = _Entry(merged, entry.count, entry.full_at)
        return merged

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_CACHE = RatesTailCache()


def shared_rates_cache() -> RatesTailCache:
    return _CACHE
