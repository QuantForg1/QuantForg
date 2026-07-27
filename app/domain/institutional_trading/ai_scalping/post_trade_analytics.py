"""Post-trade analytics for closed scalping trades (journal-ready)."""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class PostTradeAnalytics:
    ticket: str | None
    symbol: str
    direction: str
    r_multiple: Decimal | None
    mae_r: Decimal | None
    mfe_r: Decimal | None
    holding_time_minutes: float | None
    spread: str | None
    slippage: str | None
    execution_latency_ms: float | None
    rejection_reason: str | None
    pnl: str | None
    win: bool | None
    expectancy_contribution: Decimal | None
    closed_at: str
    regime: str | None = None
    setup_family: str | None = None
    entry_reason: str | None = None
    exit_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        for k in ("r_multiple", "mae_r", "mfe_r", "expectancy_contribution"):
            if out.get(k) is not None:
                out[k] = str(out[k])
        return out


def compute_post_trade_analytics(
    *,
    ticket: str | None = None,
    symbol: str = "XAUUSD",
    direction: str = "",
    entry: Decimal | None = None,
    exit_price: Decimal | None = None,
    stop_distance: Decimal | None = None,
    mae_price: Decimal | None = None,
    mfe_price: Decimal | None = None,
    opened_at: datetime | None = None,
    closed_at: datetime | None = None,
    spread: Decimal | str | None = None,
    slippage: Decimal | str | None = None,
    execution_latency_ms: float | None = None,
    rejection_reason: str | None = None,
    pnl: Decimal | str | None = None,
    regime: str | None = None,
    setup_family: str | None = None,
    entry_reason: str | None = None,
    exit_reason: str | None = None,
) -> PostTradeAnalytics:
    """Compute R / MAE / MFE / hold time for one closed trade."""
    now = closed_at or datetime.now(UTC)
    r_mult: Decimal | None = None
    mae_r: Decimal | None = None
    mfe_r: Decimal | None = None
    side = (direction or "").lower()
    risk = stop_distance if stop_distance and stop_distance > 0 else None

    if entry is not None and exit_price is not None and risk is not None:
        if side in {"buy", "long"}:
            r_mult = ((exit_price - entry) / risk).quantize(Decimal("0.0001"))
        else:
            r_mult = ((entry - exit_price) / risk).quantize(Decimal("0.0001"))

    if entry is not None and risk is not None and mae_price is not None:
        if side in {"buy", "long"}:
            mae_r = ((entry - mae_price) / risk).quantize(Decimal("0.0001"))
        else:
            mae_r = ((mae_price - entry) / risk).quantize(Decimal("0.0001"))
        if mae_r < 0:
            mae_r = Decimal("0")

    if entry is not None and risk is not None and mfe_price is not None:
        if side in {"buy", "long"}:
            mfe_r = ((mfe_price - entry) / risk).quantize(Decimal("0.0001"))
        else:
            mfe_r = ((entry - mfe_price) / risk).quantize(Decimal("0.0001"))
        if mfe_r < 0:
            mfe_r = Decimal("0")

    hold_m: float | None = None
    if opened_at is not None:
        hold_m = max(0.0, (now - opened_at).total_seconds() / 60.0)

    win: bool | None = None
    if r_mult is not None:
        win = r_mult > 0
    elif pnl is not None:
        try:
            win = Decimal(str(pnl)) > 0
        except Exception:
            win = None

    return PostTradeAnalytics(
        ticket=ticket,
        symbol=symbol,
        direction=direction,
        r_multiple=r_mult,
        mae_r=mae_r,
        mfe_r=mfe_r,
        holding_time_minutes=round(hold_m, 3) if hold_m is not None else None,
        spread=str(spread) if spread is not None else None,
        slippage=str(slippage) if slippage is not None else None,
        execution_latency_ms=execution_latency_ms,
        rejection_reason=rejection_reason,
        pnl=str(pnl) if pnl is not None else None,
        win=win,
        expectancy_contribution=r_mult,
        closed_at=now.isoformat(),
        regime=regime,
        setup_family=setup_family,
        entry_reason=entry_reason,
        exit_reason=exit_reason,
    )


@dataclass
class PostTradeJournal:
    max_records: int = 5000
    _records: list[PostTradeAnalytics] = field(default_factory=list, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(self, analytics: PostTradeAnalytics) -> PostTradeAnalytics:
        with self._lock:
            self._records.append(analytics)
            if len(self._records) > self.max_records:
                self._records = self._records[-self.max_records :]
        return analytics

    def recent(self, *, limit: int = 50, symbol: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._records[-max(1, limit * 4) :])
        if symbol:
            key = symbol.strip().upper()
            rows = [r for r in rows if (r.symbol or "").upper() == key]
        rows = rows[-max(1, limit) :]
        return [r.to_dict() for r in reversed(rows)]

    def performance_snapshot(self, *, symbol: str | None = None) -> dict[str, Any]:
        with self._lock:
            rows = list(self._records)
        if symbol:
            key = symbol.strip().upper()
            rows = [r for r in rows if (r.symbol or "").upper() == key]
        closed = [r for r in rows if r.r_multiple is not None]
        empty = {
            "trades": 0,
            "win_rate": None,
            "average_r": None,
            "profit_factor": None,
            "average_hold_minutes": None,
            "expectancy": None,
            "symbol": symbol.upper() if symbol else None,
            "scope": "symbol" if symbol else "portfolio",
        }
        if not closed:
            return empty
        wins = [r for r in closed if r.win]
        losses = [r for r in closed if r.win is False]
        rs = [float(r.r_multiple or 0) for r in closed]
        avg_r = sum(rs) / len(rs)
        gross_win = sum(float(r.r_multiple or 0) for r in wins if (r.r_multiple or 0) > 0)
        gross_loss = abs(
            sum(float(r.r_multiple or 0) for r in losses if (r.r_multiple or 0) < 0)
        )
        pf = (gross_win / gross_loss) if gross_loss > 0 else None
        holds = [
            float(r.holding_time_minutes)
            for r in closed
            if r.holding_time_minutes is not None
        ]
        return {
            "trades": len(closed),
            "win_rate": round(100.0 * len(wins) / len(closed), 2),
            "average_r": round(avg_r, 4),
            "profit_factor": round(pf, 4) if pf is not None else None,
            "average_hold_minutes": (
                round(sum(holds) / len(holds), 3) if holds else None
            ),
            "expectancy": round(avg_r, 4),
            "symbol": symbol.upper() if symbol else None,
            "scope": "symbol" if symbol else "portfolio",
        }

    def performance_by_symbol(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            symbols = sorted({(r.symbol or "UNKNOWN").upper() for r in self._records})
        return {sym: self.performance_snapshot(symbol=sym) for sym in symbols}


_JOURNAL: PostTradeJournal | None = None
_JLOCK = threading.Lock()


def get_post_trade_journal() -> PostTradeJournal:
    global _JOURNAL
    with _JLOCK:
        if _JOURNAL is None:
            _JOURNAL = PostTradeJournal()
        return _JOURNAL
