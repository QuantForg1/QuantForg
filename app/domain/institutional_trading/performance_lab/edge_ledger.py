"""Edge Ledger: where the robot actually makes and loses money.

Read-only. Built from closed broker trades (``live_trade_journal``), never from
backtests or model scores. Every bucket carries an evidence verdict so a small
sample is never presented as a proven edge.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

MIN_EVIDENCE_TRADES = 30
MIN_FINDING_TRADES = 10
EDGE_PROFIT_FACTOR = Decimal("1.10")
NO_EDGE_PROFIT_FACTOR = Decimal("1.00")
_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


@dataclass(frozen=True, slots=True)
class ClosedTrade:
    side: str
    opened_at: datetime
    pnl: Decimal
    r_multiple: Decimal | None = None


def session_of(hour_utc: int) -> str:
    """Gold liquidity sessions in UTC (London-New York overlap 12:00-16:00)."""
    if 0 <= hour_utc < 7:
        return "asia"
    if hour_utc < 12:
        return "london"
    if hour_utc < 16:
        return "london_ny_overlap"
    if hour_utc < 21:
        return "new_york"
    return "late"


def _q(value: Decimal | None, places: str = "0.01") -> str | None:
    if value is None:
        return None
    return str(value.quantize(Decimal(places)))


def _mean(values: list[Decimal]) -> Decimal | None:
    return sum(values, Decimal(0)) / len(values) if values else None


def verdict(n: int, profit_factor: Decimal | None) -> str:
    if n < MIN_EVIDENCE_TRADES:
        return "insufficient_data"
    if profit_factor is None:
        return "no_losses_yet"
    if profit_factor >= EDGE_PROFIT_FACTOR:
        return "edge"
    if profit_factor < NO_EDGE_PROFIT_FACTOR:
        return "no_edge"
    return "marginal"


def bucket_stats(trades: list[ClosedTrade]) -> dict[str, Any]:
    n = len(trades)
    wins = [t for t in trades if t.pnl > 0]
    gross_win = sum((t.pnl for t in wins), Decimal(0))
    gross_loss = -sum((t.pnl for t in trades if t.pnl < 0), Decimal(0))
    pf = gross_win / gross_loss if gross_loss > 0 else None
    rs = [t.r_multiple for t in trades if t.r_multiple is not None]
    win_rs = [t.r_multiple for t in wins if t.r_multiple is not None]
    loss_rs = [t.r_multiple for t in trades if t.r_multiple is not None and t.pnl <= 0]
    return {
        "trades": n,
        "win_rate_pct": _q(Decimal(len(wins) * 100) / n, "0.1") if n else None,
        "net_usd": _q(sum((t.pnl for t in trades), Decimal(0))),
        "gross_win_usd": _q(gross_win),
        "gross_loss_usd": _q(gross_loss),
        "profit_factor": _q(pf),
        "avg_r": _q(_mean(rs)),
        "avg_win_r": _q(_mean(win_rs)),
        "avg_loss_r": _q(_mean(loss_rs)),
        "verdict": verdict(n, pf),
    }


def _group(
    trades: Iterable[ClosedTrade], key: Callable[[ClosedTrade], str]
) -> dict[str, list[ClosedTrade]]:
    out: dict[str, list[ClosedTrade]] = {}
    for trade in trades:
        out.setdefault(key(trade), []).append(trade)
    return out


def _breakdown(
    trades: list[ClosedTrade], key: Callable[[ClosedTrade], str]
) -> dict[str, dict[str, Any]]:
    groups = _group(trades, key)
    return {name: bucket_stats(groups[name]) for name in sorted(groups)}


def _findings(dimensions: dict[str, dict[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    """Strongest and weakest buckets with at least MIN_FINDING_TRADES trades."""
    rows: list[dict[str, Any]] = []
    for dimension, buckets in dimensions.items():
        for name, stats in buckets.items():
            if stats["trades"] < MIN_FINDING_TRADES:
                continue
            rows.append(
                {
                    "dimension": dimension,
                    "bucket": name,
                    "trades": stats["trades"],
                    "net_usd": stats["net_usd"],
                    "profit_factor": stats["profit_factor"],
                    "verdict": stats["verdict"],
                }
            )
    rows.sort(key=lambda r: Decimal(r["net_usd"] or "0"))
    return rows


def build_edge_ledger(trades: Iterable[ClosedTrade]) -> dict[str, Any]:
    closed = sorted(trades, key=lambda t: t.opened_at)
    dimensions = {
        "side": _breakdown(closed, lambda t: t.side.upper() or "UNKNOWN"),
        "session_utc": _breakdown(closed, lambda t: session_of(t.opened_at.hour)),
        "hour_utc": _breakdown(closed, lambda t: f"{t.opened_at.hour:02d}"),
        "weekday": _breakdown(closed, lambda t: _WEEKDAYS[t.opened_at.weekday()]),
    }
    return {
        "overall": bucket_stats(closed),
        "first_trade_at": closed[0].opened_at.isoformat() if closed else None,
        "last_trade_at": closed[-1].opened_at.isoformat() if closed else None,
        "evidence_rule": (
            f"verdict needs >= {MIN_EVIDENCE_TRADES} trades; edge = PF >= "
            f"{EDGE_PROFIT_FACTOR}, no_edge = PF < {NO_EDGE_PROFIT_FACTOR}"
        ),
        "breakdowns": dimensions,
        "findings_worst_first": _findings(dimensions),
    }
