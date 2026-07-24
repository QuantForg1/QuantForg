"""Slippage analytics — expected vs actual entry/exit."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from app.domain.institutional_trading.ai_validation.config import (
    DEFAULT_AI_VALIDATION_CONFIG,
)


@dataclass
class SlippageSample:
    symbol: str
    side: str
    expected_entry: float
    actual_entry: float
    expected_exit: float | None
    actual_exit: float | None
    entry_slippage: float
    exit_slippage: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "expected_entry": self.expected_entry,
            "actual_entry": self.actual_entry,
            "expected_exit": self.expected_exit,
            "actual_exit": self.actual_exit,
            "entry_slippage": self.entry_slippage,
            "exit_slippage": self.exit_slippage,
        }


def compute_entry_slippage(*, side: str, expected: float, actual: float) -> float:
    """Positive = adverse for the trader."""
    s = (side or "buy").lower()
    if s in {"sell", "short"}:
        return round(expected - actual, 6)
    return round(actual - expected, 6)


def compute_exit_slippage(*, side: str, expected: float, actual: float) -> float:
    s = (side or "buy").lower()
    if s in {"sell", "short"}:
        return round(actual - expected, 6)
    return round(expected - actual, 6)


@dataclass
class SlippageAnalyticsStore:
    _samples: list[SlippageSample] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_fill(
        self,
        *,
        symbol: str,
        side: str,
        expected_entry: float,
        actual_entry: float,
        expected_exit: float | None = None,
        actual_exit: float | None = None,
    ) -> SlippageSample:
        entry_slip = compute_entry_slippage(
            side=side, expected=expected_entry, actual=actual_entry
        )
        exit_slip = None
        if expected_exit is not None and actual_exit is not None:
            exit_slip = compute_exit_slippage(
                side=side, expected=expected_exit, actual=actual_exit
            )
        sample = SlippageSample(
            symbol=symbol,
            side=side,
            expected_entry=expected_entry,
            actual_entry=actual_entry,
            expected_exit=expected_exit,
            actual_exit=actual_exit,
            entry_slippage=entry_slip,
            exit_slippage=exit_slip,
        )
        with self._lock:
            self._samples.append(sample)
            if len(self._samples) > 5_000:
                self._samples = self._samples[-5_000:]
        # Alert hook
        try:
            from app.domain.institutional_trading.ai_validation.alerts import (
                get_validation_alerter,
            )

            if abs(entry_slip) >= DEFAULT_AI_VALIDATION_CONFIG.alert_slippage_spike:
                get_validation_alerter().on_slippage_spike(slippage=entry_slip, symbol=symbol)
        except Exception:
            pass
        return sample

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            entries = [s.entry_slippage for s in self._samples]
            exits = [
                s.exit_slippage for s in self._samples if s.exit_slippage is not None
            ]
        if not entries:
            return {
                "samples": 0,
                "avg_slippage": None,
                "worst_slippage": None,
                "best_slippage": None,
                "avg_exit_slippage": None,
                "recommendation": "Insufficient fills for slippage recommendations",
                "recent": [],
            }
        avg = sum(entries) / len(entries)
        # worst = most adverse (highest positive)
        worst = max(entries)
        best = min(entries)
        avg_exit = sum(exits) / len(exits) if exits else None
        if avg > 0.5:
            rec = "Prefer limit/confirm spreads; avoid chasing market on thin liquidity"
        elif avg > 0.15:
            rec = "Soft spread filter OK — monitor session peaks"
        else:
            rec = "Execution slippage within acceptable band"
        with self._lock:
            recent = [s.to_dict() for s in self._samples[-20:]]
        return {
            "samples": len(entries),
            "avg_slippage": round(avg, 6),
            "worst_slippage": round(worst, 6),
            "best_slippage": round(best, 6),
            "avg_exit_slippage": round(avg_exit, 6) if avg_exit is not None else None,
            "recommendation": rec,
            "recent": list(reversed(recent)),
        }


_STORE: SlippageAnalyticsStore | None = None
_LOCK = threading.Lock()


def get_slippage_store() -> SlippageAnalyticsStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = SlippageAnalyticsStore()
        return _STORE
