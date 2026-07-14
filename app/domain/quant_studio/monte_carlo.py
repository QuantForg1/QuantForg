"""Quant Studio — Monte Carlo from real closed-trade PnL sequences."""

from __future__ import annotations

import math
import random
from typing import Any


def run_monte_carlo(
    trade_pnls: list[float],
    *,
    simulations: int = 1000,
    initial_equity: float = 10_000.0,
    seed: int | None = 42,
) -> dict[str, Any]:
    """Bootstrap reshuffles of observed trade PnLs — never invents trades."""
    if not trade_pnls:
        return {
            "status": "unavailable",
            "reason": "No closed-trade PnLs available for Monte Carlo",
            "data_source": "backtest_trades|history",
            "autonomous_trading": False,
        }
    if simulations < 10:
        simulations = 10
    if simulations > 10_000:
        simulations = 10_000

    rng = random.Random(seed)
    n = len(trade_pnls)
    terminal: list[float] = []
    max_dds: list[float] = []

    for _ in range(simulations):
        path = [rng.choice(trade_pnls) for _ in range(n)]
        equity = initial_equity
        peak = equity
        max_dd = 0.0
        for p in path:
            equity += p
            peak = max(peak, equity)
            if peak > 0:
                max_dd = max(max_dd, (peak - equity) / peak * 100.0)
        terminal.append(equity)
        max_dds.append(max_dd)

    terminal.sort()
    max_dds.sort()

    def pctile(sorted_vals: list[float], q: float) -> float:
        if not sorted_vals:
            return 0.0
        idx = min(len(sorted_vals) - 1, max(0, int(math.floor(q * (len(sorted_vals) - 1)))))
        return sorted_vals[idx]

    mean_eq = sum(terminal) / len(terminal)
    prob_profit = sum(1 for e in terminal if e > initial_equity) / len(terminal)
    worst = terminal[0]
    best = terminal[-1]
    p05 = pctile(terminal, 0.05)
    p50 = pctile(terminal, 0.50)
    p95 = pctile(terminal, 0.95)
    dd_p95 = pctile(max_dds, 0.95)

    return {
        "status": "available",
        "simulations": simulations,
        "sample_trades": n,
        "initial_equity": initial_equity,
        "probability_of_profit": round(prob_profit, 4),
        "mean_terminal_equity": round(mean_eq, 4),
        "worst_case": round(worst, 4),
        "best_case": round(best, 4),
        "confidence": {
            "p05": round(p05, 4),
            "p50": round(p50, 4),
            "p95": round(p95, 4),
            "drawdown_p95_pct": round(dd_p95, 4),
        },
        "risk": {
            "summary": f"95% drawdown ≈ {dd_p95:.2f}% across {simulations} paths",
            "worst_case_equity": round(worst, 4),
        },
        "why": {
            "summary": (
                f"Monte Carlo over {simulations} bootstrap paths of {n} real trade PnLs"
            ),
            "supporting_factors": [
                f"P(profit)={prob_profit:.1%}",
                f"Median terminal equity {p50:.2f}",
                f"Worst path {worst:.2f} / best {best:.2f}",
            ],
        },
        "data_source": "observed_trade_pnls",
        "seed": seed,
        "autonomous_trading": False,
        "advisory_only": True,
    }
