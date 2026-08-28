"""Sample-honesty helpers local to market-universe research.

Self-contained so production can import this package without untracked
forensics modules. Never displays a win rate without adequate n.
"""

from __future__ import annotations

from typing import Any

from app.domain.market_universe.constants import INSUFFICIENT_SAMPLE, UNKNOWN

DISCLAIMER = "Historical data does not guarantee future profitability."
EARLY_SIGNAL = "EARLY_SIGNAL"
PRELIMINARY = "PRELIMINARY"
MEANINGFUL_RESEARCH = "MEANINGFUL_RESEARCH"
STRONGER_EVIDENCE = "STRONGER_EVIDENCE"
HIGHER_CONFIDENCE = "HIGHER_CONFIDENCE"


def sample_status(n: int) -> str:
    """Research labels only. Never a trading gate."""
    if n <= 0:
        return INSUFFICIENT_SAMPLE
    if n < 10:
        return EARLY_SIGNAL
    if n < 20:
        return PRELIMINARY
    if n < 50:
        return MEANINGFUL_RESEARCH
    if n < 100:
        return STRONGER_EVIDENCE
    return HIGHER_CONFIDENCE


def _as_float(value: Any) -> float | None:
    try:
        if value in (None, "", UNKNOWN):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _metrics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(trades)
    status = sample_status(n)
    empty = {
        "sample_size": n,
        "status": status,
        "TOTAL_TRADES": n,
        "WIN_RATE": UNKNOWN if n == 0 else None,
        "WIN_RATE_DISPLAY": f"INSUFFICIENT SAMPLE n={n}",
        "EXPECTANCY": UNKNOWN,
        "PROFIT_FACTOR": UNKNOWN,
        "MAX_DRAWDOWN": UNKNOWN,
        "disclaimer": DISCLAIMER,
    }
    if n == 0:
        return empty
    pnls = [
        _as_float(
            t.get("net_pnl") if t.get("net_pnl") is not None else t.get("profit_loss")
        )
        or 0.0
        for t in trades
    ]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    win_n = len(wins)
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    wr: Any = UNKNOWN
    display = f"INSUFFICIENT SAMPLE n={n}"
    if n >= 10:
        wr = round((win_n / n) * 100.0, 2)
        display = f"{wr}% (n={n})"
    pf: Any = UNKNOWN
    if gross_loss > 0:
        pf = round(gross_win / gross_loss, 4)
    expectancy: Any = UNKNOWN
    if n >= 10:
        expectancy = round(sum(pnls) / n, 6)
    return {
        **empty,
        "WIN_RATE": wr,
        "WIN_RATE_DISPLAY": display,
        "WIN_COUNT": win_n,
        "LOSS_COUNT": len(losses),
        "EXPECTANCY": expectancy,
        "PROFIT_FACTOR": pf,
    }
