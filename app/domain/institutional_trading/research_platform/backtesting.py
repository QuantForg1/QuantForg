"""Unified backtesting framework — historical / walk-forward / OOS (research only)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True, slots=True)
class TradeBar:
    """Minimal trade outcome for research metrics."""

    pnl: float
    rr: float = 0.0
    win: bool = False


def compute_metrics(trades: Sequence[TradeBar] | Sequence[dict[str, Any]]) -> dict[str, Any]:
    samples: list[TradeBar] = []
    for t in trades:
        if isinstance(t, TradeBar):
            samples.append(t)
        elif isinstance(t, dict):
            pnl = float(t.get("pnl") or 0)
            samples.append(
                TradeBar(
                    pnl=pnl,
                    rr=float(t.get("rr") or 0),
                    win=bool(t.get("win", pnl > 0)),
                )
            )
    if not samples:
        return {
            "trades": 0,
            "win_rate": None,
            "profit_factor": None,
            "drawdown": None,
            "sharpe": None,
            "avg_rr": None,
            "expectancy": None,
            "max_consecutive_losses": 0,
        }
    wins = [s for s in samples if s.win]
    losses = [s for s in samples if not s.win]
    gw = sum(s.pnl for s in wins) if wins else 0.0
    gl = abs(sum(s.pnl for s in losses)) if losses else 0.0
    pf = round(gw / gl, 3) if gl > 0 else None
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    streak = 0
    max_streak = 0
    for s in samples:
        equity += s.pnl
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, 100.0 * (peak - equity) / peak)
        if not s.win:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    pnls = [s.pnl for s in samples]
    mean = sum(pnls) / len(pnls)
    var = sum((p - mean) ** 2 for p in pnls) / len(pnls)
    std = math.sqrt(var) if var > 0 else 0.0
    sharpe = round(mean / std, 3) if std > 0 else None
    rrs = [s.rr for s in samples if s.rr]
    return {
        "trades": len(samples),
        "win_rate": round(100.0 * len(wins) / len(samples), 2),
        "profit_factor": pf,
        "drawdown": round(max_dd, 3),
        "sharpe": sharpe,
        "avg_rr": round(sum(rrs) / len(rrs), 3) if rrs else None,
        "expectancy": round(mean, 4),
        "max_consecutive_losses": max_streak,
    }


def walk_forward(
    trades: Sequence[dict[str, Any]],
    *,
    windows: int = 3,
) -> dict[str, Any]:
    n = len(trades)
    if n < windows or windows < 1:
        return {"windows": [], "summary": compute_metrics(trades)}
    size = max(1, n // windows)
    rows = []
    for i in range(windows):
        chunk = list(trades[i * size : (i + 1) * size if i < windows - 1 else n])
        rows.append({"window": i + 1, "metrics": compute_metrics(chunk)})
    return {"windows": rows, "summary": compute_metrics(trades)}


def out_of_sample(
    trades: Sequence[dict[str, Any]],
    *,
    train_ratio: float = 0.7,
) -> dict[str, Any]:
    n = len(trades)
    cut = max(1, int(n * train_ratio))
    train = list(trades[:cut])
    test = list(trades[cut:]) or list(trades[-1:])
    return {
        "in_sample": compute_metrics(train),
        "out_of_sample": compute_metrics(test),
        "train_size": len(train),
        "test_size": len(test),
    }


def run_backtest_suite(
    trades: Sequence[dict[str, Any]],
    *,
    strategy_id: str = "research",
    sync_live_compare: bool = True,
) -> dict[str, Any]:
    """Research-only suite; optionally updates existing backtest_vs_live store (metrics only)."""
    historical = compute_metrics(trades)
    wf = walk_forward(trades)
    oos = out_of_sample(trades)
    if sync_live_compare:
        try:
            from app.domain.institutional_trading.production_hardening.backtest_live import (
                get_backtest_live_store,
            )

            get_backtest_live_store().upsert(
                strategy_id,
                backtest_win_rate=historical.get("win_rate"),
                backtest_avg_rr=historical.get("avg_rr"),
                backtest_expectancy=historical.get("expectancy"),
            )
        except Exception:
            pass
    return {
        "historical": historical,
        "walk_forward": wf,
        "out_of_sample": oos,
        "affects_production": False,
    }
