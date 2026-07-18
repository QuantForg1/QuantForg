"""Quant Studio — professional analytics from equity/trades (calculated only)."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any


def _f(raw: Any, default: float = 0.0) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _parse_ts(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def build_professional_analytics(
    *,
    equity_curve: list[dict[str, Any]],
    trades: list[dict[str, Any]],
) -> dict[str, Any]:
    if not equity_curve and not trades:
        return {
            "status": "unavailable",
            "reason": "No equity curve or trades for analytics",
            "autonomous_trading": False,
        }

    # Drawdown timeline
    dd_timeline = [
        {
            "t": p.get("timestamp") or p.get("time") or i,
            "equity": _f(p.get("equity")),
            "drawdown_pct": _f(p.get("drawdown_pct") or p.get("drawdown")),
        }
        for i, p in enumerate(equity_curve)
    ]

    # Performance timeline (equity)
    perf = [{"t": d["t"], "equity": d["equity"]} for d in dd_timeline]

    # Monthly returns from equity points with timestamps
    by_month: dict[str, list[float]] = defaultdict(list)
    for p in equity_curve:
        ts = _parse_ts(p.get("timestamp") or p.get("time"))
        if ts is None:
            continue
        key = f"{ts.year}-{ts.month:02d}"
        by_month[key].append(_f(p.get("equity")))
    monthly: list[dict[str, Any]] = []
    for key in sorted(by_month):
        vals = by_month[key]
        if len(vals) < 2 or vals[0] == 0:
            continue
        monthly.append(
            {
                "month": key,
                "return_pct": round((vals[-1] - vals[0]) / vals[0] * 100.0, 4),
            }
        )

    # Trade distribution + calendar
    pnl_bins: Counter[str] = Counter()
    calendar: dict[str, float] = defaultdict(float)
    pnls = []
    for t in trades:
        pnl = _f(t.get("pnl") or t.get("profit"))
        pnls.append(pnl)
        if pnl > 0:
            pnl_bins["win"] += 1
        elif pnl < 0:
            pnl_bins["loss"] += 1
        else:
            pnl_bins["flat"] += 1
        ts = _parse_ts(t.get("closed_at") or t.get("opened_at") or t.get("time"))
        if ts:
            calendar[ts.date().isoformat()] += pnl

    return {
        "status": "available",
        "drawdown_timeline": dd_timeline,
        "performance_timeline": perf,
        "monthly_returns": monthly,
        "trade_distribution": dict(pnl_bins),
        "trade_calendar": [
            {"date": d, "pnl": round(v, 4)} for d, v in sorted(calendar.items())
        ],
        "pnl_histogram": {
            "count": len(pnls),
            "mean": round(sum(pnls) / len(pnls), 4) if pnls else None,
            "min": round(min(pnls), 4) if pnls else None,
            "max": round(max(pnls), 4) if pnls else None,
        },
        "data_source": "equity_curve|simulated_trades",
        "autonomous_trading": False,
        "advisory_only": True,
    }
