"""Paper trading simulator for VALIDATION_EXECUTION_MODE=paper.

Simulates fills / SL / TP / partial fills and performance metrics.
Never submits broker orders. Never fabricates live tickets.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from threading import Lock
from typing import Any
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _f(raw: Any, default: float = 0.0) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


@dataclass(slots=True)
class PaperPosition:
    position_id: str
    symbol: str
    side: str  # buy | sell
    entry: float
    stop_loss: float
    take_profit: float
    lots: float
    opened_at: str
    status: str = "open"  # open | closed | partial
    filled_lots: float = 0.0
    exit_price: float | None = None
    exit_reason: str = ""
    pnl: float = 0.0
    closed_at: str | None = None
    partial_fills: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "side": self.side,
            "entry": self.entry,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "lots": self.lots,
            "opened_at": self.opened_at,
            "status": self.status,
            "filled_lots": self.filled_lots,
            "exit_price": self.exit_price,
            "exit_reason": self.exit_reason,
            "pnl": round(self.pnl, 4),
            "closed_at": self.closed_at,
            "partial_fills": list(self.partial_fills),
        }


@dataclass(slots=True)
class PaperAccount:
    starting_equity: float = 10_000.0
    equity: float = 10_000.0
    peak_equity: float = 10_000.0
    max_drawdown_pct: float = 0.0
    realized_pnl: float = 0.0
    wins: int = 0
    losses: int = 0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    returns: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "starting_equity": self.starting_equity,
            "equity": round(self.equity, 4),
            "peak_equity": round(self.peak_equity, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "realized_pnl": round(self.realized_pnl, 4),
            "wins": self.wins,
            "losses": self.losses,
            "gross_profit": round(self.gross_profit, 4),
            "gross_loss": round(self.gross_loss, 4),
        }


class PaperTradingEngine:
    """Deterministic paper fill model — next-bar / level hit simulation."""

    POINT_VALUE = 1.0  # XAUUSD contract PnL scale for validation units

    def __init__(self, *, starting_equity: float = 10_000.0) -> None:
        self._lock = Lock()
        self.account = PaperAccount(
            starting_equity=starting_equity,
            equity=starting_equity,
            peak_equity=starting_equity,
        )
        self.positions: dict[str, PaperPosition] = {}
        self.closed: list[PaperPosition] = []
        self._fill_counter = 0

    def simulate_fill(
        self,
        *,
        symbol: str,
        side: str,
        entry: float | str | Decimal,
        stop_loss: float | str | Decimal,
        take_profit: float | str | Decimal,
        lots: float | str | Decimal,
        partial_fill_pct: float = 1.0,
        fill_price: float | str | Decimal | None = None,
    ) -> dict[str, Any]:
        """Open a paper position (optionally partial). No broker call."""
        side_n = str(side).strip().lower()
        entry_f = _f(entry)
        sl = _f(stop_loss)
        tp = _f(take_profit)
        lots_f = _f(lots)
        pct = max(0.0, min(1.0, float(partial_fill_pct)))
        filled = round(lots_f * pct, 4)
        price = _f(fill_price, entry_f)
        pid = f"paper_{uuid4().hex[:12]}"
        pos = PaperPosition(
            position_id=pid,
            symbol=str(symbol).upper(),
            side=side_n,
            entry=price,
            stop_loss=sl,
            take_profit=tp,
            lots=lots_f,
            opened_at=_now_iso(),
            status="partial" if pct < 1.0 else "open",
            filled_lots=filled,
        )
        if pct < 1.0:
            pos.partial_fills.append(
                {
                    "lots": filled,
                    "price": price,
                    "timestamp": _now_iso(),
                    "pct": pct,
                }
            )
        with self._lock:
            self._fill_counter += 1
            self.positions[pid] = pos
        return {
            "simulated": True,
            "broker_submitted": False,
            "position": pos.to_dict(),
            "fill_price": price,
            "filled_lots": filled,
            "partial": pct < 1.0,
        }

    def apply_bar(
        self,
        *,
        high: float,
        low: float,
        close: float | None = None,
        position_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Hit-test open positions against OHLC for SL/TP exits."""
        closed_out: list[dict[str, Any]] = []
        with self._lock:
            targets = (
                [self.positions[position_id]]
                if position_id and position_id in self.positions
                else list(self.positions.values())
            )
            for pos in targets:
                if pos.status == "closed":
                    continue
                exit_price: float | None = None
                reason = ""
                if pos.side == "buy":
                    if low <= pos.stop_loss:
                        exit_price = pos.stop_loss
                        reason = "SL"
                    elif high >= pos.take_profit:
                        exit_price = pos.take_profit
                        reason = "TP"
                else:
                    if high >= pos.stop_loss:
                        exit_price = pos.stop_loss
                        reason = "SL"
                    elif low <= pos.take_profit:
                        exit_price = pos.take_profit
                        reason = "TP"
                if exit_price is None:
                    continue
                pnl = self._pnl(pos, exit_price)
                pos.exit_price = exit_price
                pos.exit_reason = reason
                pos.pnl = pnl
                pos.status = "closed"
                pos.closed_at = _now_iso()
                self._book_pnl(pnl)
                self.closed.append(pos)
                self.positions.pop(pos.position_id, None)
                closed_out.append(pos.to_dict())
            # Mark-to-market residual using close if provided
            if close is not None:
                _ = close  # reserved for equity MTM extension
        return closed_out

    def close_position(
        self,
        position_id: str,
        *,
        exit_price: float,
        reason: str = "manual",
    ) -> dict[str, Any] | None:
        with self._lock:
            pos = self.positions.get(position_id)
            if pos is None:
                return None
            pnl = self._pnl(pos, float(exit_price))
            pos.exit_price = float(exit_price)
            pos.exit_reason = reason
            pos.pnl = pnl
            pos.status = "closed"
            pos.closed_at = _now_iso()
            self._book_pnl(pnl)
            self.closed.append(pos)
            self.positions.pop(position_id, None)
            return pos.to_dict()

    def _pnl(self, pos: PaperPosition, exit_price: float) -> float:
        direction = 1.0 if pos.side == "buy" else -1.0
        return (
            (exit_price - pos.entry)
            * direction
            * pos.filled_lots
            * 100.0
            * self.POINT_VALUE
        )

    def _book_pnl(self, pnl: float) -> None:
        self.account.realized_pnl += pnl
        self.account.equity = self.account.starting_equity + self.account.realized_pnl
        self.account.peak_equity = max(self.account.peak_equity, self.account.equity)
        dd = 0.0
        if self.account.peak_equity > 0:
            dd = (
                (self.account.peak_equity - self.account.equity)
                / self.account.peak_equity
                * 100.0
            )
        self.account.max_drawdown_pct = max(self.account.max_drawdown_pct, dd)
        self.account.returns.append(pnl)
        if pnl >= 0:
            self.account.wins += 1
            self.account.gross_profit += pnl
        else:
            self.account.losses += 1
            self.account.gross_loss += abs(pnl)

    def performance(self) -> dict[str, Any]:
        with self._lock:
            return self._performance_unlocked()

    def _performance_unlocked(self) -> dict[str, Any]:
        closed = list(self.closed)
        acct = self.account
        n = len(closed)
        wins = acct.wins
        losses = acct.losses
        win_rate = (wins / n * 100.0) if n else None
        loss_rate = (losses / n * 100.0) if n else None
        pf = (
            (acct.gross_profit / acct.gross_loss)
            if acct.gross_loss > 0
            else (None if acct.gross_profit <= 0 else float("inf"))
        )
        expectancy = (acct.realized_pnl / n) if n else None
        rets = list(acct.returns)
        sharpe = _sharpe(rets)
        sortino = _sortino(rets)
        return {
            "fills_simulated": self._fill_counter,
            "open_positions": len(self.positions),
            "closed_positions": len(closed),
            "equity": round(acct.equity, 4),
            "drawdown_pct": round(acct.max_drawdown_pct, 4),
            "realized_pnl": round(acct.realized_pnl, 4),
            "win_rate_pct": round(win_rate, 2) if win_rate is not None else None,
            "loss_rate_pct": round(loss_rate, 2) if loss_rate is not None else None,
            "profit_factor": (
                round(pf, 4) if pf is not None and math.isfinite(pf) else pf
            ),
            "expectancy": round(expectancy, 4) if expectancy is not None else None,
            "sharpe": sharpe,
            "sortino": sortino,
            "account": acct.to_dict(),
            "broker_orders_submitted": 0,
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "open": [p.to_dict() for p in self.positions.values()],
                "closed": [p.to_dict() for p in self.closed[-100:]],
                "performance": self._performance_unlocked(),
            }


def _sharpe(returns: list[float]) -> float | None:
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    std = math.sqrt(var) if var > 0 else 0.0
    if std <= 0:
        return None
    return round(mean / std * math.sqrt(len(returns)), 4)


def _sortino(returns: list[float]) -> float | None:
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    downside = [r for r in returns if r < 0]
    if not downside:
        return None
    dvar = sum(r**2 for r in downside) / len(downside)
    dstd = math.sqrt(dvar) if dvar > 0 else 0.0
    if dstd <= 0:
        return None
    return round(mean / dstd * math.sqrt(len(returns)), 4)


_ENGINE: PaperTradingEngine | None = None
_ENGINE_LOCK = Lock()


def get_paper_engine() -> PaperTradingEngine:
    global _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is None:
            _ENGINE = PaperTradingEngine()
        return _ENGINE


def reset_paper_engine_for_tests(
    *, starting_equity: float = 10_000.0
) -> PaperTradingEngine:
    global _ENGINE
    with _ENGINE_LOCK:
        _ENGINE = PaperTradingEngine(starting_equity=starting_equity)
        return _ENGINE
