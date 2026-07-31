"""Live health monitor + self-protection — pause NEW entries only.

Global dependencies (gateway/broker/MT5/OMS/data/latency/drawdown/slippage/
gateway instability) pause the whole desk.

Reject bursts are PER-SYMBOL — a reject storm on XAUUSD must not block EURUSD.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any


@dataclass
class DependencyHealth:
    gateway_ok: bool = True
    broker_ok: bool = True
    mt5_ok: bool = True
    oms_ok: bool = True
    market_data_ok: bool = True
    latency_ok: bool = True
    detail: str = "healthy"

    @property
    def all_ok(self) -> bool:
        return all(
            (
                self.gateway_ok,
                self.broker_ok,
                self.mt5_ok,
                self.oms_ok,
                self.market_data_ok,
                self.latency_ok,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "gateway_ok": self.gateway_ok,
            "broker_ok": self.broker_ok,
            "mt5_ok": self.mt5_ok,
            "oms_ok": self.oms_ok,
            "market_data_ok": self.market_data_ok,
            "latency_ok": self.latency_ok,
            "all_ok": self.all_ok,
            "detail": self.detail,
            "critical_failed": not self.all_ok,
        }


@dataclass
class SelfProtectionState:
    new_entries_paused: bool = False
    reasons: list[str] = field(default_factory=list)
    paused_at: str | None = None
    drawdown_pct: Decimal | None = None
    reject_burst: int = 0
    slippage_events: int = 0
    gateway_instability: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "new_entries_paused": self.new_entries_paused,
            "reasons": list(self.reasons),
            "paused_at": self.paused_at,
            "drawdown_pct": (
                str(self.drawdown_pct) if self.drawdown_pct is not None else None
            ),
            "reject_burst": self.reject_burst,
            "slippage_events": self.slippage_events,
            "gateway_instability": self.gateway_instability,
            "existing_positions_managed": True,
        }


@dataclass
class LiveHealthMonitor:
    """Continuously evaluate deps; pause new entries on critical failure."""

    max_drawdown_pct: Decimal = Decimal("3.0")
    reject_burst_threshold: int = 5
    reject_window_seconds: int = 120
    slippage_burst_threshold: int = 3
    slippage_window_seconds: int = 300
    gateway_fail_threshold: int = 3
    high_latency_ms: float = 2000.0

    _health: DependencyHealth = field(default_factory=DependencyHealth)
    _protection: SelfProtectionState = field(default_factory=SelfProtectionState)
    _rejects: deque[datetime] = field(default_factory=deque, repr=False)
    _slips: deque[datetime] = field(default_factory=deque, repr=False)
    _gateway_fails: deque[datetime] = field(default_factory=deque, repr=False)
    _symbol_rejects: dict[str, deque[datetime]] = field(
        default_factory=dict, repr=False
    )
    _symbol_reject_reasons: dict[str, str] = field(default_factory=dict, repr=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def update_dependencies(
        self,
        *,
        gateway_ok: bool | None = None,
        broker_ok: bool | None = None,
        mt5_ok: bool | None = None,
        oms_ok: bool | None = None,
        market_data_ok: bool | None = None,
        latency_ms: float | None = None,
    ) -> DependencyHealth:
        with self._lock:
            if gateway_ok is not None:
                self._health.gateway_ok = gateway_ok
            if broker_ok is not None:
                self._health.broker_ok = broker_ok
            if mt5_ok is not None:
                self._health.mt5_ok = mt5_ok
            if oms_ok is not None:
                self._health.oms_ok = oms_ok
            if market_data_ok is not None:
                self._health.market_data_ok = market_data_ok
            if latency_ms is not None:
                self._health.latency_ok = float(latency_ms) < self.high_latency_ms
            fails = [
                name
                for name, ok in (
                    ("gateway", self._health.gateway_ok),
                    ("broker", self._health.broker_ok),
                    ("mt5", self._health.mt5_ok),
                    ("oms", self._health.oms_ok),
                    ("market_data", self._health.market_data_ok),
                    ("latency", self._health.latency_ok),
                )
                if not ok
            ]
            self._health.detail = (
                "healthy" if not fails else f"critical:{','.join(fails)}"
            )
            if fails:
                self._pause(f"Dependency failure: {', '.join(fails)}")
            else:
                self._maybe_resume_health()
            return DependencyHealth(
                gateway_ok=self._health.gateway_ok,
                broker_ok=self._health.broker_ok,
                mt5_ok=self._health.mt5_ok,
                oms_ok=self._health.oms_ok,
                market_data_ok=self._health.market_data_ok,
                latency_ok=self._health.latency_ok,
                detail=self._health.detail,
            )

    def record_reject(self, symbol: str | None = None) -> None:
        """Record a reject. With symbol → pause that symbol only."""
        now = datetime.now(UTC)
        key = (symbol or "").strip().upper()
        with self._lock:
            if key:
                q = self._symbol_rejects.setdefault(key, deque())
                q.append(now)
                self._trim(q, self.reject_window_seconds)
                if len(q) >= self.reject_burst_threshold:
                    reason = (
                        f"Excessive rejects on {key} ({len(q)} in "
                        f"{self.reject_window_seconds}s)"
                    )
                    self._symbol_reject_reasons[key] = reason
                # Track aggregate count for observability only (no global pause)
                self._protection.reject_burst = sum(
                    len(v) for v in self._symbol_rejects.values()
                )
                return

            # Legacy / unspecified symbol — global reject pause
            self._rejects.append(now)
            self._trim(self._rejects, self.reject_window_seconds)
            self._protection.reject_burst = len(self._rejects)
            if len(self._rejects) >= self.reject_burst_threshold:
                self._pause(
                    f"Excessive rejects ({len(self._rejects)} in "
                    f"{self.reject_window_seconds}s)"
                )

    def record_abnormal_slippage(self) -> None:
        now = datetime.now(UTC)
        with self._lock:
            self._slips.append(now)
            self._trim(self._slips, self.slippage_window_seconds)
            self._protection.slippage_events = len(self._slips)
            if len(self._slips) >= self.slippage_burst_threshold:
                self._pause(
                    f"Abnormal slippage burst ({len(self._slips)} in "
                    f"{self.slippage_window_seconds}s)"
                )

    def record_abnormal_spread(self, detail: str | None = None) -> None:
        """Pause new entries on abnormal spread — manage open positions continues."""
        with self._lock:
            self._pause(detail or "Abnormal spread protection")

    def record_flash_move(self, detail: str | None = None) -> None:
        """Pause new entries on flash-crash style moves."""
        with self._lock:
            self._pause(detail or "Flash crash protection")

    def record_margin_danger(self, detail: str | None = None) -> None:
        """Pause new entries when free margin / margin level is critical."""
        with self._lock:
            self._pause(detail or "Margin danger")

    def record_gateway_instability(self) -> None:
        now = datetime.now(UTC)
        with self._lock:
            self._gateway_fails.append(now)
            self._trim(self._gateway_fails, 180)
            self._protection.gateway_instability = len(self._gateway_fails)
            if len(self._gateway_fails) >= self.gateway_fail_threshold:
                self._pause(f"Gateway instability ({len(self._gateway_fails)} events)")

    def record_drawdown(self, drawdown_pct: Decimal) -> None:
        with self._lock:
            self._protection.drawdown_pct = drawdown_pct
            if drawdown_pct >= self.max_drawdown_pct:
                self._pause(f"Drawdown {drawdown_pct}% ≥ {self.max_drawdown_pct}%")
            elif self._protection.new_entries_paused:
                self._maybe_resume_health()

    def allow_new_entries(self, symbol: str | None = None) -> tuple[bool, str]:
        """Global deps always apply. Reject bursts are symbol-scoped when keyed."""
        key = (symbol or "").strip().upper()
        with self._lock:
            if not self._health.all_ok:
                return False, self._health.detail
            if self._protection.new_entries_paused:
                reason = "; ".join(self._protection.reasons) or "self-protection pause"
                return False, reason
            if key:
                q = self._symbol_rejects.get(key)
                if q is not None:
                    self._trim(q, self.reject_window_seconds)
                    if len(q) >= self.reject_burst_threshold:
                        why = self._symbol_reject_reasons.get(key) or (
                            f"Excessive rejects on {key}"
                        )
                        return False, why
                    if len(q) < self.reject_burst_threshold:
                        self._symbol_reject_reasons.pop(key, None)
            return True, "ok"

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            per_sym = {
                sym: {
                    "reject_burst": len(q),
                    "paused": len(q) >= self.reject_burst_threshold,
                    "reason": self._symbol_reject_reasons.get(sym),
                }
                for sym, q in self._symbol_rejects.items()
            }
            return {
                "health": self._health.to_dict(),
                "self_protection": self._protection.to_dict(),
                "symbol_rejects": per_sym,
            }

    def reset(self) -> None:
        """Clear burst counters and resume entries (unit-test isolation)."""
        with self._lock:
            self._health = DependencyHealth()
            self._protection = SelfProtectionState()
            self._rejects.clear()
            self._slips.clear()
            self._gateway_fails.clear()
            self._symbol_rejects.clear()
            self._symbol_reject_reasons.clear()

    def _pause(self, reason: str) -> None:
        if reason not in self._protection.reasons:
            self._protection.reasons.append(reason)
            self._protection.reasons = self._protection.reasons[-10:]
        if not self._protection.new_entries_paused:
            self._protection.new_entries_paused = True
            self._protection.paused_at = datetime.now(UTC).isoformat()

    def _maybe_resume_health(self) -> None:
        """Resume only when health is clear and global burst counters recovered."""
        if not self._health.all_ok:
            return
        now = datetime.now(UTC)
        self._trim(self._rejects, self.reject_window_seconds)
        self._trim(self._slips, self.slippage_window_seconds)
        self._trim(self._gateway_fails, 180)
        dd_ok = (
            self._protection.drawdown_pct is None
            or self._protection.drawdown_pct < self.max_drawdown_pct
        )
        bursts_ok = (
            len(self._rejects) < self.reject_burst_threshold
            and len(self._slips) < self.slippage_burst_threshold
            and len(self._gateway_fails) < self.gateway_fail_threshold
        )
        if dd_ok and bursts_ok and self._protection.new_entries_paused:
            # Keep dependency/slippage/drawdown/gateway pauses only — strip reject noise
            self._protection.new_entries_paused = False
            self._protection.reasons = [
                r for r in self._protection.reasons if "Excessive rejects" not in r
            ]
            self._protection.paused_at = None
            if self._protection.reasons:
                # Still have global reasons (should not happen if bursts_ok)
                pass
        _ = now

    @staticmethod
    def _trim(q: deque[datetime], window_s: int) -> None:
        now = datetime.now(UTC)
        while q and (now - q[0]) > timedelta(seconds=window_s):
            q.popleft()


_MON: LiveHealthMonitor | None = None
_LOCK = threading.Lock()


def get_live_health_monitor() -> LiveHealthMonitor:
    global _MON
    with _LOCK:
        if _MON is None:
            _MON = LiveHealthMonitor()
        return _MON
