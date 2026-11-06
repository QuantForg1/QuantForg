"""Cost-aware trade performance metrics — no invented P&L or future leakage."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PerformanceScorecard:
    label: str
    n: int
    wins: int
    losses: int
    flats: int
    win_rate: float
    gross_profit: float
    gross_loss: float
    net_profit: float
    profit_factor: float | None
    avg_win: float
    avg_loss: float
    expectancy: float
    breakeven_win_rate: float | None
    max_consecutive_losses: int
    max_drawdown: float
    classification: str


def _f(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def classify_expectancy(
    *, n: int, expectancy: float, profit_factor: float | None
) -> str:
    """Conservative labels — small samples stay provisional."""
    if n <= 0:
        return "Insufficient data"
    if n < 20:
        if expectancy > 0 and profit_factor is not None and profit_factor > 1.0:
            return "Promising but insufficient sample"
        if expectancy < 0:
            return "Negative expectancy (small sample — provisional)"
        return "Insufficient data"
    if expectancy > 0 and profit_factor is not None and profit_factor > 1.0:
        return "Demonstrated positive expectancy"
    if expectancy < 0:
        return "Negative expectancy"
    return "Insufficient data"


def build_performance_scorecard(
    rows: Sequence[Mapping[str, object]] | Iterable[Mapping[str, object]],
    *,
    label: str,
    pnl_key: str = "net_pnl",
) -> PerformanceScorecard:
    """Build a scorecard from broker-authoritative net P&L rows."""
    material = list(rows)
    pnls = [_f(row.get(pnl_key)) for row in material]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    flats = [p for p in pnls if p == 0]
    n = len(pnls)
    gross_profit = sum(wins)
    gross_loss = sum(losses)
    net = sum(pnls)
    avg_win = (gross_profit / len(wins)) if wins else 0.0
    avg_loss = (gross_loss / len(losses)) if losses else 0.0
    win_rate = (len(wins) / n) if n else 0.0
    if gross_loss < 0:
        profit_factor: float | None = gross_profit / abs(gross_loss)
    elif gross_profit > 0:
        profit_factor = float("inf")
    else:
        profit_factor = 0.0
    expectancy = (net / n) if n else 0.0
    be: float | None = None
    if avg_win > 0 and avg_loss < 0:
        be = abs(avg_loss) / (avg_win + abs(avg_loss))
    max_cl = 0
    cur = 0
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in pnls:
        if pnl < 0:
            cur += 1
            max_cl = max(max_cl, cur)
        else:
            cur = 0
        equity += pnl
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
    pf_out = None if profit_factor == float("inf") else round(profit_factor, 6)
    return PerformanceScorecard(
        label=label,
        n=n,
        wins=len(wins),
        losses=len(losses),
        flats=len(flats),
        win_rate=round(win_rate, 6),
        gross_profit=round(gross_profit, 6),
        gross_loss=round(gross_loss, 6),
        net_profit=round(net, 6),
        profit_factor=pf_out,
        avg_win=round(avg_win, 6),
        avg_loss=round(avg_loss, 6),
        expectancy=round(expectancy, 6),
        breakeven_win_rate=round(be, 6) if be is not None else None,
        max_consecutive_losses=max_cl,
        max_drawdown=round(max_dd, 6),
        classification=classify_expectancy(
            n=n, expectancy=expectancy, profit_factor=pf_out
        ),
    )
