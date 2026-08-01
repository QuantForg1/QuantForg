"""Institutional Evidence Dashboard — aggregates from real evidence only."""

from __future__ import annotations

from typing import Any

from app.domain.live_trading_evidence.persistence import utc_iso
from app.domain.live_trading_evidence.rejected_repository import (
    sync_and_list_rejections,
)
from app.domain.live_trading_evidence.trade_repository import sync_and_list_trades


def _num(value: Any) -> float | None:
    if value is None or value == "" or value == "—":
        return None
    try:
        return float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def build_evidence_dashboard() -> dict[str, Any]:
    trades_pack = sync_and_list_trades(limit=200)
    rejects_pack = sync_and_list_rejections(limit=300)
    trades = list(trades_pack.get("trades") or [])
    rejects = list(rejects_pack.get("rejections") or [])

    executed = len(trades)
    rejected = len(rejects)

    slippages: list[float] = []
    latencies: list[float] = []
    by_symbol: dict[str, dict[str, Any]] = {}

    for t in trades:
        if not isinstance(t, dict):
            continue
        s = _num(t.get("slippage"))
        if s is not None:
            slippages.append(s)
        lat = _num(t.get("latency"))
        if lat is not None:
            latencies.append(lat)
        sym = str(t.get("symbol") or "UNKNOWN")
        bucket = by_symbol.setdefault(
            sym, {"symbol": sym, "trades": 0, "pnl_sum": 0.0, "pnl_samples": 0}
        )
        bucket["trades"] += 1
        pnl = _num(t.get("pnl"))
        if pnl is not None:
            bucket["pnl_sum"] += pnl
            bucket["pnl_samples"] += 1

    # AI approval / execution rates from counts when both sides present
    total_decisions = executed + rejected
    ai_approval_rate = (
        round(executed / total_decisions, 6) if total_decisions > 0 else None
    )
    execution_rate = ai_approval_rate  # same evidence basis for this program

    avg_slippage = round(sum(slippages) / len(slippages), 6) if slippages else None
    avg_latency = round(sum(latencies) / len(latencies), 3) if latencies else None

    # Best / worst symbols by average PnL when samples exist
    scored = []
    for bucket in by_symbol.values():
        if bucket["pnl_samples"] > 0:
            scored.append(
                {
                    "symbol": bucket["symbol"],
                    "trades": bucket["trades"],
                    "avg_pnl": round(bucket["pnl_sum"] / bucket["pnl_samples"], 4),
                }
            )
    scored.sort(key=lambda r: r["avg_pnl"], reverse=True)
    best = scored[:5]
    worst = list(reversed(scored[-5:])) if scored else []

    # Execution quality — average of available quality scores on trades
    qualities = [
        q
        for q in (_num(t.get("quality")) for t in trades if isinstance(t, dict))
        if q is not None
    ]
    execution_quality = round(sum(qualities) / len(qualities), 2) if qualities else None

    return {
        "as_of": utc_iso(),
        "executed_trades": executed,
        "rejected_trades": rejected,
        "execution_quality": execution_quality,
        "ai_approval_rate": ai_approval_rate,
        "execution_rate": execution_rate,
        "average_slippage": avg_slippage,
        "average_latency": avg_latency,
        "best_symbols": best,
        "worst_symbols": worst,
        "slippage_samples": len(slippages),
        "latency_samples": len(latencies),
        "fabricated": False,
        "observe_only": True,
        "note": "Null rates/means mean insufficient evidence — never invented",
    }
