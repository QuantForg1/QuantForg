"""Benchmark comparison — QuantForg vs Buy&Hold / SMA / baseline."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BenchmarkStore:
    quantforg_return_pct: float | None = None
    buy_hold_return_pct: float | None = None
    sma_crossover_return_pct: float | None = None
    baseline_return_pct: float | None = None
    period_label: str = "rolling_30d"
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def update(
        self,
        *,
        quantforg: float | None = None,
        buy_hold: float | None = None,
        sma: float | None = None,
        baseline: float | None = None,
        period_label: str | None = None,
    ) -> None:
        with self._lock:
            if quantforg is not None:
                self.quantforg_return_pct = float(quantforg)
            if buy_hold is not None:
                self.buy_hold_return_pct = float(buy_hold)
            if sma is not None:
                self.sma_crossover_return_pct = float(sma)
            if baseline is not None:
                self.baseline_return_pct = float(baseline)
            if period_label:
                self.period_label = period_label

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            q = self.quantforg_return_pct
            rows = [
                {"name": "QuantForg", "return_pct": q},
                {"name": "Buy & Hold", "return_pct": self.buy_hold_return_pct},
                {
                    "name": "SMA Crossover",
                    "return_pct": self.sma_crossover_return_pct,
                },
                {"name": "Baseline strategy", "return_pct": self.baseline_return_pct},
            ]

            def _rel(bench: float | None) -> float | None:
                if q is None or bench is None:
                    return None
                return round(q - bench, 3)

            return {
                "period": self.period_label,
                "series": rows,
                "relative_vs_buy_hold": _rel(self.buy_hold_return_pct),
                "relative_vs_sma": _rel(self.sma_crossover_return_pct),
                "relative_vs_baseline": _rel(self.baseline_return_pct),
            }


def estimate_buy_hold_return(prices: list[float]) -> float | None:
    if len(prices) < 2 or prices[0] == 0:
        return None
    return round(100.0 * (prices[-1] - prices[0]) / prices[0], 3)


def estimate_sma_crossover_return(
    prices: list[float], *, fast: int = 10, slow: int = 30
) -> float | None:
    """Simple long-only SMA cross simulation on close prices."""
    if len(prices) < slow + 2:
        return None
    cash = 1.0
    pos = 0.0
    entry = 0.0
    for i in range(slow, len(prices)):
        f = sum(prices[i - fast : i]) / fast
        s = sum(prices[i - slow : i]) / slow
        prev_f = sum(prices[i - fast - 1 : i - 1]) / fast
        prev_s = sum(prices[i - slow - 1 : i - 1]) / slow
        price = prices[i]
        # golden cross
        if prev_f <= prev_s and f > s and pos == 0:
            pos = cash / price
            cash = 0.0
            entry = price
        # death cross
        elif prev_f >= prev_s and f < s and pos > 0:
            cash = pos * price
            pos = 0.0
    final = cash + pos * prices[-1]
    return round(100.0 * (final - 1.0), 3)


_STORE: BenchmarkStore | None = None
_LOCK = threading.Lock()


def get_benchmark_store() -> BenchmarkStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = BenchmarkStore()
        return _STORE
