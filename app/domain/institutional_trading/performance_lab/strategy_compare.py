"""Strategy comparison with filters — scalping / intradoday / swing."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.performance_lab.opportunity_db import (
    OpportunityOutcome,
    get_opportunity_outcome_store,
)


def _metrics(rows: list[OpportunityOutcome]) -> dict[str, Any]:
    traded = [r for r in rows if r.traded and r.outcome in {"win", "loss"}]
    if not traded:
        return {
            "trades": 0,
            "win_rate": None,
            "profit_factor": None,
            "drawdown": None,
            "avg_rr": None,
            "avg_duration_seconds": None,
            "avg_slippage": None,
        }
    wins = [r for r in traded if r.outcome == "win"]
    losses = [r for r in traded if r.outcome == "loss"]
    win_pnls = [float(r.pnl or 1.0) for r in wins]
    loss_pnls = [abs(float(r.pnl or 1.0)) for r in losses]
    gross_w = sum(win_pnls) if win_pnls else 0.0
    gross_l = sum(loss_pnls) if loss_pnls else 0.0
    rrs = [float(r.expected_rr) for r in traded if r.expected_rr is not None]
    slips = [float(r.slippage) for r in traded if r.slippage is not None]
    # Simple equity path for drawdown proxy using pnl
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in traded:
        equity += float(r.pnl or (1.0 if r.outcome == "win" else -1.0))
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, 100.0 * (peak - equity) / peak)
    return {
        "trades": len(traded),
        "win_rate": round(100.0 * len(wins) / len(traded), 2),
        "profit_factor": round(gross_w / gross_l, 3) if gross_l > 0 else None,
        "drawdown": round(max_dd, 3),
        "avg_rr": round(sum(rrs) / len(rrs), 3) if rrs else None,
        "avg_duration_seconds": None,  # filled when duration samples exist
        "avg_slippage": round(sum(slips) / len(slips), 6) if slips else None,
    }


def compare_strategies(
    *,
    symbol: str | None = None,
    session: str | None = None,
    regime: str | None = None,
) -> dict[str, Any]:
    store = get_opportunity_outcome_store()
    base = store.filtered(symbol=symbol, session=session, regime=regime)
    out: dict[str, Any] = {}
    for name in ("scalping", "intraday", "swing"):
        rows = [r for r in base if (r.strategy or "swing").lower() == name]
        # If strategy not tagged, attribute to swing bucket for untagged traded rows once
        if name == "swing":
            untagged = [r for r in base if not r.strategy]
            rows = rows + untagged
        out[name] = _metrics(rows)
    return {
        "filters": {"symbol": symbol, "session": session, "regime": regime},
        "by_strategy": out,
    }
