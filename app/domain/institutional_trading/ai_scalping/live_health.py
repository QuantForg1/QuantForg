"""Live health monitor + self-protection — pause NEW entries only."""

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
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

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

    def record_reject(self) -> None:
        now = datetime.now(UTC)
        with self._lock:
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

    def record_gateway_instability(self) -> None:
        now = datetime.now(UTC)
        with self._lock:
            self._gateway_fails.append(now)
            self._trim(self._gateway_fails, 180)
            self._protection.gateway_instability = len(self._gateway_fails)
            if len(self._gateway_fails) >= self.gateway_fail_threshold:
                self._pause(
                    f"Gateway instability ({len(self._gateway_fails)} events)"
                )

    def record_drawdown(self, drawdown_pct: Decimal) -> None:
        with self._lock:
            self._protection.drawdown_pct = drawdown_pct
            if drawdown_pct >= self.max_drawdown_pct:
                self._pause(f"Drawdown {drawdown_pct}% ≥ {self.max_drawdown_pct}%")
            elif self._protection.new_entries_paused:
                self._maybe_resume_health()

    def allow_new_entries(self) -> tuple[bool, str]:
        with self._lock:
            if not self._health.all_ok:
                return False, self._health.detail
            if self._protection.new_entries_paused:
                reason = "; ".join(self._protection.reasons) or "self-protection pause"
                return False, reason
            return True, "ok"

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "health": self._health.to_dict(),
                "self_protection": self._protection.to_dict(),
            }

    def _pause(self, reason: str) -> None:
        if reason not in self._protection.reasons:
            self._protection.reasons.append(reason)
            self._protection.reasons = self._protection.reasons[-10:]
        if not self._protection.new_entries_paused:
            self._protection.new_entries_paused = True
            self._protection.paused_at = datetime.now(UTC).isoformat()

    def _maybe_resume_health(self) -> None:
        """Resume only when health is clear and burst counters recovered."""
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
            self._protection.new_entries_paused = False
            self._protection.reasons = []
            self._protection.paused_at = None
        _ = now  # keep for future cool-down logic

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
