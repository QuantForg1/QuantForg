"""Live performance monitor — orders, latency, slippage, PnL windows."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass
class LivePerformanceMonitor:
    orders_submitted: int = 0
    orders_filled: int = 0
    orders_rejected: int = 0
    retry_count: int = 0
    latency_ms_sum: float = 0.0
    latency_samples: int = 0
    slippage_sum: float = 0.0
    slippage_samples: int = 0
    spread_sum: float = 0.0
    spread_samples: int = 0
    wins: int = 0
    losses: int = 0
    _pnl_events: list[tuple[datetime, float]] = field(default_factory=list, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_submit(self) -> None:
        with self._lock:
            self.orders_submitted += 1

    def record_fill(self, *, latency_ms: float | None = None, slippage: float | None = None) -> None:
        with self._lock:
            self.orders_filled += 1
            if latency_ms is not None:
                self.latency_ms_sum += float(latency_ms)
                self.latency_samples += 1
            if slippage is not None:
                self.slippage_sum += float(slippage)
                self.slippage_samples += 1

    def record_reject(self, *, latency_ms: float | None = None) -> None:
        with self._lock:
            self.orders_rejected += 1
            if latency_ms is not None:
                self.latency_ms_sum += float(latency_ms)
                self.latency_samples += 1

    def record_retry(self, n: int = 1) -> None:
        with self._lock:
            self.retry_count += int(n)

    def record_spread(self, spread: float) -> None:
        with self._lock:
            self.spread_sum += float(spread)
            self.spread_samples += 1

    def record_closed_trade(self, *, win: bool, pnl: float) -> None:
        with self._lock:
            if win:
                self.wins += 1
            else:
                self.losses += 1
            self._pnl_events.append((datetime.now(UTC), float(pnl)))
            cutoff = datetime.now(UTC) - timedelta(days=40)
            self._pnl_events = [(t, p) for t, p in self._pnl_events if t >= cutoff]

    def _pnl_since(self, delta: timedelta) -> float:
        start = datetime.now(UTC) - delta
        return round(sum(p for t, p in self._pnl_events if t >= start), 2)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            trades = self.wins + self.losses
            avg_lat = (
                self.latency_ms_sum / self.latency_samples
                if self.latency_samples
                else None
            )
            avg_slip = (
                self.slippage_sum / self.slippage_samples
                if self.slippage_samples
                else None
            )
            avg_spread = (
                self.spread_sum / self.spread_samples if self.spread_samples else None
            )
            win_rate = round(100.0 * self.wins / trades, 2) if trades else None
            daily = self._pnl_since(timedelta(days=1))
            weekly = self._pnl_since(timedelta(days=7))
            # month approx
            monthly = self._pnl_since(timedelta(days=30))
            return {
                "orders_submitted": self.orders_submitted,
                "orders_filled": self.orders_filled,
                "orders_rejected": self.orders_rejected,
                "retry_count": self.retry_count,
                "avg_execution_latency_ms": round(avg_lat, 3) if avg_lat is not None else None,
                "avg_slippage": round(avg_slip, 4) if avg_slip is not None else None,
                "avg_spread": round(avg_spread, 4) if avg_spread is not None else None,
                "win_rate": win_rate,
                "daily_pnl": daily,
                "weekly_pnl": weekly,
                "monthly_pnl": monthly,
            }


_MON: LivePerformanceMonitor | None = None
_LOCK = threading.Lock()


def get_live_performance_monitor() -> LivePerformanceMonitor:
    global _MON
    with _LOCK:
        if _MON is None:
            _MON = LivePerformanceMonitor()
        return _MON
