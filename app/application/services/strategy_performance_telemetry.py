"""Read-only strategy performance + signal-to-outcome telemetry.

Observe only. Never mutates Risk, Safety, stops, lots, OMS, or PME.
Never reuses a prior ticket on a rejected / unsubmitted cycle.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

_MAX_TRACES = 500
_MAX_PENDING = 200


def classify_exit_reason(reason: str | None) -> str:
    text = str(reason or "").strip().lower()
    if not text:
        return "OTHER"
    if "trail" in text:
        return "TRAILING"
    if "break_even" in text or "break-even" in text or "break even" in text:
        return "BE"
    if (
        "take_profit" in text
        or "take-profit" in text
        or "take profit" in text
        or text in {"tp", "tp_hit"}
        or text.startswith("tp_")
    ):
        return "TP"
    if (
        "stop_loss" in text
        or "stop-loss" in text
        or "stop loss" in text
        or text in {"sl", "sl_hit"}
        or text.startswith("sl_")
    ):
        return "SL"
    return "OTHER"


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _max_drawdown(pnls: list[float]) -> float | None:
    if not pnls:
        return None
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


@dataclass
class StrategyPerformanceTelemetry:
    """Process-local performance / cycle-efficiency counters."""

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _closed: deque[dict[str, Any]] = field(default_factory=deque, repr=False)
    _pending: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)
    _rejected: deque[dict[str, Any]] = field(default_factory=deque, repr=False)
    _last_cycle_key: str | None = None
    scanner_cycles: int = 0
    scanner_cycles_then_infeasible: int = 0
    downstream_risk_overlay_skipped: int = 0
    feasible_continued_to_risk: int = 0
    min_lot_constraint_count: int = 0
    min_lot_infeasible_count: int = 0
    risk_block_count: int = 0
    safety_block_count: int = 0
    executed_signals: int = 0
    rejected_signals: int = 0
    tp_exits: int = 0
    sl_exits: int = 0
    be_activations: int = 0
    trailing_exits: int = 0

    def __post_init__(self) -> None:
        self._closed = deque(maxlen=_MAX_TRACES)
        self._rejected = deque(maxlen=_MAX_TRACES)

    def note_feasibility(
        self,
        *,
        infeasible: bool,
        skip_expensive_downstream: bool,
        scanner_already_ran: bool = True,
    ) -> None:
        with self._lock:
            if scanner_already_ran:
                self.scanner_cycles += 1
                if infeasible:
                    self.scanner_cycles_then_infeasible += 1
            if skip_expensive_downstream:
                self.downstream_risk_overlay_skipped += 1
                self.min_lot_infeasible_count += 1
            elif not infeasible:
                self.feasible_continued_to_risk += 1

    def observe_cycle(
        self,
        *,
        cycle_key: str | None,
        forwarded_to_oms: bool,
        blocking_stage: str | None,
        fault_code: str | None,
        ticket: Any = None,
        this_cycle_forwarded: bool | None = None,
        signal: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record executed vs rejected. Never attach a stale ticket."""
        submitted = bool(forwarded_to_oms) or bool(this_cycle_forwarded)
        key = str(cycle_key or "").strip() or None
        stage = str(blocking_stage or "").strip().upper()
        code = str(fault_code or "").strip().upper()
        hay = f"{code} {stage}"
        min_lot = "MIN_LOT" in hay
        row = {
            "recorded_at": datetime.now(UTC).isoformat(),
            "forwarded_to_oms": submitted,
            "blocking_stage": stage or None,
            "fault_code": code or None,
            "ticket": str(ticket) if submitted and ticket not in (None, "") else None,
            "stale_ticket_reused": False,
            "signal": dict(signal or {}),
        }
        with self._lock:
            if key and key == self._last_cycle_key:
                return {"deduped": True, **row}
            self._last_cycle_key = key
            if submitted:
                self.executed_signals += 1
            else:
                self.rejected_signals += 1
                self._rejected.append(row)
                if stage == "RISK" or min_lot:
                    self.risk_block_count += 1
                if stage == "SAFETY":
                    self.safety_block_count += 1
                if min_lot:
                    self.min_lot_constraint_count += 1
        return row

    def observe_fill(
        self,
        *,
        ticket: Any,
        signal_quality: Any = None,
        confidence: Any = None,
        direction: Any = None,
        strategy_id: Any = None,
        approved_stop: Any = None,
        approved_lot: Any = None,
        trade_class: Any = None,
        entry: Any = None,
    ) -> dict[str, Any] | None:
        tid = str(ticket or "").strip()
        if not tid:
            return None
        row = {
            "ticket": tid,
            "signal_quality": signal_quality,
            "confidence": confidence,
            "direction": str(direction or "") or None,
            "strategy_id": str(strategy_id or "") or None,
            "approved_stop": str(approved_stop) if approved_stop is not None else None,
            "approved_lot": str(approved_lot) if approved_lot is not None else None,
            "trade_class": str(trade_class or "") or None,
            "entry": str(entry) if entry is not None else None,
            "filled_at": datetime.now(UTC).isoformat(),
        }
        with self._lock:
            self._pending[tid] = row
            if len(self._pending) > _MAX_PENDING:
                oldest = next(iter(self._pending))
                self._pending.pop(oldest, None)
        return row

    def observe_close(
        self,
        *,
        ticket: Any,
        exit_price: Any = None,
        realized_pnl: Any = None,
        realized_r: Any = None,
        exit_reason: Any = None,
        hold_seconds: Any = None,
    ) -> dict[str, Any] | None:
        tid = str(ticket or "").strip()
        if not tid:
            return None
        kind = classify_exit_reason(str(exit_reason or ""))
        pnl = _f(realized_pnl) or 0.0
        rr = _f(realized_r)
        hold = _f(hold_seconds)
        with self._lock:
            pending = dict(self._pending.pop(tid, {}) or {})
            trace = {
                **pending,
                "ticket": tid,
                "exit": str(exit_price) if exit_price is not None else None,
                "realized_pnl": pnl,
                "realized_r": rr,
                "exit_reason": str(exit_reason or "") or None,
                "exit_kind": kind,
                "hold_seconds": hold,
                "won": pnl > 0,
                "closed_at": datetime.now(UTC).isoformat(),
            }
            self._closed.append(trace)
            if kind == "TP":
                self.tp_exits += 1
            elif kind == "SL":
                self.sl_exits += 1
            elif kind == "BE":
                self.be_activations += 1
            elif kind == "TRAILING":
                self.trailing_exits += 1
        return trace

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            closed = list(self._closed)
            rejected = list(self._rejected)
            n = len(closed)
            wins = [t for t in closed if t.get("won")]
            losses = [t for t in closed if not t.get("won")]
            pnls = [float(t.get("realized_pnl") or 0.0) for t in closed]
            rs = [
                float(t["realized_r"])
                for t in closed
                if t.get("realized_r") is not None
            ]
            win_rs = [
                float(t["realized_r"])
                for t in wins
                if t.get("realized_r") is not None
            ]
            loss_rs = [
                abs(float(t["realized_r"]))
                for t in losses
                if t.get("realized_r") is not None
            ]
            holds = [
                float(t["hold_seconds"])
                for t in closed
                if t.get("hold_seconds") is not None
            ]
            total_pnl = sum(pnls)
            win_rate = (len(wins) / n) if n else None
            avg_r = (sum(rs) / len(rs)) if rs else None
            avg_win_r = (sum(win_rs) / len(win_rs)) if win_rs else None
            avg_loss_r = (sum(loss_rs) / len(loss_rs)) if loss_rs else None
            expectancy_r = None
            if (
                win_rate is not None
                and avg_win_r is not None
                and avg_loss_r is not None
            ):
                expectancy_r = (win_rate * avg_win_r) - ((1.0 - win_rate) * avg_loss_r)
            elif win_rate is not None and avg_win_r is not None and not losses:
                expectancy_r = avg_win_r
            elif avg_loss_r is not None and not wins:
                expectancy_r = -avg_loss_r
            gp = sum(float(t.get("realized_pnl") or 0.0) for t in wins)
            gl = abs(sum(float(t.get("realized_pnl") or 0.0) for t in losses))
            profit_factor = (gp / gl) if gl > 0 else None
            return {
                "advisory_only": True,
                "mutates_engines": False,
                "total_trades": n,
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": win_rate,
                "total_realized_pnl": total_pnl,
                "average_r": avg_r,
                "average_winning_r": avg_win_r,
                "average_losing_r": avg_loss_r,
                "expectancy_r": expectancy_r,
                "profit_factor": profit_factor,
                "maximum_drawdown": _max_drawdown(pnls),
                "average_hold_duration_seconds": (
                    (sum(holds) / len(holds)) if holds else None
                ),
                "tp_exits": self.tp_exits,
                "sl_exits": self.sl_exits,
                "be_activations": self.be_activations,
                "trailing_exits": self.trailing_exits,
                "min_lot_constraint_count": self.min_lot_constraint_count,
                "min_lot_infeasible_count": self.min_lot_infeasible_count,
                "risk_block_count": self.risk_block_count,
                "safety_block_count": self.safety_block_count,
                "executed_signals": self.executed_signals,
                "rejected_signals": self.rejected_signals,
                "cycle_efficiency": {
                    "scanner_cycles": self.scanner_cycles,
                    "scanner_cycles_then_infeasible": (
                        self.scanner_cycles_then_infeasible
                    ),
                    "downstream_risk_overlay_skipped": (
                        self.downstream_risk_overlay_skipped
                    ),
                    "feasible_continued_to_risk": self.feasible_continued_to_risk,
                    "scanner_rewritten": False,
                },
                "recent_outcomes": list(reversed(closed[-50:])),
                "recent_rejects": list(reversed(rejected[-50:])),
            }


_STORE: StrategyPerformanceTelemetry | None = None
_STORE_LOCK = threading.Lock()


def get_strategy_performance_telemetry() -> StrategyPerformanceTelemetry:
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = StrategyPerformanceTelemetry()
        return _STORE


def reset_strategy_performance_telemetry() -> None:
    """Test helper."""
    global _STORE
    with _STORE_LOCK:
        _STORE = StrategyPerformanceTelemetry()
