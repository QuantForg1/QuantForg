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
    emergency_window_seconds: int = 120

    _health: DependencyHealth = field(default_factory=DependencyHealth)
    _protection: SelfProtectionState = field(default_factory=SelfProtectionState)
    _rejects: deque[datetime] = field(default_factory=deque, repr=False)
    _slips: deque[datetime] = field(default_factory=deque, repr=False)
    _gateway_fails: deque[datetime] = field(default_factory=deque, repr=False)
    _symbol_rejects: dict[str, deque[datetime]] = field(
        default_factory=dict, repr=False
    )
    _symbol_reject_reasons: dict[str, str] = field(default_factory=dict, repr=False)
    _emergencies: deque[tuple[datetime, str]] = field(default_factory=deque, repr=False)
    _last_execution_reject: dict[str, Any] | None = field(default=None, repr=False)
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

    def record_reject(
        self,
        symbol: str | None = None,
        *,
        source: str | None = None,
        reason: str | None = None,
        broker_retcode: int | None = None,
        mt5_retcode: int | None = None,
    ) -> None:
        """Record a genuine execution-layer reject. With symbol → pause that symbol only.

        Callers must not invoke this for WAIT, Risk/Safety holds, or OMS
        application rejects that never reached order_send / MT5.
        """
        now = datetime.now(UTC)
        key = (symbol or "").strip().upper()
        event = {
            "at": now.isoformat(),
            "symbol": key or None,
            "reject_source": source,
            "reject_reason": reason,
            "broker_retcode": broker_retcode,
            "mt5_retcode": mt5_retcode,
        }
        with self._lock:
            self._last_execution_reject = event
            if key:
                q = self._symbol_rejects.setdefault(key, deque())
                q.append(now)
                self._trim(q, self.reject_window_seconds)
                if len(q) >= self.reject_burst_threshold:
                    burst_reason = (
                        f"EXECUTION_REJECT_BURST: Excessive rejects on {key} "
                        f"({len(q)} in {self.reject_window_seconds}s)"
                    )
                    self._symbol_reject_reasons[key] = burst_reason
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
                    f"EXECUTION_REJECT_BURST: Excessive rejects ({len(self._rejects)} in "
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
        """Observability only. Hard spread reject is the bridge SPREAD_UNACCEPTABLE gate.

        A scoring-cycle spread event must not become a sticky Safety latch that
        blocks a later valid TAKE after spread has already passed the bridge.
        """
        with self._lock:
            if detail and detail not in self._protection.reasons:
                # Keep last reason for dashboards; do not pause new entries.
                self._protection.reasons = [
                    r for r in self._protection.reasons if "spread" not in r.lower()
                ]
                self._protection.reasons.append(detail)
                self._protection.reasons = self._protection.reasons[-10:]

    def record_flash_move(self, detail: str | None = None) -> None:
        """Time-bounded pause on flash-crash style moves."""
        with self._lock:
            self._emergencies.append(
                (datetime.now(UTC), detail or "Flash crash protection")
            )
            self._trim_emergencies()
            self._pause(detail or "Flash crash protection")

    def record_margin_danger(self, detail: str | None = None) -> None:
        """Time-bounded pause when free margin / margin level is critical."""
        with self._lock:
            self._emergencies.append((datetime.now(UTC), detail or "Margin danger"))
            self._trim_emergencies()
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
        """Telemetry only. Lifetime HWM drawdown must not Safety-latch new entries.

        Daily-loss 40% is the Risk circuit breaker. A 3% peak-equity pause cannot
        recover without a fill when the book is flat, so it is not a live gate.
        """
        with self._lock:
            self._protection.drawdown_pct = drawdown_pct

    def allow_new_entries(self, symbol: str | None = None) -> tuple[bool, str]:
        """Evaluate current windows. Unset/None health defaults to allow.

        Sticky ``new_entries_paused`` is not authoritative — recovered deps,
        expired bursts, and expired emergencies re-arm without a fill.
        """
        key = (symbol or "").strip().upper()
        with self._lock:
            self._trim_windows()
            if not self._health.all_ok:
                # Exact failed deps. Bridge maps gateway/MT5/broker → Safety.
                return False, self._health.detail
            if self._emergencies:
                return False, self._emergencies[-1][1]
            if len(self._rejects) >= self.reject_burst_threshold:
                return False, (
                    "EXECUTION_REJECT_BURST: Excessive rejects "
                    f"({len(self._rejects)} in {self.reject_window_seconds}s)"
                )
            if len(self._slips) >= self.slippage_burst_threshold:
                return False, (
                    f"Abnormal slippage burst ({len(self._slips)} in "
                    f"{self.slippage_window_seconds}s)"
                )
            if len(self._gateway_fails) >= self.gateway_fail_threshold:
                return False, (
                    f"Gateway instability ({len(self._gateway_fails)} events)"
                )
            if key:
                q = self._symbol_rejects.get(key)
                if q is not None:
                    self._trim(q, self.reject_window_seconds)
                    if len(q) >= self.reject_burst_threshold:
                        why = self._symbol_reject_reasons.get(key) or (
                            f"Excessive rejects on {key}"
                        )
                        if "EXECUTION_REJECT_BURST" not in why.upper():
                            why = f"EXECUTION_REJECT_BURST: {why}"
                        return False, why
                    self._symbol_reject_reasons.pop(key, None)
            self._protection.new_entries_paused = False
            return True, "ok"

    def reject_burst_observability(self, symbol: str | None = None) -> dict[str, Any]:
        """Windowed live-health burst (5/120s). Fill is not required to clear."""
        key = (symbol or "").strip().upper()
        with self._lock:
            self._trim_windows()
            q: deque[datetime]
            if key:
                q = self._symbol_rejects.get(key) or deque()
                self._trim(q, self.reject_window_seconds)
            elif self._symbol_rejects:
                q = max(self._symbol_rejects.values(), key=len)
            else:
                q = self._rejects
            count = len(q)
            active = count >= self.reject_burst_threshold
            remaining = 0.0
            oldest_iso = None
            newest_iso = None
            if q:
                oldest_iso = q[0].isoformat()
                newest_iso = q[-1].isoformat()
                if active:
                    elapsed = (datetime.now(UTC) - q[0]).total_seconds()
                    remaining = max(0.0, float(self.reject_window_seconds) - elapsed)
            last = (
                dict(self._last_execution_reject)
                if self._last_execution_reject
                else None
            )
            return {
                "active": active,
                "count": count,
                "window": float(self.reject_window_seconds),
                "reject_burst_count": count,
                "reject_burst_window_seconds": int(self.reject_window_seconds),
                "last_event": newest_iso,
                "oldest_event": oldest_iso,
                "last_execution_reject": last,
                "clear_condition": (
                    f"windowed rejects expire after {self.reject_window_seconds}s "
                    "(fill not required; not a permanent latch)"
                ),
                "remaining_cooldown": round(remaining, 3),
                "threshold": int(self.reject_burst_threshold),
            }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            allowed, why = self.allow_new_entries()
            per_sym = {
                sym: {
                    "reject_burst": len(q),
                    "paused": len(q) >= self.reject_burst_threshold,
                    "reason": self._symbol_reject_reasons.get(sym),
                }
                for sym, q in self._symbol_rejects.items()
            }
            paused_syms = [s for s, v in per_sym.items() if v.get("paused")]
            if paused_syms and allowed:
                allowed = False
                why = str(per_sym[paused_syms[0]].get("reason") or why)
            self._protection.new_entries_paused = not allowed
            burst = self.reject_burst_observability(
                paused_syms[0] if paused_syms else None
            )
            return {
                "health": self._health.to_dict(),
                "self_protection": self._protection.to_dict(),
                "allow_new_entries": allowed,
                "block_reason": None if allowed else why,
                "symbol_rejects": per_sym,
                "reject_burst": burst,
                "reject_burst_count": burst["reject_burst_count"],
                "reject_burst_window_seconds": burst["reject_burst_window_seconds"],
                "last_execution_reject": burst.get("last_execution_reject"),
            }

    def reset(self) -> None:
        """Clear burst counters and resume entries (unit-test isolation)."""
        with self._lock:
            self._health = DependencyHealth()
            self._protection = SelfProtectionState()
            self._rejects.clear()
            self._slips.clear()
            self._gateway_fails.clear()
            self._emergencies.clear()
            self._symbol_rejects.clear()
            self._symbol_reject_reasons.clear()
            self._last_execution_reject = None

    def _pause(self, reason: str) -> None:
        if reason not in self._protection.reasons:
            self._protection.reasons.append(reason)
            self._protection.reasons = self._protection.reasons[-10:]
        if not self._protection.new_entries_paused:
            self._protection.new_entries_paused = True
            self._protection.paused_at = datetime.now(UTC).isoformat()

    def _maybe_resume_health(self) -> None:
        """Recompute pause from current windows. Fill is not required."""
        allowed, why = self.allow_new_entries()
        if allowed:
            self._protection.new_entries_paused = False
            self._protection.paused_at = None
            self._protection.reasons = [
                r
                for r in self._protection.reasons
                if "Excessive rejects" not in r and "Drawdown" not in r
            ]
        else:
            self._protection.new_entries_paused = True
            if why and why not in self._protection.reasons:
                self._protection.reasons.append(why)
                self._protection.reasons = self._protection.reasons[-10:]

    def _trim_emergencies(self) -> None:
        now = datetime.now(UTC)
        window = timedelta(seconds=self.emergency_window_seconds)
        while self._emergencies and (now - self._emergencies[0][0]) > window:
            self._emergencies.popleft()

    def _trim_windows(self) -> None:
        self._trim(self._rejects, self.reject_window_seconds)
        self._trim(self._slips, self.slippage_window_seconds)
        self._trim(self._gateway_fails, 180)
        self._trim_emergencies()
        self._protection.reject_burst = len(self._rejects) + sum(
            len(v) for v in self._symbol_rejects.values()
        )
        self._protection.slippage_events = len(self._slips)
        self._protection.gateway_instability = len(self._gateway_fails)

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
