"""IRL statistics — computed only on research trade lists."""

from __future__ import annotations

import math
import statistics
from typing import Any


def _f(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _safe_div(n: float | None, d: float | None) -> float | None:
    if n is None or d is None or abs(d) < 1e-12:
        return None
    return n / d


def compute_statistics(
    trades: list[dict[str, Any]],
    *,
    starting_equity: float = 10_000.0,
) -> dict[str, Any]:
    pnls = [_f(t.get("pnl")) or 0.0 for t in trades]
    n = len(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    net = sum(pnls)
    win_rate = (len(wins) / n) if n else None
    loss_rate = (len(losses) / n) if n else None
    pf = _safe_div(gross_profit, gross_loss) if gross_loss > 0 else (None if n == 0 else 999.0)
    avg_win = statistics.mean(wins) if wins else None
    avg_loss = abs(statistics.mean(losses)) if losses else None
    expectancy = None
    if win_rate is not None and avg_win is not None:
        al = avg_loss or 0.0
        expectancy = win_rate * avg_win - (1.0 - win_rate) * al

    rrs = [_f(t.get("rr")) for t in trades if _f(t.get("rr")) is not None]
    avg_rr = statistics.mean(rrs) if rrs else None  # type: ignore[arg-type]
    median_rr = statistics.median(rrs) if rrs else None  # type: ignore[arg-type]

    equity = starting_equity
    peak = equity
    max_dd = 0.0
    curve: list[float] = [equity]
    returns: list[float] = []
    for p in pnls:
        prev = equity
        equity += p
        curve.append(equity)
        peak = max(peak, equity)
        dd = (peak - equity) / peak * 100.0 if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
        if prev > 0:
            returns.append(p / prev)

    sharpe = None
    sortino = None
    if len(returns) >= 2:
        mu = statistics.mean(returns)
        sd = statistics.pstdev(returns)
        if sd > 1e-12:
            sharpe = round(mu / sd * math.sqrt(252), 4)
        downside = [r for r in returns if r < 0]
        if downside:
            dsd = statistics.pstdev(downside) if len(downside) > 1 else abs(downside[0])
            if dsd > 1e-12:
                sortino = round(mu / dsd * math.sqrt(252), 4)

    calmar = None
    if max_dd > 0 and starting_equity > 0:
        calmar = round((net / starting_equity * 100.0) / max_dd, 4)

    recovery = _safe_div(net, max_dd * starting_equity / 100.0) if max_dd > 0 else None

    holds = [_f(t.get("holding_sec")) for t in trades if _f(t.get("holding_sec")) is not None]
    avg_hold = statistics.mean(holds) if holds else None  # type: ignore[arg-type]

    # Exposure ≈ fraction of time in market (sum hold / window estimate)
    total_hold = sum(holds) if holds else 0.0
    window_sec = max((_f(t.get("exit_offset_sec")) or 0.0 for t in trades), default=0.0)
    if window_sec <= 0 and trades:
        window_sec = float(n) * 3600.0
    exposure = _safe_div(float(total_hold), float(window_sec)) if window_sec else None

    return {
        "total_trades": n,
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": round(win_rate * 100.0, 2) if win_rate is not None else None,
        "loss_rate": round(loss_rate * 100.0, 2) if loss_rate is not None else None,
        "profit_factor": round(pf, 4) if pf is not None else None,
        "expectancy": round(expectancy, 4) if expectancy is not None else None,
        "average_rr": round(avg_rr, 4) if avg_rr is not None else None,
        "median_rr": round(median_rr, 4) if median_rr is not None else None,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "maximum_drawdown_pct": round(max_dd, 4),
        "recovery_factor": round(recovery, 4) if recovery is not None else None,
        "average_holding_time_sec": round(avg_hold, 1) if avg_hold is not None else None,
        "trade_frequency": round(n / max(window_sec / 86400.0, 1e-6), 4) if window_sec else n,
        "exposure": round(exposure, 4) if exposure is not None else None,
        "net_profit": round(net, 2),
        "equity_curve": [round(x, 2) for x in curve],
    }
