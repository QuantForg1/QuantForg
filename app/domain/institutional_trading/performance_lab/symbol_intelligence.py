"""Symbol intelligence rankings."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.domain.institutional_trading.performance_lab.opportunity_db import (
    get_opportunity_outcome_store,
)


def build_symbol_rankings() -> dict[str, Any]:
    rows = [
        r.to_dict() for r in get_opportunity_outcome_store().filtered()
    ]

    by_sym: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_session: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        sym = str(r.get("symbol") or "")
        if not sym:
            continue
        by_sym[sym].append(r)
        sess = str(r.get("session") or "unknown")
        if r.get("pnl") is not None:
            by_session[sess].append(float(r["pnl"]))

    def pf(samples: list[dict[str, Any]]) -> float | None:
        traded = [s for s in samples if s.get("traded") and s.get("outcome") in {"win", "loss"}]
        if not traded:
            return None
        gw = sum(float(s.get("pnl") or 1) for s in traded if s.get("outcome") == "win")
        gl = sum(abs(float(s.get("pnl") or 1)) for s in traded if s.get("outcome") == "loss")
        return round(gw / gl, 3) if gl > 0 else None

    def wr(samples: list[dict[str, Any]]) -> float | None:
        traded = [s for s in samples if s.get("traded") and s.get("outcome") in {"win", "loss"}]
        if not traded:
            return None
        wins = sum(1 for s in traded if s.get("outcome") == "win")
        return round(100.0 * wins / len(traded), 2)

    def avg(key: str, samples: list[dict[str, Any]]) -> float | None:
        vals = [float(s[key]) for s in samples if s.get(key) is not None]
        return round(sum(vals) / len(vals), 6) if vals else None

    symbol_rows = []
    for sym, samples in by_sym.items():
        symbol_rows.append(
            {
                "symbol": sym,
                "profit_factor": pf(samples),
                "win_rate": wr(samples),
                "avg_slippage": avg("slippage", samples),
                "avg_latency_ms": avg("latency_ms", samples),
                "avg_spread": avg("spread", samples),
                "trades": sum(1 for s in samples if s.get("traded")),
            }
        )

    best = sorted(
        [s for s in symbol_rows if s["profit_factor"] is not None],
        key=lambda x: x["profit_factor"],
        reverse=True,
    )
    worst = list(reversed(best))
    slip = sorted(
        [s for s in symbol_rows if s["avg_slippage"] is not None],
        key=lambda x: x["avg_slippage"],
        reverse=True,
    )
    lat = sorted(
        [s for s in symbol_rows if s["avg_latency_ms"] is not None],
        key=lambda x: x["avg_latency_ms"],
        reverse=True,
    )
    spread = sorted(
        [s for s in symbol_rows if s["avg_spread"] is not None],
        key=lambda x: x["avg_spread"],
        reverse=True,
    )

    session_pnl = [
        {"session": k, "total_pnl": round(sum(v), 2), "samples": len(v)}
        for k, v in by_session.items()
    ]
    session_pnl.sort(key=lambda x: x["total_pnl"], reverse=True)

    return {
        "best_symbols": best[:10],
        "worst_symbols": worst[:10],
        "most_profitable_session": session_pnl[0] if session_pnl else None,
        "highest_slippage": slip[:5],
        "highest_latency": lat[:5],
        "highest_spread": spread[:5],
        "lowest_drawdown_proxy": sorted(
            [s for s in symbol_rows if s["win_rate"] is not None],
            key=lambda x: x["win_rate"],
            reverse=True,
        )[:5],
        "sessions": session_pnl,
    }
