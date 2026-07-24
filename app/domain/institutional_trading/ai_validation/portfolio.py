"""Portfolio analytics — returns, drawdown, exposure."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any


_ASSET_CLASS: dict[str, str] = {
    "XAUUSD": "metals",
    "XAGUSD": "metals",
    "EURUSD": "fx",
    "GBPUSD": "fx",
    "USDJPY": "fx",
    "NAS100": "indices",
    "US30": "indices",
    "BTCUSD": "crypto",
}


def asset_class_for(symbol: str) -> str:
    return _ASSET_CLASS.get((symbol or "").upper(), "other")


@dataclass
class PortfolioAnalyticsStore:
    equity_points: list[tuple[datetime, float]] = field(default_factory=list)
    peak_equity: float = 0.0
    daily_returns: list[float] = field(default_factory=list)
    exposure_by_symbol: dict[str, float] = field(default_factory=dict)
    correlation_exposure: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_equity(self, equity: float) -> None:
        now = datetime.now(UTC)
        with self._lock:
            self.equity_points.append((now, float(equity)))
            if len(self.equity_points) > 10_000:
                self.equity_points = self.equity_points[-10_000:]
            if equity > self.peak_equity:
                self.peak_equity = float(equity)

    def record_pnl(self, pnl: float) -> None:
        with self._lock:
            self.daily_returns.append(float(pnl))
            if len(self.daily_returns) > 5_000:
                self.daily_returns = self.daily_returns[-5_000:]

    def set_exposures(
        self,
        *,
        by_symbol: dict[str, float],
        correlation_exposure: float = 0.0,
    ) -> None:
        with self._lock:
            self.exposure_by_symbol = {k: float(v) for k, v in by_symbol.items()}
            self.correlation_exposure = float(correlation_exposure)

    def _return_since(self, delta: timedelta) -> float | None:
        if len(self.equity_points) < 2:
            # fallback: sum pnl samples
            return round(sum(self.daily_returns[-max(1, int(delta.days) or 1) :]), 2) if self.daily_returns else None
        start = datetime.now(UTC) - delta
        series = [(t, e) for t, e in self.equity_points if t >= start]
        if len(series) < 2:
            first = self.equity_points[0][1]
            last = self.equity_points[-1][1]
        else:
            first = series[0][1]
            last = series[-1][1]
        if first == 0:
            return None
        return round(100.0 * (last - first) / first, 3)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            equity = self.equity_points[-1][1] if self.equity_points else None
            peak = self.peak_equity or (equity or 0.0)
            current_dd = None
            max_dd = None
            if equity is not None and peak > 0:
                current_dd = round(100.0 * (peak - equity) / peak, 3)
            # Max drawdown from equity path
            running_peak = 0.0
            worst = 0.0
            for _, e in self.equity_points:
                running_peak = max(running_peak, e)
                if running_peak > 0:
                    dd = 100.0 * (running_peak - e) / running_peak
                    worst = max(worst, dd)
            max_dd = round(worst, 3) if self.equity_points else None

            by_class: dict[str, float] = {}
            for sym, exp in self.exposure_by_symbol.items():
                cls = asset_class_for(sym)
                by_class[cls] = by_class.get(cls, 0.0) + exp

            daily = self._return_since(timedelta(days=1))
            weekly = self._return_since(timedelta(days=7))
            monthly = self._return_since(timedelta(days=30))

            return {
                "daily_return_pct": daily,
                "weekly_return_pct": weekly,
                "monthly_return_pct": monthly,
                "max_drawdown_pct": max_dd,
                "current_drawdown_pct": current_dd,
                "exposure_by_symbol": dict(self.exposure_by_symbol),
                "exposure_by_asset_class": by_class,
                "correlation_exposure": self.correlation_exposure,
                "equity": equity,
                "peak_equity": peak or None,
            }


_STORE: PortfolioAnalyticsStore | None = None
_LOCK = threading.Lock()


def get_portfolio_analytics_store() -> PortfolioAnalyticsStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = PortfolioAnalyticsStore()
        return _STORE
