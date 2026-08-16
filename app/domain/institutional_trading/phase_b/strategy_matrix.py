"""Strategy × regime performance matrices with minimum-sample safeguards."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from threading import RLock
from typing import Any


@dataclass
class CellStats:
    trade_count: int = 0
    wins: int = 0
    sum_win: float = 0.0
    sum_loss: float = 0.0  # absolute losses
    sum_r: float = 0.0
    rs: list[float] = field(default_factory=list)
    sum_mae_r: float = 0.0
    sum_mfe_r: float = 0.0
    mae_n: int = 0
    mfe_n: int = 0
    sum_slippage: float = 0.0
    slip_n: int = 0
    sum_exec_q: float = 0.0
    exec_n: int = 0
    max_loss_r: float | None = None

    def add(
        self,
        *,
        realized_r: float | None,
        win: bool | None,
        mae_r: float | None = None,
        mfe_r: float | None = None,
        slippage: float | None = None,
        execution_quality: float | None = None,
    ) -> None:
        self.trade_count += 1
        if realized_r is not None:
            self.sum_r += realized_r
            self.rs.append(realized_r)
            if realized_r < 0:
                self.sum_loss += abs(realized_r)
                if self.max_loss_r is None or realized_r < self.max_loss_r:
                    self.max_loss_r = realized_r
            else:
                self.sum_win += realized_r
        if win is True:
            self.wins += 1
        if mae_r is not None:
            self.sum_mae_r += mae_r
            self.mae_n += 1
        if mfe_r is not None:
            self.sum_mfe_r += mfe_r
            self.mfe_n += 1
        if slippage is not None:
            self.sum_slippage += slippage
            self.slip_n += 1
        if execution_quality is not None:
            self.sum_exec_q += execution_quality
            self.exec_n += 1

    def to_dict(self, *, min_sample: int) -> dict[str, Any]:
        n = self.trade_count
        insufficient = n < int(min_sample)
        avg_r = (self.sum_r / n) if n else None
        median_r = None
        if self.rs:
            s = sorted(self.rs)
            mid = len(s) // 2
            median_r = s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2.0
        avg_win = (self.sum_win / self.wins) if self.wins else None
        losses = n - self.wins
        avg_loss = (self.sum_loss / losses) if losses else None
        profit_factor = (
            (self.sum_win / self.sum_loss) if self.sum_loss > 0 else None
        )
        win_rate = (100.0 * self.wins / n) if n else None
        expectancy = avg_r  # R expectancy proxy
        return {
            "trade_count": n,
            "sample_status": "INSUFFICIENT_SAMPLE" if insufficient else "OK",
            "win_rate": None if insufficient else win_rate,
            "avg_win": None if insufficient else avg_win,
            "avg_loss": None if insufficient else avg_loss,
            "profit_factor": None if insufficient else profit_factor,
            "expectancy": None if insufficient else expectancy,
            "avg_R": None if insufficient else avg_r,
            "median_R": None if insufficient else median_r,
            "max_loss_R": self.max_loss_r,
            "max_drawdown_contribution": self.max_loss_r,
            "MAE_R": (self.sum_mae_r / self.mae_n) if self.mae_n else None,
            "MFE_R": (self.sum_mfe_r / self.mfe_n) if self.mfe_n else None,
            "slippage": (self.sum_slippage / self.slip_n) if self.slip_n else None,
            "execution_quality": (
                self.sum_exec_q / self.exec_n if self.exec_n else None
            ),
        }


@dataclass
class StrategyMatrixStore:
    cells: dict[tuple[str, str, str, str, str], CellStats] = field(
        default_factory=lambda: defaultdict(CellStats)
    )
    min_sample: int = 20
    _lock: RLock = field(default_factory=RLock, repr=False)

    def record(
        self,
        *,
        strategy: str,
        symbol: str,
        regime: str,
        session: str = "",
        direction: str = "",
        realized_r: float | None = None,
        win: bool | None = None,
        mae_r: float | None = None,
        mfe_r: float | None = None,
        slippage: float | None = None,
        execution_quality: float | None = None,
    ) -> None:
        key = (
            str(strategy or "UNKNOWN"),
            str(symbol or "").upper(),
            str(regime or "UNKNOWN"),
            str(session or "UNKNOWN"),
            str(direction or "UNKNOWN").upper(),
        )
        with self._lock:
            self.cells[key].add(
                realized_r=realized_r,
                win=win,
                mae_r=mae_r,
                mfe_r=mfe_r,
                slippage=slippage,
                execution_quality=execution_quality,
            )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            rows = []
            for (strategy, symbol, regime, session, direction), cell in self.cells.items():
                d = cell.to_dict(min_sample=self.min_sample)
                d.update(
                    {
                        "strategy": strategy,
                        "symbol": symbol,
                        "regime": regime,
                        "session": session,
                        "direction": direction,
                    }
                )
                rows.append(d)
        return {
            "min_sample_trades": self.min_sample,
            "cells": rows[:100],
            "cell_count": len(rows),
            "live_weight_change": False,
        }
