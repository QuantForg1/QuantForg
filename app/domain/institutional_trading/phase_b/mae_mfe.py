"""Live MAE/MFE telemetry — observation only. Never mutates SL/TP."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from typing import Any
from uuid import uuid4


@dataclass
class LiveTradeTelemetry:
    trade_id: str
    symbol: str
    strategy: str
    direction: str
    entry_price: float
    entry_timestamp: str
    initial_stop: float | None
    initial_target: float | None
    risk_distance: float | None
    # Running extremes (price)
    extreme_adverse_price: float | None = None
    extreme_favorable_price: float | None = None
    time_to_mae: float | None = None  # seconds from entry
    time_to_mfe: float | None = None
    mae_r: float | None = None
    mfe_r: float | None = None
    last_mark: float | None = None
    last_update: str | None = None
    telemetry_complete: bool = True
    incomplete_reason: str | None = None
    closed: bool = False
    realized_r: float | None = None
    exit_reason: str | None = None
    holding_time_s: float | None = None
    final_mae_r: float | None = None
    final_mfe_r: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "strategy": self.strategy,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "entry_timestamp": self.entry_timestamp,
            "initial_stop": self.initial_stop,
            "initial_target": self.initial_target,
            "MAE": self.extreme_adverse_price,
            "MFE": self.extreme_favorable_price,
            "MAE_R": self.mae_r,
            "MFE_R": self.mfe_r,
            "time_to_MAE": self.time_to_mae,
            "time_to_MFE": self.time_to_mfe,
            "maximum_adverse_R": self.mae_r,
            "maximum_favorable_R": self.mfe_r,
            "realized_R": self.realized_r,
            "exit_reason": self.exit_reason,
            "holding_time": self.holding_time_s,
            "final_MAE_R": self.final_mae_r,
            "final_MFE_R": self.final_mfe_r,
            "closed": self.closed,
            "telemetry_complete": self.telemetry_complete,
            "incomplete_reason": self.incomplete_reason,
            "last_mark": self.last_mark,
            "last_update": self.last_update,
        }


def _r_adverse(direction: str, entry: float, mark: float, risk: float) -> float:
    side = direction.lower()
    if side in {"buy", "long"}:
        return max(0.0, (entry - mark) / risk)
    return max(0.0, (mark - entry) / risk)


def _r_favorable(direction: str, entry: float, mark: float, risk: float) -> float:
    side = direction.lower()
    if side in {"buy", "long"}:
        return max(0.0, (mark - entry) / risk)
    return max(0.0, (entry - mark) / risk)


@dataclass
class LiveMaeMfeTracker:
    open: dict[str, LiveTradeTelemetry] = field(default_factory=dict)
    closed: list[LiveTradeTelemetry] = field(default_factory=list)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def observe_entry(
        self,
        *,
        trade_id: str | None = None,
        symbol: str,
        strategy: str = "",
        direction: str,
        entry_price: float,
        initial_stop: float | None = None,
        initial_target: float | None = None,
        entry_timestamp: str | None = None,
    ) -> LiveTradeTelemetry:
        tid = str(trade_id or uuid4())
        risk = None
        if initial_stop is not None and entry_price:
            risk = abs(float(entry_price) - float(initial_stop))
            if risk <= 0:
                risk = None
        rec = LiveTradeTelemetry(
            trade_id=tid,
            symbol=str(symbol or "").upper(),
            strategy=str(strategy or ""),
            direction=str(direction or ""),
            entry_price=float(entry_price),
            entry_timestamp=entry_timestamp or datetime.now(UTC).isoformat(),
            initial_stop=float(initial_stop) if initial_stop is not None else None,
            initial_target=float(initial_target) if initial_target is not None else None,
            risk_distance=risk,
            telemetry_complete=risk is not None,
            incomplete_reason=None if risk is not None else "missing_stop_or_risk",
        )
        with self._lock:
            self.open[tid] = rec
        return rec

    def observe_mark(
        self,
        trade_id: str,
        *,
        mark_price: float | None,
        now: datetime | None = None,
    ) -> LiveTradeTelemetry | None:
        if mark_price is None:
            with self._lock:
                rec = self.open.get(trade_id)
                if rec is not None:
                    rec.telemetry_complete = False
                    rec.incomplete_reason = rec.incomplete_reason or "missing_quote"
                return rec
        try:
            px = float(mark_price)
        except Exception:
            with self._lock:
                rec = self.open.get(trade_id)
                if rec is not None:
                    rec.telemetry_complete = False
                    rec.incomplete_reason = "malformed_quote"
                return rec
        if px <= 0:
            with self._lock:
                rec = self.open.get(trade_id)
                if rec is not None:
                    rec.telemetry_complete = False
                    rec.incomplete_reason = "non_positive_quote"
                return rec

        moment = now or datetime.now(UTC)
        with self._lock:
            rec = self.open.get(trade_id)
            if rec is None or rec.closed:
                return rec
            rec.last_mark = px
            rec.last_update = moment.isoformat()
            try:
                entry_dt = datetime.fromisoformat(rec.entry_timestamp.replace("Z", "+00:00"))
                age_s = max(0.0, (moment - entry_dt).total_seconds())
            except Exception:
                age_s = 0.0

            side = rec.direction.lower()
            # Adverse extreme
            if rec.extreme_adverse_price is None:
                rec.extreme_adverse_price = px
                rec.time_to_mae = age_s
            else:
                if side in {"buy", "long"} and px < rec.extreme_adverse_price:
                    rec.extreme_adverse_price = px
                    rec.time_to_mae = age_s
                elif side not in {"buy", "long"} and px > rec.extreme_adverse_price:
                    rec.extreme_adverse_price = px
                    rec.time_to_mae = age_s
            # Favorable extreme
            if rec.extreme_favorable_price is None:
                rec.extreme_favorable_price = px
                rec.time_to_mfe = age_s
            else:
                if side in {"buy", "long"} and px > rec.extreme_favorable_price:
                    rec.extreme_favorable_price = px
                    rec.time_to_mfe = age_s
                elif side not in {"buy", "long"} and px < rec.extreme_favorable_price:
                    rec.extreme_favorable_price = px
                    rec.time_to_mfe = age_s

            if rec.risk_distance and rec.risk_distance > 0:
                rec.mae_r = _r_adverse(
                    rec.direction, rec.entry_price, rec.extreme_adverse_price, rec.risk_distance
                )
                rec.mfe_r = _r_favorable(
                    rec.direction,
                    rec.entry_price,
                    rec.extreme_favorable_price,
                    rec.risk_distance,
                )
            else:
                rec.telemetry_complete = False
                rec.incomplete_reason = rec.incomplete_reason or "missing_risk_distance"
            return rec

    def observe_close(
        self,
        trade_id: str,
        *,
        exit_price: float | None = None,
        exit_reason: str | None = None,
        now: datetime | None = None,
    ) -> LiveTradeTelemetry | None:
        moment = now or datetime.now(UTC)
        if exit_price is not None:
            self.observe_mark(trade_id, mark_price=exit_price, now=moment)
        with self._lock:
            rec = self.open.pop(trade_id, None)
            if rec is None:
                return None
            rec.closed = True
            rec.exit_reason = exit_reason
            try:
                entry_dt = datetime.fromisoformat(rec.entry_timestamp.replace("Z", "+00:00"))
                rec.holding_time_s = max(0.0, (moment - entry_dt).total_seconds())
            except Exception:
                rec.holding_time_s = None
            rec.final_mae_r = rec.mae_r
            rec.final_mfe_r = rec.mfe_r
            if (
                exit_price is not None
                and rec.risk_distance
                and rec.risk_distance > 0
            ):
                side = rec.direction.lower()
                if side in {"buy", "long"}:
                    rec.realized_r = (float(exit_price) - rec.entry_price) / rec.risk_distance
                else:
                    rec.realized_r = (rec.entry_price - float(exit_price)) / rec.risk_distance
            elif rec.realized_r is None:
                rec.telemetry_complete = False
                rec.incomplete_reason = rec.incomplete_reason or "missing_exit_or_risk"
            self.closed.append(rec)
            if len(self.closed) > 500:
                self.closed = self.closed[-500:]
            return rec

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "mode": "OBSERVE_ONLY",
                "open": [r.to_dict() for r in self.open.values()],
                "recent_closed": [r.to_dict() for r in self.closed[-20:]],
                "open_count": len(self.open),
                "closed_count": len(self.closed),
            }
