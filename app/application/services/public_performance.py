"""Public, audited track record built from closed live trades (read-only).

Shows every closed trade outcome (wins AND losses) with no filtering. Only
aggregate results and per-trade result in R are exposed: no ticket numbers,
account ids, prices or broker details.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.application.services.edge_ledger import (
    _dec,
    _when,
    fetch_closed_rows,
)

_RECENT = 30


def _summ(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [p for r in rows if (p := _dec(r.get("pnl"))) is not None]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_win = sum(wins, Decimal(0))
    gross_loss = -sum(losses, Decimal(0))
    rs = [x for r in rows if (x := _dec(r.get("r_multiple"))) is not None]
    n = len(pnls)
    return {
        "trades": n,
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": n - len(wins) - len(losses),
        "win_rate_pct": round(len(wins) / n * 100, 1) if n else None,
        "net_pnl_usd": float(sum(pnls, Decimal(0))),
        "profit_factor": (
            round(float(gross_win / gross_loss), 2) if gross_loss > 0 else None
        ),
        "avg_r": round(float(sum(rs, Decimal(0)) / len(rs)), 2) if rs else None,
    }


def build_public_performance() -> dict[str, Any]:
    rows = fetch_closed_rows(since=None)
    if rows is None:
        return {"available": False}
    gold = [
        r
        for r in rows
        if str(r.get("symbol") or "").upper().startswith("XAU")
        and _when(r.get("opened_at")) is not None
    ]
    now = datetime.now(UTC)
    d30 = [
        r for r in gold if (_when(r["opened_at"]) or now) >= now - timedelta(days=30)
    ]
    d7 = [r for r in gold if (_when(r["opened_at"]) or now) >= now - timedelta(days=7)]
    recent = sorted(gold, key=lambda r: str(r["opened_at"]), reverse=True)[:_RECENT]
    return {
        "available": True,
        "symbol": "XAUUSD",
        "generated_at": now.replace(microsecond=0).isoformat(),
        "all_time": _summ(gold),
        "last_30_days": _summ(d30),
        "last_7_days": _summ(d7),
        "recent": [
            {
                "opened_at": str(r["opened_at"]),
                "side": str(r.get("side") or "").upper(),
                "result_r": (
                    float(x) if (x := _dec(r.get("r_multiple"))) is not None else None
                ),
                "outcome": (
                    "win"
                    if (p := _dec(r.get("pnl"))) is not None and p > 0
                    else "loss" if p is not None and p < 0 else "breakeven"
                ),
            }
            for r in recent
        ],
        "disclosure": (
            "All closed XAUUSD trades are included, wins and losses. "
            "Past results do not guarantee future results."
        ),
    }
