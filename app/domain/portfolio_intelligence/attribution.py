"""Performance attribution from real deal rows only."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any


def _parse_time(raw: str | datetime | None) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def _session(hour_utc: int) -> str:
    if 0 <= hour_utc < 7:
        return "asia"
    if 7 <= hour_utc < 12:
        return "london"
    if 12 <= hour_utc < 17:
        return "new_york_overlap"
    if 17 <= hour_utc < 21:
        return "new_york"
    return "off_hours"


def attribute_returns(trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {
            "status": "unavailable",
            "reason": "No trades/deals for attribution",
            "data_source": "history_deals|paper_trades",
            "by_symbol": [],
            "by_strategy": [],
            "by_direction": [],
            "by_session": [],
            "by_week": [],
            "by_month": [],
        }

    buckets: dict[str, dict[str, float]] = {
        "symbol": defaultdict(float),
        "strategy": defaultdict(float),
        "direction": defaultdict(float),
        "session": defaultdict(float),
        "week": defaultdict(float),
        "month": defaultdict(float),
    }

    for t in trades:
        pnl = float(t.get("profit") or t.get("pnl") or 0.0)
        symbol = str(t.get("symbol") or "UNK").upper()
        side = str(t.get("side") or t.get("direction") or "unknown").lower()
        strategy = str(
            t.get("strategy") or t.get("comment") or t.get("magic") or "unspecified"
        )
        buckets["symbol"][symbol] += pnl
        buckets["direction"][side] += pnl
        buckets["strategy"][str(strategy)] += pnl
        ts = _parse_time(t.get("time") or t.get("closed_at") or t.get("opened_at"))
        if ts is not None:
            buckets["session"][_session(ts.utctimetuple().tm_hour)] += pnl
            iso = ts.isocalendar()
            buckets["week"][f"{iso.year}-W{iso.week:02d}"] += pnl
            buckets["month"][f"{ts.year}-{ts.month:02d}"] += pnl

    def _rows(m: dict[str, float]) -> list[dict[str, Any]]:
        return [
            {"key": k, "pnl": round(v, 4)}
            for k, v in sorted(m.items(), key=lambda x: x[1], reverse=True)
        ]

    return {
        "status": "available",
        "data_source": "history_deals|paper_trades",
        "by_symbol": _rows(dict(buckets["symbol"])),
        "by_strategy": _rows(dict(buckets["strategy"])),
        "by_direction": _rows(dict(buckets["direction"])),
        "by_session": _rows(dict(buckets["session"])),
        "by_week": _rows(dict(buckets["week"])),
        "by_month": _rows(dict(buckets["month"])),
    }
