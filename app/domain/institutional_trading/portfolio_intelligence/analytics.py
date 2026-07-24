"""Long-term portfolio analytics — rolling windows."""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass
class LongTermAnalyticsStore:
    _equity: list[tuple[datetime, float]] = field(default_factory=list)
    _returns: list[tuple[datetime, float]] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_equity(self, equity: float) -> None:
        now = datetime.now(UTC)
        with self._lock:
            self._equity.append((now, float(equity)))
            if len(self._equity) > 20_000:
                self._equity = self._equity[-20_000:]
            if len(self._equity) >= 2:
                prev = self._equity[-2][1]
                if prev:
                    self._returns.append((now, (float(equity) - prev) / prev))
                    if len(self._returns) > 20_000:
                        self._returns = self._returns[-20_000:]

    def _perf(self, days: int) -> dict[str, Any]:
        start = datetime.now(UTC) - timedelta(days=days)
        with self._lock:
            series = [(t, e) for t, e in self._equity if t >= start]
            rets = [r for t, r in self._returns if t >= start]
        if len(series) < 2:
            return {
                "return_pct": None,
                "volatility": None,
                "sharpe": None,
                "stability": None,
                "capital_efficiency": None,
            }
        first, last = series[0][1], series[-1][1]
        ret = round(100.0 * (last - first) / first, 3) if first else None
        if rets:
            mean = sum(rets) / len(rets)
            var = sum((x - mean) ** 2 for x in rets) / len(rets)
            vol = math.sqrt(var)
            sharpe = round(mean / vol, 3) if vol > 0 else None
            # stability: inverse of vol scaled
            stability = round(max(0.0, 100.0 * (1.0 - min(1.0, vol * 50))), 2)
            capital_efficiency = round((ret or 0) / max(vol * 100, 0.01), 3)
        else:
            vol = sharpe = stability = capital_efficiency = None
        return {
            "return_pct": ret,
            "volatility": round(vol, 6) if isinstance(vol, float) else None,
            "sharpe": sharpe,
            "stability": stability,
            "capital_efficiency": capital_efficiency,
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "rolling_30d": self._perf(30),
            "rolling_90d": self._perf(90),
            "rolling_1y": self._perf(365),
        }


_STORE: LongTermAnalyticsStore | None = None
_LOCK = threading.Lock()


def get_long_term_analytics() -> LongTermAnalyticsStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = LongTermAnalyticsStore()
        return _STORE
